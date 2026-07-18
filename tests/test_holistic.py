import json
import os
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from viberank.clients import ChatResult
from viberank.debug_questions import FIXED_DEBUG_QUESTIONS
from viberank.evaluation import EvaluationConfig, run_evaluation
from viberank.holistic import (
    HolisticCalibration,
    fit_holistic_calibration,
)


GEN_INTERCEPT = 420.0
GEN_SLOPE = 0.7
GEN_NOISE = 90.0


def synthetic_bank(models: int = 10, prefixes: int = 5, seed: int = 9) -> dict:
    rng = random.Random(seed)
    bank = {}
    for index in range(models):
        elo = 1150.0 + 700.0 * index / (models - 1)
        bank[f"ref-{index}"] = {
            "true_elo": elo,
            "prefix_reads": [
                GEN_INTERCEPT + GEN_SLOPE * elo + rng.gauss(0.0, GEN_NOISE)
                for _ in range(prefixes)
            ],
        }
    return bank


class FitTests(unittest.TestCase):
    def test_fit_recovers_scale_and_measures_noise(self):
        calibration = fit_holistic_calibration(synthetic_bank(), grader_model="test")
        self.assertTrue(calibration.usable)
        self.assertEqual(sorted(calibration.per_prefix), [1, 2, 3, 4, 5])
        for fit in calibration.per_prefix.values():
            self.assertAlmostEqual(fit.slope, GEN_SLOPE, delta=0.2)
            self.assertLess(fit.sigma_elo, 220.0)
        corrected, sigma = calibration.apply(5, GEN_INTERCEPT + GEN_SLOPE * 1500.0)
        self.assertAlmostEqual(corrected, 1500.0, delta=110.0)
        self.assertGreaterEqual(sigma, 50.0)

    def test_apply_falls_back_to_nearest_prefix(self):
        calibration = fit_holistic_calibration(
            synthetic_bank(prefixes=3), grader_model="test"
        )
        corrected_3, _ = calibration.apply(3, 1500.0)
        corrected_9, _ = calibration.apply(9, 1500.0)
        self.assertEqual(corrected_3, corrected_9)

    def test_too_few_models_unusable(self):
        calibration = fit_holistic_calibration(synthetic_bank(models=4))
        self.assertFalse(calibration.usable)

    def test_narrow_spread_unusable(self):
        bank = synthetic_bank()
        for entry in bank.values():
            entry["true_elo"] = 1500.0 + (entry["true_elo"] - 1500.0) * 0.1
        calibration = fit_holistic_calibration(bank)
        self.assertFalse(calibration.usable)

    def test_flat_final_prefix_unusable(self):
        bank = synthetic_bank()
        for entry in bank.values():
            entry["prefix_reads"] = [1500.0] * 5
        calibration = fit_holistic_calibration(bank)
        self.assertFalse(calibration.usable)
        self.assertIn("no positive signal", calibration.reason)

    def test_round_trip(self):
        calibration = fit_holistic_calibration(synthetic_bank(), grader_model="test")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "holistic-calibration.json"
            calibration.save(path)
            loaded = HolisticCalibration.load(path)
        self.assertIsNotNone(loaded)
        self.assertEqual(sorted(loaded.per_prefix), sorted(calibration.per_prefix))
        self.assertAlmostEqual(
            loaded.apply(5, 1500.0)[0], calibration.apply(5, 1500.0)[0], places=1
        )


class FakeLiveClient:
    """Returns an answer for plain calls, a grade for grading calls, and a
    holistic read for transcript calls."""

    def __init__(self):
        self.calls = []

    def complete_with_usage(self, messages, **kwargs):
        prompt = messages[-1]["content"]
        self.calls.append(prompt[:40])
        if not kwargs.get("json_mode"):
            return ChatResult("Turn over A and 7; either could falsify the rule.", 60, 25, 85)
        if "TRANSCRIPT" in prompt:
            return ChatResult(
                json.dumps(
                    {
                        "mean_elo": 1550,
                        "low_90": 1450,
                        "high_90": 1650,
                        "assessment": "solid",
                    }
                ),
                200,
                40,
                240,
            )
        return ChatResult(
            json.dumps(
                {
                    "grade_probabilities": {
                        "wrong": 0.02,
                        "major_error": 0.05,
                        "minor_error": 0.13,
                        "fully_correct": 0.80,
                    },
                    "error_type": "none",
                    "explanation": "Correct.",
                    "confidence": 0.9,
                    "apparent_elo": 1600,
                    "satisfied_criteria": [],
                }
            ),
            120,
            40,
            160,
        )


class LiveIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._previous = os.environ.get("VIBERANK_HOLISTIC_CALIBRATION_PATH")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def tearDown(self):
        if self._previous is None:
            os.environ.pop("VIBERANK_HOLISTIC_CALIBRATION_PATH", None)
        else:
            os.environ["VIBERANK_HOLISTIC_CALIBRATION_PATH"] = self._previous

    def test_active_calibration_makes_holistic_headline(self):
        calibration = fit_holistic_calibration(
            synthetic_bank(), grader_model="mistral-medium-3.5"
        )
        path = Path(self._tmp.name) / "holistic-calibration.json"
        calibration.save(path)
        os.environ["VIBERANK_HOLISTIC_CALIBRATION_PATH"] = str(path)

        client = FakeLiveClient()
        with patch("viberank.evaluation.mistral_client", return_value=client):
            result = run_evaluation(
                EvaluationConfig(
                    provider="mistral",
                    model="mistral-small-latest",
                    questions=2,
                    question_mode="fixed",
                )
            )

        # answer + grade + holistic per question
        self.assertEqual(len(client.calls), 6)
        self.assertTrue(result["holistic_channel"]["active"])
        expected, _ = calibration.apply(2, 1550.0)
        self.assertAlmostEqual(result["estimate"]["mean_elo"], expected, delta=0.11)
        self.assertIn("ordinal_estimate", result)
        self.assertNotEqual(
            result["estimate"]["mean_elo"], result["ordinal_estimate"]["mean_elo"]
        )
        for trace in result["traces"]:
            self.assertIsNotNone(trace["holistic"])
            self.assertEqual(
                trace["posterior"]["mean_elo"], trace["holistic"]["mean_elo"]
            )
        self.assertIn("holistic transcript read", result["method"])

    def test_without_calibration_no_holistic_calls(self):
        os.environ["VIBERANK_HOLISTIC_CALIBRATION_PATH"] = str(
            Path(self._tmp.name) / "missing.json"
        )
        client = FakeLiveClient()
        with patch("viberank.evaluation.mistral_client", return_value=client):
            result = run_evaluation(
                EvaluationConfig(
                    provider="mistral",
                    model="mistral-small-latest",
                    questions=1,
                    question_mode="fixed",
                )
            )
        self.assertEqual(len(client.calls), 2)
        self.assertFalse(result["holistic_channel"]["active"])
        self.assertEqual(result["estimate"], result["ordinal_estimate"])


if __name__ == "__main__":
    unittest.main()

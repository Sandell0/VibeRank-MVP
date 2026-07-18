import json
import math
import os
import random
import tempfile
import unittest
from pathlib import Path

from viberank.calibration import (
    DirectCalibration,
    DirectObservation,
    fit_direct_calibration,
)
from viberank.clients import ChatResult
from viberank.debug_questions import FIXED_DEBUG_QUESTIONS
from viberank.evaluation import EvaluationConfig, run_evaluation
from viberank.grading import MistralGrader
from viberank.irt import EloPosterior


GENERATIVE_INTERCEPT = 380.0
GENERATIVE_SLOPE = 0.62
GENERATIVE_MODEL_BIAS_SD = 80.0
GENERATIVE_ANSWER_SD = 180.0


def synthetic_observations(
    *,
    models: int = 12,
    answers: int = 8,
    seed: int = 5,
    low: float = 950.0,
    high: float = 2150.0,
) -> list[DirectObservation]:
    rng = random.Random(seed)
    observations = []
    for index in range(models):
        elo = low + (high - low) * index / (models - 1)
        bias = rng.gauss(0.0, GENERATIVE_MODEL_BIAS_SD)
        for _ in range(answers):
            latent = elo + bias + rng.gauss(0.0, GENERATIVE_ANSWER_SD)
            observations.append(
                DirectObservation(
                    model=f"model-{index}",
                    true_elo=elo,
                    raw_guess=GENERATIVE_INTERCEPT + GENERATIVE_SLOPE * latent,
                )
            )
    return observations


class FitTests(unittest.TestCase):
    def test_fit_recovers_generative_parameters(self):
        calibration = fit_direct_calibration(synthetic_observations(), grader_model="test")
        self.assertTrue(calibration.usable)
        # Classical calibration fits the measurement model raw = a + b * true,
        # so the slope estimates the generative distortion directly and
        # apply() inverts it without population shrinkage.
        self.assertAlmostEqual(calibration.slope, GENERATIVE_SLOPE, delta=0.12)
        self.assertGreater(calibration.r_squared, 0.5)
        self.assertGreater(calibration.sigma_w_elo, 140.0)
        self.assertLess(calibration.sigma_w_elo, 230.0)
        self.assertGreater(calibration.tau_elo, 25.0)
        self.assertLess(calibration.tau_elo, 180.0)
        # The inverse map is unbiased across the whole range, edges included.
        for elo in (1000.0, 1550.0, 2100.0):
            raw = GENERATIVE_INTERCEPT + GENERATIVE_SLOPE * elo
            self.assertAlmostEqual(calibration.apply(raw), elo, delta=90.0)

    def test_too_few_models_is_unusable(self):
        observations = [
            observation
            for observation in synthetic_observations(models=12)
            if observation.model in {"model-0", "model-5", "model-11"}
        ]
        calibration = fit_direct_calibration(observations)
        self.assertFalse(calibration.usable)
        self.assertIn("calibration models", calibration.reason)

    def test_constant_guesses_are_unusable(self):
        observations = [
            DirectObservation(f"model-{index}", 1000.0 + 200.0 * index, 1400.0)
            for index in range(5)
            for _ in range(3)
        ]
        calibration = fit_direct_calibration(observations)
        self.assertFalse(calibration.usable)

    def test_inverted_signal_is_unusable(self):
        observations = [
            DirectObservation(f"model-{index}", 1000.0 + 200.0 * index, 2200.0 - 200.0 * index)
            for index in range(5)
            for _ in range(3)
        ]
        calibration = fit_direct_calibration(observations)
        self.assertFalse(calibration.usable)
        self.assertIn("no signal", calibration.reason)

    def test_narrow_ability_spread_is_unusable(self):
        observations = [
            DirectObservation(f"model-{index}", 1500.0 + 40.0 * index, 1300.0 + 50.0 * index)
            for index in range(5)
            for _ in range(3)
        ]
        calibration = fit_direct_calibration(observations)
        self.assertFalse(calibration.usable)
        self.assertIn("span", calibration.reason)

    def test_noise_floors_are_enforced(self):
        # Nearly noiseless synthetic reads must still report the floor noise.
        observations = [
            DirectObservation(f"model-{index}", elo, elo + offset)
            for index, elo in enumerate((1000.0, 1250.0, 1500.0, 1750.0, 2000.0))
            for offset in (-2.0, 0.0, 2.0)
        ]
        calibration = fit_direct_calibration(observations)
        self.assertTrue(calibration.usable)
        self.assertGreaterEqual(calibration.sigma_w_elo, 50.0)
        self.assertGreaterEqual(calibration.tau_elo, 25.0)

    def test_save_and_load_round_trip(self):
        calibration = fit_direct_calibration(synthetic_observations(), grader_model="test")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibration.json"
            calibration.save(path)
            loaded = DirectCalibration.load(path)
        self.assertIsNotNone(loaded)
        self.assertTrue(loaded.usable)
        self.assertAlmostEqual(loaded.slope, calibration.slope, places=4)
        self.assertAlmostEqual(loaded.tau_elo, calibration.tau_elo, places=1)

    def test_corrupt_file_loads_as_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibration.json"
            path.write_text("not json", encoding="utf-8")
            self.assertIsNone(DirectCalibration.load(path))


class DirectChannelPosteriorTests(unittest.TestCase):
    def test_single_observation_matches_analytic_gaussian_product(self):
        tau, sigma_w, guess = 80.0, 180.0, 1900.0
        posterior = EloPosterior()
        posterior.observe_direct(guess, tau_elo=tau, sigma_w_elo=sigma_w)
        observation_variance = tau ** 2 + sigma_w ** 2
        prior_variance = 420.0 ** 2
        expected_mean = (
            (1500.0 / prior_variance + guess / observation_variance)
            / (1.0 / prior_variance + 1.0 / observation_variance)
        )
        expected_sd = math.sqrt(1.0 / (1.0 / prior_variance + 1.0 / observation_variance))
        summary = posterior.summary()
        self.assertAlmostEqual(summary.mean_elo, expected_mean, delta=15.0)
        self.assertAlmostEqual(summary.standard_deviation, expected_sd, delta=15.0)

    def test_repeated_observations_shrink_via_shared_bias_formula(self):
        tau, sigma_w = 80.0, 180.0
        posterior = EloPosterior()
        for _ in range(5):
            posterior.observe_direct(1700.0, tau_elo=tau, sigma_w_elo=sigma_w)
        observation_variance = tau ** 2 + sigma_w ** 2 / 5
        prior_variance = 420.0 ** 2
        expected_sd = math.sqrt(1.0 / (1.0 / prior_variance + 1.0 / observation_variance))
        summary = posterior.summary()
        self.assertAlmostEqual(summary.standard_deviation, expected_sd, delta=15.0)
        # tau is a floor: infinitely many guesses cannot beat the shared bias.
        self.assertGreater(summary.standard_deviation, tau * 0.8)

    def test_degenerate_noise_is_rejected(self):
        posterior = EloPosterior()
        with self.assertRaises(ValueError):
            posterior.observe_direct(1700.0, tau_elo=80.0, sigma_w_elo=0.0)

    def test_direct_channel_combines_with_ordinal_updates(self):
        from viberank.domain import Grade

        question = FIXED_DEBUG_QUESTIONS[1]
        ordinal_only = EloPosterior()
        combined = EloPosterior()
        grade = Grade((0.0, 0.02, 0.13, 0.85), "none", "", 0.9)
        ordinal_only.update(question, grade)
        combined.update(question, grade)
        combined.observe_direct(1800.0, tau_elo=80.0, sigma_w_elo=180.0)
        self.assertLess(
            combined.summary().standard_deviation,
            ordinal_only.summary().standard_deviation,
        )


class EvaluationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._previous = os.environ.get("VIBERANK_CALIBRATION_PATH")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def tearDown(self):
        if self._previous is None:
            os.environ.pop("VIBERANK_CALIBRATION_PATH", None)
        else:
            os.environ["VIBERANK_CALIBRATION_PATH"] = self._previous

    def _run(self, seed: int = 11):
        return run_evaluation(
            EvaluationConfig(
                provider="simulation",
                model="synthetic-1600",
                questions=5,
                target_elo=1600.0,
                seed=seed,
            )
        )

    def test_missing_calibration_leaves_channel_off(self):
        os.environ["VIBERANK_CALIBRATION_PATH"] = str(Path(self._tmp.name) / "missing.json")
        result = self._run()
        self.assertFalse(result["direct_channel"]["enabled"])
        for trace in result["traces"]:
            self.assertFalse(trace["direct"]["applied"])
            self.assertIsNone(trace["direct"]["calibrated_guess"])

    def test_unusable_calibration_leaves_channel_off(self):
        path = Path(self._tmp.name) / "calibration.json"
        unusable = fit_direct_calibration([])
        path.write_text(json.dumps(unusable.to_dict()), encoding="utf-8")
        os.environ["VIBERANK_CALIBRATION_PATH"] = str(path)
        result = self._run()
        self.assertFalse(result["direct_channel"]["enabled"])

    def test_usable_calibration_activates_and_tightens(self):
        calibration = fit_direct_calibration(
            synthetic_observations(), grader_model="simulation"
        )
        path = Path(self._tmp.name) / "calibration.json"
        calibration.save(path)

        os.environ["VIBERANK_CALIBRATION_PATH"] = str(Path(self._tmp.name) / "missing.json")
        without = self._run()
        os.environ["VIBERANK_CALIBRATION_PATH"] = str(path)
        with_channel = self._run()

        self.assertTrue(with_channel["direct_channel"]["enabled"])
        self.assertEqual(with_channel["direct_channel"]["observations"], 5)
        for trace in with_channel["traces"]:
            self.assertTrue(trace["direct"]["applied"])
            self.assertIsInstance(trace["direct"]["calibrated_guess"], float)
        self.assertLess(
            with_channel["estimate"]["standard_deviation"],
            without["estimate"]["standard_deviation"],
        )

    def test_grader_mismatch_deactivates_channel(self):
        # A calibration fit against a different grader (here a live one) must
        # not apply to simulation runs, and vice versa.
        calibration = fit_direct_calibration(
            synthetic_observations(), grader_model="mistral-medium-3.5"
        )
        path = Path(self._tmp.name) / "calibration.json"
        calibration.save(path)
        os.environ["VIBERANK_CALIBRATION_PATH"] = str(path)
        result = self._run()
        self.assertFalse(result["direct_channel"]["enabled"])
        self.assertIn("recalibrate", result["direct_channel"]["reason"])


class GraderApparentEloTests(unittest.TestCase):
    class _Client:
        def __init__(self, apparent):
            self.apparent = apparent

        def complete_with_usage(self, *_args, **_kwargs):
            payload = {
                "grade_probabilities": {
                    "wrong": 0.02,
                    "major_error": 0.08,
                    "minor_error": 0.20,
                    "fully_correct": 0.70,
                },
                "error_type": "minor_omission",
                "explanation": "Mostly right.",
                "confidence": 0.8,
                "satisfied_criteria": [],
            }
            if self.apparent is not None:
                payload["apparent_elo"] = self.apparent
            return ChatResult(json.dumps(payload), 10, 10, 20)

    def _grade(self, apparent):
        grader = MistralGrader(self._Client(apparent))  # type: ignore[arg-type]
        grade, _ = grader.grade_with_usage(FIXED_DEBUG_QUESTIONS[0], "an answer")
        return grade

    def test_valid_apparent_elo_is_kept(self):
        self.assertEqual(self._grade(1720).apparent_elo, 1720.0)

    def test_missing_apparent_elo_is_none(self):
        self.assertIsNone(self._grade(None).apparent_elo)

    def test_absurd_apparent_elo_is_discarded(self):
        self.assertIsNone(self._grade(99999).apparent_elo)
        self.assertIsNone(self._grade("not a number").apparent_elo)


if __name__ == "__main__":
    unittest.main()

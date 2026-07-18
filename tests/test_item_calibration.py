import os
import random
import tempfile
import unittest
from pathlib import Path

from viberank.debug_questions import FIXED_DEBUG_QUESTIONS
from viberank.evaluation import EvaluationConfig, run_evaluation
from viberank.irt import gpcm_probabilities
from viberank.item_calibration import (
    ItemCalibration,
    ItemObservation,
    fit_item_calibration,
)


TRUE_DIFFICULTIES = {"item-a": 1200.0, "item-b": 1500.0, "item-c": 1850.0}
TRUE_DISCRIMINATION = 1.3
STEPS = (-160.0, 0.0, 160.0)
THETAS = {
    "m1": 1000.0,
    "m2": 1180.0,
    "m3": 1350.0,
    "m4": 1520.0,
    "m5": 1700.0,
    "m6": 1880.0,
    "m7": 2050.0,
    "m8": 2200.0,
}


def exact_observations() -> list[ItemObservation]:
    """Soft grades equal to the exact GPCM probabilities: the MLE should sit
    at the generative parameters."""
    observations = []
    for model, theta in THETAS.items():
        for item, difficulty in TRUE_DIFFICULTIES.items():
            probs = gpcm_probabilities(theta, difficulty, TRUE_DISCRIMINATION, STEPS)
            observations.append(
                ItemObservation(model, theta, item, tuple(probs))  # type: ignore[arg-type]
            )
    return observations


def sampled_observations(seed: int = 3, draws: int = 2) -> list[ItemObservation]:
    rng = random.Random(seed)
    observations = []
    for model, theta in THETAS.items():
        for item, difficulty in TRUE_DIFFICULTIES.items():
            probs = gpcm_probabilities(theta, difficulty, TRUE_DISCRIMINATION, STEPS)
            for _ in range(draws):
                draw = rng.random()
                cumulative = 0.0
                category = len(probs) - 1
                for index, p in enumerate(probs):
                    cumulative += p
                    if draw <= cumulative:
                        category = index
                        break
                soft = [0.04, 0.04, 0.04, 0.04]
                soft[category] = 0.88
                observations.append(
                    ItemObservation(model, theta, item, tuple(soft))  # type: ignore[arg-type]
                )
    return observations


class FitTests(unittest.TestCase):
    def test_exact_grades_recover_generative_parameters(self):
        calibration = fit_item_calibration(exact_observations(), grader_model="test")
        self.assertTrue(calibration.usable)
        self.assertAlmostEqual(calibration.discrimination, TRUE_DISCRIMINATION, delta=0.1)
        for item, difficulty in TRUE_DIFFICULTIES.items():
            self.assertAlmostEqual(calibration.difficulties[item], difficulty, delta=25.0)
        self.assertEqual(calibration.boundary_items, ())

    def test_sampled_grades_recover_approximately(self):
        calibration = fit_item_calibration(sampled_observations(), grader_model="test")
        self.assertTrue(calibration.usable)
        for item, difficulty in TRUE_DIFFICULTIES.items():
            self.assertAlmostEqual(calibration.difficulties[item], difficulty, delta=220.0)

    def test_too_few_models_unusable(self):
        observations = [o for o in exact_observations() if o.model in {"m1", "m4", "m8"}]
        calibration = fit_item_calibration(observations)
        self.assertFalse(calibration.usable)

    def test_narrow_spread_unusable(self):
        observations = [
            ItemObservation(f"m{i}", 1500.0 + i * 30.0, "item-a", (0.1, 0.2, 0.3, 0.4))
            for i in range(5)
        ]
        calibration = fit_item_calibration(observations)
        self.assertFalse(calibration.usable)
        self.assertIn("span", calibration.reason)

    def test_round_trip_and_apply(self):
        calibration = fit_item_calibration(exact_observations(), grader_model="test")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "item-calibration.json"
            calibration.save(path)
            loaded = ItemCalibration.load(path)
        self.assertIsNotNone(loaded)
        self.assertAlmostEqual(
            loaded.difficulties["item-b"], calibration.difficulties["item-b"], places=1
        )

        renamed = ItemCalibration(
            difficulties={FIXED_DEBUG_QUESTIONS[0].id: 1111.0},
            discrimination=2.0,
            step_offsets_elo=STEPS,
            grader_model="test",
            n_models=8,
            reference_models=("a",),
            elo_spread=1200.0,
            usable=True,
            reason="ok",
        )
        adjusted = renamed.apply_to_questions(FIXED_DEBUG_QUESTIONS)
        self.assertEqual(adjusted[0].difficulty_elo, 1111.0)
        self.assertEqual(adjusted[0].discrimination, 2.0)
        self.assertEqual(adjusted[1].difficulty_elo, FIXED_DEBUG_QUESTIONS[1].difficulty_elo)


class ProductionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._previous = os.environ.get("VIBERANK_ITEM_CALIBRATION_PATH")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def tearDown(self):
        if self._previous is None:
            os.environ.pop("VIBERANK_ITEM_CALIBRATION_PATH", None)
        else:
            os.environ["VIBERANK_ITEM_CALIBRATION_PATH"] = self._previous

    def _run(self):
        return run_evaluation(
            EvaluationConfig(
                provider="simulation",
                model="synthetic-1600",
                questions=5,
                target_elo=1600.0,
                seed=11,
            )
        )

    def _calibration(self, grader: str) -> ItemCalibration:
        fitted = fit_item_calibration(exact_observations(), grader_model=grader)
        return ItemCalibration(
            difficulties={
                question.id: 1000.0 + 150.0 * index
                for index, question in enumerate(FIXED_DEBUG_QUESTIONS)
            },
            discrimination=fitted.discrimination,
            step_offsets_elo=STEPS,
            grader_model=grader,
            n_models=fitted.n_models,
            reference_models=fitted.reference_models,
            elo_spread=fitted.elo_spread,
            usable=True,
            reason="ok",
        )

    def test_matching_calibration_overrides_difficulties(self):
        path = Path(self._tmp.name) / "item-calibration.json"
        self._calibration("simulation").save(path)
        os.environ["VIBERANK_ITEM_CALIBRATION_PATH"] = str(path)
        result = self._run()
        self.assertTrue(result["item_calibration"]["active"])
        self.assertEqual(
            [trace["question"]["difficulty_elo"] for trace in result["traces"]],
            [1000.0, 1150.0, 1300.0, 1450.0, 1600.0],
        )

    def test_grader_mismatch_keeps_original_difficulties(self):
        path = Path(self._tmp.name) / "item-calibration.json"
        self._calibration("mistral-medium-3.5").save(path)
        os.environ["VIBERANK_ITEM_CALIBRATION_PATH"] = str(path)
        result = self._run()
        self.assertFalse(result["item_calibration"]["active"])
        self.assertIn("recalibrate", result["item_calibration"]["reason"])
        self.assertEqual(
            [trace["question"]["difficulty_elo"] for trace in result["traces"]],
            [question.difficulty_elo for question in FIXED_DEBUG_QUESTIONS],
        )


if __name__ == "__main__":
    unittest.main()

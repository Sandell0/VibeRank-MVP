import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from viberank.clients import ChatResult
from viberank.debug_questions import FIXED_DEBUG_QUESTIONS
from viberank.evaluation import (
    DEFAULT_TARGET_MAX_TOKENS,
    EvaluationConfig,
    run_evaluation,
    run_synthetic_validation,
)


class FakeLiveClient:
    def __init__(self):
        self.calls = []

    def complete_with_usage(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if kwargs.get("json_mode"):
            grade = {
                "grade_probabilities": {
                    "wrong": 0.01,
                    "major_error": 0.02,
                    "minor_error": 0.07,
                    "fully_correct": 0.90,
                },
                "error_type": "none",
                "explanation": "The answer is correct and justified.",
                "confidence": 0.95,
                "satisfied_criteria": list(FIXED_DEBUG_QUESTIONS[0].rubric),
            }
            return ChatResult(json.dumps(grade), 120, 40, 160)
        return ChatResult(
            "Turn A and 7: either card could reveal a violation of the one-way rule.",
            60,
            25,
            85,
        )


CALIBRATION_ENV_VARS = (
    "VIBERANK_CALIBRATION_PATH",
    "VIBERANK_ITEM_CALIBRATION_PATH",
    "VIBERANK_HOLISTIC_CALIBRATION_PATH",
)


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        # Isolate from any real calibration artifacts in the working directory.
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._previous = {name: os.environ.get(name) for name in CALIBRATION_ENV_VARS}
        for name in CALIBRATION_ENV_VARS:
            os.environ[name] = str(Path(self._tmp.name) / f"{name}.json")

    def tearDown(self):
        for name, value in self._previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    def test_simulated_evaluation_uses_fixed_questions_in_order(self):
        result = run_evaluation(
            EvaluationConfig(
                provider="simulation",
                model="synthetic-1700",
                questions=5,
                target_elo=1700,
                seed=4,
            )
        )
        self.assertEqual(result["questions"], 5)
        self.assertEqual(result["question_mode"], "fixed")
        self.assertEqual(len(result["traces"]), 5)
        self.assertEqual(
            [trace["question"]["id"] for trace in result["traces"]],
            [question.id for question in FIXED_DEBUG_QUESTIONS],
        )
        self.assertEqual(
            result["traces"][0]["grader_context"]["reference_answer"],
            FIXED_DEBUG_QUESTIONS[0].reference_answer,
        )
        self.assertIn("mean_elo", result["estimate"])
        self.assertIn("absolute_error", result)
        self.assertEqual(set(result["usage"]), {"author", "target", "grader"})
        self.assertEqual(result["usage"]["author"]["total_tokens"], 0)

    def test_authored_simulation_remains_available_for_later(self):
        result = run_evaluation(
            EvaluationConfig(
                provider="simulation",
                model="synthetic-1700",
                questions=3,
                target_elo=1700,
                seed=4,
                question_mode="authored",
            )
        )
        self.assertEqual(result["question_mode"], "authored")
        self.assertTrue(
            all(trace["question"]["id"].startswith("synthetic-generated-") for trace in result["traces"])
        )

    def test_live_fixed_mode_makes_only_target_and_grader_calls(self):
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
        self.assertFalse(client.calls[0][1].get("json_mode", False))
        self.assertEqual(client.calls[0][1]["max_tokens"], DEFAULT_TARGET_MAX_TOKENS)
        self.assertTrue(client.calls[1][1].get("json_mode"))
        self.assertEqual(result["usage"]["author"]["total_tokens"], 0)
        self.assertEqual(result["usage"]["target"]["total_tokens"], 85)
        self.assertEqual(result["usage"]["grader"]["total_tokens"], 160)
        self.assertGreater(result["cost"]["total_usd"], 0)

    def test_synthetic_validation_has_all_three_methods(self):
        result = run_synthetic_validation(questions=2, repeats=2, seed=1)
        self.assertEqual(result["question_mode"], "fixed")
        self.assertEqual(set(result["results"]), {"binary", "ordinal", "ordinal_direct"})
        self.assertTrue(result["direct_calibration"]["usable"])

    def test_fixed_debug_set_has_exactly_five_complete_questions(self):
        self.assertEqual(len(FIXED_DEBUG_QUESTIONS), 5)
        self.assertEqual(
            [question.difficulty_elo for question in FIXED_DEBUG_QUESTIONS],
            [1300.0, 1700.0, 2100.0, 1500.0, 1900.0],
        )
        for question in FIXED_DEBUG_QUESTIONS:
            self.assertTrue(question.reference_answer)
            self.assertGreaterEqual(len(question.rubric), 2)
            self.assertEqual(len(question.grade_anchors), 4)

    def test_invalid_question_count_is_rejected(self):
        with self.assertRaises(ValueError):
            run_evaluation(
                EvaluationConfig(
                    provider="simulation",
                    model="invalid",
                    questions=6,
                    target_elo=1500,
                )
            )


if __name__ == "__main__":
    unittest.main()

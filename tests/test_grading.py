import json
import unittest

from viberank.clients import ChatResult
from viberank.debug_questions import FIXED_DEBUG_QUESTIONS
from viberank.grading import MistralGrader, MistralQuestionAuthor
from viberank.irt import EloPosterior


class FakeClient:
    def complete_with_usage(self, *_args, **_kwargs):
        payload = {
            "title": "Generated logic question",
            "domain": "logic",
            "prompt": "Explain why the conclusion follows.",
            "reference_answer": "The conclusion follows by contradiction.",
            "rubric": ["States the contradiction", "Connects it to the conclusion"],
            "grade_anchors": {
                "wrong": "It does not follow.",
                "major_error": "Claims contradiction without locating it.",
                "minor_error": "Correct argument with a small omission.",
                "fully_correct": "Complete contradiction argument.",
            },
        }
        return ChatResult(json.dumps(payload), 20, 40, 60)


class QuestionAuthorTests(unittest.TestCase):
    def test_author_builds_question_at_current_posterior_median(self):
        author = MistralQuestionAuthor(FakeClient())  # type: ignore[arg-type]
        posterior = EloPosterior().summary()
        question, usage = author.write_with_usage(
            posterior,
            step=1,
            previous_questions=[],
        )
        self.assertEqual(question.difficulty_elo, round(posterior.median_elo / 10) * 10)
        self.assertTrue(question.id.startswith("generated-1-"))
        self.assertEqual(usage["total_tokens"], 60)


class RecordingGraderClient:
    def __init__(self):
        self.messages = []

    def complete_with_usage(self, messages, **_kwargs):
        self.messages = messages
        payload = {
            "grade_probabilities": {
                "wrong": 0.01,
                "major_error": 0.04,
                "minor_error": 0.15,
                "fully_correct": 0.80,
            },
            "error_type": "minor_omission",
            "explanation": "The conclusion is correct but one justification is abbreviated.",
            "confidence": 0.9,
            "satisfied_criteria": ["Selects both A and 7"],
        }
        return ChatResult(json.dumps(payload), 100, 40, 140)


class GraderContextTests(unittest.TestCase):
    def test_grader_receives_every_fixed_question_material(self):
        question = FIXED_DEBUG_QUESTIONS[0]
        client = RecordingGraderClient()
        grader = MistralGrader(client)  # type: ignore[arg-type]
        answer = "Turn A and 7 because either could falsify the rule."

        grade, usage = grader.grade_with_usage(question, answer)

        prompt = client.messages[-1]["content"]
        self.assertIn(question.prompt, prompt)
        self.assertIn(question.reference_answer, prompt)
        for criterion in question.rubric:
            self.assertIn(criterion, prompt)
        for anchor in question.grade_anchors:
            self.assertIn(anchor, prompt)
        self.assertIn(answer, prompt)
        self.assertEqual(grade.error_type, "minor_omission")
        self.assertEqual(usage["total_tokens"], 140)


if __name__ == "__main__":
    unittest.main()

import unittest

from viberank.domain import Grade, Question
from viberank.irt import EloPosterior, category_probabilities


def question(difficulty: float = 1500.0) -> Question:
    return Question(
        id="generated-test",
        title="Generated test question",
        domain="reasoning",
        prompt="Explain the result.",
        reference_answer="A complete result.",
        rubric=("Correct conclusion", "Valid reasoning"),
        grade_anchors=("wrong", "major", "minor", "complete"),
        difficulty_elo=difficulty,
    )


class IrtTests(unittest.TestCase):
    def test_category_probabilities_are_normalized(self):
        generated = question()
        for elo in (900, 1500, 2100):
            probabilities = category_probabilities(generated, elo)
            self.assertAlmostEqual(sum(probabilities), 1.0, places=8)
            self.assertTrue(all(value >= 0 for value in probabilities))

    def test_higher_ability_moves_mass_to_higher_categories(self):
        generated = question()
        low = category_probabilities(generated, 1000)
        high = category_probabilities(generated, 2000)
        low_expected = sum(index * value for index, value in enumerate(low))
        high_expected = sum(index * value for index, value in enumerate(high))
        self.assertGreater(high_expected, low_expected)

    def test_posterior_moves_with_grade(self):
        generated = question()
        low = EloPosterior()
        high = EloPosterior()
        low.update(generated, Grade((0.95, 0.04, 0.01, 0.0), "wrong", "", 1.0))
        high.update(generated, Grade((0.0, 0.01, 0.04, 0.95), "none", "", 1.0))
        self.assertLess(low.summary().mean_elo, 1500)
        self.assertGreater(high.summary().mean_elo, 1500)

    def test_entropy_is_reported(self):
        posterior = EloPosterior()
        before = posterior.entropy_nats
        posterior.update(question(), Grade((0.0, 0.1, 0.8, 0.1), "minor", "", 1.0))
        self.assertGreater(before, posterior.entropy_nats)


if __name__ == "__main__":
    unittest.main()

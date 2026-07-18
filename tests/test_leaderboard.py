import unittest

from viberank.leaderboard import parse_known_models, select_known_models


class LeaderboardTests(unittest.TestCase):
    def test_parse_and_select_known_models(self):
        payload = {
            "models": [
                {
                    "model": "Human Expert",
                    "provider": "Human",
                    "elo": 2502,
                    "theta": 5.7,
                    "num_benchmarks": 72,
                    "effective_benchmarks": 52.5,
                    "se_elo": 48,
                    "rank": 1,
                },
                {
                    "model": "Model A",
                    "provider": "Example",
                    "elo": 2100,
                    "theta": 3.4,
                    "num_benchmarks": 12,
                    "effective_benchmarks": 9.0,
                    "se_elo": 60,
                    "rank": 2,
                },
                {
                    "model": "Sparse Model",
                    "provider": "Example",
                    "elo": 1800,
                    "num_benchmarks": 2,
                    "rank": 3,
                },
            ]
        }
        parsed = tuple(parse_known_models(payload))
        selected = select_known_models(parsed, minimum_benchmarks=5)
        self.assertEqual([model.model for model in selected], ["Model A"])
        self.assertEqual(selected[0].elo, 2100)


if __name__ == "__main__":
    unittest.main()

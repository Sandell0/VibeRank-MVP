import threading
import unittest
from dataclasses import dataclass

import experiments.day_one as d1
from viberank.clients import ProviderError


@dataclass
class FakeResult:
    content: str = "FINAL: 42"
    prompt_tokens: int = 10
    completion_tokens: int = 5
    total_tokens: int = 15


class FakeInner:
    def __init__(self, errors=()):
        self.model = "lab/model:free"
        self.provider_name = "OpenRouter"
        self.calls = []
        self.errors = list(errors)

    def complete_with_usage(self, messages, **kwargs):
        self.calls.append(kwargs)
        if self.errors:
            raise ProviderError(self.errors.pop(0))
        return FakeResult()


class RateLimiterTests(unittest.TestCase):
    def test_third_request_in_a_minute_waits_for_the_window(self):
        now = [0.0]
        slept = []

        def clock():
            return now[0]

        def sleep(seconds):
            slept.append(seconds)
            now[0] += seconds

        limiter = d1.RateLimiter(2, clock=clock, sleep=sleep)
        self.assertEqual(limiter.acquire(), 0.0)
        now[0] = 1.0
        self.assertEqual(limiter.acquire(), 0.0)
        waited = limiter.acquire()
        self.assertGreater(waited, 59.0)
        self.assertEqual(len(slept), 1)
        # The window has rolled: another request goes straight through.
        now[0] += 61.0
        self.assertEqual(limiter.acquire(), 0.0)


class GuardedClientTests(unittest.TestCase):
    def test_clamps_max_tokens_to_the_served_ceiling(self):
        inner = FakeInner()
        client = d1.GuardedClient(inner, max_tokens_cap=8192, sleep=lambda s: None)
        client.complete_with_usage([], max_tokens=60000)
        client.complete_with_usage([], max_tokens=4000)
        client.complete_with_usage([])  # module default (60k) is above the cap too
        self.assertEqual([c["max_tokens"] for c in inner.calls], [8192, 4000, 8192])
        self.assertEqual(client.clamped, 2)

    def test_retries_a_per_minute_429_then_succeeds(self):
        inner = FakeInner(errors=["OpenRouter returned HTTP 429: free-models-per-min"])
        slept = []
        client = d1.GuardedClient(inner, sleep=slept.append)
        result = client.complete_with_usage([{"role": "user", "content": "x"}])
        self.assertEqual(result.content, "FINAL: 42")
        self.assertEqual(client.retries, 1)
        self.assertEqual(slept, [d1.RETRY_429_SLEEPS[0]])

    def test_daily_cap_halts_the_run_and_short_circuits_later_calls(self):
        inner = FakeInner(
            errors=['OpenRouter returned HTTP 429: {"error":{"message":"Rate limit exceeded: free-models-per-day"}}']
        )
        halt = threading.Event()
        client = d1.GuardedClient(inner, halt=halt, sleep=lambda s: None)
        with self.assertRaises(d1.DailyCapReached):
            client.complete_with_usage([])
        self.assertTrue(halt.is_set())
        self.assertNotIsInstance(d1.DailyCapReached("x"), ProviderError)
        calls_before = len(inner.calls)
        with self.assertRaises(d1.DailyCapReached):
            client.complete_with_usage([])
        self.assertEqual(len(inner.calls), calls_before)

    def test_non_429_provider_errors_pass_through_unchanged(self):
        inner = FakeInner(errors=["OpenRouter returned HTTP 502: upstream"])
        client = d1.GuardedClient(inner, sleep=lambda s: None)
        with self.assertRaises(ProviderError):
            client.complete_with_usage([])
        self.assertEqual(client.retries, 0)

    def test_paces_only_when_a_limiter_is_given(self):
        inner = FakeInner()
        waits = iter([0.0, 12.5])
        limiter = type("L", (), {"acquire": lambda self: next(waits)})()
        client = d1.GuardedClient(inner, limiter=limiter)
        client.complete_with_usage([])
        client.complete_with_usage([])
        self.assertEqual(client.waited, 12.5)


class FactoryTests(unittest.TestCase):
    def setUp(self):
        self._openrouter = d1.openrouter_client
        self._mistral = d1.mistral_client
        d1.openrouter_client = lambda model: FakeClientStub("OpenRouter", model)
        d1.mistral_client = lambda model=None: FakeClientStub("Mistral", model or "grader")

    def tearDown(self):
        d1.openrouter_client = self._openrouter
        d1.mistral_client = self._mistral

    def test_parse_slug(self):
        self.assertEqual(d1.parse_slug("mistral/mistral-small-2603"), ("mistral", "mistral-small-2603"))
        self.assertEqual(d1.parse_slug("nvidia/nemotron:free"), ("openrouter", "nvidia/nemotron:free"))

    def test_target_is_guarded_and_shared_others_are_plain(self):
        factory = d1.make_factory("lab/model:free", limiter=None, max_tokens_cap=100, halt=threading.Event())
        target = factory("lab/model:free")
        self.assertIsInstance(target, d1.GuardedClient)
        self.assertIs(factory("lab/model:free"), target)
        author = factory("openai/gpt-5.6-sol")
        self.assertIsInstance(author, FakeClientStub)
        self.assertEqual(author.provider_name, "OpenRouter")
        grader = factory(None)
        self.assertEqual((grader.provider_name, grader.model), ("Mistral", "grader"))

    def test_mistral_direct_slug_routes_to_the_mistral_client(self):
        factory = d1.make_factory("mistral/ministral-8b-2512", limiter=None, max_tokens_cap=None, halt=threading.Event())
        target = factory("mistral/ministral-8b-2512")
        self.assertIsInstance(target, d1.GuardedClient)
        self.assertEqual(target.inner.provider_name, "Mistral")
        self.assertEqual(target.inner.model, "ministral-8b-2512")
        self.assertIs(factory("ministral-8b-2512"), target)
        other = factory("mistral/mistral-medium-3.5")
        self.assertEqual((other.provider_name, other.model), ("Mistral", "mistral-medium-3.5"))


class FakeClientStub:
    def __init__(self, provider_name, model):
        self.provider_name = provider_name
        self.model = model


def _sources(slug):
    wm_bank = [
        {"id": "recall-famous-1-0", "family": "recall", "tier": "famous"},
        {"id": "recall-mid-2-0", "family": "recall", "tier": "mid"},
        {"id": "recall-obscure-3-0", "family": "recall", "tier": "obscure"},
        {"id": "recall-mid-155-1", "family": "recall", "tier": "mid"},  # junk item
        {"id": "retro-x", "family": "retro", "resolution": "YES"},
    ]
    wm_data = {
        "responses": {
            slug: {
                "recall-famous-1-0": {"correct": True},
                "recall-mid-2-0": {"correct": True},
                "recall-obscure-3-0": {"correct": False},
                "recall-mid-155-1": {"correct": False},
            },
            "openai/gpt-5.5": {
                "recall-famous-1-0": {"correct": True},
                "recall-mid-2-0": {"correct": False},
                "recall-obscure-3-0": {"correct": False},
            },
            "anthropic/claude-fable-5": {
                "recall-famous-1-0": {"correct": True},
                "recall-mid-2-0": {"correct": True},
                "recall-obscure-3-0": {"correct": True},
            },
        }
    }
    retro_bank = [
        {"id": "today-a", "question": "A?", "resolution": "YES"},
        {"id": "today-b", "question": "B?", "resolution": "NO"},
        {"id": "today-c", "question": "C?", "resolution": "NO"},
    ]
    import experiments.retro_today as rt

    panel_model = rt.PANEL[0][0]
    retro_data = {
        "responses": {
            panel_model: {"today-c:know": {"extracted": "NO"}},  # leaks c for everyone
            slug: {
                "today-a:know": {"extracted": "UNKNOWN"},
                "today-b:know": {"extracted": "YES"},
                "today-c:know": {"extracted": "NO"},  # correct commit, off the scored set
                "today-a:forecast": {"extracted": "0.8"},
                "today-b:forecast": {"extracted": "0.3"},
            },
        }
    }
    domain_bank = [
        {"id": "inv-1", "family": "inv", "kind": "number"},
        {"id": "inv-2", "family": "inv", "kind": "number"},
        {"id": "audit-1", "family": "audit", "kind": "text"},
    ]
    domain_data = {
        "responses": {
            slug: {
                "answers": {
                    "inv-1": {"family": "inv", "correct": True, "completion_tokens": 400, "extracted": "7"},
                    "inv-2": {"family": "inv", "correct": False, "completion_tokens": None, "extracted": None},
                    "audit-1": {"family": "audit", "correct": True, "completion_tokens": 1200, "extracted": "ok"},
                }
            }
        },
        "usage": {slug: {"prompt": 100, "completion": 1600}},
        "effort_applied": {slug: True},
    }
    frontier_data = {
        "items": {
            "inv-a": {"family": "inversion"},
            "exe-a": {"family": "execution"},
            "inv-b": {"family": "inversion"},
            "inv-c": {"family": "inversion"},
        },
        "responses": {
            slug: {
                "answers": {
                    "inv-a": {"correct": True, "text": "FINAL: 7"},
                    "exe-a": {"correct": False, "text": "FINAL: 9"},
                    # empty at every retry: censored, not wrong
                    "inv-b": {"correct": False, "extracted": None, "text": None},
                }
            }
        },
    }
    return {
        "wm_bank": wm_bank,
        "wm_data": wm_data,
        "retro_bank": retro_bank,
        "retro_data": retro_data,
        "domain_bank": domain_bank,
        "domain_data": domain_data,
        "frontier_data": frontier_data,
        "portfolio_data": {"items": {}, "responses": {}},
        "interview_data": {"models": {}},
    }


class SummaryTests(unittest.TestCase):
    slug = "lab/model:free"

    def test_summary_reads_every_instrument_and_ranks_recall(self):
        summary = d1.summarize(self.slug, sources=_sources(self.slug), facts={"name": "Lab Model"})
        recall = summary["steps"]["recall"]
        self.assertEqual(recall["n"], 3)  # junk item excluded
        self.assertAlmostEqual(recall["accuracy"], 2 / 3)
        self.assertAlmostEqual(recall["zone_famous_mid"], 1.0)
        self.assertEqual((recall["rank"], recall["of"]), (2, 3))

        retro = summary["steps"]["retro"]
        self.assertEqual(retro["frozen_set"], 2)  # today-c leaked by the panel
        self.assertEqual(retro["n"], 2)
        self.assertAlmostEqual(retro["brier"], ((0.8 - 1) ** 2 + (0.3 - 0) ** 2) / 2)
        self.assertEqual(retro["commits"], 2)
        self.assertEqual(retro["correct_commits"], 1)
        self.assertEqual(retro["correct_commits_on_scored_set"], 0)
        self.assertAlmostEqual(retro["base_rate"], 0.5)

        domain = summary["steps"]["domain"]
        self.assertEqual(domain["censored"], 1)
        self.assertEqual((domain["solved"], domain["measurable"]), (2, 2))
        self.assertEqual(domain["ctok_per_solved_median"], 800)
        self.assertTrue(domain["effort_applied"])
        self.assertEqual(domain["families"]["inv"], {"solved": 1, "n": 1, "censored": 1})

        frontier = summary["steps"]["frontier"]
        self.assertEqual((frontier["solved"], frontier["n"]), (1, 2))
        self.assertEqual(frontier["censored"], 1)
        self.assertEqual((frontier["attempted"], frontier["bank"]), (3, 4))
        self.assertEqual(frontier["families"]["inversion"], {"solved": 1, "n": 1, "censored": 1})
        self.assertIsNone(summary["steps"]["portfolio"])
        self.assertIsNone(summary["steps"]["interview"])

        markdown = d1.render_markdown(summary)
        self.assertIn("# Day-one battery: lab/model:free", markdown)
        self.assertIn("**Lab Model** (lab/model:free) - recall 0.67", markdown)
        self.assertIn("| inv | 1 | 1 | 1 |", markdown)
        self.assertIn("frontier ladder 1/2, 1 censored, 1 unattempted", markdown)
        self.assertIn("3/4 items attempted, 1 censored", markdown)
        self.assertIn("| inversion | 1 | 1 | 1 |", markdown)

    def test_summary_without_results_says_so(self):
        summary = d1.summarize("lab/never-run", sources=_sources(self.slug))
        self.assertTrue(all(v is None for v in summary["steps"].values()))
        self.assertIn("no results on file yet", d1.dossier_line(summary))


class TolerantLadderTests(unittest.TestCase):
    def test_exhausted_cell_is_censored_and_the_ladder_continues(self):
        calls = []

        class Ladder:
            @staticmethod
            def ask(client, prompt, label):
                calls.append(label)
                if "inv-14-0" in label:
                    raise RuntimeError(f"{label}: retries exhausted")
                return "FINAL: 5", 10, 20

        censored = set()
        ask = d1.tolerant_ask(Ladder, censored)
        self.assertEqual(ask(None, "p", "lab/model inv-4-0"), ("FINAL: 5", 10, 20))
        self.assertEqual(ask(None, "p", "lab/model inv-14-0"), ("", 0, 0))
        self.assertEqual(censored, {"inv-14-0"})
        self.assertEqual(len(calls), 2)

    def test_daily_cap_still_stops_the_ladder(self):
        class Ladder:
            @staticmethod
            def ask(client, prompt, label):
                raise d1.DailyCapReached("cap")

        with self.assertRaises(d1.DailyCapReached):
            d1.tolerant_ask(Ladder, set())(None, "p", "lab/model inv-4-0")

    def test_mark_censored_rewrites_only_the_named_cells(self):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "frontier_ladder_data.json"
            path.write_text(
                json.dumps(
                    {
                        "items": {},
                        "responses": {
                            "lab/model": {
                                "answers": {
                                    "inv-4-0": {"correct": True, "extracted": "5", "text": "FINAL: 5"},
                                    "inv-14-0": {"correct": False, "extracted": None, "text": ""},
                                }
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            d1.mark_censored(path, "lab/model", {"inv-14-0", "never-stored"})
            answers = json.loads(path.read_text(encoding="utf-8"))["responses"]["lab/model"]["answers"]
            self.assertEqual(answers["inv-14-0"], {"correct": False, "extracted": None, "text": None})
            self.assertEqual(answers["inv-4-0"]["text"], "FINAL: 5")
            self.assertNotIn("never-stored", answers)

    def test_ladder_coverage_reads_partial_runs(self):
        import json
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "frontier_ladder_data.json").write_text(
                json.dumps(
                    {
                        "items": {f"i{k}": {"family": "inversion"} for k in range(24)},
                        "responses": {"lab/model": {"answers": {"i0": {"correct": True}}}},
                    }
                ),
                encoding="utf-8",
            )
            original = d1.EXP
            d1.EXP = Path(tmp)
            try:
                self.assertEqual(d1.coverage("frontier", "lab/model"), (1, 24))
                self.assertEqual(d1.coverage("frontier", "lab/other"), (0, 24))
            finally:
                d1.EXP = original
        self.assertEqual(d1.outcome_label("ok", (1, 24)), "partial (1/24, re-run to continue)")
        self.assertEqual(d1.outcome_label("ok", (24, 24)), "ok (24/24)")
        self.assertEqual(d1.outcome_label("stopped: cap", (3, 24)), "stopped: cap (3/24)")
        self.assertEqual(d1.outcome_label("ok", None), "ok")


class RetryPolicyTests(unittest.TestCase):
    def test_free_routes_keep_one_retry_and_paid_routes_keep_three(self):
        import experiments.frontier_ladder as fl
        import experiments.worldmodel_smoke as ws

        saved = (fl.RETRY_SLEEPS, ws.RETRY_SLEEPS)
        try:
            untouched = d1.apply_retry_policy(False)
            self.assertEqual(untouched["frontier"], (5, 15, 30))
            self.assertEqual(fl.RETRY_SLEEPS, (5, 15, 30))
            applied = d1.apply_retry_policy(True)
            self.assertEqual(set(applied), {"domain", "frontier", "portfolio", "retro", "recall"})
            self.assertTrue(all(v == (5,) for v in applied.values()))
            self.assertEqual(ws.RETRY_SLEEPS, (5,))
        finally:
            fl.RETRY_SLEEPS, ws.RETRY_SLEEPS = saved
            d1.apply_retry_policy(False)


class PlanTests(unittest.TestCase):
    def test_plan_lists_steps_calls_and_pacing(self):
        lines = d1.plan_lines(
            "lab/model:free",
            ["recall", "domain"],
            rpm=18,
            cap=32768,
            price=(0.0, 0.0),
            cost_ceiling=25.0,
            keys={"OPENROUTER_API_KEY": True, "MISTRAL_API_KEY": False},
            facts={"name": "Lab", "created": "2026-09-01", "context_length": 1, "max_completion_tokens": 32768,
                   "supports_reasoning": True, "price_per_m": (0.0, 0.0)},
        )
        text = "\n".join(lines)
        self.assertIn("recall (86), domain (80) = up to 166 calls", text)
        self.assertIn("pacing: 18 req/min", text)
        self.assertIn("MISTRAL_API_KEY MISSING", text)
        self.assertIn("pacing floor: ~9 min", text)

    def test_safe_name(self):
        self.assertEqual(d1.safe_name("nvidia/nemotron-3.5:free"), "nvidia__nemotron-3.5_free")


if __name__ == "__main__":
    unittest.main()

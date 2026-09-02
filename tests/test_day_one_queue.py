import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import experiments.day_one as d1
import experiments.day_one_queue as q


def _summary(slug, results):
    return {"slug": slug, "catalog": {"name": slug}, "step_results": results,
            "steps": {k: None for k in ("recall", "retro", "domain", "frontier", "portfolio", "interview")}}


class QueueTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self._runs_dir = d1.RUNS_DIR
        d1.RUNS_DIR = tmp / "runs"
        d1.RUNS_DIR.mkdir()
        self.queue = {"models": []}
        self.saved = 0

    def tearDown(self):
        d1.RUNS_DIR = self._runs_dir
        self._tmp.cleanup()

    def _save(self, queue):
        self.saved += 1

    def _write_summary(self, slug, results):
        (d1.RUNS_DIR / f"{d1.safe_name(slug)}.json").write_text(
            json.dumps(_summary(slug, results)), encoding="utf-8")

    def test_add_is_idempotent_and_keeps_order(self):
        self.assertEqual(q.add(self.queue, ["a/one:free", "b/two:free"]), ["a/one:free", "b/two:free"])
        self.assertEqual(q.add(self.queue, ["b/two:free", " ", "c/three:free"]), ["c/three:free"])
        self.assertEqual([m["slug"] for m in self.queue["models"]], ["a/one:free", "b/two:free", "c/three:free"])
        self.assertTrue(all(m["status"] == "pending" for m in self.queue["models"]))

    def test_pass_marks_done_and_incomplete_from_the_summary(self):
        q.add(self.queue, ["a/one:free", "b/two:free"])
        ok = {s: f"ok ({n}/{n})" for s, n in zip(d1.CORE_STEPS, (86, 55, 80, 24, 30))}
        partial = dict(ok, frontier="partial (8/24, re-run to continue)")

        def runner(slug):
            self._write_summary(slug, ok if slug == "a/one:free" else partial)
            return 0

        outcome = q.run_pass(self.queue, max_models=None, wait_for_cap=False,
                             runner=runner, sleeper=lambda: None, save=self._save)
        self.assertEqual(outcome, "idle")
        one, two = self.queue["models"]
        self.assertEqual((one["status"], one["attempts"], one["last_exit"]), ("done", 1, 0))
        self.assertEqual((two["status"], two["attempts"]), ("incomplete", 1))
        self.assertIn("frontier: partial", two["note"])
        self.assertGreater(self.saved, 0)

    def test_day_cap_stops_the_pass_without_charging_an_attempt(self):
        q.add(self.queue, ["a/one:free", "b/two:free"])
        calls = []

        def runner(slug):
            calls.append(slug)
            return q.CAP_EXIT

        outcome = q.run_pass(self.queue, max_models=None, wait_for_cap=False,
                             runner=runner, sleeper=lambda: None, save=self._save)
        self.assertEqual(outcome, "cap")
        self.assertEqual(calls, ["a/one:free"])
        one = self.queue["models"][0]
        self.assertEqual((one["status"], one["attempts"], one["note"]), ("incomplete", 0, "stopped at the day cap"))
        self.assertEqual(self.queue["models"][1]["status"], "pending")

    def test_wait_for_cap_sleeps_then_finishes_the_same_model(self):
        q.add(self.queue, ["a/one:free"])
        codes = iter([q.CAP_EXIT, 0])
        slept = []

        def runner(slug):
            code = next(codes)
            if code == 0:
                self._write_summary(slug, {s: "ok (1/1)" for s in d1.CORE_STEPS})
            return code

        outcome = q.run_pass(self.queue, max_models=None, wait_for_cap=True,
                             runner=runner, sleeper=lambda: slept.append(1), save=self._save)
        self.assertEqual(outcome, "idle")
        self.assertEqual(slept, [1])
        self.assertEqual((self.queue["models"][0]["status"], self.queue["models"][0]["attempts"]), ("done", 1))

    def test_repeated_cap_trips_stop_for_a_human(self):
        q.add(self.queue, ["a/one:free"])
        outcome = q.run_pass(self.queue, max_models=None, wait_for_cap=True,
                             runner=lambda slug: q.CAP_EXIT, sleeper=lambda: None, save=self._save)
        self.assertEqual(outcome, "stopped")
        self.assertEqual(self.queue["models"][0]["attempts"], 0)

    def test_max_models_and_max_attempts(self):
        q.add(self.queue, ["a/one:free", "b/two:free"])
        self.queue["models"][0]["attempts"] = q.MAX_ATTEMPTS
        self.queue["models"][0]["status"] = "incomplete"
        self.queue["models"][0]["note"] = "domain: error: boom"
        calls = []

        def runner(slug):
            calls.append(slug)
            self._write_summary(slug, {s: "ok (1/1)" for s in d1.CORE_STEPS})
            return 0

        outcome = q.run_pass(self.queue, max_models=1, wait_for_cap=False,
                             runner=runner, sleeper=lambda: None, save=self._save)
        self.assertEqual(outcome, "idle")  # the failed one is skipped, the other finishes the pass
        self.assertEqual(self.queue["models"][0]["status"], "failed")
        self.assertIn("gave up after 3 attempts", self.queue["models"][0]["note"])
        self.assertEqual(calls, ["b/two:free"])
        q.add(self.queue, ["c/three:free"])
        outcome = q.run_pass(self.queue, max_models=0, wait_for_cap=False,
                             runner=runner, sleeper=lambda: None, save=self._save)
        self.assertEqual(outcome, "limit")

    def test_classify_reads_missing_steps_and_summary_absence(self):
        self.assertEqual(q.classify("never/ran")[0], "incomplete")
        self._write_summary("x/y", {"recall": "ok (86/86)"})
        status, note = q.classify("x/y")
        self.assertEqual(status, "incomplete")
        self.assertIn("steps not run: retro", note)

    def test_cap_reset_wait_targets_the_next_utc_day(self):
        at = datetime(2026, 9, 2, 23, 30, tzinfo=timezone.utc)
        self.assertAlmostEqual(q.seconds_until_cap_reset(at), 30 * 60 + q.CAP_RESET_MARGIN_MIN * 60)
        self.assertGreaterEqual(q.seconds_until_cap_reset(datetime(2026, 9, 2, 0, 0, tzinfo=timezone.utc)), 60)

    def test_status_render_counts(self):
        q.add(self.queue, ["a/one:free"])
        text = q.render_status(self.queue)
        self.assertIn("a/one:free", text)
        self.assertIn("pending 1", text)


if __name__ == "__main__":
    unittest.main()

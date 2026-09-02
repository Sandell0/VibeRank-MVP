"""Day-one queue: work through free models one at a time, slowly.

The free-route caps are per account (20 req/min, 1,000 req/day on
OpenRouter `:free` routes), so models run strictly one after another; a
full battery is ~340 requests, so two fit in a day. The queue lives in
experiments/day_one_runs/queue.json and survives restarts: re-running the
command continues with the next pending model, a model whose run was cut
short (daily cap, provider errors, censored steps) is retried on a later
pass, and a model that fails MAX_ATTEMPTS times is parked as `failed` for a
human to look at.

    python -m experiments.day_one_queue --add <slug> [<slug> ...]
    python -m experiments.day_one_queue --status
    python -m experiments.day_one_queue --run                   # one pass
    python -m experiments.day_one_queue --run --wait-for-cap    # sleep past the day cap
    python -m experiments.day_one_queue --run --passes 0 --wait-for-cap   # until done
    python -m experiments.day_one_queue --run --max-models 2

Each model runs as its own `python -m experiments.day_one <slug>` process;
its output goes to work/day_one_queue/<slug>.<timestamp>.log (gitignored).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import experiments.day_one as d1

ROOT = d1.EXP.parent
QUEUE_PATH = d1.RUNS_DIR / "queue.json"
LOG_DIR = ROOT / "work" / "day_one_queue"
MAX_ATTEMPTS = 3
CAP_EXIT = 3  # day_one's exit code for the per-day request cap
CAP_RESET_MARGIN_MIN = 15  # OpenRouter's day cap rolls at 00:00 UTC; add slack
CAP_TRIPS_BEFORE_STOP = 3  # consecutive cap stops on one model: stop for a human


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_queue(path: Path = None) -> dict:
    path = path or QUEUE_PATH
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"models": []}


def save_queue(queue: dict, path: Path = None) -> None:
    path = path or QUEUE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(queue, indent=1), encoding="utf-8")


def add(queue: dict, slugs: list[str]) -> list[str]:
    known = {m["slug"] for m in queue["models"]}
    added = []
    for slug in slugs:
        slug = slug.strip()
        if not slug or slug in known:
            continue
        queue["models"].append(
            {"slug": slug, "added": now(), "attempts": 0, "status": "pending",
             "last_run": None, "last_exit": None, "note": ""}
        )
        known.add(slug)
        added.append(slug)
    return added


def classify(slug: str) -> tuple[str, str]:
    """('done'|'incomplete', note) from the summary day_one wrote."""
    path = d1.RUNS_DIR / f"{d1.safe_name(slug)}.json"
    if not path.is_file():
        return "incomplete", "no summary written"
    summary = json.loads(path.read_text(encoding="utf-8"))
    results = summary.get("step_results") or {}
    steps = [s for s in d1.CORE_STEPS if s in results]
    if len(steps) < len(d1.CORE_STEPS):
        missing = [s for s in d1.CORE_STEPS if s not in results]
        return "incomplete", f"steps not run: {', '.join(missing)}"
    bad = {s: results[s] for s in steps if not str(results[s]).startswith("ok")}
    if bad:
        return "incomplete", "; ".join(f"{s}: {v}" for s, v in bad.items())
    return "done", d1.dossier_line(summary)[:300]


def run_battery(slug: str) -> int:
    """Run one model in its own process; return its exit code."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = LOG_DIR / f"{d1.safe_name(slug)}.{stamp}.log"
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    print(f"[{now()}] {slug}: starting, log {log_path}", flush=True)
    with log_path.open("w", encoding="utf-8") as log:
        proc = subprocess.run(
            [sys.executable, "-m", "experiments.day_one", slug],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
        )
    return proc.returncode


def seconds_until_cap_reset(at: datetime | None = None) -> float:
    at = at or datetime.now(timezone.utc)
    next_day = (at + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(60.0, (next_day - at).total_seconds() + CAP_RESET_MARGIN_MIN * 60)


def sleep_past_cap(sleep=time.sleep) -> None:
    wait = seconds_until_cap_reset()
    print(f"[{now()}] day cap: sleeping {wait / 3600:.1f} h until the next UTC day", flush=True)
    remaining = wait
    while remaining > 0:
        chunk = min(remaining, 600.0)
        sleep(chunk)
        remaining -= chunk


def run_pass(queue: dict, *, max_models: int | None, wait_for_cap: bool,
             runner=run_battery, sleeper=sleep_past_cap, save=save_queue) -> str:
    """One pass over the pending/incomplete models. Returns 'idle' (nothing
    left to do), 'limit' (max_models reached), 'cap' (day cap, not waiting)
    or 'stopped' (repeated cap trips on one model)."""
    started = 0
    for entry in queue["models"]:
        if entry["status"] not in ("pending", "incomplete"):
            continue
        if entry["attempts"] >= MAX_ATTEMPTS:
            entry["status"] = "failed"
            entry["note"] = f"gave up after {entry['attempts']} attempts: {entry['note']}"
            save(queue)
            print(f"[{now()}] {entry['slug']}: {entry['note']}", flush=True)
            continue
        if max_models is not None and started >= max_models:
            return "limit"
        cap_trips = 0
        while True:
            entry["attempts"] += 1
            entry["last_run"] = now()
            entry["status"] = "running"
            save(queue)
            started += 1
            code = runner(entry["slug"])
            entry["last_exit"] = code
            if code == CAP_EXIT:
                entry["attempts"] -= 1  # the cap is the account's, not the model's
                entry["status"] = "incomplete"
                entry["note"] = "stopped at the day cap"
                save(queue)
                cap_trips += 1
                if cap_trips >= CAP_TRIPS_BEFORE_STOP:
                    print(f"[{now()}] {entry['slug']}: cap tripped {cap_trips}x in a row, "
                          "stopping for a human", flush=True)
                    return "stopped"
                if not wait_for_cap:
                    return "cap"
                sleeper()
                continue
            status, note = classify(entry["slug"])
            entry["status"], entry["note"] = status, note
            save(queue)
            print(f"[{now()}] {entry['slug']}: {status} (exit {code}) {note[:160]}", flush=True)
            break
    return "idle"


def render_status(queue: dict) -> str:
    lines = [f"{'slug':50s} {'status':10s} {'att':>3s} {'exit':>4s} last run"]
    for m in queue["models"]:
        lines.append(
            f"{m['slug'][:50]:50s} {m['status']:10s} {m['attempts']:3d} "
            f"{str(m['last_exit'] if m['last_exit'] is not None else '-'):>4s} "
            f"{(m['last_run'] or '-')[:16]}  {m['note'][:90]}"
        )
    counts = {}
    for m in queue["models"]:
        counts[m["status"]] = counts.get(m["status"], 0) + 1
    lines.append(", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "queue empty")
    return "\n".join(lines)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--add", nargs="+", metavar="SLUG", help="append models")
    parser.add_argument("--status", action="store_true", help="print the queue")
    parser.add_argument("--run", action="store_true", help="work the queue")
    parser.add_argument("--max-models", type=int, default=None,
                        help="stop after starting this many models")
    parser.add_argument("--passes", type=int, default=1,
                        help="passes over the queue per invocation; 0 = until nothing is left")
    parser.add_argument("--wait-for-cap", action="store_true",
                        help="on the day cap, sleep until the next UTC day and continue")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    queue = load_queue()
    if args.add:
        added = add(queue, args.add)
        save_queue(queue)
        print(f"added {len(added)}: {', '.join(added) or '-'}")
    if args.status or not (args.add or args.run):
        print(render_status(queue))
    if not args.run:
        return 0
    passes = 0
    while True:
        passes += 1
        outcome = run_pass(queue, max_models=args.max_models, wait_for_cap=args.wait_for_cap)
        print(f"[{now()}] pass {passes}: {outcome}", flush=True)
        if outcome in ("limit", "cap", "stopped"):
            print(render_status(queue))
            return CAP_EXIT if outcome in ("cap", "stopped") else 0
        pending = [m for m in queue["models"] if m["status"] in ("pending", "incomplete")]
        if not pending or (args.passes and passes >= args.passes):
            print(render_status(queue))
            return 0


if __name__ == "__main__":
    raise SystemExit(main())

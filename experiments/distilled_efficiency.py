"""Distilled-probe efficiency smoke (2026-09-01).

Question: does tokens-to-solve unbundle from recall below the flagship
class, the way recall unbundles from Elo? Run the frozen 80-item domain
bank on the three distilled probes from the recall bank (Haiku 4.5,
GPT-5.4-mini, Qwen3.6-35B-A3B) with PER-CELL completion-token logging.

Predictions:
  - efficiency ~ recipe/skills: Haiku solves what it solves cheaply
    despite recall 0.12 -> token board and recall board SPLIT below the
    flagship class (two components).
  - one quality axis: Haiku grinds or fails like its Elo class -> boards
    stay glued.

Usage (from repo root):
  python -m experiments.distilled_efficiency                    # run (resumable)
  DISTILLED_SMOKE=1 python -m experiments.distilled_efficiency  # 1 model x 2 items
  python -m experiments.distilled_efficiency --report           # analysis only
"""
from __future__ import annotations

import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import experiments.domain_portfolio as dp
from viberank.clients import openrouter_client

DATA_PATH = dp.EXP / "distilled_efficiency_data.json"

MODELS = (  # slug, site elo (worldmodel_analysis scale), $/M (in, out) rough
    ("anthropic/claude-haiku-4.5", 1686, (1.0, 5.0)),
    ("openai/gpt-5.4-mini", 1776, (0.6, 4.8)),
    ("qwen/qwen3.6-35b-a3b", 1701, (0.15, 0.6)),
)
PRICE = {m: p for m, _, p in MODELS}
COST_CEILING_USD = 12.0  # hard stop; expected $3-7

_lock = threading.Lock()


def est_cost(data):
    total = 0.0
    for m, u in data["usage"].items():
        pi, po = PRICE.get(m, (1.0, 5.0))
        total += u["prompt"] / 1e6 * pi + u["completion"] / 1e6 * po
    return total


def main():
    bank = dp.load_bank()
    data = json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.is_file() else {
        "seed": dp.SEED, "effort": "high", "responses": {}, "usage": {},
        "effort_applied": {}}
    models = [m for m, _, _ in MODELS]
    if os.environ.get("DISTILLED_SMOKE"):
        models, bank = models[:1], bank[:2]

    todo = []
    for m in models:
        rec = data["responses"].setdefault(m, {"answers": {}})
        data["usage"].setdefault(m, {"prompt": 0, "completion": 0})
        for it in bank:
            if it["id"] not in rec["answers"]:
                todo.append((m, it))
    print(f"{len(todo)} calls ({len(models)} models x {len(bank)} items, resumable)")
    clients = {m: openrouter_client(m) for m in models}
    no_effort = set()

    def work(job):
        m, it = job
        if est_cost(data) > COST_CEILING_USD:
            return f"SKIP {m} {it['id']} (cost ceiling)"
        result, effort_on = dp.run_one(clients[m], m, it, data, no_effort)
        text = result.content if result else None
        ok = bool(text) and dp.grade(it, text)
        with _lock:
            data["responses"][m]["answers"][it["id"]] = {
                "family": it["family"], "rung": it.get("rung"), "correct": ok,
                "completion_tokens": result.completion_tokens if result else None,
                "extracted": dp.extract(text) if text else None, "text": text}
            data["effort_applied"][m] = effort_on
            if result:
                data["usage"][m]["prompt"] += result.prompt_tokens or 0
                data["usage"][m]["completion"] += result.completion_tokens or 0
            DATA_PATH.write_text(json.dumps(data, indent=1), encoding="utf-8")
            done = sum(len(r["answers"]) for r in data["responses"].values())
            ct = result.completion_tokens if result else 0
            status = "PASS" if ok else ("fail" if text else "CENSORED")
            print(f"[{done:3d}/{len(models)*len(bank)}] {m:32s} {it['id']:14s} "
                  f"{status:8s} {ct or 0:,} ctok  ~${est_cost(data):.2f}")
        return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        for msg in pool.map(work, todo):
            if msg:
                print(msg)
    report(data)


def report(data=None):
    if data is None:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    print(f"\n{'model':34s} {'solved':>9s} {'censored':>8s} {'ctok/solved':>12s}")
    for m, rec in data["responses"].items():
        ans = list(rec["answers"].values())
        solved = [a["completion_tokens"] for a in ans
                  if a["correct"] and a.get("completion_tokens")]
        cens = sum(1 for a in ans if a.get("text") is None)
        mean = sum(solved) / len(solved) if solved else 0
        print(f"{m:34s} {len(solved):4d}/{len(ans):3d} {cens:8d} {mean:12,.0f}")


if __name__ == "__main__":
    if "--report" in sys.argv:
        report()
    else:
        main()

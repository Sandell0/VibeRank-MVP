"""Checkpoint re-grades of the pilot transcripts by three diverse evaluators.

Each grader gives a holistic Elo read of every pilot interview at prefix
lengths 5, 10, 15, 20, 25. Same transcripts for every grader, so differences
between graders are pure evaluator bias (tau) — the quantity that decides
whether any interview budget can match the aggregate, and whether ensembling
diverse evaluators cuts the floor.

Grader ids are ones this repo has already used successfully on OpenRouter.
Resumable per (model, grader, prefix).

    python -m experiments.pilot_checkpoint_regrade
"""
from __future__ import annotations

import json
from pathlib import Path

import time

import experiments.self_steered_interview as ssi
from viberank.clients import ProviderError, openrouter_client
from viberank.grading import _extract_json

EXP = Path(__file__).resolve().parent
DEEP_PATH = EXP / "pilot_deep_data.json"
DATA_PATH = EXP / "pilot_regrade_data.json"

GRADERS = (
    "anthropic/claude-opus-4.8",
    "qwen/qwen3.7-max",
    "deepseek/deepseek-v4-pro",
)
CHECKPOINTS = (5, 10, 15, 20, 25)

# $/1M tokens (list prices from theaggregate.ai data, 2026-08)
PRICES = {
    "anthropic/claude-opus-4.8": (5.0, 25.0),
    "qwen/qwen3.7-max": (0.8, 3.2),
    "deepseek/deepseek-v4-pro": (0.6, 2.0),
}


def read_prompt(steps: list[dict]) -> str:
    return f"""You are an expert examiner. Below is an interview of an anonymous language model: questions with the examiner's private reference answers, and the candidate's answers. Read the candidate's answers yourself and estimate the candidate's ability as an Elo (1000 very weak small model, 1400 capable mid-tier, 1800 strong frontier, 2200 exceptional).

Return JSON only:
{{"mean_elo": 0, "low_90": 0, "high_90": 0, "assessment": "brief evidence"}}

INTERVIEW
{ssi.transcript_text(steps)}"""


def metered_json(client, usage: dict, system: str, user: str, label: str) -> dict:
    """call_json with token accounting (ssi.call_json discards usage)."""
    for attempt, sleep_s in enumerate((0,) + ssi.RETRY_SLEEPS):
        if sleep_s:
            time.sleep(sleep_s)
        try:
            result = client.complete_with_usage(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.0,
                json_mode=True,
                max_tokens=12000,
            )
            usage["prompt"] += getattr(result, "prompt_tokens", None) or 0
            usage["completion"] += getattr(result, "completion_tokens", None) or 0
            return _extract_json(result.content)
        except ProviderError as exc:
            print(f"    {label} attempt {attempt + 1} failed: {str(exc)[:110]}")
    raise RuntimeError(f"{label}: retries exhausted")


def main() -> None:
    deep = json.loads(DEEP_PATH.read_text(encoding="utf-8"))["models"]
    data = (
        json.loads(DATA_PATH.read_text(encoding="utf-8"))
        if DATA_PATH.is_file()
        else {"reads": {}, "usage": {}}
    )
    clients = {}
    for model, record in deep.items():
        steps = record.get("steps", [])
        if len(steps) < max(CHECKPOINTS):
            print(f"{model}: only {len(steps)} steps, grading available prefixes only")
        for grader in GRADERS:
            store = data["reads"].setdefault(model, {}).setdefault(grader, {})
            gu = data["usage"].setdefault(grader, {"prompt": 0, "completion": 0})
            for k in CHECKPOINTS:
                if str(k) in store or len(steps) < k:
                    continue
                client = clients.setdefault(grader, openrouter_client(grader))
                try:
                    raw = metered_json(
                        client,
                        gu,
                        "Return strict JSON. Deliver your examiner's read with honest uncertainty.",
                        read_prompt(steps[:k]),
                        f"{grader} k={k} {model[:24]}",
                    )
                    store[str(k)] = {
                        "mean_elo": float(raw["mean_elo"]),
                        "low_90": float(raw.get("low_90", 0)),
                        "high_90": float(raw.get("high_90", 0)),
                    }
                    print(
                        f"{model[:28]:<28} {grader.split('/')[-1]:<18} k={k:>2} "
                        f"-> {float(raw['mean_elo']):.0f}"
                    )
                except (RuntimeError, ProviderError, ValueError, KeyError) as exc:
                    print(f"  FAILED {model} {grader} k={k}: {str(exc)[:120]}")
                    continue
                DATA_PATH.write_text(
                    json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8"
                )
    print("done; reads in", DATA_PATH.name)


if __name__ == "__main__":
    main()

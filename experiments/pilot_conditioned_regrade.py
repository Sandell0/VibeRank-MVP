"""Difficulty-conditioned re-reads of the pilot transcripts.

Tests the pass-rate-anchoring hypothesis from the pilot: readers judged
mid-tier candidates low because boundary-hugging interviews make every
transcript ~half failures, and readers anchored on failure rate instead of
on WHERE the pass/fail boundary sits. If true, giving readers the
difficulty-outcome ladder plus an explicit conditioning instruction should
collapse the shared 235-Elo bias without any smarter model.

Variants, per grader per model:
  A "conditioned"  — full transcript + ladder table + conditioning
                     instruction, at k=10 and k=25;
  B "ladder-only"  — ladder table alone (no transcript), at k=25: does the
                     texture in answers add anything beyond boundary location?

    python -m experiments.pilot_conditioned_regrade
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import experiments.self_steered_interview as ssi
from viberank.clients import ProviderError, openrouter_client
from viberank.grading import _extract_json

EXP = Path(__file__).resolve().parent
DEEP_PATH = EXP / "pilot_deep_data.json"
DATA_PATH = EXP / "pilot_conditioned_data.json"

GRADERS = (
    "anthropic/claude-opus-4.8",
    "qwen/qwen3.7-max",
    "deepseek/deepseek-v4-pro",
)
COND_PREFIXES = (10, 25)

CONDITIONING = """How to estimate: the examiner deliberately targets each question at the candidate's current failure boundary, so roughly half the answers fail REGARDLESS of the candidate's absolute ability. Do not judge by overall pass rate. Estimate ability from WHERE the boundary sits: a candidate that passes most questions rated ~1300 and fails most rated ~1600 has ability roughly in between, whatever the raw failure count. Use the answer texture to refine within that band, and discount the examiner's difficulty ratings if the content clearly contradicts them."""


def ladder_table(steps: list[dict]) -> str:
    rows = ["#  examiner-difficulty  outcome (0=wrong .. 3=fully correct; >=2.5 is a pass)"]
    for i, s in enumerate(steps, 1):
        rows.append(f"{i:>2}  d{s['difficulty']:.0f}  score {s['medium_score']:.2f}")
    return "\n".join(rows)


def conditioned_prompt(steps: list[dict]) -> str:
    return f"""You are an expert examiner. Below is an adaptive interview of an anonymous language model: a difficulty-outcome ladder, then the full transcript (questions, the examiner's private reference answers, and the candidate's answers). Estimate the candidate's ability as an Elo (1000 very weak small model, 1400 capable mid-tier, 1800 strong frontier, 2200 exceptional).

{CONDITIONING}

Return JSON only:
{{"mean_elo": 0, "low_90": 0, "high_90": 0, "assessment": "brief evidence"}}

DIFFICULTY-OUTCOME LADDER
{ladder_table(steps)}

INTERVIEW
{ssi.transcript_text(steps)}"""


def ladder_only_prompt(steps: list[dict]) -> str:
    return f"""You are an expert examiner. Below is the difficulty-outcome ladder of an adaptive interview of an anonymous language model: each question's difficulty as rated by the examiner (Elo scale: 1000 very weak, 1400 capable mid-tier, 1800 strong frontier, 2200 exceptional) and the graded outcome. Estimate the candidate's ability as an Elo on the same scale.

{CONDITIONING}

Return JSON only:
{{"mean_elo": 0, "low_90": 0, "high_90": 0, "assessment": "brief reasoning"}}

DIFFICULTY-OUTCOME LADDER
{ladder_table(steps)}"""


def metered_json(client, usage: dict, user: str, label: str) -> dict:
    for attempt, sleep_s in enumerate((0,) + ssi.RETRY_SLEEPS):
        if sleep_s:
            time.sleep(sleep_s)
        try:
            result = client.complete_with_usage(
                [
                    {"role": "system", "content": "Return strict JSON. Deliver your examiner's read with honest uncertainty."},
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
        else {"conditioned": {}, "ladder_only": {}, "usage": {}}
    )
    clients = {}
    jobs = []
    for model, record in deep.items():
        steps = record.get("steps", [])
        for grader in GRADERS:
            for k in COND_PREFIXES:
                if len(steps) >= k:
                    jobs.append(("conditioned", model, grader, k, conditioned_prompt(steps[:k])))
            if len(steps) >= 25:
                jobs.append(("ladder_only", model, grader, 25, ladder_only_prompt(steps[:25])))
    for variant, model, grader, k, prompt in jobs:
        store = data[variant].setdefault(model, {}).setdefault(grader, {})
        if str(k) in store:
            continue
        gu = data["usage"].setdefault(grader, {"prompt": 0, "completion": 0})
        client = clients.setdefault(grader, openrouter_client(grader))
        try:
            raw = metered_json(client, gu, prompt, f"{variant} {grader.split('/')[-1]} k={k} {model[:22]}")
        except (RuntimeError, ProviderError, ValueError, KeyError) as exc:
            print(f"  FAILED {variant} {model} {grader} k={k}: {str(exc)[:120]}")
            continue
        store[str(k)] = {"mean_elo": float(raw["mean_elo"])}
        print(f"{variant:<12} {model[:26]:<26} {grader.split('/')[-1]:<16} k={k:>2} -> {float(raw['mean_elo']):.0f}")
        DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
    print("done")


if __name__ == "__main__":
    main()

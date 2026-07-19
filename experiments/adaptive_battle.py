"""Adaptive-question protocol vs fixed questions, on the full known-Elo set.

Runs `question_mode: "authored"` — each question written on the fly, targeted
at the current posterior — over the 25 reference models (18 bank + 7
frontier). The unit of calibration is the PROTOCOL: every model sees
different questions, but the procedure yields one raw transcript read per
prefix, calibrated leave-one-out exactly like the fixed-question system.

Questions this must answer:
  1. mid-range (<=1749): does adaptive match the fixed-question MAE of 86?
  2. frontier (>=1744): do raw reads spread where fixed mode collapsed to
     a single value (5/7 models reading an identical 1950)?
  3. does authored-question difficulty actually track the model (mechanism)?

    python -m experiments.adaptive_battle
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from experiments.frontier_test import FRONTIER_TARGETS
from experiments.method_battle import TARGETS as BATTLE_TARGETS
from viberank.clients import ProviderError
from viberank.evaluation import EvaluationConfig, run_evaluation

DATA_PATH = Path(__file__).resolve().parent / "adaptive_battle_data.json"
RESULTS_PATH = Path(__file__).resolve().parent / "adaptive_battle_results.json"
QUESTIONS = 5
MODEL_ATTEMPTS = 3
FRONTIER_FLOOR = 1740.0

TARGETS = tuple(
    (provider, model, elo, row)
    for provider, model, elo, row in (*BATTLE_TARGETS, *FRONTIER_TARGETS)
    if provider != "openai"
)


def collect() -> dict:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.is_file() else {"models": {}}
    for provider, model, elo, row in TARGETS:
        if model in data["models"]:
            print(f"{model}: cached")
            continue
        print(f"{model} (public {elo:.0f}, {provider}):")
        result = None
        for attempt in range(1, MODEL_ATTEMPTS + 1):
            try:
                result = run_evaluation(
                    EvaluationConfig(
                        provider=provider,
                        model=model,
                        questions=QUESTIONS,
                        question_mode="authored",
                    )
                )
                break
            except ProviderError as exc:
                print(f"  attempt {attempt} failed: {str(exc)[:140]}")
                time.sleep(5 * attempt)
        if result is None:
            print(f"  SKIPPED {model}")
            continue
        traces = []
        for trace in result["traces"]:
            traces.append(
                {
                    "step": trace["step"],
                    "question_title": trace["question"]["title"],
                    "question_difficulty_target": trace["question"]["difficulty_elo"],
                    "grade_expected_score": trace["grade"]["expected_score"],
                    "holistic_raw": (
                        trace["holistic"]["raw_mean_elo"] if trace.get("holistic") else None
                    ),
                }
            )
            print(
                f"  Q{trace['step']} target {trace['question']['difficulty_elo']:.0f} "
                f"({trace['question']['title'][:44]}) -> score "
                f"{trace['grade']['expected_score']:.2f}, raw read "
                f"{traces[-1]['holistic_raw']}"
            )
        data["models"][model] = {
            "provider": provider,
            "public_elo": elo,
            "leaderboard_row": row,
            "traces": traces,
            "usage": result["usage"],
            "full_traces": result["traces"],
        }
        DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
    return data


def spearman(left: list[float], right: list[float]) -> float:
    def ranks(values):
        pairs = sorted(range(len(values)), key=values.__getitem__)
        out = [0.0] * len(values)
        index = 0
        while index < len(pairs):
            end = index
            while end + 1 < len(pairs) and values[pairs[end + 1]] == values[pairs[index]]:
                end += 1
            average = (index + end) / 2.0
            for position in range(index, end + 1):
                out[pairs[position]] = average
            index = end + 1
        return out

    lr, rr = ranks(left), ranks(right)
    lm, rm = sum(lr) / len(lr), sum(rr) / len(rr)
    num = sum((a - lm) * (b - rm) for a, b in zip(lr, rr))
    den = math.sqrt(sum((a - lm) ** 2 for a in lr) * sum((b - rm) ** 2 for b in rr))
    return num / den if den else 0.0


def analyze(data: dict) -> None:
    models = {
        name: record
        for name, record in data["models"].items()
        if record["traces"] and record["traces"][-1]["holistic_raw"] is not None
    }
    if len(models) < 8:
        print(f"Only {len(models)} usable models; need more before analyzing.")
        return
    names = list(models)
    truths = {n: models[n]["public_elo"] for n in names}
    finals = {n: models[n]["traces"][-1]["holistic_raw"] for n in names}

    loo_estimates = {}
    for held in names:
        pairs = [(truths[n], finals[n]) for n in names if n != held]
        k = len(pairs)
        tm = sum(t for t, _ in pairs) / k
        rm = sum(r for _, r in pairs) / k
        tv = sum((t - tm) ** 2 for t, _ in pairs)
        cov = sum((t - tm) * (r - rm) for t, r in pairs)
        slope = cov / tv if tv else 0.0
        if slope <= 0.05:
            loo_estimates[held] = finals[held]
            continue
        intercept = rm - slope * tm
        loo_estimates[held] = (finals[held] - intercept) / slope

    rows = sorted(
        (
            {
                "model": n,
                "true": truths[n],
                "raw_final": finals[n],
                "estimate": round(loo_estimates[n], 1),
                "error": round(loo_estimates[n] - truths[n], 1),
            }
            for n in names
        ),
        key=lambda r: r["true"],
    )
    print(f"\n{'model':<30} {'true':>5} {'raw@5':>6} {'estimate':>9} {'err':>6}")
    for r in rows:
        print(
            f"{r['model']:<30} {r['true']:>5.0f} {r['raw_final']:>6.0f} "
            f"{r['estimate']:>9.0f} {r['error']:>+6.0f}"
        )

    def subset_stats(subset):
        errors = [abs(r["error"]) for r in subset]
        return sum(errors) / len(errors) if errors else float("nan")

    mid = [r for r in rows if r["true"] < FRONTIER_FLOOR]
    frontier = [r for r in rows if r["true"] >= FRONTIER_FLOOR]
    print(f"\nmid-range  (n={len(mid)}): MAE {subset_stats(mid):.0f}  (fixed-question was 86)")
    if frontier:
        f_raws = [r["raw_final"] for r in frontier]
        f_truths = [r["true"] for r in frontier]
        print(
            f"frontier   (n={len(frontier)}): MAE {subset_stats(frontier):.0f}, "
            f"raw spread {max(f_raws) - min(f_raws):.0f} Elo, "
            f"distinct reads {len(set(f_raws))}/{len(f_raws)}, "
            f"spearman {spearman(f_truths, f_raws):.2f}  "
            "(fixed: 5/7 identical, censored)"
        )
    all_truths = [r["true"] for r in rows]
    all_estimates = [r["estimate"] for r in rows]
    print(f"overall    (n={len(rows)}): MAE {subset_stats(rows):.0f}, "
          f"spearman {spearman(all_truths, all_estimates):.3f}")

    print("\nDifficulty adaptation (mean authored target by step, weakest vs strongest third):")
    ordered = sorted(names, key=lambda n: truths[n])
    third = max(1, len(ordered) // 3)
    for label, group in (("weakest", ordered[:third]), ("strongest", ordered[-third:])):
        by_step = []
        for step in range(QUESTIONS):
            values = [
                models[n]["traces"][step]["question_difficulty_target"]
                for n in group
                if len(models[n]["traces"]) > step
            ]
            by_step.append(sum(values) / len(values))
        print(f"  {label:<10} " + " ".join(f"{v:>6.0f}" for v in by_step))

    RESULTS_PATH.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nSaved {RESULTS_PATH}")


def main() -> None:
    data = collect()
    analyze(data)


if __name__ == "__main__":
    main()

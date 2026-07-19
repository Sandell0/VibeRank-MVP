"""Grader-dialect test: re-read the same 18 transcripts with other graders.

Prediction under test: each grader's raw Elo vocabulary sits on its own scale
(different intercept/slope/clustering), so raw numbers shift model-wide when
the grader changes — but a per-grader refit restores accuracy. If raw reads
barely move across graders, the swap-guard was paranoia.

Uses cached answers only (no target calls); one full-transcript read per
model per grader. Results cached in grader_swap_data.json.

    python -m experiments.grader_swap_test
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from viberank.clients import mistral_client
from viberank.debug_questions import FIXED_DEBUG_QUESTIONS
from viberank.holistic import holistic_read

BANK_PATH = Path(__file__).resolve().parent / "method_battle_data.json"
SWAP_PATH = Path(__file__).resolve().parent / "grader_swap_data.json"
ALT_GRADERS = ("mistral-small-2506", "mistral-large-2512")
BASELINE_GRADER = "mistral-medium-3.5"
CALL_PAUSE_SECONDS = 0.7


def loo_fit_mae(reads: dict[str, float], truths: dict[str, float]) -> tuple[float, float, float]:
    """LOO classical-calibration MAE plus the pooled fit's slope/intercept."""
    names = list(reads)
    errors = []
    for held in names:
        pairs = [(truths[n], reads[n]) for n in names if n != held]
        k = len(pairs)
        tm = sum(t for t, _ in pairs) / k
        rm = sum(r for _, r in pairs) / k
        tv = sum((t - tm) ** 2 for t, _ in pairs)
        cov = sum((t - tm) * (r - rm) for t, r in pairs)
        slope = cov / tv if tv else 0.0
        if slope <= 0.05:
            errors.append(abs(reads[held] - truths[held]))
            continue
        intercept = rm - slope * tm
        errors.append(abs((reads[held] - intercept) / slope - truths[held]))
    tm = sum(truths.values()) / len(names)
    rm = sum(reads.values()) / len(names)
    tv = sum((truths[n] - tm) ** 2 for n in names)
    cov = sum((truths[n] - tm) * (reads[n] - rm) for n in names)
    slope = cov / tv if tv else 0.0
    intercept = rm - slope * tm
    return sum(errors) / len(errors), slope, intercept


def main() -> None:
    bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))["models"]
    swap = json.loads(SWAP_PATH.read_text(encoding="utf-8")) if SWAP_PATH.is_file() else {}

    for grader_model in ALT_GRADERS:
        store = swap.setdefault(grader_model, {})
        client = mistral_client(grader_model)
        for name, record in bank.items():
            if name in store:
                continue
            answers = [entry["answer"] for entry in record["answers"]]
            read, usage = holistic_read(client, FIXED_DEBUG_QUESTIONS, answers)
            store[name] = {
                "read": read["mean_elo"],
                "total_tokens": usage.get("total_tokens") or 0,
            }
            print(f"{grader_model} read {name}: {read['mean_elo']:.0f}")
            SWAP_PATH.write_text(json.dumps(swap, indent=2), encoding="utf-8")
            time.sleep(CALL_PAUSE_SECONDS)

    truths = {name: record["public_elo"] for name, record in bank.items()}
    baseline = {
        name: record["holistic_prefixes"][-1]["mean_elo"] for name, record in bank.items()
    }

    alt_reads = {
        grader: {name: entry["read"] for name, entry in swap[grader].items()}
        for grader in ALT_GRADERS
    }
    print(f"\n{'grader':<22} {'mean read':>9} {'slope':>7} {'intercept':>9} {'LOO MAE':>8}")
    all_reads = {BASELINE_GRADER: baseline, **alt_reads}
    summary = {}
    for grader_model, reads in all_reads.items():
        mae, slope, intercept = loo_fit_mae(reads, truths)
        mean_read = sum(reads.values()) / len(reads)
        summary[grader_model] = {
            "loo_mae": round(mae, 1),
            "slope": round(slope, 3),
            "intercept": round(intercept, 1),
            "mean_read": round(mean_read, 1),
        }
        print(
            f"{grader_model:<22} {mean_read:>9.0f} {slope:>7.2f} {intercept:>9.0f} {mae:>8.0f}"
        )

    print("\nPairwise raw-read shift on identical transcripts:")
    names = list(bank)
    for grader_model in ALT_GRADERS:
        diffs = [alt_reads[grader_model][n] - baseline[n] for n in names]
        mean_diff = sum(diffs) / len(diffs)
        sd = math.sqrt(sum((d - mean_diff) ** 2 for d in diffs) / (len(diffs) - 1))
        summary[grader_model]["shift_vs_baseline"] = round(mean_diff, 1)
        print(f"  {grader_model} vs {BASELINE_GRADER}: mean {mean_diff:+.0f} Elo, sd {sd:.0f}")

    out = SWAP_PATH.with_name("grader_swap_results.json")
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()

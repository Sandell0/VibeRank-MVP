"""Strong author + strong reader: the completed matrix of the interviewer theory.

Same adaptive protocol as experiments.adaptive_battle, but the questions are
authored by gpt-5.6-terra instead of mistral-medium-3.5, and the final
transcripts are additionally read by terra. All data cached separately in
terra_author_data.json / terra_reads.json — nothing from earlier runs is
overwritten.

Prediction on record: with real frontier-grade questions and correct
references, frontier rank correlation breaks past the reader-only plateau
of 0.40.

    python -m experiments.terra_author_battle
"""
from __future__ import annotations

import json
import os
from pathlib import Path

os.environ["VIBERANK_AUTHOR_PROVIDER"] = "openrouter"
os.environ["VIBERANK_AUTHOR_MODEL"] = "openai/gpt-5.6-terra"

import experiments.adaptive_battle as adaptive
from experiments.strong_reader_test import (
    TranscriptItem,
    loo_estimates,
    read_with_retries,
    tie_aware_spearman,
)
from viberank.clients import openrouter_client

DATA_PATH = Path(__file__).resolve().parent / "terra_author_data.json"
RESULTS_PATH = Path(__file__).resolve().parent / "terra_author_results.json"
READS_PATH = Path(__file__).resolve().parent / "terra_reads.json"
READER = "openai/gpt-5.6-terra"
FRONTIER_FLOOR = 1740.0

adaptive.DATA_PATH = DATA_PATH
adaptive.RESULTS_PATH = RESULTS_PATH


def terra_reads(data: dict) -> dict[str, float]:
    reads = json.loads(READS_PATH.read_text(encoding="utf-8")) if READS_PATH.is_file() else {}
    client = None
    for name, record in data["models"].items():
        if name in reads:
            continue
        if client is None:
            client = openrouter_client(READER)
        items = [
            TranscriptItem(
                prompt=trace["question"]["prompt"],
                reference_answer=trace["grader_context"]["reference_answer"],
                rubric=tuple(trace["grader_context"]["rubric"]),
            )
            for trace in record["full_traces"]
        ]
        answers = [trace["answer"] for trace in record["full_traces"]]
        value = read_with_retries(client, items, answers, f"terra read {name}")
        reads[name] = value
        print(f"terra read {name}: {value:.0f} (true {record['public_elo']:.0f})")
        READS_PATH.write_text(json.dumps(reads, indent=2), encoding="utf-8")
    return reads


def report(data: dict, reads: dict[str, float]) -> None:
    models = {n: r for n, r in data["models"].items() if n in reads}
    truths = {n: models[n]["public_elo"] for n in models}
    estimates = loo_estimates(reads, truths)

    rows = sorted(
        (
            {
                "model": n,
                "true": truths[n],
                "terra_read": reads[n],
                "estimate": round(estimates[n], 1),
                "error": round(estimates[n] - truths[n], 1),
            }
            for n in models
        ),
        key=lambda r: r["true"],
    )
    print(f"\n{'model':<30} {'true':>5} {'read':>6} {'estimate':>9} {'err':>6}")
    for r in rows:
        print(
            f"{r['model']:<30} {r['true']:>5.0f} {r['terra_read']:>6.0f} "
            f"{r['estimate']:>9.0f} {r['error']:>+6.0f}"
        )

    def mae(subset):
        return sum(abs(r["error"]) for r in subset) / len(subset)

    mid = [r for r in rows if r["true"] < FRONTIER_FLOOR]
    frontier = [r for r in rows if r["true"] >= FRONTIER_FLOOR]
    print(f"\nmid-range  (n={len(mid)}): MAE {mae(mid):.0f}   [medium-author+terra-reader was 98]")
    if frontier:
        f_reads = [r["terra_read"] for r in frontier]
        f_true = [r["true"] for r in frontier]
        print(
            f"frontier   (n={len(frontier)}): MAE {mae(frontier):.0f}, "
            f"spread {max(f_reads) - min(f_reads):.0f}, "
            f"distinct {len(set(f_reads))}/{len(f_reads)}, "
            f"spearman {tie_aware_spearman(f_true, f_reads):.2f}   "
            "[medium-author plateau was 0.38-0.40]"
        )
    print(f"overall    (n={len(rows)}): MAE {mae(rows):.0f}")
    RESULTS_PATH.with_name("terra_author_final.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8"
    )


def main() -> None:
    data = adaptive.collect()
    reads = terra_reads(data)
    report(data, reads)


if __name__ == "__main__":
    main()

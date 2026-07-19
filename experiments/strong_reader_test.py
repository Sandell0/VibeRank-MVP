"""Strong-reader test: can frontier-tier judges read what mistral-medium couldn't?

Re-reads cached transcripts with GPT-5.6 Luna and Terra as holistic judges:

  - the 25 ADAPTIVE transcripts (authored questions, real failure surfaces) —
    the user's interviewer theory predicts a strong reader extracts frontier
    discrimination here where mistral-medium output one value eight times;
  - the 7 FIXED frontier transcripts (all-perfect answers) — control: these
    carry no failure information, so even a strong reader should stay flat.

No new target calls; readers only. Results cached in strong_reader_data.json.

    python -m experiments.strong_reader_test
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

from viberank.clients import ProviderError, openrouter_client
from viberank.debug_questions import FIXED_DEBUG_QUESTIONS
from viberank.holistic import holistic_read

ADAPTIVE_PATH = Path(__file__).resolve().parent / "adaptive_battle_data.json"
FIXED_FRONTIER_PATH = Path(__file__).resolve().parent / "frontier_test_data.json"
DATA_PATH = Path(__file__).resolve().parent / "strong_reader_data.json"
READERS = ("openai/gpt-5.6-luna", "openai/gpt-5.6-terra", "openai/gpt-5.6-sol")
FRONTIER_FLOOR = 1740.0
RETRY_SLEEPS = (5, 15, 30)


@dataclass(frozen=True)
class TranscriptItem:
    prompt: str
    reference_answer: str
    rubric: tuple


def adaptive_transcripts() -> dict:
    data = json.loads(ADAPTIVE_PATH.read_text(encoding="utf-8"))["models"]
    out = {}
    for name, record in data.items():
        items = []
        answers = []
        for trace in record["full_traces"]:
            items.append(
                TranscriptItem(
                    prompt=trace["question"]["prompt"],
                    reference_answer=trace["grader_context"]["reference_answer"],
                    rubric=tuple(trace["grader_context"]["rubric"]),
                )
            )
            answers.append(trace["answer"])
        out[name] = {
            "true": record["public_elo"],
            "items": items,
            "answers": answers,
            "medium_read": record["traces"][-1]["holistic_raw"],
        }
    return out


def fixed_frontier_transcripts() -> dict:
    data = json.loads(FIXED_FRONTIER_PATH.read_text(encoding="utf-8"))["models"]
    out = {}
    for name, record in data.items():
        out[name] = {
            "true": record["public_elo"],
            "items": list(FIXED_DEBUG_QUESTIONS),
            "answers": [entry["answer"] for entry in record["answers"]],
            "medium_read": record["holistic_prefixes"][-1]["mean_elo"],
        }
    return out


def read_with_retries(client, items, answers, label: str) -> float:
    for attempt, sleep_s in enumerate((0,) + RETRY_SLEEPS):
        if sleep_s:
            time.sleep(sleep_s)
        try:
            read, _ = holistic_read(client, items, answers)
            time.sleep(0.5)
            return read["mean_elo"]
        except ProviderError as exc:
            print(f"    {label} failed (attempt {attempt + 1}): {str(exc)[:120]}")
    raise RuntimeError(f"{label}: all retries failed")


def tie_aware_spearman(left: list[float], right: list[float]) -> float:
    def ranks(values):
        order = sorted(range(len(values)), key=values.__getitem__)
        out = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg = (i + j) / 2.0
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    lr, rr = ranks(left), ranks(right)
    lm, rm = sum(lr) / len(lr), sum(rr) / len(rr)
    num = sum((a - lm) * (b - rm) for a, b in zip(lr, rr))
    den = math.sqrt(sum((a - lm) ** 2 for a in lr) * sum((b - rm) ** 2 for b in rr))
    return num / den if den else 0.0


def loo_estimates(reads: dict[str, float], truths: dict[str, float]) -> dict[str, float]:
    names = list(reads)
    estimates = {}
    for held in names:
        pairs = [(truths[n], reads[n]) for n in names if n != held]
        k = len(pairs)
        tm = sum(t for t, _ in pairs) / k
        rm = sum(r for _, r in pairs) / k
        tv = sum((t - tm) ** 2 for t, _ in pairs)
        cov = sum((t - tm) * (r - rm) for t, r in pairs)
        slope = cov / tv if tv else 0.0
        if slope <= 0.05:
            estimates[held] = reads[held]
            continue
        intercept = rm - slope * tm
        estimates[held] = (reads[held] - intercept) / slope
    return estimates


def report_set(label: str, entries: dict, reads: dict[str, float]) -> None:
    truths = {n: entries[n]["true"] for n in reads}
    frontier = [n for n in reads if truths[n] >= FRONTIER_FLOOR]
    print(f"\n  {label}: n={len(reads)}")
    estimates = loo_estimates(reads, truths)

    def mae(names) -> float:
        return sum(abs(estimates[n] - truths[n]) for n in names) / len(names)

    if len(reads) >= 8:
        mid = [n for n in reads if truths[n] < FRONTIER_FLOOR]
        line = f"    LOO MAE: {mae(list(reads)):.0f}"
        if len(mid) >= 5:
            line += f"  (mid-range {mae(mid):.0f}"
            if len(frontier) >= 4:
                line += f", frontier {mae(frontier):.0f}"
            line += ")"
        print(line)
    elif len(reads) >= 5:
        print(f"    within-set LOO MAE: {mae(list(reads)):.0f}  (small n, indicative only)")
    if len(frontier) >= 4:
        f_reads = [reads[n] for n in frontier]
        f_true = [truths[n] for n in frontier]
        print(
            f"    frontier (n={len(frontier)}): spread {max(f_reads) - min(f_reads):.0f}, "
            f"distinct {len(set(f_reads))}/{len(f_reads)}, "
            f"spearman {tie_aware_spearman(f_true, f_reads):.2f}"
        )


def main() -> None:
    adaptive = adaptive_transcripts()
    fixed_frontier = fixed_frontier_transcripts()
    store = json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.is_file() else {}

    for reader in READERS:
        reader_store = store.setdefault(reader, {"adaptive": {}, "fixed_frontier": {}})
        pending = any(
            name not in reader_store[set_name]
            for set_name, entries in (("adaptive", adaptive), ("fixed_frontier", fixed_frontier))
            for name in entries
        )
        if not pending:
            continue
        client = openrouter_client(reader)
        for set_name, entries in (("adaptive", adaptive), ("fixed_frontier", fixed_frontier)):
            for name, entry in entries.items():
                if name in reader_store[set_name]:
                    continue
                value = read_with_retries(
                    client, entry["items"], entry["answers"], f"{reader} {set_name} {name}"
                )
                reader_store[set_name][name] = value
                print(f"{reader} [{set_name}] {name}: {value:.0f} (true {entry['true']:.0f})")
                DATA_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")

    print("\n=== BASELINE mistral-medium-3.5 ===")
    report_set("adaptive", adaptive, {n: e["medium_read"] for n, e in adaptive.items()})
    report_set("fixed frontier", fixed_frontier, {n: e["medium_read"] for n, e in fixed_frontier.items()})
    for reader in READERS:
        print(f"\n=== READER {reader} ===")
        report_set("adaptive", adaptive, store[reader]["adaptive"])
        report_set("fixed frontier", fixed_frontier, store[reader]["fixed_frontier"])


if __name__ == "__main__":
    main()

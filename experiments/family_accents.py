"""Family-accent test: does the grader systematically over/under-read some
model families, beyond its global scale distortion?

Fits the global classical calibration on all bank models, then groups the
per-model residuals (in Elo) by family. A family whose mean residual is large
relative to its standard error has an accent the global correction cannot
remove. Small n per family — read the standard errors before believing.

    python -m experiments.family_accents
"""
from __future__ import annotations

import json
import math
from pathlib import Path

BANK_PATH = Path(__file__).resolve().parent / "method_battle_data.json"
FRONTIER_PATH = Path(__file__).resolve().parent / "frontier_test_data.json"

FAMILY_BY_PREFIX = (
    ("mistral", "Mistral"),
    ("open-mistral", "Mistral"),
    ("ministral", "Mistral"),
    ("meta-llama/", "Meta Llama"),
    ("google/", "Google"),
    ("microsoft/", "Microsoft"),
    ("openai/gpt-oss", "GPT-OSS"),
    ("openai/", "OpenAI frontier"),
    ("qwen/", "Qwen"),
    ("deepseek/", "DeepSeek"),
    ("moonshotai/", "Moonshot"),
    ("anthropic/", "Anthropic"),
)


def family(name: str) -> str:
    for prefix, label in FAMILY_BY_PREFIX:
        if name.startswith(prefix):
            return label
    return "other"


def main() -> None:
    models = dict(json.loads(BANK_PATH.read_text(encoding="utf-8"))["models"])
    if FRONTIER_PATH.is_file():
        models.update(json.loads(FRONTIER_PATH.read_text(encoding="utf-8"))["models"])

    names = [n for n in models if "holistic_prefixes" in models[n]]
    truths = {n: models[n]["public_elo"] for n in names}
    reads = {n: models[n]["holistic_prefixes"][-1]["mean_elo"] for n in names}

    tm = sum(truths.values()) / len(names)
    rm = sum(reads.values()) / len(names)
    tv = sum((truths[n] - tm) ** 2 for n in names)
    cov = sum((truths[n] - tm) * (reads[n] - rm) for n in names)
    slope = cov / tv
    intercept = rm - slope * tm
    residuals = {n: (reads[n] - (intercept + slope * truths[n])) / slope for n in names}

    groups: dict[str, list[str]] = {}
    for n in names:
        groups.setdefault(family(n), []).append(n)

    print(f"Global fit on {len(names)} models: raw = {intercept:.0f} + {slope:.2f} x true\n")
    print(f"{'family':<16} {'n':>3} {'mean residual':>14} {'std error':>10}")
    for label, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        values = [residuals[n] for n in members]
        mean = sum(values) / len(values)
        if len(values) > 1:
            sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (len(values) - 1))
            se = sd / math.sqrt(len(values))
            se_text = f"{se:>10.0f}"
        else:
            se_text = f"{'—':>10}"
        print(f"{label:<16} {len(members):>3} {mean:>+14.0f} {se_text}")
    print("\nPositive residual = grader over-reads the family (in Elo, after the")
    print("global correction). |mean| > 2x std error is a real accent.")


if __name__ == "__main__":
    main()

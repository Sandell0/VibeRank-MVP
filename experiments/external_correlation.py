"""Correlate the shipped VibeRank estimate with external capability indices.

Uses leave-one-out calibrated holistic estimates (the production system) for
the 18-model bank, matched by leaderboard row name against Epoch ECI and the
Artificial Analysis Intelligence Index exported from the llm-leaderboard
project. Writes external_correlation.json for plotting.

    python -m experiments.external_correlation
"""
from __future__ import annotations

import json
import math
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "method_battle_data.json"
TRAJECTORY_PATH = Path(__file__).resolve().parent / "trajectory_results.json"
RESULTS_PATH = Path(__file__).resolve().parent / "external_correlation.json"
BENCH_BASE = Path(r"C:\Projects\llm-leaderboard\data\nodes\benchmarks")
SOURCES = {
    "epoch_eci": "epoch-ai-eci.json",
    "aa_index": "artificial-analysis-intelligence-index.json",
}

# Documented name aliases: our bank row -> the external row for the variant we
# actually evaluated (default API configs). Chosen by provenance, never score.
ALIASES: dict[str, dict[str, str]] = {
    "aa_index": {
        # mistral-tiny-2407 serves 7B Instruct v0.3; AA's row is unversioned.
        "Mistral 7B Instruct (v0.3)": "Mistral 7B Instruct",
        "Ministral-3-3B-Instruct-2512": "Ministral 3 3B",
        "Ministral-3-8B-Instruct-2512": "Ministral 3 8B",
        "Ministral-3-14B-Instruct-2512": "Ministral 3 14B",
        # deepseek-chat-v3.1 is the non-thinking endpoint.
        "DeepSeek V3.1": "DeepSeek V3.1 (Non-reasoning)",
        # OpenRouter kimi-k2.5 defaults to thinking; answer traces confirm.
        "Kimi K2.5": "Kimi K2.5 (Thinking)",
    },
    "epoch_eci": {},
}


def external_scores(filename: str) -> dict[str, float]:
    payload = json.loads((BENCH_BASE / filename).read_text(encoding="utf-8"))
    unified = payload["scores"].get("unified") or []
    return {entry["model"]: float(entry["score"]) for entry in unified}


def pearson(left: list[float], right: list[float]) -> float:
    lm, rm = sum(left) / len(left), sum(right) / len(right)
    num = sum((a - lm) * (b - rm) for a, b in zip(left, right))
    den = math.sqrt(
        sum((a - lm) ** 2 for a in left) * sum((b - rm) ** 2 for b in right)
    )
    return num / den if den else 0.0


def spearman(left: list[float], right: list[float]) -> float:
    def ranks(values):
        order = sorted(range(len(values)), key=values.__getitem__)
        out = [0.0] * len(values)
        for rank, index in enumerate(order):
            out[index] = float(rank)
        return out

    return pearson(ranks(left), ranks(right))


def main() -> None:
    bank = json.loads(DATA_PATH.read_text(encoding="utf-8"))["models"]
    trajectories = json.loads(TRAJECTORY_PATH.read_text(encoding="utf-8"))["models"]

    output: dict[str, dict] = {}
    for source, filename in SOURCES.items():
        scores = external_scores(filename)
        pairs = []
        missing = []
        for name, record in bank.items():
            row = record["leaderboard_row"]
            if name not in trajectories:
                continue
            external_row = ALIASES.get(source, {}).get(row, row)
            if external_row not in scores:
                missing.append(row)
                continue
            pairs.append(
                {
                    "model": name,
                    "leaderboard_row": row,
                    "external_row": external_row,
                    "aliased": external_row != row,
                    "viberank": round(trajectories[name]["holistic_cal"][-1], 1),
                    "viberank_q3": round(trajectories[name]["holistic_cal"][2], 1),
                    "public_elo": record["public_elo"],
                    "external": scores[external_row],
                }
            )
        ours = [p["viberank"] for p in pairs]
        ours_q3 = [p["viberank_q3"] for p in pairs]
        truth = [p["public_elo"] for p in pairs]
        ext = [p["external"] for p in pairs]
        output[source] = {
            "n": len(pairs),
            "missing": missing,
            "pairs": pairs,
            "viberank_spearman": round(spearman(ours, ext), 3),
            "viberank_pearson": round(pearson(ours, ext), 3),
            "viberank_q3_spearman": round(spearman(ours_q3, ext), 3),
            "ground_truth_spearman": round(spearman(truth, ext), 3),
        }
        print(f"=== {source}: {len(pairs)} matched, {len(missing)} missing {missing}")
        print(
            f"  VibeRank (5Q) vs external: spearman {output[source]['viberank_spearman']}, "
            f"pearson {output[source]['viberank_pearson']}"
        )
        print(f"  VibeRank (3Q) vs external: spearman {output[source]['viberank_q3_spearman']}")
        print(
            f"  aibenchmarks Elo vs external (reference ceiling): "
            f"spearman {output[source]['ground_truth_spearman']}"
        )

    RESULTS_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nSaved {RESULTS_PATH}")


if __name__ == "__main__":
    main()

"""Correlate self-steered interview estimates with the Epoch Capabilities
Index (out-of-sample: ECI never touched any part of the pipeline).

    python -m experiments.selfsteer_vs_epoch
"""
from __future__ import annotations

import json
import math
from pathlib import Path

EXP = Path(__file__).resolve().parent
ECI_PATH = Path(r"C:\Projects\llm-leaderboard\data\nodes\benchmarks\epoch-ai-eci.json")


def spearman(a, b):
    def ranks(v):
        order = sorted(range(len(v)), key=v.__getitem__)
        out = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2.0
            i = j + 1
        return out

    ra, rb = ranks(a), ranks(b)
    return pearson(ra, rb)


def pearson(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else 0.0


def main() -> None:
    results = json.loads((EXP / "self_steered_results.json").read_text(encoding="utf-8"))
    ladders, truths = results["ladders"], results["truths"]

    rows = {}
    for filename in ("method_battle_data.json", "frontier_test_data.json"):
        for name, record in json.loads((EXP / filename).read_text(encoding="utf-8"))["models"].items():
            rows[name] = record["leaderboard_row"]

    eci = {
        entry["model"]: float(entry["score"])
        for entry in json.loads(ECI_PATH.read_text(encoding="utf-8"))["scores"]["unified"]
    }

    matched = []
    missing = []
    for name in ladders:
        row = rows.get(name)
        if row in eci:
            matched.append((name, row, ladders[name], truths[name], eci[row]))
        else:
            missing.append(row or name)

    ours = [m[2] for m in matched]
    truth = [m[3] for m in matched]
    external = [m[4] for m in matched]
    print(f"matched {len(matched)} models against Epoch ECI; missing: {missing}")
    print(f"\n{'model':<34} {'ladder':>7} {'true':>5} {'ECI':>6}")
    for name, row, ladder, true, score in sorted(matched, key=lambda m: m[4]):
        print(f"{name:<34} {ladder:>7.0f} {true:>5.0f} {score:>6.1f}")
    print(f"\nself-steered ladder vs ECI: spearman {spearman(ours, external):.3f}, "
          f"pearson {pearson(ours, external):.3f}")
    print(f"aibenchmarks Elo vs ECI (ceiling): spearman {spearman(truth, external):.3f}")
    print("(shipped fixed-question system scored 0.90 vs a 0.94 ceiling on its n=10 overlap)")


if __name__ == "__main__":
    main()

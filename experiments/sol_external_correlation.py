"""Sol-interviewer estimates vs aibenchmarks Elo, Epoch ECI, and the AA index.

    python -m experiments.sol_external_correlation
"""
from __future__ import annotations

import json
from pathlib import Path

from experiments.external_correlation import ALIASES
from experiments.selfsteer_vs_epoch import pearson, spearman

EXP = Path(__file__).resolve().parent
BENCH = Path(r"C:\Projects\llm-leaderboard\data\nodes\benchmarks")


def scores_of(filename: str) -> dict[str, float]:
    payload = json.loads((BENCH / filename).read_text(encoding="utf-8"))
    return {e["model"]: float(e["score"]) for e in payload["scores"]["unified"]}


def main() -> None:
    results = json.loads((EXP / "sol_interview_results.json").read_text(encoding="utf-8"))
    ladders, verdicts, truths = results["ladders"], results["verdicts"], results["truths"]
    rows = {}
    for filename in ("method_battle_data.json", "frontier_test_data.json"):
        for name, record in json.loads((EXP / filename).read_text(encoding="utf-8"))["models"].items():
            rows[name] = record["leaderboard_row"]

    external = {
        "aibenchmarks Elo": ({row: truths[n] for n, row in rows.items() if n in truths}, {}),
        "Epoch ECI": (scores_of("epoch-ai-eci.json"), ALIASES.get("epoch_eci", {})),
        "AA index": (scores_of("artificial-analysis-intelligence-index.json"), ALIASES.get("aa_index", {})),
    }
    print(f"{'reference':<18} {'n':>3} {'ladder ρ':>9} {'ladder r':>9} {'verdict ρ':>10} {'truth ρ (ceiling)':>18}")
    for label, (scores, aliases) in external.items():
        rows_matched = []
        for name in ladders:
            row = aliases.get(rows.get(name, ""), rows.get(name, ""))
            if row in scores:
                rows_matched.append((ladders[name], verdicts[name], truths[name], scores[row]))
        lad = [m[0] for m in rows_matched]
        ver = [m[1] for m in rows_matched]
        tru = [m[2] for m in rows_matched]
        ext = [m[3] for m in rows_matched]
        ceiling = spearman(tru, ext) if label != "aibenchmarks Elo" else 1.0
        print(
            f"{label:<18} {len(rows_matched):>3} {spearman(lad, ext):>9.3f} "
            f"{pearson(lad, ext):>9.3f} {spearman(ver, ext):>10.3f} {ceiling:>18.3f}"
        )


if __name__ == "__main__":
    main()

"""Saturation test: score frontier models far above the calibration bank.

Collects 7 models (public Elo 1744-1911, all above or at the bank's 1749
ceiling) into frontier_test_data.json — kept separate so the reference bank
stays pure — then scores them with the SHIPPED holistic calibration,
extrapolating exactly as production would for a frontier model today.

Predictions under test (made before running):
  1. raw grader reads saturate near ~1950 regardless of true Elo;
  2. within-frontier rank discrimination collapses in the raw reads;
  3. calibrated MAE blows out far above the in-bank 86.

    python -m experiments.frontier_test
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import experiments.method_battle as battle
from viberank.holistic import HolisticCalibration

FRONTIER_DATA_PATH = Path(__file__).resolve().parent / "frontier_test_data.json"

FRONTIER_TARGETS: tuple[tuple[str, str, float, str], ...] = (
    ("openrouter", "openai/gpt-5.2", 1744.0, "GPT-5.2"),
    ("openrouter", "moonshotai/kimi-k2.6", 1758.0, "Kimi K2.6"),
    ("openrouter", "qwen/qwen3.6-plus", 1759.0, "Qwen 3.6 Plus"),
    ("openrouter", "deepseek/deepseek-v4-pro", 1775.0, "DeepSeek V4 Pro"),
    ("openrouter", "openai/gpt-5.4", 1829.0, "GPT-5.4"),
    ("openrouter", "anthropic/claude-opus-4.8", 1906.0, "Claude Opus 4.8"),
    ("openrouter", "openai/gpt-5.5", 1911.0, "GPT-5.5"),
)


def spearman(left: list[float], right: list[float]) -> float:
    def ranks(values):
        order = sorted(range(len(values)), key=values.__getitem__)
        out = [0.0] * len(values)
        for rank, index in enumerate(order):
            out[index] = float(rank)
        return out

    lr, rr = ranks(left), ranks(right)
    lm, rm = sum(lr) / len(lr), sum(rr) / len(rr)
    num = sum((a - lm) * (b - rm) for a, b in zip(lr, rr))
    den = math.sqrt(sum((a - lm) ** 2 for a in lr) * sum((b - rm) ** 2 for b in rr))
    return num / den if den else 0.0


def main() -> None:
    battle.DATA_PATH = FRONTIER_DATA_PATH
    battle.TARGETS = FRONTIER_TARGETS
    data = battle.collect_all()

    calibration = HolisticCalibration.load()
    if calibration is None or not calibration.usable:
        raise SystemExit("Shipped holistic-calibration.json not found or unusable")

    models = data["models"]
    rows = []
    for name, record in models.items():
        raw_reads = [read["mean_elo"] for read in record["holistic_prefixes"]]
        corrected, sigma = calibration.apply(len(raw_reads), raw_reads[-1])
        rows.append(
            {
                "model": name,
                "true": record["public_elo"],
                "raw_final": raw_reads[-1],
                "raw_reads": raw_reads,
                "corrected": round(corrected, 1),
                "sigma": round(sigma, 1),
                "error": round(corrected - record["public_elo"], 1),
            }
        )
    rows.sort(key=lambda r: r["true"])

    truths = [r["true"] for r in rows]
    raws = [r["raw_final"] for r in rows]
    correcteds = [r["corrected"] for r in rows]
    errors = [abs(r["error"]) for r in rows]

    print(f"\n{'model':<30} {'true':>5} {'raw@5':>6} {'corrected':>10} {'err':>6}")
    for r in rows:
        print(
            f"{r['model']:<30} {r['true']:>5.0f} {r['raw_final']:>6.0f} "
            f"{r['corrected']:>10.0f} {r['error']:>+6.0f}"
        )
    raw_spread = max(raws) - min(raws)
    true_spread = max(truths) - min(truths)
    print(f"\ntrue spread {true_spread:.0f} Elo -> raw read spread {raw_spread:.0f} Elo")
    print(f"raw-vs-true spearman (n={len(rows)}): {spearman(truths, raws):.3f}")
    print(f"corrected-vs-true spearman:          {spearman(truths, correcteds):.3f}")
    print(f"out-of-bank MAE: {sum(errors) / len(errors):.0f}  (in-bank LOO was 86)")
    print(f"mean signed error: {sum(r['error'] for r in rows) / len(rows):+.0f}")

    out = FRONTIER_DATA_PATH.with_name("frontier_test_results.json")
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nSaved {out}")


if __name__ == "__main__":
    main()

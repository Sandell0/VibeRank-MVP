"""Fit the holistic-channel calibration from a collected reference bank.

    python -m viberank.calibrate_holistic [--data experiments/method_battle_data.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .holistic import fit_holistic_calibration, holistic_calibration_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("experiments") / "method_battle_data.json",
        help="reference bank collected by experiments.method_battle",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data = json.loads(args.data.read_text(encoding="utf-8"))
    bank = {
        name: {
            "true_elo": record["public_elo"],
            "prefix_reads": [read["mean_elo"] for read in record["holistic_prefixes"]],
        }
        for name, record in data["models"].items()
        if "holistic_prefixes" in record
    }
    grader_model = data.get("grader_model") or "mistral-medium-3.5"
    calibration = fit_holistic_calibration(bank, grader_model=grader_model)

    print(f"Bank: {calibration.n_models} models, spread {calibration.elo_spread:.0f} Elo")
    print(f"Usable: {calibration.usable} ({calibration.reason})")
    for prefix, fit in sorted(calibration.per_prefix.items()):
        print(
            f"  after Q{prefix}: raw = {fit.intercept:.0f} + {fit.slope:.3f} x true; "
            f"sigma {fit.sigma_elo:.0f} Elo"
        )
    if not calibration.usable:
        raise SystemExit(1)
    if args.dry_run:
        print("Dry run: nothing written.")
        return
    saved = calibration.save(args.output or holistic_calibration_path())
    print(f"Saved to {saved}")


if __name__ == "__main__":
    main()

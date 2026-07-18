"""Fit the direct-regression texture channel against models of known Elo.

Free plumbing check (no API keys):

    python -m viberank.calibrate --simulate

Live calibration (requires MISTRAL_API_KEY, plus OPENROUTER_API_KEY for openrouter):

    python -m viberank.calibrate --provider openrouter --models "id=1521,id=1645,..."

Each live model answers the fixed debug questions once; the grader's raw
apparent-Elo reads are regressed on the known public Elos. The fitted map and
the measured noise components are written to the calibration file, which
activates the channel in `python -m viberank` runs.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .calibration import (
    DirectCalibration,
    DirectObservation,
    calibration_path,
    fit_direct_calibration,
)
from .clients import mistral_client, openrouter_client
from .debug_questions import FIXED_DEBUG_QUESTIONS
from .evaluation import (
    EvaluationConfig,
    _empty_usage,
    _add_usage,
    _generate_answer,
    _usage_cost,
    run_evaluation,
    simulated_calibration,
)
from .grading import MistralGrader


def _parse_models(raw: str) -> list[tuple[str, float]]:
    pairs = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise SystemExit(f"Expected model=elo, got: {chunk}")
        model, _, elo = chunk.rpartition("=")
        pairs.append((model.strip(), float(elo)))
    return pairs


def _collect_live_observations(
    provider: str,
    models: list[tuple[str, float]],
    questions: int,
    usage_totals: dict[str, dict[str, int]],
) -> list[DirectObservation]:
    grader = MistralGrader(mistral_client())
    observations: list[DirectObservation] = []
    for model_id, true_elo in models:
        target_client = (
            openrouter_client(model_id) if provider == "openrouter" else mistral_client(model_id)
        )
        print(f"  {model_id} (public Elo {true_elo:.0f})...")
        for question in FIXED_DEBUG_QUESTIONS[:questions]:
            answer, target_usage = _generate_answer(target_client, question)
            grade, grader_usage = grader.grade_with_usage(question, answer)
            _add_usage(usage_totals["target"], target_usage)
            _add_usage(usage_totals["grader"], grader_usage)
            if grade.apparent_elo is None:
                print(f"    {question.id}: grader returned no apparent_elo, skipping")
                continue
            observations.append(
                DirectObservation(model=model_id, true_elo=true_elo, raw_guess=grade.apparent_elo)
            )
            print(f"    {question.id}: raw texture read {grade.apparent_elo:.0f}")
    return observations


def _report(calibration: DirectCalibration) -> None:
    print("\nFit:")
    print(f"  usable      {calibration.usable} ({calibration.reason})")
    print(
        f"  model       raw = {calibration.intercept:.1f} + {calibration.slope:.3f} x true; "
        f"applied as calibrated = (raw - {calibration.intercept:.1f}) / {calibration.slope:.3f}"
    )
    print(f"  r-squared   {calibration.r_squared:.3f}")
    print(f"  tau         {calibration.tau_elo:.0f} Elo (shared per-model grader bias)")
    print(f"  sigma_w     {calibration.sigma_w_elo:.0f} Elo (independent per-answer noise)")
    print(f"  data        {calibration.n_observations} reads across {calibration.n_models} models")
    if calibration.per_model:
        print("\n  model                                    true    raw->calibrated")
        for row in calibration.per_model:
            print(
                f"  {str(row['model'])[:40]:<40} {row['true_elo']:>6} "
                f"{row['mean_raw_guess']:>7} -> {row['mean_calibrated']}"
            )


def _simulate_demo(output: Path) -> None:
    """Show the same seeds with the channel off and on, using the saved file."""
    previous = os.environ.get("VIBERANK_CALIBRATION_PATH")
    try:
        print("\nPosterior SD on identical simulated runs (target 1600, 5 questions):")
        for label, path in (("channel off", str(output) + ".missing"), ("channel on", str(output))):
            os.environ["VIBERANK_CALIBRATION_PATH"] = path
            sds = []
            errors = []
            for seed in range(20):
                result = run_evaluation(
                    EvaluationConfig(
                        provider="simulation",
                        model="synthetic-1600",
                        questions=5,
                        target_elo=1600.0,
                        seed=3000 + seed,
                    )
                )
                sds.append(result["estimate"]["standard_deviation"])
                errors.append(result["absolute_error"])
            print(
                f"  {label:<12} mean posterior SD {sum(sds) / len(sds):>6.1f}   "
                f"MAE {sum(errors) / len(errors):>6.1f}"
            )
    finally:
        if previous is None:
            os.environ.pop("VIBERANK_CALIBRATION_PATH", None)
        else:
            os.environ["VIBERANK_CALIBRATION_PATH"] = previous


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--simulate", action="store_true", help="fit on synthetic reads, no API calls")
    parser.add_argument("--provider", choices=("mistral", "openrouter"), default="openrouter")
    parser.add_argument("--models", default="", help='comma-separated "model=elo" pairs')
    parser.add_argument("--questions", type=int, default=len(FIXED_DEBUG_QUESTIONS))
    parser.add_argument("--output", type=Path, default=None, help="calibration file path")
    parser.add_argument("--seed", type=int, default=29, help="seed for --simulate")
    parser.add_argument("--dry-run", action="store_true", help="fit and report without saving")
    args = parser.parse_args()

    output = args.output or calibration_path()
    questions = max(2, min(args.questions, len(FIXED_DEBUG_QUESTIONS)))

    if args.simulate:
        print(f"Fitting on synthetic texture reads (seed {args.seed})...")
        calibration = simulated_calibration(seed=args.seed, answers_per_model=questions)
    else:
        models = _parse_models(args.models)
        if not models:
            raise SystemExit("Provide --models \"model=elo,model=elo,...\" or use --simulate")
        usage_totals = {"target": _empty_usage(), "grader": _empty_usage()}
        print(f"Collecting {questions} graded answers per model via {args.provider}...")
        observations = _collect_live_observations(args.provider, models, questions, usage_totals)
        grader_model = os.environ.get("MISTRAL_GRADER_MODEL", "mistral-medium-3.5")
        calibration = fit_direct_calibration(observations, grader_model=grader_model)
        grader_cost = _usage_cost(usage_totals["grader"], grader_model)
        total_tokens = (
            usage_totals["target"]["total_tokens"] + usage_totals["grader"]["total_tokens"]
        )
        print(f"\nTokens: {total_tokens:,} total"
              + (f"; grader cost ${grader_cost:.4f}" if grader_cost is not None else ""))

    _report(calibration)

    if not calibration.usable:
        print("\nNot saved: the channel stays off until calibration passes the honesty guards.")
        sys.exit(1)
    if args.dry_run:
        print("\nDry run: nothing written.")
        return
    saved = calibration.save(output)
    print(f"\nSaved to {saved}. Runs of `python -m viberank` now use the channel.")
    if args.simulate:
        _simulate_demo(saved)


if __name__ == "__main__":
    main()

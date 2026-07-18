"""Per-question Elo-error trajectories: refit factorized vs holistic reads.

For each reference model (leave-one-out):
  - refit ordinal   — item difficulties fit on the other models' grades, then
                      the posterior updated question by question;
  - legacy ordinal  — same posterior with the original hand-assigned
                      difficulties, as the before-refit reference;
  - holistic        — the grader's direct read after each transcript prefix.

Prints the mean absolute error after each question and writes
trajectory_results.json next to this file.

    python -m experiments.trajectory_analysis
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from viberank.debug_questions import FIXED_DEBUG_QUESTIONS
from viberank.domain import Grade
from viberank.irt import EloPosterior
from viberank.item_calibration import ItemObservation, fit_item_calibration

DATA_PATH = Path(__file__).resolve().parent / "method_battle_data.json"
RESULTS_PATH = Path(__file__).resolve().parent / "trajectory_results.json"
QUESTION_COUNT = len(FIXED_DEBUG_QUESTIONS)


def load_models() -> tuple[dict, str]:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    models = {
        name: record
        for name, record in data["models"].items()
        if "holistic_prefixes" in record
    }
    return models, data.get("grader_model") or "mistral-medium-3.5"


def grade_objects(record: dict) -> list[Grade]:
    return [
        Grade(
            probabilities=tuple(graded["probabilities"]),  # type: ignore[arg-type]
            error_type=graded["error_type"],
            explanation=graded["explanation"],
            confidence=1.0,
        )
        for graded in record["grades"]
    ]


def ordinal_trajectory(record: dict, questions) -> list[float]:
    posterior = EloPosterior()
    trajectory = []
    for question, grade in zip(questions, grade_objects(record)):
        posterior.update(question, grade)
        trajectory.append(posterior.summary().mean_elo)
    return trajectory


def loo_prefix_fit(models: dict, held_out: str, prefix_index: int) -> tuple[float, float] | None:
    """Classical fit raw = a + b*true for one prefix length, excluding held_out."""
    pairs = [
        (record["public_elo"], record["holistic_prefixes"][prefix_index]["mean_elo"])
        for name, record in models.items()
        if name != held_out
    ]
    n = len(pairs)
    true_mean = sum(t for t, _ in pairs) / n
    raw_mean = sum(r for _, r in pairs) / n
    true_var = sum((t - true_mean) ** 2 for t, _ in pairs)
    cov = sum((t - true_mean) * (r - raw_mean) for t, r in pairs)
    if true_var <= 0:
        return None
    slope = cov / true_var
    if slope <= 0.05:
        return None
    return raw_mean - slope * true_mean, slope


def spearman(left: list[float], right: list[float]) -> float:
    def ranks(values: list[float]) -> list[float]:
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
    models, grader_model = load_models()
    if len(models) < 5:
        raise SystemExit(f"Only {len(models)} models with prefix reads; need at least 5.")

    per_model: dict[str, dict] = {}
    fold_notes = []
    for name, record in models.items():
        observations = [
            ItemObservation(
                other,
                other_record["public_elo"],
                graded["question_id"],
                tuple(graded["probabilities"]),  # type: ignore[arg-type]
            )
            for other, other_record in models.items()
            if other != name
            for graded in other_record["grades"]
        ]
        calibration = fit_item_calibration(observations, grader_model=grader_model)
        if not calibration.usable:
            raise SystemExit(f"LOO fold for {name} unusable: {calibration.reason}")
        fold_notes.append(
            {
                "held_out": name,
                "discrimination": round(calibration.discrimination, 2),
                "difficulties": {
                    k: round(v) for k, v in sorted(calibration.difficulties.items())
                },
            }
        )
        refit_questions = calibration.apply_to_questions(FIXED_DEBUG_QUESTIONS)
        holistic_cal = []
        for prefix_index in range(QUESTION_COUNT):
            raw = record["holistic_prefixes"][prefix_index]["mean_elo"]
            fit = loo_prefix_fit(models, name, prefix_index)
            holistic_cal.append(raw if fit is None else (raw - fit[0]) / fit[1])
        per_model[name] = {
            "true": record["public_elo"],
            "refit": ordinal_trajectory(record, refit_questions),
            "legacy": ordinal_trajectory(record, FIXED_DEBUG_QUESTIONS),
            "holistic": [read["mean_elo"] for read in record["holistic_prefixes"]],
            "holistic_cal": holistic_cal,
        }

    arms = ("refit", "legacy", "holistic", "holistic_cal")
    names = list(per_model)
    truths = [per_model[n]["true"] for n in names]
    curves = {
        arm: [
            sum(abs(per_model[n][arm][k] - per_model[n]["true"]) for n in names) / len(names)
            for k in range(QUESTION_COUNT)
        ]
        for arm in arms
    }
    spearmen = {
        arm: [
            round(spearman(truths, [per_model[n][arm][k] for n in names]), 3)
            for k in range(QUESTION_COUNT)
        ]
        for arm in arms
    }

    print(f"Models: {len(names)}; span {min(truths):.0f}-{max(truths):.0f}\n")
    print("Mean absolute Elo error after each question:")
    print(
        f"{'after Q':>8} | {'refit ordinal':>13} | {'legacy ordinal':>14} | "
        f"{'holistic raw':>12} | {'holistic cal':>12}"
    )
    for k in range(QUESTION_COUNT):
        print(
            f"{k + 1:>8} | {curves['refit'][k]:>13.0f} | {curves['legacy'][k]:>14.0f} | "
            f"{curves['holistic'][k]:>12.0f} | {curves['holistic_cal'][k]:>12.0f}"
        )
    print("\nSpearman by question count:")
    for arm in arms:
        print(f"  {arm:<9} {spearmen[arm]}")

    RESULTS_PATH.write_text(
        json.dumps(
            {
                "models": per_model,
                "mae_curves": curves,
                "spearman_curves": spearmen,
                "loo_folds": fold_notes,
                "grader_model": grader_model,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved {RESULTS_PATH}")


if __name__ == "__main__":
    main()

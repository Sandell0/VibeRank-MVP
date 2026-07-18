"""Does the Bayesian machinery improve the FINAL point estimate over the raw
holistic read? All arms scored leave-one-out on the collected bank:

  holistic_raw   — the grader's full-transcript read, used as-is;
  holistic_cal   — the read passed through a LOO-fitted affine correction;
  prefix_avg     — mean of the last two prefix reads, raw (denoising check);
  fusion         — posterior combining the refit ordinal channel with the
                   corrected holistic read at its measured noise.

    python -m experiments.fusion_test
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
SIGMA_FLOOR = 50.0


def load_models() -> tuple[dict, str]:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    models = {
        name: record
        for name, record in data["models"].items()
        if "holistic_prefixes" in record
    }
    return models, data.get("grader_model") or "mistral-medium-3.5"


def loo_holistic_fit(models: dict, held_out: str) -> tuple[float, float, float] | None:
    """Classical fit raw = a + b*true on all but held_out; returns (a, b, sigma_elo)."""
    pairs = [
        (record["public_elo"], record["holistic"]["mean_elo"])
        for name, record in models.items()
        if name != held_out
    ]
    n = len(pairs)
    if n < 4:
        return None
    true_mean = sum(t for t, _ in pairs) / n
    raw_mean = sum(r for _, r in pairs) / n
    true_var = sum((t - true_mean) ** 2 for t, _ in pairs)
    cov = sum((t - true_mean) * (r - raw_mean) for t, r in pairs)
    if true_var <= 0:
        return None
    slope = cov / true_var
    if slope <= 0.05:
        return None
    intercept = raw_mean - slope * true_mean
    residuals = [(r - (intercept + slope * t)) / slope for t, r in pairs]
    df = n - 2
    variance = sum(v ** 2 for v in residuals) / df
    variance *= df / (df - 2) if df > 2 else 3.0
    return intercept, slope, max(SIGMA_FLOOR, math.sqrt(variance))


def refit_questions(models: dict, held_out: str, grader_model: str):
    observations = [
        ItemObservation(
            other,
            record["public_elo"],
            graded["question_id"],
            tuple(graded["probabilities"]),  # type: ignore[arg-type]
        )
        for other, record in models.items()
        if other != held_out
        for graded in record["grades"]
    ]
    calibration = fit_item_calibration(observations, grader_model=grader_model)
    if not calibration.usable:
        raise SystemExit(f"LOO item fold for {held_out} unusable: {calibration.reason}")
    return calibration.apply_to_questions(FIXED_DEBUG_QUESTIONS)


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
    models, grader_model = load_models()
    if len(models) < 5:
        raise SystemExit(f"Only {len(models)} models with prefix reads; need at least 5.")

    estimates: dict[str, dict[str, float]] = {
        "holistic_raw": {},
        "holistic_cal": {},
        "prefix_avg": {},
        "fusion": {},
    }
    for name, record in models.items():
        raw_read = record["holistic"]["mean_elo"]
        estimates["holistic_raw"][name] = raw_read
        prefixes = [read["mean_elo"] for read in record["holistic_prefixes"]]
        estimates["prefix_avg"][name] = sum(prefixes[-2:]) / 2

        fit = loo_holistic_fit(models, name)
        if fit is None:
            corrected, sigma = raw_read, 200.0
        else:
            intercept, slope, sigma = fit
            corrected = (raw_read - intercept) / slope
        estimates["holistic_cal"][name] = corrected

        posterior = EloPosterior()
        questions = refit_questions(models, name, grader_model)
        for question, graded in zip(questions, record["grades"]):
            posterior.update(
                question,
                Grade(
                    probabilities=tuple(graded["probabilities"]),  # type: ignore[arg-type]
                    error_type=graded["error_type"],
                    explanation=graded["explanation"],
                    confidence=1.0,
                ),
            )
        posterior.observe_direct(corrected, tau_elo=0.0, sigma_w_elo=sigma)
        estimates["fusion"][name] = posterior.summary().mean_elo

    names = list(models)
    truths = [models[n]["public_elo"] for n in names]
    print(f"Models: {len(names)}; span {min(truths):.0f}-{max(truths):.0f}\n")
    print(f"{'arm':<14} {'MAE':>6} {'median':>7} {'max':>6} {'spearman':>9}")
    for arm, values in estimates.items():
        errors = [abs(values[n] - models[n]["public_elo"]) for n in names]
        rho = spearman(truths, [values[n] for n in names])
        print(
            f"{arm:<14} {sum(errors) / len(errors):>6.0f} "
            f"{sorted(errors)[len(errors) // 2]:>7.0f} {max(errors):>6.0f} {rho:>9.3f}"
        )
    print("\nPer-model (true | raw -> cal -> fusion):")
    for n in names:
        print(
            f"  {n:<36} {models[n]['public_elo']:>5.0f} | "
            f"{estimates['holistic_raw'][n]:>5.0f} -> {estimates['holistic_cal'][n]:>5.0f} "
            f"-> {estimates['fusion'][n]:>5.0f}"
        )


if __name__ == "__main__":
    main()

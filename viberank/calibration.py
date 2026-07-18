from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DEFAULT_CALIBRATION_FILENAME = "calibration.json"

# Honesty guards. A small or degenerate calibration sample must widen the
# channel or disable it, never manufacture near-zero measured noise.
MINIMUM_CALIBRATION_MODELS = 4
MINIMUM_OBSERVATIONS_PER_MODEL = 2
MINIMUM_TRUE_ELO_SPREAD = 250.0
MINIMUM_SIGMA_W_ELO = 50.0
MINIMUM_TAU_ELO = 25.0


def calibration_path() -> Path:
    return Path(os.environ.get("VIBERANK_CALIBRATION_PATH", DEFAULT_CALIBRATION_FILENAME))


@dataclass(frozen=True)
class DirectObservation:
    """One grader texture read: a raw apparent-Elo guess for one answer."""

    model: str
    true_elo: float
    raw_guess: float


@dataclass(frozen=True)
class DirectCalibration:
    """Affine map from raw grader guesses to the public Elo scale, with measured noise.

    ``intercept`` and ``slope`` are the measurement model fit by OLS of the
    raw guess on true Elo (classical calibration): ``raw = intercept +
    slope * true + noise``. ``apply`` inverts that map, which keeps the
    channel an unbiased likelihood in ability space — inverse regression
    (true on raw) would shrink extreme guesses toward the calibration
    population mean, silently acting as a second prior on top of the
    posterior's own and producing systematic edge-of-range bias.

    The residual noise, divided by the slope to express it in Elo, is
    decomposed into a per-evaluation shared bias with standard deviation
    ``tau_elo`` (the grader mis-reading one model's style in a correlated way
    across all of its answers) and independent per-answer noise
    ``sigma_w_elo``. The posterior treats the running mean of k calibrated
    guesses as one Gaussian observation with variance
    ``tau_elo**2 + sigma_w_elo**2 / k``, so correlated guesses never overcount.
    """

    intercept: float
    slope: float
    tau_elo: float
    sigma_w_elo: float
    n_models: int
    n_observations: int
    r_squared: float
    usable: bool
    reason: str
    grader_model: str
    per_model: tuple[dict[str, Any], ...] = ()

    def apply(self, raw_guess: float) -> float:
        """Invert the measurement model: the Elo at which this raw read is expected."""
        return (raw_guess - self.intercept) / self.slope

    def to_dict(self) -> dict[str, Any]:
        return {
            "intercept": round(self.intercept, 3),
            "slope": round(self.slope, 5),
            "tau_elo": round(self.tau_elo, 1),
            "sigma_w_elo": round(self.sigma_w_elo, 1),
            "n_models": self.n_models,
            "n_observations": self.n_observations,
            "r_squared": round(self.r_squared, 3),
            "usable": self.usable,
            "reason": self.reason,
            "grader_model": self.grader_model,
            "per_model": list(self.per_model),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "DirectCalibration":
        return cls(
            intercept=float(raw["intercept"]),
            slope=float(raw["slope"]),
            tau_elo=float(raw["tau_elo"]),
            sigma_w_elo=float(raw["sigma_w_elo"]),
            n_models=int(raw["n_models"]),
            n_observations=int(raw["n_observations"]),
            r_squared=float(raw.get("r_squared", 0.0)),
            usable=bool(raw.get("usable", False)),
            reason=str(raw.get("reason", "")),
            grader_model=str(raw.get("grader_model", "unknown")),
            per_model=tuple(raw.get("per_model", [])),
        )

    def save(self, path: Path | None = None) -> Path:
        target = path or calibration_path()
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: Path | None = None) -> "DirectCalibration | None":
        target = path or calibration_path()
        if not target.is_file():
            return None
        try:
            return cls.from_dict(json.loads(target.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None


def load_calibration(path: Path | None = None) -> DirectCalibration | None:
    return DirectCalibration.load(path)


def _unusable(reason: str, *, grader_model: str, n_models: int, n_observations: int) -> DirectCalibration:
    return DirectCalibration(
        intercept=0.0,
        slope=0.0,
        tau_elo=0.0,
        sigma_w_elo=0.0,
        n_models=n_models,
        n_observations=n_observations,
        r_squared=0.0,
        usable=False,
        reason=reason,
        grader_model=grader_model,
    )


def fit_direct_calibration(
    observations: Iterable[DirectObservation],
    *,
    grader_model: str = "unknown",
) -> DirectCalibration:
    """Fit true Elo on raw guesses, then decompose residual variance.

    Between-model variance of mean residuals estimates ``tau**2 + sigma_w**2/k``,
    so ``tau**2`` is recovered by subtracting the within-model component.
    """
    groups: dict[str, list[DirectObservation]] = {}
    for observation in observations:
        groups.setdefault(observation.model, []).append(observation)
    pooled = [observation for group in groups.values() for observation in group]
    n_models = len(groups)
    n_observations = len(pooled)

    if n_models < MINIMUM_CALIBRATION_MODELS:
        return _unusable(
            f"Need at least {MINIMUM_CALIBRATION_MODELS} calibration models, got {n_models}",
            grader_model=grader_model,
            n_models=n_models,
            n_observations=n_observations,
        )
    if any(len(group) < MINIMUM_OBSERVATIONS_PER_MODEL for group in groups.values()):
        return _unusable(
            f"Need at least {MINIMUM_OBSERVATIONS_PER_MODEL} graded answers per model",
            grader_model=grader_model,
            n_models=n_models,
            n_observations=n_observations,
        )
    true_values = [group[0].true_elo for group in groups.values()]
    spread = max(true_values) - min(true_values)
    if spread < MINIMUM_TRUE_ELO_SPREAD:
        return _unusable(
            f"Calibration models span only {spread:.0f} Elo; need at least {MINIMUM_TRUE_ELO_SPREAD:.0f}",
            grader_model=grader_model,
            n_models=n_models,
            n_observations=n_observations,
        )

    raw_mean = sum(observation.raw_guess for observation in pooled) / n_observations
    true_mean = sum(observation.true_elo for observation in pooled) / n_observations
    raw_variance = sum((observation.raw_guess - raw_mean) ** 2 for observation in pooled)
    covariance = sum(
        (observation.raw_guess - raw_mean) * (observation.true_elo - true_mean)
        for observation in pooled
    )
    true_variance = sum((observation.true_elo - true_mean) ** 2 for observation in pooled)
    # Measurement model: raw = intercept + slope * true. Fitting this
    # direction (not true on raw) keeps apply() free of population shrinkage.
    slope = covariance / true_variance
    if slope <= 1e-6:
        return _unusable(
            "Raw guesses do not increase with true Elo; the texture read carries no signal",
            grader_model=grader_model,
            n_models=n_models,
            n_observations=n_observations,
        )
    intercept = raw_mean - slope * true_mean
    r_squared = (
        (covariance ** 2) / (raw_variance * true_variance) if raw_variance > 0 else 0.0
    )

    # Residuals on the raw scale, then divided by the slope so both noise
    # components are expressed in Elo, matching apply().
    residuals_by_model: dict[str, list[float]] = {
        model: [
            (observation.raw_guess - (intercept + slope * observation.true_elo)) / slope
            for observation in group
        ]
        for model, group in groups.items()
    }
    within_sum = 0.0
    within_df = 0
    for residuals in residuals_by_model.values():
        model_mean = sum(residuals) / len(residuals)
        within_sum += sum((value - model_mean) ** 2 for value in residuals)
        within_df += len(residuals) - 1
    sigma_w_squared = within_sum / within_df if within_df > 0 else 0.0

    model_means = [sum(residuals) / len(residuals) for residuals in residuals_by_model.values()]
    grand_mean = sum(model_means) / n_models
    between_variance = sum((value - grand_mean) ** 2 for value in model_means) / (n_models - 1)
    mean_group_size = n_observations / n_models
    tau_squared = max(0.0, between_variance - sigma_w_squared / mean_group_size)

    # Small-sample honesty: the variance components are themselves estimates,
    # so plugging them in as exact would be overconfident. Inflate each by the
    # t-predictive factor df/(df-2) for its degrees of freedom; more
    # calibration models shrink the inflation toward 1.
    between_df = n_models - 1
    within_inflation = within_df / (within_df - 2) if within_df > 2 else 3.0
    between_inflation = between_df / (between_df - 2) if between_df > 2 else 3.0
    sigma_w_squared *= within_inflation
    tau_squared *= between_inflation

    sigma_w = max(MINIMUM_SIGMA_W_ELO, math.sqrt(sigma_w_squared))
    tau = max(MINIMUM_TAU_ELO, math.sqrt(tau_squared))

    per_model = tuple(
        {
            "model": model,
            "true_elo": round(group[0].true_elo, 1),
            "mean_raw_guess": round(sum(o.raw_guess for o in group) / len(group), 1),
            "mean_calibrated": round(
                (sum(o.raw_guess for o in group) / len(group) - intercept) / slope, 1
            ),
            "answers": len(group),
        }
        for model, group in groups.items()
    )
    return DirectCalibration(
        intercept=intercept,
        slope=slope,
        tau_elo=tau,
        sigma_w_elo=sigma_w,
        n_models=n_models,
        n_observations=n_observations,
        r_squared=r_squared,
        usable=True,
        reason="ok",
        grader_model=grader_model,
        per_model=per_model,
    )

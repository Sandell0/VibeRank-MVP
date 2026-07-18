from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .domain import Grade, Question


ELO_LOGISTIC_SCALE = 400.0 / math.log(10.0)


def _softmax(logits: Iterable[float]) -> list[float]:
    values = list(logits)
    peak = max(values)
    weights = [math.exp(value - peak) for value in values]
    total = sum(weights)
    return [weight / total for weight in weights]


def gpcm_probabilities(
    ability_elo: float,
    difficulty_elo: float,
    discrimination: float,
    step_offsets_elo: tuple[float, ...],
) -> list[float]:
    """Generalized partial-credit probabilities for the ordinal grades."""
    logits = [0.0]
    running = 0.0
    for offset in step_offsets_elo:
        transition = difficulty_elo + offset
        running += discrimination * (ability_elo - transition) / ELO_LOGISTIC_SCALE
        logits.append(running)
    return _softmax(logits)


def category_probabilities(question: Question, ability_elo: float) -> list[float]:
    return gpcm_probabilities(
        ability_elo,
        question.difficulty_elo,
        question.discrimination,
        question.step_offsets_elo,
    )


def _normalize(values: Iterable[float]) -> list[float]:
    result = list(values)
    total = sum(result)
    if total <= 0:
        raise ValueError("Cannot normalize zero probability mass")
    return [value / total for value in result]


def _entropy(probabilities: Iterable[float]) -> float:
    return -sum(p * math.log(p) for p in probabilities if p > 0)


@dataclass
class PosteriorSummary:
    mean_elo: float
    median_elo: float
    low_elo: float
    high_elo: float
    standard_deviation: float

    def to_dict(self) -> dict[str, float]:
        return {
            "mean_elo": round(self.mean_elo, 1),
            "median_elo": round(self.median_elo, 1),
            "low_elo": round(self.low_elo, 1),
            "high_elo": round(self.high_elo, 1),
            "standard_deviation": round(self.standard_deviation, 1),
        }


class EloPosterior:
    def __init__(
        self,
        minimum: int = 800,
        maximum: int = 2600,
        step: int = 10,
        prior_mean: float = 1500.0,
        prior_sd: float = 420.0,
    ) -> None:
        self.grid = list(range(minimum, maximum + 1, step))
        self._log_prior = [-0.5 * ((elo - prior_mean) / prior_sd) ** 2 for elo in self.grid]
        self._ordinal_log_likelihood = [0.0] * len(self.grid)
        self._direct_guesses: list[float] = []
        self._direct_tau_elo = 0.0
        self._direct_sigma_w_elo = 0.0
        self.probabilities: list[float] = []
        self._recompute()

    def _recompute(self) -> None:
        log_posterior = [
            prior + ordinal
            for prior, ordinal in zip(self._log_prior, self._ordinal_log_likelihood)
        ]
        if self._direct_guesses:
            count = len(self._direct_guesses)
            mean_guess = sum(self._direct_guesses) / count
            # The k calibrated guesses share one per-evaluation grader bias, so
            # their mean is a single Gaussian observation with this variance.
            variance = self._direct_tau_elo ** 2 + (self._direct_sigma_w_elo ** 2) / count
            log_posterior = [
                value - 0.5 * (elo - mean_guess) ** 2 / variance
                for value, elo in zip(log_posterior, self.grid)
            ]
        peak = max(log_posterior)
        self.probabilities = _normalize(math.exp(value - peak) for value in log_posterior)

    @property
    def entropy_nats(self) -> float:
        return _entropy(self.probabilities)

    @property
    def direct_observation_count(self) -> int:
        return len(self._direct_guesses)

    def update(self, question: Question, grade: Grade) -> None:
        observed = grade.normalized_probabilities
        for index, elo in enumerate(self.grid):
            model_probs = category_probabilities(question, elo)
            likelihood = sum(q * p for q, p in zip(observed, model_probs))
            self._ordinal_log_likelihood[index] += math.log(max(likelihood, 1e-12))
        self._recompute()

    def update_binary(self, question: Question, fully_correct_probability: float) -> None:
        q = max(0.0, min(1.0, fully_correct_probability))
        for index, elo in enumerate(self.grid):
            correct = category_probabilities(question, elo)[3]
            likelihood = q * correct + (1.0 - q) * (1.0 - correct)
            self._ordinal_log_likelihood[index] += math.log(max(likelihood, 1e-12))
        self._recompute()

    def observe_direct(
        self,
        calibrated_guess: float,
        *,
        tau_elo: float,
        sigma_w_elo: float,
    ) -> None:
        """Add one calibrated texture read from the grader.

        ``tau_elo`` and ``sigma_w_elo`` must come from a measured calibration,
        never from assumption; the update refuses degenerate noise so an
        uncalibrated channel cannot sharpen the posterior.
        """
        if sigma_w_elo <= 0 or tau_elo < 0:
            raise ValueError("Direct-channel noise must be measured and positive")
        self._direct_tau_elo = float(tau_elo)
        self._direct_sigma_w_elo = float(sigma_w_elo)
        self._direct_guesses.append(float(calibrated_guess))
        self._recompute()

    def _quantile(self, target: float) -> float:
        cumulative = 0.0
        for elo, probability in zip(self.grid, self.probabilities):
            cumulative += probability
            if cumulative >= target:
                return float(elo)
        return float(self.grid[-1])

    def summary(self) -> PosteriorSummary:
        mean = sum(elo * probability for elo, probability in zip(self.grid, self.probabilities))
        variance = sum(
            ((elo - mean) ** 2) * probability
            for elo, probability in zip(self.grid, self.probabilities)
        )
        return PosteriorSummary(
            mean_elo=mean,
            median_elo=self._quantile(0.5),
            low_elo=self._quantile(0.05),
            high_elo=self._quantile(0.95),
            standard_deviation=math.sqrt(variance),
        )

    def series(self) -> list[dict[str, float]]:
        peak = max(self.probabilities)
        return [
            {"elo": float(elo), "density": probability / peak}
            for elo, probability in zip(self.grid, self.probabilities)
        ]

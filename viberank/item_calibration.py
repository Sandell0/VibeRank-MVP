"""Fit fixed-question GPCM difficulties from live grades of known-Elo models.

This replaces the provisional hand-assigned difficulties with maximum-
likelihood estimates from a reference bank: each reference model has a known
public Elo and one graded (soft ordinal) response per question. Difficulties
are fit per item with one shared discrimination, holding the step offsets
fixed — few enough parameters that a small bank identifies them.

Production flow: fit on the whole bank, save the artifact, and the evaluator
scores unseen models with the fitted parameters. Leave-one-out refits of the
same function are the audit that estimates out-of-sample accuracy.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Sequence

from .domain import Question
from .irt import gpcm_probabilities


DEFAULT_ITEM_CALIBRATION_FILENAME = "item-calibration.json"

MINIMUM_REFERENCE_MODELS = 4
MINIMUM_TRUE_ELO_SPREAD = 250.0
# Discrimination is capped so a lucky small bank cannot claim razor items.
DISCRIMINATION_RANGE = (0.4, 3.0)
DIFFICULTY_RANGE = (600.0, 2800.0)


def item_calibration_path() -> Path:
    return Path(
        os.environ.get("VIBERANK_ITEM_CALIBRATION_PATH", DEFAULT_ITEM_CALIBRATION_FILENAME)
    )


@dataclass(frozen=True)
class ItemObservation:
    """One reference model's soft ordinal grade on one fixed question."""

    model: str
    true_elo: float
    question_id: str
    probabilities: tuple[float, float, float, float]


@dataclass(frozen=True)
class ItemCalibration:
    difficulties: dict[str, float]
    discrimination: float
    step_offsets_elo: tuple[float, float, float]
    grader_model: str
    n_models: int
    reference_models: tuple[str, ...]
    elo_spread: float
    usable: bool
    reason: str
    boundary_items: tuple[str, ...] = ()

    def apply_to_questions(self, questions: Sequence[Question]) -> list[Question]:
        """Return questions with fitted parameters where the bank covers them."""
        adjusted = []
        for question in questions:
            if question.id in self.difficulties:
                adjusted.append(
                    replace(
                        question,
                        difficulty_elo=self.difficulties[question.id],
                        discrimination=self.discrimination,
                    )
                )
            else:
                adjusted.append(question)
        return adjusted

    def to_dict(self) -> dict[str, Any]:
        return {
            "difficulties": {key: round(value, 1) for key, value in self.difficulties.items()},
            "discrimination": round(self.discrimination, 3),
            "step_offsets_elo": list(self.step_offsets_elo),
            "grader_model": self.grader_model,
            "n_models": self.n_models,
            "reference_models": list(self.reference_models),
            "elo_spread": round(self.elo_spread, 1),
            "usable": self.usable,
            "reason": self.reason,
            "boundary_items": list(self.boundary_items),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ItemCalibration":
        return cls(
            difficulties={str(k): float(v) for k, v in raw["difficulties"].items()},
            discrimination=float(raw["discrimination"]),
            step_offsets_elo=tuple(float(v) for v in raw.get("step_offsets_elo", (-160.0, 0.0, 160.0))),  # type: ignore[arg-type]
            grader_model=str(raw.get("grader_model", "unknown")),
            n_models=int(raw.get("n_models", 0)),
            reference_models=tuple(raw.get("reference_models", [])),
            elo_spread=float(raw.get("elo_spread", 0.0)),
            usable=bool(raw.get("usable", False)),
            reason=str(raw.get("reason", "")),
            boundary_items=tuple(raw.get("boundary_items", [])),
        )

    def save(self, path: Path | None = None) -> Path:
        target = path or item_calibration_path()
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: Path | None = None) -> "ItemCalibration | None":
        target = path or item_calibration_path()
        if not target.is_file():
            return None
        try:
            return cls.from_dict(json.loads(target.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None


def _unusable(reason: str, *, grader_model: str, n_models: int) -> ItemCalibration:
    return ItemCalibration(
        difficulties={},
        discrimination=1.0,
        step_offsets_elo=(-160.0, 0.0, 160.0),
        grader_model=grader_model,
        n_models=n_models,
        reference_models=(),
        elo_spread=0.0,
        usable=False,
        reason=reason,
    )


def _item_log_likelihood(
    difficulty: float,
    discrimination: float,
    step_offsets: tuple[float, ...],
    responses: list[tuple[float, tuple[float, float, float, float]]],
) -> float:
    """Cross-entropy of the soft grades under the item parameters.

    Soft grades enter as fractional counts (sum_k q_k log P_k), which is
    uniquely maximized where the model matches the grade distribution. The
    marginal form sum_k q_k P_k — correct for ability inference — is linear
    in P and would drive discrimination to the cap during fitting.
    """
    total = 0.0
    for true_elo, soft_grade in responses:
        model_probs = gpcm_probabilities(true_elo, difficulty, discrimination, step_offsets)
        total += sum(
            q * math.log(max(p, 1e-12))
            for q, p in zip(soft_grade, model_probs)
            if q > 0
        )
    return total


def _best_difficulty(
    discrimination: float,
    step_offsets: tuple[float, ...],
    responses: list[tuple[float, tuple[float, float, float, float]]],
) -> tuple[float, float]:
    low, high = DIFFICULTY_RANGE
    coarse = [low + 20.0 * index for index in range(int((high - low) / 20.0) + 1)]
    best = max(
        coarse,
        key=lambda b: _item_log_likelihood(b, discrimination, step_offsets, responses),
    )
    fine = [best - 20.0 + index for index in range(41)]
    best = max(
        (b for b in fine if low <= b <= high),
        key=lambda b: _item_log_likelihood(b, discrimination, step_offsets, responses),
    )
    return best, _item_log_likelihood(best, discrimination, step_offsets, responses)


def fit_item_calibration(
    observations: Iterable[ItemObservation],
    *,
    grader_model: str = "unknown",
    step_offsets: tuple[float, float, float] = (-160.0, 0.0, 160.0),
) -> ItemCalibration:
    pooled = list(observations)
    models: dict[str, float] = {}
    for observation in pooled:
        models[observation.model] = observation.true_elo
    n_models = len(models)
    if n_models < MINIMUM_REFERENCE_MODELS:
        return _unusable(
            f"Need at least {MINIMUM_REFERENCE_MODELS} reference models, got {n_models}",
            grader_model=grader_model,
            n_models=n_models,
        )
    spread = max(models.values()) - min(models.values())
    if spread < MINIMUM_TRUE_ELO_SPREAD:
        return _unusable(
            f"Reference models span only {spread:.0f} Elo; need at least {MINIMUM_TRUE_ELO_SPREAD:.0f}",
            grader_model=grader_model,
            n_models=n_models,
        )

    by_item: dict[str, list[tuple[float, tuple[float, float, float, float]]]] = {}
    for observation in pooled:
        by_item.setdefault(observation.question_id, []).append(
            (observation.true_elo, observation.probabilities)
        )

    def joint_fit(discrimination: float) -> tuple[dict[str, float], float]:
        difficulties = {}
        total = 0.0
        for item_id, responses in by_item.items():
            best, ll = _best_difficulty(discrimination, step_offsets, responses)
            difficulties[item_id] = best
            total += ll
        return difficulties, total

    a_low, a_high = DISCRIMINATION_RANGE
    coarse_grid = [a_low + 0.1 * index for index in range(int((a_high - a_low) / 0.1) + 1)]
    best_a = max(coarse_grid, key=lambda a: joint_fit(a)[1])
    fine_grid = [
        value
        for value in (best_a + 0.01 * index for index in range(-9, 10))
        if a_low <= value <= a_high
    ]
    best_a = max(fine_grid, key=lambda a: joint_fit(a)[1])
    difficulties, _ = joint_fit(best_a)

    low, high = DIFFICULTY_RANGE
    boundary = tuple(
        item_id
        for item_id, value in difficulties.items()
        if value <= low + 1.0 or value >= high - 1.0
    )
    return ItemCalibration(
        difficulties=difficulties,
        discrimination=best_a,
        step_offsets_elo=step_offsets,
        grader_model=grader_model,
        n_models=n_models,
        reference_models=tuple(sorted(models)),
        elo_spread=spread,
        usable=True,
        reason="ok",
        boundary_items=boundary,
    )

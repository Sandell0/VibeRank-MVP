"""Holistic transcript channel — the production primary estimator.

The grader reads the whole transcript (questions, private references, rubrics,
answers so far) and emits a direct Elo read. Raw reads carry a systematic
scale distortion, so a per-prefix affine correction is fit against a reference
bank of models with known public Elo (classical calibration: raw = a + b*true,
inverted at apply time), with residual noise measured per prefix length and
t-inflated for the bank size. The corrected read is the headline estimate;
the ordinal channel stays as a diagnostic.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .clients import ChatClient
from .domain import Question
from .grading import _extract_json


DEFAULT_HOLISTIC_CALIBRATION_FILENAME = "holistic-calibration.json"

MINIMUM_BANK_MODELS = 5
MINIMUM_TRUE_ELO_SPREAD = 250.0
MINIMUM_SLOPE = 0.05
SIGMA_FLOOR_ELO = 50.0
INTERVAL_Z = 1.645


def holistic_calibration_path() -> Path:
    return Path(
        os.environ.get(
            "VIBERANK_HOLISTIC_CALIBRATION_PATH", DEFAULT_HOLISTIC_CALIBRATION_FILENAME
        )
    )


def holistic_read(
    client: ChatClient,
    questions: Sequence[Question],
    answers: Sequence[str],
) -> tuple[dict[str, Any], dict[str, int | None]]:
    """One direct transcript read: mean Elo, self-reported 90% band, evidence."""
    count = len(answers)
    blocks = []
    for index, (question, answer) in enumerate(zip(questions, answers), start=1):
        rubric = "\n".join(f"- {criterion}" for criterion in question.rubric)
        blocks.append(
            f"""QUESTION {index}: {question.prompt}

PRIVATE REFERENCE: {question.reference_answer}

RUBRIC:
{rubric}

CANDIDATE ANSWER: {answer}"""
        )
    transcript = "\n\n---\n\n".join(blocks)
    plural = "s" if count != 1 else ""
    prompt = f"""You are a calibrated evaluator. Below is one anonymous language model's transcript: {count} reasoning question{plural}, each with a private reference answer, a rubric, and the model's answer.

Read the whole transcript jointly — consistency across answers, error character, reasoning depth — and estimate the model's ability as an Elo on a scale where 1000 is a very weak small model, 1400 is a capable mid-tier model, 1800 is a strong frontier model, and 2200 is exceptional. Judge correctness and demonstrated reasoning, not verbosity or style. Keep the 90% interval honest for evidence from only {count} answer{plural}.

Return JSON only:
{{
  "mean_elo": 0,
  "low_90": 0,
  "high_90": 0,
  "assessment": "brief evidence-based summary"
}}

TRANSCRIPT
{transcript}"""
    result = client.complete_with_usage(
        [
            {
                "role": "system",
                "content": (
                    "Return strict JSON. Estimate ability from the full transcript "
                    "and preserve honest uncertainty."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        json_mode=True,
    )
    raw = _extract_json(result.content)
    return (
        {
            "mean_elo": float(raw.get("mean_elo", 0.0)),
            "low_90": float(raw.get("low_90", 0.0)),
            "high_90": float(raw.get("high_90", 0.0)),
            "assessment": str(raw.get("assessment", "")),
        },
        result.usage_dict(),
    )


@dataclass(frozen=True)
class PrefixFit:
    intercept: float
    slope: float
    sigma_elo: float

    def to_dict(self) -> dict[str, float]:
        return {
            "intercept": round(self.intercept, 3),
            "slope": round(self.slope, 5),
            "sigma_elo": round(self.sigma_elo, 1),
        }


@dataclass(frozen=True)
class HolisticCalibration:
    per_prefix: dict[int, PrefixFit]
    grader_model: str
    n_models: int
    reference_models: tuple[str, ...]
    elo_spread: float
    usable: bool
    reason: str

    def apply(self, prefix: int, raw_mean_elo: float) -> tuple[float, float]:
        """Corrected estimate and measured noise for a read after `prefix` questions."""
        if not self.per_prefix:
            raise ValueError("Holistic calibration has no fitted prefixes")
        key = min(self.per_prefix, key=lambda k: abs(k - prefix))
        fit = self.per_prefix[key]
        return (raw_mean_elo - fit.intercept) / fit.slope, fit.sigma_elo

    def to_dict(self) -> dict[str, Any]:
        return {
            "per_prefix": {str(k): fit.to_dict() for k, fit in self.per_prefix.items()},
            "grader_model": self.grader_model,
            "n_models": self.n_models,
            "reference_models": list(self.reference_models),
            "elo_spread": round(self.elo_spread, 1),
            "usable": self.usable,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "HolisticCalibration":
        return cls(
            per_prefix={
                int(k): PrefixFit(
                    intercept=float(v["intercept"]),
                    slope=float(v["slope"]),
                    sigma_elo=float(v["sigma_elo"]),
                )
                for k, v in raw.get("per_prefix", {}).items()
            },
            grader_model=str(raw.get("grader_model", "unknown")),
            n_models=int(raw.get("n_models", 0)),
            reference_models=tuple(raw.get("reference_models", [])),
            elo_spread=float(raw.get("elo_spread", 0.0)),
            usable=bool(raw.get("usable", False)),
            reason=str(raw.get("reason", "")),
        )

    def save(self, path: Path | None = None) -> Path:
        target = path or holistic_calibration_path()
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: Path | None = None) -> "HolisticCalibration | None":
        target = path or holistic_calibration_path()
        if not target.is_file():
            return None
        try:
            return cls.from_dict(json.loads(target.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None


def _unusable(reason: str, *, grader_model: str, n_models: int) -> HolisticCalibration:
    return HolisticCalibration(
        per_prefix={},
        grader_model=grader_model,
        n_models=n_models,
        reference_models=(),
        elo_spread=0.0,
        usable=False,
        reason=reason,
    )


def fit_holistic_calibration(
    bank: dict[str, dict[str, Any]],
    *,
    grader_model: str = "unknown",
) -> HolisticCalibration:
    """Fit per-prefix affine corrections from a reference bank.

    ``bank`` maps model name -> {"true_elo": float, "prefix_reads": [read after
    Q1, ..., read after Qn]} with equal-length read lists.
    """
    n_models = len(bank)
    if n_models < MINIMUM_BANK_MODELS:
        return _unusable(
            f"Need at least {MINIMUM_BANK_MODELS} reference models, got {n_models}",
            grader_model=grader_model,
            n_models=n_models,
        )
    truths = [float(entry["true_elo"]) for entry in bank.values()]
    spread = max(truths) - min(truths)
    if spread < MINIMUM_TRUE_ELO_SPREAD:
        return _unusable(
            f"Reference models span only {spread:.0f} Elo; need at least {MINIMUM_TRUE_ELO_SPREAD:.0f}",
            grader_model=grader_model,
            n_models=n_models,
        )
    lengths = {len(entry["prefix_reads"]) for entry in bank.values()}
    if len(lengths) != 1:
        return _unusable(
            "Reference models have differing prefix-read counts",
            grader_model=grader_model,
            n_models=n_models,
        )
    prefix_count = lengths.pop()

    per_prefix: dict[int, PrefixFit] = {}
    for index in range(prefix_count):
        pairs = [
            (float(entry["true_elo"]), float(entry["prefix_reads"][index]))
            for entry in bank.values()
        ]
        true_mean = sum(t for t, _ in pairs) / n_models
        raw_mean = sum(r for _, r in pairs) / n_models
        true_var = sum((t - true_mean) ** 2 for t, _ in pairs)
        cov = sum((t - true_mean) * (r - raw_mean) for t, r in pairs)
        slope = cov / true_var if true_var > 0 else 0.0
        if slope <= MINIMUM_SLOPE:
            continue
        intercept = raw_mean - slope * true_mean
        residuals = [(r - (intercept + slope * t)) / slope for t, r in pairs]
        df = n_models - 2
        variance = sum(v ** 2 for v in residuals) / df
        variance *= df / (df - 2) if df > 2 else 3.0
        per_prefix[index + 1] = PrefixFit(
            intercept=intercept,
            slope=slope,
            sigma_elo=max(SIGMA_FLOOR_ELO, math.sqrt(variance)),
        )

    if prefix_count not in per_prefix:
        return _unusable(
            "Final-prefix reads carry no positive signal against true Elo",
            grader_model=grader_model,
            n_models=n_models,
        )
    return HolisticCalibration(
        per_prefix=per_prefix,
        grader_model=grader_model,
        n_models=n_models,
        reference_models=tuple(sorted(bank)),
        elo_spread=spread,
        usable=True,
        reason="ok",
    )

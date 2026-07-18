from __future__ import annotations

from dataclasses import dataclass
from typing import Any


GRADE_NAMES = ("wrong", "major_error", "minor_error", "fully_correct")


@dataclass(frozen=True)
class Question:
    id: str
    title: str
    domain: str
    prompt: str
    reference_answer: str
    rubric: tuple[str, ...]
    grade_anchors: tuple[str, str, str, str]
    difficulty_elo: float
    discrimination: float = 1.0
    step_offsets_elo: tuple[float, float, float] = (-160.0, 0.0, 160.0)

    @classmethod
    def from_author_dict(
        cls,
        raw: dict[str, Any],
        *,
        identifier: str,
        difficulty_elo: float,
    ) -> "Question":
        raw_rubric = raw.get("rubric", [])
        raw_anchors = raw.get("grade_anchors", {})
        if not isinstance(raw_rubric, list):
            raise ValueError("Question author must provide rubric as a list")
        if not isinstance(raw_anchors, dict):
            raise ValueError("Question author must provide grade anchors as an object")
        rubric = tuple(str(value).strip() for value in raw_rubric if str(value).strip())
        anchors = tuple(
            str(raw_anchors.get(name, "")).strip()
            for name in GRADE_NAMES
        )
        if not raw.get("title") or not raw.get("prompt") or not raw.get("reference_answer"):
            raise ValueError("Question author omitted a required field")
        if len(rubric) < 2:
            raise ValueError("Question author must provide at least two rubric criteria")
        if len(anchors) != 4 or any(not value for value in anchors):
            raise ValueError("Question author must provide all four grade anchors")
        return cls(
            id=identifier,
            title=str(raw["title"]).strip(),
            domain=str(raw.get("domain", "reasoning")).strip() or "reasoning",
            prompt=str(raw["prompt"]).strip(),
            reference_answer=str(raw["reference_answer"]).strip(),
            rubric=rubric,
            grade_anchors=anchors,  # type: ignore[arg-type]
            difficulty_elo=float(difficulty_elo),
        )

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "domain": self.domain,
            "prompt": self.prompt,
            "difficulty_elo": self.difficulty_elo,
            "discrimination": self.discrimination,
        }

    def grader_context_dict(self) -> dict[str, Any]:
        return {
            "reference_answer": self.reference_answer,
            "rubric": list(self.rubric),
            "grade_anchors": dict(zip(GRADE_NAMES, self.grade_anchors)),
        }


@dataclass(frozen=True)
class Grade:
    probabilities: tuple[float, float, float, float]
    error_type: str
    explanation: str
    confidence: float
    satisfied_criteria: tuple[str, ...] = ()
    apparent_elo: float | None = None

    def __post_init__(self) -> None:
        if len(self.probabilities) != 4:
            raise ValueError("A grade must contain four ordinal probabilities")
        if any(value < 0 for value in self.probabilities):
            raise ValueError("Grade probabilities cannot be negative")
        if sum(self.probabilities) <= 0:
            raise ValueError("Grade probabilities must contain positive mass")

    @property
    def normalized_probabilities(self) -> tuple[float, float, float, float]:
        total = sum(self.probabilities)
        return tuple(value / total for value in self.probabilities)  # type: ignore[return-value]

    @property
    def expected_score(self) -> float:
        return sum(index * probability for index, probability in enumerate(self.normalized_probabilities))

    def to_dict(self) -> dict[str, Any]:
        return {
            "probabilities": dict(zip(GRADE_NAMES, self.normalized_probabilities)),
            "error_type": self.error_type,
            "explanation": self.explanation,
            "confidence": self.confidence,
            "expected_score": self.expected_score,
            "satisfied_criteria": list(self.satisfied_criteria),
            "apparent_elo": self.apparent_elo,
        }

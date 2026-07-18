from __future__ import annotations

import json
import math
import re
from typing import Any

from .clients import DEFAULT_MAX_TOKENS, ChatClient, ProviderError
from .domain import GRADE_NAMES, Grade, Question
from .irt import PosteriorSummary


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ProviderError(f"Model did not return JSON: {text[:500]}")
        return json.loads(match.group(0))


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized[:48] or "question"


def _parse_apparent_elo(value: Any) -> float | None:
    """A missing or absurd texture read silently disables the channel for that answer."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or not 0.0 < parsed < 5000.0:
        return None
    return parsed


class MistralQuestionAuthor:
    def __init__(self, client: ChatClient) -> None:
        self.client = client

    def write_with_usage(
        self,
        posterior: PosteriorSummary,
        *,
        step: int,
        previous_questions: list[Question],
    ) -> tuple[Question, dict[str, int | None]]:
        target_difficulty = round(posterior.median_elo / 10.0) * 10.0
        history = "\n".join(
            f"- {question.domain}: {question.title} — {question.prompt[:180]}"
            for question in previous_questions
        ) or "- none"
        prompt = f"""You author adaptive evaluation questions for estimating an AI model's Elo.

Current posterior:
- mean Elo: {posterior.mean_elo:.1f}
- median Elo: {posterior.median_elo:.1f}
- 90% interval: {posterior.low_elo:.0f} to {posterior.high_elo:.0f}
- standard deviation: {posterior.standard_deviation:.1f}

This is question {step}. Write one new free-form reasoning question targeted near Elo {target_difficulty:.0f}. It should distinguish models near the middle of the current uncertainty range. Do not repeat the topics or substance of earlier questions:
{history}

The question must be self-contained, objectively gradable, answerable without browsing or tools, and difficult because of reasoning rather than obscure facts. Vary the domain across questions. Supply a rigorous private reference answer, concise rubric, and four concrete answer anchors.

Return JSON only with this exact shape:
{{
  "title": "short title",
  "domain": "short domain label",
  "prompt": "the question shown to the target model",
  "reference_answer": "complete private solution",
  "rubric": ["criterion one", "criterion two", "criterion three"],
  "grade_anchors": {{
    "wrong": "representative fundamentally wrong answer",
    "major_error": "representative answer with a central error",
    "minor_error": "representative nearly correct answer",
    "fully_correct": "representative complete correct answer"
  }}
}}

Do not mention Elo, grading, evaluation, or the reference answer inside the target-facing prompt."""
        result = self.client.complete_with_usage(
            [
                {
                    "role": "system",
                    "content": "Return strict JSON. Author one original, self-contained reasoning question and its private grading materials.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            json_mode=True,
            max_tokens=DEFAULT_MAX_TOKENS,
        )
        raw = _extract_json(result.content)
        try:
            question = Question.from_author_dict(
                raw,
                identifier=f"generated-{step}-{_slug(str(raw.get('title', 'question')))}",
                difficulty_elo=target_difficulty,
            )
        except ValueError as exc:
            raise ProviderError(f"Invalid authored question: {exc}") from exc
        return question, result.usage_dict()


class MistralGrader:
    def __init__(self, client: ChatClient) -> None:
        self.client = client

    def grade(self, question: Question, answer: str) -> Grade:
        grade, _ = self.grade_with_usage(question, answer)
        return grade

    def grade_with_usage(
        self, question: Question, answer: str
    ) -> tuple[Grade, dict[str, int | None]]:
        rubric = "\n".join(f"- {criterion}" for criterion in question.rubric)
        anchors = "\n\n".join(
            f"{GRADE_NAMES[index]} anchor:\n{anchor}"
            for index, anchor in enumerate(question.grade_anchors)
        )
        prompt = f"""You are a calibrated evaluator of a free-form model answer.

Question:
{question.prompt}

Reference answer:
{question.reference_answer}

Rubric:
{rubric}

Calibration anchors:
{anchors}

Candidate answer:
{answer}

Return JSON only. Grade the answer into four ordered categories:
- wrong: no meaningful correct progress or a fundamentally incorrect answer
- major_error: some relevant progress, but a central conclusion or required step is wrong/missing
- minor_error: essentially correct, with a limited omission or non-central mistake
- fully_correct: correct, complete, and responsive to the question

Separately from the four probabilities, read the answer's texture: reasoning depth, rigor,
error character, and how it handles the hardest part of the question. From that texture alone,
estimate the apparent ability of whoever wrote it as "apparent_elo" on a scale where 1000 is a
very weak small model, 1400 is a capable mid-tier model, 1800 is a strong frontier model, and
2200 is exceptional. This raw reading is recalibrated downstream, so prioritize consistency
between answers over absolute placement. Never reward length or confident tone.

Use this exact JSON shape:
{{
  "grade_probabilities": {{
    "wrong": 0.0,
    "major_error": 0.0,
    "minor_error": 0.0,
    "fully_correct": 0.0
  }},
  "error_type": "short_snake_case_label",
  "explanation": "one concise evidence-based sentence",
  "confidence": 0.0,
  "apparent_elo": 0,
  "satisfied_criteria": ["criterion text"]
}}

The four probabilities must sum to 1. Judge correctness, not verbosity or writing style."""
        result = self.client.complete_with_usage(
            [
                {
                    "role": "system",
                    "content": "Return strict JSON and follow the supplied evaluation rubric.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            json_mode=True,
        )
        raw = _extract_json(result.content)
        probabilities = raw.get("grade_probabilities", {})
        values = tuple(float(probabilities.get(name, 0.0)) for name in GRADE_NAMES)
        grade = Grade(
            probabilities=values,  # type: ignore[arg-type]
            error_type=str(raw.get("error_type", "unspecified")),
            explanation=str(raw.get("explanation", "No explanation returned.")),
            confidence=max(0.0, min(1.0, float(raw.get("confidence", 0.5)))),
            satisfied_criteria=tuple(str(value) for value in raw.get("satisfied_criteria", [])),
            apparent_elo=_parse_apparent_elo(raw.get("apparent_elo")),
        )
        return grade, result.usage_dict()


def simulated_grade(category: int) -> Grade:
    templates = (
        (0.86, 0.11, 0.025, 0.005),
        (0.10, 0.76, 0.12, 0.02),
        (0.02, 0.13, 0.76, 0.09),
        (0.005, 0.025, 0.12, 0.85),
    )
    labels = ("fundamental_error", "major_omission", "minor_omission", "none")
    explanations = (
        "The answer misses the central requirement.",
        "The answer shows relevant progress but contains a major error or omission.",
        "The answer is essentially correct with a limited omission.",
        "The answer satisfies the reference and rubric.",
    )
    return Grade(
        probabilities=templates[category],
        error_type=labels[category],
        explanation=explanations[category],
        confidence=0.85,
    )

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from typing import Any

from experiments.adaptive_smoke_test import CallRecord, call_json, warmup_prompt
from viberank.debug_questions import FIXED_DEBUG_QUESTIONS


TARGETS = {
    "candidate_a": {"model": "mistral-small-latest", "public_elo": 1521},
    "candidate_b": {"model": "mistral-medium-3.5", "public_elo": 1645},
}
GRADERS = ("mistral-medium-3.5", "mistral-large-latest")
MAX_GENERATION_ATTEMPTS = 3


def answer_text(payload: dict[str, Any]) -> str:
    return str(payload.get("answer", payload))


def initial_answers(payload: dict[str, Any]) -> list[str]:
    values = payload.get("answers") or []
    return [str(value.get("answer", "")) for value in values[:3]]


def artifact_text(question: dict[str, Any]) -> str:
    return json.dumps(question, ensure_ascii=True)


def history_text(
    questions: list[dict[str, Any]],
    answers: list[str],
) -> str:
    blocks = []
    for index, (question, answer) in enumerate(zip(questions, answers), start=1):
        blocks.append(
            f"""QUESTION {index}
{question['prompt']}

PRIVATE REFERENCE
{json.dumps(question['reference_answer'], ensure_ascii=True)}

TARGET ANSWER
{answer}"""
        )
    return "\n\n---\n\n".join(blocks)


def candidate_prefix(
    questions: list[dict[str, Any]],
    answers: list[str],
    prefix: int,
) -> str:
    blocks = []
    for index in range(prefix):
        question = questions[index]
        blocks.append(
            f"""Q{index + 1}
PROMPT: {question['prompt']}
PRIVATE REFERENCE: {json.dumps(question['reference_answer'], ensure_ascii=True)}
ANSWER: {answers[index]}"""
        )
    return "\n\n".join(blocks)


def generate_adaptive_question(
    records: list[CallRecord],
    *,
    number: int,
    questions: list[dict[str, Any]],
    target_answers: list[str],
) -> tuple[dict[str, Any], dict[str, Any], int]:
    rejection_feedback = "none"
    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):
        prompt = f"""Create adaptive reasoning question Q{number} from the target's complete transcript below.

The next question must extract information that the previous questions did not. If the target answered everything correctly, increase difficulty substantially. Choose the content dynamically from the demonstrated performance; do not select from a bank and do not mention Elo or evaluation.

Requirements:
- novel, self-contained, objectively gradable, and answerable without browsing or tools
- difficult because of interacting reasoning steps, not obscure factual recall
- not a routine textbook problem, direct calculation, or tiny mechanical enumeration comparable to the prior questions
- include all assumptions needed for one defensible answer
- independently solve it and adversarially search for ambiguity and counterexamples before emitting it

Return strict JSON only:
{{
  "title": "short title",
  "domain": "short domain",
  "prompt": "complete target-facing question",
  "reference_answer": "complete rigorous private solution",
  "rubric": ["criterion 1", "criterion 2", "criterion 3"]
}}

Feedback from a rejected attempt, if any:
{rejection_feedback}

TARGET TRANSCRIPT
{history_text(questions, target_answers)}
"""
        generated = call_json(
            records,
            stage=f"q{number}_generation_attempt_{attempt}",
            model="mistral-large-latest",
            system=(
                "Return strict JSON. Adapt to the transcript, then self-check the completed "
                "question and private solution before emitting them."
            ),
            user=prompt,
            temperature=0.7,
        )

        verification_prompt = f"""Evaluate this completed adaptive benchmark artifact as a strict gate.

Work in this exact order:
1. Independently solve the question and check the supplied reference.
2. Search for ambiguity, missing assumptions, counterexamples, and alternative valid answers.
3. Compare its reasoning demands with the target's prior transcript.
4. Decide whether the completed question is likely to reveal new ability information. A merely valid question that the demonstrated target would very likely answer perfectly is not discriminative and must be rejected.
5. Emit the final acceptance decision only after the analysis.

The verifier may veto but may not repair the artifact. Return strict JSON with fields in this order:
{{
  "analysis": "validity and independent-solution analysis",
  "difficulty_assessment": "why this should or should not reveal new information after the transcript",
  "valid": true,
  "expected_discriminative": true,
  "issue_type": "none or short_snake_case_issue",
  "confidence": 0.0,
  "accept": true
}}

PRIOR TARGET TRANSCRIPT
{history_text(questions, target_answers)}

CANDIDATE ARTIFACT
{artifact_text(generated)}
"""
        verification = call_json(
            records,
            stage=f"q{number}_verification_attempt_{attempt}",
            model="mistral-large-latest",
            system=(
                "Solve independently and assess incremental discriminative value before emitting "
                "the final accept field. Return strict JSON."
            ),
            user=verification_prompt,
            temperature=0.0,
        )
        accepted = (
            verification.get("valid") is True
            and verification.get("expected_discriminative") is True
            and verification.get("accept") is True
        )
        if accepted:
            return generated, verification, attempt
        rejection_feedback = json.dumps(verification, ensure_ascii=True)
    raise RuntimeError(f"Q{number} failed verification after {MAX_GENERATION_ATTEMPTS} attempts")


def main() -> None:
    records: list[CallRecord] = []
    warmup_system = (
        "Answer each reasoning question directly and independently. Explain enough to support "
        "each conclusion. Return strict JSON and do not discuss evaluation or grading."
    )
    warmups: dict[str, dict[str, Any]] = {}
    for candidate, config in TARGETS.items():
        warmups[candidate] = call_json(
            records,
            stage=f"{candidate}_q1_q3_answers",
            model=str(config["model"]),
            system=warmup_system,
            user=warmup_prompt(),
            temperature=0.2,
        )

    questions: list[dict[str, Any]] = [
        {
            "title": question.title,
            "domain": question.domain,
            "prompt": question.prompt,
            "reference_answer": question.reference_answer,
            "rubric": list(question.rubric),
        }
        for question in FIXED_DEBUG_QUESTIONS[:3]
    ]
    answers = {
        candidate: initial_answers(payload)
        for candidate, payload in warmups.items()
    }
    adaptive: list[dict[str, Any]] = []

    for number in (4, 5):
        generated, verification, attempts = generate_adaptive_question(
            records,
            number=number,
            questions=questions,
            target_answers=answers["candidate_a"],
        )
        questions.append(generated)
        q_answers: dict[str, str] = {}
        for candidate, config in TARGETS.items():
            payload = call_json(
                records,
                stage=f"{candidate}_q{number}_answer",
                model=str(config["model"]),
                system=(
                    "Answer the question directly. Explain enough to support the conclusion. "
                    "Return strict JSON with one key named answer."
                ),
                user=str(generated["prompt"]),
                temperature=0.2,
            )
            q_answers[candidate] = answer_text(payload)
            answers[candidate].append(q_answers[candidate])
        adaptive.append(
            {
                "question_number": number,
                "title": generated.get("title"),
                "prompt": generated.get("prompt"),
                "verification": verification,
                "generation_attempts": attempts,
                "answer_lengths": {
                    candidate: len(value) for candidate, value in q_answers.items()
                },
            }
        )

    trajectory: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for grader_model in GRADERS:
        for prefix in range(1, 6):
            grading_prompt = f"""Estimate the aggregate public reasoning Elo of two anonymous language models using ONLY the first {prefix} question(s) shown for each.

This is a genuinely sequential estimate: later questions are not present. Judge correctness and reasoning, not verbosity or style. Independently check the answers and private references. There is no externally assigned Elo for any question; infer how much evidence each answer provides. Use a scale from roughly 800 (very weak) to 2200 (exceptional). Keep the 90% interval wide when evidence is weak; it need not tighten if a question adds no information.

Return strict JSON:
{{
  "candidate_a": {{"mean_elo": 0, "low_90": 0, "high_90": 0, "assessment": "brief evidence"}},
  "candidate_b": {{"mean_elo": 0, "low_90": 0, "high_90": 0, "assessment": "brief evidence"}},
  "stronger_candidate": "candidate_a, candidate_b, or tie",
  "ranking_confidence": 0.0,
  "information_from_latest_question": "none, low, medium, or high",
  "reason": "brief comparison"
}}

CANDIDATE A
{candidate_prefix(questions, answers['candidate_a'], prefix)}

CANDIDATE B
{candidate_prefix(questions, answers['candidate_b'], prefix)}
"""
            estimate = call_json(
                records,
                stage=f"{grader_model}_after_q{prefix}",
                model=grader_model,
                system=(
                    "You are a calibrated holistic model evaluator. Return strict JSON and "
                    "preserve uncertainty from small samples."
                ),
                user=grading_prompt,
                temperature=0.0,
            )
            point: dict[str, Any] = {
                "question": prefix,
                "ranking": estimate.get("stronger_candidate"),
                "ranking_confidence": estimate.get("ranking_confidence"),
                "information": estimate.get("information_from_latest_question"),
            }
            for candidate, config in TARGETS.items():
                value = estimate.get(candidate) or {}
                mean = float(value.get("mean_elo", 0))
                truth = float(config["public_elo"])
                point[candidate] = {
                    "mean": mean,
                    "low": float(value.get("low_90", 0)),
                    "high": float(value.get("high_90", 0)),
                    "absolute_error": abs(mean - truth),
                    "interval_width": float(value.get("high_90", 0))
                    - float(value.get("low_90", 0)),
                }
            trajectory[grader_model].append(point)

    costs_by_stage: dict[str, float] = defaultdict(float)
    for record in records:
        if "generation" in record.stage:
            group = "generation"
        elif "verification" in record.stage:
            group = "verification"
        elif "answer" in record.stage:
            group = "targets"
        else:
            group = "grading"
        costs_by_stage[group] += record.cost_usd

    output = {
        "status": "complete",
        "targets": TARGETS,
        "adaptive_questions": adaptive,
        "trajectory": trajectory,
        "cost_by_stage_usd": {
            key: round(value, 8) for key, value in costs_by_stage.items()
        },
        "total_cost_usd": round(sum(record.cost_usd for record in records), 8),
        "total_calls": len(records),
        "total_tokens": sum(record.total_tokens for record in records),
        "calls": [asdict(record) for record in records],
    }
    print(json.dumps(output, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

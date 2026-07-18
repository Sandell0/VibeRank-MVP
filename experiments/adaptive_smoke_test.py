from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from viberank.clients import DEFAULT_MAX_TOKENS, ChatClient, ChatResult, mistral_client
from viberank.debug_questions import FIXED_DEBUG_QUESTIONS


RATES_PER_MILLION = {
    "mistral-small-latest": (0.15, 0.60),
    "mistral-medium-3.5": (1.50, 7.50),
    "mistral-large-latest": (0.50, 1.50),
}

PUBLIC_ELO = {
    "candidate_a": 1521,
    "candidate_b": 1645,
}


@dataclass
class CallRecord:
    stage: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float


def parse_json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object in response: {text[:500]}")
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def usage_cost(result: ChatResult, model: str) -> float:
    input_rate, output_rate = RATES_PER_MILLION[model]
    return (
        int(result.prompt_tokens or 0) * input_rate
        + int(result.completion_tokens or 0) * output_rate
    ) / 1_000_000


def call_json(
    records: list[CallRecord],
    *,
    stage: str,
    model: str,
    system: str,
    user: str,
    temperature: float,
) -> dict[str, Any]:
    client: ChatClient = mistral_client(model)
    result = client.complete_with_usage(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        json_mode=True,
        max_tokens=DEFAULT_MAX_TOKENS,
    )
    records.append(
        CallRecord(
            stage=stage,
            model=model,
            prompt_tokens=int(result.prompt_tokens or 0),
            completion_tokens=int(result.completion_tokens or 0),
            total_tokens=int(result.total_tokens or 0),
            cost_usd=usage_cost(result, model),
        )
    )
    return parse_json(result.content)


def warmup_prompt() -> str:
    questions = []
    for index, question in enumerate(FIXED_DEBUG_QUESTIONS[:3], start=1):
        questions.append(f"Question {index}:\n{question.prompt}")
    return "\n\n".join(questions) + """

Answer all three independently. Return JSON only:
{
  "answers": [
    {"question": 1, "answer": "complete answer"},
    {"question": 2, "answer": "complete answer"},
    {"question": 3, "answer": "complete answer"}
  ]
}
"""


def transcript_for_generator(warmup: dict[str, Any]) -> str:
    entries = []
    answers = warmup.get("answers") or []
    for index, question in enumerate(FIXED_DEBUG_QUESTIONS[:3]):
        answer = answers[index].get("answer", "") if index < len(answers) else ""
        entries.append(
            f"""Previous question {index + 1}:
{question.prompt}

Private reference:
{question.reference_answer}

Target answer:
{answer}"""
        )
    return "\n\n---\n\n".join(entries)


def grader_transcript(warmup: dict[str, Any], q4: str, q4_answer: str) -> str:
    entries = []
    answers = warmup.get("answers") or []
    for index, question in enumerate(FIXED_DEBUG_QUESTIONS[:3]):
        answer = answers[index].get("answer", "") if index < len(answers) else ""
        entries.append(f"Q{index + 1}: {question.prompt}\nANSWER: {answer}")
    entries.append(f"Q4: {q4}\nANSWER: {q4_answer}")
    return "\n\n".join(entries)


def main() -> None:
    records: list[CallRecord] = []

    warmup_system = (
        "Answer each reasoning question directly and independently. Explain enough to support "
        "each conclusion. Return strict JSON and do not discuss evaluation or grading."
    )
    candidate_a_warmup = call_json(
        records,
        stage="candidate_a_warmups",
        model="mistral-small-latest",
        system=warmup_system,
        user=warmup_prompt(),
        temperature=0.2,
    )
    candidate_b_warmup = call_json(
        records,
        stage="candidate_b_warmups",
        model="mistral-medium-3.5",
        system=warmup_system,
        user=warmup_prompt(),
        temperature=0.2,
    )

    generator_prompt = f"""You generate the next adaptive question in an in-context model Elo evaluation.

Below is one target model's transcript on three previous questions, including private references. Assess what the answers do and do not establish, then create ONE new question whose answer should be maximally informative about the target's reasoning ability. It should be meaningfully harder if the previous questions were saturated.

Requirements:
- Adapt to the actual answers below; do not choose from a bank.
- Be novel, self-contained, objectively gradable, and answerable without browsing or tools.
- Test reasoning, not obscure factual recall.
- Do not mention models, Elo, evaluation, grading, or this transcript in the target-facing prompt.
- Before returning, independently solve the question and search for ambiguity, missing assumptions, counterexamples, and alternative valid answers.
- Return only the final artifact as strict JSON.

JSON shape:
{{
  "title": "short title",
  "domain": "short domain",
  "prompt": "complete target-facing question",
  "reference_answer": "complete private solution",
  "rubric": ["criterion 1", "criterion 2", "criterion 3"]
}}

TRANSCRIPT
{transcript_for_generator(candidate_a_warmup)}
"""
    generated = call_json(
        records,
        stage="adaptive_generation",
        model="mistral-large-latest",
        system=(
            "Return strict JSON. Generate one adaptive reasoning question and rigorously "
            "self-check its private solution before emitting the final artifact."
        ),
        user=generator_prompt,
        temperature=0.7,
    )

    verification_prompt = f"""Independently verify this completed benchmark artifact.

Work in this exact order:
1. Solve the target-facing question from scratch without trusting the reference.
2. Search for counterexamples, alternative answers, ambiguity, and missing assumptions.
3. Compare the independent solution with the supplied reference and rubric.
4. Only after the analysis is complete, emit the verdict.

The verifier is a gate, not an editor. If anything material is wrong or ambiguous, reject it. In the JSON object, emit "analysis" before "valid" so the verdict is produced after the reasoning. Return JSON only:
{{
  "analysis": "concise verification reasoning",
  "valid": true,
  "issue_type": "none or short_snake_case_issue",
  "confidence": 0.0
}}

ARTIFACT
{json.dumps(generated, ensure_ascii=False)}
"""
    verification = call_json(
        records,
        stage="independent_verification",
        model="mistral-large-latest",
        system="Return strict JSON. Solve independently before issuing the final validity verdict.",
        user=verification_prompt,
        temperature=0.0,
    )

    if verification.get("valid") is not True:
        output = {
            "status": "stopped_after_rejected_question",
            "generated_question": generated,
            "verification": verification,
            "calls": [asdict(record) for record in records],
            "total_cost_usd": round(sum(record.cost_usd for record in records), 8),
        }
        print(json.dumps(output, indent=2, ensure_ascii=True))
        return

    q4 = str(generated.get("prompt", ""))
    target_system = (
        "Answer the question directly. Explain enough to support the conclusion, but do not "
        "discuss evaluation or grading. Return strict JSON with one key named answer."
    )
    q4_a = call_json(
        records,
        stage="candidate_a_adaptive_answer",
        model="mistral-small-latest",
        system=target_system,
        user=q4,
        temperature=0.2,
    )
    q4_b = call_json(
        records,
        stage="candidate_b_adaptive_answer",
        model="mistral-medium-3.5",
        system=target_system,
        user=q4,
        temperature=0.2,
    )
    q4_a_answer = str(q4_a.get("answer", q4_a))
    q4_b_answer = str(q4_b.get("answer", q4_b))

    grader_prompt = f"""Estimate the aggregate public reasoning Elo of two anonymous language models from their answers to the same four questions.

Judge correctness and demonstrated reasoning, not verbosity or style. Independently solve questionable parts. The first three questions may be saturated and therefore weak evidence; the fourth was adaptively generated from Candidate A's earlier answers. Do not assume the supplied private reference is correct merely because it is supplied, although an independent verifier accepted it.

Use an Elo scale spanning roughly 800 (very weak) to 2200 (exceptional). Produce an independent estimate and 90% interval for each candidate, then state which candidate appears stronger. The intervals should express genuine uncertainty from only four answers.

Return JSON only:
{{
  "candidate_a": {{"mean_elo": 0, "low_90": 0, "high_90": 0, "assessment": "brief evidence"}},
  "candidate_b": {{"mean_elo": 0, "low_90": 0, "high_90": 0, "assessment": "brief evidence"}},
  "stronger_candidate": "candidate_a, candidate_b, or tie",
  "ranking_confidence": 0.0,
  "adaptive_question_discriminated": true,
  "reason": "brief comparison"
}}

PRIVATE Q4 REFERENCE
{generated.get('reference_answer', '')}

PRIVATE Q4 RUBRIC
{json.dumps(generated.get('rubric', []), ensure_ascii=False)}

CANDIDATE A TRANSCRIPT
{grader_transcript(candidate_a_warmup, q4, q4_a_answer)}

CANDIDATE B TRANSCRIPT
{grader_transcript(candidate_b_warmup, q4, q4_b_answer)}
"""
    grade = call_json(
        records,
        stage="blind_holistic_grading",
        model="mistral-large-latest",
        system=(
            "You are a calibrated holistic model evaluator. Solve independently, return strict "
            "JSON, and preserve meaningful uncertainty from the small sample."
        ),
        user=grader_prompt,
        temperature=0.0,
    )

    estimates: dict[str, Any] = {}
    for candidate, truth in PUBLIC_ELO.items():
        estimate = grade.get(candidate) or {}
        mean = float(estimate.get("mean_elo", 0))
        estimates[candidate] = {
            "public_elo": truth,
            "predicted_elo": mean,
            "absolute_error": abs(mean - truth),
            "inside_90_interval": (
                float(estimate.get("low_90", 0)) <= truth <= float(estimate.get("high_90", 0))
            ),
        }

    output = {
        "status": "complete",
        "generated_question": generated,
        "verification": verification,
        "adaptive_answers": {
            "candidate_a": q4_a_answer,
            "candidate_b": q4_b_answer,
        },
        "grader": grade,
        "score_against_public_elo": estimates,
        "calls": [asdict(record) for record in records],
        "total_cost_usd": round(sum(record.cost_usd for record in records), 8),
    }
    print(json.dumps(output, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()

"""Factorized channels vs whole-transcript holistic grading, on live models.

Both methods read the SAME five answers per target model; the only difference
is how the grader's judgment is extracted and aggregated:

  A. factorized  — per-answer ordinal grades + per-answer texture reads pooled
                   by the Elo posterior, texture calibrated leave-one-out;
  B. ordinal     — per-answer ordinal grades only (baseline);
  C. holistic    — all five Q/A pairs in one grader context, direct mean and
                   90% interval, used raw (the "attach everything" proposal);
  D. holistic+   — the same holistic read, leave-one-out calibrated like A.

Ground truth is the public Elo from aibenchmarks.dev. Collection is cached in
method_battle_data.json next to this file; rerunning skips finished models.

    python -m experiments.method_battle
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from viberank.calibration import DirectObservation, fit_direct_calibration
from viberank.clients import ChatClient, ProviderError, mistral_client, openrouter_client
from viberank.debug_questions import FIXED_DEBUG_QUESTIONS
from viberank.domain import GRADE_NAMES, Grade
from viberank.grading import MistralGrader, _extract_json
from viberank.irt import EloPosterior

import os


DATA_PATH = Path(__file__).resolve().parent / "method_battle_data.json"
TARGET_MAX_TOKENS = 8000
CALL_PAUSE_SECONDS = 0.7
RETRY_SLEEPS = (5, 15, 30)

# (provider, api model id, public Elo, leaderboard row) — n_bench >= 150 rows
# only (kimi-k2-0905 at 199); mistral-medium-3.5 is the grader and therefore
# not a target. OpenAI targets kept for whenever that key has credit again.
TARGETS: tuple[tuple[str, str, float, str], ...] = (
    ("mistral", "mistral-tiny-2407", 1339.0, "Mistral 7B Instruct (v0.3)"),
    ("mistral", "open-mistral-nemo-2407", 1466.0, "Mistral Nemo Instruct (2407)"),
    ("mistral", "ministral-3b-2512", 1480.0, "Ministral-3-3B-Instruct-2512"),
    ("mistral", "ministral-8b-2512", 1521.0, "Ministral-3-8B-Instruct-2512"),
    ("mistral", "ministral-14b-2512", 1535.0, "Ministral-3-14B-Instruct-2512"),
    ("mistral", "mistral-small-2506", 1574.0, "Mistral Small 3.2"),
    ("mistral", "mistral-medium-2508", 1628.0, "Mistral Medium 3.1"),
    ("openrouter", "meta-llama/llama-3.2-1b-instruct", 1210.0, "Llama 3.2 1B Instruct"),
    ("openrouter", "meta-llama/llama-3.2-3b-instruct", 1371.0, "Llama 3.2 3B Instruct"),
    ("openrouter", "meta-llama/llama-3.1-8b-instruct", 1440.0, "Llama 3.1 8B Instruct"),
    ("openrouter", "microsoft/phi-4", 1485.0, "Phi-4"),
    ("openrouter", "meta-llama/llama-3.3-70b-instruct", 1546.0, "Llama 3.3 70B Instruct"),
    ("openrouter", "google/gemma-3-27b-it", 1588.0, "Gemma 3 27B (IT)"),
    ("openrouter", "openai/gpt-oss-120b", 1599.0, "GPT-OSS-120B"),
    ("openrouter", "qwen/qwen3-235b-a22b-2507", 1625.0, "Qwen 3 235B A22B 2507 Instruct"),
    ("openrouter", "deepseek/deepseek-chat-v3.1", 1667.0, "DeepSeek V3.1"),
    ("openrouter", "moonshotai/kimi-k2-0905", 1688.0, "Kimi K2 0905"),
    ("openrouter", "moonshotai/kimi-k2.5", 1749.0, "Kimi K2.5"),
    ("openai", "gpt-4.1-nano", 1452.0, "GPT-4.1 Nano"),
    ("openai", "gpt-4o-mini", 1542.0, "GPT-4o Mini"),
    ("openai", "gpt-4.1", 1636.0, "GPT-4.1"),
    ("openai", "gpt-4o", 1646.0, "GPT-4o"),
)


def openai_client(model: str) -> ChatClient:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ProviderError("OPENAI_API_KEY is not set")
    return ChatClient(
        endpoint="https://api.openai.com/v1/chat/completions",
        api_key=key,
        model=model,
        provider_name="OpenAI",
    )


def target_client(provider: str, model: str) -> ChatClient:
    if provider == "openai":
        return openai_client(model)
    if provider == "openrouter":
        return openrouter_client(model)
    return mistral_client(model)


def call_with_retries(fn, label: str):
    for attempt, sleep_seconds in enumerate((0,) + RETRY_SLEEPS):
        if sleep_seconds:
            print(f"    retrying {label} in {sleep_seconds}s...")
            time.sleep(sleep_seconds)
        try:
            result = fn()
            time.sleep(CALL_PAUSE_SECONDS)
            return result
        except ProviderError as exc:
            message = str(exc)
            retryable = (
                any(code in message for code in ("429", "500", "502", "503"))
                and "insufficient_quota" not in message
            )
            if attempt == len(RETRY_SLEEPS) or not retryable:
                raise
            print(f"    {label} failed ({message[:120]})")
    raise RuntimeError("unreachable")


def collect_answers(client: ChatClient) -> list[dict]:
    answers = []
    for question in FIXED_DEBUG_QUESTIONS:
        result = call_with_retries(
            lambda q=question: client.complete_with_usage(
                [
                    {
                        "role": "system",
                        "content": (
                            "Answer the question directly. Explain enough to support the "
                            "conclusion, but do not discuss evaluation or grading."
                        ),
                    },
                    {"role": "user", "content": q.prompt},
                ],
                temperature=0.2,
                max_tokens=TARGET_MAX_TOKENS,
            ),
            label=f"answer {question.id}",
        )
        answers.append(
            {
                "question_id": question.id,
                "answer": result.content,
                "usage": result.usage_dict(),
            }
        )
        print(f"    answered {question.id} ({result.completion_tokens} tokens)")
    return answers


def grade_answers(grader: MistralGrader, answers: list[dict]) -> list[dict]:
    grades = []
    for question, entry in zip(FIXED_DEBUG_QUESTIONS, answers):
        grade, usage = call_with_retries(
            lambda q=question, a=entry["answer"]: grader.grade_with_usage(q, a),
            label=f"grade {question.id}",
        )
        grades.append(
            {
                "question_id": question.id,
                "probabilities": list(grade.normalized_probabilities),
                "apparent_elo": grade.apparent_elo,
                "error_type": grade.error_type,
                "explanation": grade.explanation,
                "usage": usage,
            }
        )
        top = GRADE_NAMES[max(range(4), key=grade.normalized_probabilities.__getitem__)]
        print(f"    graded {question.id}: {top}, texture {grade.apparent_elo}")
    return grades


def holistic_transcript(answers: list[dict], prefix: int | None = None) -> str:
    included = answers if prefix is None else answers[:prefix]
    blocks = []
    for index, (question, entry) in enumerate(zip(FIXED_DEBUG_QUESTIONS, included), start=1):
        rubric = "\n".join(f"- {criterion}" for criterion in question.rubric)
        blocks.append(
            f"""QUESTION {index}: {question.prompt}

PRIVATE REFERENCE: {question.reference_answer}

RUBRIC:
{rubric}

CANDIDATE ANSWER: {entry['answer']}"""
        )
    return "\n\n---\n\n".join(blocks)


def holistic_grade(grader_client: ChatClient, answers: list[dict], prefix: int | None = None) -> dict:
    count = len(answers) if prefix is None else prefix
    prompt = f"""You are a calibrated evaluator. Below is one anonymous language model's transcript: {count} reasoning question{"s" if count != 1 else ""}, each with a private reference answer, a rubric, and the model's answer.

Read the whole transcript jointly — consistency across answers, error character, reasoning depth — and estimate the model's ability as an Elo on a scale where 1000 is a very weak small model, 1400 is a capable mid-tier model, 1800 is a strong frontier model, and 2200 is exceptional. Judge correctness and demonstrated reasoning, not verbosity or style. Keep the 90% interval honest for evidence from only {count} answer{"s" if count != 1 else ""}.

Return JSON only:
{{
  "mean_elo": 0,
  "low_90": 0,
  "high_90": 0,
  "assessment": "brief evidence-based summary"
}}

TRANSCRIPT
{holistic_transcript(answers, prefix)}"""
    result = call_with_retries(
        lambda: grader_client.complete_with_usage(
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
        ),
        label="holistic read",
    )
    raw = _extract_json(result.content)
    return {
        "mean_elo": float(raw.get("mean_elo", 0.0)),
        "low_90": float(raw.get("low_90", 0.0)),
        "high_90": float(raw.get("high_90", 0.0)),
        "assessment": str(raw.get("assessment", "")),
        "usage": result.usage_dict(),
    }


def load_data() -> dict:
    if DATA_PATH.is_file():
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return {"grader_model": None, "models": {}}


def save_data(data: dict) -> None:
    DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")


def collect_all() -> dict:
    data = load_data()
    grader_client = mistral_client()
    data["grader_model"] = grader_client.model
    grader = MistralGrader(grader_client)
    for provider, model, elo, row in TARGETS:
        if model in data["models"]:
            print(f"{model}: cached, skipping")
            continue
        print(f"{model} (public {elo:.0f}, {provider}):")
        try:
            client = target_client(provider, model)
            answers = collect_answers(client)
            grades = grade_answers(grader, answers)
            prefixes = []
            for prefix in range(1, len(answers) + 1):
                read = holistic_grade(grader_client, answers, prefix)
                prefixes.append(read)
                print(f"    holistic after Q{prefix}: {read['mean_elo']:.0f} ({read['low_90']:.0f}-{read['high_90']:.0f})")
        except ProviderError as exc:
            print(f"  SKIPPED {model}: {exc}")
            continue
        data["models"][model] = {
            "provider": provider,
            "public_elo": elo,
            "leaderboard_row": row,
            "answers": answers,
            "grades": grades,
            "holistic": prefixes[-1],
            "holistic_prefixes": prefixes,
        }
        save_data(data)
    return data


def backfill_prefixes(data: dict) -> dict:
    """Add per-prefix holistic reads (Q1..Q4) to models collected before this
    feature existed; the cached full-transcript read is reused as Q5."""
    grader_client = mistral_client()
    for name, record in data["models"].items():
        if "holistic_prefixes" in record:
            continue
        print(f"{name}: backfilling prefix holistic reads")
        prefixes = []
        for prefix in range(1, len(record["answers"])):
            read = holistic_grade(grader_client, record["answers"], prefix)
            prefixes.append(read)
            print(f"    holistic after Q{prefix}: {read['mean_elo']:.0f} ({read['low_90']:.0f}-{read['high_90']:.0f})")
        prefixes.append(record["holistic"])
        record["holistic_prefixes"] = prefixes
        save_data(data)
    return data


def factorized_estimate(record: dict, calibration) -> tuple[dict, dict]:
    """Returns (full estimate with texture, ordinal-only estimate)."""
    full = EloPosterior()
    ordinal_only = EloPosterior()
    for question, graded in zip(FIXED_DEBUG_QUESTIONS, record["grades"]):
        grade = Grade(
            probabilities=tuple(graded["probabilities"]),  # type: ignore[arg-type]
            error_type=graded["error_type"],
            explanation=graded["explanation"],
            confidence=1.0,
            apparent_elo=graded["apparent_elo"],
        )
        full.update(question, grade)
        ordinal_only.update(question, grade)
        if calibration is not None and calibration.usable and grade.apparent_elo is not None:
            full.observe_direct(
                calibration.apply(grade.apparent_elo),
                tau_elo=calibration.tau_elo,
                sigma_w_elo=calibration.sigma_w_elo,
            )
    return full.summary().to_dict(), ordinal_only.summary().to_dict()


def holistic_loo_calibration(models: dict, held_out: str) -> tuple[float, float, float] | None:
    """Classical fit raw_holistic = a + b*true on all models except held_out.

    Returns (intercept, slope, sigma_elo with t inflation) or None if degenerate.
    """
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
    covariance = sum((t - true_mean) * (r - raw_mean) for t, r in pairs)
    if true_var <= 0:
        return None
    slope = covariance / true_var
    if slope <= 1e-6:
        return None
    intercept = raw_mean - slope * true_mean
    residuals = [(r - (intercept + slope * t)) / slope for t, r in pairs]
    df = n - 2
    variance = sum(value ** 2 for value in residuals) / df
    variance *= df / (df - 2) if df > 2 else 3.0
    return intercept, slope, max(50.0, math.sqrt(variance))


def spearman(left: list[float], right: list[float]) -> float:
    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=values.__getitem__)
        result = [0.0] * len(values)
        for rank, index in enumerate(order):
            result[index] = float(rank)
        return result

    lr, rr = ranks(left), ranks(right)
    lm, rm = sum(lr) / len(lr), sum(rr) / len(rr)
    num = sum((a - lm) * (b - rm) for a, b in zip(lr, rr))
    den = math.sqrt(sum((a - lm) ** 2 for a in lr) * sum((b - rm) ** 2 for b in rr))
    return num / den if den else 0.0


def analyze(data: dict) -> None:
    models = data["models"]
    grader_model = data.get("grader_model") or "mistral-medium-3.5"
    if len(models) < 5:
        print(f"Only {len(models)} models collected; need at least 5 to analyze.")
        return

    arms = {"factorized": {}, "ordinal": {}, "holistic_raw": {}, "holistic_cal": {}}
    intervals = {"factorized": {}, "holistic_raw": {}, "holistic_cal": {}}
    texture_r2_notes = []

    for name, record in models.items():
        observations = [
            DirectObservation(other, other_record["public_elo"], graded["apparent_elo"])
            for other, other_record in models.items()
            if other != name
            for graded in other_record["grades"]
            if graded["apparent_elo"] is not None
        ]
        calibration = fit_direct_calibration(observations, grader_model=grader_model)
        texture_r2_notes.append(calibration.r_squared if calibration.usable else None)

        full, ordinal_only = factorized_estimate(record, calibration)
        arms["factorized"][name] = full["mean_elo"]
        arms["ordinal"][name] = ordinal_only["mean_elo"]
        intervals["factorized"][name] = (full["low_elo"], full["high_elo"])

        holistic = record["holistic"]
        arms["holistic_raw"][name] = holistic["mean_elo"]
        intervals["holistic_raw"][name] = (holistic["low_90"], holistic["high_90"])

        loo = holistic_loo_calibration(models, name)
        if loo is None:
            arms["holistic_cal"][name] = holistic["mean_elo"]
            intervals["holistic_cal"][name] = (holistic["low_90"], holistic["high_90"])
        else:
            intercept, slope, sigma = loo
            estimate = (holistic["mean_elo"] - intercept) / slope
            arms["holistic_cal"][name] = estimate
            intervals["holistic_cal"][name] = (estimate - 1.645 * sigma, estimate + 1.645 * sigma)

    names = list(models)
    truths = [models[name]["public_elo"] for name in names]

    print(f"\n{'model':<26} {'true':>5} | " + " | ".join(f"{arm:>14}" for arm in arms))
    for name in names:
        row = f"{name:<26} {models[name]['public_elo']:>5.0f} | "
        row += " | ".join(
            f"{arms[arm][name]:>6.0f} ({abs(arms[arm][name] - models[name]['public_elo']):>4.0f})"
            for arm in arms
        )
        print(row)

    print(f"\n{'metric':<12} | " + " | ".join(f"{arm:>13}" for arm in arms))
    for metric, fn in (
        ("MAE", lambda errs: sum(errs) / len(errs)),
        ("median AE", lambda errs: sorted(errs)[len(errs) // 2]),
        ("max AE", max),
    ):
        row = f"{metric:<12} | "
        row += " | ".join(
            f"{fn([abs(arms[arm][n] - models[n]['public_elo']) for n in names]):>13.0f}"
            for arm in arms
        )
        print(row)
    row = f"{'spearman':<12} | "
    row += " | ".join(
        f"{spearman(truths, [arms[arm][n] for n in names]):>13.3f}" for arm in arms
    )
    print(row)

    print("\n90% interval performance:")
    for arm, arm_intervals in intervals.items():
        hits = sum(
            1
            for name in names
            if arm_intervals[name][0] <= models[name]["public_elo"] <= arm_intervals[name][1]
        )
        mean_width = sum(high - low for low, high in arm_intervals.values()) / len(names)
        print(f"  {arm:<13} coverage {hits}/{len(names)}   mean width {mean_width:.0f}")

    usable = [value for value in texture_r2_notes if value is not None]
    if usable:
        print(f"\nTexture LOO calibrations usable for {len(usable)}/{len(names)} models; "
              f"r-squared range {min(usable):.3f}-{max(usable):.3f}")
    else:
        print("\nNo usable texture calibration in any LOO fold.")

    usage_total = 0
    for record in models.values():
        for entry in record["answers"]:
            usage_total += entry["usage"].get("total_tokens") or 0
        for graded in record["grades"]:
            usage_total += graded["usage"].get("total_tokens") or 0
        usage_total += record["holistic"]["usage"].get("total_tokens") or 0
    print(f"\nTotal tokens across all calls: {usage_total:,}")


def main() -> None:
    data = collect_all()
    backfill_prefixes(data)
    analyze(data)


if __name__ == "__main__":
    main()

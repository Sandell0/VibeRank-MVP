from __future__ import annotations

import math
import os
import random
from dataclasses import dataclass, replace
from typing import Any

from .calibration import (
    DirectCalibration,
    DirectObservation,
    calibration_path,
    fit_direct_calibration,
    load_calibration,
)
from .clients import DEFAULT_MAX_TOKENS, mistral_client, openrouter_client
from .debug_questions import FIXED_DEBUG_QUESTIONS
from .domain import Question
from .grading import MistralGrader, MistralQuestionAuthor, simulated_grade
from .holistic import (
    INTERVAL_Z,
    HolisticCalibration,
    holistic_calibration_path,
    holistic_read,
)
from .irt import EloPosterior, PosteriorSummary, category_probabilities
from .item_calibration import ItemCalibration, item_calibration_path


DEFAULT_MAX_QUESTIONS = 10
DEFAULT_QUESTION_MODE = "fixed"
DEFAULT_TARGET_MAX_TOKENS = DEFAULT_MAX_TOKENS
QUESTION_MODES = ("fixed", "authored")

# Display-only estimates for the live models used by the MVP. Rates are USD per
# million input/output tokens and were last checked on 2026-07-18.
MODEL_RATES: dict[str, tuple[float, float]] = {
    "mistral-small-latest": (0.15, 0.60),
    "mistral-small-2603": (0.15, 0.60),
    "mistral-medium-2508": (0.40, 2.00),
    "mistral-medium-3.5": (1.50, 7.50),
    "mistral-large-latest": (0.50, 1.50),
    "meta-llama/llama-3.2-1b-instruct": (0.027, 0.201),
}


# Generative model for simulated texture reads: the raw guess is an affine
# distortion of true ability plus a shared per-run bias and per-answer noise.
# Calibration must undo the distortion and measure both noise components.
SIM_DIRECT_INTERCEPT = 380.0
SIM_DIRECT_SLOPE = 0.62
SIM_DIRECT_MODEL_BIAS_SD = 80.0
SIM_DIRECT_ANSWER_SD = 180.0


def _simulated_raw_guess(target_elo: float, model_bias: float, rng: random.Random) -> float:
    latent = target_elo + model_bias + rng.gauss(0.0, SIM_DIRECT_ANSWER_SD)
    return SIM_DIRECT_INTERCEPT + SIM_DIRECT_SLOPE * latent


def simulated_calibration(seed: int = 29, answers_per_model: int = 5) -> DirectCalibration:
    """Fit the real calibration code on synthetic texture reads with known truth."""
    rng = random.Random(seed)
    observations: list[DirectObservation] = []
    for index, elo in enumerate((950.0, 1150.0, 1350.0, 1550.0, 1750.0, 1950.0, 2150.0)):
        model_bias = rng.gauss(0.0, SIM_DIRECT_MODEL_BIAS_SD)
        for _ in range(answers_per_model):
            observations.append(
                DirectObservation(
                    model=f"synthetic-calibration-{index}",
                    true_elo=elo,
                    raw_guess=_simulated_raw_guess(elo, model_bias, rng),
                )
            )
    return fit_direct_calibration(observations, grader_model="simulation")


def _resolve_question_mode(value: str | None) -> str:
    mode = (value or os.environ.get("VIBERANK_QUESTION_MODE", DEFAULT_QUESTION_MODE)).strip().lower()
    if mode not in QUESTION_MODES:
        raise ValueError(f"question_mode must be one of: {', '.join(QUESTION_MODES)}")
    return mode


def _question_limit(mode: str) -> int:
    configured = int(os.environ.get("VIBERANK_MAX_QUESTIONS", DEFAULT_MAX_QUESTIONS))
    return min(configured, len(FIXED_DEBUG_QUESTIONS)) if mode == "fixed" else configured


def _sample_index(probabilities: list[float], rng: random.Random) -> int:
    draw = rng.random()
    cumulative = 0.0
    for index, probability in enumerate(probabilities):
        cumulative += probability
        if draw <= cumulative:
            return index
    return len(probabilities) - 1


def _generate_answer(client: Any, question: Question) -> tuple[str, dict[str, int | None]]:
    result = client.complete_with_usage(
        [
            {
                "role": "system",
                "content": "Answer the question directly. Explain enough to support the conclusion, but do not discuss evaluation or grading.",
            },
            {"role": "user", "content": question.prompt},
        ],
        temperature=0.2,
        max_tokens=int(
            os.environ.get("VIBERANK_TARGET_MAX_TOKENS", DEFAULT_TARGET_MAX_TOKENS)
        ),
    )
    return result.content, result.usage_dict()


def _empty_usage() -> dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _add_usage(total: dict[str, int], addition: dict[str, int | None]) -> None:
    for key in total:
        total[key] += int(addition.get(key) or 0)


def _usage_cost(usage: dict[str, int], model: str) -> float | None:
    rates = MODEL_RATES.get(model)
    if rates is None:
        return None
    input_rate, output_rate = rates
    return (
        usage["prompt_tokens"] * input_rate
        + usage["completion_tokens"] * output_rate
    ) / 1_000_000


def _simulation_question(
    posterior: PosteriorSummary,
    *,
    step: int,
    rng: random.Random,
) -> Question:
    left = rng.randint(4, 14)
    right = rng.randint(3, 11)
    offset = rng.randint(2, 17)
    result = left * right + offset
    difficulty = round(posterior.median_elo / 10.0) * 10.0
    prompt = (
        f"A synthetic reasoning process multiplies {left} by {right}, then adds {offset}. "
        "Compute the result and briefly identify the two operations in order."
    )
    return Question(
        id=f"synthetic-generated-{step}-{left}-{right}-{offset}",
        title=f"Generated arithmetic probe {step}",
        domain="synthetic reasoning",
        prompt=prompt,
        reference_answer=f"{left} × {right} = {left * right}; adding {offset} gives {result}.",
        rubric=(
            "Computes the multiplication correctly",
            "Adds the offset correctly",
            "States the operations in the requested order",
        ),
        grade_anchors=(
            f"The result is {result + left}.",
            f"Multiply {left} and {right}; the answer is {left * right}, without applying the final addition.",
            f"The result is {result}, obtained by multiplication and addition.",
            f"First {left} × {right} = {left * right}; then {left * right} + {offset} = {result}.",
        ),
        difficulty_elo=difficulty,
    )


@dataclass
class EvaluationConfig:
    provider: str
    model: str
    questions: int
    target_elo: float | None = None
    seed: int = 7
    question_mode: str | None = None


def run_evaluation(config: EvaluationConfig) -> dict[str, Any]:
    question_mode = _resolve_question_mode(config.question_mode)
    max_questions = _question_limit(question_mode)
    if config.questions < 1 or config.questions > max_questions:
        raise ValueError(f"questions must be between 1 and {max_questions}")
    rng = random.Random(config.seed)
    posterior = EloPosterior()
    authored_questions: list[Question] = []
    traces: list[dict[str, Any]] = []
    aggregate_usage = {
        "author": _empty_usage(),
        "target": _empty_usage(),
        "grader": _empty_usage(),
    }

    calibration = load_calibration()
    expected_grader = (
        "simulation"
        if config.provider == "simulation"
        else os.environ.get("MISTRAL_GRADER_MODEL", "mistral-medium-3.5")
    )
    direct_off_reason: str | None = None
    if calibration is None:
        direct_off_reason = f"No calibration file at {calibration_path()}"
    elif not calibration.usable:
        direct_off_reason = calibration.reason
    elif calibration.grader_model != expected_grader:
        # The noise components are measured properties of one specific grader;
        # a mismatched grader (including simulation vs live) invalidates them.
        direct_off_reason = (
            f"Calibration was fit for grader '{calibration.grader_model}' but this run "
            f"uses '{expected_grader}'; recalibrate before the channel can activate"
        )
    direct_active = direct_off_reason is None
    simulated_model_bias = 0.0

    item_calibration = ItemCalibration.load()
    if item_calibration is None:
        items_off_reason: str | None = f"No item calibration at {item_calibration_path()}"
    elif not item_calibration.usable:
        items_off_reason = item_calibration.reason
    elif item_calibration.grader_model != expected_grader:
        items_off_reason = (
            f"Item calibration was fit for grader '{item_calibration.grader_model}' but this "
            f"run uses '{expected_grader}'; recalibrate before fitted difficulties can apply"
        )
    else:
        items_off_reason = None
    items_active = items_off_reason is None
    question_bank: tuple[Question, ...] = (
        tuple(item_calibration.apply_to_questions(FIXED_DEBUG_QUESTIONS))  # type: ignore[union-attr]
        if items_active
        else FIXED_DEBUG_QUESTIONS
    )

    holistic_calibration = HolisticCalibration.load()
    if config.provider == "simulation":
        holistic_off_reason: str | None = "Holistic channel needs a live grader"
    elif holistic_calibration is None:
        holistic_off_reason = f"No holistic calibration at {holistic_calibration_path()}"
    elif not holistic_calibration.usable:
        holistic_off_reason = holistic_calibration.reason
    elif holistic_calibration.grader_model != expected_grader:
        holistic_off_reason = (
            f"Holistic calibration was fit for grader '{holistic_calibration.grader_model}' "
            f"but this run uses '{expected_grader}'; recalibrate"
        )
    else:
        holistic_off_reason = None
    holistic_active = holistic_off_reason is None
    holistic_final: dict[str, Any] | None = None

    grader_client = None
    if config.provider == "simulation":
        if config.target_elo is None:
            raise ValueError("Simulation mode requires target_elo")
        target_client = None
        author = None
        grader = None
        simulated_model_bias = rng.gauss(0.0, SIM_DIRECT_MODEL_BIAS_SD)
    elif config.provider == "mistral":
        target_client = mistral_client(config.model)
        grader_client = mistral_client()
        author = MistralQuestionAuthor(grader_client) if question_mode == "authored" else None
        grader = MistralGrader(grader_client)
    elif config.provider == "openrouter":
        target_client = openrouter_client(config.model)
        grader_client = mistral_client()
        author = MistralQuestionAuthor(grader_client) if question_mode == "authored" else None
        grader = MistralGrader(grader_client)
    else:
        raise ValueError("provider must be simulation, mistral, or openrouter")
    collected_answers: list[str] = []

    for step in range(1, config.questions + 1):
        before_entropy = posterior.entropy_nats
        if question_mode == "fixed":
            question = question_bank[step - 1]
            author_usage = _empty_usage()
        elif config.provider == "simulation":
            question = _simulation_question(
                posterior.summary(),
                step=step,
                rng=rng,
            )
            author_usage = _empty_usage()
        else:
            question, author_usage = author.write_with_usage(  # type: ignore[union-attr]
                posterior.summary(),
                step=step,
                previous_questions=authored_questions,
            )

        if config.provider == "simulation":
            true_probs = category_probabilities(question, float(config.target_elo))
            category = _sample_index(true_probs, rng)
            answer = question.grade_anchors[category]
            grade = simulated_grade(category)
            raw_guess = _simulated_raw_guess(
                float(config.target_elo), simulated_model_bias, rng
            )
            grade = replace(grade, apparent_elo=round(raw_guess, 1))
            target_usage = _empty_usage()
            grader_usage = _empty_usage()
        else:
            answer, target_usage = _generate_answer(target_client, question)
            grade, grader_usage = grader.grade_with_usage(question, answer)  # type: ignore[union-attr]

        authored_questions.append(question)
        collected_answers.append(answer)
        _add_usage(aggregate_usage["author"], author_usage)
        _add_usage(aggregate_usage["target"], target_usage)
        _add_usage(aggregate_usage["grader"], grader_usage)

        holistic_trace: dict[str, Any] | None = None
        if holistic_active and grader_client is not None:
            raw_read, holistic_usage = holistic_read(
                grader_client, authored_questions, collected_answers
            )
            _add_usage(aggregate_usage["grader"], holistic_usage)
            corrected, sigma = holistic_calibration.apply(step, raw_read["mean_elo"])  # type: ignore[union-attr]
            holistic_trace = {
                "raw_mean_elo": round(raw_read["mean_elo"], 1),
                "mean_elo": round(corrected, 1),
                "sigma_elo": round(sigma, 1),
                "low_elo": round(corrected - INTERVAL_Z * sigma, 1),
                "high_elo": round(corrected + INTERVAL_Z * sigma, 1),
                "assessment": raw_read["assessment"],
            }
            holistic_final = holistic_trace

        posterior.update(question, grade)
        direct_trace: dict[str, Any] | None = None
        if grade.apparent_elo is not None:
            if direct_active:
                calibrated_guess = calibration.apply(grade.apparent_elo)
                posterior.observe_direct(
                    calibrated_guess,
                    tau_elo=calibration.tau_elo,
                    sigma_w_elo=calibration.sigma_w_elo,
                )
                direct_trace = {
                    "raw_guess": round(grade.apparent_elo, 1),
                    "calibrated_guess": round(calibrated_guess, 1),
                    "applied": True,
                }
            else:
                direct_trace = {
                    "raw_guess": round(grade.apparent_elo, 1),
                    "calibrated_guess": None,
                    "applied": False,
                }
        after_entropy = posterior.entropy_nats
        ordinal_step = posterior.summary().to_dict()
        if holistic_trace is not None:
            step_estimate = {
                "mean_elo": holistic_trace["mean_elo"],
                "median_elo": holistic_trace["mean_elo"],
                "low_elo": holistic_trace["low_elo"],
                "high_elo": holistic_trace["high_elo"],
                "standard_deviation": holistic_trace["sigma_elo"],
            }
        else:
            step_estimate = ordinal_step
        traces.append(
            {
                "step": step,
                "question": question.public_dict(),
                "grader_context": question.grader_context_dict(),
                "answer": answer,
                "grade": grade.to_dict(),
                "direct": direct_trace,
                "holistic": holistic_trace,
                "usage": {
                    "author": author_usage,
                    "target": target_usage,
                    "grader": grader_usage,
                },
                "entropy_reduction_nats": round(before_entropy - after_entropy, 4),
                "posterior_entropy_nats": round(after_entropy, 4),
                "posterior": step_estimate,
                "ordinal_posterior": ordinal_step,
            }
        )

    summary = posterior.summary()
    if holistic_final is not None:
        headline = {
            "mean_elo": holistic_final["mean_elo"],
            "median_elo": holistic_final["mean_elo"],
            "low_elo": holistic_final["low_elo"],
            "high_elo": holistic_final["high_elo"],
            "standard_deviation": holistic_final["sigma_elo"],
        }
        sigma = float(holistic_final["sigma_elo"])
        center = float(holistic_final["mean_elo"])
        series = [
            {
                "elo": float(elo),
                "density": math.exp(-0.5 * ((elo - center) / sigma) ** 2),
            }
            for elo in posterior.grid
        ]
        method = (
            "calibrated holistic transcript read (primary) with ordinal partial-credit "
            "channel as diagnostic"
        )
    else:
        headline = summary.to_dict()
        series = posterior.series()
        method = (
            "fixed debug questions with soft ordinal partial-credit Elo updates"
            if question_mode == "fixed"
            else "grader-authored questions with soft ordinal partial-credit Elo updates"
        )
    if direct_active:
        direct_channel: dict[str, Any] = {
            "enabled": True,
            "observations": posterior.direct_observation_count,
            "tau_elo": round(calibration.tau_elo, 1),
            "sigma_w_elo": round(calibration.sigma_w_elo, 1),
            "calibration_models": calibration.n_models,
            "grader_model": calibration.grader_model,
        }
    else:
        direct_channel = {
            "enabled": False,
            "reason": direct_off_reason,
        }
    if items_active:
        item_status: dict[str, Any] = {
            "active": True,
            "reference_models": item_calibration.n_models,  # type: ignore[union-attr]
            "discrimination": round(item_calibration.discrimination, 2),  # type: ignore[union-attr]
        }
    else:
        item_status = {"active": False, "reason": items_off_reason}
    if holistic_active:
        holistic_status: dict[str, Any] = {
            "active": True,
            "reference_models": holistic_calibration.n_models,  # type: ignore[union-attr]
            "final_sigma_elo": (
                holistic_final["sigma_elo"] if holistic_final is not None else None
            ),
        }
    else:
        holistic_status = {"active": False, "reason": holistic_off_reason}
    result: dict[str, Any] = {
        "provider": config.provider,
        "model": config.model,
        "questions": config.questions,
        "question_mode": question_mode,
        "estimate": headline,
        "ordinal_estimate": summary.to_dict(),
        "posterior_series": series,
        "traces": traces,
        "direct_channel": direct_channel,
        "item_calibration": item_status,
        "holistic_channel": holistic_status,
        "method": method,
        "usage": aggregate_usage,
    }
    if config.provider != "simulation":
        grader_model = os.environ.get("MISTRAL_GRADER_MODEL", "mistral-medium-3.5")
        target_cost = _usage_cost(aggregate_usage["target"], config.model)
        grader_cost = _usage_cost(aggregate_usage["grader"], grader_model)
        author_cost = (
            _usage_cost(aggregate_usage["author"], grader_model)
            if question_mode == "authored"
            else 0.0
        )
        known_costs = [target_cost, grader_cost, author_cost]
        result["cost"] = {
            "target_usd": round(target_cost, 8) if target_cost is not None else None,
            "grader_usd": round(grader_cost, 8) if grader_cost is not None else None,
            "author_usd": round(author_cost, 8) if author_cost is not None else None,
            "total_usd": (
                round(sum(float(cost) for cost in known_costs), 8)
                if all(cost is not None for cost in known_costs)
                else None
            ),
        }
    if config.target_elo is not None:
        result["target_elo"] = config.target_elo
        result["absolute_error"] = round(
            abs(float(headline["mean_elo"]) - config.target_elo), 1
        )
    return result


def _ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor
        while end + 1 < len(order) and values[order[end + 1]] == values[order[cursor]]:
            end += 1
        average_rank = (cursor + end) / 2.0
        for position in range(cursor, end + 1):
            result[order[position]] = average_rank
        cursor = end + 1
    return result


def _pearson(left: list[float], right: list[float]) -> float:
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_scale = math.sqrt(sum((x - left_mean) ** 2 for x in left))
    right_scale = math.sqrt(sum((y - right_mean) ** 2 for y in right))
    if left_scale == 0 or right_scale == 0:
        return 0.0
    return numerator / (left_scale * right_scale)


def _spearman(left: list[float], right: list[float]) -> float:
    return _pearson(_ranks(left), _ranks(right))


def run_synthetic_validation(
    questions: int = 3,
    repeats: int = 20,
    seed: int = 17,
    question_mode: str | None = None,
) -> dict[str, Any]:
    resolved_mode = _resolve_question_mode(question_mode)
    max_questions = _question_limit(resolved_mode)
    if questions < 1 or questions > max_questions:
        raise ValueError(f"questions must be between 1 and {max_questions}")
    targets = [1000.0, 1150.0, 1300.0, 1450.0, 1600.0, 1750.0, 1900.0, 2050.0]
    methods = ("binary", "ordinal", "ordinal_direct")
    calibration = simulated_calibration(seed=seed + 7919)
    output: dict[str, Any] = {}

    for method_index, method in enumerate(methods):
        true_values: list[float] = []
        predictions: list[float] = []
        points: list[dict[str, float]] = []
        covered = 0
        sd_total = 0.0
        for target_index, target in enumerate(targets):
            target_predictions = []
            for repetition in range(repeats):
                rng = random.Random(seed + method_index * 100_000 + target_index * 1000 + repetition)
                posterior = EloPosterior()
                model_bias = rng.gauss(0.0, SIM_DIRECT_MODEL_BIAS_SD)
                for step in range(1, questions + 1):
                    question = (
                        FIXED_DEBUG_QUESTIONS[step - 1]
                        if resolved_mode == "fixed"
                        else _simulation_question(
                            posterior.summary(),
                            step=step,
                            rng=rng,
                        )
                    )
                    category = _sample_index(category_probabilities(question, target), rng)
                    if method == "binary":
                        posterior.update_binary(question, 1.0 if category == 3 else 0.0)
                    else:
                        posterior.update(question, simulated_grade(category))
                    if method == "ordinal_direct" and calibration.usable:
                        raw_guess = _simulated_raw_guess(target, model_bias, rng)
                        posterior.observe_direct(
                            calibration.apply(raw_guess),
                            tau_elo=calibration.tau_elo,
                            sigma_w_elo=calibration.sigma_w_elo,
                        )
                summary = posterior.summary()
                prediction = summary.mean_elo
                sd_total += summary.standard_deviation
                if summary.low_elo <= target <= summary.high_elo:
                    covered += 1
                true_values.append(target)
                predictions.append(prediction)
                target_predictions.append(prediction)
            points.append(
                {
                    "true_elo": target,
                    "predicted_elo": round(sum(target_predictions) / len(target_predictions), 1),
                }
            )
        output[method] = {
            "spearman": round(_spearman(true_values, predictions), 3),
            "mae": round(
                sum(abs(true - predicted) for true, predicted in zip(true_values, predictions))
                / len(true_values),
                1,
            ),
            "mean_posterior_sd": round(sd_total / len(true_values), 1),
            "coverage_90": round(covered / len(true_values), 3),
            "points": points,
        }

    return {
        "questions": questions,
        "question_mode": resolved_mode,
        "repeats_per_ability": repeats,
        "abilities": targets,
        "results": output,
        "direct_calibration": {
            "usable": calibration.usable,
            "slope": round(calibration.slope, 3),
            "intercept": round(calibration.intercept, 1),
            "tau_elo": round(calibration.tau_elo, 1),
            "sigma_w_elo": round(calibration.sigma_w_elo, 1),
            "r_squared": round(calibration.r_squared, 3),
        },
        "warning": (
            "Synthetic validation tests the estimator under assumed fixed-question difficulties; "
            "it does not test the live grader or establish that those difficulties are calibrated."
        ),
    }


def runtime_config() -> dict[str, Any]:
    question_mode = _resolve_question_mode(None)
    calibration = load_calibration()
    if calibration is None:
        direct_channel: dict[str, Any] = {
            "calibrated": False,
            "reason": f"No calibration file at {calibration_path()}",
        }
    else:
        direct_channel = {
            "calibrated": calibration.usable,
            "reason": calibration.reason,
            "calibration_models": calibration.n_models,
            "tau_elo": round(calibration.tau_elo, 1),
            "sigma_w_elo": round(calibration.sigma_w_elo, 1),
            "r_squared": round(calibration.r_squared, 3),
            "grader_model": calibration.grader_model,
        }
    item_calibration = ItemCalibration.load()
    if item_calibration is None:
        item_status: dict[str, Any] = {
            "calibrated": False,
            "reason": f"No item calibration at {item_calibration_path()}",
        }
    else:
        item_status = {
            "calibrated": item_calibration.usable,
            "reason": item_calibration.reason,
            "reference_models": item_calibration.n_models,
            "grader_model": item_calibration.grader_model,
            "discrimination": round(item_calibration.discrimination, 2),
        }
    holistic_calibration = HolisticCalibration.load()
    if holistic_calibration is None:
        holistic_status: dict[str, Any] = {
            "calibrated": False,
            "reason": f"No holistic calibration at {holistic_calibration_path()}",
        }
    else:
        holistic_status = {
            "calibrated": holistic_calibration.usable,
            "reason": holistic_calibration.reason,
            "reference_models": holistic_calibration.n_models,
            "grader_model": holistic_calibration.grader_model,
            "elo_spread": holistic_calibration.elo_spread,
        }
    return {
        "max_questions": _question_limit(question_mode),
        "question_mode": question_mode,
        "fixed_question_count": len(FIXED_DEBUG_QUESTIONS),
        "mistral_available": bool(os.environ.get("MISTRAL_API_KEY")),
        "openrouter_available": bool(os.environ.get("OPENROUTER_API_KEY")),
        "grader_model": os.environ.get("MISTRAL_GRADER_MODEL", "mistral-medium-3.5"),
        "direct_channel": direct_channel,
        "item_calibration": item_status,
        "holistic_channel": holistic_status,
    }

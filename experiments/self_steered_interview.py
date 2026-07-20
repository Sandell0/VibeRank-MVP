"""Self-steered interviews: the interviewer decides everything itself.

No posterior, no difficulty target handed down. At each step gpt-5.6-terra
sees the raw transcript so far (its questions, references, the candidate's
answers — no grades) and freely chooses the next probe and its difficulty,
with license to jump aggressively. Medium grades in parallel (unseen by the
interviewer) for the ladder readout and dual-grade data. Terra gives a final
examiner's verdict after Q5.

Readouts, all leave-one-out on 25 known-Elo models:
  - interviewer's final verdict (raw + calibrated);
  - ladder on Terra's self-chosen difficulty labels with medium pass/fail;
  - difficulty trajectories (does self-steering fix the runway problem?).

    python -m experiments.self_steered_interview
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from experiments.adaptive_battle import TARGETS
from viberank.clients import ProviderError, mistral_client, openrouter_client
from viberank.domain import Question
from viberank.grading import MistralGrader, _extract_json

EXP = Path(__file__).resolve().parent
DATA_PATH = EXP / "self_steered_data.json"
INTERVIEWER = "openai/gpt-5.6-terra"
QUESTIONS = 5
FRONTIER_FLOOR = 1740.0
PASS = 2.5
RETRY_SLEEPS = (5, 15, 30)


def call_json(client, system: str, user: str, temperature: float, label: str) -> dict:
    for attempt, sleep_s in enumerate((0,) + RETRY_SLEEPS):
        if sleep_s:
            time.sleep(sleep_s)
        try:
            result = client.complete_with_usage(
                [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                json_mode=True,
                # OpenRouter reserves credits for the full max_tokens; the
                # default 60k reservation fails on a low balance.
                max_tokens=12000,
            )
            return _extract_json(result.content)
        except ProviderError as exc:
            print(f"    {label} attempt {attempt + 1} failed: {str(exc)[:110]}")
    raise RuntimeError(f"{label}: retries exhausted")


def transcript_text(steps: list[dict]) -> str:
    if not steps:
        return "(no questions asked yet)"
    blocks = []
    for index, step in enumerate(steps, start=1):
        blocks.append(
            f"""QUESTION {index} (you rated it difficulty {step['difficulty']:.0f}):
{step['prompt']}

YOUR PRIVATE REFERENCE:
{step['reference']}

CANDIDATE'S ANSWER:
{step['answer']}"""
        )
    return "\n\n---\n\n".join(blocks)


def next_question(client, steps: list[dict], step_number: int) -> dict:
    prompt = f"""You are an expert examiner estimating an anonymous language model's ability, expressed as an Elo on a scale where 1000 is a very weak small model, 1400 a capable mid-tier model, 1800 a strong frontier model, and 2200 exceptional.

You may ask {QUESTIONS} questions total. This is question {step_number}. Below is the interview so far. Read the candidate's answers yourself and decide what to probe next. Choose the content AND the difficulty freely — jump as aggressively as the evidence warrants in either direction. Your goal is that each question extracts maximum new information about where the candidate's ability boundary lies.

Requirements for the question: novel, self-contained, objectively gradable, answerable without tools, hard through reasoning rather than obscure recall. Solve it yourself first; the reference answer must be complete and correct. Rate its difficulty honestly on the Elo scale above.

Return JSON only:
{{
  "steering_note": "one sentence: what the answers so far tell you and why this next question",
  "difficulty_elo": 0,
  "title": "short title",
  "domain": "short domain",
  "prompt": "complete question shown to the candidate",
  "reference_answer": "complete rigorous private solution",
  "rubric": ["criterion 1", "criterion 2", "criterion 3"],
  "grade_anchors": {{
    "wrong": "representative fundamentally wrong answer",
    "major_error": "representative answer with a central error",
    "minor_error": "representative nearly correct answer",
    "fully_correct": "representative complete correct answer"
  }}
}}

INTERVIEW SO FAR
{transcript_text(steps)}"""
    raw = call_json(
        client,
        "Return strict JSON. You are conducting an adaptive examination; steer it yourself.",
        prompt,
        0.7,
        f"author q{step_number}",
    )
    question = Question.from_author_dict(
        raw,
        identifier=f"self-steered-{step_number}",
        difficulty_elo=float(raw["difficulty_elo"]),
    )
    return {"question": question, "steering_note": str(raw.get("steering_note", ""))}


def final_verdict(client, steps: list[dict]) -> dict:
    prompt = f"""You are the examiner who conducted the interview below. Give your final assessment of the candidate's ability as an Elo (1000 very weak small model, 1400 capable mid-tier, 1800 strong frontier, 2200 exceptional). Weigh which difficulties were handled and which failed. Keep the 90% interval honest.

Return JSON only:
{{"mean_elo": 0, "low_90": 0, "high_90": 0, "assessment": "brief evidence"}}

INTERVIEW
{transcript_text(steps)}"""
    return call_json(
        client,
        "Return strict JSON. Deliver your examiner's verdict with honest uncertainty.",
        prompt,
        0.0,
        "final verdict",
    )


def answer_question(client, prompt_text: str) -> str:
    for attempt, sleep_s in enumerate((0,) + RETRY_SLEEPS):
        if sleep_s:
            time.sleep(sleep_s)
        try:
            result = client.complete_with_usage(
                [
                    {
                        "role": "system",
                        "content": (
                            "Answer the question directly. Explain enough to support the "
                            "conclusion, but do not discuss evaluation or grading."
                        ),
                    },
                    {"role": "user", "content": prompt_text},
                ],
                temperature=0.2,
                max_tokens=8000,
            )
            return result.content
        except ProviderError as exc:
            print(f"    answer attempt {attempt + 1} failed: {str(exc)[:110]}")
    raise RuntimeError("answer: retries exhausted")


def collect() -> dict:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.is_file() else {"models": {}}
    interviewer = openrouter_client(INTERVIEWER)
    grader = MistralGrader(mistral_client())
    for provider, model, elo, row in TARGETS:
        record = data["models"].setdefault(
            model,
            {"provider": provider, "public_elo": elo, "leaderboard_row": row, "steps": []},
        )
        if record.get("verdict") is not None:
            print(f"{model}: cached")
            continue
        print(f"{model} (public {elo:.0f}):")
        try:
            target = openrouter_client(model) if provider == "openrouter" else mistral_client(model)
            steps = record["steps"]
            while len(steps) < QUESTIONS:
                authored = next_question(interviewer, steps, len(steps) + 1)
                question = authored["question"]
                answer = answer_question(target, question.prompt)
                grade, _ = grader.grade_with_usage(question, answer)
                steps.append(
                    {
                        "difficulty": question.difficulty_elo,
                        "title": question.title,
                        "prompt": question.prompt,
                        "reference": question.reference_answer,
                        "rubric": list(question.rubric),
                        "answer": answer,
                        "medium_score": grade.expected_score,
                        "steering_note": authored["steering_note"],
                    }
                )
                print(
                    f"  Q{len(steps)} d{question.difficulty_elo:.0f} ({question.title[:38]}) "
                    f"-> medium {grade.expected_score:.2f} | {authored['steering_note'][:70]}"
                )
                DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
            verdict = final_verdict(interviewer, steps)
            record["verdict"] = verdict
            print(f"  verdict: {verdict['mean_elo']:.0f} ({verdict['low_90']:.0f}-{verdict['high_90']:.0f})")
            DATA_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
        except (RuntimeError, ProviderError, ValueError, KeyError) as exc:
            print(f"  SKIPPED {model}: {str(exc)[:140]}")
            continue
    return data


def spearman(a, b):
    def ranks(v):
        order = sorted(range(len(v)), key=v.__getitem__)
        out = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2.0
            i = j + 1
        return out

    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else 0.0


def loo_stats(scores, truths):
    names = list(scores)
    estimates = {}
    for held in names:
        pairs = [(truths[n], scores[n]) for n in names if n != held]
        k = len(pairs)
        tm = sum(t for t, _ in pairs) / k
        sm = sum(s for _, s in pairs) / k
        tv = sum((t - tm) ** 2 for t, _ in pairs)
        cov = sum((t - tm) * (s - sm) for t, s in pairs)
        slope = cov / tv if tv else 0.0
        estimates[held] = (
            scores[held] if slope <= 0.05 else (scores[held] - (sm - slope * tm)) / slope
        )
    frontier = [n for n in names if truths[n] >= FRONTIER_FLOOR]

    def mae(sub):
        return sum(abs(estimates[n] - truths[n]) for n in sub) / len(sub)

    return {
        "overall_mae": mae(names),
        "overall_rho": spearman([truths[n] for n in names], [scores[n] for n in names]),
        "frontier_mae": mae(frontier) if frontier else float("nan"),
        "frontier_rho": (
            spearman([truths[n] for n in frontier], [scores[n] for n in frontier])
            if len(frontier) >= 4
            else float("nan")
        ),
    }


def ladder_score(steps) -> float:
    passed = [s["difficulty"] for s in steps if s["medium_score"] >= PASS]
    failed = [s["difficulty"] for s in steps if s["medium_score"] < PASS]
    top_pass = max(passed) if passed else min(s["difficulty"] for s in steps) - 300.0
    low_fail = min(failed) if failed else max(s["difficulty"] for s in steps) + 300.0
    return (top_pass + low_fail) / 2.0


def analyze(data: dict) -> None:
    models = {
        n: r for n, r in data["models"].items() if r.get("verdict") and len(r["steps"]) == QUESTIONS
    }
    if len(models) < 8:
        print(f"only {len(models)} complete; not analyzing")
        return
    truths = {n: models[n]["public_elo"] for n in models}
    verdicts = {n: float(models[n]["verdict"]["mean_elo"]) for n in models}
    ladders = {n: ladder_score(models[n]["steps"]) for n in models}

    print(f"\ncomplete models: {len(models)}")
    for label, scores in (("interviewer verdict", verdicts), ("self-labeled ladder", ladders)):
        stats = loo_stats(scores, truths)
        print(
            f"{label:<22} overall MAE {stats['overall_mae']:.0f} rho {stats['overall_rho']:.2f} | "
            f"frontier MAE {stats['frontier_mae']:.0f} rho {stats['frontier_rho']:.2f}"
        )
    print("\ndifficulty trajectories (weakest/strongest thirds):")
    ordered = sorted(models, key=lambda n: truths[n])
    third = max(1, len(ordered) // 3)
    for label, group in (("weakest", ordered[:third]), ("strongest", ordered[-third:])):
        by_step = [
            sum(models[n]["steps"][k]["difficulty"] for n in group) / len(group)
            for k in range(QUESTIONS)
        ]
        print(f"  {label:<10} " + " ".join(f"{v:>6.0f}" for v in by_step))
    out = EXP / "self_steered_results.json"
    out.write_text(
        json.dumps(
            {
                "verdicts": {n: verdicts[n] for n in models},
                "ladders": {n: ladders[n] for n in models},
                "truths": truths,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved {out}")


def main() -> None:
    data = collect()
    analyze(data)


if __name__ == "__main__":
    main()

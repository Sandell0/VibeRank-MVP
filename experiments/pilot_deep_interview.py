"""Pilot for the deep-interview experiment: 5 mid-tier models x 25 questions.

De-risks the full 30-model run before spending on it:
  * does the self-steered ladder stay coherent to k=25 (never run past 5)?
  * does err(k) keep falling past k=5, or hit a floor early?
  * is the cost model right? (usage is metered per role and priced live)

Sol authors (matching the best-accuracy run), mistral-medium grades each
answer for the ladder readout, targets answer standalone. Resumable: state
is written after every step, finished models are skipped on rerun.

    $env:MISTRAL_API_KEY = "..."; $env:OPENROUTER_API_KEY = "..."
    python -m experiments.pilot_deep_interview
"""
from __future__ import annotations

import json
from pathlib import Path

import experiments.self_steered_interview as ssi
from viberank.clients import ProviderError, mistral_client, openrouter_client
from viberank.grading import MistralGrader

EXP = Path(__file__).resolve().parent
DATA_PATH = EXP / "pilot_deep_data.json"

INTERVIEWER = "openai/gpt-5.6-sol"
QUESTIONS = 25
ssi.QUESTIONS = QUESTIONS  # next_question() reads the module global in its prompt

# five families, spanning the mid-tier band where the aggregate is weakest
TARGETS = (
    ("openrouter", "meta-llama/llama-3.1-8b-instruct", 1440.0, "Llama 3.1 8B Instruct"),
    ("openrouter", "microsoft/phi-4", 1485.0, "Phi-4"),
    ("mistral", "mistral-small-2506", 1574.0, "Mistral Small 3.2"),
    ("openrouter", "google/gemma-3-27b-it", 1588.0, "Gemma 3 27B (IT)"),
    ("openrouter", "moonshotai/kimi-k2-0905", 1688.0, "Kimi K2 0905"),
)

# $/1M tokens (list prices from theaggregate.ai data, 2026-08)
PRICES = {
    "author": (5.0, 30.0),     # gpt-5.6-sol
    "steer": (1.5, 7.5),       # mistral-medium
    "target": (0.5, 2.0),      # mid-tier average, close enough for a meter
}


class Meter:
    """Wraps a client; accumulates prompt/completion tokens across calls."""

    def __init__(self, client):
        self._client = client
        self.prompt = 0
        self.completion = 0

    def complete_with_usage(self, *args, **kwargs):
        result = self._client.complete_with_usage(*args, **kwargs)
        self.prompt += getattr(result, "prompt_tokens", None) or 0
        self.completion += getattr(result, "completion_tokens", None) or 0
        return result


def usd(meter: Meter, role: str) -> float:
    pin, pout = PRICES[role]
    return meter.prompt / 1e6 * pin + meter.completion / 1e6 * pout


def main() -> None:
    data = (
        json.loads(DATA_PATH.read_text(encoding="utf-8"))
        if DATA_PATH.is_file()
        else {"models": {}}
    )
    author = Meter(openrouter_client(INTERVIEWER))
    grader = MistralGrader(mistral_client())
    steer_usage = {"prompt": 0, "completion": 0}
    for provider, model, elo, row in TARGETS:
        record = data["models"].setdefault(
            model,
            {"provider": provider, "public_elo": elo, "leaderboard_row": row, "steps": []},
        )
        if record.get("verdict") is not None:
            print(f"{model}: done, skipping")
            continue
        print(f"{model} (public {elo:.0f}):")
        target = Meter(
            openrouter_client(model) if provider == "openrouter" else mistral_client(model)
        )
        try:
            steps = record["steps"]
            while len(steps) < QUESTIONS:
                authored = ssi.next_question(author, steps, len(steps) + 1)
                question = authored["question"]
                answer = ssi.answer_question(target, question.prompt)
                grade, g_usage = grader.grade_with_usage(question, answer)
                if g_usage:  # dict from CompletionResult.usage_dict()
                    steer_usage["prompt"] += g_usage.get("prompt_tokens") or 0
                    steer_usage["completion"] += g_usage.get("completion_tokens") or 0
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
                record["target_usage"] = {
                    "prompt": target.prompt,
                    "completion": target.completion,
                }
                data["author_usage"] = {
                    "prompt": author.prompt,
                    "completion": author.completion,
                }
                data["steer_usage"] = steer_usage
                DATA_PATH.write_text(
                    json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8"
                )
                print(
                    f"  Q{len(steps):>2} d{question.difficulty_elo:.0f} "
                    f"({question.title[:36]}) -> medium {grade.expected_score:.2f} "
                    f"| spend so far ~${usd(author, 'author'):.2f} author"
                )
            verdict = ssi.final_verdict(author, steps)
            record["verdict"] = verdict
            DATA_PATH.write_text(
                json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8"
            )
            print(
                f"  verdict: {verdict['mean_elo']:.0f} "
                f"({verdict['low_90']:.0f}-{verdict['high_90']:.0f}) vs public {elo:.0f}"
            )
        except (RuntimeError, ProviderError, ValueError, KeyError) as exc:
            print(f"  STOPPED {model}: {str(exc)[:140]} (state saved, rerun resumes)")
            continue

    a = usd(author, "author")
    s = steer_usage["prompt"] / 1e6 * PRICES["steer"][0] + steer_usage["completion"] / 1e6 * PRICES["steer"][1]
    print(f"\npilot spend: author ~${a:.2f}  steering ~${s:.2f}  (+ target calls, per-model in data file)")
    print(f"author tokens: {author.prompt:,} in / {author.completion:,} out")


if __name__ == "__main__":
    main()

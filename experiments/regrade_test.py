"""Does the grader matter? Terra re-grades every answer from the
Terra-authored run; compare verdicts with mistral-medium's and re-score the
ladder estimator with Terra's grades.

    python -m experiments.regrade_test
"""
from __future__ import annotations

import json
import math
import time
from pathlib import Path

from viberank.clients import ProviderError, openrouter_client
from viberank.domain import Question
from viberank.grading import MistralGrader

EXP = Path(__file__).resolve().parent
DATA_PATH = EXP / "terra_author_data.json"
REGRADE_PATH = EXP / "terra_regrade_data.json"
GRADER = "openai/gpt-5.6-terra"
FRONTIER_FLOOR = 1740.0
PASS = 2.5
RETRY_SLEEPS = (5, 15, 30)


def rebuild_question(trace) -> Question:
    q = trace["question"]
    ctx = trace["grader_context"]
    return Question(
        id=q["id"],
        title=q["title"],
        domain=q.get("domain", "reasoning"),
        prompt=q["prompt"],
        reference_answer=ctx["reference_answer"],
        rubric=tuple(ctx["rubric"]),
        grade_anchors=tuple(ctx["grade_anchors"][name] for name in ("wrong", "major_error", "minor_error", "fully_correct")),
        difficulty_elo=q["difficulty_elo"],
    )


def collect() -> dict:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))["models"]
    store = json.loads(REGRADE_PATH.read_text(encoding="utf-8")) if REGRADE_PATH.is_file() else {}
    grader = MistralGrader(openrouter_client(GRADER))
    for name, record in data.items():
        model_store = store.setdefault(name, {})
        for trace in record["full_traces"]:
            key = str(trace["step"])
            if key in model_store:
                continue
            question = rebuild_question(trace)
            grade = None
            for attempt, sleep_s in enumerate((0,) + RETRY_SLEEPS):
                if sleep_s:
                    time.sleep(sleep_s)
                try:
                    grade, _ = grader.grade_with_usage(question, trace["answer"])
                    break
                except ProviderError as exc:
                    print(f"  {name} Q{key} attempt {attempt + 1} failed: {str(exc)[:100]}")
            if grade is None:
                print(f"  SKIP {name} Q{key}")
                continue
            model_store[key] = {
                "terra_score": grade.expected_score,
                "medium_score": trace["grade"]["expected_score"],
                "difficulty": trace["question"]["difficulty_elo"],
                "explanation": grade.explanation,
            }
            print(
                f"{name} Q{key} (d{trace['question']['difficulty_elo']:.0f}): "
                f"medium {trace['grade']['expected_score']:.2f} -> terra {grade.expected_score:.2f}"
            )
            REGRADE_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")
            time.sleep(0.4)
    return store


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


def ladder_score(entries) -> float:
    passed = [e["difficulty"] for e in entries if e["score"] >= PASS]
    failed = [e["difficulty"] for e in entries if e["score"] < PASS]
    top_pass = max(passed) if passed else min(e["difficulty"] for e in entries) - 300.0
    low_fail = min(failed) if failed else max(e["difficulty"] for e in entries) + 300.0
    return (top_pass + low_fail) / 2.0


def loo_stats(scores, truths, floor):
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
    def mae(sub):
        return sum(abs(estimates[n] - truths[n]) for n in sub) / len(sub)
    frontier = [n for n in names if truths[n] >= floor]
    return (
        mae(names),
        mae(frontier),
        spearman([truths[n] for n in frontier], [scores[n] for n in frontier]),
    )


def analyze(store: dict) -> None:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))["models"]
    pairs = [
        (e["medium_score"], e["terra_score"], e["difficulty"])
        for model_store in store.values()
        for e in model_store.values()
    ]
    n = len(pairs)
    flips = [(m, t, d) for m, t, d in pairs if (m >= PASS) != (t >= PASS)]
    hard = [(m, t, d) for m, t, d in pairs if d >= 2000]
    hard_flips = [(m, t, d) for m, t, d in hard if (m >= PASS) != (t >= PASS)]
    mean_delta = sum(abs(t - m) for m, t, _ in pairs) / n
    print(f"\nanswers regraded: {n}")
    print(f"pass/fail flips: {len(flips)}/{n} ({100 * len(flips) / n:.0f}%)")
    print(f"  on hard items (d>=2000): {len(hard_flips)}/{len(hard)} ({100 * len(hard_flips) / max(1, len(hard)):.0f}%)")
    print(f"mean |score delta|: {mean_delta:.2f} (scale 0-3)")
    medium_stricter = sum(1 for m, t, _ in flips if m < t)
    print(f"flip direction: medium stricter {medium_stricter}, terra stricter {len(flips) - medium_stricter}")

    truths = {n_: data[n_]["public_elo"] for n_ in data}
    for grader_label, key in (("medium", "medium_score"), ("terra", "terra_score")):
        scores = {}
        for name, model_store in store.items():
            entries = [
                {"difficulty": e["difficulty"], "score": e[key]}
                for e in model_store.values()
            ]
            if len(entries) == 5:
                scores[name] = ladder_score(entries)
        overall, frontier_mae, frontier_rho = loo_stats(
            scores, {n_: truths[n_] for n_ in scores}, FRONTIER_FLOOR
        )
        print(
            f"ladder with {grader_label} grades: overall MAE {overall:.0f}, "
            f"frontier MAE {frontier_mae:.0f}, frontier spearman {frontier_rho:.2f}"
        )


def main() -> None:
    store = collect()
    analyze(store)


if __name__ == "__main__":
    main()

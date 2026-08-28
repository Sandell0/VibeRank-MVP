"""Tier 0: examiner difficulty-calibration from existing transcripts. Free.

Adaptive interviews target each candidate's boundary on the examiner's own
scale, so pooled (public_elo - rated_difficulty) analysis is confounded by
cross-candidate scale compression (measured: it inverts). Two metrics that
survive the adaptive design:

  1. WITHIN-candidate ordering AUC — across a single candidate's questions,
     does the examiner's own difficulty ranking predict pass/fail? (Higher-
     rated question => more likely to fail.) Scale-free, per-candidate,
     averaged with question-count weights. This is label NOISE.
  2. BOUNDARY consistency — per candidate, the maximum-likelihood pass/fail
     threshold on the examiner's difficulty scale; then (a) Spearman of
     boundaries vs public Elo across candidates, (b) LOO-affine residual of
     boundary -> public Elo. This is how much usable signal the examiner's
     labels carry end-to-end. Offset/stretch are affine-absorbable; rank
     errors and residuals are not.

Thesis test: do these improve with examiner Elo?
  mistral-medium 1626 -> qwen3.7-max 1831 -> terra 1889 -> sol 1954

    python -m experiments.examiner_calibration
"""
from __future__ import annotations

import json
import math
import statistics as st
from pathlib import Path

EXP = Path(__file__).resolve().parent
PASS = 2.5

SOURCES = [
    ("mistral-medium-3.5", 1626, "adaptive_battle_data.json", "medium-graded"),
    ("qwen3.7-max", 1831, "qwen_interview_data.json", "SELF-graded (confound)"),
    ("gpt-5.6-terra", 1889, "self_steered_data.json", "medium-graded"),
    ("gpt-5.6-sol", 1954, "sol_interview_data.json", "medium-graded"),
    ("gpt-5.6-sol (k=25 pilot)", 1954, "pilot_deep_data.json", "medium-graded"),
    ("gpt-5.6-terra (k=25 pilot)", 1889, "pilot_terra_data.json", "medium-graded"),
]


def extract(path: Path):
    """{candidate: (public_elo, [(difficulty, pass), ...])}"""
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for name, record in data.get("models", {}).items():
        elo = record.get("public_elo")
        if elo is None:
            continue
        qs = []
        for s in record.get("steps") or []:
            d, sc = s.get("difficulty"), s.get("medium_score")
            if d is not None and sc is not None:
                qs.append((float(d), float(sc) >= PASS))
        for t in record.get("traces") or []:
            d, sc = t.get("question_difficulty_target"), t.get("grade_expected_score")
            if d is not None and sc is not None:
                qs.append((float(d), float(sc) >= PASS))
        if len(qs) >= 4:
            out[name] = (float(elo), qs)
    return out


def within_auc(qs):
    """AUC of rated difficulty predicting FAILURE within one candidate."""
    fail = [d for d, p in qs if not p]
    ok = [d for d, p in qs if p]
    if not fail or not ok:
        return None
    wins = ties = 0
    for f in fail:
        for o in ok:
            if f > o:
                wins += 1
            elif f == o:
                ties += 1
    return (wins + 0.5 * ties) / (len(fail) * len(ok))


def boundary(qs):
    """ML threshold: difficulty b maximizing agreement (pass below, fail above)."""
    cands = sorted({d for d, _ in qs})
    best_b, best_score = None, -1
    for i in range(len(cands) + 1):
        b = (
            cands[0] - 50
            if i == 0
            else cands[-1] + 50
            if i == len(cands)
            else (cands[i - 1] + cands[i]) / 2
        )
        score = sum(1 for d, p in qs if (p and d <= b) or (not p and d > b))
        if score > best_score:
            best_b, best_score = b, score
    return best_b


def spearman(a, b):
    n = len(a)
    ra = {v: i for i, v in enumerate(sorted(range(n), key=lambda i: a[i]))}
    def ranks(x):
        order = sorted(range(n), key=lambda i: x[i])
        r = [0.0] * n
        for i, ix in enumerate(order):
            r[ix] = i
        return r
    da, db = ranks(a), ranks(b)
    ma, mb = sum(da) / n, sum(db) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(da, db))
    den = math.sqrt(sum((x - ma) ** 2 for x in da) * sum((y - mb) ** 2 for y in db))
    return num / den if den else float("nan")


def loo_affine_res(x, y):
    res = []
    for i in range(len(x)):
        xs = [v for j, v in enumerate(x) if j != i]
        ys = [v for j, v in enumerate(y) if j != i]
        mx, my = st.mean(xs), st.mean(ys)
        vx = sum((v - mx) ** 2 for v in xs)
        b = sum((a - mx) * (c - my) for a, c in zip(xs, ys)) / vx if vx else 0
        a0 = my - b * mx
        res.append(a0 + b * x[i] - y[i])
    return res


print(
    f"{'examiner':<26} {'elo':>5} {'cands':>5} {'qs':>4} "
    f"{'within-AUC':>10} {'bound-rho':>9} {'LOO|res|':>8}  grading"
)
for label, elo, fn, note in SOURCES:
    path = EXP / fn
    if not path.is_file():
        print(f"{label:<26} {elo:>5}  file missing: {fn}")
        continue
    cand = extract(path)
    if len(cand) < 5:
        print(f"{label:<26} {elo:>5}  only {len(cand)} usable candidates")
        continue
    aucs, weights = [], []
    for _, qs in cand.values():
        a = within_auc(qs)
        if a is not None:
            aucs.append(a)
            weights.append(len(qs))
    wauc = sum(a * w for a, w in zip(aucs, weights)) / sum(weights)
    elos = [e for e, _ in cand.values()]
    bounds = [boundary(qs) for _, qs in cand.values()]
    rho = spearman(bounds, elos)
    res = loo_affine_res(bounds, elos)
    nq = sum(len(qs) for _, qs in cand.values())
    print(
        f"{label:<26} {elo:>5} {len(cand):>5} {nq:>4} "
        f"{wauc:>10.3f} {rho:>9.3f} {st.mean(abs(r) for r in res):>8.0f}  {note}"
    )

print(
    "\nwithin-AUC: examiner's own difficulty ranking predicting its own fails "
    "(0.5 = labels carry no local order). bound-rho: candidate boundaries vs "
    "public Elo. LOO|res|: boundary->Elo affine, leave-one-out, in Elo."
)

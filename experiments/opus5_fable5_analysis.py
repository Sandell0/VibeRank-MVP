"""Compare Opus 5 vs Fable 5 (and Fable 5.1, the distilled probes) on the
frozen domain bank: accuracy, tokens per solved item, per-family medians,
matched-item token ratios, and the hard-tail signature (mean/median,
tokens-vs-rung slope). Reads opus5_fable5_bank_data.json (new run) and
distilled_efficiency_data.json (Fable 5.1 + probes, same protocol).

    python -m experiments.opus5_fable5_analysis
"""
from __future__ import annotations

import json
import math
from collections import defaultdict

import numpy as np

import experiments.domain_portfolio as dp

NEW = dp.EXP / "opus5_fable5_bank_data.json"
OLD = dp.EXP / "distilled_efficiency_data.json"
MUSE = dp.EXP / "muse13_bank_data.json"
SHOW = ["meta/muse-spark-1.3", "anthropic/claude-opus-5", "anthropic/claude-fable-5", "anthropic/claude-fable-5.1",
        "openai/gpt-5.4-mini", "anthropic/claude-haiku-4.5", "qwen/qwen3.6-35b-a3b"]
SKIP = {"toolsim"}


def load():
    ans = {}
    for path in (OLD, NEW, MUSE):
        if path.is_file():
            d = json.loads(path.read_text(encoding="utf-8"))
            for m, rec in d["responses"].items():
                ans.setdefault(m, {}).update({k: v for k, v in rec["answers"].items() if v.get("family") not in SKIP})
    return ans


def sign_test(wins, n):
    """two-sided exact binomial p for wins out of n at p=0.5"""
    k = min(wins, n - wins)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def main():
    ans = load()
    models = [m for m in SHOW if m in ans]
    print(f"{'model':30s} {'n':>3} {'meas':>4} {'acc':>5} {'cens':>4} {'solved':>6} {'mean':>7} {'median':>7} {'p90':>7} {'max':>7} {'mean/med':>8}")
    for m in models:
        a = list(ans[m].values())
        meas = [x for x in a if x.get("text") is not None]
        solved = [x["completion_tokens"] for x in a if x.get("correct") and x.get("completion_tokens")]
        if not solved:
            print(f"{m:30s} {len(a):3d} {len(meas):4d}   -  {len(a)-len(meas):4d}  (no solved cells yet)"); continue
        s = np.array(solved, float)
        print(f"{m:30s} {len(a):3d} {len(meas):4d} {sum(x['correct'] for x in meas)/max(1,len(meas)):5.2f} {len(a)-len(meas):4d} {len(solved):6d} {s.mean():7,.0f} {np.median(s):7,.0f} {np.percentile(s,90):7,.0f} {s.max():7,.0f} {s.mean()/np.median(s):8.2f}")

    fams = sorted({x["family"] for m in models for x in ans[m].values()})
    print(f"\nper family: solved/n and median ctok per solved item")
    print(f"{'family':10s}" + "".join(f"{m.split('/')[-1]:>22s}" for m in models))
    for f in fams:
        row = f"{f:10s}"
        for m in models:
            cells = [x for x in ans[m].values() if x["family"] == f]
            sol = [x["completion_tokens"] for x in cells if x.get("correct") and x.get("completion_tokens")]
            row += f"{(str(len(sol)) + '/' + str(len(cells))):>9s} {np.median(sol) if sol else 0:>12,.0f}"
        print(row)

    # matched items: solved by both
    pairs = [("meta/muse-spark-1.3", "anthropic/claude-fable-5.1"), ("meta/muse-spark-1.3", "anthropic/claude-opus-5"), ("meta/muse-spark-1.3", "openai/gpt-5.4-mini"), ("anthropic/claude-opus-5", "anthropic/claude-fable-5"), ("anthropic/claude-opus-5", "anthropic/claude-fable-5.1"), ("anthropic/claude-fable-5", "anthropic/claude-fable-5.1")]
    print("\nmatched items solved by both: median ratio of tokens (A/B), share of items where A used more, sign-test p")
    for a, b in pairs:
        if a not in ans or b not in ans: continue
        ids = [i for i in ans[a] if i in ans[b] and ans[a][i].get("correct") and ans[b][i].get("correct") and ans[a][i].get("completion_tokens") and ans[b][i].get("completion_tokens")]
        if len(ids) < 3: print(f"  {a.split('/')[-1]} vs {b.split('/')[-1]}: {len(ids)} matched items"); continue
        ratios = np.array([ans[a][i]["completion_tokens"] / ans[b][i]["completion_tokens"] for i in ids])
        wins = int((ratios > 1).sum())
        print(f"  {a.split('/')[-1]:12s} vs {b.split('/')[-1]:12s} n={len(ids):2d}  median ratio {np.median(ratios):.2f}  A-more {wins}/{len(ids)}  p={sign_test(wins, len(ids)):.3f}  geo-mean ratio {math.exp(np.mean(np.log(ratios))):.2f}")

    # tokens vs rung within family (log-linear slope), hard tail
    print("\nlog(tokens/solved) vs rung slope per family (positive = cost climbs with difficulty; steeper = closer to ceiling)")
    print(f"{'family':10s}" + "".join(f"{m.split('/')[-1]:>16s}" for m in models))
    for f in fams:
        row = f"{f:10s}"
        for m in models:
            pts = [(x["rung"], x["completion_tokens"]) for x in ans[m].values() if x["family"] == f and x.get("correct") and x.get("completion_tokens") and isinstance(x.get("rung"), (int, float))]
            if len(pts) >= 3 and len({r for r, _ in pts}) >= 2:
                r = np.array([p[0] for p in pts], float); t = np.log(np.array([p[1] for p in pts], float))
                row += f"{np.polyfit(r, t, 1)[0]:>16.2f}"
            else:
                row += f"{'-':>16s}"
        print(row)


if __name__ == "__main__":
    main()

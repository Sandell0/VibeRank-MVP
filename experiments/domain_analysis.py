"""Analysis: fresh multi-domain verifiable bank vs the frontier band.

Verdict inputs: (a) per-model/family table by wave; (b) in-band rho of the
fresh basket vs budget-unified Elo AND vs the public-board LOO consensus
(Check-2 target, no Elo in the loop); (c) family factor structure at pinned
effort incl. the inv grind anchor; (d) drop-one sensitivity on everything.
"""
import json
from pathlib import Path

import numpy as np

VR = Path(r"C:\Projects\VibeRank-MVP\experiments")
ROOT = Path(r"C:\Projects\llm-leaderboard")

ELO = {
    "openai/gpt-oss-120b": 1665, "moonshotai/kimi-k2-0905": 1722,
    "openai/gpt-5.2": 1818, "moonshotai/kimi-k2.6": 1835,
    "qwen/qwen3.6-plus": 1814, "deepseek/deepseek-v4-pro": 1836,
    "openai/gpt-5.4": 1881, "anthropic/claude-opus-4.8": 1934,
    "openai/gpt-5.5": 1937,
}
SLUG2SITE = {
    "openai/gpt-5.2": "GPT-5.2", "qwen/qwen3.6-plus": "Qwen 3.6 Plus",
    "deepseek/deepseek-v4-pro": "DeepSeek V4 Pro", "moonshotai/kimi-k2.6": "Kimi K2.6",
    "openai/gpt-5.4": "GPT-5.4", "anthropic/claude-opus-4.8": "Claude Opus 4.8",
    "openai/gpt-5.5": "GPT-5.5",
}
BAND = list(SLUG2SITE)


def spearman(x, y):
    rx = np.argsort(np.argsort(x)); ry = np.argsort(np.argsort(y))
    if np.std(rx) == 0 or np.std(ry) == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


bank = {i["id"]: i for i in json.loads((VR / "domain_portfolio_bank.json").read_text(encoding="utf-8"))}
data = json.loads((VR / "domain_portfolio_data.json").read_text(encoding="utf-8"))
FAMS = sorted({i["family"] for i in bank.values()})
MODELS = list(ELO)

import re as _re


def censored(item, a):
    """Uncorrectable-by-budget cell: wrong AND no parseable answer even after
    the 120k rerun (provider output ceiling / glitch), i.e. unmeasurable."""
    if a["correct"]:
        return False
    got = a.get("extracted")
    if got is None:
        return True
    return item["kind"] == "number" and _re.sub(r"[^\d]", "", got) == ""


print("=== per-model accuracy (censored = no answer at any served budget) ===")
acc_all, acc_w2 = {}, {}
for m in MODELS:
    ans = data["responses"][m]["answers"]
    cens = {iid for iid, a in ans.items() if censored(bank[iid], a)}
    meas = {iid: a for iid, a in ans.items() if iid not in cens}
    w3 = [a["correct"] for iid, a in meas.items() if "-w3" in iid]
    acc_all[m] = np.mean([a["correct"] for a in meas.values()])
    acc_w2[m] = np.mean(w3) if w3 else float("nan")
    print(f"  {m:32s} measurable {sum(a['correct'] for a in meas.values()):2d}"
          f"/{len(meas)}  censored {len(cens)}  w3 {sum(w3):2d}/{len(w3)}  "
          f"all {acc_all[m]:.2f}")
print("(acc_w2 slot below now holds wave-3 measurable accuracy)")

print("\n=== per-family accuracy (all waves) ===")
fam_acc = {}
for m in MODELS:
    ans = data["responses"][m]["answers"]
    fam_acc[m] = {}
    for f in FAMS:
        xs = [a["correct"] for iid, a in ans.items() if bank[iid]["family"] == f]
        fam_acc[m][f] = np.mean(xs) if xs else float("nan")
hdr = "  ".join(f"{f[:8]:>8s}" for f in FAMS)
print(f"  {'model':32s} {hdr}")
for m in MODELS:
    row = "  ".join(f"{fam_acc[m][f]:8.2f}" for f in FAMS)
    print(f"  {m:32s} {row}")

# board consensus target (Check-2 construction, budget-unified)
scores = json.load(open(ROOT / "data" / "unified-scores-budget-unified.json", encoding="utf-8"))
by_model = {r["model"]: r["benchmarks"] for r in scores if r["model"] in SLUG2SITE.values()}
sites = [SLUG2SITE[m] for m in BAND]
names = set(by_model[sites[0]])
for s in sites[1:]:
    names &= set(by_model[s])
Z = {}
for b in sorted(names):
    v = np.array([by_model[s][b]["percentile"] for s in sites], float)
    if np.ptp(v) > 0:
        Z[b] = (v - v.mean()) / v.std()
consensus = np.mean(list(Z.values()), axis=0)

elos = np.array([ELO[m] for m in BAND], float)
for label, accd in (("fresh bank ALL items", acc_all), ("fresh bank wave-2 only", acc_w2)):
    v = np.array([accd[m] for m in BAND], float)
    print(f"\n=== {label} (band-7) ===")
    print(f"  accuracies: " + "  ".join(f"{m.split('/')[-1]}={accd[m]:.2f}" for m in BAND))
    print(f"  rho vs Elo (budget-unified): {spearman(v, elos):+.2f}")
    print(f"  rho vs board LOO consensus:  {spearman(v, consensus):+.2f}")
    print("  drop-one vs consensus: ", end="")
    outs = []
    for i, m in enumerate(BAND):
        keep = [j for j in range(7) if j != i]
        outs.append(f"{m.split('/')[-1]}:{spearman(v[keep], consensus[keep]):+.2f}")
    print("  ".join(outs))

print("\n=== family factor structure (band-7, both waves, pinned effort) ===")
mat = np.array([[fam_acc[m][f] for f in FAMS] for m in BAND])
k = len(FAMS)
corr = np.eye(k)
for i in range(k):
    for j in range(i + 1, k):
        a, b = mat[:, i], mat[:, j]
        if np.nanstd(a) == 0 or np.nanstd(b) == 0:
            c = np.nan
        else:
            c = float(np.corrcoef(a, b)[0, 1])
        corr[i, j] = corr[j, i] = c
off = corr[np.triu_indices(k, 1)]
cfix = np.nan_to_num(corr, nan=float(np.nanmean(off)))
np.fill_diagonal(cfix, 1.0)
vals, vecs = np.linalg.eigh(cfix)
order = np.argsort(vals)[::-1]
print(f"  lambda1 share {vals[order[0]]/vals.sum():.1%}   mean off-diag r {np.nanmean(off):+.2f}")
pc1 = vecs[:, order[0]]
if pc1.sum() < 0:
    pc1 = -pc1
print("  PC1 loadings:", {f: round(float(l), 2) for f, l in zip(FAMS, pc1)})
print("  per-family rho vs Elo (band):",
      {f: round(spearman(mat[:, i], elos), 2) for i, f in enumerate(FAMS)})
print("  per-family rho vs consensus: ",
      {f: round(spearman(mat[:, i], consensus), 2) for i, f in enumerate(FAMS)})

# usage + cost snapshot
tot_p = sum(u["prompt"] for u in data["usage"].values())
tot_c = sum(u["completion"] for u in data["usage"].values())
print(f"\nusage: {tot_p:,} prompt + {tot_c:,} completion tokens")

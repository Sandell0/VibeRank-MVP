"""Check 1: factor structure of the 7-family verifiable bank.

H2 (aggregates-track-aggregates) predicts the 7 planted-key families are
effectively ONE factor: dominant lambda-1 share, all-positive PC1 loadings.
Rival (content story) allows multi-factor structure whose combinations still
fail to predict in-band Elo.
"""
import json
import random
from pathlib import Path

import numpy as np

EXP = Path(r"C:\Projects\VibeRank-MVP\experiments")

ELO = {  # budget-unified site Elo (unified-leaderboard-budget-unified.json, 2026-08-30)
    "openai/gpt-oss-120b": 1665,
    "moonshotai/kimi-k2-0905": 1722,
    "openai/gpt-5.2": 1818,
    "moonshotai/kimi-k2.6": 1835,
    "qwen/qwen3.6-plus": 1814,
    "deepseek/deepseek-v4-pro": 1836,
    "openai/gpt-5.4": 1881,
    "anthropic/claude-opus-4.8": 1934,
    "openai/gpt-5.5": 1937,
}
BAND7 = [m for m in ELO if m not in ("openai/gpt-oss-120b", "moonshotai/kimi-k2-0905")]

front = json.load(open(EXP / "frontier_ladder_data.json"))["responses"]
port = json.load(open(EXP / "portfolio_ladder_data.json"))["responses"]

# outcomes[model][item_id] = 0/1, item ids prefixed by source to stay unique
outcomes = {m: {} for m in ELO}
fam_items = {}  # family -> sorted list of item ids
for src, tag in ((front, "F:"), (port, "P:")):
    for m, v in src.items():
        if m not in outcomes:
            continue
        for iid, a in v.get("answers", {}).items():
            fam = iid.split("-")[0]
            qid = tag + iid
            outcomes[m][qid] = 1 if a.get("correct") else 0
            fam_items.setdefault(fam, set()).add(qid)
fam_items = {f: sorted(s) for f, s in fam_items.items()}
FAMS = sorted(fam_items)

print("items per family:", {f: len(v) for f, v in fam_items.items()})
print("\nanswered per model per family:")
for m in ELO:
    row = {f: sum(1 for i in fam_items[f] if i in outcomes[m]) for f in FAMS}
    print(f"  {m:35s} {row}")


def fam_acc(model, fam, items=None):
    ids = [i for i in (items or fam_items[fam]) if i in outcomes[model]]
    if not ids:
        return np.nan
    return float(np.mean([outcomes[model][i] for i in ids]))


def acc_matrix(models, boot_items=None):
    """models x families accuracy matrix."""
    return np.array(
        [[fam_acc(m, f, boot_items[f] if boot_items else None) for f in FAMS] for m in models]
    )


def corr_stats(mat):
    """Pairwise-complete Pearson corr of family columns; return (corr, lam1_share, mean_offdiag, pc1_loadings)."""
    k = mat.shape[1]
    corr = np.eye(k)
    for i in range(k):
        for j in range(i + 1, k):
            mask = ~np.isnan(mat[:, i]) & ~np.isnan(mat[:, j])
            a, b = mat[mask, i], mat[mask, j]
            if len(a) < 3 or a.std() == 0 or b.std() == 0:
                c = np.nan
            else:
                c = float(np.corrcoef(a, b)[0, 1])
            corr[i, j] = corr[j, i] = c
    off = corr[np.triu_indices(k, 1)]
    cfix = np.nan_to_num(corr, nan=np.nanmean(off))
    np.fill_diagonal(cfix, 1.0)
    vals, vecs = np.linalg.eigh(cfix)
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    lam1 = float(vals[0] / vals.sum())
    pc1 = vecs[:, 0]
    if pc1.sum() < 0:
        pc1 = -pc1
    return corr, lam1, float(np.nanmean(off)), pc1


def spearman(x, y):
    rx, ry = np.argsort(np.argsort(x)), np.argsort(np.argsort(y))
    return float(np.corrcoef(rx, ry)[0, 1])


for label, models in (("ALL-9", list(ELO)), ("BAND-7", BAND7),
                      ("BAND-6 (no k2.6)", [m for m in BAND7 if "k2.6" not in m])):
    mat = acc_matrix(models)
    corr, lam1, moff, pc1 = corr_stats(mat)
    print(f"\n=== {label} ===")
    print("  family accuracy matrix:")
    for m, row in zip(models, mat):
        print(f"    {m:35s}", " ".join(f"{v:.2f}" if not np.isnan(v) else "  - " for v in row))
    print("  lambda1 share = {:.1%}   mean off-diag r = {:+.2f}".format(lam1, moff))
    print("  PC1 loadings:", {f: round(float(l), 2) for f, l in zip(FAMS, pc1)})
    # PC1 model scores vs Elo
    z = (mat - np.nanmean(mat, 0)) / np.where(np.nanstd(mat, 0) == 0, 1, np.nanstd(mat, 0))
    z = np.nan_to_num(z)
    pc1_scores = z @ pc1
    elos = np.array([ELO[m] for m in models])
    print(f"  spearman(PC1 score, Elo) = {spearman(pc1_scores, elos):+.2f}")
    if lam1 < 0.999:
        _, vecs = None, None  # PC2 check
        cfix = np.nan_to_num(corr, nan=moff); np.fill_diagonal(cfix, 1.0)
        vals2, vecs2 = np.linalg.eigh(cfix)
        o = np.argsort(vals2)[::-1]
        pc2 = vecs2[:, o[1]]
        print(f"  spearman(PC2 score, Elo) = {spearman(z @ pc2, elos):+.2f}   (lam2 share {vals2[o[1]]/vals2.sum():.1%})")

# bootstrap over items (within family) for ALL-9 and BAND-7
rng = random.Random(20260830)
for label, models in (("ALL-9", list(ELO)), ("BAND-7", BAND7)):
    l1s, moffs = [], []
    for _ in range(1000):
        bi = {f: [rng.choice(fam_items[f]) for _ in fam_items[f]] for f in FAMS}
        mat = acc_matrix(models, bi)
        try:
            _, lam1, moff, _ = corr_stats(mat)
            l1s.append(lam1); moffs.append(moff)
        except Exception:
            pass
    l1s.sort(); moffs.sort()
    n = len(l1s)
    print(f"\nbootstrap {label} (n={n}): lambda1 share {l1s[n//2]:.1%} [{l1s[int(n*.05)]:.1%}, {l1s[int(n*.95)]:.1%}]"
          f"   mean off-diag r {moffs[n//2]:+.2f} [{moffs[int(n*.05)]:+.2f}, {moffs[int(n*.95)]:+.2f}]")

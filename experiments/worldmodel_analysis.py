"""Analysis for the world-model smoke: recall gradient + retrocast Brier.

Recall: per-tier accuracy (famous/mid/obscure), band spread, bootstrap
ordering stability. Retro: KNOW-pass leakage exclusion per model, then
Brier vs baselines. Cross-axis correlation = multi-dimensionality check.
"""
import json
import random
import re
from pathlib import Path

import numpy as np

EXP = Path(__file__).resolve().parent

ELO = {  # budget-unified, 2026-08-30
    "openai/gpt-oss-120b": 1665, "moonshotai/kimi-k2-0905": 1722,
    "openai/gpt-5.2": 1818, "moonshotai/kimi-k2.6": 1835,
    "qwen/qwen3.6-plus": 1814, "deepseek/deepseek-v4-pro": 1836,
    "openai/gpt-5.4": 1881, "anthropic/claude-opus-4.8": 1934,
    "openai/gpt-5.5": 1937,
    "anthropic/claude-fable-5": 2037,  # above-band probes, not in band metrics
    "anthropic/claude-opus-5": 2060,
}
ABOVE_BAND = {"anthropic/claude-fable-5", "anthropic/claude-opus-5"}
BAND = [m for m in ELO if ELO[m] >= 1800 and m not in ABOVE_BAND]

BAD_ITEMS = {  # extractor junk, excluded from scoring
    "recall-mid-155-1": "key is 'my servant', not a name",
    "recall-obscure-60432-0": "extractor confused author with Empress",
}

bank = {i["id"]: i for i in json.loads((EXP / "worldmodel_smoke_bank.json").read_text(encoding="utf-8"))}
data = json.loads((EXP / "worldmodel_smoke_data.json").read_text(encoding="utf-8"))
MODELS = list(ELO)


def spearman(x, y):
    rx = np.argsort(np.argsort(x)); ry = np.argsort(np.argsort(y))
    if np.std(rx) == 0 or np.std(ry) == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


# ---------------- recall ----------------
recall_ids = [i for i in bank if bank[i]["family"] == "recall" and i not in BAD_ITEMS]
tiers = ("famous", "mid", "obscure")
print(f"=== A. long-tail recall ({len(recall_ids)} items after excluding "
      f"{len(BAD_ITEMS)} junk) ===")
print(f"  {'model':32s} {'all':>5} " + " ".join(f"{t:>8}" for t in tiers))
recall_acc = {}
for m in MODELS:
    r = data["responses"][m]
    accs = {}
    for t in tiers:
        ids = [i for i in recall_ids if bank[i]["tier"] == t]
        accs[t] = np.mean([r[i]["correct"] for i in ids if i in r]) if ids else np.nan
    all_ids = [i for i in recall_ids if i in r]
    recall_acc[m] = np.mean([r[i]["correct"] for i in all_ids])
    print(f"  {m:32s} {recall_acc[m]:5.2f} " + " ".join(f"{accs[t]:8.2f}" for t in tiers))

# per-item solve counts (spot junk / too-easy)
print("\n  items by solve count (n/9):")
counts = {}
for i in recall_ids:
    c = sum(1 for m in MODELS if data["responses"][m].get(i, {}).get("correct"))
    counts.setdefault(c, []).append(i)
for c in sorted(counts):
    print(f"    {c}/9: {len(counts[c])} items" +
          (f"  e.g. {counts[c][:3]}" if c in (0, 9) else ""))

# band spread + bootstrap ordering stability
rng = random.Random(20260831)
band_acc = np.array([recall_acc[m] for m in BAND])
print(f"\n  band-7 accuracies: " +
      "  ".join(f"{m.split('/')[-1]}={recall_acc[m]:.2f}" for m in BAND))
print(f"  band spread (max-min): {band_acc.max()-band_acc.min():.2f}")
elos = np.array([ELO[m] for m in BAND])
print(f"  rho vs Elo (band-7, n=7 caution): {spearman(band_acc, elos):+.2f}")
boots = []
for _ in range(500):
    ids = [rng.choice(recall_ids) for _ in recall_ids]
    accs = [np.mean([data["responses"][m].get(i, {}).get("correct", False) for i in ids])
            for m in BAND]
    boots.append(spearman(np.array(accs), band_acc))
print(f"  bootstrap self-agreement of band ordering: median "
      f"{np.median(boots):+.2f} [{np.percentile(boots,5):+.2f}, {np.percentile(boots,95):+.2f}]")

# ---------------- retro ----------------
retro_ids = [i for i in bank if bank[i]["family"] == "retro"]
print(f"\n=== B. retrocast ({len(retro_ids)} questions) ===")


def parse_prob(s):
    if s is None:
        return None
    s = s.strip().rstrip(".")
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", s)
    if m:
        return float(m.group(1)) / 100
    m = re.search(r"\d*\.\d+|\b[01]\b", s)
    if m:
        v = float(m.group(0))
        return v if v <= 1 else None
    return None


print(f"  {'model':32s} {'Brier':>6} {'N':>3} {'excl':>4} {'know-acc':>8} {'commit':>6} {'|p-.5|':>6}")
briers = {}
for m in MODELS:
    r = data["responses"][m]
    excluded, pts = 0, []
    know_correct = know_commit = 0
    for i in retro_ids:
        res = 1.0 if bank[i]["resolution"] == "YES" else 0.0
        know = (r.get(i + ":know", {}).get("extracted") or "").upper()
        committed = know.startswith(("YES", "NO"))
        if committed:
            know_commit += 1
            if (know.startswith("YES")) == (res == 1.0):
                know_correct += 1
                excluded += 1     # model may already know the outcome
                continue
        p = parse_prob(r.get(i + ":forecast", {}).get("extracted"))
        if p is None:
            continue
        pts.append((p, res))
    if pts:
        b = float(np.mean([(p - y) ** 2 for p, y in pts]))
        briers[m] = b
        dec = float(np.mean([abs(p - 0.5) for p, _ in pts]))
        ka = know_correct / know_commit if know_commit else float("nan")
        print(f"  {m:32s} {b:6.3f} {len(pts):3d} {excluded:4d} {ka:8.2f} "
              f"{know_commit:6d} {dec:6.2f}")

ys = [1.0 if bank[i]["resolution"] == "YES" else 0.0 for i in retro_ids]
base = float(np.mean(ys))
print(f"\n  baselines: always-0.5 Brier = 0.250; base-rate ({base:.2f}) Brier = "
      f"{float(np.mean([(base - y) ** 2 for y in ys])):.3f}")
bb = np.array([briers[m] for m in BAND if m in briers])
print(f"  band-7 Brier spread (max-min): {bb.max()-bb.min():.3f}")
print(f"  rho Brier vs Elo (band, lower better so negated): "
      f"{spearman(-np.array([briers[m] for m in BAND if m in briers]), np.array([ELO[m] for m in BAND if m in briers])):+.2f}")

# ---------------- cross-axis ----------------
common = [m for m in MODELS if m in briers]
ra = np.array([recall_acc[m] for m in common])
rb = -np.array([briers[m] for m in common])  # higher = better
print(f"\n=== cross-axis (all 9): spearman(recall, retro-skill) = {spearman(ra, rb):+.2f} ===")
print("  (low correlation in-band = the axes measure different things)")

tot_c = sum(u["completion"] for u in data["usage"].values())
tot_p = sum(u["prompt"] for u in data["usage"].values())
print(f"\nusage: {tot_p:,} prompt + {tot_c:,} completion tokens")

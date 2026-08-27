"""Pilot readout: err(k) trend, evaluator-bias structure, measured cost.

Go/no-go for the full 30-model experiment:
  GO if (1) the ladder stayed coherent to k=25, (2) ensemble |deviation|
  keeps falling past k=10, (3) grader deviations are model-specific rather
  than shared (so ensembling diverse evaluators attacks the tau floor),
  (4) measured spend is within ~1.5x of the projection.

n=5 models: every number here is directional, not final. The pilot's job is
to identify show-stoppers, not to estimate tau precisely.

    python -m experiments.pilot_analysis
"""
from __future__ import annotations

import json
import math
import statistics as st
from pathlib import Path

EXP = Path(__file__).resolve().parent
deep = json.loads((EXP / "pilot_deep_data.json").read_text(encoding="utf-8"))
reg = json.loads((EXP / "pilot_regrade_data.json").read_text(encoding="utf-8"))

PRICES = {
    "author": (5.0, 30.0),
    "steer": (1.5, 7.5),
    "target": (0.5, 2.0),
    "anthropic/claude-opus-4.8": (5.0, 25.0),
    "qwen/qwen3.7-max": (0.8, 3.2),
    "deepseek/deepseek-v4-pro": (0.6, 2.0),
}
CHECKPOINTS = ("5", "10", "15", "20", "25")

models = deep["models"]
truths = {m: r["public_elo"] for m, r in models.items()}
graders = sorted({g for m in reg["reads"].values() for g in m})

# ---------- err(k): per grader and ensemble ----------
print("=== |deviation| vs public Elo by prefix length (mean over models) ===")
hdr = f"{'grader':<28}" + "".join(f"  k={k:>2}" for k in CHECKPOINTS)
print(hdr)
ens = {k: {} for k in CHECKPOINTS}
for g in graders:
    line = f"{g.split('/')[-1]:<28}"
    for k in CHECKPOINTS:
        devs = []
        for m in reg["reads"]:
            read = reg["reads"][m].get(g, {}).get(k)
            if read and m in truths:
                devs.append(read["mean_elo"] - truths[m])
                ens[k].setdefault(m, []).append(read["mean_elo"])
        line += f"  {st.mean(abs(d) for d in devs):5.0f}" if devs else "      -"
    print(line)
line = f"{'ENSEMBLE (mean of graders)':<28}"
for k in CHECKPOINTS:
    devs = [st.mean(v) - truths[m] for m, v in ens[k].items() if len(v) == len(graders)]
    line += f"  {st.mean(abs(d) for d in devs):5.0f}" if devs else "      -"
print(line)

verd = {m: r["verdict"]["mean_elo"] for m, r in models.items() if r.get("verdict")}
if verd:
    devs = [verd[m] - truths[m] for m in verd]
    print(f"{'Sol interviewer verdict':<28}  k=25: mean|dev|={st.mean(abs(d) for d in devs):.0f}")

# ---------- bias structure: shared vs model-specific ----------
print("\n=== evaluator-bias structure at k=25 (does ensembling help?) ===")
shared_sq, specific_sq = [], []
for m in reg["reads"]:
    reads = [reg["reads"][m][g].get("25", {}).get("mean_elo") for g in graders if g in reg["reads"][m]]
    reads = [r for r in reads if r is not None]
    if len(reads) < 2 or m not in truths:
        continue
    devs = [r - truths[m] for r in reads]
    shared = st.mean(devs)
    shared_sq.append(shared**2)
    specific_sq.extend((d - shared) ** 2 for d in devs)
if shared_sq and specific_sq:
    rms_shared = math.sqrt(st.mean(shared_sq))
    rms_spec = math.sqrt(st.mean(specific_sq))
    print(f"rms shared deviation (all graders agree, wrong together): {rms_shared:.0f} Elo")
    print(f"rms grader-specific deviation (averages out in ensemble): {rms_spec:.0f} Elo")
    print(
        "reading: specific >> shared -> diverse ensembling cuts the floor; "
        "shared >> specific -> the floor is in the transcripts, not the readers"
    )

# ---------- ladder coherence ----------
print("\n=== ladder coherence (difficulty trajectories) ===")
for m, r in models.items():
    ds = [s["difficulty"] for s in r.get("steps", [])]
    if ds:
        print(f"{m[:36]:<36} n={len(ds):>2} d: {ds[0]:.0f} -> {max(ds):.0f} max, {ds[-1]:.0f} last")

# ---------- measured cost ----------
print("\n=== measured spend ===")
total = 0.0
au = deep.get("author_usage", {})
if au:
    c = au.get("prompt", 0) / 1e6 * PRICES["author"][0] + au.get("completion", 0) / 1e6 * PRICES["author"][1]
    total += c
    print(f"author (Sol): {au.get('prompt', 0):,} in / {au.get('completion', 0):,} out = ${c:.2f}")
su = deep.get("steer_usage", {})
if su:
    c = su.get("prompt", 0) / 1e6 * PRICES["steer"][0] + su.get("completion", 0) / 1e6 * PRICES["steer"][1]
    total += c
    print(f"steering (medium): ${c:.2f}")
tin = sum(r.get("target_usage", {}).get("prompt", 0) for r in models.values())
tout = sum(r.get("target_usage", {}).get("completion", 0) for r in models.values())
c = tin / 1e6 * PRICES["target"][0] + tout / 1e6 * PRICES["target"][1]
total += c
print(f"targets: {tin:,} in / {tout:,} out = ${c:.2f}")
for g, u in reg.get("usage", {}).items():
    pin, pout = PRICES.get(g, (1.0, 4.0))
    c = u.get("prompt", 0) / 1e6 * pin + u.get("completion", 0) / 1e6 * pout
    total += c
    print(f"grader {g.split('/')[-1]}: ${c:.2f}")
n = len([m for m in models.values() if m.get("verdict")])
if n:
    print(f"TOTAL ~${total:.2f} for {n} models  ->  projected 30-model full run: ~${total / n * 30:.0f}")

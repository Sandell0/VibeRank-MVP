# Day-one battery: nvidia/nemotron-3.5-lightning:free

Generated 2026-09-02T01:09:19+00:00.
Catalog: NVIDIA: Nemotron 3.5 Lightning (free) - listed 2026-08-11, ctx 1000000, max out 65536, reasoning param, $0.00/$0.00 per M.

## Dossier draft

**NVIDIA: Nemotron 3.5 Lightning (free)** (nvidia/nemotron-3.5-lightning:free) - recall 0.18 (famous+mid 0.26, obscure 0.00; #15/16 on file, nearest gpt-oss-120b 0.21, kimi-k2-0905 0.24); retro-today Brier 0.263 vs base rate 0.198 (n=22, |p-.5| 0.27, 1 correct commits on the scored set); domain bank 50/55 measurable (25 censored, median 2590 ctok/solved, effort on); frontier ladder 8/8, 16 unattempted; portfolio ladder 1/1, 29 unattempted

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.18 | 0.25 | 0.27 | 0.00 | 0.26 | 15/16 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 22/22 | 0.263 | 0.198 | 0.64 | 0.27 | 4 (3) | 1 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 50/55 (0.91), censored 25, median 2590 / mean 5053 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 10 | 10 | 0 |
| bigknap | 0 | 1 | 4 |
| casework | 6 | 6 | 4 |
| inv | 0 | 0 | 7 |
| longctx | 7 | 7 | 3 |
| repobug | 10 | 10 | 0 |
| tableqa | 8 | 11 | 3 |
| toolsim | 9 | 10 | 4 |

## Frontier ladder (inversion/execution)

8/24 items attempted, 0 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 4 | 4 | 0 |
| inversion | 4 | 4 | 0 |
| all | 8 | 8 | 0 |

## Portfolio ladder (five families)

1/30 items attempted, 0 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| zebra | 1 | 1 | 0 |
| all | 1 | 1 | 0 |

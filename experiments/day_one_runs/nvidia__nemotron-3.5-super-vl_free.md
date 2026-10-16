# Day-one battery: nvidia/nemotron-3.5-super-vl:free

Generated 2026-10-16T02:02:25+00:00.
Catalog: NVIDIA: Nemotron 3.5 Super VL (free) - listed 2026-10-15, ctx 1000000, max out 131072, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 296 requests, 0 429 retries, 0 max_tokens clamps, 6.8 min paced |
| _elapsed | 115 min |

## Dossier draft

**NVIDIA: Nemotron 3.5 Super VL (free)** (nvidia/nemotron-3.5-super-vl:free) - recall 0.29 (famous+mid 0.43, obscure 0.00; #12/42 on file, nearest gpt-5.4-mini 0.29, qwen3.6-35b-a3b 0.29); retro-today Brier 0.284 vs base rate 0.198 (n=22, |p-.5| 0.28, 0 correct commits on the scored set); domain bank 71/74 measurable (6 censored, median 1513 ctok/solved, effort on); frontier ladder 22/24; portfolio ladder 25/27, 3 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.29 | 0.50 | 0.36 | 0.00 | 0.43 | 12/42 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 22/22 | 0.284 | 0.198 | 0.64 | 0.28 | 5 (1) | 0 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 71/74 (0.96), censored 6, median 1513 / mean 4031 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 9 | 9 | 1 |
| bigknap | 0 | 0 | 5 |
| casework | 10 | 10 | 0 |
| inv | 5 | 7 | 0 |
| longctx | 10 | 10 | 0 |
| repobug | 10 | 10 | 0 |
| tableqa | 14 | 14 | 0 |
| toolsim | 13 | 14 | 0 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 0 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 11 | 12 | 0 |
| inversion | 11 | 12 | 0 |
| all | 22 | 24 | 0 |

## Portfolio ladder (five families)

30/30 items attempted, 3 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 6 | 6 | 0 |
| docfact | 5 | 6 | 0 |
| knapsack | 3 | 3 | 3 |
| spec | 5 | 6 | 0 |
| zebra | 6 | 6 | 0 |
| all | 25 | 27 | 3 |

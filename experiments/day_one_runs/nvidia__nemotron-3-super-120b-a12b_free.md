# Day-one battery: nvidia/nemotron-3-super-120b-a12b:free

Generated 2026-09-25T11:29:54+00:00.
Catalog: NVIDIA: Nemotron 3 Super (free) - listed 2026-03-11, ctx 262144, max out 235929, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 105 requests, 1 429 retries, 0 max_tokens clamps, 1.5 min paced |
| _elapsed | 28 min |

## Dossier draft

**NVIDIA: Nemotron 3 Super (free)** (nvidia/nemotron-3-super-120b-a12b:free) - recall 0.26 (famous+mid 0.39, obscure 0.00; #16/39 on file, nearest kimi-k2-0905 0.24, qwen3.6-plus 0.24); retro-today Brier 0.289 vs base rate 0.198 (n=22, |p-.5| 0.34, 1 correct commits on the scored set); domain bank 65/71 measurable (9 censored, median 1177 ctok/solved, effort on); frontier ladder 20/24; portfolio ladder 18/27, 3 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.26 | 0.50 | 0.27 | 0.00 | 0.39 | 16/39 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 22/22 | 0.289 | 0.198 | 0.64 | 0.34 | 6 (4) | 1 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 65/71 (0.92), censored 9, median 1177 / mean 4276 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 10 | 10 | 0 |
| bigknap | 0 | 1 | 4 |
| casework | 10 | 10 | 0 |
| inv | 4 | 7 | 0 |
| longctx | 9 | 9 | 1 |
| repobug | 10 | 10 | 0 |
| tableqa | 12 | 13 | 1 |
| toolsim | 10 | 11 | 3 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 0 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 10 | 12 | 0 |
| inversion | 10 | 12 | 0 |
| all | 20 | 24 | 0 |

## Portfolio ladder (five families)

30/30 items attempted, 3 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 4 | 4 | 2 |
| docfact | 5 | 6 | 0 |
| knapsack | 0 | 6 | 0 |
| spec | 4 | 6 | 0 |
| zebra | 5 | 5 | 1 |
| all | 18 | 27 | 3 |

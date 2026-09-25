# Day-one battery: poolside/laguna-s-2.1:free

Generated 2026-09-23T07:07:10+00:00.
Catalog: Poolside: Laguna S 2.1 (free) - listed 2026-07-21, ctx 262144, max out 32768, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 136 requests, 66 429 retries, 70 max_tokens clamps, 0.0 min paced |
| _elapsed | 455 min |

## Dossier draft

**Poolside: Laguna S 2.1 (free)** (poolside/laguna-s-2.1:free) - recall 0.06 (famous+mid 0.09, obscure 0.00; #24/28 on file, nearest lfm-2.5-2.6b:free 0.03, qwen3.8-27b:free 0.03); retro-today Brier 0.232 vs base rate 0.198 (n=22, |p-.5| 0.22, 5 correct commits on the scored set); domain bank 64/69 measurable (11 censored, median 1163 ctok/solved, effort on); frontier ladder 11/15, 9 censored; portfolio ladder 19/24, 6 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.06 | 0.08 | 0.09 | 0.00 | 0.09 | 24/28 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 22/22 | 0.232 | 0.198 | 0.64 | 0.22 | 12 (9) | 5 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 64/69 (0.93), censored 11, median 1163 / mean 2692 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 9 | 10 | 0 |
| bigknap | 0 | 0 | 5 |
| casework | 10 | 10 | 0 |
| inv | 3 | 4 | 3 |
| longctx | 10 | 10 | 0 |
| repobug | 10 | 10 | 0 |
| tableqa | 11 | 12 | 2 |
| toolsim | 11 | 13 | 1 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 9 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 5 | 7 | 5 |
| inversion | 6 | 8 | 4 |
| all | 11 | 15 | 9 |

## Portfolio ladder (five families)

30/30 items attempted, 6 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 6 | 6 | 0 |
| docfact | 5 | 6 | 0 |
| knapsack | 0 | 0 | 6 |
| spec | 2 | 6 | 0 |
| zebra | 6 | 6 | 0 |
| all | 19 | 24 | 6 |

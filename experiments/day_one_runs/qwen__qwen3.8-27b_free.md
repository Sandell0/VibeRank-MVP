# Day-one battery: qwen/qwen3.8-27b:free

Generated 2026-09-22T22:06:21+00:00.
Catalog: Qwen: Qwen3.8 27B (free) - listed 2026-08-14, ctx 262144, max out 235929, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 2349 requests, 1885 429 retries, 0 max_tokens clamps, 4.0 min paced |
| _elapsed | 726 min |

## Dossier draft

**Qwen: Qwen3.8 27B (free)** (qwen/qwen3.8-27b:free) - recall 0.03 (famous+mid 0.04, obscure 0.00; #24/27 on file, nearest lfm-2.5-2.6b:free 0.03, inkling-small:free 0.00); retro-today Brier 0.407 vs base rate 0.198 (n=7, |p-.5| 0.29, 1 correct commits on the scored set); domain bank 41/41 measurable (39 censored, median 765 ctok/solved, effort on); frontier ladder 9/9, 15 censored; portfolio ladder 24/24, 6 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.03 | 0.00 | 0.09 | 0.00 | 0.04 | 24/27 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 7/22 | 0.407 | 0.198 | 0.43 | 0.29 | 3 (2) | 1 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 41/41 (1.00), censored 39, median 765 / mean 2327 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 5 | 5 | 5 |
| bigknap | 0 | 0 | 5 |
| casework | 4 | 4 | 6 |
| inv | 1 | 1 | 6 |
| longctx | 8 | 8 | 2 |
| repobug | 6 | 6 | 4 |
| tableqa | 10 | 10 | 4 |
| toolsim | 7 | 7 | 7 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 15 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 4 | 4 | 8 |
| inversion | 5 | 5 | 7 |
| all | 9 | 9 | 15 |

## Portfolio ladder (five families)

30/30 items attempted, 6 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 6 | 6 | 0 |
| docfact | 4 | 4 | 2 |
| knapsack | 3 | 3 | 3 |
| spec | 5 | 5 | 1 |
| zebra | 6 | 6 | 0 |
| all | 24 | 24 | 6 |

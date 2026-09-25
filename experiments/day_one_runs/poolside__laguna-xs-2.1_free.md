# Day-one battery: poolside/laguna-xs-2.1:free

Generated 2026-09-23T13:06:42+00:00.
Catalog: Poolside: Laguna XS 2.1 (free) - listed 2026-07-02, ctx 262144, max out 32768, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 846 requests, 528 429 retries, 164 max_tokens clamps, 3.0 min paced |
| _elapsed | 360 min |

## Dossier draft

**Poolside: Laguna XS 2.1 (free)** (poolside/laguna-xs-2.1:free) - recall 0.09 (famous+mid 0.13, obscure 0.00; #23/29 on file, nearest claude-haiku-4.5 0.09, dots-3-note-preview:free 0.12); retro-today Brier 0.247 vs base rate 0.198 (n=22, |p-.5| 0.22, 3 correct commits on the scored set); domain bank 56/69 measurable (11 censored, median 1562 ctok/solved, effort on); frontier ladder 8/18, 6 censored; portfolio ladder 13/29, 1 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.09 | 0.17 | 0.09 | 0.00 | 0.13 | 23/29 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 22/22 | 0.247 | 0.198 | 0.59 | 0.22 | 15 (10) | 3 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 56/69 (0.81), censored 11, median 1562 / mean 2636 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 8 | 10 | 0 |
| bigknap | 1 | 4 | 1 |
| casework | 10 | 10 | 0 |
| inv | 0 | 0 | 7 |
| longctx | 7 | 10 | 0 |
| repobug | 10 | 10 | 0 |
| tableqa | 10 | 14 | 0 |
| toolsim | 10 | 11 | 3 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 6 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 6 | 12 | 0 |
| inversion | 2 | 6 | 6 |
| all | 8 | 18 | 6 |

## Portfolio ladder (five families)

30/30 items attempted, 1 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 3 | 6 | 0 |
| docfact | 4 | 6 | 0 |
| knapsack | 0 | 5 | 1 |
| spec | 1 | 6 | 0 |
| zebra | 5 | 6 | 0 |
| all | 13 | 29 | 1 |

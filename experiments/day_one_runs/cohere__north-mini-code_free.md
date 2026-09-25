# Day-one battery: cohere/north-mini-code:free

Generated 2026-09-23T20:04:27+00:00.
Catalog: Cohere: North Mini Code (free) - listed 2026-06-17, ctx 256000, max out 64000, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 315 requests, 0 429 retries, 0 max_tokens clamps, 1.0 min paced |
| _elapsed | 418 min |

## Dossier draft

**Cohere: North Mini Code (free)** (cohere/north-mini-code:free) - recall 0.09 (famous+mid 0.13, obscure 0.00; #23/30 on file, nearest claude-haiku-4.5 0.09, laguna-xs-2.1:free 0.09); retro-today Brier 0.368 vs base rate 0.198 (n=20, |p-.5| 0.29, 1 correct commits on the scored set); domain bank 65/67 measurable (13 censored, median 1758 ctok/solved, effort on); frontier ladder 16/19, 5 censored; portfolio ladder 19/21, 9 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.09 | 0.17 | 0.09 | 0.00 | 0.13 | 23/30 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 20/22 | 0.368 | 0.198 | 0.45 | 0.29 | 5 (4) | 1 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 65/67 (0.97), censored 13, median 1758 / mean 3113 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 10 | 10 | 0 |
| bigknap | 0 | 2 | 3 |
| casework | 10 | 10 | 0 |
| inv | 2 | 2 | 5 |
| longctx | 10 | 10 | 0 |
| repobug | 10 | 10 | 0 |
| tableqa | 9 | 9 | 5 |
| toolsim | 14 | 14 | 0 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 5 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 11 | 12 | 0 |
| inversion | 5 | 7 | 5 |
| all | 16 | 19 | 5 |

## Portfolio ladder (five families)

30/30 items attempted, 9 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 6 | 6 | 0 |
| docfact | 5 | 6 | 0 |
| knapsack | 1 | 1 | 5 |
| spec | 1 | 2 | 4 |
| zebra | 6 | 6 | 0 |
| all | 19 | 21 | 9 |

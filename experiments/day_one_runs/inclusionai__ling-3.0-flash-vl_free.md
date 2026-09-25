# Day-one battery: inclusionai/ling-3.0-flash-vl:free

Generated 2026-09-21T03:57:53+00:00.
Catalog: inclusionAI: Ling 3.0 Flash VL (free) - listed 2026-09-10, ctx 262144, max out 32768, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 1 requests, 0 429 retries, 1 max_tokens clamps, 0.0 min paced |
| _elapsed | 2 min |

## Dossier draft

**inclusionAI: Ling 3.0 Flash VL (free)** (inclusionai/ling-3.0-flash-vl:free) - recall 0.18 (famous+mid 0.26, obscure 0.00; #16/24 on file, nearest nemotron-3.5-lightning:free 0.18, ling-3.0-flash-sante:free 0.18); retro-today Brier 0.275 vs base rate 0.198 (n=22, |p-.5| 0.25, 1 correct commits on the scored set); domain bank 67/72 measurable (8 censored, median 927 ctok/solved, effort on); frontier ladder 18/23, 1 censored; portfolio ladder 19/30

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.18 | 0.25 | 0.27 | 0.00 | 0.26 | 16/24 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 22/22 | 0.275 | 0.198 | 0.55 | 0.25 | 8 (3) | 1 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 67/72 (0.93), censored 8, median 927 / mean 2274 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 10 | 10 | 0 |
| bigknap | 0 | 0 | 5 |
| casework | 8 | 10 | 0 |
| inv | 3 | 4 | 3 |
| longctx | 10 | 10 | 0 |
| repobug | 10 | 10 | 0 |
| tableqa | 13 | 14 | 0 |
| toolsim | 13 | 14 | 0 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 1 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 10 | 12 | 0 |
| inversion | 8 | 11 | 1 |
| all | 18 | 23 | 1 |

## Portfolio ladder (five families)

30/30 items attempted, 0 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 6 | 6 | 0 |
| docfact | 5 | 6 | 0 |
| knapsack | 0 | 6 | 0 |
| spec | 2 | 6 | 0 |
| zebra | 6 | 6 | 0 |
| all | 19 | 30 | 0 |

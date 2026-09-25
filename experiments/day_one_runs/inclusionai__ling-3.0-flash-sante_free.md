# Day-one battery: inclusionai/ling-3.0-flash-sante:free

Generated 2026-09-22T09:59:57+00:00.
Catalog: inclusionAI: Ling 3.0 Flash Sante (free) - listed 2026-09-04, ctx 262144, max out 32768, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 0 requests, 0 429 retries, 0 max_tokens clamps, 0.0 min paced |
| _elapsed | 0 min |

## Dossier draft

**inclusionAI: Ling 3.0 Flash Sante (free)** (inclusionai/ling-3.0-flash-sante:free) - recall 0.18 (famous+mid 0.26, obscure 0.00; #18/26 on file, nearest nemotron-3.5-lightning:free 0.18, ling-3.0-flash-vl:free 0.18); retro-today Brier 0.292 vs base rate 0.198 (n=22, |p-.5| 0.25, 1 correct commits on the scored set); domain bank 69/72 measurable (8 censored, median 1176 ctok/solved, effort on); frontier ladder 20/21, 3 censored; portfolio ladder 18/24, 6 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.18 | 0.33 | 0.18 | 0.00 | 0.26 | 18/26 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 22/22 | 0.292 | 0.198 | 0.55 | 0.25 | 7 (5) | 1 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 69/72 (0.96), censored 8, median 1176 / mean 2171 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 10 | 10 | 0 |
| bigknap | 0 | 0 | 5 |
| casework | 10 | 10 | 0 |
| inv | 4 | 4 | 3 |
| longctx | 10 | 10 | 0 |
| repobug | 10 | 10 | 0 |
| tableqa | 11 | 14 | 0 |
| toolsim | 14 | 14 | 0 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 3 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 12 | 12 | 0 |
| inversion | 8 | 9 | 3 |
| all | 20 | 21 | 3 |

## Portfolio ladder (five families)

30/30 items attempted, 6 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 6 | 6 | 0 |
| docfact | 4 | 6 | 0 |
| knapsack | 0 | 0 | 6 |
| spec | 2 | 6 | 0 |
| zebra | 6 | 6 | 0 |
| all | 18 | 24 | 6 |

# Day-one battery: nex-agi/nex-n2.5-mini:free

Generated 2026-09-22T09:59:56+00:00.
Catalog: Nex AGI: Nex-N2.5-Mini (free) - listed 2026-09-08, ctx 262144, max out 235929, reasoning param, $0.00/$0.00 per M, expires 2026-09-25.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 291 requests, 0 429 retries, 0 max_tokens clamps, 2.3 min paced |
| _elapsed | 261 min |

## Dossier draft

**Nex AGI: Nex-N2.5-Mini (free)** (nex-agi/nex-n2.5-mini:free) - recall 0.32 (famous+mid 0.48, obscure 0.00; #8/26 on file, nearest kimi-k2.6 0.32, deepseek-v4-pro 0.32); retro-today Brier 0.373 vs base rate 0.198 (n=19, |p-.5| 0.34, 0 correct commits on the scored set); domain bank 58/73 measurable (7 censored, median 480 ctok/solved, effort on); frontier ladder 11/22, 2 censored; portfolio ladder 23/25, 5 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.32 | 0.50 | 0.45 | 0.00 | 0.48 | 8/26 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 19/22 | 0.373 | 0.198 | 0.53 | 0.34 | 4 (2) | 0 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 58/73 (0.79), censored 7, median 480 / mean 1829 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 10 | 10 | 0 |
| bigknap | 1 | 1 | 4 |
| casework | 5 | 10 | 0 |
| inv | 1 | 4 | 3 |
| longctx | 10 | 10 | 0 |
| repobug | 10 | 10 | 0 |
| tableqa | 12 | 14 | 0 |
| toolsim | 9 | 14 | 0 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 2 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 3 | 12 | 0 |
| inversion | 8 | 10 | 2 |
| all | 11 | 22 | 2 |

## Portfolio ladder (five families)

30/30 items attempted, 5 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 6 | 6 | 0 |
| docfact | 5 | 6 | 0 |
| knapsack | 1 | 1 | 5 |
| spec | 5 | 6 | 0 |
| zebra | 6 | 6 | 0 |
| all | 23 | 25 | 5 |

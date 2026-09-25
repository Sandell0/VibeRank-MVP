# Day-one battery: mistral/zai-glm-5-3

Generated 2026-09-22T23:32:00+00:00.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 369 requests, 49 429 retries, 0 max_tokens clamps, 0.5 min paced |
| _elapsed | 86 min |

## Dossier draft

**mistral/zai-glm-5-3** (mistral/zai-glm-5-3) - recall 0.32 (famous+mid 0.48, obscure 0.00; #8/28 on file, nearest kimi-k2.6 0.32, deepseek-v4-pro 0.32); retro-today Brier 0.426 vs base rate 0.198 (n=22, |p-.5| 0.31, 0 correct commits on the scored set); domain bank 71/74 measurable (6 censored, median 828 ctok/solved, effort rejected); frontier ladder 22/24; portfolio ladder 26/28, 2 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.32 | 0.50 | 0.45 | 0.00 | 0.48 | 8/28 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 22/22 | 0.426 | 0.198 | 0.41 | 0.31 | 3 (0) | 0 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 71/74 (0.96), censored 6, median 828 / mean 3176 completion tokens per solved item, effort param rejected or unset.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 10 | 10 | 0 |
| bigknap | 2 | 2 | 3 |
| casework | 10 | 10 | 0 |
| inv | 4 | 6 | 1 |
| longctx | 10 | 10 | 0 |
| repobug | 10 | 10 | 0 |
| tableqa | 12 | 12 | 2 |
| toolsim | 13 | 14 | 0 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 0 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 11 | 12 | 0 |
| inversion | 11 | 12 | 0 |
| all | 22 | 24 | 0 |

## Portfolio ladder (five families)

30/30 items attempted, 2 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 6 | 6 | 0 |
| docfact | 5 | 6 | 0 |
| knapsack | 4 | 4 | 2 |
| spec | 5 | 6 | 0 |
| zebra | 6 | 6 | 0 |
| all | 26 | 28 | 2 |

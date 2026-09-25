# Day-one battery: z-ai/glm-5.2:free

Generated 2026-09-25T05:42:29+00:00.
Catalog: Z.ai: GLM 5.2 (free) - listed 2026-06-16, ctx 32768, max out 29491, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 387 requests, 271 429 retries, 116 max_tokens clamps, 1.2 min paced |
| _elapsed | 52 min |

## Dossier draft

**Z.ai: GLM 5.2 (free)** (z-ai/glm-5.2:free) - recall 0.24 (famous+mid 0.35, obscure 0.00; #17/39 on file, nearest kimi-k2-0905 0.24, qwen3.6-plus 0.24); retro-today Brier 0.312 vs base rate 0.198 (n=18, |p-.5| 0.27, 0 correct commits on the scored set); domain bank 52/57 measurable (23 censored, median 759 ctok/solved, effort rejected); frontier ladder 14/21, 3 censored; portfolio ladder 17/21, 9 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.24 | 0.33 | 0.36 | 0.00 | 0.35 | 17/39 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 18/22 | 0.312 | 0.198 | 0.56 | 0.27 | 5 (2) | 0 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 52/57 (0.91), censored 23, median 759 / mean 1595 completion tokens per solved item, effort param rejected or unset.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 10 | 10 | 0 |
| bigknap | 0 | 0 | 5 |
| casework | 9 | 9 | 1 |
| inv | 3 | 6 | 1 |
| longctx | 1 | 1 | 9 |
| repobug | 7 | 7 | 3 |
| tableqa | 12 | 12 | 2 |
| toolsim | 10 | 12 | 2 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 3 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 8 | 11 | 1 |
| inversion | 6 | 10 | 2 |
| all | 14 | 21 | 3 |

## Portfolio ladder (five families)

30/30 items attempted, 9 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 6 | 6 | 0 |
| docfact | 3 | 4 | 2 |
| knapsack | 2 | 2 | 4 |
| spec | 1 | 4 | 2 |
| zebra | 5 | 5 | 1 |
| all | 17 | 21 | 9 |

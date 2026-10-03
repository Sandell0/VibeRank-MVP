# Day-one battery: inclusionai/ling-3.1-flash

Generated 2026-10-03T07:08:53+00:00.
Catalog: inclusionAI: Ling 3.1 Flash - listed 2026-10-02, ctx 262144, max out 32768, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 311 requests, 5 429 retries, 165 max_tokens clamps, 0.0 min paced |
| _elapsed | 205 min |

## Dossier draft

**inclusionAI: Ling 3.1 Flash** (inclusionai/ling-3.1-flash) - recall 0.15 (famous+mid 0.22, obscure 0.00; #26/41 on file, nearest nemotron-3-nano-omni-30b-a3b-reasoning:free 0.15, gemma-4-26b-a4b-it:free 0.15); retro-today Brier 0.245 vs base rate 0.198 (n=21, |p-.5| 0.23, 0 correct commits on the scored set); domain bank 75/75 measurable (5 censored, median 1466 ctok/solved, effort on); frontier ladder 22/24; portfolio ladder 26/27, 3 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.15 | 0.25 | 0.18 | 0.00 | 0.22 | 26/41 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 21/22 | 0.245 | 0.198 | 0.71 | 0.23 | 4 (1) | 0 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 75/75 (1.00), censored 5, median 1466 / mean 4062 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 10 | 10 | 0 |
| bigknap | 1 | 1 | 4 |
| casework | 10 | 10 | 0 |
| inv | 6 | 6 | 1 |
| longctx | 10 | 10 | 0 |
| repobug | 10 | 10 | 0 |
| tableqa | 14 | 14 | 0 |
| toolsim | 14 | 14 | 0 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 0 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 10 | 12 | 0 |
| inversion | 12 | 12 | 0 |
| all | 22 | 24 | 0 |

## Portfolio ladder (five families)

30/30 items attempted, 3 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 6 | 6 | 0 |
| docfact | 5 | 6 | 0 |
| knapsack | 3 | 3 | 3 |
| spec | 6 | 6 | 0 |
| zebra | 6 | 6 | 0 |
| all | 26 | 27 | 3 |

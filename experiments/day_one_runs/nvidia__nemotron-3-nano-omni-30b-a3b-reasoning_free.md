# Day-one battery: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free

Generated 2026-09-25T07:12:09+00:00.
Catalog: NVIDIA: Nemotron 3 Nano Omni (free) - listed 2026-04-28, ctx 256000, max out 65536, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 114 requests, 0 429 retries, 0 max_tokens clamps, 0.0 min paced |
| _elapsed | 48 min |

## Dossier draft

**NVIDIA: Nemotron 3 Nano Omni (free)** (nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free) - recall 0.15 (famous+mid 0.22, obscure 0.00; #25/39 on file, nearest gemma-4-26b-a4b-it:free 0.15, gemma-4-31b-it:free 0.15); retro-today Brier 0.217 vs base rate 0.198 (n=15, |p-.5| 0.25, 0 correct commits on the scored set); domain bank 43/54 measurable (26 censored, median 1084 ctok/solved, effort on); frontier ladder 1/19, 5 censored; portfolio ladder 7/19, 11 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.15 | 0.17 | 0.27 | 0.00 | 0.22 | 25/39 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 15/22 | 0.217 | 0.198 | 0.73 | 0.25 | 2 (1) | 0 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 43/54 (0.80), censored 26, median 1084 / mean 2000 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 9 | 9 | 1 |
| bigknap | 0 | 0 | 5 |
| casework | 8 | 8 | 2 |
| inv | 0 | 6 | 1 |
| longctx | 4 | 4 | 6 |
| repobug | 8 | 8 | 2 |
| tableqa | 7 | 7 | 7 |
| toolsim | 7 | 12 | 2 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 5 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 1 | 9 | 3 |
| inversion | 0 | 10 | 2 |
| all | 1 | 19 | 5 |

## Portfolio ladder (five families)

30/30 items attempted, 11 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 1 | 5 | 1 |
| docfact | 4 | 4 | 2 |
| knapsack | 0 | 4 | 2 |
| spec | 0 | 4 | 2 |
| zebra | 2 | 2 | 4 |
| all | 7 | 19 | 11 |

# Day-one battery: stealth/space-bunny-alpha

Generated 2026-09-25T04:50:34+00:00.
Catalog: Space Bunny Alpha - listed 2026-09-23, ctx 1000000, max out 524288, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 283 requests, 0 429 retries, 0 max_tokens clamps, 0.0 min paced |
| _elapsed | 159 min |

## Dossier draft

**Space Bunny Alpha** (stealth/space-bunny-alpha) - recall 0.15 (famous+mid 0.22, obscure 0.00; #25/39 on file, nearest nemotron-3-nano-omni-30b-a3b-reasoning:free 0.15, gemma-4-26b-a4b-it:free 0.15); retro-today Brier 0.290 vs base rate 0.198 (n=22, |p-.5| 0.26, 1 correct commits on the scored set); domain bank 70/79 measurable (1 censored, median 588 ctok/solved, effort on); frontier ladder 6/23, 1 censored; portfolio ladder 18/30

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.15 | 0.33 | 0.09 | 0.00 | 0.22 | 25/39 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 22/22 | 0.290 | 0.198 | 0.50 | 0.26 | 8 (4) | 1 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 70/79 (0.89), censored 1, median 588 / mean 2249 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 10 | 10 | 0 |
| bigknap | 5 | 5 | 0 |
| casework | 8 | 10 | 0 |
| inv | 3 | 6 | 1 |
| longctx | 10 | 10 | 0 |
| repobug | 10 | 10 | 0 |
| tableqa | 14 | 14 | 0 |
| toolsim | 10 | 14 | 0 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 1 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 3 | 12 | 0 |
| inversion | 3 | 11 | 1 |
| all | 6 | 23 | 1 |

## Portfolio ladder (five families)

30/30 items attempted, 0 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 5 | 6 | 0 |
| docfact | 5 | 6 | 0 |
| knapsack | 3 | 6 | 0 |
| spec | 0 | 6 | 0 |
| zebra | 5 | 6 | 0 |
| all | 18 | 30 | 0 |

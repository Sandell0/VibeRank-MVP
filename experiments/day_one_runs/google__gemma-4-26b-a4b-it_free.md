# Day-one battery: google/gemma-4-26b-a4b-it:free

Generated 2026-09-25T09:46:14+00:00.
Catalog: Google: Gemma 4 26B A4B  (free) - listed 2026-04-03, ctx 262144, max out 32768, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 163 requests, 45 429 retries, 118 max_tokens clamps, 0.0 min paced |
| _elapsed | 154 min |

## Dossier draft

**Google: Gemma 4 26B A4B  (free)** (google/gemma-4-26b-a4b-it:free) - recall 0.15 (famous+mid 0.22, obscure 0.00; #25/39 on file, nearest nemotron-3-nano-omni-30b-a3b-reasoning:free 0.15, gemma-4-31b-it:free 0.15); retro-today Brier 0.313 vs base rate 0.198 (n=22, |p-.5| 0.29, 0 correct commits on the scored set); domain bank 43/46 measurable (34 censored, median 2797 ctok/solved, effort on); frontier ladder 10/24; portfolio ladder 16/30

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.15 | 0.25 | 0.18 | 0.00 | 0.22 | 25/39 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 22/22 | 0.313 | 0.198 | 0.55 | 0.29 | 3 (1) | 0 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 43/46 (0.93), censored 34, median 2797 / mean 5410 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 2 | 2 | 8 |
| bigknap | 0 | 0 | 5 |
| casework | 8 | 8 | 2 |
| inv | 1 | 4 | 3 |
| longctx | 6 | 6 | 4 |
| repobug | 9 | 9 | 1 |
| tableqa | 10 | 10 | 4 |
| toolsim | 7 | 7 | 7 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 0 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 5 | 12 | 0 |
| inversion | 5 | 12 | 0 |
| all | 10 | 24 | 0 |

## Portfolio ladder (five families)

30/30 items attempted, 0 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 2 | 6 | 0 |
| docfact | 5 | 6 | 0 |
| knapsack | 0 | 6 | 0 |
| spec | 3 | 6 | 0 |
| zebra | 6 | 6 | 0 |
| all | 16 | 30 | 0 |

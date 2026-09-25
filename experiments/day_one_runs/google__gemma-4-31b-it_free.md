# Day-one battery: google/gemma-4-31b-it:free

Generated 2026-09-25T10:53:33+00:00.
Catalog: Google: Gemma 4 31B (free) - listed 2026-04-02, ctx 262144, max out 32768, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 136 requests, 50 429 retries, 86 max_tokens clamps, 0.0 min paced |
| _elapsed | 67 min |

## Dossier draft

**Google: Gemma 4 31B (free)** (google/gemma-4-31b-it:free) - recall 0.15 (famous+mid 0.22, obscure 0.00; #25/39 on file, nearest nemotron-3-nano-omni-30b-a3b-reasoning:free 0.15, gemma-4-26b-a4b-it:free 0.15); retro-today Brier 0.358 vs base rate 0.198 (n=22, |p-.5| 0.30, 0 correct commits on the scored set); domain bank 73/75 measurable (5 censored, median 4147 ctok/solved, effort on); frontier ladder 6/24; portfolio ladder 22/30

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.15 | 0.17 | 0.27 | 0.00 | 0.22 | 25/39 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 22/22 | 0.358 | 0.198 | 0.50 | 0.30 | 9 (4) | 0 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 73/75 (0.97), censored 5, median 4147 / mean 5767 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 10 | 10 | 0 |
| bigknap | 5 | 5 | 0 |
| casework | 10 | 10 | 0 |
| inv | 4 | 6 | 1 |
| longctx | 6 | 6 | 4 |
| repobug | 10 | 10 | 0 |
| tableqa | 14 | 14 | 0 |
| toolsim | 14 | 14 | 0 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 0 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 5 | 12 | 0 |
| inversion | 1 | 12 | 0 |
| all | 6 | 24 | 0 |

## Portfolio ladder (five families)

30/30 items attempted, 0 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 3 | 6 | 0 |
| docfact | 5 | 6 | 0 |
| knapsack | 3 | 6 | 0 |
| spec | 5 | 6 | 0 |
| zebra | 6 | 6 | 0 |
| all | 22 | 30 | 0 |

# Day-one battery: apodex/apodex-1.1-mini:free

Generated 2026-10-02T06:12:45+00:00.
Catalog: Apodex: Apodex 1.1 Mini (free) - listed 2026-10-01, ctx 262144, max out 235929, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 299 requests, 0 429 retries, 0 max_tokens clamps, 3.4 min paced |
| _elapsed | 160 min |

## Dossier draft

**Apodex: Apodex 1.1 Mini (free)** (apodex/apodex-1.1-mini:free) - recall 0.18 (famous+mid 0.26, obscure 0.00; #22/40 on file, nearest nemotron-3.5-lightning:free 0.18, ling-3.0-flash-sante:free 0.18); retro-today Brier 0.407 vs base rate 0.198 (n=19, |p-.5| 0.36, 0 correct commits on the scored set); domain bank 69/73 measurable (7 censored, median 3230 ctok/solved, effort on); frontier ladder 13/18, 6 censored; portfolio ladder 18/24, 6 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.18 | 0.33 | 0.18 | 0.00 | 0.26 | 22/40 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 19/22 | 0.407 | 0.198 | 0.42 | 0.36 | 9 (4) | 0 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 69/73 (0.95), censored 7, median 3230 / mean 4708 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 10 | 10 | 0 |
| bigknap | 1 | 3 | 2 |
| casework | 10 | 10 | 0 |
| inv | 1 | 2 | 5 |
| longctx | 10 | 10 | 0 |
| repobug | 10 | 10 | 0 |
| tableqa | 13 | 14 | 0 |
| toolsim | 14 | 14 | 0 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 6 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 7 | 12 | 0 |
| inversion | 6 | 6 | 6 |
| all | 13 | 18 | 6 |

## Portfolio ladder (five families)

30/30 items attempted, 6 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 5 | 5 | 1 |
| docfact | 5 | 6 | 0 |
| knapsack | 0 | 1 | 5 |
| spec | 2 | 6 | 0 |
| zebra | 6 | 6 | 0 |
| all | 18 | 24 | 6 |

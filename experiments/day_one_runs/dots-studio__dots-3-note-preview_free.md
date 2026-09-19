# Day-one battery: dots-studio/dots-3-note-preview:free

Generated 2026-09-02T18:54:16+00:00.
Catalog: Dots Studio: Dots3-Note Preview (free) - listed 2026-08-14, ctx 512000, max out 460800, reasoning param, $0.00/$0.00 per M, expires 2026-09-30.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 289 requests, 0 429 retries, 0 max_tokens clamps, 4.6 min paced |
| _elapsed | 214 min |

## Dossier draft

**Dots Studio: Dots3-Note Preview (free)** (dots-studio/dots-3-note-preview:free) - recall 0.12 (famous+mid 0.17, obscure 0.00; #17/18 on file, nearest claude-haiku-4.5 0.09, nemotron-3.5-lightning:free 0.18); retro-today Brier 0.311 vs base rate 0.198 (n=22, |p-.5| 0.27, 1 correct commits on the scored set); domain bank 74/77 measurable (3 censored, median 1436 ctok/solved, effort on); frontier ladder 23/23, 1 censored; portfolio ladder 24/26, 4 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.12 | 0.17 | 0.18 | 0.00 | 0.17 | 17/18 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 22/22 | 0.311 | 0.198 | 0.50 | 0.27 | 7 (5) | 1 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 74/77 (0.96), censored 3, median 1436 / mean 6971 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 10 | 10 | 0 |
| bigknap | 2 | 3 | 2 |
| casework | 9 | 10 | 0 |
| inv | 6 | 6 | 1 |
| longctx | 9 | 10 | 0 |
| repobug | 10 | 10 | 0 |
| tableqa | 14 | 14 | 0 |
| toolsim | 14 | 14 | 0 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 1 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 12 | 12 | 0 |
| inversion | 11 | 11 | 1 |
| all | 23 | 23 | 1 |

## Portfolio ladder (five families)

30/30 items attempted, 4 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 6 | 6 | 0 |
| docfact | 5 | 6 | 0 |
| knapsack | 2 | 2 | 4 |
| spec | 5 | 6 | 0 |
| zebra | 6 | 6 | 0 |
| all | 24 | 26 | 4 |

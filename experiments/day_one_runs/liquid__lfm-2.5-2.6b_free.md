# Day-one battery: liquid/lfm-2.5-2.6b:free

Generated 2026-09-02T20:13:59+00:00.
Catalog: LiquidAI: LFM2.5-2.6B (free) - listed 2026-08-11, ctx 65536, max out 8192, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 353 requests, 9 429 retries, 344 max_tokens clamps, 6.3 min paced |
| _elapsed | 80 min |

## Dossier draft

**LiquidAI: LFM2.5-2.6B (free)** (liquid/lfm-2.5-2.6b:free) - recall 0.03 (famous+mid 0.04, obscure 0.00; #19/19 on file, nearest claude-haiku-4.5 0.09, dots-3-note-preview:free 0.12); retro-today Brier 0.327 vs base rate 0.198 (n=22, |p-.5| 0.19, 0 correct commits on the scored set); domain bank 28/52 measurable (28 censored, median 1930 ctok/solved, effort on); frontier ladder 1/3, 21 censored; portfolio ladder 4/12, 18 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.03 | 0.00 | 0.09 | 0.00 | 0.04 | 19/19 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 22/22 | 0.327 | 0.198 | 0.55 | 0.19 | 2 (1) | 0 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 28/52 (0.54), censored 28, median 1930 / mean 2341 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 6 | 10 | 0 |
| bigknap | 0 | 0 | 5 |
| casework | 2 | 10 | 0 |
| inv | 0 | 0 | 7 |
| longctx | 3 | 6 | 4 |
| repobug | 10 | 10 | 0 |
| tableqa | 1 | 8 | 6 |
| toolsim | 6 | 8 | 6 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 21 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 1 | 3 | 9 |
| inversion | 0 | 0 | 12 |
| all | 1 | 3 | 21 |

## Portfolio ladder (five families)

30/30 items attempted, 18 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 1 | 2 | 4 |
| docfact | 2 | 6 | 0 |
| knapsack | 0 | 0 | 6 |
| spec | 0 | 2 | 4 |
| zebra | 1 | 2 | 4 |
| all | 4 | 12 | 18 |

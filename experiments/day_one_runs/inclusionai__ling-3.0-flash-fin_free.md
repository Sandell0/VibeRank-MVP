# Day-one battery: inclusionai/ling-3.0-flash-fin:free

Generated 2026-09-02T15:20:38+00:00.
Catalog: Ling 3.0 Flash Fin (free) - listed 2026-08-27, ctx 262144, max out 32768, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 295 requests, 0 429 retries, 154 max_tokens clamps, 6.5 min paced |
| _elapsed | 235 min |

## Dossier draft

**Ling 3.0 Flash Fin (free)** (inclusionai/ling-3.0-flash-fin:free) - recall 0.24 (famous+mid 0.35, obscure 0.00; #12/17 on file, nearest kimi-k2-0905 0.24, qwen3.6-plus 0.24); retro-today Brier 0.291 vs base rate 0.198 (n=22, |p-.5| 0.24, 1 correct commits on the scored set); domain bank 71/72 measurable (8 censored, median 1085 ctok/solved, effort on); frontier ladder 20/21, 3 censored; portfolio ladder 18/24, 6 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.24 | 0.33 | 0.36 | 0.00 | 0.35 | 12/17 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 22/22 | 0.291 | 0.198 | 0.55 | 0.24 | 8 (3) | 1 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 71/72 (0.99), censored 8, median 1085 / mean 3427 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 10 | 10 | 0 |
| bigknap | 0 | 0 | 5 |
| casework | 10 | 10 | 0 |
| inv | 4 | 4 | 3 |
| longctx | 10 | 10 | 0 |
| repobug | 10 | 10 | 0 |
| tableqa | 13 | 14 | 0 |
| toolsim | 14 | 14 | 0 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 3 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 11 | 12 | 0 |
| inversion | 9 | 9 | 3 |
| all | 20 | 21 | 3 |

## Portfolio ladder (five families)

30/30 items attempted, 6 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 6 | 6 | 0 |
| docfact | 5 | 6 | 0 |
| knapsack | 0 | 0 | 6 |
| spec | 1 | 6 | 0 |
| zebra | 6 | 6 | 0 |
| all | 18 | 24 | 6 |

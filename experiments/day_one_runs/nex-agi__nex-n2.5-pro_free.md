# Day-one battery: nex-agi/nex-n2.5-pro:free

Generated 2026-09-22T05:39:11+00:00.
Catalog: Nex AGI: Nex-N2.5-Pro (free) - listed 2026-09-08, ctx 262144, max out 235929, reasoning param, $0.00/$0.00 per M, expires 2026-09-25.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 24 requests, 0 429 retries, 0 max_tokens clamps, 0.0 min paced |
| _elapsed | 95 min |

## Dossier draft

**Nex AGI: Nex-N2.5-Pro (free)** (nex-agi/nex-n2.5-pro:free) - recall 0.29 (famous+mid 0.43, obscure 0.00; #10/25 on file, nearest gpt-5.4-mini 0.29, qwen3.6-35b-a3b 0.29); retro-today Brier 0.393 vs base rate 0.198 (n=22, |p-.5| 0.29, 1 correct commits on the scored set); domain bank 71/77 measurable (3 censored, median 600 ctok/solved, effort on); frontier ladder 17/24; portfolio ladder 23/28, 2 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.29 | 0.58 | 0.27 | 0.00 | 0.43 | 10/25 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 22/22 | 0.393 | 0.198 | 0.41 | 0.29 | 5 (1) | 1 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 71/77 (0.92), censored 3, median 600 / mean 4115 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 9 | 10 | 0 |
| bigknap | 3 | 3 | 2 |
| casework | 10 | 10 | 0 |
| inv | 5 | 7 | 0 |
| longctx | 10 | 10 | 0 |
| repobug | 9 | 9 | 1 |
| tableqa | 12 | 14 | 0 |
| toolsim | 13 | 14 | 0 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 0 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 5 | 12 | 0 |
| inversion | 12 | 12 | 0 |
| all | 17 | 24 | 0 |

## Portfolio ladder (five families)

30/30 items attempted, 2 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 4 | 6 | 0 |
| docfact | 4 | 5 | 1 |
| knapsack | 4 | 5 | 1 |
| spec | 5 | 6 | 0 |
| zebra | 6 | 6 | 0 |
| all | 23 | 28 | 2 |

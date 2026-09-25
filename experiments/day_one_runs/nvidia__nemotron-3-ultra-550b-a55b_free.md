# Day-one battery: nvidia/nemotron-3-ultra-550b-a55b:free

Generated 2026-09-25T06:16:04+00:00.
Catalog: NVIDIA: Nemotron 3 Ultra (free) - listed 2026-06-04, ctx 1000000, max out 65536, reasoning param, $0.00/$0.00 per M.

| step | outcome |
|---|---|
| recall | ok (86/86) |
| retro | ok (55/55) |
| domain | ok (80/80) |
| frontier | ok (24/24) |
| portfolio | ok (30/30) |
| _target_calls | 81 requests, 0 429 retries, 0 max_tokens clamps, 0.6 min paced |
| _elapsed | 34 min |

## Dossier draft

**NVIDIA: Nemotron 3 Ultra (free)** (nvidia/nemotron-3-ultra-550b-a55b:free) - recall 0.29 (famous+mid 0.43, obscure 0.00; #12/39 on file, nearest gpt-5.4-mini 0.29, qwen3.6-35b-a3b 0.29); retro-today Brier 0.188 vs base rate 0.198 (n=18, |p-.5| 0.27, 0 correct commits on the scored set); domain bank 73/77 measurable (3 censored, median 1350 ctok/solved, effort on); frontier ladder 19/19, 5 censored; portfolio ladder 21/27, 3 censored

## Recall (long-tail, closed book)

| items | all | famous | mid | obscure | famous+mid | rank on file |
|---|---|---|---|---|---|---|
| 34 | 0.29 | 0.50 | 0.36 | 0.00 | 0.43 | 12/39 |

## Retro-today (72h Manifold bank, panel-frozen shared set)

| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |
|---|---|---|---|---|---|---|
| 18/22 | 0.188 | 0.198 | 0.83 | 0.27 | 4 (2) | 0 |

A correct commit on the scored set is a leakage footnote (freshness law, lab record K).

## Domain bank (80 items, per-cell tokens)

Measurable 73/77 (0.95), censored 3, median 1350 / mean 4448 completion tokens per solved item, effort param accepted.

| family | solved | measurable | censored |
|---|---|---|---|
| audit | 10 | 10 | 0 |
| bigknap | 0 | 2 | 3 |
| casework | 10 | 10 | 0 |
| inv | 6 | 7 | 0 |
| longctx | 10 | 10 | 0 |
| repobug | 10 | 10 | 0 |
| tableqa | 13 | 14 | 0 |
| toolsim | 14 | 14 | 0 |

## Frontier ladder (inversion/execution)

24/24 items attempted, 5 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| execution | 10 | 10 | 2 |
| inversion | 9 | 9 | 3 |
| all | 19 | 19 | 5 |

## Portfolio ladder (five families)

30/30 items attempted, 3 censored (empty completion at every retry).

| family | solved | measurable | censored |
|---|---|---|---|
| bughunt | 6 | 6 | 0 |
| docfact | 4 | 5 | 1 |
| knapsack | 2 | 6 | 0 |
| spec | 4 | 5 | 1 |
| zebra | 5 | 5 | 1 |
| all | 21 | 27 | 3 |

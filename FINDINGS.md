# Experiment findings index (2026-08-28 → 08-30)

Full program write-up (context, conclusions, open experiments, costs) lives in
the **llm-leaderboard repo**: `research/interview-instrument-findings-2026-08.md`.
This file maps conclusions to the artifacts in this repo.

| finding | experiment files |
|---|---|
| Holistic reads saturate at k≈10; ladder channel improves to k=25 | `experiments/pilot_deep_data.json`, `pilot_regrade_data.json` |
| Shared reader "floor" is affine-removable scale error; readers converge when conditioned (specific 101→42→10) | `pilot_conditioned_regrade.py`, `pilot_conditioned_data.json` |
| Ladder-only reads ≈ full-transcript reads; mechanical boundary fit beats LLM readers | same + `examiner_calibration.py` |
| Examiner Elo scales difficulty-label calibration (0.49→0.86 @k5; Sol 0.90 vs Terra 0.70 @k25 — k5 tie was resolution) | `examiner_calibration.py`, `pilot_terra_data.json` |
| 2-ladder ensemble hits mid-tier parity band (mae 39 vs target 37, n=5, residual r=+0.40) | `pilot_deep_data.json` + `pilot_terra_data.json` |
| Oral protocol caps at examiner−ε; GPT-5.5 uncapped (24/24) | `frontier_ladder.py`, `frontier_ladder_data.json` |
| 2-family verifiable ladder: frontier ρ −0.11; partial-credit prefix scoring leaves it unchanged | same (texts saved; chains recomputable from seed 20260828) |
| Breadth does NOT rescue the frontier: +5 families → ρ flat (+0.11 → −0.14) | `portfolio_ladder.py`, `portfolio_bank.json` (frozen), `portfolio_ladder_data.json` (252/270; 18 missing cells at budget) |
| Budget starvation misgrades reasoners (qwen 0/24 → 18/20 via 12k→60k) | frontier/portfolio data usage fields |
| Base rate: ladder is bottom-6% of public boards for in-band frontier agreement; GPT-5.4's Elo disagrees with 20/48 of its own in-band boards | computed in the leaderboard repo (unified-scores.json), see write-up §C |
| GPT-5.4's ladder collapse was a default-reasoning-effort artifact: 24/26 failures recover at effort=high (0.52→0.96; 1.9k→6.9k ctok/item) — retracts the §C corroboration | `effort_control_gpt54.py`, `effort_control_data.json` |
| The 7 planted-key families are ONE in-band factor (λ1 73% [49,87], six positive loadings) — the breadth test never left the grind cluster | `factor_structure.py` |
| Fresh 80-item multi-DOMAIN verifiable bank (8 families, 3 escalation waves, effort pinned) saturates the frontier band every wave (measurable 0.97–1.00; 4 real in-band misses/560 cells); discriminates fine below the band | `domain_portfolio.py`, `domain_portfolio_bank.json`, `domain_portfolio_data.json`, `domain_analysis.py` |
| Provider output ceilings censor before difficulty discriminates: 7/12 no-answer cells flip at 120k budget; qwen3.6-plus has a hard ~65k completion ceiling (4 cells permanently unmeasurable) | `domain_rerun_null.py`, write-up §G4 |
| Public-board side of the same checks (basket curves: verifiable-only baskets reach +0.89 in-band; frontier boards agree MORE than mid) | leaderboard repo `research/scripts/aggregation-curve.py`, write-up §G3 |

Earlier (pre-program) baselines: `sol_interview_*` (best k=5 run),
`self_steered_*` (Terra), `qwen_interview_*` (confounded self-grading),
`grader_swap_*`, `strong_reader_*`, `prefix_error_results.json`,
`holistic-calibration.json`.

Ops: run experiments with max_tokens ≥60k for reasoning models; TaskStop any
predecessor task before resuming after a laptop sleep (suspended tasks revive
and race the data file); gpt-oss-120b is not a valid difficulty-smoke reference.

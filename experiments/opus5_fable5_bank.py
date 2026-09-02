"""Claude Opus 5 and Claude Fable 5 through the frozen 80-item domain bank
with per-cell completion-token logging (2026-09-02).

Question (owner): is Opus 5 a smaller model compensating with serial
computation, or a same-class model with its own library? Same protocol as
distilled_efficiency.py / fable51_bank.py (effort pinned high, 60k
max_tokens, temperature 0.2), but written to its OWN data file so it never
races the day-one battery that appends to distilled_efficiency_data.json.

Prediction if Opus 5 is a compressed student: at tied accuracy its median
tokens per solved item sits above Fable 5's and its hard tail is steep
(mean >> median), the distance-to-ceiling signature of Mini and Haiku.

    python -m experiments.opus5_fable5_bank              # run (resumable)
    DISTILLED_SMOKE=1 python -m experiments.opus5_fable5_bank   # opus-5 x 2 items
    python -m experiments.opus5_fable5_bank --report
"""
import sys

import experiments.distilled_efficiency as de
import experiments.domain_portfolio as dp

OPUS5 = "anthropic/claude-opus-5"
FABLE5 = "anthropic/claude-fable-5"
de.MODELS = ((OPUS5, 2060, (5.0, 25.0)), (FABLE5, 2037, (10.0, 50.0)))
de.PRICE[OPUS5] = (5.0, 25.0)
de.PRICE[FABLE5] = (10.0, 50.0)
de.DATA_PATH = dp.EXP / "opus5_fable5_bank_data.json"
de.COST_CEILING_USD = 32.0  # hard stop; expected ~$15-25

# The toolsim family (simulated banking console) returns empty content from
# Anthropic's newest models (Fable 5.1 day-one: 0/14 all-empty; Opus 5 smoke:
# 2/2 empty across 4 attempts each). It is censored for both models by
# construction, so skip it rather than pay for 112 doomed calls. The
# comparison conditions on solved items and loses nothing.
SKIP_FAMILIES = {"toolsim"}
_load_bank = dp.load_bank
dp.load_bank = lambda: [it for it in _load_bank() if it["family"] not in SKIP_FAMILIES]

if __name__ == "__main__":
    if "--report" in sys.argv:
        de.report()
    else:
        de.main()

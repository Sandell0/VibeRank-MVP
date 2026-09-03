"""Muse Spark 1.3 through the frozen 80-item domain bank with per-cell tokens
(2026-09-03, owner request: does tokens-to-solve place it where its 30-board
Elo of 1981 says?). Same protocol as opus5_fable5_bank.py; own data file.

    python -m experiments.muse13_bank              # run (resumable)
    python -m experiments.muse13_bank --report
"""
import sys

import experiments.distilled_efficiency as de
import experiments.domain_portfolio as dp

MUSE = "meta/muse-spark-1.3"
de.MODELS = ((MUSE, 1981, (1.25, 4.25)),)
de.PRICE[MUSE] = (1.25, 4.25)
de.DATA_PATH = dp.EXP / "muse13_bank_data.json"
de.COST_CEILING_USD = 12.0  # hard stop; expected $2-7

if __name__ == "__main__":
    if "--report" in sys.argv:
        de.report()
    else:
        de.main()

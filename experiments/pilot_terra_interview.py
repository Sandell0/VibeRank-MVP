"""Terra-authored k=25 interviews of the same 5 pilot candidates.

Disambiguates the Tier-0 plateau: at k=5, Terra and Sol tie on boundary
consistency (0.85 vs 0.86) — examiner saturation, or k=5 instrument
resolution? Same candidates, same protocol, same depth as the Sol pilot;
compare via experiments.examiner_calibration (boundary rho and LOO
residual). If Terra-k25 matches Sol-k25, the plateau is real and protocol
is the remaining lever; if Sol pulls ahead, examiner scaling is alive.

    python -m experiments.pilot_terra_interview
"""
from __future__ import annotations

from pathlib import Path

import experiments.pilot_deep_interview as pdi

pdi.INTERVIEWER = "openai/gpt-5.6-terra"
pdi.DATA_PATH = Path(__file__).resolve().parent / "pilot_terra_data.json"
pdi.PRICES["author"] = (2.5, 15.0)  # gpt-5.6-terra list price

if __name__ == "__main__":
    pdi.main()

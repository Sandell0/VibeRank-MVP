"""Run any additional model through the world-model smoke bank.

Same frozen bank, runner, and grading as the ten-model record; results
append into worldmodel_smoke_data.json (resumable per cell).

    python -m experiments.worldmodel_probe anthropic/claude-opus-5
"""
import sys

import experiments.worldmodel_smoke as ws

if len(sys.argv) < 2 or "/" not in sys.argv[1]:
    raise SystemExit("usage: python -m experiments.worldmodel_probe <openrouter-slug>")

ws.CANDIDATES = (sys.argv[1],)

if __name__ == "__main__":
    ws.main()

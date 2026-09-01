"""Claude Fable 5.1 (released ~2026-09-01) through the world-model smoke
bank — same 86-call protocol as the Fable 5 / Opus 5 probes, for a
like-for-like recall comparison. No site Elo yet: pure out-of-sample.

    python -m experiments.worldmodel_fable51
"""
import experiments.worldmodel_smoke as ws

ws.CANDIDATES = ("anthropic/claude-fable-5.1",)

if __name__ == "__main__":
    ws.main()

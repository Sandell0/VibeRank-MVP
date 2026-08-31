"""Run Claude Fable 5 through the world-model smoke bank as the 10th model.

Same bank, runner, system prompt, and grading as the nine-model run; a
fresh API instance has no exposure to this session's context, so the
original bank stays uncontaminated. Site prices Fable 5 at 2037 (rank 5),
~100 Elo above the band top - an out-of-sample probe of the recall axis
above its calibration range.

    python -m experiments.worldmodel_fable
"""
import experiments.worldmodel_smoke as ws

ws.CANDIDATES = ("anthropic/claude-fable-5",)

if __name__ == "__main__":
    ws.main()

"""Claude Fable 5.1 through retro v2 as an out-of-sample probe.

The shared no-model-knows set stays FROZEN as defined by the original
nine-model panel (§J): 5.1 is scored on the same 76 questions, so its
Brier is column-comparable. Its own KNOW pass runs on all 103 for
horizon info, but its commits do not re-shrink the published set (a
correct-commit count on the scored set is reported as a residual-leakage
footnote instead).

    python -m experiments.retro_v2_fable51
"""
import json

import experiments.retro_v2 as rv
from viberank.clients import openrouter_client

M51 = "anthropic/claude-fable-5.1"


def main():
    bank = rv.load_bank()
    data = json.loads(rv.DATA_PATH.read_text(encoding="utf-8"))
    data["responses"].setdefault(M51, {})
    data["usage"].setdefault(M51, {"prompt": 0, "completion": 0})
    data.setdefault("effort_applied", {})
    survivors = rv.shared_set(bank, data)  # panel-frozen: rv.MODELS is still the 9
    print(f"frozen shared set: {len(survivors)} questions")
    rv.MODELS = ((M51, 0),)
    rv.PRICE[M51] = (10.0, 50.0)
    rv.COST_CEILING_USD = 40.0
    clients = {M51: openrouter_client(M51)}
    no_effort = set()
    print("=== 5.1 KNOW pass (all 103, horizon info) ===")
    rv.run_calls([(it["id"] + ":know", rv.know_prompt(it["question"])) for it in bank],
                 data, clients, no_effort, "know")
    print("=== 5.1 FORECAST pass (frozen shared set) ===")
    rv.run_calls([(it["id"] + ":forecast", rv.forecast_prompt(it["question"])) for it in survivors],
                 data, clients, no_effort, "forecast")
    print("done — analyze with the frozen-set snippet, not rv.report")


if __name__ == "__main__":
    main()

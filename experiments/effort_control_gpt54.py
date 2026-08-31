"""Tier-C control: GPT-5.4's failed ladder items at forced-high reasoning effort.

The combined 7-family runs show GPT-5.4 failing 26/54 items while spending
1.9k completion tokens/item - the lowest of the fleet (5.2: 6.5k, 5.5: 3.1k,
qwen: 29k). If its API default reasoning effort simply sits low, part of the
ladder anomaly is a measurement artifact, not ability. This re-asks the exact
original prompts with identical params plus OpenRouter
reasoning={"effort": "high"}. Four previously-PASSED items ride along as a
formatting control (high effort must not break the FINAL: convention).

Resumable per item. Verifies the recomputed frontier bank matches the stored
keys (seed 20260828) before spending anything.

    python -m experiments.effort_control_gpt54            # full run
    EFFORT_SMOKE=1 python -m experiments.effort_control_gpt54   # 1 item
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from viberank.clients import ProviderError, openrouter_client

import experiments.frontier_ladder as fl
import experiments.portfolio_ladder as pl

EXP = Path(__file__).resolve().parent
DATA_PATH = EXP / "effort_control_data.json"
MODEL = "openai/gpt-5.4"
EFFORT = {"reasoning": {"effort": "high"}}
RETRY_SLEEPS = (5, 15, 30)
N_PASSED_CONTROLS = 4

SYSTEM = {
    # exact system prompts of the original runs
    "F": ("Solve the problem by reasoning alone - you have no tools, "
          "no code execution. Be careful and exact."),
    "P": "Solve by reasoning alone - no tools, no code execution. Be careful and exact.",
}


def build_items():
    front = json.loads((EXP / "frontier_ladder_data.json").read_text(encoding="utf-8"))
    port = json.loads((EXP / "portfolio_ladder_data.json").read_text(encoding="utf-8"))

    fbank = {it["id"]: it for it in fl.build_bank()}
    for iid, meta in front["items"].items():
        assert fbank[iid]["key"] == meta["key"], f"seed drift on {iid}!"
    pbank = {it["id"]: it for it in pl.load_bank()}

    items = []  # (uid, source, item_dict, old_correct)
    for src_tag, data, bank in (("F", front, fbank), ("P", port, pbank)):
        answers = data["responses"][MODEL]["answers"]
        for iid, rec in sorted(answers.items()):
            items.append((f"{src_tag}:{iid}", src_tag, bank[iid], bool(rec.get("correct"))))

    failed = [x for x in items if not x[3]]
    passed = [x for x in items if x[3]]
    # controls: spread across distinct families
    controls, seen = [], set()
    for x in passed:
        fam = x[2]["family"]
        if fam not in seen:
            controls.append(x); seen.add(fam)
        if len(controls) == N_PASSED_CONTROLS:
            break
    return failed + controls


def grade(source, item, text):
    if source == "F":
        return fl.grade(text, item["key"]), fl.extract(text)
    return pl.grade(item, text), pl.extract(text)


def main():
    todo = build_items()
    print(f"{len(todo)} items ({sum(1 for x in todo if not x[3])} old-failed, "
          f"{sum(1 for x in todo if x[3])} passed controls)")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.is_file() else {
        "model": MODEL, "effort": "high", "answers": {}, "usage": {"prompt": 0, "completion": 0}}
    client = openrouter_client(MODEL)
    smoke = bool(os.environ.get("EFFORT_SMOKE"))

    for uid, source, item, old_correct in todo:
        if uid in data["answers"]:
            continue
        text, ptok, ctok = None, 0, 0
        for attempt, sleep_s in enumerate((0,) + RETRY_SLEEPS):
            if sleep_s:
                time.sleep(sleep_s)
            try:
                result = client.complete_with_usage(
                    [{"role": "system", "content": SYSTEM[source]},
                     {"role": "user", "content": item["prompt"]}],
                    temperature=0.2, max_tokens=60000, extra=EFFORT, timeout=300.0,
                )
                if not (result.content or "").strip() or result.content.strip() == "None":
                    raise ProviderError("empty/null content")
                text = result.content
                ptok = result.prompt_tokens or 0
                ctok = result.completion_tokens or 0
                break
            except ProviderError as exc:
                print(f"  {uid} attempt {attempt + 1} failed: {str(exc)[:110]}")
        ok, got = (False, None) if text is None else grade(source, item, text)
        data["answers"][uid] = {
            "family": item["family"], "rung": item["rung"], "old_correct": old_correct,
            "correct": bool(ok), "extracted": got, "completion_tokens": ctok, "text": text,
        }
        data["usage"]["prompt"] += ptok
        data["usage"]["completion"] += ctok
        flag = "PASS" if ok else "fail"
        print(f"  {uid:16s} {item['family']:9s} rung {item['rung']:>2}  old="
              f"{'pass' if old_correct else 'FAIL'} -> {flag}   {ctok:,} ctok")
        DATA_PATH.write_text(json.dumps(data, indent=1), encoding="utf-8")
        if smoke:
            print("smoke mode: stopping after 1 item")
            return

    ans = data["answers"]
    was_failed = {u: a for u, a in ans.items() if not a["old_correct"]}
    was_passed = {u: a for u, a in ans.items() if a["old_correct"]}
    rec = sum(1 for a in was_failed.values() if a["correct"])
    kept = sum(1 for a in was_passed.values() if a["correct"])
    ctoks = [a["completion_tokens"] for a in ans.values()]
    print(f"\nrecovered {rec}/{len(was_failed)} previously-failed items at effort=high")
    print(f"controls kept: {kept}/{len(was_passed)}")
    by_fam = {}
    for a in was_failed.values():
        f_ = by_fam.setdefault(a["family"], [0, 0])
        f_[1] += 1; f_[0] += 1 if a["correct"] else 0
    print("per family (recovered/failed):", {f: f"{v[0]}/{v[1]}" for f, v in sorted(by_fam.items())})
    print(f"completion tokens/item: {sum(ctoks)//max(1,len(ctoks)):,} "
          f"(default-effort baseline was 1,938)")
    p, c = data["usage"]["prompt"], data["usage"]["completion"]
    print(f"usage: {p:,} prompt + {c:,} completion  ~= ${p/1e6*1.25 + c/1e6*10:.2f} "
          f"at $1.25/$10 per M (BYOK - check the OpenAI dashboard)")


if __name__ == "__main__":
    main()

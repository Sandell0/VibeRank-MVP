"""Re-run domain-portfolio cells that failed with NO extractable answer.

A missing FINAL line on a hard item is the budget-truncation signature
(reasoning ate the 60k cap), not evidence of inability - the same artifact
the qwen 0/24 incident taught. Re-asks ONLY cells where correct=False and
the extraction came back None/non-numeric, at max_tokens=120000, effort
still pinned high. The 60k-budget answer is preserved under "prev_60k".

    python -m experiments.domain_rerun_null
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from viberank.clients import ProviderError, openrouter_client

import experiments.domain_portfolio as dp

EXP = Path(__file__).resolve().parent
DATA_PATH = EXP / "domain_portfolio_data.json"
RETRY_SLEEPS = (5, 15, 30)


def is_artifact_candidate(item, ans):
    if ans["correct"]:
        return False
    got = ans.get("extracted")
    if got is None:
        return True
    if item["kind"] == "number" and re.sub(r"[^\d]", "", got or "") == "":
        return True  # FINAL line present but non-numeric (mid-work truncation)
    return False


def main():
    bank = {i["id"]: i for i in json.loads(
        (EXP / "domain_portfolio_bank.json").read_text(encoding="utf-8"))}
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    jobs = []
    for m, r in data["responses"].items():
        for iid, ans in r["answers"].items():
            if is_artifact_candidate(bank[iid], ans) and "prev_60k" not in ans:
                jobs.append((m, iid))
    print(f"{len(jobs)} artifact-candidate cells to re-run at 120k budget")
    for m, iid in jobs:
        item = bank[iid]
        client = openrouter_client(m)
        text = None
        for attempt, sleep_s in enumerate((0,) + RETRY_SLEEPS):
            if sleep_s:
                time.sleep(sleep_s)
            try:
                result = client.complete_with_usage(
                    [{"role": "system", "content": dp.SYSTEM},
                     {"role": "user", "content": item["prompt"]}],
                    temperature=0.2, max_tokens=120000,
                    extra=dp.EFFORT, timeout=600.0,
                )
                if not (result.content or "").strip():
                    raise ProviderError("empty content again")
                text = result.content
                break
            except ProviderError as exc:
                print(f"  {m} {iid} attempt {attempt + 1}: {str(exc)[:100]}")
        old = data["responses"][m]["answers"][iid]
        ok = bool(text) and dp.grade(item, text)
        data["responses"][m]["answers"][iid] = {
            "correct": ok, "extracted": dp.extract(text) if text else None,
            "text": text, "prev_60k": {"correct": old["correct"],
                                       "extracted": old.get("extracted")},
            "budget": 120000,
        }
        if text and result.completion_tokens:
            data["usage"][m]["completion"] += result.completion_tokens
            data["usage"][m]["prompt"] += result.prompt_tokens or 0
        DATA_PATH.write_text(json.dumps(data, indent=1), encoding="utf-8")
        ct = result.completion_tokens if text else 0
        print(f"  {m.split('/')[-1]:18s} {iid:16s} -> "
              f"{'PASS' if ok else 'fail'} ({ct or 0:,} ctok)")

    flips = kept = 0
    for m, r in data["responses"].items():
        for iid, ans in r["answers"].items():
            if "prev_60k" in ans:
                if ans["correct"]:
                    flips += 1
                else:
                    kept += 1
    print(f"\n120k-budget verdict: {flips} artifact flips to PASS, {kept} still fail")


if __name__ == "__main__":
    main()

"""Retro-today (2026-09-01): the owner's freshness design — one bank from
the bleeding edge, no multi-week sampling.

Questions = Manifold binaries RESOLVED IN THE LAST ~72H (Aug 29 - Sep 1).
Outcomes are in today's news but weeks inside every model's pretraining
lag — including Fable 5.1, released this morning — so the field is clean
by construction and the KNOW pass becomes a validation (expected: ~zero
correct commits; any correct commit on a 72h-old outcome is a red flag).

Deviations from retro v2, on purpose:
  - bettors >= 15 (not 40): a 72h window can't fill at 40, and manual
    curation replaces the crowd-size proxy for resolution quality.
  - horizon >= 10d (market lived >= 10 days before resolving).
  - Fable 5.1 is IN the exclusion panel (all 10 models symmetric).

Prompts/runner/analysis are retro_v2's, verbatim, via import.

    python -m experiments.retro_today --harvest
    python -m experiments.retro_today --bank
    python -m experiments.retro_today            # know -> exclude -> forecast
    python -m experiments.retro_today --report
"""
from __future__ import annotations

import datetime as dt
import json
import sys

import requests

import experiments.retro_v2 as rv
from viberank.clients import openrouter_client

EXP = rv.EXP
BANK_PATH = EXP / "retro_today_bank.json"
DATA_PATH = EXP / "retro_today_data.json"

M51 = "anthropic/claude-fable-5.1"
PANEL = rv.MODELS + ((M51, 0),)

MIN_BETTORS = 15
MIN_HORIZON_DAYS = 10
RESOLVED_WINDOW = ("2026-08-29", "2026-09-01")

CURATED_DROPS = {  # manual resolver-subjectivity pass, 2026-09-01
    "today-zyqt6uttL5": "'falls behind' — subjective",
    "today-uAPRyuqyq0": "'new frontier of intelligence' — resolver judgment",
    "today-t29cIQpNNN": "private individual's employment",
    "today-uOICcdtOpc": "photo-hunt junk (glasses)",
    "today-O8hELNuAE6": "stock-price comparison (missed by word filter)",
    "today-N2Zuz5RuIE": "financial-index threshold",
    "today-pIPsZLP80l": "'better than' — criteria not in title",
    "today-fRLI6LYP9QLY7PsTtifu": "ambiguous conditional, truncated premise",
    "today-Z2IhIAqRsl": "'actually \"run\"' — scare-quote subjective",
    "today-LZAEp8dzpU": "'high-quality short film' — subjective",
    "today-Rc02zEIlZ6": "near-duplicate of the Polymarket Hormuz market",
}


def harvest():
    def ts(datestr):
        return int(dt.datetime.fromisoformat(datestr + "T00:00:00+00:00").timestamp() * 1000)

    lo = ts(RESOLVED_WINDOW[0])
    hi = ts(RESOLVED_WINDOW[1]) + 86400 * 1000  # inclusive end day
    horizon_ms = MIN_HORIZON_DAYS * 86400 * 1000
    prior_ids = set()
    for p in (rv.V1_BANK_PATH, rv.BANK_PATH):
        if p.is_file():
            prior_ids |= {i["id"].split("-", 1)[1] for i in
                          json.loads(p.read_text(encoding="utf-8"))
                          if i.get("family") == "retro"}
    picked, seen = [], set()
    for offset in (0, 500, 1000):
        r = requests.get("https://api.manifold.markets/v0/search-markets",
                         params={"term": "", "filter": "resolved", "contractType": "BINARY",
                                 "sort": "resolve-date", "limit": 500, "offset": offset},
                         timeout=60, headers=rv.UA)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        for m in batch:
            rt = m.get("resolutionTime") or 0
            ct = m.get("createdTime") or 0
            if rt < lo or rt > hi or rt - ct < horizon_ms:
                continue
            if m.get("resolution") not in ("YES", "NO"):
                continue
            if (m.get("uniqueBettorCount") or 0) < MIN_BETTORS:
                continue
            if m["id"] in prior_ids:
                continue
            q = m["question"].strip()
            if len(q) < 25 or rv.norm(q) in seen:
                continue
            if any(w in q.lower() for w in rv.PRICE_WORDS):
                continue
            if rv.SUBJECTIVE_RE.search(q):
                continue
            seen.add(rv.norm(q))
            picked.append({
                "id": f"today-{m['id']}", "family": "retro",
                "question": q, "resolution": m["resolution"],
                "resolved": dt.datetime.fromtimestamp(rt / 1000, dt.UTC).strftime("%Y-%m-%d"),
                "created": dt.datetime.fromtimestamp(ct / 1000, dt.UTC).strftime("%Y-%m-%d"),
                "bettors": m.get("uniqueBettorCount"),
            })
    return picked


def load_bank():
    bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    return [it for it in bank if it["id"] not in CURATED_DROPS]


def main():
    if "--harvest" in sys.argv:
        bank = harvest()
        BANK_PATH.write_text(json.dumps(bank, indent=1), encoding="utf-8")
        yes = sum(1 for it in bank if it["resolution"] == "YES")
        print(f"bank frozen -> {BANK_PATH.name}: {len(bank)} questions, "
              f"YES rate {yes/len(bank):.2f}")
        return
    bank = load_bank()
    if "--bank" in sys.argv:
        for it in bank:
            print(f"[{it['id']}] res={it['resolution']} resolved {it['resolved']} "
                  f"created {it['created']} bettors {it['bettors']}: {it['question'][:95]}")
        return

    rv.MODELS = PANEL
    rv.PRICE[M51] = (10.0, 50.0)
    rv.DATA_PATH = DATA_PATH
    rv.COST_CEILING_USD = 20.0

    if "--report" in sys.argv:
        rv.report(bank)
        return

    data = json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.is_file() else {
        "responses": {}, "usage": {}, "effort_applied": {}}
    for m, _ in PANEL:
        data["responses"].setdefault(m, {})
        data["usage"].setdefault(m, {"prompt": 0, "completion": 0})
    clients = {m: openrouter_client(m) for m, _ in PANEL}
    no_effort = set()
    print("=== stage 1: KNOW pass (freshness validation) ===")
    rv.run_calls([(it["id"] + ":know", rv.know_prompt(it["question"])) for it in bank],
                 data, clients, no_effort, "know")
    survivors = rv.shared_set(bank, data)
    print(f"=== exclusion: {len(bank) - len(survivors)} dropped (expected ~0), "
          f"{len(survivors)} scored ===")
    print("=== stage 2: FORECAST pass ===")
    rv.run_calls([(it["id"] + ":forecast", rv.forecast_prompt(it["question"])) for it in survivors],
                 data, clients, no_effort, "forecast")
    rv.report(bank, data)


if __name__ == "__main__":
    main()

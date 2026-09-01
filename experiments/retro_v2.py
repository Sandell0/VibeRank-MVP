"""Retrocast v2 (2026-09-01): symmetric exclusion, powered n.

v1 (worldmodel_smoke.py retro arm, n=25) died of two things: base-rate-
dominated n, and an ASYMMETRIC leakage control — the KNOW pass excluded
questions per-model by each model's own commit propensity, so conservative
committers kept hidden knowledge in their scored set and cashed it as
forecast skill (§H retraction).

v2 changes exactly three things, everything else verbatim from v1
(prompts, system, temp 0.2, effort pinned high with auto-fallback):
  1. SYMMETRIC exclusion: a question where ANY model's KNOW pass commits
     the correct outcome is dropped for EVERY model. Over-exclusion is
     accepted (costs power, never validity). Forecast runs only on the
     shared surviving set.
  2. Power: target ~160 questions resolved 2026-07-01..08-29 (v1
     evidence: correct commits do not decay by month inside 2026, so the
     window buys recency, not immunity — the KNOW pass does the work).
  3. Quality filters: bettors >= 40 (v1: 15), created <= 2026-05-31 (a
     real forecasting horizon, no insta-resolved markets), personal/self-
     referential/subjective markets dropped, v1 market ids excluded.

Per-cell completion tokens are logged (program default since §I).

Usage (from repo root):
  python -m experiments.retro_v2 --harvest   # build + freeze the bank
  python -m experiments.retro_v2 --bank      # eyeball the frozen bank
  python -m experiments.retro_v2            # run KNOW then FORECAST (resumable)
  python -m experiments.retro_v2 --report    # analysis only
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from viberank.clients import ProviderError, openrouter_client

EXP = Path(__file__).resolve().parent
BANK_PATH = EXP / "retro_v2_bank.json"
DATA_PATH = EXP / "retro_v2_data.json"
V1_BANK_PATH = EXP / "worldmodel_smoke_bank.json"

MODELS = (  # band-7 + the two above-band probes; slug: elo (budget-unified 2026-08-30)
    ("openai/gpt-5.2", 1818), ("moonshotai/kimi-k2.6", 1835),
    ("qwen/qwen3.6-plus", 1814), ("deepseek/deepseek-v4-pro", 1836),
    ("openai/gpt-5.4", 1881), ("anthropic/claude-opus-4.8", 1934),
    ("openai/gpt-5.5", 1937), ("anthropic/claude-fable-5", 2037),
    ("anthropic/claude-opus-5", 2060),
)
PRICE = {  # $/M (in, out) rough, for the cost ceiling only
    "openai/gpt-5.2": (1.25, 10.0), "moonshotai/kimi-k2.6": (0.6, 2.5),
    "qwen/qwen3.6-plus": (0.4, 2.4), "deepseek/deepseek-v4-pro": (0.27, 1.1),
    "openai/gpt-5.4": (1.25, 10.0), "anthropic/claude-opus-4.8": (5.0, 25.0),
    "openai/gpt-5.5": (1.25, 10.0), "anthropic/claude-fable-5": (6.0, 30.0),
    "anthropic/claude-opus-5": (5.0, 25.0),
}
COST_CEILING_USD = 25.0

EFFORT = {"reasoning": {"effort": "high"}}
RETRY_SLEEPS = (5, 15, 30)
UA = {"User-Agent": "aggregate-research/0.1"}
SYSTEM = "Answer from your own knowledge. No tools, no browsing."
FINAL_RE = re.compile(r"FINAL[:\s]*(.+)", re.I)

RETRO_TARGET = 160
MIN_BETTORS = 40
RESOLVED_WINDOW = ("2026-05-01", "2026-08-29")
MIN_HORIZON_DAYS = 45  # market must have existed this long before resolving
PRICE_WORDS = ("price", "$", "btc", "bitcoin", "eth", "stock", "s&p", "nasdaq",
               "close above", "close below", "market cap", "all-time high")
SUBJECTIVE_RE = re.compile(
    r"\b(i|my|me|mine|we|our|this market|\[poll\]|subjective|best|favorite)\b", re.I)
SEARCH_TERMS = ("", "will", "2026", "world", "ai", "election", "war", "season",
                "release")
SEARCH_SORTS = ("resolve-date", "close-date", "most-popular", "last-updated")

CURATED_DROPS = {  # manual resolver-subjectivity pass over the frozen bank, 2026-09-01
    "retro2-sJnxqZZWl88OEPxbdXwX": "self-referential ('this tweet hold up')",
    "retro2-vxi6XfA9celPUwAzC6BL": "opaque joke market (ChadGPT)",
    "retro2-8Nzq0Iq92g": "personal gossip market",
    "retro2-5D2M9ROOmLDoHODXZZ8B": "garbled/ambiguous question",
    "retro2-qt5pcdLy9g": "'anything CRAZY' — maximally subjective",
    "retro2-dIntAyAcUZ": "'more cautious' — subjective",
    "retro2-QSVgwCxYAV2HedfGyMiv": "'ubiquitous' — subjective",
    "retro2-UuKeZO2xvwtE3qMNxMKw": "'convincing hands' — subjective grading",
    "retro2-USpnpA6Idq": "title has no referent standalone",
    "retro2-q8dtCdNgsn": "relative deadline invisible in title",
    "retro2-IZNcZQAu0d": "'substantially reduced' — subjective",
    "retro2-su6n5h6AZS": "'interfere' — undefined",
    "retro2-cJr9XGDCpr6oaNng4prv": "'coherent films' — subjective",
    "retro2-UlZEC6Rys2": "'end of Iran War' — undefined boundary",
    "retro2-MkXkFzbsnGcOc0ja4M4A": "'some X negatively affected' family — resolver judgment",
    "retro2-H6DS1JfUIX8Evql1KLK2": "'some X negatively affected' family — resolver judgment",
    "retro2-eithThMNGm1lATYq6f54": "'some X negatively affected' family — resolver judgment",
    "retro2-pM6Xx8AdGWZfTdysrIjv": "'some X negatively affected' family — resolver judgment",
    "retro2-Vt5H2E5rjTtjZaEUN9Wk": "'some X negatively affected' family — resolver judgment",
    "retro2-0vfCTCfht3mB2XgEsrxz": "'some X negatively affected' family — resolver judgment",
}

_lock = threading.Lock()


def load_bank():
    bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    return [it for it in bank if it["id"] not in CURATED_DROPS]


def extract_final(text):
    if not text:
        return None
    hits = FINAL_RE.findall(text)
    return hits[-1].strip() if hits else None


def norm(s):
    return re.sub(r"\W+", " ", (s or "").lower()).strip()


# ----------------------------- harvest ---------------------------------------
def harvest():
    def ts(datestr):
        return int(dt.datetime.fromisoformat(datestr + "T00:00:00+00:00").timestamp() * 1000)

    lo, hi = ts(RESOLVED_WINDOW[0]), ts(RESOLVED_WINDOW[1])
    horizon_ms = MIN_HORIZON_DAYS * 86400 * 1000
    v1_ids = set()
    if V1_BANK_PATH.is_file():
        v1_ids = {i["id"].replace("retro-", "") for i in
                  json.loads(V1_BANK_PATH.read_text(encoding="utf-8"))
                  if i.get("family") == "retro"}
    picked, seen = [], set()
    for term in SEARCH_TERMS:
        for sort in SEARCH_SORTS:
            for offset in (0, 500, 1000):  # API rejects offsets past 1000
                params = {"term": term, "filter": "resolved", "contractType": "BINARY",
                          "sort": sort, "limit": 500, "offset": offset}
                try:
                    r = requests.get("https://api.manifold.markets/v0/search-markets",
                                     params=params, timeout=60, headers=UA)
                except requests.RequestException as exc:
                    print(f"  term={term!r} sort={sort} offset={offset}: {exc}")
                    break
                if not r.ok:
                    print(f"  term={term!r} sort={sort} offset={offset}: HTTP {r.status_code}")
                    break
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
                    if m["id"] in v1_ids:
                        continue
                    q = m["question"].strip()
                    if len(q) < 25 or norm(q) in seen:
                        continue
                    if any(w in q.lower() for w in PRICE_WORDS):
                        continue
                    if SUBJECTIVE_RE.search(q):
                        continue
                    seen.add(norm(q))
                    picked.append({
                        "id": f"retro2-{m['id']}", "family": "retro",
                        "question": q, "resolution": m["resolution"],
                        "resolution_month": dt.datetime.fromtimestamp(rt / 1000, dt.UTC).strftime("%Y-%m"),
                        "created": dt.datetime.fromtimestamp(ct / 1000, dt.UTC).strftime("%Y-%m-%d"),
                        "bettors": m.get("uniqueBettorCount"),
                    })
        print(f"  term={term!r}: pool now {len(picked)}")
    # spread across resolution months, earliest-created first within month
    by_month = {}
    for it in picked:
        by_month.setdefault(it["resolution_month"], []).append(it)
    for mo in by_month:
        by_month[mo].sort(key=lambda x: x["created"])
    out, months = [], sorted(by_month)
    while len(out) < RETRO_TARGET and any(by_month.values()):
        for mo in months:
            if by_month[mo] and len(out) < RETRO_TARGET:
                out.append(by_month[mo].pop(0))
    return out


# ----------------------------- prompts (v1 verbatim) --------------------------
def know_prompt(q):
    return (f"From your training knowledge: has this already happened / "
            f"how did it turn out?\n\n\"{q}\"\n\nIf you know the outcome, "
            f"answer YES or NO (the resolution). If this is after your "
            f"knowledge cutoff or you are unsure it has occurred, answer "
            f"UNKNOWN.\nEnd your reply with a line 'FINAL: YES/NO/UNKNOWN'.")


def forecast_prompt(q):
    return (f"Forecast, using only what you know (do not assume you know "
            f"the outcome):\n\n\"{q}\"\n\nGive your probability that this "
            f"resolves YES, as a number between 0 and 1.\n"
            f"End your reply with a line 'FINAL: <probability>'.")


# ----------------------------- runner -----------------------------------------
def est_cost(data):
    total = 0.0
    for m, u in data["usage"].items():
        pi, po = PRICE.get(m, (2.0, 10.0))
        total += u["prompt"] / 1e6 * pi + u["completion"] / 1e6 * po
    return total


def committed_correct(rec, resolution):
    know = (rec.get("extracted") or "").upper()
    return know.startswith(("YES", "NO")) and know.startswith(resolution)


def shared_set(bank, data):
    """Questions no model provably knows: drop any item where ANY model's
    KNOW pass committed the correct outcome."""
    out = []
    for it in bank:
        leaked = any(
            committed_correct(data["responses"].get(m, {}).get(it["id"] + ":know", {}),
                              it["resolution"])
            for m, _ in MODELS)
        if not leaked:
            out.append(it)
    return out


def run_calls(calls, data, clients, no_effort, total_label):
    todo = []
    for m, _ in MODELS:
        for cid, prompt in calls:
            if cid not in data["responses"][m]:
                todo.append((m, cid, prompt))
    print(f"{len(todo)} calls to make ({total_label})")

    def work(job):
        m, cid, prompt = job
        if est_cost(data) > COST_CEILING_USD:
            return f"SKIP {m} {cid} (cost ceiling)"
        extra = None if m in no_effort else EFFORT
        text, result = None, None
        for attempt, sleep_s in enumerate((0,) + RETRY_SLEEPS):
            if sleep_s:
                time.sleep(sleep_s)
            try:
                result = clients[m].complete_with_usage(
                    [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": prompt}],
                    temperature=0.2, max_tokens=16000, extra=extra, timeout=300.0)
                if not (result.content or "").strip():
                    raise ProviderError("empty content")
                text = result.content
                break
            except ProviderError as exc:
                msg = str(exc)
                if extra and ("reasoning" in msg.lower() or "400" in msg[:60]):
                    extra = None
                    with _lock:
                        no_effort.add(m)
                    continue
                print(f"  {m} {cid} attempt {attempt+1}: {msg[:90]}")
        got = extract_final(text) if text else None
        with _lock:
            data["responses"][m][cid] = {
                "extracted": got, "text": text,
                "completion_tokens": (result.completion_tokens if text and result else None)}
            data["effort_applied"][m] = extra is not None
            if text and result:
                data["usage"][m]["prompt"] += result.prompt_tokens or 0
                data["usage"][m]["completion"] += result.completion_tokens or 0
            done = sum(len(v) for v in data["responses"].values())
            DATA_PATH.write_text(json.dumps(data, indent=1), encoding="utf-8")
            print(f"[{done:4d}] {m:30s} {cid:36s} {str(got)[:24]:24s} ~${est_cost(data):.2f}")
        return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        for msg in pool.map(work, todo):
            if msg:
                print(msg)


def main():
    if "--harvest" in sys.argv:
        print("harvesting Manifold resolved markets...")
        bank = harvest()
        BANK_PATH.write_text(json.dumps(bank, indent=1), encoding="utf-8")
        mo = {}
        for it in bank:
            mo[it["resolution_month"]] = mo.get(it["resolution_month"], 0) + 1
        yes = sum(1 for it in bank if it["resolution"] == "YES")
        print(f"bank frozen -> {BANK_PATH.name}: {len(bank)} questions, "
              f"months {mo}, YES rate {yes/len(bank):.2f}")
        return
    bank = load_bank()
    if "--bank" in sys.argv:
        for it in bank:
            print(f"[{it['id']}] res={it['resolution']} {it['resolution_month']} "
                  f"created {it['created']} bettors {it['bettors']}: {it['question'][:95]}")
        return
    if "--report" in sys.argv:
        report(bank)
        return

    data = json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.is_file() else {
        "responses": {}, "usage": {}, "effort_applied": {}}
    for m, _ in MODELS:
        data["responses"].setdefault(m, {})
        data["usage"].setdefault(m, {"prompt": 0, "completion": 0})
    if os.environ.get("RETRO_SMOKE"):
        bank = bank[:2]
    clients = {m: openrouter_client(m) for m, _ in MODELS}
    no_effort = set()

    print("=== stage 1: KNOW pass ===")
    run_calls([(it["id"] + ":know", know_prompt(it["question"])) for it in bank],
              data, clients, no_effort, "know")
    survivors = shared_set(bank, data)
    print(f"=== symmetric exclusion: {len(bank) - len(survivors)} dropped, "
          f"{len(survivors)} in the shared no-model-knows set ===")
    print("=== stage 2: FORECAST pass (shared set only) ===")
    run_calls([(it["id"] + ":forecast", forecast_prompt(it["question"])) for it in survivors],
              data, clients, no_effort, "forecast")
    report(bank, data)


# ----------------------------- analysis ---------------------------------------
def parse_prob(s):
    if s is None:
        return None
    s = s.strip().rstrip(".")
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", s)
    if m:
        return float(m.group(1)) / 100
    m = re.search(r"\d*\.\d+|\b[01]\b", s)
    if m:
        v = float(m.group(0))
        return v if v <= 1 else None
    return None


def report(bank, data=None):
    import random as _random

    if data is None:
        data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    survivors = shared_set(bank, data)
    ids = [it["id"] for it in survivors]
    res = {it["id"]: 1.0 if it["resolution"] == "YES" else 0.0 for it in survivors}
    print(f"\n=== retro v2: {len(bank)} questions, {len(bank)-len(survivors)} "
          f"excluded symmetrically, {len(survivors)} scored ===")
    print(f"{'model':30s} {'Brier':>6} {'90% CI':>16} {'N':>4} {'commit':>6} "
          f"{'k-acc':>5} {'|p-.5|':>6}")
    rng = _random.Random(20260901)
    briers = {}
    for m, elo in MODELS:
        r = data["responses"][m]
        pts = []
        for i in ids:
            p = parse_prob(r.get(i + ":forecast", {}).get("extracted"))
            if p is not None:
                pts.append((p, res[i]))
        commits = corr = 0
        for it in bank:
            rec = r.get(it["id"] + ":know", {})
            know = (rec.get("extracted") or "").upper()
            if know.startswith(("YES", "NO")):
                commits += 1
                if know.startswith(it["resolution"]):
                    corr += 1
        if not pts:
            continue
        b = sum((p - y) ** 2 for p, y in pts) / len(pts)
        boots = []
        for _ in range(2000):
            s = [pts[rng.randrange(len(pts))] for _ in pts]
            boots.append(sum((p - y) ** 2 for p, y in s) / len(s))
        boots.sort()
        lo, hi = boots[int(0.05 * len(boots))], boots[int(0.95 * len(boots))]
        dec = sum(abs(p - 0.5) for p, _ in pts) / len(pts)
        briers[m] = b
        ka = corr / commits if commits else float("nan")
        print(f"{m:30s} {b:6.3f} [{lo:.3f}, {hi:.3f}] {len(pts):4d} {commits:6d} "
              f"{ka:5.2f} {dec:6.2f}")
    ys = list(res.values())
    base = sum(ys) / len(ys)
    base_brier = sum((base - y) ** 2 for y in ys) / len(ys)
    print(f"\nbaselines: always-0.5 = 0.250; base-rate ({base:.2f}) = {base_brier:.3f}")
    if len(briers) >= 3:
        order = sorted(briers, key=briers.get)
        print("ranking (best first): " + " > ".join(m.split("/")[-1] for m in order))
        elos = {m: e for m, e in MODELS}
        bs = [-briers[m] for m in briers]
        es = [elos[m] for m in briers]
        rk = lambda v: [sorted(v).index(x) for x in v]
        rx, ry = rk(bs), rk(es)
        n = len(bs)
        mx, my = sum(rx) / n, sum(ry) / n
        num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
        den = (sum((a - mx) ** 2 for a in rx) ** 0.5) * (sum((b - my) ** 2 for b in ry) ** 0.5)
        print(f"rho(-Brier, Elo) n={n}: {num/den:+.2f}")


if __name__ == "__main__":
    main()

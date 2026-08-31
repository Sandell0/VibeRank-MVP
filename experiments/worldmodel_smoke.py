"""World-model smoke test: two fresh instrument axes at small scale.

A. recall  - long-tail closed-book recall: facts sampled from Project
             Gutenberg books across an obscurity gradient, keys verified as
             literal spans of the source. Tests the world model AT REST.
B. retro   - retrocast: resolved Manifold binary questions whose resolution
             happened after the fleet's plausible cutoffs. Two passes per
             question: a KNOW pass (does the model already know the outcome
             -> effective knowledge horizon) and a FORECAST pass
             (probability, Brier-scored at analysis). Tests the world model
             RUN FORWARD, with per-model leakage exclusion by horizon.

    MISTRAL_API_KEY=... python -m experiments.worldmodel_smoke --harvest
    python -m experiments.worldmodel_smoke --bank        # print banks for review
    python -m experiments.worldmodel_smoke               # run candidates
"""
from __future__ import annotations

import datetime as dt
import json
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from viberank.clients import ProviderError, mistral_client, openrouter_client

EXP = Path(__file__).resolve().parent
BANK_PATH = EXP / "worldmodel_smoke_bank.json"
DATA_PATH = EXP / "worldmodel_smoke_data.json"
SEED = 20260831

CANDIDATES = (
    "openai/gpt-oss-120b", "moonshotai/kimi-k2-0905", "openai/gpt-5.2",
    "moonshotai/kimi-k2.6", "qwen/qwen3.6-plus", "deepseek/deepseek-v4-pro",
    "openai/gpt-5.4", "anthropic/claude-opus-4.8", "openai/gpt-5.5",
)
EFFORT = {"reasoning": {"effort": "high"}}
RETRY_SLEEPS = (5, 15, 30)
UA = {"User-Agent": "aggregate-research/0.1"}

BOOKS = (  # (gutenberg id, tier guess: famous / mid / obscure)
    (1342, "famous"), (2701, "famous"), (84, "famous"), (1661, "famous"),
    (308, "mid"), (155, "mid"), (2398, "mid"), (1023, "mid"),
    (52153, "obscure"), (60432, "obscure"),
    (63311, "obscure"), (69777, "obscure"),
)
QA_PER_BOOK = 3
RETRO_TARGET = 25
RETRO_MIN_BETTORS = 15
RETRO_WINDOW = ("2026-03-01", "2026-08-25")
PRICE_WORDS = ("price", "$", "btc", "bitcoin", "eth", "stock", "s&p", "nasdaq",
               "close above", "close below", "market cap", "all-time high")

FINAL_RE = re.compile(r"FINAL[:\s]*(.+)", re.I)


def extract_final(text):
    hits = FINAL_RE.findall(text or "")
    return hits[-1].strip().strip("'\"` .*") if hits else None


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower().replace("the ", " ")).strip()


# ----------------------------- harvest: recall ------------------------------
def gutenberg_text(book_id):
    r = requests.get(f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt",
                     timeout=60, headers=UA)
    r.raise_for_status()
    t = r.text
    title = author = None
    m = re.search(r"Title:\s*(.+)", t)
    if m:
        title = m.group(1).strip()
    m = re.search(r"Author:\s*(.+)", t)
    if m:
        author = m.group(1).strip()
    if not title:
        m = re.search(r"The Project Gutenberg eBook of (.+?)[\r\n]", t)
        title = m.group(1).strip() if m else f"book {book_id}"
    start = t.find("*** START")
    end = t.find("*** END")
    body = t[t.find("\n", start) + 1: end if end > 0 else len(t)]
    return title, author or "unknown author", body


EXTRACT_PROMPT = """From the passage below, write ONE factual recall question about a specific, distinctive detail (a name, place, number, or object). Rules:
- The exact answer text must appear VERBATIM in the passage, 1-4 words.
- The question must be answerable by someone who remembers the book well, so prefer plot/entity-level facts over passage-local phrasing ("what word follows X" is forbidden).
- The question must NOT contain the answer and must make sense without seeing the passage (name the characters/situation it refers to).
Reply as JSON only: {"question": "...", "answer": "..."}

PASSAGE:
"""


def harvest_recall(rng):
    ex = mistral_client()
    items = []
    for book_id, tier in BOOKS:
        try:
            title, author, body = gutenberg_text(book_id)
        except Exception as e:
            print(f"  skip {book_id}: {e}")
            continue
        if len(body) < 60000:
            print(f"  skip {book_id} ({title[:40]}): too short")
            continue
        got = 0
        tries = 0
        print(f"  {book_id} [{tier}] {title[:60]} — {author[:40]}")
        while got < QA_PER_BOOK and tries < 10:
            tries += 1
            lo = rng.randrange(int(len(body) * 0.15), int(len(body) * 0.8))
            passage = body[lo:lo + 1100]
            try:
                out = ex.complete(
                    [{"role": "user", "content": EXTRACT_PROMPT + passage}],
                    temperature=0.4, json_mode=True, max_tokens=400)
                qa = json.loads(out)
                q, a = qa["question"].strip(), qa["answer"].strip()
            except Exception:
                continue
            if not (1 <= len(a.split()) <= 4) or len(a) > 40:
                continue
            if a.lower() not in passage.lower():          # span check
                continue
            if norm(a) in norm(q):                        # leak check
                continue
            items.append({
                "id": f"recall-{tier}-{book_id}-{got}", "family": "recall",
                "tier": tier, "book": title, "author": author,
                "question": q, "key": a,
                "prompt": (f"From your memory of the book '{title}' by {author}: "
                           f"{q}\nAnswer with just the name/number/phrase; if you "
                           f"do not remember, answer UNKNOWN.\n"
                           f"End your reply with a line 'FINAL: <answer>'."),
            })
            got += 1
    return items


# ----------------------------- harvest: retro -------------------------------
def harvest_retro():
    def ts(datestr):
        return int(dt.datetime.fromisoformat(datestr + "T00:00:00+00:00").timestamp() * 1000)

    lo, hi = ts(RETRO_WINDOW[0]), ts(RETRO_WINDOW[1])
    picked, seen = [], set()
    for offset in (0, 500, 1000):  # API rejects offsets past 1000
        params = {"term": "", "filter": "resolved", "contractType": "BINARY",
                  "sort": "resolve-date", "limit": 500, "offset": offset}
        r = requests.get("https://api.manifold.markets/v0/search-markets",
                         params=params, timeout=60, headers=UA)
        if not r.ok:
            print(f"  manifold page offset={offset}: HTTP {r.status_code}, stopping")
            break
        batch = r.json()
        if not batch:
            break
        for m in batch:
            rt = m.get("resolutionTime") or 0
            if rt < lo or rt > hi:
                continue
            if m.get("resolution") not in ("YES", "NO"):
                continue
            if (m.get("uniqueBettorCount") or 0) < RETRO_MIN_BETTORS:
                continue
            q = m["question"].strip()
            if any(w in q.lower() for w in PRICE_WORDS):
                continue
            if len(q) < 25 or norm(q) in seen:
                continue
            seen.add(norm(q))
            picked.append({
                "id": f"retro-{m['id']}", "family": "retro",
                "question": q, "resolution": m["resolution"],
                "resolution_month": dt.datetime.fromtimestamp(rt / 1000, dt.UTC).strftime("%Y-%m"),
                "created": dt.datetime.fromtimestamp((m.get("createdTime") or 0) / 1000, dt.UTC).strftime("%Y-%m-%d"),
                "bettors": m.get("uniqueBettorCount"),
            })
    # spread across months, earliest-created first within month
    by_month = {}
    for it in picked:
        by_month.setdefault(it["resolution_month"], []).append(it)
    out = []
    months = sorted(by_month)
    while len(out) < RETRO_TARGET and any(by_month.values()):
        for mo in months:
            if by_month[mo] and len(out) < RETRO_TARGET:
                by_month[mo].sort(key=lambda x: x["created"])
                out.append(by_month[mo].pop(0))
    return out


# ----------------------------- grading --------------------------------------
def grade_recall(item, got):
    if got is None:
        return False
    g, k = norm(got), norm(item["key"])
    return bool(g) and (g == k or k in g or (len(g) > 3 and g in k))


# ----------------------------- runner ----------------------------------------
SYSTEM = "Answer from your own knowledge. No tools, no browsing."
_lock = threading.Lock()


def build_calls(bank):
    calls = []
    for it in bank:
        if it["family"] == "recall":
            calls.append((it["id"], it["prompt"], it))
        else:
            q = it["question"]
            calls.append((it["id"] + ":know",
                          f"From your training knowledge: has this already happened / "
                          f"how did it turn out?\n\n\"{q}\"\n\nIf you know the outcome, "
                          f"answer YES or NO (the resolution). If this is after your "
                          f"knowledge cutoff or you are unsure it has occurred, answer "
                          f"UNKNOWN.\nEnd your reply with a line 'FINAL: YES/NO/UNKNOWN'.", it))
            calls.append((it["id"] + ":forecast",
                          f"Forecast, using only what you know (do not assume you know "
                          f"the outcome):\n\n\"{q}\"\n\nGive your probability that this "
                          f"resolves YES, as a number between 0 and 1.\n"
                          f"End your reply with a line 'FINAL: <probability>'.", it))
    return calls


def main():
    rng = random.Random(SEED)
    if "--harvest" in sys.argv:
        print("harvesting recall bank (Gutenberg + extractor)...")
        recall = harvest_recall(rng)
        print(f"  {len(recall)} recall items")
        print("harvesting retro bank (Manifold resolved)...")
        retro = harvest_retro()
        print(f"  {len(retro)} retro items")
        BANK_PATH.write_text(json.dumps(recall + retro, indent=1), encoding="utf-8")
        print(f"bank frozen -> {BANK_PATH.name}")
        return
    bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    if "--bank" in sys.argv:
        for it in bank:
            if it["family"] == "recall":
                print(f"[{it['id']}] ({it['book'][:38]}) {it['question'][:90]}  => {it['key']}")
            else:
                print(f"[{it['id']}] res={it['resolution']} {it['resolution_month']} "
                      f"created {it['created']} bettors {it['bettors']}: {it['question'][:90]}")
        return

    data = json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.is_file() else {
        "responses": {}, "usage": {}}
    calls = build_calls(bank)
    todo = []
    for m in CANDIDATES:
        data["responses"].setdefault(m, {})
        data["usage"].setdefault(m, {"prompt": 0, "completion": 0})
        for cid, prompt, item in calls:
            if cid not in data["responses"][m]:
                todo.append((m, cid, prompt, item))
    print(f"{len(todo)} calls ({len(CANDIDATES)} models x {len(calls)})")
    clients = {m: openrouter_client(m) for m in CANDIDATES}
    no_effort = set()

    def work(job):
        m, cid, prompt, item = job
        extra = None if m in no_effort else EFFORT
        text = None
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
        rec = {"extracted": got, "text": text}
        if item["family"] == "recall":
            rec["correct"] = grade_recall(item, got)
        with _lock:
            data["responses"][m][cid] = rec
            if text:
                data["usage"][m]["prompt"] += result.prompt_tokens or 0
                data["usage"][m]["completion"] += result.completion_tokens or 0
            done = sum(len(v) for v in data["responses"].values())
            DATA_PATH.write_text(json.dumps(data, indent=1), encoding="utf-8")
            print(f"[{done:4d}/{len(CANDIDATES)*len(calls)}] {m:30s} {cid:34s} "
                  f"{str(got)[:28]}")

    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(work, todo))
    print("run complete")


if __name__ == "__main__":
    main()

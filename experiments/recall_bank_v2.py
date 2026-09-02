"""Production long-tail recall bank (v2, 2026-09-02).

Same instrument as the worldmodel smoke recall axis (closed-book facts from
Project Gutenberg books, keys verified as literal spans, FINAL-line answers,
containment grading) scaled to ~300 items on a measured obscurity ladder.

Ladder = Wikipedia pageviews of the book's own article (Jun-Aug 2026 monthly
mean), five rungs: canon >= 30k, known >= 5k, mid >= 800, obscure < 800,
deep = no article. Cultural exposure, not Gutenberg download counts (the
Gutendex API is unusable from this host).

Quality gates beyond the smoke: extractor asked for entity-level keys,
stoplist + author-name + small-number rejection, a validator pass, and a
free tiny model run as a guessability floor.

    MISTRAL_API_KEY=... python -m experiments.recall_bank_v2 --ladder
    MISTRAL_API_KEY=... python -m experiments.recall_bank_v2 --harvest
    python -m experiments.recall_bank_v2 --bank
    OPENROUTER_API_KEY=... python -m experiments.recall_bank_v2 --run [slug ...]
    python -m experiments.recall_bank_v2 --report
"""
from __future__ import annotations

import csv
import json
import os
import random
import re
import sys
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from viberank.clients import ProviderError, mistral_client, openrouter_client

EXP = Path(__file__).resolve().parent
CATALOG = EXP / "pg_catalog.csv"
BOOKS_PATH = EXP / "recall_v2_books.json"
BANK_PATH = EXP / "recall_v2_bank.json"
DATA_PATH = EXP / "recall_v2_data.json"
SEED = 20260902
UA = {"User-Agent": "aggregate-research/0.1 (contact: research@theaggregate.ai)"}

TIERS = ("canon", "known", "mid", "obscure", "deep")
VIEW_CUTS = ((30000, "canon"), (5000, "known"), (800, "mid"), (-1, "obscure"))
BOOKS_PER_TIER = 12
RESERVE_PER_TIER = 20
QA_PER_BOOK = 5
QA_TRIES = 16
MIN_BODY = 60000

FINAL_RE = re.compile(r"FINAL[:\s]*(.+)", re.I)
STOP_KEYS = {"he", "she", "it", "they", "him", "her", "them", "man", "woman", "boy", "girl", "servant", "house",
             "home", "morning", "night", "day", "evening", "money", "letter", "door", "room", "father", "mother",
             "son", "daughter", "wife", "husband", "friend", "yes", "no", "none", "nothing", "one", "two", "three",
             "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "twenty", "hundred",
             "thousand", "first", "second", "third", "the", "a", "an", "god", "love", "death", "war", "sea", "town",
             "city", "village", "church", "school", "horse", "dog", "cat", "king", "queen", "doctor", "captain"}
_lock = threading.Lock()


def extract_final(text):
    hits = FINAL_RE.findall(text or "")
    return hits[-1].strip().strip("'\"` .*") if hits else None


def extract_lenient(text):
    """FINAL line if present; else a short single-line reply is the answer
    (qwen3.6-plus often answers 'Kurtz' with no FINAL line)."""
    got = extract_final(text)
    if got is not None:
        return got
    t = (text or "").strip().strip("'\"` .*")
    return t if t and len(t) <= 60 and chr(10) not in t else None


def norm(s):
    s = (s or "").lower().replace("-", " ").replace("’", "'").replace("the ", " ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", s)).strip()


def grade(item, got):
    if got is None:
        return False
    g, k = norm(got), norm(item["key"])
    if not g or g.startswith("unknown"):
        return False
    return g == k or k in g or (len(g) > 3 and g in k)


# ----------------------------- ladder ---------------------------------------
def load_catalog():
    rows = list(csv.DictReader(open(CATALOG, encoding="utf-8")))
    out = []
    for x in rows:
        if x["Language"] != "en" or x["Type"] != "Text" or not x["Authors"] or not x["Title"]:
            continue
        first_author = x["Authors"].split(";")[0].strip()
        if first_author.split(",")[0].strip() in ("Various", "Anonymous", "Unknown"):
            continue
        subj = x["Subjects"].lower()
        if "fiction" not in subj:
            continue
        if any(b in subj for b in ("periodicals", "poetry", "drama", "comic books", "plays", "juvenile poetry")):
            continue
        tl = x["Title"].lower()
        if any(b in tl for b in ("volume ", "vol.", "vol ", "part 1", "part 2", "part i", "index", "selections",
                                 "anthology", "collected", "complete works", "stories", "tales")):
            continue
        out.append(x)
    return out


def short_title(title):
    t = title.replace("\n", " ").replace("\r", " ")
    t = re.split(r"[;:]", t)[0].strip()
    return re.sub(r"\s+", " ", t)


def _intro_mentions_book(page_title, author):
    """For one-word titles: accept the page only if its intro reads like the book."""
    try:
        r = requests.get("https://en.wikipedia.org/w/api.php", timeout=30, headers=UA, params={
            "action": "query", "titles": page_title, "prop": "extracts", "exintro": 1, "explaintext": 1,
            "format": "json"})
        intro = " ".join(p.get("extract", "") for p in r.json()["query"]["pages"].values()).lower()
    except Exception:
        return False
    surname = (author or "").split(",")[0].strip().lower()
    return any(w in intro for w in ("novel", "novella", "book", "short story")) and (not surname or surname in intro)


def wiki_lookup(title, author=""):
    """Return (wiki_title, monthly_views) for the book's own article, or (None, None)."""
    st = short_title(title)
    cands = [st, f"{st} (novel)", title.strip()]
    try:
        r = requests.get("https://en.wikipedia.org/w/api.php", timeout=30, headers=UA, params={
            "action": "query", "titles": "|".join(cands[:3]), "redirects": 1, "prop": "pageprops",
            "ppprop": "disambiguation", "format": "json"})
        pages = r.json().get("query", {}).get("pages", {})
    except Exception:
        return None, None
    found = None
    single_word = len(st.split()) == 1
    for p in pages.values():
        if "missing" in p or ("pageprops" in p and "disambiguation" in p["pageprops"]):
            continue
        pt = p.get("title", "")
        if single_word and "(novel)" not in pt.lower() and not _intro_mentions_book(pt, author):
            continue  # "Hagar", "Heart": a bare one-word page is usually not the book; Dracula/Carmilla pass the intro check
        if norm(pt).replace(" novel", "") == norm(st) or norm(pt) == norm(title) or pt.lower().startswith(st.lower()):
            found = pt
            break
    if not found:
        return None, None
    try:
        r = requests.get("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/"
                         f"all-access/user/{urllib.parse.quote(found.replace(' ', '_'), safe='')}/monthly/"
                         "2026060100/2026083100", timeout=30, headers=UA)
        items = r.json().get("items", []) if r.ok else []
        views = sum(i["views"] for i in items) / max(1, len(items)) if items else 0.0
    except Exception:
        views = 0.0
    return found, views


def tier_of(wiki, views):
    if wiki is None:
        return "deep"
    for cut, name in VIEW_CUTS:
        if views >= cut:
            return name
    return "obscure"


def build_ladder(rng):
    rows = load_catalog()
    print(f"catalog fiction candidates: {len(rows)}")
    classic = [x for x in rows if "best books" in x["Bookshelves"].lower() or "classics" in x["Bookshelves"].lower()]
    classic_ids = {x["Text#"] for x in classic}
    rest = [x for x in rows if x["Text#"] not in classic_ids]
    sample = rng.sample(classic, min(160, len(classic))) + rng.sample(rest, min(320, len(rest)))
    print(f"looking up {len(sample)} books on Wikipedia ({len(classic)} classics-shelf, {len(rest)} other)")
    looked = []

    def work(x):
        w, v = wiki_lookup(x["Title"], x["Authors"])
        return {"id": int(x["Text#"]), "title": x["Title"], "authors": x["Authors"], "subjects": x["Subjects"],
                "bookshelves": x["Bookshelves"], "wiki": w, "views": v, "tier": tier_of(w, v)}

    with ThreadPoolExecutor(max_workers=6) as pool:
        for i, rec in enumerate(pool.map(work, sample)):
            looked.append(rec)
            if i % 50 == 0:
                print(f"  {i}/{len(sample)}")
    by_tier = {t: [b for b in looked if b["tier"] == t] for t in TIERS}
    print("tier counts:", {t: len(v) for t, v in by_tier.items()})
    chosen = {}
    for t in TIERS:
        pool_t = by_tier[t][:]
        rng.shuffle(pool_t)
        picked, authors = [], set()
        for b in pool_t:
            a = b["authors"].split(";")[0].split(",")[0].strip()
            if a in authors:
                continue
            authors.add(a)
            picked.append(b)
            if len(picked) >= RESERVE_PER_TIER:
                break
        chosen[t] = picked
        print(f"  {t:8s} reserve {len(picked)}: " + "; ".join(f"{b['title'][:28]} ({int(b['views'] or 0)})" for b in picked[:6]))
    BOOKS_PATH.write_text(json.dumps({"seed": SEED, "cuts": VIEW_CUTS, "chosen": chosen, "looked": looked}, indent=1),
                          encoding="utf-8")
    print(f"ladder saved -> {BOOKS_PATH.name}")


# ----------------------------- harvest --------------------------------------
def gutenberg_text(book_id):
    r = requests.get(f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt", timeout=90, headers=UA)
    r.raise_for_status()
    t = r.text
    m = re.search(r"Title:\s*(.+)", t)
    title = m.group(1).strip() if m else None
    m = re.search(r"Author:\s*(.+)", t)
    author = m.group(1).strip() if m else None
    if not title:
        m = re.search(r"The Project Gutenberg eBook of (.+?)[\r\n]", t)
        title = m.group(1).strip() if m else f"book {book_id}"
    start = t.find("*** START")
    end = t.find("*** END")
    body = t[t.find("\n", start) + 1: end if end > 0 else len(t)]
    return title, author or "unknown author", body


EXTRACT_PROMPT = """From the passage below, write ONE closed-book recall question about a specific, distinctive detail of this book. Rules:
- The answer must be a specific entity: a character's name, a place, a named object, a title, or a distinctive number (like a sum of money or a year). Not a generic word.
- The exact answer text must appear VERBATIM in the passage, 1-4 words.
- Someone who remembers the book well (but does not have the text) must be able to answer: refer to characters and the situation by name, never to "the passage" or "this scene"; phrasing-local questions ("what word follows X") are forbidden.
- The question must NOT contain the answer.
Reply as JSON only: {"question": "...", "answer": "..."}

PASSAGE:
"""

VALIDATE_PROMPT = """You are checking a closed-book trivia question about the book '{title}' by {author}.
Question: {q}
Reference answer: {key}
Is this a fair question for someone who remembers the book well but has no text in front of them? Fail it if: the answer is a generic word rather than a specific entity, place, object, title or distinctive number; the question needs the surrounding passage to make sense; the answer is the author's own name; the question is ambiguous or has several plausible answers; the answer could be guessed from the question alone without knowing the book.
Reply as JSON only: {{"ok": true or false, "reason": "..."}}"""


def key_ok(key, question, author):
    k = norm(key)
    if not k or k in STOP_KEYS or len(key) > 40 or not (1 <= len(key.split()) <= 4):
        return False
    if k in norm(question):
        return False
    if k.isdigit() and int(k) < 100:
        return False
    for tok in re.findall(r"[a-z]+", norm(author)):
        if len(tok) > 2 and tok == k:
            return False
    return True


def harvest_book(ex, rng, book, tier):
    try:
        title, author, body = gutenberg_text(book["id"])
    except Exception as e:
        return None, f"download failed: {str(e)[:60]}"
    if len(body) < MIN_BODY:
        return None, f"too short ({len(body)})"
    items, tries = [], 0
    while len(items) < QA_PER_BOOK and tries < QA_TRIES:
        tries += 1
        lo = rng.randrange(int(len(body) * 0.10), int(len(body) * 0.90))
        passage = body[lo:lo + 1200]
        try:
            out = ex.complete([{"role": "user", "content": EXTRACT_PROMPT + passage}],
                              temperature=0.5, json_mode=True, max_tokens=300)
            qa = json.loads(out)
            q, a = qa["question"].strip(), str(qa["answer"]).strip()
        except Exception:
            continue
        if a.lower() not in passage.lower() or not key_ok(a, q, author):
            continue
        try:
            v = json.loads(ex.complete(
                [{"role": "user", "content": VALIDATE_PROMPT.format(title=title, author=author, q=q, key=a)}],
                temperature=0.0, json_mode=True, max_tokens=200))
            if not v.get("ok"):
                continue
        except Exception:
            continue
        if any(norm(a) == norm(it["key"]) for it in items):
            continue
        items.append({
            "id": f"r2-{tier}-{book['id']}-{len(items)}", "family": "recall", "tier": tier,
            "book": title, "author": author, "gutenberg_id": book["id"], "wiki": book["wiki"],
            "views": round(book["views"] or 0), "question": q, "key": a,
            "prompt": (f"From your memory of the book '{title}' by {author}: {q}\n"
                       f"Answer with just the name/number/phrase; if you do not remember, answer UNKNOWN.\n"
                       f"End your reply with a line 'FINAL: <answer>'."),
        })
    return items, f"{len(items)} items in {tries} tries"


def harvest(rng):
    ladder = json.loads(BOOKS_PATH.read_text(encoding="utf-8"))
    ex = mistral_client()
    bank = []
    for tier in TIERS:
        books = ladder["chosen"][tier][:BOOKS_PER_TIER + 4]  # a few spares for download/short failures
        seeds = [rng.random() for _ in books]

        def work(job):
            book, seed = job
            items, msg = harvest_book(ex, random.Random(seed), book, tier)
            with _lock:
                print(f"  [{tier}] {book['title'][:50]:50s} views {int(book['views'] or 0):>7} -> {msg}", flush=True)
            return book, items

        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(work, zip(books, seeds)))
        got_books = 0
        for book, items in results:  # ladder order, first BOOKS_PER_TIER usable books
            if got_books >= BOOKS_PER_TIER:
                break
            if items and len(items) >= 3:
                bank.extend(items)
                got_books += 1
        print(f"{tier}: {got_books} books, {sum(1 for i in bank if i['tier'] == tier)} items", flush=True)
    # mechanical self-test of grading on the frozen bank
    for it in bank:
        assert grade(it, it["key"]) and not grade(it, "UNKNOWN") and not grade(it, "zzz-not-an-answer"), it["id"]
    BANK_PATH.write_text(json.dumps(bank, indent=1), encoding="utf-8")
    print(f"bank frozen: {len(bank)} items -> {BANK_PATH.name}")


# ----------------------------- run -------------------------------------------
PANEL = {  # slug: (site Elo budget-unified 2026-09-02, ($/M in, $/M out))
    "anthropic/claude-fable-5": (2037, (10.0, 50.0)),
    "anthropic/claude-opus-5": (2058, (5.0, 25.0)),
    "anthropic/claude-fable-5.1": (2053, (10.0, 50.0)),
    "anthropic/claude-opus-4.8": (1934, (5.0, 25.0)),
    "anthropic/claude-haiku-4.5": (1686, (1.0, 5.0)),
    "openai/gpt-5.4": (1879, (2.5, 15.0)),
    "openai/gpt-5.4-mini": (1776, (0.75, 4.5)),
    "openai/gpt-5.5": (1936, (5.0, 30.0)),
    "openai/gpt-5.2": (1817, (1.75, 14.0)),
    "qwen/qwen3.6-plus": (1813, (0.33, 1.95)),
    "qwen/qwen3.6-35b-a3b": (1701, (0.10, 0.90)),
    "deepseek/deepseek-v4-pro": (1836, (1.03, 2.05)),
    "moonshotai/kimi-k2.6": (1834, (0.95, 4.0)),
    "moonshotai/kimi-k2-0905": (1722, (0.6, 2.5)),
    "openai/gpt-oss-120b": (1665, (0.04, 0.17)),
    "liquid/lfm-2.5-2.6b:free": (0, (0.0, 0.0)),   # guessability floor
}
FLOOR = "liquid/lfm-2.5-2.6b:free"
EFFORT = {"reasoning": {"effort": "high"}}
SYSTEM = "Answer from your own knowledge. No tools, no browsing."
RETRY_SLEEPS = (5, 15, 30)
COST_CEILING_USD = float(os.environ.get("RECALL_V2_CEILING", "40"))


def est_cost(data):
    total = 0.0
    for m, u in data["usage"].items():
        pi, po = PANEL.get(m, (0, (1.0, 5.0)))[1]
        total += u["prompt"] / 1e6 * pi + u["completion"] / 1e6 * po
    return total


def run(models):
    bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    if os.environ.get("RECALL_V2_SMOKE"):
        bank = bank[:5]
    data = json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.is_file() else {
        "seed": SEED, "effort": "high", "responses": {}, "usage": {}, "effort_applied": {}}
    todo = []
    for m in models:
        data["responses"].setdefault(m, {})
        data["usage"].setdefault(m, {"prompt": 0, "completion": 0})
        for it in bank:
            if it["id"] not in data["responses"][m]:
                todo.append((m, it))
    print(f"{len(todo)} calls ({len(models)} models x {len(bank)} items, resumable); ceiling ${COST_CEILING_USD:.0f}")
    clients = {m: openrouter_client(m) for m in models}
    no_effort = set()

    def work(job):
        m, it = job
        if est_cost(data) > COST_CEILING_USD:
            return "ceiling"
        extra = None if m in no_effort else EFFORT
        text, result, refusal = None, None, None
        for attempt, sleep_s in enumerate((0,) + RETRY_SLEEPS):
            if sleep_s:
                time.sleep(sleep_s)
            try:
                result = clients[m].complete_with_usage(
                    [{"role": "system", "content": SYSTEM}, {"role": "user", "content": it["prompt"]}],
                    temperature=0.2, max_tokens=16000, extra=extra, timeout=300.0)
                if getattr(result, "refusal", None) or getattr(result, "finish_reason", None) == "content_filter":
                    refusal = result.refusal or result.finish_reason
                    break
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
                print(f"  {m} {it['id']} attempt {attempt + 1}: {msg[:90]}")
        got = extract_final(text) if text else None
        rec = {"tier": it["tier"], "extracted": got, "correct": grade(it, got) if text else None,
               "completion_tokens": result.completion_tokens if (result and text) else None,
               "refusal": refusal, "text": text}
        with _lock:
            data["responses"][m][it["id"]] = rec
            data["effort_applied"][m] = extra is not None
            if text and result:
                data["usage"][m]["prompt"] += result.prompt_tokens or 0
                data["usage"][m]["completion"] += result.completion_tokens or 0
            DATA_PATH.write_text(json.dumps(data, indent=1), encoding="utf-8")
            done = sum(len(v) for v in data["responses"].values())
            st = "PASS" if rec["correct"] else ("CENS" if text is None else "fail")
            print(f"[{done:5d}] {m:30s} {it['id']:24s} {st:4s} {str(got)[:24]:24s} ~${est_cost(data):.2f}")
        return None

    with ThreadPoolExecutor(max_workers=int(os.environ.get("RECALL_V2_WORKERS", "6"))) as pool:
        msgs = list(pool.map(work, todo))
    if "ceiling" in msgs:
        print("COST CEILING HIT - run stopped early (resumable)")
    print("run complete")


# ----------------------------- judged re-grade ------------------------------
JUDGE_PATH = EXP / "recall_v2_judgments.json"
JUDGE_PROMPT = """Book: '{title}' by {author}.
Question: {q}
Reference answer (a verbatim span from the book): {key}
Candidate answer: {cand}
Does the candidate answer refer to the same entity, place, object or fact as the reference? Accept alternate names, titles, spellings, or a name that uniquely identifies the same referent (e.g. a character's first name when the reference gives the full name). Reject a different entity, a vaguer category, or a guess that merely overlaps in wording.
Reply as JSON only: {{"equivalent": true or false, "reason": "..."}}"""


def judge():
    """Second-pass grading for strict-fail cells with a committed answer.
    Writes to its own file so it never races the runner."""
    bank = {i["id"]: i for i in json.loads(BANK_PATH.read_text(encoding="utf-8"))}
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    judg = json.loads(JUDGE_PATH.read_text(encoding="utf-8")) if JUDGE_PATH.is_file() else {}
    ex = mistral_client()
    todo = []
    for m, cells in data["responses"].items():
        for iid, r in cells.items():
            if r.get("text") is None or iid not in bank:
                continue
            got = extract_lenient(r.get("text"))
            if got and not grade(bank[iid], got) and not norm(got).startswith("unknown") and f"{m}|{iid}" not in judg:
                todo.append((m, iid, got))
    print(f"{len(todo)} strict-fail committed answers to judge ({len(judg)} already judged)")

    def work(job):
        m, iid, got = job
        it = bank[iid]
        try:
            v = json.loads(ex.complete([{"role": "user", "content": JUDGE_PROMPT.format(
                title=it["book"], author=it["author"], q=it["question"], key=it["key"], cand=got[:120])}],
                temperature=0.0, json_mode=True, max_tokens=150))
            eq, reason = bool(v.get("equivalent")), str(v.get("reason", ""))[:120]
        except Exception as e:
            eq, reason = None, f"judge error {str(e)[:60]}"
        with _lock:
            judg[f"{m}|{iid}"] = {"equivalent": eq, "reason": reason, "candidate": got[:120]}
            if len(judg) % 25 == 0:
                JUDGE_PATH.write_text(json.dumps(judg, indent=1), encoding="utf-8")
        return eq

    with ThreadPoolExecutor(max_workers=4) as pool:
        res = list(pool.map(work, todo))
    JUDGE_PATH.write_text(json.dumps(judg, indent=1), encoding="utf-8")
    print(f"judged: {sum(1 for r in res if r)} equivalent, {sum(1 for r in res if r is False)} not, {sum(1 for r in res if r is None)} errors")


# ----------------------------- report ---------------------------------------
def report():
    import math
    import numpy as np
    bank = {i["id"]: i for i in json.loads(BANK_PATH.read_text(encoding="utf-8"))}
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    judg = json.loads(JUDGE_PATH.read_text(encoding="utf-8")) if JUDGE_PATH.is_file() else {}
    ids = sorted(bank)
    resp = data["responses"]
    # recompute strict grades from the stored FINAL answers with the current norm()
    n_len = 0
    for m, cells in resp.items():
        for iid, r in cells.items():
            if r.get("text") is not None and iid in bank:
                got = extract_lenient(r.get("text"))
                if got != r.get("extracted"):
                    n_len += 1
                    r["extracted"] = got
                r["correct"] = grade(bank[iid], got)
    print(f"lenient extraction recovered {n_len} bare-answer cells without a FINAL line")
    lenient = "--strict" not in sys.argv
    if lenient and judg:  # fold judged equivalences into correctness
        n_up = 0
        for m, cells in resp.items():
            for iid, r in cells.items():
                j = judg.get(f"{m}|{iid}")
                if r.get("correct") is False and j and j.get("equivalent"):
                    r["correct"] = True
                    n_up += 1
        print(f"lenient grading: {n_up} strict-fail cells accepted as equivalent by the judge (use --strict to disable)")
    models = [m for m in PANEL if m in resp and len(resp[m]) >= len(ids) * 0.9]
    floor_ok = {i for i in ids if resp.get(FLOOR, {}).get(i, {}).get("correct")}
    print(f"{len(ids)} items; {len(models)} models with >=90% coverage; guessability floor solved {len(floor_ok)} items")

    def acc(m, subset):
        v = [resp[m][i]["correct"] for i in subset if i in resp[m] and resp[m][i]["correct"] is not None]
        return (sum(v) / len(v)) if v else float("nan"), len(v)

    print(f"\n{'model':30s} {'Elo':>5} {'all':>6} " + " ".join(f"{t:>8}" for t in TIERS) + f" {'cens':>5} {'ctok':>6}")
    accs = {}
    for m in sorted(models, key=lambda m: -PANEL[m][0]):
        a, n = acc(m, ids)
        accs[m] = a
        tiers = " ".join(f"{acc(m, [i for i in ids if bank[i]['tier'] == t])[0]:8.2f}" for t in TIERS)
        cens = sum(1 for i in ids if i in resp[m] and resp[m][i]["correct"] is None)
        ct = [resp[m][i]["completion_tokens"] for i in ids if i in resp[m] and resp[m][i].get("completion_tokens")]
        print(f"{m:30s} {PANEL[m][0]:5d} {a:6.3f} {tiers} {cens:5d} {np.mean(ct) if ct else 0:6.0f}")
    counts = {}
    real = [m for m in models if m != FLOOR]
    for i in ids:
        c = sum(1 for m in real if resp[m].get(i, {}).get("correct"))
        counts[c] = counts.get(c, 0) + 1
    print("\nitems by number of models solving:", dict(sorted(counts.items())))
    flag = [m for m in real if PANEL[m][0] >= 1800]
    if len(flag) >= 5:
        errs = []
        for held in flag:
            others = [m for m in flag if m != held]
            x = np.array([accs[m] for m in others])
            y = np.array([PANEL[m][0] for m in others])
            b, a0 = np.polyfit(x, y, 1)
            errs.append(abs(a0 + b * accs[held] - PANEL[held][0]))
        rx = np.argsort(np.argsort([accs[m] for m in flag]))
        ry = np.argsort(np.argsort([PANEL[m][0] for m in flag]))
        print(f"\nflagship line (n={len(flag)}): LOO-affine MAE {np.mean(errs):.0f} Elo, rho {np.corrcoef(rx, ry)[0, 1]:+.2f}")
    pairs = [("anthropic/claude-fable-5", "anthropic/claude-opus-5"), ("anthropic/claude-fable-5", "anthropic/claude-fable-5.1"),
             ("anthropic/claude-fable-5.1", "anthropic/claude-opus-5"), ("anthropic/claude-opus-4.8", "anthropic/claude-haiku-4.5"),
             ("openai/gpt-5.4", "openai/gpt-5.4-mini"), ("qwen/qwen3.6-plus", "qwen/qwen3.6-35b-a3b"),
             ("openai/gpt-5.5", "openai/gpt-5.4"), ("anthropic/claude-fable-5", "anthropic/claude-opus-4.8"),
             ("anthropic/claude-fable-5", "openai/gpt-5.4"), ("openai/gpt-5.4", "anthropic/claude-opus-4.8"),
             ("anthropic/claude-opus-4.8", "openai/gpt-5.4-mini"), ("openai/gpt-5.2", "deepseek/deepseek-v4-pro"),
             ("deepseek/deepseek-v4-pro", "moonshotai/kimi-k2.6"), ("openai/gpt-5.5", "anthropic/claude-fable-5")]
    twins = ("anthropic/claude-fable-5", "anthropic/claude-fable-5.1")
    f_noise = 0.08
    if all(t in models for t in twins):
        ca = [i for i in ids if resp[twins[0]].get(i, {}).get("correct") is not None
              and resp[twins[1]].get(i, {}).get("correct") is not None]
        TA = np.array([resp[twins[0]][i]["correct"] for i in ca], dtype=bool)
        TB = np.array([resp[twins[1]][i]["correct"] for i in ca], dtype=bool)
        f_noise = ((TA & ~TB).sum() / max(1, TA.sum()) + (~TA & TB).sum() / max(1, TB.sum())) / 2
    print()
    print(f"noise floor from the same-library twins (Fable 5 / 5.1): f = {f_noise:.3f}, the share of one twin's correct items the other misses")
    print(f"{'pair (A vs B)':46s} {'both':>5} {'onlyA':>6} {'onlyB':>6} {'A-B':>7} {'P(A>B)':>7} {'E[onlyB]':>9} {'obs/exp':>8} {'P(>=obs)':>9}")
    rng = random.Random(SEED)
    for a, b in pairs:
        if a not in models or b not in models:
            continue
        common = [i for i in ids if resp[a].get(i, {}).get("correct") is not None
                  and resp[b].get(i, {}).get("correct") is not None]
        A = np.array([resp[a][i]["correct"] for i in common], dtype=bool)
        B = np.array([resp[b][i]["correct"] for i in common], dtype=bool)
        both, oa, ob = int((A & B).sum()), int((A & ~B).sum()), int((~A & B).sum())
        diffs = []
        for _ in range(1000):
            idx = np.array([rng.randrange(len(common)) for _ in common])
            diffs.append(A[idx].mean() - B[idx].mean())
        p_a = float(np.mean([d > 0 for d in diffs]))
        nb = int(B.sum())
        exp_b = nb * f_noise
        p_ge = 1 - sum(math.comb(nb, k) * f_noise ** k * (1 - f_noise) ** (nb - k) for k in range(ob))
        ratio = ob / exp_b if exp_b else float("nan")
        tag = "" if a.split("/")[0] == b.split("/")[0] else "  cross-lab"
        print(f"{a.split('/')[-1] + ' vs ' + b.split('/')[-1]:46s} {both:5d} {oa:6d} {ob:6d} {A.mean() - B.mean():+7.3f} {p_a:7.2f} {exp_b:9.1f} {ratio:8.2f} {p_ge:9.3f}{tag}")
    print("(E[onlyB] = B's correct count x f: only-B items expected if B's library were nested in A's with twin-level retrieval noise;")
    print(" obs/exp near 1 = nested up to noise; obs/exp >> 1 with small P(>=obs) = B knows things A's corpus does not.)")
    print(f"\nestimated spend so far: ${est_cost(data):.2f}")


if __name__ == "__main__":
    rng = random.Random(SEED)
    if "--ladder" in sys.argv:
        build_ladder(rng)
    elif "--harvest" in sys.argv:
        harvest(rng)
    elif "--bank" in sys.argv:
        for it in json.loads(BANK_PATH.read_text(encoding="utf-8")):
            print(f"[{it['id']}] ({it['book'][:34]}, {it['views']}) {it['question'][:88]}  => {it['key']}")
    elif "--judge" in sys.argv:
        judge()
    elif "--report" in sys.argv:
        report()
    elif "--run" in sys.argv:
        slugs = [a for a in sys.argv[2:] if "/" in a] or list(PANEL)
        run(slugs)
    else:
        print(__doc__)

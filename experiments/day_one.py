"""Day-one battery: run one new model through every live fresh instrument.

Owner rule (2026-09-01): whenever a new free model appears on OpenRouter (or
another API provider) it gets run on all our benchmarks. This is the runner:
the same protocols the Fable 5.1 day-one probes used (lab record section K),
generalised to any slug and hardened for free routes (20 req/min and 1,000
req/day on OpenRouter `:free` routes, served output ceilings, effort params
that a route may reject).

Steps (all resumable: every instrument skips cells already on file, so a run
that trips the free-route day cap is finished by re-running tomorrow):

  recall     worldmodel_smoke bank, 36 recall + 25 v1 retro items (86 calls)
             -> worldmodel_smoke_data.json
  retro      retro_today bank: KNOW pass on all curated questions, FORECAST
             on the panel-frozen shared set (~55 calls) -> retro_today_data.json
  domain     80-item domain bank with per-cell tokens (distilled_efficiency
             protocol) -> distilled_efficiency_data.json
  frontier   24-item inversion/execution ladder -> frontier_ladder_data.json
  portfolio  30-item five-family ladder -> portfolio_ladder_data.json
  interview  Sol-authored k=25 ladder, Mistral-graded (~$5-14 of examiner
             cost, so opt-in with --interview) -> pilot_deep_data.json

Slugs: an OpenRouter id (`vendor/model`, `vendor/model:free`), or
`mistral/<native-id>` for Mistral's direct API (free tier on this account).
Keys come from OPENROUTER_API_KEY / MISTRAL_API_KEY, else from the leaderboard
repo's pipeline/config/*-key.txt (LLM_LEADERBOARD_DIR, default sibling dir).

    python -m experiments.day_one nvidia/nemotron-3.5-lightning:free
    python -m experiments.day_one mistral/mistral-small-2603 --elo 1574
    python -m experiments.day_one <slug> --steps recall,domain
    python -m experiments.day_one <slug> --interview
    python -m experiments.day_one <slug> --plan      # what would run, no calls
    python -m experiments.day_one <slug> --report    # summary only, no calls

The summary lands in experiments/day_one_runs/<slug>.json and .md, with a
draft dossier line for research/what-we-know-about-llm-benchmarks.md section 6.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import statistics
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from viberank.clients import (
    DEFAULT_MAX_TOKENS,
    ProviderError,
    mistral_client,
    openrouter_client,
)

EXP = Path(__file__).resolve().parent
RUNS_DIR = EXP / "day_one_runs"
LEADERBOARD_DIR = Path(
    os.environ.get("LLM_LEADERBOARD_DIR") or EXP.parents[1] / "llm-leaderboard"
)
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
UA = {"User-Agent": "aggregate-research/0.1"}

CORE_STEPS = ("recall", "retro", "domain", "frontier", "portfolio")
OPTIONAL_STEPS = ("interview",)
CALLS = {
    "recall": 86,
    "retro": 55,
    "domain": 80,
    "frontier": 24,
    "portfolio": 30,
    "interview": 25,
}
FREE_RPM = 18  # OpenRouter caps :free routes at 20 requests/minute
MISTRAL_RPM = 50  # Mistral's free tier: ~1 request/second
FREE_DAILY_CAP = 1000  # OpenRouter :free routes, account with >= $10 credits
RETRY_429_SLEEPS = (10, 20, 40, 60, 90)
DAILY_CAP_MARKERS = ("per-day", "per day", "daily")
# worldmodel_analysis.BAD_ITEMS: extractor junk excluded from recall scoring.
BAD_RECALL_ITEMS = {"recall-mid-155-1", "recall-obscure-60432-0"}


# --------------------------------------------------------------------------
# keys, slugs, catalog
# --------------------------------------------------------------------------


def ensure_keys() -> dict[str, bool]:
    """Fill OPENROUTER_API_KEY / MISTRAL_API_KEY from the leaderboard key files
    when the environment does not carry them. Returns which keys are set."""
    sources = (
        ("OPENROUTER_API_KEY", ("OPENROUTER_KEY",), "openrouter-key.txt"),
        ("MISTRAL_API_KEY", (), "mistral-key.txt"),
    )
    present = {}
    for env, aliases, filename in sources:
        value = os.environ.get(env, "").strip()
        for alias in aliases:
            value = value or os.environ.get(alias, "").strip()
        if not value:
            path = LEADERBOARD_DIR / "pipeline" / "config" / filename
            if path.is_file():
                value = path.read_text(encoding="utf-8").strip()
        if value:
            os.environ[env] = value
        present[env] = bool(value)
    return present


def parse_slug(slug: str) -> tuple[str, str]:
    """('mistral', native_id) for mistral/<id>; ('openrouter', slug) otherwise."""
    if slug.startswith("mistral/"):
        return "mistral", slug.split("/", 1)[1]
    return "openrouter", slug


def safe_name(slug: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", slug.replace("/", "__"))


def openrouter_catalog_entry(slug: str) -> dict | None:
    try:
        payload = requests.get(OPENROUTER_MODELS_URL, headers=UA, timeout=30).json()
    except Exception as exc:  # offline: the run still works, without the facts
        print(f"  (OpenRouter catalog unavailable: {exc})")
        return None
    for model in payload.get("data") or []:
        if model.get("id") == slug:
            return model
    return None


def catalog_facts(entry: dict | None) -> dict:
    if not entry:
        return {}
    top = entry.get("top_provider") or {}
    arch = entry.get("architecture") or {}
    pricing = entry.get("pricing") or {}

    def per_million(key):
        try:
            return round(float(pricing.get(key) or 0) * 1e6, 4)
        except (TypeError, ValueError):
            return None

    created = entry.get("created")
    return {
        "name": entry.get("name"),
        "created": (
            datetime.fromtimestamp(created, tz=timezone.utc).strftime("%Y-%m-%d")
            if isinstance(created, (int, float)) and created > 0
            else None
        ),
        "context_length": entry.get("context_length") or top.get("context_length"),
        "max_completion_tokens": top.get("max_completion_tokens"),
        "input_modalities": list(arch.get("input_modalities") or []),
        "supports_reasoning": "reasoning" in (entry.get("supported_parameters") or []),
        "price_per_m": (per_million("prompt"), per_million("completion")),
        "expires": entry.get("expiration_date"),
        "hugging_face_id": entry.get("hugging_face_id"),
    }


# --------------------------------------------------------------------------
# free-route guards
# --------------------------------------------------------------------------


class DailyCapReached(RuntimeError):
    """The provider's per-day request cap: stop cleanly, resume tomorrow.

    Deliberately not a ProviderError: the instruments retry ProviderErrors
    three times with sleeps, which would burn minutes per remaining cell.
    A RuntimeError falls straight out of their worker pools (state is saved
    per cell, so nothing is lost)."""


class RateLimiter:
    """Sliding-window request pacer shared by every worker thread of a run."""

    def __init__(self, per_minute: int, *, clock=time.monotonic, sleep=time.sleep):
        self.per_minute = per_minute
        self._stamps: collections.deque[float] = collections.deque()
        self._lock = threading.Lock()
        self._clock = clock
        self._sleep = sleep

    def acquire(self) -> float:
        """Block until a slot is free; return the seconds spent waiting."""
        waited = 0.0
        while True:
            with self._lock:
                now = self._clock()
                while self._stamps and now - self._stamps[0] >= 60.0:
                    self._stamps.popleft()
                if len(self._stamps) < self.per_minute:
                    self._stamps.append(now)
                    return waited
                delay = 60.0 - (now - self._stamps[0]) + 0.05
            self._sleep(delay)
            waited += delay


class GuardedClient:
    """Wraps a ChatClient for the target model: paces free routes, clamps
    max_tokens to the served output ceiling, retries per-minute 429s, and
    turns the per-day cap into a clean stop for the whole run."""

    def __init__(
        self,
        inner,
        *,
        limiter: RateLimiter | None = None,
        max_tokens_cap: int | None = None,
        halt: threading.Event | None = None,
        sleep=time.sleep,
    ):
        self.inner = inner
        self.limiter = limiter
        self.cap = max_tokens_cap
        self.halt = halt if halt is not None else threading.Event()
        self._sleep = sleep
        self.model = inner.model
        self.provider_name = inner.provider_name
        self.calls = 0
        self.retries = 0
        self.clamped = 0
        self.waited = 0.0

    def complete(self, messages, **kwargs):
        return self.complete_with_usage(messages, **kwargs).content

    def complete_with_usage(self, messages, **kwargs):
        requested = kwargs.get("max_tokens", DEFAULT_MAX_TOKENS)
        if self.cap and requested > self.cap:
            kwargs["max_tokens"] = self.cap
            self.clamped += 1
        for attempt in range(len(RETRY_429_SLEEPS) + 1):
            if self.halt.is_set():
                raise DailyCapReached(
                    f"{self.model}: daily request cap reached earlier in this run"
                )
            if self.limiter is not None:
                self.waited += self.limiter.acquire()
            self.calls += 1
            try:
                return self.inner.complete_with_usage(messages, **kwargs)
            except ProviderError as exc:
                message = str(exc)
                if "429" not in message[:80]:
                    raise
                lowered = message.lower()
                if any(marker in lowered for marker in DAILY_CAP_MARKERS):
                    self.halt.set()
                    raise DailyCapReached(f"{self.model}: {message[:200]}") from exc
                if attempt == len(RETRY_429_SLEEPS):
                    raise
                self.retries += 1
                self._sleep(RETRY_429_SLEEPS[attempt])
        raise AssertionError("unreachable")


def make_factory(target: str, *, limiter, max_tokens_cap, halt):
    """Return a drop-in for the instruments' `openrouter_client` /
    `mistral_client` symbols: the target gets the guarded client, every other
    model (the interview's author, the grader) the plain one."""
    provider, native = parse_slug(target)
    guarded: dict[str, GuardedClient] = {}

    def factory(model: str | None = None):
        if model is None:  # MistralGrader asks for Mistral's default grader
            return mistral_client()
        if model == target or (provider == "mistral" and model == native):
            if target not in guarded:
                base = (
                    mistral_client(native)
                    if provider == "mistral"
                    else openrouter_client(target)
                )
                guarded[target] = GuardedClient(
                    base, limiter=limiter, max_tokens_cap=max_tokens_cap, halt=halt
                )
            return guarded[target]
        if model.startswith("mistral/"):
            return mistral_client(model.split("/", 1)[1])
        return openrouter_client(model)

    factory.guarded = guarded  # type: ignore[attr-defined]
    return factory


# --------------------------------------------------------------------------
# steps
# --------------------------------------------------------------------------


class Context:
    def __init__(self, slug, *, elo, name, price, cost_ceiling, factory, halt):
        self.slug = slug
        self.elo = elo
        self.name = name
        self.price = price
        self.cost_ceiling = cost_ceiling
        self.factory = factory
        self.halt = halt


def step_recall(ctx: Context) -> None:
    import experiments.worldmodel_smoke as ws

    ws.CANDIDATES = (ctx.slug,)
    ws.openrouter_client = ctx.factory
    ws.main()


def frozen_retro_set(bank, data):
    """The retro_today shared set as the 10-model panel defined it. A new
    model's own KNOW commits never re-shrink it (retro_v2_fable51 rule), so
    its Brier is column-comparable with the published run."""
    import experiments.retro_today as rt
    import experiments.retro_v2 as rv

    previous = rv.MODELS
    rv.MODELS = rt.PANEL
    try:
        return rv.shared_set(bank, data)
    finally:
        rv.MODELS = previous


def step_retro(ctx: Context) -> None:
    import experiments.retro_today as rt
    import experiments.retro_v2 as rv

    bank = rt.load_bank()
    data = (
        json.loads(rt.DATA_PATH.read_text(encoding="utf-8"))
        if rt.DATA_PATH.is_file()
        else {"responses": {}, "usage": {}, "effort_applied": {}}
    )
    frozen = frozen_retro_set(bank, data)
    print(
        f"frozen shared set: {len(frozen)}/{len(bank)} questions (panel-defined; "
        "this model's commits do not re-shrink it)"
    )
    rv.MODELS = ((ctx.slug, ctx.elo or 0),)
    rv.PRICE[ctx.slug] = ctx.price
    rv.DATA_PATH = rt.DATA_PATH
    rv.COST_CEILING_USD = ctx.cost_ceiling
    data["responses"].setdefault(ctx.slug, {})
    data["usage"].setdefault(ctx.slug, {"prompt": 0, "completion": 0})
    data.setdefault("effort_applied", {})
    clients = {ctx.slug: ctx.factory(ctx.slug)}
    no_effort: set[str] = set()
    rv.run_calls(
        [(it["id"] + ":know", rv.know_prompt(it["question"])) for it in bank],
        data, clients, no_effort, "know",
    )
    rv.run_calls(
        [(it["id"] + ":forecast", rv.forecast_prompt(it["question"])) for it in frozen],
        data, clients, no_effort, "forecast",
    )


def step_domain(ctx: Context) -> None:
    import experiments.distilled_efficiency as de

    de.MODELS = ((ctx.slug, ctx.elo or 0, ctx.price),)
    de.PRICE[ctx.slug] = ctx.price
    de.COST_CEILING_USD = ctx.cost_ceiling
    de.openrouter_client = ctx.factory
    de.main()


def tolerant_ask(module, censored: set[str]):
    """Wrap a ladder module's ask(). The ladders abort a model on the first
    cell whose retries are exhausted - on a paid route that meant budget
    starvation, a run-level problem. On a free route an empty completion is
    routine (nemotron-3.5-lightning:free, 2026-09-01: 25/80 domain cells),
    so the cell is recorded as censored and the ladder continues."""
    original = module.ask

    def ask(client, prompt, label):
        try:
            return original(client, prompt, label)
        except DailyCapReached:
            raise
        except RuntimeError as exc:
            censored.add(label.split()[-1])
            print(f"    {label}: censored, continuing ({str(exc)[:70]})")
            return "", 0, 0

    return ask


def mark_censored(data_path: Path, slug: str, censored: set[str]) -> None:
    """Rewrite the ladder cells the tolerant ask() gave up on as censored
    (text None), the same marker the domain bank uses, so the summary counts
    them apart from wrong answers and a re-run does not retry them."""
    if not censored or not data_path.is_file():
        return
    data = json.loads(data_path.read_text(encoding="utf-8"))
    answers = data.get("responses", {}).get(slug, {}).get("answers", {})
    for iid in censored:
        if iid in answers:
            answers[iid] = {"correct": False, "extracted": None, "text": None}
    data_path.write_text(json.dumps(data, indent=1, ensure_ascii=True), encoding="utf-8")


def step_frontier(ctx: Context) -> None:
    import experiments.frontier_ladder as fl

    fl.CANDIDATES = ((ctx.slug, ctx.elo),)
    fl.openrouter_client = ctx.factory
    censored: set[str] = set()
    fl.ask = tolerant_ask(fl, censored)
    try:
        fl.main()
    finally:
        mark_censored(fl.DATA_PATH, ctx.slug, censored)


def step_portfolio(ctx: Context) -> None:
    import experiments.portfolio_ladder as pl

    pl.CANDIDATES = ((ctx.slug, ctx.elo),)
    pl.openrouter_client = ctx.factory
    censored: set[str] = set()
    pl.ask = tolerant_ask(pl, censored)
    try:
        pl.main()
    finally:
        mark_censored(pl.DATA_PATH, ctx.slug, censored)


def step_interview(ctx: Context) -> None:
    import experiments.pilot_deep_interview as pdi

    provider, _ = parse_slug(ctx.slug)
    # Route everything through the factory: the provider column is fixed up
    # afterwards so the record still says where the target was served.
    pdi.TARGETS = (("openrouter", ctx.slug, float(ctx.elo or 0), ctx.name),)
    pdi.openrouter_client = ctx.factory
    pdi.mistral_client = ctx.factory
    pdi.main()
    if provider != "openrouter" and pdi.DATA_PATH.is_file():
        data = json.loads(pdi.DATA_PATH.read_text(encoding="utf-8"))
        record = data.get("models", {}).get(ctx.slug)
        if record:
            record["provider"] = provider
            pdi.DATA_PATH.write_text(
                json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8"
            )


FREE_ROUTE_RETRY_SLEEPS = (5,)  # one retry; the instruments' default is three


def apply_retry_policy(free_route: bool) -> dict[str, tuple]:
    """Every instrument retries a failed cell three times with 5/15/30 s
    sleeps, sized for transient paid-route errors. On a free route the usual
    failure is an empty completion after a full 60k-token grind (~10 min a
    try on nemotron-3.5-lightning:free), and it repeats, so three retries
    cost an hour per censored cell for nothing. Keep one. Returns what was
    applied, per module."""
    import experiments.domain_portfolio as dp
    import experiments.frontier_ladder as fl
    import experiments.portfolio_ladder as pl
    import experiments.retro_v2 as rv
    import experiments.worldmodel_smoke as ws

    applied = {}
    for name, module in (("domain", dp), ("frontier", fl), ("portfolio", pl),
                         ("retro", rv), ("recall", ws)):
        if free_route:
            module.RETRY_SLEEPS = FREE_ROUTE_RETRY_SLEEPS
        applied[name] = tuple(module.RETRY_SLEEPS)
    return applied


RUNNERS = {
    "recall": step_recall,
    "retro": step_retro,
    "domain": step_domain,
    "frontier": step_frontier,
    "portfolio": step_portfolio,
    "interview": step_interview,
}


def coverage(step: str, slug: str) -> tuple[int, int] | None:
    """(cells on file, cells expected) for a step, read fresh from disk, so a
    step that an instrument cut short reads as partial rather than ok."""
    if step == "recall":
        import experiments.worldmodel_smoke as ws

        bank = _read_json(ws.BANK_PATH) or []
        data = _read_json(ws.DATA_PATH) or {"responses": {}}
        return len(data["responses"].get(slug, {})), len(ws.build_calls(bank))
    if step == "retro":
        import experiments.retro_today as rt

        bank = rt.load_bank() if rt.BANK_PATH.is_file() else []
        data = _read_json(rt.DATA_PATH) or {"responses": {}}
        frozen = frozen_retro_set(bank, data) if bank else []
        return len(data["responses"].get(slug, {})), len(bank) + len(frozen)
    if step == "domain":
        import experiments.distilled_efficiency as de

        bank = _read_json(EXP / "domain_portfolio_bank.json") or []
        data = _read_json(de.DATA_PATH) or {"responses": {}}
        return len(data["responses"].get(slug, {}).get("answers", {})), len(bank)
    if step in ("frontier", "portfolio"):
        name = "frontier_ladder_data.json" if step == "frontier" else "portfolio_ladder_data.json"
        data = _read_json(EXP / name) or {"items": {}, "responses": {}}
        expected = len(data.get("items") or {}) or CALLS[step]
        return len(data["responses"].get(slug, {}).get("answers", {})), expected
    if step == "interview":
        import experiments.pilot_deep_interview as pdi

        data = _read_json(pdi.DATA_PATH) or {"models": {}}
        record = data["models"].get(slug) or {}
        return len(record.get("steps") or []), pdi.QUESTIONS
    return None


def outcome_label(base: str, cov: tuple[int, int] | None) -> str:
    if cov is None:
        return base
    answered, expected = cov
    if answered >= expected:
        return f"{base} ({answered}/{expected})"
    return f"partial ({answered}/{expected}, re-run to continue)" if base == "ok" else (
        f"{base} ({answered}/{expected})"
    )


def run_steps(ctx: Context, steps: list[str]) -> dict[str, str]:
    results: dict[str, str] = {}
    for step in steps:
        if ctx.halt.is_set():
            results[step] = "skipped: daily request cap (re-run tomorrow)"
            print(f"\n===== {step}: {results[step]}")
            continue
        print(f"\n===== {step} (<= {CALLS.get(step, '?')} calls) =====")
        started = time.time()
        try:
            RUNNERS[step](ctx)
            base = (
                "stopped: daily request cap (re-run tomorrow)"
                if ctx.halt.is_set()
                else "ok"
            )
        except DailyCapReached as exc:
            ctx.halt.set()
            base = f"stopped: {str(exc)[:160]}"
        except Exception as exc:  # keep going: the other steps are independent
            base = f"error: {type(exc).__name__}: {str(exc)[:160]}"
        try:
            cov = coverage(step, ctx.slug)
        except Exception as exc:  # a summary problem must not hide a finished step
            print(f"  (coverage unavailable: {exc})")
            cov = None
        results[step] = outcome_label(base, cov)
        print(f"  {step}: {results[step]} ({time.time() - started:.0f}s)")
    return results


# --------------------------------------------------------------------------
# summary
# --------------------------------------------------------------------------


def _mean(values):
    values = [float(v) for v in values]
    return sum(values) / len(values) if values else None


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def load_sources() -> dict:
    """Every bank and data file the summary reads, loaded once."""
    import experiments.retro_today as rt

    return {
        "wm_bank": _read_json(EXP / "worldmodel_smoke_bank.json") or [],
        "wm_data": _read_json(EXP / "worldmodel_smoke_data.json") or {"responses": {}},
        "retro_bank": rt.load_bank() if rt.BANK_PATH.is_file() else [],
        "retro_data": _read_json(rt.DATA_PATH) or {"responses": {}},
        "domain_bank": _read_json(EXP / "domain_portfolio_bank.json") or [],
        "domain_data": _read_json(EXP / "distilled_efficiency_data.json")
        or {"responses": {}, "usage": {}, "effort_applied": {}},
        "frontier_data": _read_json(EXP / "frontier_ladder_data.json")
        or {"items": {}, "responses": {}},
        "portfolio_data": _read_json(EXP / "portfolio_ladder_data.json")
        or {"items": {}, "responses": {}},
        "interview_data": _read_json(EXP / "pilot_deep_data.json") or {"models": {}},
    }


def recall_accuracy(bank, responses, model):
    r = responses.get(model, {})
    ids = [
        it["id"]
        for it in bank
        if it["family"] == "recall" and it["id"] not in BAD_RECALL_ITEMS and it["id"] in r
    ]
    if not ids:
        return None
    return _mean(bool(r[i].get("correct")) for i in ids)


def summarize_recall(src, slug):
    bank, data = src["wm_bank"], src["wm_data"]
    acc = recall_accuracy(bank, data["responses"], slug)
    if acc is None:
        return None
    r = data["responses"][slug]
    tiers = {}
    for tier in ("famous", "mid", "obscure"):
        ids = [
            it["id"]
            for it in bank
            if it["family"] == "recall"
            and it.get("tier") == tier
            and it["id"] not in BAD_RECALL_ITEMS
            and it["id"] in r
        ]
        tiers[tier] = _mean(bool(r[i].get("correct")) for i in ids)
    zone_ids = [
        it["id"]
        for it in bank
        if it["family"] == "recall"
        and it.get("tier") in ("famous", "mid")
        and it["id"] not in BAD_RECALL_ITEMS
        and it["id"] in r
    ]
    others = {}
    for m in data["responses"]:
        if m == slug:
            continue
        other = recall_accuracy(bank, data["responses"], m)
        if other is not None:
            others[m] = other
    rank = 1 + sum(1 for v in others.values() if v > acc)
    nearest = sorted(others, key=lambda m: abs(others[m] - acc))[:2]
    return {
        "n": sum(1 for it in bank if it["family"] == "recall" and it["id"] in r
                 and it["id"] not in BAD_RECALL_ITEMS),
        "accuracy": acc,
        "tiers": tiers,
        "zone_famous_mid": _mean(bool(r[i].get("correct")) for i in zone_ids),
        "rank": rank,
        "of": len(others) + 1,
        "nearest": [(m, others[m]) for m in nearest],
    }


def summarize_retro(src, slug):
    import experiments.retro_v2 as rv

    bank, data = src["retro_bank"], src["retro_data"]
    r = data.get("responses", {}).get(slug)
    if not bank or not r:
        return None
    frozen = frozen_retro_set(bank, data)
    points = []
    for it in frozen:
        p = rv.parse_prob(r.get(it["id"] + ":forecast", {}).get("extracted"))
        if p is not None:
            points.append((p, 1.0 if it["resolution"] == "YES" else 0.0))
    commits = correct_commits = commits_scored = 0
    frozen_ids = {it["id"] for it in frozen}
    for it in bank:
        know = (r.get(it["id"] + ":know", {}).get("extracted") or "").upper()
        if know.startswith(("YES", "NO")):
            commits += 1
            if know.startswith(it["resolution"]):
                correct_commits += 1
                if it["id"] in frozen_ids:
                    commits_scored += 1
    if not points:
        return {"n": 0, "commits": commits, "correct_commits": correct_commits}
    ys = [1.0 if it["resolution"] == "YES" else 0.0 for it in frozen]
    base = sum(ys) / len(ys)
    return {
        "n": len(points),
        "frozen_set": len(frozen),
        "brier": _mean((p - y) ** 2 for p, y in points),
        "base_rate": base,
        "base_rate_brier": _mean((base - y) ** 2 for y in ys),
        "direction_accuracy": _mean((p >= 0.5) == (y == 1.0) for p, y in points),
        "boldness": _mean(abs(p - 0.5) for p, _ in points),
        "commits": commits,
        "correct_commits": correct_commits,
        "correct_commits_on_scored_set": commits_scored,
    }


def domain_censored(item, answer):
    """domain_analysis.censored: wrong AND no parseable answer (output ceiling
    or provider glitch) is unmeasurable, never a zero."""
    if answer.get("correct"):
        return False
    got = answer.get("extracted")
    if got is None:
        return True
    return item.get("kind") == "number" and re.sub(r"[^\d]", "", str(got)) == ""


def summarize_domain(src, slug):
    bank = {it["id"]: it for it in src["domain_bank"]}
    data = src["domain_data"]
    rec = data.get("responses", {}).get(slug)
    if not rec or not rec.get("answers"):
        return None
    answers = rec["answers"]
    families: dict[str, dict] = {}
    solved_tokens = []
    censored = 0
    for iid, a in answers.items():
        item = bank.get(iid, {"family": a.get("family") or "?"})
        fam = families.setdefault(item.get("family", "?"), {"solved": 0, "n": 0, "censored": 0})
        if domain_censored(item, a):
            censored += 1
            fam["censored"] += 1
            continue
        fam["n"] += 1
        if a.get("correct"):
            fam["solved"] += 1
            if a.get("completion_tokens"):
                solved_tokens.append(a["completion_tokens"])
    measurable = sum(f["n"] for f in families.values())
    solved = sum(f["solved"] for f in families.values())
    return {
        "n": len(answers),
        "measurable": measurable,
        "solved": solved,
        "accuracy": (solved / measurable) if measurable else None,
        "censored": censored,
        "families": dict(sorted(families.items())),
        "ctok_per_solved_median": (
            statistics.median(solved_tokens) if solved_tokens else None
        ),
        "ctok_per_solved_mean": _mean(solved_tokens),
        "effort_applied": data.get("effort_applied", {}).get(slug),
        "usage": data.get("usage", {}).get(slug),
    }


def summarize_ladder(data, slug):
    store = data.get("responses", {}).get(slug)
    if not store or not store.get("answers"):
        return None
    items = data.get("items", {})
    families: dict[str, dict] = {}
    for iid, a in store["answers"].items():
        fam = items.get(iid, {}).get("family", "?")
        row = families.setdefault(fam, {"solved": 0, "n": 0, "censored": 0})
        if a.get("text") is None and not a.get("correct"):
            row["censored"] += 1  # empty completion at every retry: unmeasured
            continue
        row["n"] += 1
        row["solved"] += 1 if a.get("correct") else 0
    n = sum(f["n"] for f in families.values())
    solved = sum(f["solved"] for f in families.values())
    censored = sum(f["censored"] for f in families.values())
    return {
        "n": n,
        "solved": solved,
        "censored": censored,
        "attempted": len(store["answers"]),
        "bank": len(items) or None,
        "accuracy": solved / n if n else None,
        "families": dict(sorted(families.items())),
    }


def summarize_interview(src, slug):
    record = src["interview_data"].get("models", {}).get(slug)
    if not record:
        return None
    verdict = record.get("verdict") or {}
    return {
        "questions": len(record.get("steps") or []),
        "mean_elo": verdict.get("mean_elo"),
        "low_90": verdict.get("low_90"),
        "high_90": verdict.get("high_90"),
        "done": bool(verdict),
    }


def summarize(slug: str, *, sources: dict | None = None, facts: dict | None = None,
              elo: float | None = None, results: dict | None = None) -> dict:
    src = sources if sources is not None else load_sources()
    return {
        "slug": slug,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "public_elo": elo,
        "catalog": facts or {},
        "step_results": results or {},
        "steps": {
            "recall": summarize_recall(src, slug),
            "retro": summarize_retro(src, slug),
            "domain": summarize_domain(src, slug),
            "frontier": summarize_ladder(src["frontier_data"], slug),
            "portfolio": summarize_ladder(src["portfolio_data"], slug),
            "interview": summarize_interview(src, slug),
        },
    }


def _f(value, digits=2):
    return "-" if value is None else f"{value:.{digits}f}"


def dossier_line(summary: dict) -> str:
    s = summary["steps"]
    name = summary["catalog"].get("name") or summary["slug"]
    bits = []
    if s["recall"]:
        r = s["recall"]
        near = ", ".join(f"{m.split('/')[-1]} {v:.2f}" for m, v in r["nearest"])
        bits.append(
            f"recall {r['accuracy']:.2f} (famous+mid {_f(r['zone_famous_mid'])}, "
            f"obscure {_f(r['tiers'].get('obscure'))}; #{r['rank']}/{r['of']} on "
            f"file, nearest {near})"
        )
    if s["retro"] and s["retro"].get("n"):
        r = s["retro"]
        bits.append(
            f"retro-today Brier {r['brier']:.3f} vs base rate {r['base_rate_brier']:.3f} "
            f"(n={r['n']}, |p-.5| {r['boldness']:.2f}, "
            f"{r['correct_commits_on_scored_set']} correct commits on the scored set)"
        )
    if s["domain"]:
        d = s["domain"]
        bits.append(
            f"domain bank {d['solved']}/{d['measurable']} measurable "
            f"({d['censored']} censored, median {_f(d['ctok_per_solved_median'], 0)} "
            f"ctok/solved, effort {'on' if d['effort_applied'] else 'rejected'})"
        )
    for key in ("frontier", "portfolio"):
        if s[key]:
            ladder = s[key]
            note = ""
            if ladder.get("censored"):
                note += f", {ladder['censored']} censored"
            if ladder.get("bank") and ladder["attempted"] < ladder["bank"]:
                note += f", {ladder['bank'] - ladder['attempted']} unattempted"
            bits.append(f"{key} ladder {ladder['solved']}/{ladder['n']}{note}")
    if s["interview"] and s["interview"]["done"]:
        i = s["interview"]
        bits.append(
            f"interview read {i['mean_elo']:.0f} ({i['low_90']:.0f}-{i['high_90']:.0f})"
        )
    return f"**{name}** ({summary['slug']}) - " + "; ".join(bits) if bits else (
        f"**{name}** ({summary['slug']}) - no results on file yet"
    )


def render_markdown(summary: dict) -> str:
    s = summary["steps"]
    facts = summary["catalog"]
    lines = [f"# Day-one battery: {summary['slug']}", ""]
    lines.append(f"Generated {summary['generated_at']}.")
    if facts:
        price = facts.get("price_per_m") or (None, None)
        lines.append(
            f"Catalog: {facts.get('name')} - listed {facts.get('created') or '?'}, "
            f"ctx {facts.get('context_length') or '?'}, max out "
            f"{facts.get('max_completion_tokens') or '?'}, "
            f"{'reasoning param' if facts.get('supports_reasoning') else 'no reasoning param'}, "
            f"${_f(price[0])}/${_f(price[1])} per M"
            + (f", expires {facts['expires']}" if facts.get("expires") else "")
            + "."
        )
    if summary.get("public_elo"):
        lines.append(f"Public Elo given: {summary['public_elo']:.0f}.")
    if summary.get("step_results"):
        lines.append("")
        lines.append("| step | outcome |")
        lines.append("|---|---|")
        for step, outcome in summary["step_results"].items():
            lines.append(f"| {step} | {outcome} |")
    lines.append("")
    lines.append("## Dossier draft")
    lines.append("")
    lines.append(dossier_line(summary))
    lines.append("")
    if s["recall"]:
        r = s["recall"]
        lines += [
            "## Recall (long-tail, closed book)",
            "",
            "| items | all | famous | mid | obscure | famous+mid | rank on file |",
            "|---|---|---|---|---|---|---|",
            f"| {r['n']} | {_f(r['accuracy'])} | {_f(r['tiers'].get('famous'))} | "
            f"{_f(r['tiers'].get('mid'))} | {_f(r['tiers'].get('obscure'))} | "
            f"{_f(r['zone_famous_mid'])} | {r['rank']}/{r['of']} |",
            "",
        ]
    if s["retro"]:
        r = s["retro"]
        if r.get("n"):
            lines += [
                "## Retro-today (72h Manifold bank, panel-frozen shared set)",
                "",
                "| scored | Brier | base-rate Brier | direction acc | boldness | commits (correct) | correct commits on scored set |",
                "|---|---|---|---|---|---|---|",
                f"| {r['n']}/{r['frozen_set']} | {_f(r['brier'], 3)} | {_f(r['base_rate_brier'], 3)} | "
                f"{_f(r['direction_accuracy'])} | {_f(r['boldness'])} | "
                f"{r['commits']} ({r['correct_commits']}) | {r['correct_commits_on_scored_set']} |",
                "",
                "A correct commit on the scored set is a leakage footnote (freshness law, lab record K).",
                "",
            ]
        else:
            lines += ["## Retro-today", "", f"KNOW pass only so far: {r['commits']} commits, "
                      f"{r['correct_commits']} correct.", ""]
    if s["domain"]:
        d = s["domain"]
        lines += [
            "## Domain bank (80 items, per-cell tokens)",
            "",
            f"Measurable {d['solved']}/{d['measurable']} ({_f(d['accuracy'])}), "
            f"censored {d['censored']}, median {_f(d['ctok_per_solved_median'], 0)} / mean "
            f"{_f(d['ctok_per_solved_mean'], 0)} completion tokens per solved item, "
            f"effort param {'accepted' if d['effort_applied'] else 'rejected or unset'}.",
            "",
            "| family | solved | measurable | censored |",
            "|---|---|---|---|",
        ]
        for fam, row in d["families"].items():
            lines.append(f"| {fam} | {row['solved']} | {row['n']} | {row['censored']} |")
        lines.append("")
    for key, title in (("frontier", "Frontier ladder (inversion/execution)"),
                       ("portfolio", "Portfolio ladder (five families)")):
        if s[key]:
            ladder = s[key]
            lines += [f"## {title}", ""]
            if ladder.get("bank"):
                lines.append(
                    f"{ladder['attempted']}/{ladder['bank']} items attempted, "
                    f"{ladder['censored']} censored (empty completion at every retry)."
                )
                lines.append("")
            lines += ["| family | solved | measurable | censored |", "|---|---|---|---|"]
            for fam, row in ladder["families"].items():
                lines.append(f"| {fam} | {row['solved']} | {row['n']} | {row['censored']} |")
            lines.append(f"| all | {ladder['solved']} | {ladder['n']} | {ladder['censored']} |")
            lines.append("")
    if s["interview"]:
        i = s["interview"]
        lines += [
            "## Interview (Sol-authored ladder)",
            "",
            f"{i['questions']} questions; "
            + (
                f"read {i['mean_elo']:.0f} ({i['low_90']:.0f}-{i['high_90']:.0f})."
                if i["done"]
                else "no verdict yet (re-run resumes)."
            ),
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def write_summary(summary: dict) -> tuple[Path, Path]:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stem = safe_name(summary["slug"])
    json_path = RUNS_DIR / f"{stem}.json"
    md_path = RUNS_DIR / f"{stem}.md"
    json_path.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    md_path.write_text(render_markdown(summary), encoding="utf-8")
    return json_path, md_path


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def plan_lines(slug, steps, *, rpm, cap, price, cost_ceiling, keys, facts) -> list[str]:
    total = sum(CALLS.get(s, 0) for s in steps)
    lines = [f"Day-one battery plan for {slug}"]
    if facts:
        lines.append(
            f"  catalog: {facts.get('name')} listed {facts.get('created')}, ctx "
            f"{facts.get('context_length')}, max out {facts.get('max_completion_tokens')}, "
            f"reasoning param {'yes' if facts.get('supports_reasoning') else 'no'}, "
            f"${_f((facts.get('price_per_m') or (None, None))[0])}/"
            f"${_f((facts.get('price_per_m') or (None, None))[1])} per M"
        )
    lines.append(f"  steps: {', '.join(f'{s} ({CALLS.get(s, '?')})' for s in steps)} "
                 f"= up to {total} calls")
    lines.append(
        f"  pacing: {rpm} req/min" if rpm else "  pacing: none (paid route)"
    )
    lines.append(f"  max_tokens cap: {cap or 'none'}")
    lines.append(
        f"  price used for cost ceilings: ${price[0]}/${price[1]} per M, "
        f"ceiling ${cost_ceiling:.0f}"
    )
    lines.append(
        "  keys: "
        + ", ".join(f"{k} {'set' if v else 'MISSING'}" for k, v in keys.items())
    )
    if "interview" in steps:
        lines.append("  interview: Sol authoring + Mistral grading, ~$5-14 examiner cost")
    if total and rpm:
        lines.append(f"  pacing floor: ~{total / rpm:.0f} min of request slots")
    return lines


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("slug", help="OpenRouter id, or mistral/<native-id>")
    parser.add_argument("--elo", type=float, default=None, help="public Elo if known")
    parser.add_argument("--name", default=None, help="display name (default: catalog)")
    parser.add_argument(
        "--steps",
        default=",".join(CORE_STEPS),
        help=f"comma-separated subset of {', '.join(CORE_STEPS + OPTIONAL_STEPS)}",
    )
    parser.add_argument("--skip", default="", help="comma-separated steps to skip")
    parser.add_argument(
        "--interview",
        action="store_true",
        help="add the Sol-authored interview ladder (~$5-14 examiner cost)",
    )
    parser.add_argument(
        "--cost-ceiling",
        type=float,
        default=25.0,
        help="target-side USD hard stop per instrument at catalog price",
    )
    parser.add_argument(
        "--rpm",
        type=int,
        default=None,
        help="requests/minute for the target (default 18 on :free, 50 on mistral/, else unpaced)",
    )
    parser.add_argument(
        "--max-tokens-cap",
        type=int,
        default=None,
        help="clamp max_tokens (default: the route's served max_completion_tokens)",
    )
    parser.add_argument(
        "--full-retries",
        action="store_true",
        help="keep the instruments' three retries per cell even on a free route",
    )
    parser.add_argument("--plan", action="store_true", help="print the plan, no calls")
    parser.add_argument("--report", action="store_true", help="summarize what is on file")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    slug = args.slug.strip()
    provider, _ = parse_slug(slug)
    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    if args.interview and "interview" not in steps:
        steps.append("interview")
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    steps = [s for s in steps if s not in skip]
    unknown = [s for s in steps if s not in RUNNERS]
    if unknown:
        print(f"unknown step(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    keys = ensure_keys()
    facts = catalog_facts(openrouter_catalog_entry(slug)) if provider == "openrouter" else {}
    name = args.name or facts.get("name") or slug
    is_free = slug.endswith(":free") or provider == "mistral"
    price = (0.0, 0.0) if is_free else tuple(
        p if p is not None else 2.0 for p in (facts.get("price_per_m") or (2.0, 10.0))
    )
    rpm = args.rpm
    if rpm is None:
        rpm = FREE_RPM if slug.endswith(":free") else (MISTRAL_RPM if provider == "mistral" else 0)
    cap = args.max_tokens_cap or facts.get("max_completion_tokens")

    if args.report:
        summary = summarize(slug, facts=facts, elo=args.elo)
        json_path, md_path = write_summary(summary)
        print(render_markdown(summary))
        print(f"written: {json_path.name}, {md_path.name} in {RUNS_DIR}")
        return 0

    for line in plan_lines(slug, steps, rpm=rpm, cap=cap, price=price,
                           cost_ceiling=args.cost_ceiling, keys=keys, facts=facts):
        print(line)
    if args.plan:
        return 0
    if provider == "openrouter" and not keys["OPENROUTER_API_KEY"]:
        print("OPENROUTER_API_KEY missing", file=sys.stderr)
        return 2
    if (provider == "mistral" or "interview" in steps) and not keys["MISTRAL_API_KEY"]:
        print("MISTRAL_API_KEY missing", file=sys.stderr)
        return 2

    retries = apply_retry_policy(is_free and not args.full_retries)
    print("  retries per cell: " + ", ".join(
        f"{k} {len(v) + 1}" for k, v in retries.items()))
    halt = threading.Event()
    limiter = RateLimiter(rpm) if rpm else None
    factory = make_factory(slug, limiter=limiter, max_tokens_cap=cap, halt=halt)
    ctx = Context(slug, elo=args.elo, name=name, price=price,
                  cost_ceiling=args.cost_ceiling, factory=factory, halt=halt)
    started = time.time()
    results = run_steps(ctx, steps)
    guarded = factory.guarded.get(slug)  # type: ignore[attr-defined]
    if guarded is not None:
        results["_target_calls"] = (
            f"{guarded.calls} requests, {guarded.retries} 429 retries, "
            f"{guarded.clamped} max_tokens clamps, {guarded.waited / 60:.1f} min paced"
        )
    results["_elapsed"] = f"{(time.time() - started) / 60:.0f} min"
    summary = summarize(slug, facts=facts, elo=args.elo, results=results)
    json_path, md_path = write_summary(summary)
    print()
    print(render_markdown(summary))
    print(f"written: {json_path.name}, {md_path.name} in {RUNS_DIR}")
    if halt.is_set():
        print("daily request cap reached: re-run the same command tomorrow to finish.")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

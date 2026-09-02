"""Domain portfolio: fresh multi-DOMAIN verifiable bank (Tier A).

Check 1 showed the 7 existing planted-key families collapse onto ONE factor
(lambda1 73% in-band); Check 2 showed broad multi-domain baskets of public
verifiable boards rank the frontier band fine (+0.89). This bank tests the
surviving question: does a FRESH verifiable instrument work once it spans
skill domains instead of grind depth?  H2 predicts yes; failure revives
corpus-level contamination/targeting (H-A at scale).

Six new families, each a different public-board skill direction, all with
by-construction keys; plus a 4-item inversion anchor (old grind factor,
same-run conditions):

  toolsim  - agentic planning: banking ops with preconditions; grade by
             simulating the proposed call sequence (property: reaches goal,
             no errors, within planted length + 2).            [TAU/agentic]
  longctx  - two planted fact chains scattered in 4k-24k-token memo noise;
             answer combines both chains arithmetically.       [AA-LCR]
  casework - invented levy schedule (brackets, credits, phase-outs, caps)
             applied to a case; all-integer arithmetic.        [Tax/LegalBench]
  tableqa  - 3 linked tables, NL filter+join+aggregate query.  [structured data]
  repobug  - mini-module where exactly one helper's body violates its
             paraphrased docstring; name the function.         [code reading]
  audit    - deployment manifest vs 12-20 numbered requirements; list the
             violated requirement numbers (set equality).      [IFBench/review]
  inv      - inversion chains at rungs 8/14/22/32 (anchor).    [grind factor]

Every item is SELF-TESTED at build. Bank frozen to domain_portfolio_bank.json
before any call. Reasoning effort pinned {"effort": "high"} for every model
(fallback: stripped on provider rejection, recorded). Resumable per
(model, item); light threading.

    python -m experiments.domain_portfolio --build     # build + freeze bank only
    DOMAIN_SMOKE=1 python -m experiments.domain_portfolio   # 1 item x 2 models
    python -m experiments.domain_portfolio             # full run
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from viberank.clients import ProviderError, openrouter_client

import experiments.frontier_ladder as fl

EXP = Path(__file__).resolve().parent
BANK_PATH = EXP / "domain_portfolio_bank.json"
DATA_PATH = EXP / "domain_portfolio_data.json"
SEED = 20260830

CANDIDATES = (
    ("openai/gpt-oss-120b", 1665.0),
    ("moonshotai/kimi-k2-0905", 1722.0),
    ("openai/gpt-5.2", 1818.0),
    ("moonshotai/kimi-k2.6", 1835.0),
    ("qwen/qwen3.6-plus", 1814.0),
    ("deepseek/deepseek-v4-pro", 1836.0),
    ("openai/gpt-5.4", 1881.0),
    ("anthropic/claude-opus-4.8", 1934.0),
    ("openai/gpt-5.5", 1937.0),
)
RETRY_SLEEPS = (5, 15, 30)
EFFORT = {"reasoning": {"effort": "high"}}
COST_CEILING_USD = 90.0  # hard stop; quoted budget was $40-70

FINAL_RE = re.compile(r"FINAL[:\s]*(.+)", re.I)


def extract(text):
    hits = FINAL_RE.findall(text or "")
    return hits[-1].strip().strip("'\"` .*") if hits else None


def _num(s):
    if s is None:
        return None
    digits = re.sub(r"[^\d-]", "", s.split(".")[0] if "." in s else s)
    try:
        return int(digits)
    except ValueError:
        return None


# ================= toolsim: precondition planning, simulator-graded =========
def _sim(state, calls, maxlen):
    """Apply calls to state; return (ok, final_state). Any invalid call -> fail."""
    if len(calls) > maxlen:
        return False, state
    st = {a: dict(v) for a, v in state.items()}
    for name, args in calls:
        if name == "verify" and len(args) == 1 and args[0] in st:
            st[args[0]]["verified"] = True
        elif name == "unlock" and len(args) == 1 and args[0] in st:
            if not st[args[0]]["verified"]:
                return False, st
            st[args[0]]["locked"] = False
        elif name == "deposit" and len(args) == 2 and args[0] in st:
            try:
                n = int(args[1])
            except ValueError:
                return False, st
            if st[args[0]]["locked"] or n <= 0:
                return False, st
            st[args[0]]["balance"] += n
        elif name == "move" and len(args) == 3 and args[0] in st and args[1] in st:
            try:
                n = int(args[2])
            except ValueError:
                return False, st
            a, b = args[0], args[1]
            if st[a]["locked"] or st[b]["locked"] or n <= 0 or st[a]["balance"] < n or a == b:
                return False, st
            st[a]["balance"] -= n
            st[b]["balance"] += n
        else:
            return False, st
    return True, st


CALL_RE = re.compile(r"([a-z]+)\s*\(([^)]*)\)")


def parse_calls(s):
    calls = []
    for name, argstr in CALL_RE.findall(s or ""):
        args = tuple(a.strip().strip("'\"") for a in argstr.split(",") if a.strip())
        calls.append((name, args))
    return calls


def make_toolsim(rng, tier, ident):
    n_acct = min(3 + (tier - 1), 9)  # 3..5 (wave 1), 6..7 (wave 2), 8..9 (wave 3)
    n_ops = 3 + tier * 2             # mutating ops in the planted plan
    names = [chr(ord("A") + i) for i in range(n_acct)]
    while True:
        state = {a: {"balance": rng.randrange(2, 12) * 10,
                     "locked": True, "verified": False} for a in names}
        n_usable = 1 if tier >= 4 else max(1, n_acct - 2)  # wave 2: everything gated
        for a in rng.sample(names, n_usable):
            state[a] = {"balance": state[a]["balance"], "locked": False, "verified": True}
        # roll a valid forward plan
        st = {a: dict(v) for a, v in state.items()}
        plan = []
        for _ in range(n_ops):
            choices = []
            for a in names:
                if st[a]["locked"] and st[a]["verified"]:
                    choices.append(("unlock", (a,)))
                if st[a]["locked"] and not st[a]["verified"]:
                    choices.append(("verify", (a,)))
                if not st[a]["locked"]:
                    choices.append(("deposit", (a, str(rng.randrange(1, 6) * 10))))
                    for b in names:
                        if b != a and not st[b]["locked"] and st[a]["balance"] >= 10:
                            amt = rng.randrange(1, st[a]["balance"] // 10 + 1) * 10
                            choices.append(("move", (a, b, str(amt))))
            name, args = rng.choice(choices)
            plan.append((name, args))
            ok, st = _sim(st, [(name, args)], 99)
            assert ok
        goal = {a: st[a]["balance"] for a in names}
        if goal == {a: state[a]["balance"] for a in names}:
            continue  # trivial goal; reroll
        used_locked = any(
            n in ("verify", "unlock") for n, _ in plan
        )
        if tier >= 2 and not used_locked:
            continue
        break
    maxlen = len(plan) + 2
    ok, st2 = _sim(state, plan, maxlen)
    assert ok and {a: st2[a]["balance"] for a in names} == goal  # self-test
    lines = [f"  {a}: balance {v['balance']}, {'LOCKED' if v['locked'] else 'unlocked'}, "
             f"{'verified' if v['verified'] else 'NOT verified'}" for a, v in state.items()]
    goal_lines = [f"  {a}: balance {g}" for a, g in goal.items()]
    prompt = (
        "You operate a banking console with exactly these operations:\n"
        "  verify(X)      - marks account X as verified (always allowed)\n"
        "  unlock(X)      - requires X verified; unlocks X\n"
        "  deposit(X, N)  - requires X unlocked; adds N (a positive integer) to X\n"
        "  move(X, Y, N)  - requires BOTH X and Y unlocked, X's balance >= N, X != Y;\n"
        "                   moves N from X to Y\n"
        "Any call that violates a requirement ABORTS the whole session.\n\n"
        f"Initial accounts:\n" + "\n".join(lines) +
        "\n\nReach exactly this goal state (verified/locked flags do not matter, "
        "only balances):\n" + "\n".join(goal_lines) +
        f"\n\nUse at most {maxlen} calls. End your reply with ONE line:\n"
        "FINAL: call1; call2; ...\n"
        "for example 'FINAL: verify(A); unlock(A); move(A, B, 20)'."
    )
    return {"id": ident, "family": "toolsim", "rung": tier, "prompt": prompt,
            "key": "; ".join(f"{n}({', '.join(a)})" for n, a in plan),
            "kind": "toolsim", "state": state, "goal": goal, "maxlen": maxlen}


def grade_toolsim(item, ans):
    calls = parse_calls(ans)
    if not calls:
        return False
    ok, st = _sim(item["state"], calls, item["maxlen"])
    return ok and {a: st[a]["balance"] for a in item["goal"]} == item["goal"]


# ================= longctx: planted chains in memo noise ====================
FIRST = ("Marisol Vega Dario Quint Ilsa Brandt Tomas Reyes Nadia Osei Petra Lindqvist "
         "Rustam Aliyev Greta Hoffman Yusuf Kaan Bea Solano Henrik Dahl Zoe Marchetti "
         "Omar Haddad Livia Costa Anders Berg Priya Nair Cormac Doyle Selin Aydin "
         "Viktor Lang Amara Diallo Jonas Meyer Talia Rosen Bruno Vidal Ines Ferreira "
         "Casper Holm Dina Waheed Elio Sartori Freja Nilsson Gustav Weber Hana Sato "
         "Ivo Petrov Jana Kovac Kenji Mori Lena Vogel Milan Novak Nora Lindgren").split()
PEOPLE = [f"{FIRST[i]} {FIRST[i+1]}" for i in range(0, len(FIRST) - 1, 2)]
PROJ_A = ("Zephyr Boreal Cinder Delta Ember Fjord Glacier Harrow Indigo Juniper Krait "
          "Lumen Meridian Nimbus Obsidian Pinnacle Quartz Rampart Sable Talus Umber "
          "Vertex Willow Xenon Yarrow Zenith Anvil Basalt Cobalt Drift").split()
PROGRAMS = ("Atlas Beacon Compass Dynamo Everest Falcon Granite Horizon Ironwood "
            "Jubilee Keystone Lantern Monarch Northstar Orchard Pioneer Quarry "
            "Redwood Summit Trident").split()
FILLER_TMPL = (
    "Reminder: the {p} sync moved to {h}:00 on {day}; {who} will circulate the notes "
    "and the room booking stays under cost code {n}.",
    "Facilities note: badge readers on floor {h} will be offline {day} morning; "
    "contractors for {p} should use the east entrance until {h2}:00.",
    "{who} filed the quarterly compliance attestation for {p}; the review window "
    "closes on the {n2}th and no exceptions were logged.",
    "Travel desk: bookings coded to {p} above {n} units now need pre-approval from "
    "{who}; economy defaults apply from {day}.",
    "IT bulletin: the {p} shared drive migrates {day} night; expect read-only access "
    "for about {h} hours and file histories are preserved.",
    "Catering for the {p} retro on {day} is confirmed for {n2} people; {who} owns "
    "the dietary list and the invoice lands on code {n}.",
    "Security drill: floor {h} evacuates {day} at {h2}:15; {p} standup shifts back "
    "by thirty minutes and wardens report counts to {who}.",
    "HR: the mentoring cohort adds {n2} seats this cycle; nominations route through "
    "{who} and close {day} for the {p} group.",
)
DAYS = "Monday Tuesday Wednesday Thursday Friday".split()


def make_longctx(rng, tier, ident):
    n_filler = (55, 100, 150, 210, 280, 360)[tier - 1]
    depth = 2 if tier <= 2 else (3 if tier <= 4 else 4)
    people = rng.sample(PEOPLE, 8)
    projects = rng.sample(PROJ_A, 8)
    programs = rng.sample(PROGRAMS, 6)
    chain_people, filler_people = people[:2], people[2:]
    chain_proj, filler_proj = projects[:2], projects[2:]
    chain_prog = programs[:2]

    vals, chains = [], []
    for c in range(2):
        who, proj, prog = chain_people[c], chain_proj[c], chain_prog[c]
        val = rng.randrange(120, 980) * 10
        vals.append(val)
        facts = [f"After the reshuffle, {who} now leads project {proj}.",
                 f"Project {proj} was folded into the {prog} program last quarter."]
        if depth >= 3:
            code = f"{'KR'[c]}{rng.randrange(10, 99)}"
            facts.append(f"The {prog} program reports under budget line {code}.")
            tail = f"Budget line {code} carries a quarterly allocation of {val} units."
        else:
            tail = f"The {prog} program carries a quarterly allocation of {val} units."
        if depth >= 4:
            desk = f"desk {'EW'[c]}{rng.randrange(3, 9)}"
            facts.append(tail.replace(f"{val} units", f"the amount posted at {desk}"))
            facts.append(f"The amount posted at {desk} is {val} units.")
        else:
            facts.append(tail)
        chains.append(facts)

    memos = []
    for _ in range(n_filler):
        t = rng.choice(FILLER_TMPL)
        memos.append(t.format(
            p=rng.choice(filler_proj), who=rng.choice(filler_people),
            h=rng.randrange(2, 9), h2=rng.randrange(9, 17), day=rng.choice(DAYS),
            n=rng.randrange(1200, 9800), n2=rng.randrange(6, 60)))
    flat = [f for facts in chains for f in facts]
    rng.shuffle(flat)
    positions = sorted(rng.sample(range(3, n_filler - 3), len(flat)))
    for pos, fact in zip(positions, flat):
        memos.insert(pos, fact)
    doc = "\n\n".join(f"[note {i+1}] {m}" for i, m in enumerate(memos))
    q = (f"Question: find the quarterly allocation (in units) of the program that "
         f"contains the project led by {chain_people[0]}, and the quarterly "
         f"allocation of the program that contains the project led by "
         f"{chain_people[1]}. Report the SUM of the two amounts.")
    key = vals[0] + vals[1]
    for c in range(2):  # self-test: chain resolvable & entities unique
        assert doc.count(f"{chain_people[c]} now leads") == 1
        assert str(vals[c]) in doc
    prompt = (f"Below is an internal notes dump. Somewhere in it are the facts needed "
              f"to answer the question at the end.\n\n{doc}\n\n{q}\n\n"
              f"End your reply with a line 'FINAL: <number>'.")
    return {"id": ident, "family": "longctx", "rung": tier, "prompt": prompt,
            "key": str(key), "kind": "number"}


LEAD_TMPL = ("After the reshuffle, {w} now leads project {p}.",
             "{w} took over as lead of project {p} this cycle.",
             "{w} was appointed to head project {p}.")


def make_longctx2(rng, tier, ident):
    """Wave-2 rungs 7/8: much longer docs, deeper chains, paraphrased lead
    facts, and near-miss memos mentioning the chain people innocuously."""
    n_filler = {7: 700, 8: 1100}[tier]
    depth = {7: 4, 8: 5}[tier]
    people = rng.sample(PEOPLE, 10)
    projects = rng.sample(PROJ_A, 10)
    programs = rng.sample(PROGRAMS, 6)
    chain_people, filler_people = people[:2], people[2:]
    chain_proj, filler_proj = projects[:2], projects[2:]
    chain_prog = programs[:2]

    def fill_kwargs(who=None, proj=None):
        return dict(p=proj or rng.choice(filler_proj), who=who or rng.choice(filler_people),
                    h=rng.randrange(2, 9), h2=rng.randrange(9, 17), day=rng.choice(DAYS),
                    n=rng.randrange(1200, 9800), n2=rng.randrange(6, 60))

    vals, flat, leads = [], [], []
    for c in range(2):
        who, proj, prog = chain_people[c], chain_proj[c], chain_prog[c]
        val = rng.randrange(120, 980) * 10
        vals.append(val)
        lead = rng.choice(LEAD_TMPL).format(w=who, p=proj)
        leads.append(lead)
        code = f"{'KR'[c]}{rng.randrange(10, 99)}"
        desk = f"desk {'EW'[c]}{rng.randrange(3, 9)}"
        facts = [lead,
                 f"Project {proj} was folded into the {prog} program last quarter.",
                 f"The {prog} program reports under budget line {code}.",
                 f"Budget line {code} carries the amount posted at {desk}."]
        if depth >= 5:
            row = f"{'GH'[c]}{rng.randrange(100, 999)}"
            facts += [f"The amount posted at {desk} matches ledger row {row}.",
                      f"Ledger row {row} shows {val} units."]
        else:
            facts.append(f"The amount posted at {desk} is {val} units.")
        flat += facts
        # near-miss: the chain person in unrelated memos with OTHER projects
        for t in (FILLER_TMPL[2], FILLER_TMPL[3]):
            flat.append(t.format(**fill_kwargs(who=who)))

    memos = [rng.choice(FILLER_TMPL).format(**fill_kwargs()) for _ in range(n_filler)]
    rng.shuffle(flat)
    positions = sorted(rng.sample(range(3, n_filler - 3), len(flat)))
    for pos, fact in zip(positions, flat):
        memos.insert(pos, fact)
    doc = "\n\n".join(f"[note {i+1}] {m}" for i, m in enumerate(memos))
    for c in range(2):  # self-test
        assert doc.count(leads[c]) == 1
        assert str(vals[c]) in doc
        assert doc.count(chain_people[c]) >= 3  # lead + 2 near-miss mentions
    q = (f"Question: find the quarterly allocation (in units) of the program that "
         f"contains the project led by {chain_people[0]}, and the quarterly "
         f"allocation of the program that contains the project led by "
         f"{chain_people[1]}. Report the SUM of the two amounts.")
    key = vals[0] + vals[1]
    prompt = (f"Below is an internal notes dump. Somewhere in it are the facts needed "
              f"to answer the question at the end.\n\n{doc}\n\n{q}\n\n"
              f"End your reply with a line 'FINAL: <number>'.")
    return {"id": ident, "family": "longctx", "rung": tier, "prompt": prompt,
            "key": str(key), "kind": "number"}


# ================= casework: invented levy schedule =========================
def make_casework(rng, tier, ident):
    brackets = sorted(rng.sample(range(2, 20), 3))
    b1, b2, b3 = (x * 1000 for x in brackets)
    r1, r2, r3, r4 = (rng.randrange(4, 30) for _ in range(4))
    per_unit = rng.randrange(30, 90)
    credit = rng.randrange(300, 900)
    cthresh = rng.randrange(8, 22) * 1000
    phase_per = rng.randrange(4, 12) * 10  # multiple of 10: phase-out stays integer-clean
    capmult = rng.randrange(28, 45)
    base = rng.randrange(3, 40) * 500 + rng.randrange(0, 9) * 100
    units = rng.randrange(0, 7)
    cls = rng.choice(("alpha", "beta", "gamma"))
    flagged = rng.random() < 0.6

    def compute():
        t = 0
        t += min(base, b1) * r1 // 100
        if base > b1:
            t += (min(base, b2) - b1) * r2 // 100
        if base > b2:
            t += (min(base, b3) - b2) * r3 // 100
        if base > b3:
            t += (base - b3) * r4 // 100
        if cls in ("alpha", "gamma"):
            t += per_unit * units
            if tier >= 4 and units > 3:
                t += per_unit * (units - 3)  # units beyond 3 count double
        c = 0
        if flagged:
            c = credit
            if tier >= 2 and base > cthresh:
                c = max(0, c - ((base - cthresh) // 100) * (phase_per // 10))
        t = max(0, t - c)
        if tier >= 3:
            surtax_thresh = b3 + 2000
            if t > surtax_thresh // 10:
                t += (t - surtax_thresh // 10) * 5 // 100
        if tier >= 5:
            if t > b2 // 8:
                t += (t - b2 // 8) * 3 // 100
            if t % 7 == 0:
                t += 13
        cap = base * capmult // 100
        return min(t, cap)

    key = compute()
    surcharge_txt = (f"2. If the filing class is alpha or gamma, add a surcharge of {per_unit} "
                     f"per registered unit.")
    if tier >= 4:
        surcharge_txt += (f" Each registered unit beyond the third counts double "
                          f"(i.e. add a further {per_unit} for every unit above 3).")
    rules = [
        f"1. Levy on the base amount, applied per slice IN ORDER (integer division "
        f"by 100 after each multiplication):\n"
        f"   - the first {b1} units are levied at {r1}%\n"
        f"   - units above {b1} up to {b2} at {r2}%\n"
        f"   - units above {b2} up to {b3} at {r3}%\n"
        f"   - units above {b3} at {r4}%",
        surcharge_txt,
        f"3. If the case is flagged for relief, subtract a credit of {credit} "
        f"(the total cannot go below 0).",
    ]
    if tier >= 2:
        rules[2] = (f"3. If the case is flagged for relief, subtract a credit of {credit}, "
                    f"but when the base amount exceeds {cthresh} the credit is first "
                    f"reduced by {phase_per // 10} for every full 100 units above "
                    f"{cthresh}; the credit cannot go below 0, and the total after "
                    f"subtraction cannot go below 0.")
    if tier >= 3:
        rules.append(f"4. Surtax: if the running total now exceeds {(b3 + 2000) // 10}, "
                     f"add 5% of the excess (integer division by 100 after the "
                     f"multiplication).")
    if tier >= 5:
        rules.append(f"{len(rules) + 1}. Second surtax: if the running total now exceeds "
                     f"{b2 // 8}, add 3% of the excess (integer division by 100 after "
                     f"the multiplication).")
        rules.append(f"{len(rules) + 1}. Oddity levy: if the running total is now exactly "
                     f"divisible by 7, add 13.")
    rules.append(f"{len(rules) + 1}. Cap: the final levy never exceeds {capmult}% of the "
                 f"base amount (integer division by 100).")
    prompt = (
        "Apply the following levy schedule EXACTLY as written, in the listed order. "
        "All arithmetic is on whole numbers; wherever a percentage is applied, "
        "multiply first and then use integer division as stated.\n\n"
        + "\n".join(rules) +
        f"\n\nCase file:\n  base amount: {base}\n  filing class: {cls}\n"
        f"  registered units: {units}\n  flagged for relief: {'yes' if flagged else 'no'}\n\n"
        "Compute the final levy. End your reply with a line 'FINAL: <number>'."
    )
    assert compute() == key
    return {"id": ident, "family": "casework", "rung": tier, "prompt": prompt,
            "key": str(key), "kind": "number"}


# ================= tableqa: NL query over linked tables =====================
DEPTS = "Ops Design Research Compliance Logistics Field Support".split()
STATUSES = ("active", "paused", "wrapped")


def make_tableqa(rng, tier, ident):
    n_emp = (12, 16, 22, 28, 34, 40, 60, 90, 120, 160)[tier - 1]
    n_dept = min(4 + tier // 2, len(DEPTS))
    depts = rng.sample(DEPTS, n_dept)
    people = rng.sample(PEOPLE, min(n_emp, len(PEOPLE)))
    while len(people) < n_emp:
        people.append(f"{rng.choice(FIRST)} {rng.choice(FIRST)}")
    dept_rows = [{"dept": d, "floor": rng.randrange(1, 7),
                  "head": rng.choice(people)} for d in depts]
    emp_rows = [{"id": 100 + i, "name": people[i], "dept": rng.choice(depts),
                 "hours": rng.randrange(4, 40), "rate": rng.randrange(20, 90),
                 "joined": rng.randrange(2019, 2027)} for i in range(n_emp)]
    proj_rows = [{"proj": f"{rng.choice(PROJ_A)}-{rng.randrange(10, 99)}",
                  "dept": rng.choice(depts), "status": rng.choice(STATUSES)}
                 for _ in range(n_dept + 2 + tier)]

    floor_min = rng.randrange(2, 5)
    year_max = rng.randrange(2022, 2026)
    active_depts = {p["dept"] for p in proj_rows if p["status"] == "active"}
    q_depts = [d["dept"] for d in dept_rows if d["floor"] >= floor_min and d["dept"] in active_depts]
    extra_q = ""
    if tier >= 7:
        paused_depts = {p["dept"] for p in proj_rows if p["status"] == "paused"}
        heads = {d["head"] for d in dept_rows}
        rate_min = rng.randrange(30, 55)
        q_depts = [d for d in q_depts if d not in paused_depts]
        hit = [e for e in emp_rows if e["dept"] in q_depts and e["joined"] < year_max
               and e["rate"] >= rate_min and e["name"] not in heads]
        extra_q = (f" Exclude departments that ALSO have at least one 'paused' project. "
                   f"Among the remaining employees, count only those with a rate of at "
                   f"least {rate_min} who are not listed as the head of any department.")
    else:
        hit = [e for e in emp_rows if e["dept"] in q_depts and e["joined"] < year_max]
    if not (2 <= len(hit) <= n_emp - 2):
        return make_tableqa(rng, tier, ident)  # non-degenerate filter only
    if tier >= 9:
        groups = {}
        for e in hit:
            groups[e["dept"]] = groups.get(e["dept"], 0) + e["hours"] * e["rate"]
        if len(groups) < 3 or sorted(groups.values())[-1] == sorted(groups.values())[-2]:
            return make_tableqa(rng, tier, ident)  # need >=3 groups, unique max
        key = max(groups.values())
    else:
        key = sum(e["hours"] * e["rate"] for e in hit)
    tail = ("compute hours * rate summed PER DEPARTMENT, and report the largest "
            "single departmental total" if tier >= 9 else
            "compute hours * rate, and report the total sum")

    def tbl(rows, cols):
        head = " | ".join(cols)
        body = "\n".join(" | ".join(str(r[c]) for c in cols) for r in rows)
        return f"{head}\n{body}"

    prompt = (
        "Three tables from an internal tracker.\n\n"
        "DEPARTMENTS:\n" + tbl(dept_rows, ["dept", "floor", "head"]) + "\n\n"
        "EMPLOYEES:\n" + tbl(emp_rows, ["id", "name", "dept", "hours", "rate", "joined"]) + "\n\n"
        "PROJECTS:\n" + tbl(proj_rows, ["proj", "dept", "status"]) + "\n\n"
        f"Query: consider departments that are on floor {floor_min} or higher AND "
        f"have at least one project with status 'active'.{extra_q} For every "
        f"remaining employee of those departments who joined strictly before "
        f"{year_max}, {tail}.\n\n"
        "End your reply with a line 'FINAL: <number>'."
    )
    return {"id": ident, "family": "tableqa", "rung": tier, "prompt": prompt,
            "key": str(key), "kind": "number"}


# ================= bigknap: exact optimum, search-hard ======================
def make_bigknap(rng, tier, ident):
    """0/1 knapsack at sizes where mental DP is infeasible and greedy-by-density
    provably misses the optimum (regenerated until it does)."""
    n = {1: 28, 2: 30, 3: 32, 4: 34, 5: 36}[tier]
    while True:
        goods = [(rng.randrange(8, 120), rng.randrange(5, 90)) for _ in range(n)]
        cap = int(sum(w for _, w in goods) * 0.38)
        dp = [0] * (cap + 1)
        for v, w in goods:
            for c in range(cap, w - 1, -1):
                if dp[c - w] + v > dp[c]:
                    dp[c] = dp[c - w] + v
        opt = dp[cap]
        g, rem = 0, cap
        for v, w in sorted(goods, key=lambda vw: vw[0] / vw[1], reverse=True):
            if w <= rem:
                g += v
                rem -= w
        if g < opt:
            break
    lines = "\n".join(f"  item {i+1}: value {v}, weight {w}"
                      for i, (v, w) in enumerate(goods))
    prompt = (
        f"A knapsack has capacity {cap}: the total weight of the chosen items must "
        f"not exceed it. Choose any subset of the items below to MAXIMIZE the total "
        f"value. Report the maximum achievable total value — the exact optimum, "
        f"not an approximation.\n\n{lines}\n\n"
        "End your reply with a line 'FINAL: <number>'."
    )
    assert dp[cap] == opt and g < opt
    return {"id": ident, "family": "bigknap", "rung": tier, "prompt": prompt,
            "key": str(opt), "kind": "number"}


# ================= repobug: paraphrased-docstring violation =================
PARA = (
    ("Return x scaled by {a}, shifted up by {b}, reduced modulo {m}.",
     "scale then shift then reduce"),
    ("Multiply the input by {a}, then add {b}, keeping the result modulo {m}.",
     "same"),
    ("Return the remainder of (x times {a} plus {b}) divided by {m}.", "same"),
    ("Add {b} to {a} copies of x, then take the result mod {m}.", "same"),
)


def make_repobug(rng, tier, ident):
    n_leaf = (5, 6, 8, 11, 14)[tier - 1]
    m = rng.choice((89, 97, 101, 103))
    params = [(rng.randrange(2, 12), rng.randrange(3, 40)) for _ in range(n_leaf)]
    target = rng.randrange(n_leaf)
    mut = list(params[target])
    if tier == 1:
        mut[0] = mut[0] + rng.choice((2, 3))
    elif tier == 2:
        mut[1] = mut[1] + rng.choice((-2, 2, 10))
    elif tier == 3:
        mut[0], mut[1] = mut[1] % 12 + 2, mut[0] + 1  # subtle reshuffle
    elif tier == 4:
        mut[0], mut[1] = mut[1], mut[0]  # args swapped: x*b+a vs x*a+b
        if mut[0] == mut[1]:
            mut[1] += 1
    else:
        mut[1] = mut[1] + 1  # minimal off-by-one in a big module
    if tuple(mut) == tuple(params[target]):
        mut[1] += 1
    lines, docmap = [], {}
    for i, (a, b) in enumerate(params):
        body_a, body_b = (mut if i == target else (a, b))
        doc = rng.choice(PARA)[0].format(a=a, b=b, m=m)
        docmap[f"f{i+1}"] = (a, b)
        lines += [f"def f{i+1}(x):", f'    """{doc}"""',
                  f"    return (x * {body_a} + {body_b}) % {m}", ""]
    order = rng.sample(range(n_leaf), 3)
    comp = " then ".join(f"f{i+1}" for i in order)
    lines += ["def pipeline(x):",
              f'    """Apply {comp} in that order."""',
              f"    return f{order[2]+1}(f{order[1]+1}(f{order[0]+1}(x)))", ""]
    code = "\n".join(lines)
    # self-test: exactly one leaf violates its docstring on a probe domain
    bad = []
    for i, (a, b) in enumerate(params):
        body_a, body_b = (mut if i == target else (a, b))
        if any((x * a + b) % m != (x * body_a + body_b) % m for x in range(50)):
            bad.append(f"f{i+1}")
    assert bad == [f"f{target+1}"], (bad, target)
    prompt = (
        "The module below was reviewed: exactly ONE of the numbered helper "
        "functions (f1, f2, ...) has a body that does NOT match its own "
        "docstring. The pipeline docstring is accurate.\n\n"
        f"```python\n{code}```\n\n"
        "Name the function whose body violates its docstring. "
        "End your reply with a line 'FINAL: <function name>'."
    )
    return {"id": ident, "family": "repobug", "rung": tier, "prompt": prompt,
            "key": f"f{target+1}", "kind": "word"}


# ================= audit: manifest vs numbered requirements =================
REGIONS = ("eu-west", "eu-north", "us-east", "ap-south")
TIERS_ = ("dev", "staging", "prod")


def make_audit(rng, tier, ident):
    n_req = {1: 12, 2: 14, 3: 16, 4: 18, 5: 20, 6: 26, 7: 30}[tier]
    man = {
        "replicas": rng.randrange(1, 9),
        "tier": rng.choice(TIERS_),
        "region": rng.choice(REGIONS + ("me-central", "sa-east")),
        "backups": rng.random() < 0.7,
        "cpu": rng.randrange(1, 33),
        "mem_gb": rng.randrange(1, 65),
        "window_start": rng.randrange(0, 24),
        "owner_tag": rng.random() < 0.8,
        "log_days": rng.randrange(1, 120),
        "tls": rng.choice(("1.1", "1.2", "1.3")),
        "autoscale_max": rng.randrange(2, 20),
        "canary_pct": rng.randrange(0, 60),
    }
    reqs = [
        ("replicas must be between 2 and 6 (inclusive)",
         lambda m: 2 <= m["replicas"] <= 6),
        ("region must be one of: " + ", ".join(REGIONS),
         lambda m: m["region"] in REGIONS),
        ("if tier is 'prod', backups must be enabled",
         lambda m: m["tier"] != "prod" or m["backups"]),
        ("cpu must be at least twice the replica count",
         lambda m: m["cpu"] >= 2 * m["replicas"]),
        ("mem_gb must be at least 4 times cpu, or at least 32",
         lambda m: m["mem_gb"] >= 4 * m["cpu"] or m["mem_gb"] >= 32),
        ("maintenance window must start between 0:00 and 5:00 (inclusive)",
         lambda m: 0 <= m["window_start"] <= 5),
        ("an owner tag must be present",
         lambda m: m["owner_tag"]),
        ("log retention must be at least 30 days",
         lambda m: m["log_days"] >= 30),
        ("TLS version must be 1.2 or 1.3",
         lambda m: m["tls"] in ("1.2", "1.3")),
        ("autoscale_max must be strictly greater than replicas",
         lambda m: m["autoscale_max"] > m["replicas"]),
        ("canary_pct must be at most 25",
         lambda m: m["canary_pct"] <= 25),
        ("if tier is 'dev', replicas must be at most 3",
         lambda m: m["tier"] != "dev" or m["replicas"] <= 3),
        ("if region starts with 'eu-', log retention must be at least 45 days",
         lambda m: not m["region"].startswith("eu-") or m["log_days"] >= 45),
        ("if backups are enabled, the maintenance window must start at 4:00 or earlier",
         lambda m: not m["backups"] or m["window_start"] <= 4),
        ("if autoscale_max exceeds 10, cpu must be at least 8",
         lambda m: m["autoscale_max"] <= 10 or m["cpu"] >= 8),
        ("if canary_pct is above 0, tier must not be 'dev'",
         lambda m: m["canary_pct"] == 0 or m["tier"] != "dev"),
        ("mem_gb must not exceed 48",
         lambda m: m["mem_gb"] <= 48),
        ("if tier is 'prod', TLS version must be 1.3",
         lambda m: m["tier"] != "prod" or m["tls"] == "1.3"),
        ("replicas times cpu must be at most 120",
         lambda m: m["replicas"] * m["cpu"] <= 120),
        ("if the owner tag is missing, tier must be 'dev'",
         lambda m: m["owner_tag"] or m["tier"] == "dev"),
        ("if mem_gb exceeds 32, backups must be enabled",
         lambda m: m["mem_gb"] <= 32 or m["backups"]),
        ("if tier is 'staging', log retention must be an even number of days",
         lambda m: m["tier"] != "staging" or m["log_days"] % 2 == 0),
        ("canary_pct must be 0 when replicas are fewer than 3",
         lambda m: m["replicas"] >= 3 or m["canary_pct"] == 0),
        ("cpu must not exceed 24",
         lambda m: m["cpu"] <= 24),
        ("if TLS is 1.1, tier must be 'dev'",
         lambda m: m["tls"] != "1.1" or m["tier"] == "dev"),
        ("autoscale_max must be at most 4 times replicas",
         lambda m: m["autoscale_max"] <= 4 * m["replicas"]),
        ("if region is 'ap-south', the maintenance window must start at 2:00 or later",
         lambda m: m["region"] != "ap-south" or m["window_start"] >= 2),
        ("an owner tag is required whenever canary_pct is above 10",
         lambda m: m["canary_pct"] <= 10 or m["owner_tag"]),
        ("replicas plus autoscale_max must be at most 22",
         lambda m: m["replicas"] + m["autoscale_max"] <= 22),
        ("if backups are disabled, log retention must be at least 60 days",
         lambda m: m["backups"] or m["log_days"] >= 60),
    ][:n_req]
    violated = sorted(i + 1 for i, (_, chk) in enumerate(reqs) if not chk(man))
    if not (2 <= len(violated) <= (7 if n_req > 20 else 6)):
        return make_audit(rng, tier, ident)
    key = ",".join(map(str, violated))
    man_lines = "\n".join(f"  {k}: {str(v).lower() if isinstance(v, bool) else v}"
                          for k, v in man.items())
    req_lines = "\n".join(f"  {i+1}. {t}" for i, (t, _) in enumerate(reqs))
    prompt = (
        "A deployment manifest and the policy it must satisfy.\n\n"
        f"MANIFEST:\n{man_lines}\n\nPOLICY REQUIREMENTS:\n{req_lines}\n\n"
        "List the numbers of ALL requirements the manifest violates (and no "
        "others), comma-separated, in increasing order. "
        "End your reply with a line 'FINAL: <numbers>'."
    )
    return {"id": ident, "family": "audit", "rung": tier, "prompt": prompt,
            "key": key, "kind": "numset"}


# ================= bank ====================================================
def build_bank():
    rng = random.Random(SEED)
    items = []
    for fam, maker, tiers in (
        ("toolsim", make_toolsim, (1, 1, 2, 2, 3, 3)),
        ("longctx", make_longctx, (1, 2, 3, 4, 5, 6)),
        ("casework", make_casework, (1, 1, 2, 2, 3, 3)),
        ("tableqa", make_tableqa, (1, 2, 3, 4, 5, 6)),
        ("repobug", make_repobug, (1, 1, 2, 2, 3, 3)),
        ("audit", make_audit, (1, 2, 3, 4, 5, 5)),
    ):
        for j, t in enumerate(tiers):
            items.append(maker(rng, t, f"{fam}-{t}-{j}"))
    inv_rng = random.Random(SEED + 1)
    for j, k in enumerate((8, 14, 22, 32)):
        it = fl.make_inversion_item(inv_rng, k, f"inv-{k}-{j}")
        it["family"] = "inv"
        it["kind"] = "number"
        items.append(it)
    return items


def build_wave2():
    """Escalation wave: wave 1 saturated at pinned-high effort (5 of 9 models
    perfect, whole band at 39-40/40). Fresh seed; appended to the frozen bank
    with w2 ids. Changing generators does not disturb wave-1 items (frozen)."""
    rng = random.Random(SEED + 2)
    items = []
    for fam, maker, tiers in (
        ("toolsim", make_toolsim, (4, 4, 5, 5)),
        ("longctx", make_longctx2, (7, 7, 8, 8)),
        ("casework", make_casework, (4, 4, 5, 5)),
        ("tableqa", make_tableqa, (7, 7, 8, 8)),
        ("repobug", make_repobug, (4, 4, 5, 5)),
        ("audit", make_audit, (6, 6, 7, 7)),
    ):
        for j, t in enumerate(tiers):
            items.append(maker(rng, t, f"{fam}-{t}-w2{j}"))
    inv_rng = random.Random(SEED + 3)
    for j, k in enumerate((45, 60)):
        it = fl.make_inversion_item(inv_rng, k, f"inv-{k}-w2{j}")
        it["family"] = "inv"
        it["kind"] = "number"
        items.append(it)
    return items


def build_wave3():
    """Compute-hardness wave: wave 2 still saturated the band (four models
    66/66). Search problems where exactness needs real optimization, plus the
    deepest toolsim/tableqa rungs and one inv-70 bridge."""
    rng = random.Random(SEED + 4)
    items = []
    for fam, maker, tiers in (
        ("bigknap", make_bigknap, (1, 2, 3, 4, 5)),
        ("toolsim", make_toolsim, (6, 6, 7, 7)),
        ("tableqa", make_tableqa, (9, 9, 10, 10)),
    ):
        for j, t in enumerate(tiers):
            items.append(maker(rng, t, f"{fam}-{t}-w3{j}"))
    inv_rng = random.Random(SEED + 5)
    it = fl.make_inversion_item(inv_rng, 70, "inv-70-w30")
    it["family"] = "inv"
    it["kind"] = "number"
    items.append(it)
    return items


def load_bank():
    if BANK_PATH.is_file():
        bank = json.loads(BANK_PATH.read_text(encoding="utf-8"))
    else:
        bank = build_bank()
        BANK_PATH.write_text(json.dumps(bank, indent=1), encoding="utf-8")
        print(f"bank frozen: {len(bank)} items -> {BANK_PATH.name}")
    for flag, tag, builder in (("--wave2", "-w2", build_wave2),
                               ("--wave3", "-w3", build_wave3)):
        if flag in sys.argv and not any(tag in i["id"] for i in bank):
            new = builder()
            bank += new
            BANK_PATH.write_text(json.dumps(bank, indent=1), encoding="utf-8")
            print(f"{flag[2:]} appended: +{len(new)} items -> {len(bank)} total")
    return bank


def grade(item, text):
    got = extract(text)
    if got is None:
        return False
    kind = item["kind"]
    if kind == "toolsim":
        return grade_toolsim(item, got)
    if kind == "number":
        n = _num(got)
        return n is not None and str(n) == item["key"]
    if kind == "numset":
        nums = sorted(set(int(x) for x in re.findall(r"\d+", got)))
        return ",".join(map(str, nums)) == item["key"]
    if kind == "word":
        return got.lower().split()[0].strip(".,`'\"") == item["key"].lower()
    raise ValueError(kind)


# ================= runner ==================================================
PRICE = {  # $/M (in, out) rough - BYOK models billed on their own dashboards
    "openai/gpt-oss-120b": (0.1, 0.5), "moonshotai/kimi-k2-0905": (0.5, 2.5),
    "openai/gpt-5.2": (1.25, 10.0), "moonshotai/kimi-k2.6": (0.6, 2.5),
    "qwen/qwen3.6-plus": (0.4, 2.4), "deepseek/deepseek-v4-pro": (0.3, 1.6),
    "openai/gpt-5.4": (1.25, 10.0), "anthropic/claude-opus-4.8": (5.0, 25.0),
    "openai/gpt-5.5": (1.25, 10.0),
}
SYSTEM = "Solve by reasoning alone - no tools, no code execution. Be careful and exact."
_lock = threading.Lock()


def est_cost(data):
    total = 0.0
    for m, u in data["usage"].items():
        pi, po = PRICE.get(m, (1.0, 5.0))
        total += u["prompt"] / 1e6 * pi + u["completion"] / 1e6 * po
    return total


def run_one(client, model, item, data, no_effort):
    extra = None if model in no_effort else EFFORT
    for attempt, sleep_s in enumerate((0,) + RETRY_SLEEPS):
        if sleep_s:
            time.sleep(sleep_s)
        try:
            result = client.complete_with_usage(
                [{"role": "system", "content": SYSTEM},
                 {"role": "user", "content": item["prompt"]}],
                temperature=0.2, max_tokens=60000, extra=extra, timeout=300.0,
            )
            if getattr(result, "refusal", None) or getattr(result, "finish_reason", None) == "content_filter":
                # Provider-side policy refusal (seen 2026-09-02: Anthropic's cyber-content
                # classifier cutting Opus 5 mid-answer on longctx/casework/toolsim/tableqa).
                # Censored by construction; retrying re-bills the prompt for the same verdict.
                print(f"  {model} {item['id']}: provider refusal -> censored, no retry "
                      f"({(result.refusal or result.finish_reason or '')[:70]})")
                return None, extra is not None
            if not (result.content or "").strip() or result.content.strip() == "None":
                raise ProviderError("empty/null content")
            return result, extra is not None
        except ProviderError as exc:
            msg = str(exc)
            if extra and ("reasoning" in msg.lower() or "400" in msg[:60]):
                with _lock:
                    if model not in no_effort:
                        no_effort.add(model)
                        print(f"  ! {model}: effort param rejected, running without")
                extra = None
                continue
            print(f"  {model} {item['id']} attempt {attempt + 1}: {msg[:100]}")
    return None, extra is not None


def main():
    bank = load_bank()
    if "--build" in sys.argv:
        toks = sum(len(it["prompt"]) for it in bank) // 4
        fams = {}
        for it in bank:
            fams[it["family"]] = fams.get(it["family"], 0) + 1
        print("families:", fams)
        print(f"~{toks:,} prompt tokens per model, x9 models ~ {toks*9:,} total input")
        return
    data = json.loads(DATA_PATH.read_text(encoding="utf-8")) if DATA_PATH.is_file() else {
        "seed": SEED, "effort": "high", "responses": {}, "usage": {}, "effort_applied": {}}
    smoke = bool(os.environ.get("DOMAIN_SMOKE"))
    models = [m for m, _ in CANDIDATES]
    if smoke:
        models, bank = ["openai/gpt-5.4", "deepseek/deepseek-v4-pro"], bank[:1]

    todo = []
    for m in models:
        rec = data["responses"].setdefault(m, {"answers": {}})
        data["usage"].setdefault(m, {"prompt": 0, "completion": 0})
        for it in bank:
            if it["id"] not in rec["answers"]:
                todo.append((m, it))
    print(f"{len(todo)} calls to make ({len(models)} models x {len(bank)} items, resumable)")
    clients = {m: openrouter_client(m) for m in models}
    no_effort = set()

    def work(job):
        m, it = job
        if est_cost(data) > COST_CEILING_USD:
            return f"SKIP {m} {it['id']} (cost ceiling)"
        result, effort_on = run_one(clients[m], m, it, data, no_effort)
        text = result.content if result else None
        ok = bool(text) and grade(it, text)
        with _lock:
            data["responses"][m]["answers"][it["id"]] = {
                "correct": ok, "extracted": extract(text) if text else None, "text": text}
            data["effort_applied"][m] = effort_on
            if result:
                data["usage"][m]["prompt"] += result.prompt_tokens or 0
                data["usage"][m]["completion"] += result.completion_tokens or 0
            DATA_PATH.write_text(json.dumps(data, indent=1), encoding="utf-8")
            done = sum(len(r["answers"]) for r in data["responses"].values())
            ct = result.completion_tokens if result else 0
            print(f"[{done:3d}/{len(models)*len(bank)}] {m:32s} {it['id']:14s} "
                  f"{'PASS' if ok else 'fail'}  {ct or 0:,} ctok  ~${est_cost(data):.2f}")
        return None

    with ThreadPoolExecutor(max_workers=5) as pool:
        for msg in pool.map(work, todo):
            if msg:
                print(msg)

    print("\nper-model accuracy:")
    for m in models:
        ans = data["responses"][m]["answers"]
        n = len(ans)
        ok = sum(1 for a in ans.values() if a["correct"])
        print(f"  {m:32s} {ok:2d}/{n}   effort_applied={data['effort_applied'].get(m)}")
    print(f"\nestimated OpenRouter-priced cost: ${est_cost(data):.2f} "
          f"(BYOK models bill on their own dashboards)")


if __name__ == "__main__":
    main()

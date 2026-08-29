"""Portfolio ladder: 5 additional planted-key families for the breadth test.

The frontier ladder (2 families) measured one trait and got frontier rho
-0.11. Free-form interviews (~10 implicit directions) got ~0.4. This run
un-confounds verifiable-vs-judged from narrow-vs-broad: 5 new families,
each a different skill direction, all with by-construction keys:

  zebra    - 4-house/3-attribute constraint grid, clues derived from a
             planted solution then minimized under a brute-force UNIQUENESS
             check (24^3 enumeration). Answer: one queried cell.
  knapsack - 0/1 knapsack, optimum verified by DP at build. Answer: value.
  docfact  - generated document with a planted fact chain + distractors;
             answer requires combining chain facts arithmetically.
  spec     - produce ANY string satisfying N derived constraints
             (constraints generated FROM a planted witness, so always
             satisfiable); graded by property-checker, not exact match.
  bughunt  - a correct program + a mutated copy; answer: the single test
             input (verified unique at build) where outputs differ.

Tiers target the frontier band; the existing frontier_ladder families
anchor the easy end. Same 9 candidates, 60k budget from the start.

    PORTFOLIO_SMOKE=1 python -m experiments.portfolio_ladder   # oss-120b only
    python -m experiments.portfolio_ladder                     # full run
"""
from __future__ import annotations

import itertools
import json
import os
import random
import re
import time
from pathlib import Path

from viberank.clients import ProviderError, openrouter_client

EXP = Path(__file__).resolve().parent
DATA_PATH = EXP / "portfolio_ladder_data.json"

CANDIDATES = (
    ("openai/gpt-oss-120b", 1599.0),
    ("moonshotai/kimi-k2-0905", 1688.0),
    ("openai/gpt-5.2", 1744.0),
    ("moonshotai/kimi-k2.6", 1758.0),
    ("qwen/qwen3.6-plus", 1759.0),
    ("deepseek/deepseek-v4-pro", 1775.0),
    ("openai/gpt-5.4", 1829.0),
    ("anthropic/claude-opus-4.8", 1906.0),
    ("openai/gpt-5.5", 1911.0),
)
RETRY_SLEEPS = (5, 15, 30)

# ---------------- zebra: planted-unique constraint grid ----------------
N = 4
NAMES = ["Ada", "Bo", "Cy", "Dee"]
DRINKS = ["tea", "milk", "juice", "cocoa"]
PETS = ["fox", "owl", "crab", "newt"]


def zebra_solutions(clues):
    sols = []
    for pn in itertools.permutations(range(N)):
        for pd in itertools.permutations(range(N)):
            for pp in itertools.permutations(range(N)):
                # position -> index of name/drink/pet
                if all(c(pn, pd, pp) for c in clues):
                    sols.append((pn, pd, pp))
                    if len(sols) > 1:
                        return sols
    return sols


def make_zebra(rng, tier, ident):
    sol_n = list(range(N)); rng.shuffle(sol_n)
    sol_d = list(range(N)); rng.shuffle(sol_d)
    sol_p = list(range(N)); rng.shuffle(sol_p)
    planted = (tuple(sol_n), tuple(sol_d), tuple(sol_p))
    pos_of = lambda arr, i: arr.index(i)

    def clue_same(a_arr, a_i, b_arr, b_i, a_lab, b_lab):
        arrs = {"n": 0, "d": 1, "p": 2}
        ai, bi = arrs[a_arr], arrs[b_arr]
        f = lambda pn, pd, pp: (pn, pd, pp)[ai].index(a_i) == (pn, pd, pp)[bi].index(b_i)
        return f, f"{a_lab} has the {b_lab}." if ai == 0 else f"The person with {a_lab} has {b_lab}."

    def clue_pos(arr, i, pos, lab):
        ai = {"n": 0, "d": 1, "p": 2}[arr]
        f = lambda pn, pd, pp: (pn, pd, pp)[ai].index(i) == pos
        return f, f"{lab} is in house {pos + 1}."

    def clue_left(a_arr, a_i, b_arr, b_i, a_lab, b_lab):
        ai, bi = {"n": 0, "d": 1, "p": 2}[a_arr], {"n": 0, "d": 1, "p": 2}[b_arr]
        f = lambda pn, pd, pp: (pn, pd, pp)[ai].index(a_i) < (pn, pd, pp)[bi].index(b_i)
        return f, f"{a_lab} is somewhere left of {b_lab}."

    def clue_adj(a_arr, a_i, b_arr, b_i, a_lab, b_lab):
        ai, bi = {"n": 0, "d": 1, "p": 2}[a_arr], {"n": 0, "d": 1, "p": 2}[b_arr]
        f = lambda pn, pd, pp: abs((pn, pd, pp)[ai].index(a_i) - (pn, pd, pp)[bi].index(b_i)) == 1
        return f, f"{a_lab} is next to {b_lab}."

    def clue_not_pos(arr, i, pos, lab):
        ai = {"n": 0, "d": 1, "p": 2}[arr]
        f = lambda pn, pd, pp: (pn, pd, pp)[ai].index(i) != pos
        return f, f"{lab} is not in house {pos + 1}."

    # generate a large pool of clues TRUE of the planted solution
    pool = []
    for i in range(N):
        pool.append(clue_pos("n", i, pos_of(sol_n, i), NAMES[i]))
        pool.append(clue_pos("d", i, pos_of(sol_d, i), f"the {DRINKS[i]} drinker"))
        for j in range(N):
            if pos_of(sol_n, i) == pos_of(sol_d, j):
                pool.append(clue_same("n", i, "d", j, NAMES[i], f"drinks {DRINKS[j]}"))
            if pos_of(sol_n, i) == pos_of(sol_p, j):
                pool.append(clue_same("n", i, "p", j, NAMES[i], f"the {PETS[j]}"))
            if pos_of(sol_d, i) < pos_of(sol_p, j):
                pool.append(clue_left("d", i, "p", j, f"the {DRINKS[i]} drinker", f"the {PETS[j]}"))
            if abs(pos_of(sol_n, i) - pos_of(sol_p, j)) == 1:
                pool.append(clue_adj("n", i, "p", j, NAMES[i], f"the {PETS[j]}"))
        for pos in range(N):
            if pos != pos_of(sol_p, i) and rng.random() < 0.3:
                pool.append(clue_not_pos("p", i, pos, f"The {PETS[i]}"))
    # conditional and disjunctive clues (true of the planted solution) add
    # reasoning depth without enlarging the search space
    for _ in range(10 + 6 * tier):
        (fa, ta), (fb, tb) = rng.sample(pool, 2)
        if rng.random() < 0.5:
            pool.append((lambda pn, pd, pp, fa=fa, fb=fb: (not fa(pn, pd, pp)) or fb(pn, pd, pp),
                         f"If {ta[:-1].lower()}, then {tb[:-1].lower()}."))
        else:
            neg = rng.choice(pool)[0]
            pool.append((lambda pn, pd, pp, fa=fa, fb=fb: fa(pn, pd, pp) or fb(pn, pd, pp),
                         f"At least one holds: {ta[:-1].lower()}; or {tb[:-1].lower()}."))
    rng.shuffle(pool)
    # tier controls which clue kinds survive minimization order: harder tiers
    # prefer relational/negative clues (direct position clues removed first)
    def directness(c):
        return 0 if ("is in house" in c[1] and "not" not in c[1]) else 1
    clues = list(pool)
    fs = [c[0] for c in clues]
    assert len(zebra_solutions(fs)) == 1, "pool must pin the solution"
    order = sorted(range(len(clues)), key=lambda i: (directness(clues[i]), rng.random()))
    kept = list(range(len(clues)))
    for i in order:
        trial = [clues[j][0] for j in kept if j != i]
        if len(zebra_solutions(trial)) == 1:
            kept.remove(i)
    clues = [clues[j] for j in kept]
    assert len(zebra_solutions([c[0] for c in clues])) == 1
    qi = rng.randrange(N)
    # two-hop query: the pet of the person immediately LEFT of person qi
    # (wrap to rightmost if qi is leftmost) - forces full-grid recovery
    qpos = pos_of(sol_n, qi)
    tpos = qpos - 1 if qpos > 0 else N - 1
    answer = PETS[sol_p[tpos]]
    text = "\n".join(f"{k+1}. {c[1]}" for k, c in enumerate(clues))
    prompt = (
        f"Four houses are in a row, numbered 1 (leftmost) to 4 (rightmost). Each house has "
        f"exactly one resident ({', '.join(NAMES)}), one drink ({', '.join(DRINKS)}) and one "
        f"pet ({', '.join(PETS)}). Clues:\n\n{text}\n\nThe puzzle has exactly one solution. "
        f"Which pet lives in the house immediately to the LEFT of {NAMES[qi]}'s house "
        f"(if {NAMES[qi]} is in house 1, take house {N} instead)? End with 'FINAL: <pet>'."
    )
    return {"id": ident, "family": "zebra", "rung": tier, "prompt": prompt, "key": answer, "kind": "word"}


# ---------------- knapsack: DP-verified optimum ----------------
def make_knapsack(rng, tier, ident):
    n = {1: 22, 2: 30, 3: 38}[tier]
    for _attempt in range(80):
        items = []
        for _ in range(n):
            w = rng.randrange(8, 60)
            items.append((w, w * 3 + rng.randrange(-6, 7)))
        cap = int(sum(w for w, _ in items) * 0.37)
        dp = [0] * (cap + 1)
        for w, v in items:
            for c in range(cap, w - 1, -1):
                dp[c] = max(dp[c], dp[c - w] + v)
        opt = dp[cap]
        greedy_v, room = 0, cap
        for w, v in sorted(items, key=lambda t: -t[1] / t[0]):
            if w <= room:
                greedy_v += v
                room -= w
        if greedy_v < opt:
            break
    listing = "\n".join(f"item {k+1}: weight {w}, value {v}" for k, (w, v) in enumerate(items))
    prompt = (
        f"A knapsack has capacity {cap}. You may take each item at most once:\n\n{listing}\n\n"
        f"What is the maximum total value achievable without exceeding the capacity? "
        f"End with 'FINAL: <number>'."
    )
    return {"id": ident, "family": "knapsack", "rung": tier, "prompt": prompt, "key": str(opt), "kind": "number"}


# ---------------- docfact: planted fact chain in generated prose ----------------
DEPTS = ["Aria", "Basalt", "Cinder", "Dune", "Ember", "Flint", "Gale", "Harbor", "Iris", "Juniper", "Krait", "Lumen", "Moss"]


def make_docfact(rng, tier, ident):
    chain_len = {1: 5, 2: 7, 3: 9}[tier]
    depts = rng.sample(DEPTS, chain_len + 2)
    base = rng.randrange(200, 900) * 10
    facts, val = [], base
    facts.append(f"The {depts[0]} team's annual budget is {base} thousand credits.")
    ops = []
    for i in range(1, chain_len):
        kind = rng.randrange(4)
        if kind == 0:
            d = rng.randrange(2, 6)
            facts.append(f"The {depts[i]} team's budget is exactly {d} times smaller than {depts[i-1]}'s.")
            nv = val // d
            nv_adjust = val - nv * d
            if nv_adjust:  # keep divisions exact so the chain has one clean answer
                base2 = val - nv_adjust
                facts[-1] = f"The {depts[i]} team's budget is {depts[i-1]}'s minus {nv_adjust} thousand, divided by {d}."
                nv = base2 // d
            val = nv
        elif kind == 1:
            a = rng.randrange(15, 240)
            facts.append(f"The {depts[i]} team's budget exceeds {depts[i-1]}'s by {a} thousand credits.")
            val = val + a
        elif kind == 2:
            pct = 10
            for pct in rng.sample([5, 10, 20, 25, 50], 5):
                if val * pct % 100 == 0:
                    break
            up = rng.random() < 0.5
            word = "larger" if up else "smaller"
            facts.append(f"The {depts[i]} team's budget is {pct}% {word} than {depts[i-1]}'s.")
            val = val + val * pct // 100 if up else val - val * pct // 100
        else:
            facts.append(f"The {depts[i]} team's budget is double {depts[i-1]}'s budget minus {depts[i-1]}'s budget.")
        ops.append(val)
    # distractor facts about unused teams
    distract = []
    for dd in depts[chain_len:]:
        distract.append(f"The {dd} team's budget is {rng.randrange(100, 999)} thousand credits.")
        distract.append(f"The {dd} team was founded in 20{rng.randrange(10, 25)}.")
        distract.append(f"The {dd} team's headcount grew {rng.randrange(3, 40)}% last year.")
        distract.append(f"The {dd} team's budget is reviewed every {rng.randrange(2, 7)} months.")
    lines = facts + distract
    rng.shuffle(lines)
    doc = " ".join(lines)
    prompt = (
        f"Company memo:\n\n{doc}\n\nUsing only the memo, compute the {depts[chain_len-1]} team's "
        f"annual budget in thousand credits. End with 'FINAL: <number>'."
    )
    return {"id": ident, "family": "docfact", "rung": tier, "prompt": prompt, "key": str(val), "kind": "number"}


# ---------------- spec: constraints derived from a planted witness ----------------
ALPHA = "abcdehknrstz"


def make_spec(rng, tier, ident):
    n_con = {1: 10, 2: 13, 3: 16}[tier]
    L = rng.randrange(18, 24)
    witness = "".join(rng.choice(ALPHA) for _ in range(L))
    cons = [("len", L, f"the string is exactly {L} characters long"),
            ("alpha", None, f"every character is one of: {ALPHA}")]
    c = rng.choice(witness)
    cons.append(("count", (c, witness.count(c)), f"the character '{c}' appears exactly {witness.count(c)} times"))
    p = rng.randrange(L)
    cons.append(("at", (p, witness[p]), f"character {p+1} (1-indexed) is '{witness[p]}'"))
    if n_con >= 5:
        cons.append(("start", witness[0], f"it starts with '{witness[0]}'"))
        cons.append(("end", witness[-1], f"it ends with '{witness[-1]}'"))
    if n_con >= 7:
        c2 = rng.choice([ch for ch in ALPHA if ch not in witness] or ["q"])
        cons.append(("absent", c2, f"the character '{c2}' does not appear"))
        i2 = rng.randrange(L - 1)
        cons.append(("pair", (i2, witness[i2:i2+2]), f"characters {i2+1}-{i2+2} are '{witness[i2:i2+2]}'"))
        pool2 = sorted(set(witness))
        ca, cb = (rng.sample(pool2, 2) if len(pool2) >= 2 else ("a", "b"))
        dv = witness.count(ca) - witness.count(cb)
        cons.append(("reldiff", (ca, cb, dv),
                     f"the count of '{ca}' minus the count of '{cb}' is exactly {dv}"))
    if n_con >= 10:
        c3 = rng.choice(sorted(set(witness)))
        cons.append(("firstat", (c3, witness.index(c3)),
                     f"the first occurrence of '{c3}' is at position {witness.index(c3) + 1}"))
        oc = sum(1 for k in range(0, L, 2) if witness[k] in "aehz")
        cons.append(("oddset", ("aehz", oc),
                     f"exactly {oc} of the odd-numbered positions (1,3,5,...) hold a character from 'aehz'"))
        gc = sum(witness.count(ch) for ch in "krt")
        cons.append(("groupcount", ("krt", gc), f"characters from 'krt' appear {gc} times in total"))
    if n_con >= 13:
        seg = witness[2:5]
        cons.append(("segment", (2, seg), f"characters 3-5 are '{seg}'"))
        la = witness.rindex(witness[0])
        cons.append(("lastat", (witness[0], la),
                     f"the last occurrence of '{witness[0]}' is at position {la + 1}"))
        c5 = rng.choice(sorted(set(witness)))
        if c5 + c5 not in witness:
            cons.append(("nodouble", c5, f"'{c5}{c5}' never appears as a substring"))
    cons = cons[:max(4, n_con)]

    def check(s):
        for kind, arg, _ in cons:
            if kind == "len" and len(s) != arg: return False
            if kind == "alpha" and any(ch not in ALPHA for ch in s): return False
            if kind == "count" and s.count(arg[0]) != arg[1]: return False
            if kind == "at" and (len(s) <= arg[0] or s[arg[0]] != arg[1]): return False
            if kind == "start" and not s.startswith(arg): return False
            if kind == "end" and not s.endswith(arg): return False
            if kind == "absent" and arg in s: return False
            if kind == "pair" and s[arg[0]:arg[0]+2] != arg[1]: return False
            if kind == "reldiff" and s.count(arg[0]) - s.count(arg[1]) != arg[2]: return False
            if kind == "firstat" and (arg[0] not in s or s.index(arg[0]) != arg[1]): return False
            if kind == "oddset" and sum(1 for k in range(0, len(s), 2) if s[k] in arg[0]) != arg[1]: return False
            if kind == "groupcount" and sum(s.count(ch) for ch in arg[0]) != arg[1]: return False
            if kind == "segment" and s[arg[0]:arg[0]+3] != arg[1]: return False
            if kind == "lastat" and (arg[0] not in s or s.rindex(arg[0]) != arg[1]): return False
            if kind == "nodouble" and arg + arg in s: return False
        return True

    assert check(witness), "witness must satisfy its own constraints"
    text = "\n".join(f"- {c[2]}" for c in cons)
    prompt = (
        f"Construct any single string satisfying ALL of these constraints:\n\n{text}\n\n"
        f"End with 'FINAL: <your string>'."
    )
    return {"id": ident, "family": "spec", "rung": tier, "prompt": prompt,
            "key": witness, "kind": "spec", "check_desc": [c[:2] for c in cons]}


def spec_check(item, s):
    # re-derive the checker from stored (kind, arg) pairs
    for kind, arg in item["check_desc"]:
        arg = tuple(arg) if isinstance(arg, list) else arg
        if kind == "len" and len(s) != arg: return False
        if kind == "alpha" and any(ch not in ALPHA for ch in s): return False
        if kind == "count" and s.count(arg[0]) != arg[1]: return False
        if kind == "at" and (len(s) <= arg[0] or s[arg[0]] != arg[1]): return False
        if kind == "start" and not s.startswith(arg): return False
        if kind == "end" and not s.endswith(arg): return False
        if kind == "absent" and arg in s: return False
        if kind == "pair" and s[arg[0]:arg[0]+2] != arg[1]: return False
        if kind == "reldiff" and s.count(arg[0]) - s.count(arg[1]) != arg[2]: return False
        if kind == "firstat" and (arg[0] not in s or s.index(arg[0]) != arg[1]): return False
        if kind == "oddset" and sum(1 for k in range(0, len(s), 2) if s[k] in arg[0]) != arg[1]: return False
        if kind == "groupcount" and sum(s.count(ch) for ch in arg[0]) != arg[1]: return False
        if kind == "segment" and s[arg[0]:arg[0]+3] != arg[1]: return False
        if kind == "lastat" and (arg[0] not in s or s.rindex(arg[0]) != arg[1]): return False
        if kind == "nodouble" and arg + arg in s: return False
    return True


# ---------------- bughunt: planted mutation, unique failing input ----------------
def make_bughunt(rng, tier, ident):
    n_stmt = {1: 18, 2: 24, 3: 30}[tier]
    lines = ["def f(x):", "    a = x % 97", "    b = (x * 3 + 7) % 53"]
    for _ in range(n_stmt):
        k = rng.randrange(3)
        if k == 0:
            lines.append(f"    a = (a * {rng.choice([2,3,5])} + b) % 97")
        elif k == 1:
            lines.append(f"    if a % {rng.choice([2,3,4])} == {rng.randrange(2)}:")
            lines.append(f"        b = (b + a) % 53")
        else:
            lines.append(f"    b = (b * {rng.choice([2,3])} + {rng.randrange(1,9)}) % 53")
    lines.append("    return (a * 100 + b)")
    good = "\n".join(lines)
    # mutate one numeric constant
    for _ in range(200):
        nums = [(m.start(), m.group()) for m in re.finditer(r"\b\d+\b", good)][3:]
        pos, tok = nums[rng.randrange(len(nums))]
        new = str(int(tok) + rng.choice([1, 2, -1]))
        if new == tok or int(new) <= 0:
            continue
        bad = good[:pos] + new + good[pos + len(tok):]
        gs, bs = {}, {}
        exec(good, {"__builtins__": {}}, gs)
        exec(bad, {"__builtins__": {}}, bs)
        # construct the input set: one differing input + five agreeing ones,
        # so uniqueness holds by choice rather than by luck
        pool = rng.sample(range(1000, 9000), 160)
        diffs = [i for i in pool if gs["f"](i) != bs["f"](i)]
        sames = [i for i in pool if gs["f"](i) == bs["f"](i)]
        if diffs and len(sames) >= 9:
            inputs = sorted([diffs[0]] + rng.sample(sames, 9))
            diff = [i for i in inputs if gs["f"](i) != bs["f"](i)]
            assert len(diff) == 1
        else:
            continue
        if True:
            prompt = (
                f"REFERENCE implementation:\n```python\n{good}\n```\n\nA copy was made with exactly "
                f"one small change:\n```python\n{bad}\n```\n\nFor which of these inputs do the two "
                f"functions return DIFFERENT results: {inputs}? Exactly one input differs. "
                f"End with 'FINAL: <that input>'."
            )
            return {"id": ident, "family": "bughunt", "rung": tier, "prompt": prompt,
                    "key": str(diff[0]), "kind": "number"}
    raise AssertionError("bughunt: no unique-diff mutation found")


# ---------------- bank / grading / administration ----------------
def build_bank():
    rng = random.Random(20260829)
    items = []
    makers = [make_zebra, make_knapsack, make_docfact, make_spec, make_bughunt]
    for tier in (1, 2, 3):
        for j in range(2):
            for mk in makers:
                items.append(mk(rng, tier, f"{mk.__name__[5:]}-{tier}-{j}"))
    return items


FINAL_RE = re.compile(r"FINAL[:\s]*([^\n]+)", re.I)


def extract(text):
    hits = FINAL_RE.findall(text or "")
    return hits[-1].strip().strip("'\"` .*") if hits else None


def grade(item, text):
    got = extract(text)
    if got is None:
        return False
    if item["kind"] == "spec":
        return spec_check(item, got)
    if item["kind"] == "number":
        digits = re.sub(r"[^\d]", "", got)
        return digits and digits.lstrip("0") == item["key"].lstrip("0") or digits == item["key"]
    return got.lower().split()[0].strip(".,") == item["key"].lower() if got else False


def ask(client, prompt, label):
    for attempt, sleep_s in enumerate((0,) + RETRY_SLEEPS):
        if sleep_s:
            time.sleep(sleep_s)
        try:
            result = client.complete_with_usage(
                [
                    {"role": "system", "content": "Solve by reasoning alone - no tools, no code execution. Be careful and exact."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=60000,
            )
            text = result.content
            if not (text or "").strip() or text.strip() == "None":
                raise ProviderError("empty/null content (reasoning ate the budget)")
            return text, (getattr(result, "prompt_tokens", 0) or 0), (getattr(result, "completion_tokens", 0) or 0)
        except ProviderError as exc:
            print(f"    {label} attempt {attempt + 1} failed: {str(exc)[:110]}")
    raise RuntimeError(f"{label}: retries exhausted")


BANK_PATH = EXP / "portfolio_bank.json"


def load_bank():
    if BANK_PATH.is_file():
        return json.loads(BANK_PATH.read_text(encoding="utf-8"))
    items = build_bank()
    BANK_PATH.write_text(json.dumps(items, ensure_ascii=True), encoding="utf-8")
    return items


def main():
    items = load_bank()
    print(f"portfolio bank: {len(items)} items across 5 families, self-tests passed")
    candidates = CANDIDATES if not os.environ.get("PORTFOLIO_SMOKE") else CANDIDATES[:1]
    data = (
        json.loads(DATA_PATH.read_text(encoding="utf-8"))
        if DATA_PATH.is_file()
        else {"items": {it["id"]: {k: it[k] for k in it if k != "prompt"} for it in items}, "responses": {}, "usage": {}}
    )
    for model, elo in candidates:
        store = data["responses"].setdefault(model, {"public_elo": elo, "answers": {}})
        client = None
        for it in items:
            if it["id"] in store["answers"]:
                continue
            client = client or openrouter_client(model)
            try:
                text, tin, tout = ask(client, it["prompt"], f"{model[:20]} {it['id']}")
            except RuntimeError as exc:
                print(f"  STOPPED {model} at {it['id']}: {str(exc)[:100]}")
                break
            ok = grade(it, text)
            store["answers"][it["id"]] = {"correct": ok, "extracted": extract(text), "text": text}
            u = data["usage"].setdefault(model, {"prompt": 0, "completion": 0})
            u["prompt"] += tin
            u["completion"] += tout
            DATA_PATH.write_text(json.dumps(data, indent=1, ensure_ascii=True), encoding="utf-8")
            print(f"{model[:26]:<26} {it['id']:<14} -> {'PASS' if ok else 'fail'}")
        n = len(store["answers"])
        nc = sum(1 for v in store["answers"].values() if v["correct"])
        print(f"== {model}: {nc}/{n} correct")
    print("done")


if __name__ == "__main__":
    main()

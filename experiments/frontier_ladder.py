"""Frontier ladder: planted-key generator items above the examiner's level.

Tests whether tool-asymmetric items break the oral protocol's ceiling
(examiner-with-code constructs and verifies; candidate reasons unaided).
Two families, keys by construction, exact grading, difficulty parameterized
past every current model:

  A. inversion — a chain of k invertible digit-transformations is applied to
     a planted integer; the candidate sees the chain and the OUTPUT and must
     recover the input. Difficulty knob: chain length.
  B. execution — a small deterministic program (planted semantics, executed
     at build time for the key); the candidate must predict its output.
     Difficulty knob: statements / loop depth / state entanglement.

Every item is SELF-TESTED at build time (forward-apply == output; exec is
deterministic). Administration: full item bank to every candidate (shared
items -> empirical difficulties), standalone calls, no tools, temperature
0.2, exact-match grading on a FINAL: line. Resumable per (model, item).

    python -m experiments.frontier_ladder
"""
from __future__ import annotations

import json
import random
import re
import time
from pathlib import Path

from viberank.clients import ProviderError, openrouter_client

EXP = Path(__file__).resolve().parent
DATA_PATH = EXP / "frontier_ladder_data.json"

CANDIDATES = (
    # anchors bridging the mid-tier scale
    ("openai/gpt-oss-120b", 1599.0),
    ("moonshotai/kimi-k2-0905", 1688.0),
    # the frontier band where the oral protocol died
    ("openai/gpt-5.2", 1744.0),
    ("moonshotai/kimi-k2.6", 1758.0),
    ("qwen/qwen3.6-plus", 1759.0),
    ("deepseek/deepseek-v4-pro", 1775.0),
    ("openai/gpt-5.4", 1829.0),
    ("anthropic/claude-opus-4.8", 1906.0),
    ("openai/gpt-5.5", 1911.0),
)

RUNGS = (4, 8, 14, 22, 32, 45)  # family-A chain lengths; family-B scales with same index
ITEMS_PER_RUNG = 2
DIGITS = 8
RETRY_SLEEPS = (5, 15, 30)

# ---------------- family A: invertible digit-transform chains ----------------
MOD = 10**DIGITS


def op_add(rng):
    a = rng.randrange(1, MOD)
    return (lambda x: (x + a) % MOD, f"add {a}, keep the last {DIGITS} digits")


def op_mul(rng):
    m = rng.choice([3, 7, 9, 11, 13, 17, 19, 21, 23, 27])
    return (lambda x: (x * m) % MOD, f"multiply by {m}, keep the last {DIGITS} digits")


def op_reverse(rng):
    return (
        lambda x: int(str(x).zfill(DIGITS)[::-1]),
        f"write as {DIGITS} digits (leading zeros included) and reverse the digit order",
    )


def op_rotate(rng):
    r = rng.randrange(1, DIGITS)
    return (
        lambda x, r=r: int(str(x).zfill(DIGITS)[r:] + str(x).zfill(DIGITS)[:r]),
        f"write as {DIGITS} digits and rotate left by {r} positions",
    )


def op_digitmap(rng):
    a = rng.choice([3, 7, 9])
    b = rng.randrange(10)
    return (
        lambda x, a=a, b=b: int(
            "".join(str((int(c) * a + b) % 10) for c in str(x).zfill(DIGITS))
        ),
        f"replace every digit d by (d*{a}+{b}) mod 10",
    )


def op_swap(rng):
    i, j = sorted(rng.sample(range(DIGITS), 2))
    def f(x, i=i, j=j):
        s = list(str(x).zfill(DIGITS))
        s[i], s[j] = s[j], s[i]
        return int("".join(s))
    return (f, f"write as {DIGITS} digits and swap the digits at positions {i+1} and {j+1} (1-indexed from the left)")


OPS = (op_add, op_mul, op_reverse, op_rotate, op_digitmap, op_swap)


def make_inversion_item(rng, k, ident):
    x0 = rng.randrange(10 ** (DIGITS - 1), MOD)
    fs, descs = [], []
    x = x0
    for _ in range(k):
        f, d = rng.choice(OPS)(rng)
        fs.append(f)
        descs.append(d)
        x = f(x)
    # self-test: forward application reproduces the output
    y = x0
    for f in fs:
        y = f(y)
    assert y == x
    steps = "\n".join(f"{i+1}. {d}" for i, d in enumerate(descs))
    prompt = (
        f"A secret {DIGITS}-digit number (it has no leading zero) was transformed by "
        f"applying the following {k} steps IN ORDER. All arithmetic keeps exactly "
        f"{DIGITS} digits (i.e. modulo {MOD}; write intermediate values with leading "
        f"zeros when needed).\n\n{steps}\n\nThe final result is {x:0{DIGITS}d}.\n\n"
        f"Recover the original number. Work backwards carefully step by step. "
        f"End your reply with a line 'FINAL: <the original {DIGITS}-digit number>'."
    )
    return {"id": ident, "family": "inversion", "rung": k, "prompt": prompt, "key": str(x0)}


# ---------------- family B: program-output prediction ----------------
def make_program_item(rng, level, ident):
    n_vars = 3 + level // 2
    n_iters = 6 + level * 3
    names = [f"v{i}" for i in range(n_vars)]
    init = {nm: rng.randrange(1, 30) for nm in names}
    lines = [f"{nm} = {val}" for nm, val in init.items()]
    lines.append(f"for i in range(1, {n_iters + 1}):")
    body = []
    for _ in range(2 + level // 2):
        a, b = rng.sample(names, 2)
        kind = rng.randrange(4)
        if kind == 0:
            body.append(f"    {a} = ({a} + {b} * i) % 997")
        elif kind == 1:
            body.append(f"    if {a} % 3 == {rng.randrange(3)}:")
            body.append(f"        {b} = ({b} + {rng.randrange(2, 9)}) % 997")
        elif kind == 2:
            body.append(f"    {a}, {b} = {b}, ({a} + i) % 997")
        else:
            body.append(f"    {a} = ({a} * {rng.choice([2, 3, 5])} + {b}) % 997")
    lines.extend(body)
    result_expr = " + ".join(names)
    code = "\n".join(lines)
    ns: dict = {}
    exec(code, {"__builtins__": {"range": range}}, ns)  # planted semantics: build-time key
    key = sum(ns[nm] for nm in names)
    ns2: dict = {}
    exec(code, {"__builtins__": {"range": range}}, ns2)  # self-test determinism
    assert sum(ns2[nm] for nm in names) == key
    prompt = (
        "Execute the following program mentally and give the final value of "
        f"{result_expr}. Do not guess: trace it exactly.\n\n```python\n{code}\n"
        f"print({result_expr})\n```\n\nEnd your reply with a line 'FINAL: <the printed number>'."
    )
    return {"id": ident, "family": "execution", "rung": level, "prompt": prompt, "key": str(key)}


def build_bank():
    rng = random.Random(20260828)
    items = []
    for ri, k in enumerate(RUNGS):
        for j in range(ITEMS_PER_RUNG):
            items.append(make_inversion_item(rng, k, f"inv-{k}-{j}"))
            items.append(make_program_item(rng, ri * 2 + 2, f"exe-{ri * 2 + 2}-{j}"))
    return items


FINAL_RE = re.compile(r"FINAL[:\s]*([0-9][0-9 ,]*)", re.I)


def extract(text):
    hits = FINAL_RE.findall(text or "")
    if hits:
        return hits[-1].replace(" ", "").replace(",", "").lstrip("0") or "0"
    nums = re.findall(r"\b\d{3,}\b", text or "")
    return (nums[-1].lstrip("0") or "0") if nums else None


def grade(answer, key):
    got = extract(answer)
    return got is not None and got == key.lstrip("0")


def ask(client, prompt, label):
    for attempt, sleep_s in enumerate((0,) + RETRY_SLEEPS):
        if sleep_s:
            time.sleep(sleep_s)
        try:
            result = client.complete_with_usage(
                [
                    {
                        "role": "system",
                        "content": (
                            "Solve the problem by reasoning alone - you have no tools, "
                            "no code execution. Be careful and exact."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                # reasoning models spend from the same budget as content; 12k
                # starved several (qwen3.6-plus returned null content on all
                # 24 items, kimi-k2.6/deepseek truncated mid-trace on ~10).
                max_tokens=60000,
            )
            text = result.content
            if not (text or "").strip() or text.strip() == "None":
                raise ProviderError("empty/null content (reasoning ate the budget)")
            return text, (getattr(result, "prompt_tokens", 0) or 0), (
                getattr(result, "completion_tokens", 0) or 0
            )
        except ProviderError as exc:
            print(f"    {label} attempt {attempt + 1} failed: {str(exc)[:110]}")
    raise RuntimeError(f"{label}: retries exhausted")


def main():
    items = build_bank()
    print(f"item bank: {len(items)} items, all self-tests passed")
    data = (
        json.loads(DATA_PATH.read_text(encoding="utf-8"))
        if DATA_PATH.is_file()
        else {"items": {it["id"]: {"family": it["family"], "rung": it["rung"], "key": it["key"]} for it in items},
              "responses": {}, "usage": {}}
    )
    for model, elo in CANDIDATES:
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
            ok = grade(text, it["key"])
            # keep the full response: partial-credit re-scoring (longest valid
            # prefix of the back-solve, per-variable traces) and texture
            # analyses need the text, not just the bit.
            store["answers"][it["id"]] = {
                "correct": ok,
                "extracted": extract(text),
                "text": text,
            }
            u = data["usage"].setdefault(model, {"prompt": 0, "completion": 0})
            u["prompt"] += tin
            u["completion"] += tout
            DATA_PATH.write_text(json.dumps(data, indent=1, ensure_ascii=True), encoding="utf-8")
            print(f"{model[:26]:<26} {it['id']:<10} -> {'PASS' if ok else 'fail'}")
        n = len(store["answers"])
        nc = sum(1 for a in store["answers"].values() if a["correct"])
        print(f"== {model}: {nc}/{n} correct")
    print("done")


if __name__ == "__main__":
    main()

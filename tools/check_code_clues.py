"""
Independent checker for code_clues (Code Lock) problems.

Does not import the generator. It reads the number of wheels from the prompt,
checks it against the scene, scores the answer against every clue with its own
counting code, enumerates every code the wheels could show (itertools.product,
keeping codes with all-different symbols) to confirm exactly one fits, and
re-derives every wrong answer's tags from its own reading of each mistake.

Usage: python3 check_code_clues.py L1-1000.js [...]   (files from code-lock/)
"""

import json
import re
import sys
from itertools import product

NAMES = {"S": "sun", "M": "moon", "T": "star", "H": "heart", "L": "leaf", "D": "drop", "Z": "bolt", "B": "bell"}
WORD = {"three": 3, "four": 4}


def score(guess, code):
    right = wrong = 0
    for i, g in enumerate(guess):
        if code[i] == g:
            right += 1
        elif g in code:
            wrong += 1
    return right, wrong


def readings(code, clues):
    """The mistakes under which a code that breaks some clue would look right."""
    true = [score(g, code) == (r, w) for g, r, w in clues]
    if all(true):
        return None
    out = set()
    if all(ok or (r, w) == (0, 0) for ok, (g, r, w) in zip(true, clues)):
        out.add("SKIPS_EMPTY_CLUE")
    if all(sum(score(g, code)) == r + w for g, r, w in clues):
        out.add("CLUE_POSITION_IGNORED")
    if all(score(g, code) == (w, r) for g, r, w in clues):
        out.add("CLUE_FEEDBACK_SWAPPED")
    if true.count(False) == 1:
        out.add("SKIPS_A_CLUE")
    return out


def check(p):
    errs = []
    sc = p["scene"]
    n, pool, clues = sc["slots"], sc["pool"], [tuple(c) for c in sc["clues"]]
    m = re.search(r"a lock with (\w+) wheels", p["prompt"])
    if not m or WORD.get(m.group(1)) != n:
        errs.append("prompt does not give the number of wheels in the scene")
    if f"uses {m.group(1) if m else '?'} different symbols" not in p["prompt"]:
        errs.append("prompt does not say the symbols are all different")
    if len(set(pool)) != len(pool) or not set(pool) <= set(NAMES):
        errs.append("bad symbol pool")
    for g, r, w in clues:
        if len(g) != n or len(set(g)) != n or not set(g) <= set(pool):
            errs.append(f"guess {g} is not a valid code")
        if r == n:
            errs.append(f"guess {g} is the code itself")

    ans = p["answer_value"]
    if len(ans) != n or len(set(ans)) != n or not set(ans) <= set(pool):
        return errs + [f"answer {ans} is not a valid code"]
    for g, r, w in clues:
        if score(g, ans) != (r, w):
            errs.append(f"clue {g} says {(r, w)} but the answer gives {score(g, ans)}")
    codes = ["".join(c) for c in product(pool, repeat=n) if len(set(c)) == n]
    fitting = [c for c in codes if readings(c, clues) is None]
    if fitting != [ans]:
        errs.append(f"codes that fit every clue: {fitting[:5]} (want only {ans})")

    first = None
    if p["entry"] == "choice":
        o = p["options"]
        if p["question_type"] != "choose" or len(o) != 4 or len(set(o)) != 4:
            errs.append("a choice question needs four different codes")
        if not 0 <= p["answer_index"] < len(o) or o[p["answer_index"]] != ans:
            errs.append("marked option is not the answer")
        d = {x["option"]: x["misconceptions"] for x in p["distractors"]}
        if sorted(d) != sorted(c for c in o if c != ans):
            errs.append("distractors do not match the wrong options")
        for c, tags in d.items():
            got = readings(c, clues)
            if not tags or got is None or set(tags) != got:
                errs.append(f"option {c} tagged {tags}, recomputed {sorted(got or [])}")
        if not all(any(s in c for c in o if c != ans) for s in ans):
            errs.append("an answer symbol appears in no wrong option (guessable)")
        if p["question"] != "Which code opens the lock?":
            errs.append("unexpected question")
    elif p["entry"] == "code":
        if p["question_type"] != "crack" or p["options"]:
            errs.append("a code question has no options")
        vt = p["value_tags"]
        want = {c: sorted(readings(c, clues)) for c in codes if c != ans and readings(c, clues)}
        if {k: sorted(v) for k, v in vt.items()} != want:
            errs.append("typed-code tags differ from the recomputed ones")
        if ans in vt:
            errs.append("the answer has tags")
        if not p["question"].startswith("What is the code?"):
            errs.append("unexpected question")
    else:
        errs.append(f"unexpected entry {p['entry']}")
    if p["explanation"][-1] != "So the code is " + ", ".join(NAMES[s] for s in ans) + ".":
        errs.append("the explanation does not end with the answer")
    return errs


if __name__ == "__main__":
    bad = 0
    for path in sys.argv[1:]:
        text = open(path).read()
        rec = json.loads(text[text.index("{"):text.rindex("}") + 1])
        e = check(rec)
        if e:
            bad += 1
            print(path, e)
    print(f"{len(sys.argv) - 1 - bad} ok, {bad} bad")

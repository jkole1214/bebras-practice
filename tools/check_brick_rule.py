"""
Independent checker for brick_rule (Brick Pyramid) problems.

Does not import the generator. It rebuilds the pyramid from the SVG picture (each
brick's data-k, its drawn fill, its letter and whether it is tappable), checks it
against the scene, and solves again with arithmetic: with red, yellow, blue as 0, 1, 2,
the brick on top of a and b is (-(a + b)) mod 3. Hidden bricks are found by trying
every colouring; wrong answers' tags are re-derived from its own versions of each mistake.

Usage: python3 check_brick_rule.py L1-1000.js [...]   (files from brick-pyramid/)
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from itertools import product

NS = "{http://www.w3.org/2000/svg}"
V = {"R": 0, "Y": 1, "B": 2}
L = "RYB"
DRAWN = {"#d9534f": "R", "#f2c14e": "Y", "#3b6fd8": "B", "#f4f1ea": ""}
WORD = {"red": "R", "yellow": "Y", "blue": "B"}


def top(a, b):
    return L[(-(V[a] + V[b])) % 3]


def tops(bottom, f=top):
    rows = [list(bottom)]
    while len(rows[-1]) > 1:
        rows.append([f(x, y) for x, y in zip(rows[-1], rows[-1][1:])])
    return {f"{r},{c}": v for r, row in enumerate(rows) for c, v in enumerate(row)}


MISTAKES = {
    "COPIES_A_SUPPORT": [lambda a, b: a if a != b else top(a, b), lambda a, b: b if a != b else top(a, b)],
    "MATCH_MEANS_CHANGE": [lambda a, b: L[(V[a] + 1) % 3] if a == b else top(a, b)],
}


def parse(svg):
    root = ET.fromstring(svg)
    bricks, edit, errs = {}, [], []
    for g in root.iter(NS + "g"):
        if "brick" not in (g.get("class") or "").split():
            continue
        k, col = g.get("data-k"), g.get("data-col")
        drawn = DRAWN.get(g.find(NS + "rect").get("fill"), "?")
        label = g.find(NS + "text").text or ""
        tappable = "edit" in g.get("class").split()
        if drawn != col:
            errs.append(f"brick {k} drawn {drawn or 'empty'} but data says {col or 'empty'}")
        if label != (col or ("?" if tappable else "")):
            errs.append(f"brick {k} labelled {label!r}")
        if col:
            bricks[k] = col
        if tappable:
            edit.append(k)
    return bricks, edit, errs


def check(p):
    shown, edit, errs = parse(p["svg"])
    sc = p["scene"]
    n = sc["rows"]
    if shown != sc["given"] or sorted(edit) != sorted(sc["edit"]):
        errs.append("scene differs from the picture")
    keys = {f"{r},{c}" for r in range(n) for c in range(n - r)}
    if not set(shown) | set(edit) <= keys:
        return errs + ["a brick outside the pyramid"]
    if "all the same colour or all different" not in p["prompt"]:
        errs.append("prompt does not state the rule")
    q = p["question_type"]

    if q in ("fill", "count"):
        if sorted(shown) != sorted(f"0,{c}" for c in range(n)):
            errs.append("fill and count show exactly the bottom row")
        full = tops("".join(shown[f"0,{c}"] for c in range(n)))
    if q == "fill":
        if p["entry"] != "bricks" or sorted(edit) != sorted(keys - set(shown)):
            errs.append("fill must let the student colour every other brick")
        if p["answer_value"] != {k: full[k] for k in edit}:
            errs.append("answer differs from the recomputed pyramid")
    elif q == "count":
        m = re.fullmatch(r"When the pyramid is finished, how many bricks are (red|yellow|blue)\?", p["question"])
        if not m:
            return errs + ["unknown question"]
        ask = WORD[m.group(1)]
        truth = list(full.values()).count(ask)
        if p["answer_value"] != truth:
            errs.append(f"answer {p['answer_value']} != recomputed {truth}")
        o = p["options"]
        if o[p["answer_index"]] != truth or o.count(truth) != 1:
            errs.append("marked option is not the recomputed answer")
        if truth in (min(o), max(o)):
            errs.append("the right answer is the smallest or largest option (guessable)")
        bottom = "".join(shown[f"0,{c}"] for c in range(n))
        got = {}
        for tag, fs in MISTAKES.items():
            for f in fs:
                got.setdefault(list(tops(bottom, f).values()).count(ask), set()).add(tag)
        got.setdefault(truth - bottom.count(ask), set()).add("FORGETS_BOTTOM_ROW")
        for d in p["distractors"]:
            if not d["misconceptions"] or set(d["misconceptions"]) - got.get(d["option"], set()):
                errs.append(f"option {d['option']} tagged {d['misconceptions']}, recomputed {sorted(got.get(d['option'], []))}")
        if sorted(d["option"] for d in p["distractors"]) != sorted(v for v in o if v != truth):
            errs.append("every wrong option needs tags")
        if truth in got and "COPIES_A_SUPPORT" in got[truth]:
            errs.append("copying a support gives the right count")
    elif q == "hidden":
        hide = sorted(edit)
        if not all(k.startswith("0,") for k in hide) or any(k in shown for k in hide):
            errs.append("hidden bricks must be empty bottom bricks")
        upper = {k: v for k, v in shown.items() if not k.startswith("0,")}
        if not upper:
            errs.append("no brick above the bottom row is shown")
        if sorted([k for k in shown if k.startswith("0,")] + hide) != sorted(f"0,{c}" for c in range(n)):
            errs.append("the bottom row must be shown except for the hidden bricks")

        def fill(combo, f=top):
            b = dict(shown)
            b.update(zip(hide, combo))
            return tops("".join(b[f"0,{c}"] for c in range(n)), f)
        combos = ["".join(x) for x in product(L, repeat=len(hide))]
        good = [x for x in combos if all(fill(x)[k] == v for k, v in upper.items())]
        if len(good) != 1:
            return errs + [f"{len(good)} colourings fit the shown bricks"]
        if p["answer_value"] != dict(zip(hide, good[0])):
            errs.append("answer differs from the only colouring that fits")
        want = {}
        for x in combos:
            if x != good[0]:
                tags = sorted(t for t, fs in MISTAKES.items() if any(all(fill(x, f)[k] == v for k, v in upper.items()) for f in fs))
                if tags:
                    want[x] = tags
        if {k: sorted(v) for k, v in p["value_tags"].items()} != want:
            errs.append("hidden-brick tags differ from the recomputed ones")
    else:
        errs.append(f"unknown question type {q}")
    last = p["explanation"][-1]
    if q == "count" and not last.endswith(f"So {p['answer_value']} bricks are {m.group(1)}."):
        errs.append("the explanation does not end with the answer")
    if q == "hidden":
        names = [{"R": "red", "Y": "yellow", "B": "blue"}[p["answer_value"][k]] for k in hide]
        if not all(w in last for w in names) or not last.startswith("So the hidden brick"):
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

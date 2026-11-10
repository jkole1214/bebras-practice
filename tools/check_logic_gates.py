"""
Independent checker for logic_gates problems. Does not import the generator.

Checks that the picture's gate shapes (read from the SVG, in drawing order)
match the scene tree, then evaluates every set of pressed buttons by brute
force and re-derives the answer, the option key, the misreading tags and
the counts.
"""

import itertools
import json
import re
import sys

RULE = {"AND": lambda a, b: a and b, "XOR": lambda a, b: a != b, "OR": lambda a, b: a or b}


def ev(node, on, swap=None):
    if "in" in node:
        return node["in"] in on
    a, b = ev(node["kids"][0], on, swap), ev(node["kids"][1], on, swap)
    op = node["op"]
    if swap and op == swap[0]:
        op = swap[1]
    return RULE[op](a, b)


def preorder(node):
    return [] if "in" in node else [node["op"]] + preorder(node["kids"][0]) + preorder(node["kids"][1])


def subsets(n):
    return [set(c) for r in range(n + 1) for c in itertools.combinations(range(1, n + 1), r)]


def check(p):
    errs = []
    tree, n = p["scene"]["tree"], p["scene"]["buttons"]
    drawn = re.findall(r'data-op="(AND|XOR|OR)"', p["svg"])
    if drawn != preorder(tree):
        errs.append("gate shapes in the picture differ from the scene")
    shapes = {"AND": "polygon", "XOR": "rect", "OR": "circle"}
    for op, tag in shapes.items():
        if len(re.findall(rf'<{tag} class="gate g-{op.lower()}"', p["svg"])) != drawn.count(op):
            errs.append(f"{op} drawn with the wrong shape")
    if sorted(map(int, re.findall(r'data-btn="(\d+)"', p["svg"]))) != list(range(1, n + 1)):
        errs.append("buttons in the picture are not 1..n")
    good = [s for s in subsets(n) if ev(tree, s)]
    if not good:
        errs.append("light can never turn on")
    qt = p["question_type"]
    if qt == "choose":
        works = [o for o in p["options"] if ev(tree, set(o))]
        if len(works) != 1 or p["options"][p["answer_index"]] != works[0]:
            errs.append("not exactly one working option, or key wrong")
        for d in p["distractors"]:
            s = set(d["option"])
            if not d["misconceptions"]:
                errs.append("untagged distractor")
            if "XOR_AS_OR" in d["misconceptions"] and not ev(tree, s, ("XOR", "OR")):
                errs.append(f"{d['option']} tagged XOR_AS_OR but does not light under that reading")
            if "BOTH_AS_EITHER" in d["misconceptions"] and not ev(tree, s, ("AND", "OR")):
                errs.append(f"{d['option']} tagged BOTH_AS_EITHER but does not light under that reading")
    elif qt == "press":
        if not ev(tree, set(p["answer_value"])):
            errs.append("example answer does not light the bulb")
    elif qt == "fewest":
        m = min(len(s) for s in good)
        if p["answer_value"] != m:
            errs.append(f"fewest {p['answer_value']} != {m}")
    elif qt == "count":
        if p["answer_value"] != len(good):
            errs.append(f"count {p['answer_value']} != {len(good)}")
        tags = {k: int(v) for v, ks in p["value_tags"].items() for k in ks}
        if "XOR_AS_OR" in tags and tags["XOR_AS_OR"] != sum(ev(tree, s, ("XOR", "OR")) for s in subsets(n)):
            errs.append("XOR_AS_OR count wrong")
        if str(p["answer_value"]) in p["value_tags"]:
            errs.append("a misconception value equals the answer")
    else:
        errs.append("unknown question type")
    if not p["explanation"] or not p["hints"]:
        errs.append("missing explanation or hints")
    return errs


if __name__ == "__main__":
    probs = json.load(open(sys.argv[1]))
    bad = 0
    for p in probs:
        e = check(p)
        if e:
            bad += 1
            print(p["level"], p["seed"], e[:3])
    print(f"{len(probs) - bad}/{len(probs)} problems pass")

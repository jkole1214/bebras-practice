"""
Independent checker for conditional_trace problems.

Deliberately does not import the generator. It re-reads the scene from the
problem's JSON and re-implements the semantics from scratch, so a bug in the
generator's evaluator cannot hide itself.
"""

import json
import sys

CMP = {">": lambda a, b: a > b, "<": lambda a, b: a < b,
       ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b}


def run(tree, roll):
    while "outcome" not in tree:
        c = tree["if"]
        rhs = c["const"] if "const" in c else roll[c["right"]]
        tree = tree["then"] if CMP[c["op"]](roll[c["left"]], rhs) else tree["else"]
    return tree["outcome"]


def leaf_names(t):
    return [t["outcome"]] if "outcome" in t else leaf_names(t["then"]) + leaf_names(t["else"])


def check(p):
    errs = []
    s = p["scene"]
    tree = s["tree"]
    n = s["dice"]
    names = leaf_names(tree)
    if len(set(names)) != len(names):
        errs.append("duplicate outcome labels")
    if len(p["options"]) != len({json.dumps(o) for o in p["options"]}):
        errs.append("duplicate options")
    if p["question_type"] == "count":
        import itertools
        target = s["target"]
        truth = sum(1 for r in itertools.product(range(1, 7), repeat=n) if run(tree, r) == target)
        if truth != p["answer_value"]:
            errs.append(f"count key {p['answer_value']} != brute force {truth}")
        if str(truth) in p["value_tags"]:
            errs.append("a misconception value equals the answer")
        if not p["value_tags"]:
            errs.append("no misconception values")
        return errs + ([] if p["explanation"] and p["hints"] else ["missing explanation or hints"])
    if p["question_type"] == "trace":
        truth = run(tree, s["roll"])
        if p["options"][p["answer_index"]] != truth:
            errs.append(f"answer key wrong: key={p['options'][p['answer_index']]} truth={truth}")
        if sorted(p["options"]) != sorted(names):
            errs.append("options are not exactly the outcomes")
    else:
        target = s["target"]
        hits = [i for i, o in enumerate(p["options"]) if run(tree, o) == target]
        if hits != [p["answer_index"]]:
            errs.append(f"expected exactly one correct option at {p['answer_index']}, got {hits}")
        for o in p["options"]:
            if len(o) != n or not all(1 <= v <= 6 for v in o):
                errs.append(f"invalid roll {o}")
    for d in p["distractors"]:
        if not d["misconceptions"]:
            errs.append(f"untagged distractor {d['option']}")
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
            print(p["level"], p["seed"], e)
    print(f"{len(probs) - bad}/{len(probs)} problems pass")

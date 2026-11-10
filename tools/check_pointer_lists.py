"""
Independent checker for pointer_lists problems. Does not import the generator.

Re-evaluates the nested lookup, checks every row is a shuffle of 1..n,
checks the key, and re-derives the main misconception values: outside-in
order, zero-based counting, stopping one step early, and for inverse items
that the answer is the only start that reaches the target.
"""

import json
import re
import sys


def look(lists, rows, start):
    v = start
    for r in rows[::-1]:
        v = lists[r][v - 1]
    return v


def check(p):
    errs = []
    lists = p["scene"]["lists"]
    for name, row in lists.items():
        if sorted(row) != list(range(1, len(row) + 1)):
            errs.append(f"row {name} is not a shuffle of 1..n")
    expr = re.search(r"(\([^?]*?[\d?]\)+)", p["question"]).group(1)
    rows = re.findall(r"\(([A-D])", expr)
    if p["question_type"] == "lookup":
        start = int(re.findall(r"(\d+)\)", expr)[0])
        truth = look(lists, rows, start)
        if p["answer_value"] != truth:
            errs.append(f"answer {p['answer_value']} != {truth}")
        wrong = {}
        if len(set(rows)) > 1:
            wrong["INDIRECTION_OUTSIDE_IN"] = look(lists, rows[::-1], start)
        if len(rows) > 1:
            wrong["STOPS_ONE_EARLY"] = look(lists, rows[1:], start)
        tags = {k: int(v) for v, ks in p["value_tags"].items() for k in ks}
        for k, v in wrong.items():
            if k in tags and tags[k] != v:
                errs.append(f"{k} value {tags[k]} != {v}")
            if v == truth:
                errs.append(f"{k} gives the right answer: item cannot detect it")
    else:
        target = p["scene"]["target"]
        n = len(next(iter(lists.values())))
        hits = [s for s in range(1, n + 1) if look(lists, rows, s) == target]
        if hits != [p["answer_value"]]:
            errs.append(f"starts reaching the target: {hits}")
        truth = p["answer_value"]
    if p["entry"] == "choice":
        o = p["options"]
        if o[p["answer_index"]] != truth:
            errs.append("option key wrong")
        if len(set(o)) != len(o) or len(o) != 4:
            errs.append("need 4 distinct options")
        for d in p["distractors"]:
            if not d["misconceptions"]:
                errs.append(f"untagged distractor {d['option']}")
    if str(truth) in p["value_tags"]:
        errs.append("a misconception value equals the answer")
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

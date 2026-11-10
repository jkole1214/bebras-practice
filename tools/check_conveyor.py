"""
Independent checker for conveyor problems. Does not import the generator.

Re-simulates every belt with a pile of nuts, recomputes the most nuts in the
bucket and the fewest parts to add, and recomputes the misconception values.
"""

import json
import sys


def ok(belt):
    pile = []
    for t in belt:
        if t in "nN":
            pile.append(t)
        elif not pile or {"b": "n", "B": "N"}[t] != pile.pop():
            return False
    return not pile


def peak(belt):
    c = best = 0
    for t in belt:
        c += 1 if t == "n" else -1
        best = max(best, c)
    return best


def fix_count(belt):
    need_nuts = held = 0
    for t in belt:
        if t == "n":
            held += 1
        elif held:
            held -= 1
        else:
            need_nuts += 1
    return need_nuts, held


def check(p):
    errs = []
    qt = p["question_type"]
    if qt in ("valid", "stack"):
        o = p["options"]
        good = [b for b in o if ok(b)]
        if len(good) != 1:
            errs.append(f"{len(good)} working belts among the options")
        elif o[p["answer_index"]] != good[0] or p["answer_value"] != good[0]:
            errs.append("answer key wrong")
        if len(set(o)) != 4:
            errs.append("duplicate options")
        if qt == "valid" and any(set(b) - set("nb") for b in o):
            errs.append("two sizes in a one-size level")
        for d in p["distractors"]:
            b, tags = d["option"], d["misconceptions"]
            if not tags:
                errs.append(f"untagged distractor {b}")
            nuts = sum(t in "nN" for t in b)
            if "TOTALS_ONLY_MATCHING" in tags and nuts * 2 != len(b):
                errs.append(f"{b}: tagged totals-only but totals differ")
            if "IGNORES_LEFTOVERS" in tags:
                c = 0
                for t in b:
                    c += 1 if t in "nN" else -1
                    if c < 0:
                        errs.append(f"{b}: tagged leftovers but goes negative")
                        break
            if "SIZES_SEPARATELY" in tags:
                for size in "nN":
                    sub = [t for t in b if t.isupper() == size.isupper()]
                    if not ok(sub):
                        errs.append(f"{b}: tagged sizes-separately but a size fails on its own")
        if qt == "stack" and not ok(p["answer_value"]):
            errs.append("answer belt fails")
    elif qt == "depth":
        b = p["scene"]["belt"]
        if not ok(b):
            errs.append("depth belt should work")
        if peak(b) != p["answer_value"]:
            errs.append(f"answer {p['answer_value']} != peak {peak(b)}")
        tag = {k: v for v, ks in p["value_tags"].items() for k in ks}
        if tag.get("TOTAL_NUTS_FOR_DEPTH") not in (None, str(b.count("n"))):
            errs.append("total-nuts value wrong")
    elif qt == "repair":
        b = p["scene"]["belt"]
        short, left = fix_count(b)
        if short + left != p["answer_value"]:
            errs.append(f"answer {p['answer_value']} != {short}+{left}")
        tag = {k: v for v, ks in p["value_tags"].items() for k in ks}
        if tag.get("DIFFERENCE_FOR_REPAIR") not in (None, str(abs(b.count("n") - b.count("b")))):
            errs.append("difference value wrong")
        if tag.get("SHORTFALL_ONLY") not in (None, str(short)) or tag.get("LEFTOVER_ONLY") not in (None, str(left)):
            errs.append("shortfall/leftover value wrong")
    else:
        errs.append("unknown question type")
    if str(p["answer_value"]) in p["value_tags"]:
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

"""
Independent checker for signal_code problems.

Does not import the generator. It reads the codebook and signal exactly as the
student sees them (the codebook rows and the signal string), counts readings
by brute force over every way to cut the signal into pieces (no dynamic
programming), and re-checks the answer key, option uniqueness, shortcuts and
misconception tags that it can recompute independently.
"""

import itertools
import json
import sys


def all_cuts(signal):
    n = len(signal)
    for mask in range(1 << max(n - 1, 0)):
        pieces, start = [], 0
        for i in range(1, n):
            if mask >> (i - 1) & 1:
                pieces.append(signal[start:i])
                start = i
        pieces.append(signal[start:])
        yield pieces


def brute_readings(rows, signal):
    lookup = {c: w for w, c in rows}
    out = set()
    for pieces in all_cuts(signal):
        if all(p in lookup for p in pieces):
            out.add(tuple(lookup[p] for p in pieces))
    return out


def check(p):
    errs = []
    rows = p["codebook"]
    words = [w for w, _ in rows]
    codes = [c for _, c in rows]
    if len(set(words)) != len(words) or len(set(codes)) != len(codes):
        errs.append("duplicate word or code in codebook")
    if any(set(c) - {"S", "L"} or not c for c in codes):
        errs.append("code uses symbols other than S and L")
    if p["scene"]["code"] != {w: c for w, c in rows}:
        errs.append("scene code differs from displayed codebook")
    qt = p["question_type"]
    if qt == "decode":
        rs = brute_readings(rows, p["signal"])
        if len(rs) != 1:
            errs.append(f"decode signal has {len(rs)} readings, expected 1")
        elif ", ".join(next(iter(rs))) != p["options"][p["answer_index"]]:
            errs.append("decode answer key wrong")
        for i, o in enumerate(p["options"]):
            if i != p["answer_index"] and tuple(o.split(", ")) in rs:
                errs.append("a distractor is also a valid reading")
    elif qt == "count":
        n = len(brute_readings(rows, p["signal"]))
        if n != p["answer_value"]:
            errs.append(f"count key {p['answer_value']} != brute force {n}")
        if p["entry"] == "choice":
            if p["options"][p["answer_index"]] != n:
                errs.append("count option key wrong")
            if min(p["options"]) == n or max(p["options"]) == n:
                errs.append("shortcut: answer is smallest or largest option")
        if str(n) in p["value_tags"]:
            errs.append("a misconception value equals the true answer")
        # recompute two misconception values independently
        rs = brute_readings(rows, p["signal"])
        ws = len({tuple(sorted(r)) for r in rs})
        if ws != n and "COUNTS_WORD_SETS" not in p["value_tags"].get(str(ws), []):
            errs.append("word-set misconception value missing or wrong")
        if "FIRST_PARSE_ONLY" not in p["value_tags"].get("1", []):
            errs.append("first-parse misconception (value 1) not tagged")
    elif qt == "inverse":
        k = p["scene"]["target"]
        hits = [i for i, s in enumerate(p["options"]) if len(brute_readings(rows, s)) == k]
        if hits != [p["answer_index"]]:
            errs.append(f"expected exactly one signal with {k} readings at {p['answer_index']}, got {hits}")
        for d in p["distractors"]:
            if len(brute_readings(rows, d["option"])) != d["meanings"]:
                errs.append("distractor meaning count wrong")
    if len(p.get("options", [])) != len({json.dumps(o) for o in p.get("options", [])}):
        errs.append("duplicate options")
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
            print(p["level"], p["seed"], e[:3])
    print(f"{len(probs) - bad}/{len(probs)} problems pass")

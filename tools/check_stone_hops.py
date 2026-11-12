"""
Independent checker for stone_hops (Frog Hops) problems.

Does not import the generator. It rebuilds the row from the SVG picture (each spot's data-n,
whether it holds a stone, its position and label; the frog's stone; the hop rule), checks it
against the scene and the prompt, then solves again with a different method: dynamic
programming over (visited set, current stone) bitmasks counts every full trip and records each
one. Wrong answers' tags are re-derived from its own versions of each mistake.

Usage: python3 check_stone_hops.py L1-1000.js [...]   (files from frog-hops/)
"""

import json
import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://www.w3.org/2000/svg}"


def parse(svg):
    root = ET.fromstring(svg)
    spots, frog, rule, errs = {}, None, None, []
    for g in root.iter(NS + "g"):
        cls = (g.get("class") or "").split()
        if "spot" in cls:
            n = int(g.get("data-n"))
            c, t = g.find(NS + "circle"), g.find(NS + "text")
            if t is None or t.text != str(n):
                errs.append(f"spot {n} is labelled {t.text if t is not None else None!r}")
            spots[n] = ("stone" in cls, float(c.get("cx")))
        elif "frog" in cls:
            frog = int(g.get("data-at"))
        elif "rule" in cls:
            rule = (int(g.get("data-fwd")), int(g.get("data-back")), "".join(g.itertext()))
    return spots, frog, rule, errs


def trips(stones, a, b, s):
    """Every full trip from s, by DP over (visited mask, last stone); each state keeps its paths."""
    idx = {x: i for i, x in enumerate(stones)}
    full = (1 << len(stones)) - 1
    layer = {(1 << idx[s], s): [[s]]}
    for _ in range(len(stones) - 1):
        nxt = {}
        for (mask, x), paths in layer.items():
            for y in (x + a, x - b):
                if y in idx and not mask >> idx[y] & 1:
                    nxt.setdefault((mask | 1 << idx[y], y), []).extend(p + [y] for p in paths)
        layer = nxt
    return [p for (mask, _), ps in layer.items() if mask == full for p in ps]


def stuck_run(stones, a, b, s, prefer_forward):
    path = [s]
    while True:
        fw, bk = path[-1] + a, path[-1] - b
        ok = [y for y in ((fw, bk) if prefer_forward else (bk, fw)) if y in stones and y not in path]
        if not ok:
            return path
        path.append(ok[0])


def list_tags(a, b, seq):
    d = [y - x for x, y in zip(seq, seq[1:])]
    t = set()
    if any(h not in (a, -b) for h in d):
        t.add("SWAPS_HOP_DIRECTIONS" if all(h in (b, -a) for h in d) else "HOPS_WRONG_SIZE")
    if len(set(seq)) != len(seq):
        t.add("LANDS_TWICE")
    return t


def check(p):
    spots, frog, rule, errs = parse(p["svg"])
    sc = p["scene"]
    m = sc["spots"]
    if sorted(spots) != list(range(1, m + 1)):
        return errs + ["spots are not numbered 1 to the end"]
    xs = [spots[n][1] for n in range(1, m + 1)]
    if any(abs((xs[i + 1] - xs[i]) - (xs[1] - xs[0])) > 0.01 or xs[1] <= xs[0] for i in range(m - 1)):
        errs.append("spots are not evenly spaced from left to right")
    stones = [n for n in range(1, m + 1) if spots[n][0]]
    if stones != sc["stones"] or frog != sc["start"] or not rule or rule[:2] != (sc["fwd"], sc["back"]):
        errs.append("scene differs from the picture")
    a, b, s = sc["fwd"], sc["back"], sc["start"]
    unit = lambda k: f"{k} spot{'' if k == 1 else 's'}"
    if rule and f"{unit(a)} forward or {unit(b)} back" not in rule[2]:
        errs.append("the picture's rule text is wrong")
    water = [n for n in range(1, m + 1) if n not in stones]
    pr = p["prompt"]
    if (f"starts on stone {s}." not in pr or f"exactly {unit(a)} forward" not in pr or f"exactly {unit(b)} back" not in pr
            or "never lands on the same stone twice" not in pr):
        errs.append("prompt does not state the rule")
    named = sorted(int(x) for x in re.findall(r"\d+", (re.search(r"Spots? ([\d, and]+) (?:is|are) water", pr) or [None, ""])[1]))
    if named != water:
        errs.append("prompt names the wrong water spots")
    if s not in stones:
        return errs + ["the frog is not on a stone"]
    full = trips(stones, a, b, s)
    if len(full) != 1:
        return errs + [f"{len(full)} full trips exist"]
    tour = full[0]
    if p["question_type"] != "last" and p["answer_value"] != tour:
        errs.append("answer differs from the recomputed trip")
    d = [y - x for x, y in zip(tour, tour[1:])]
    if a not in d or -b not in d:
        errs.append("the trip uses only one kind of hop")
    q = p["question_type"]

    if q == "check":
        o = p["options"]
        if p["entry"] != "choice" or o[p["answer_index"]] != tour or o.count(tour) != 1 or len(o) < 3:
            errs.append("marked option is not the recomputed trip")
        if len({len(x) for x in o}) != 1:
            errs.append("lists differ in length (guessable)")
        got = {json.dumps(x["option"]): x["misconceptions"] for x in p["distractors"]}
        if sorted(got) != sorted(json.dumps(x) for x in o if x != tour):
            errs.append("every wrong option needs tags")
        for x in o:
            if x == tour:
                continue
            want = list_tags(a, b, x)
            if not want or any(y not in stones for y in x) or x[0] != s:
                errs.append(f"option {x} is not a wrong trip from the start")
            if set(got.get(json.dumps(x), [])) != want:
                errs.append(f"option {x} tagged {got.get(json.dumps(x))}, recomputed {sorted(want)}")
        if p["explanation"][-1] != f"So the right list is {' → '.join(map(str, tour))}.":
            errs.append("the explanation does not end with the answer")

    elif q == "last":
        truth = tour[-1]
        o = p["options"]
        if p["entry"] != "choice" or p["answer_value"] != truth or o[p["answer_index"]] != truth or o.count(truth) != 1:
            errs.append("marked option is not the recomputed last stone")
        if truth in (min(o), max(o)) or len(o) < 3:
            errs.append("the right answer is the smallest or largest option (guessable)")
        want = {max(stones): {"FAR_END_IS_LAST"}}
        for f in (True, False):
            r = stuck_run(stones, a, b, s, f)
            if len(r) < len(stones):
                want.setdefault(r[-1], set()).add("STOPS_AT_DEAD_END")
        ends = {t[-1] for t in trips(stones, b, a, s)}
        if len(ends) == 1:
            want.setdefault(ends.pop(), set()).add("SWAPS_HOP_DIRECTIONS")
        if truth in want:
            errs.append(f"{sorted(want[truth])} gives the right stone")
        if s == max(stones):
            errs.append("the frog starts at the far end")
        got = {x["option"]: x["misconceptions"] for x in p["distractors"]}
        if sorted(got) != sorted(x for x in o if x != truth):
            errs.append("every wrong option needs tags")
        for x, t in got.items():
            if not t or set(t) != want.get(x, set()):
                errs.append(f"option {x} tagged {t}, recomputed {sorted(want.get(x, []))}")
        if not any("STOPS_AT_DEAD_END" in t for t in got.values()):
            errs.append("no dead-end trap among the options")
        if p["explanation"][-1] != f"So the frog lands on stone {truth} last.":
            errs.append("the explanation does not end with the answer")

    elif q == "tour":
        if p["entry"] != "hops" or p["options"]:
            errs.append("a trip is entered by tapping stones")
        if all(len(stuck_run(stones, a, b, s, f)) == len(stones) for f in (True, False)):
            errs.append("always taking the same preferred hop finds the trip, so no backing up is needed")
        if p["explanation"][-1] != f"So the frog's trip is {' → '.join(map(str, tour))}.":
            errs.append("the explanation does not end with the answer")
    else:
        errs.append(f"unknown question type {q}")
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

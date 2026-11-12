"""
Independent checker for friend_reach (Pass It On) problems.

Does not import the generator. It rebuilds the friendship graph from the SVG picture (each
person's data-name and circle, each line's data-a and data-b and its end points), checks it
against the scene and that no line runs through a person it does not join, then solves again
with breadth-first search distances. Wrong answers' tags are re-derived from its own versions
of each mistake.

Usage: python3 check_friend_reach.py L1-1000.js [...]   (files from pass-it-on/)
"""

import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from collections import deque

NS = "{http://www.w3.org/2000/svg}"
RULE = ["tells all of their friends", "tells all of their own friends", "Nobody passes it on a third time"]


def parse(svg):
    root = ET.fromstring(svg)
    pos, sender, ties, errs = {}, [], [], []
    for g in root.iter(NS + "g"):
        cls = (g.get("class") or "").split()
        if "person" not in cls:
            continue
        c, t = g.find(NS + "circle"), g.find(NS + "text")
        name = g.get("data-name")
        if t is None or t.text != name:
            errs.append(f"person {name} is labelled {t.text if t is not None else None!r}")
        pos[name] = (float(c.get("cx")), float(c.get("cy")), float(c.get("r")))
        if "sender" in cls:
            sender.append(name)
    for ln in root.iter(NS + "line"):
        if "tie" not in (ln.get("class") or "").split():
            continue
        a, b = ln.get("data-a"), ln.get("data-b")
        if a not in pos or b not in pos or a == b:
            errs.append(f"line {a}-{b} does not join two people")
            continue
        ends = {(round(float(ln.get("x1"))), round(float(ln.get("y1")))), (round(float(ln.get("x2"))), round(float(ln.get("y2"))))}
        if ends != {(round(pos[a][0]), round(pos[a][1])), (round(pos[b][0]), round(pos[b][1]))}:
            errs.append(f"line {a}-{b} is not drawn between {a} and {b}")
        ties.append(tuple(sorted((a, b))))
    return pos, sender, ties, errs


def seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    t = max(0, min(1, ((p[0] - ax) * (bx - ax) + (p[1] - ay) * (by - ay)) / ((bx - ax) ** 2 + (by - ay) ** 2)))
    return math.hypot(p[0] - ax - t * (bx - ax), p[1] - ay - t * (by - ay))


def dist_from(adj, s):
    d, q = {s: 0}, deque([s])
    while q:
        u = q.popleft()
        for v in sorted(adj[u]):
            if v not in d:
                d[v] = d[u] + 1
                q.append(v)
    return d


def hears(adj, s, steps=2):
    return sorted(v for v, k in dist_from(adj, s).items() if 0 < k <= steps)


def heard_tally(adj, s):
    """Every telling counted: step one, plus each friend telling everyone they know except the sender."""
    return sum(1 for f in adj[s]) + sum(len(adj[f]) - 1 for f in adj[s])


def plus(adj, a, b):
    out = {k: set(v) for k, v in adj.items()}
    out[a].add(b)
    out[b].add(a)
    return out


def check(p):
    pos, sender, ties, errs = parse(p["svg"])
    sc = p["scene"]
    names = list(pos)
    if sorted(names) != sorted(sc["people"]) or sorted(ties) != sorted(tuple(t) for t in sc["ties"]):
        errs.append("scene differs from the picture")
    if len(set(ties)) != len(ties):
        errs.append("a friendship is drawn twice")
    if (sender[0] if sender else "") != sc["sender"] or len(sender) > 1:
        errs.append("highlighted person differs from the scene")
    for a, b in ties:
        for x in names:
            if x not in (a, b) and seg_dist(pos[x][:2], pos[a][:2], pos[b][:2]) < pos[x][2] + 3:
                errs.append(f"line {a}-{b} runs through {x}")
    for i, x in enumerate(names):
        for y in names[i + 1:]:
            if math.hypot(pos[x][0] - pos[y][0], pos[x][1] - pos[y][1]) < pos[x][2] + pos[y][2] + 6:
                errs.append(f"{x} and {y} overlap")
    if not all(r in p["prompt"] for r in RULE):
        errs.append("prompt does not state the two-step rule")
    adj = {x: set() for x in names}
    for a, b in ties:
        adj[a].add(b)
        adj[b].add(a)
    if any(len(dist_from(adj, x)) != len(names) for x in names[:1]):
        errs.append("the group is not connected")
    n = len(names)
    q = p["question_type"]
    reach = {x: len(hears(adj, x)) for x in names}

    if q == "reach":
        m = re.fullmatch(r"(\w+) has news\. How many people hear it\? Do not count (\w+)\.", p["question"])
        if not m or m.group(1) != m.group(2) or m.group(1) != sc["sender"]:
            return errs + ["question does not name the highlighted person"]
        s = m.group(1)
        truth = reach[s]
        if p["answer_value"] != truth:
            errs.append(f"answer {p['answer_value']} != recomputed {truth}")
        mist = {"ONE_STEP_ONLY": len(adj[s]), "ONLY_SECOND_STEP": len(hears(adj, s)) - len(hears(adj, s, 1)),
                "COUNTS_SENDER": truth + 1, "PASSES_IT_ON_TOO_FAR": len(hears(adj, s, 3)),
                "COUNTS_REPEATS": heard_tally(adj, s)}
        if mist["COUNTS_REPEATS"] == truth:
            errs.append("counting every telling gives the right answer")
        if mist["PASSES_IT_ON_TOO_FAR"] == truth:
            errs.append("nobody is out of reach, so a third step changes nothing")
        want = {}
        for tag, v in mist.items():
            if v != truth:
                want.setdefault(v, set()).add(tag)
        if p["entry"] == "choice":
            o = p["options"]
            if o[p["answer_index"]] != truth or o.count(truth) != 1:
                errs.append("marked option is not the recomputed answer")
            if truth in (min(o), max(o)):
                errs.append("the right answer is the smallest or largest option (guessable)")
            got = {d["option"]: d["misconceptions"] for d in p["distractors"]}
            if sorted(got) != sorted(v for v in o if v != truth):
                errs.append("every wrong option needs tags")
            for v, t in got.items():
                if not t or set(t) != want.get(v, set()):
                    errs.append(f"option {v} tagged {t}, recomputed {sorted(want.get(v, []))}")
        elif p["entry"] == "number":
            if p["options"] or {k: sorted(v) for k, v in p["value_tags"].items()} != {str(v): sorted(t) for v, t in want.items()}:
                errs.append("typed-number tags differ from the recomputed ones")
        else:
            errs.append(f"unexpected entry {p['entry']}")
        if p["explanation"][-1] != f"So {truth} people hear {s}'s news.":
            errs.append("the explanation does not end with the answer")

    elif q == "who":
        if sc["sender"] or p["question"] != "Whose news reaches the most people?":
            errs.append("unexpected question or highlight")
        best = [x for x in names if reach[x] == max(reach.values())]
        if len(best) != 1:
            return errs + [f"{len(best)} people tie for the most"]
        ans = best[0]
        o = p["options"]
        if p["answer_value"] != ans or o[p["answer_index"]] != ans or o.count(ans) != 1:
            errs.append("marked option is not the recomputed answer")
        scores = {"MOST_FRIENDS_WINS": {x: len(adj[x]) for x in names},
                  "PASSES_IT_ON_TOO_FAR": {x: len(hears(adj, x, 3)) for x in names},
                  "COUNTS_REPEATS": {x: heard_tally(adj, x) for x in names},
                  "ONLY_SECOND_STEP": {x: reach[x] - len(adj[x]) for x in names}}
        want = {}
        for tag, sc_ in scores.items():
            top = {x for x in names if sc_[x] == max(sc_.values())}
            if ans in top:
                if tag in ("MOST_FRIENDS_WINS", "COUNTS_REPEATS"):
                    errs.append(f"{tag} picks the right answer")
                continue
            for x in top:
                want.setdefault(x, set()).add(tag)
        got = {d["option"]: d["misconceptions"] for d in p["distractors"]}
        if sorted(got) != sorted(x for x in o if x != ans) or len(o) < 3:
            errs.append("every wrong option needs tags, and there must be at least three options")
        for x, t in got.items():
            if not t or set(t) != want.get(x, set()):
                errs.append(f"option {x} tagged {t}, recomputed {sorted(want.get(x, []))}")
        if not any("MOST_FRIENDS_WINS" in t for t in got.values()):
            errs.append("the most-friends trap is not an option")
        if p["explanation"][-1] != f"So {ans}'s news reaches the most people: {reach[ans]}.":
            errs.append("the explanation does not end with the answer")

    elif q == "befriend":
        s = sc["sender"]
        if p["question"] != f"{s} wants news to reach everyone. Which one new friend should {s} make?":
            return errs + ["question does not name the highlighted person"]
        missed = set(names) - set(hears(adj, s)) - {s}
        if len(missed) < 2:
            errs.append("fewer than two people are missed")
        cands = [x for x in names if x != s and x not in adj[s]]
        works = [x for x in cands if len(hears(plus(adj, s, x), s)) == n - 1]
        if len(works) != 1:
            return errs + [f"{len(works)} new friends would work"]
        ans = works[0]
        o = p["options"]
        if p["answer_value"] != ans or o[p["answer_index"]] != ans or o.count(ans) != 1:
            errs.append("marked option is not the recomputed answer")
        if ans in missed:
            errs.append("the answer is someone who is missed")
        most = max(len(adj[x]) for x in cands)
        if len(adj[ans]) == most:
            errs.append("befriending the most-friended person is right")
        got = {d["option"]: d["misconceptions"] for d in p["distractors"]}
        if sorted(got) != sorted(x for x in o if x != ans) or len(o) < 3:
            errs.append("every wrong option needs tags, and there must be at least three options")
        for x, t in got.items():
            w = set()
            if x not in cands:
                errs.append(f"{x} is already a friend")
                continue
            if len(adj[x]) == most:
                w.add("MOST_FRIENDS_WINS")
            if x in missed:
                w.add("JOINS_A_MISSED_PERSON")
            if len(hears(plus(adj, s, x), s, 3)) == n - 1:
                w.add("PASSES_IT_ON_TOO_FAR")
            if not t or set(t) != w:
                errs.append(f"option {x} tagged {t}, recomputed {sorted(w)}")
        if p["explanation"][-1] != f"So {s} should make friends with {ans}.":
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

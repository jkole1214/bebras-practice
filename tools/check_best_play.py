"""
Independent checker for best_play (Acorn Game) problems.

Does not import the generator. It rebuilds the game from the SVG picture:
  trail: each fork (data-id, data-turn, colour), each basket (data-id, data-acorns, its number),
         each trail line (data-a, data-b, drawn between the two ends), and the path letters;
  pile:  the acorns drawn and the rule sign (data-moves and data-last, and the words on it);
  strip: the numbered pile sizes and the rule sign.
Trails are solved bottom-up level by level (the generator recurses from the top); piles are
solved top-down with a memo (the generator fills a table from 0 up). Wrong answers' tags are
re-derived from the checker's own version of each mistake.

Usage: python3 check_best_play.py L1-1000.js [...]   (files from acorn-game/)
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from functools import lru_cache

NS = "{http://www.w3.org/2000/svg}"
FILL = {"you": "#f2c14e", "raccoon": "#9aa5b1"}


def say_moves(ms):
    ms = [str(m) for m in ms]
    return ms[0] if len(ms) == 1 else ", ".join(ms[:-1]) + " or " + ms[-1]


def classes(el):
    return (el.get("class") or "").split()


# --------------------------------------------------------------------------
# Trails
# --------------------------------------------------------------------------

def parse_trail(svg):
    root = ET.fromstring(svg)
    nodes, xy, kids, errs, letters = {}, {}, {}, [], {}
    for g in root.iter(NS + "g"):
        c = classes(g)
        if "fork" in c:
            circ = g.find(NS + "circle")
            nid, turn = g.get("data-id"), g.get("data-turn")
            if circ.get("fill") != FILL.get(turn):
                errs.append(f"fork {nid} is coloured {circ.get('fill')} for {turn}")
            t = g.find(NS + "text")
            lab = g.get("data-label")
            if (t.text if t is not None else None) != lab:
                errs.append(f"fork {nid} label differs from its text")
            nodes[nid] = {"turn": turn, "label": lab}
            xy[nid] = (float(circ.get("cx")), float(circ.get("cy")))
        elif "basket" in c:
            nid = g.get("data-id")
            n = int(g.get("data-acorns"))
            if g.find(NS + "text").text != str(n):
                errs.append(f"basket {nid} shows a different number")
            r = g.find(NS + "rect")
            nodes[nid] = {"turn": "end", "acorns": n}
            xy[nid] = (float(r.get("x")) + float(r.get("width")) / 2, float(r.get("y")) + 4)
        elif "path" in c:
            letters[g.get("data-for")] = g.find(NS + "text").text
    for ln in root.iter(NS + "line"):
        if "trail" not in classes(ln):
            continue
        a, b = ln.get("data-a"), ln.get("data-b")
        if a not in nodes or b not in nodes:
            errs.append(f"trail {a}-{b} does not join two places")
            continue
        ends = {(round(float(ln.get("x1"))), round(float(ln.get("y1")))), (round(float(ln.get("x2"))), round(float(ln.get("y2"))))}
        if ends != {tuple(map(round, xy[a])), tuple(map(round, xy[b]))}:
            errs.append(f"trail {a}-{b} is not drawn between its ends")
        if not xy[b][1] > xy[a][1]:
            errs.append(f"trail {a}-{b} does not go down the page")
        kids.setdefault(a, []).append(b)
    for k in kids:
        kids[k].sort(key=lambda n: xy[n][0])
    return nodes, kids, xy, letters, errs


def solve_bottom_up(nodes, kids, pick):
    """pick[turn] chooses among the children's values; computed from the deepest level up."""
    depth = {"s": 0}
    queue = ["s"]
    for n in queue:
        for k in kids.get(n, []):
            depth[k] = depth[n] + 1
            queue.append(k)
    val = {}
    for n in sorted(depth, key=lambda n: -depth[n]):
        if nodes[n]["turn"] == "end":
            val[n] = nodes[n]["acorns"]
        else:
            val[n] = pick[nodes[n]["turn"]]([val[k] for k in kids[n]])
    return val, depth


def under(nodes, kids, n):
    if nodes[n]["turn"] == "end":
        return [nodes[n]["acorns"]]
    out = []
    for k in kids[n]:
        out += under(nodes, kids, k)
    return out


def check_trail(p):
    nodes, kids, xy, letters, errs = parse_trail(p["svg"])
    tree = p["scene"]["tree"]
    if set(tree) != set(nodes):
        return errs + ["scene differs from the picture"]
    for n, t in tree.items():
        if t["turn"] != nodes[n]["turn"] or sorted(t["kids"]) != sorted(kids.get(n, [])) or t.get("acorns") != nodes[n].get("acorns"):
            errs.append(f"node {n} differs from the picture")
    if "s" not in nodes or any("s" in v for v in kids.values()):
        return errs + ["no start fork at the top"]
    PICK = {"you": max, "raccoon": min}
    val, depth = solve_bottom_up(nodes, kids, PICK)
    for n, d in depth.items():
        want = "end" if not kids.get(n) else ("you" if d % 2 == 0 else "raccoon")
        if nodes[n]["turn"] != want:
            errs.append(f"{n}: turns do not alternate, starting with you")
    if len(depth) != len(nodes):
        errs.append("some places are not on the trail")
    if not all(w in p["prompt"] for w in ["yellow fork, you choose", "grey fork, the raccoon chooses",
                                          "leaves you the fewest acorns", "keep the basket"]):
        errs.append("prompt does not state the rules")
    first = kids["s"]
    want_letters = {k: "ABCD"[i] for i, k in enumerate(first)}
    if letters != want_letters:
        errs.append("path letters are not A, B, C from the left")
    allv = under(nodes, kids, "s")
    q = p["question_type"]

    if q == "path":
        if max(depth.values()) != 2:
            errs.append("a path trail should be two forks deep")
        names = [want_letters[k] for k in first]
        score = {want_letters[k]: val[k] for k in first}
        best = [x for x in names if score[x] == max(score.values())]
        if len(best) != 1:
            return errs + ["more than one best path"]
        ans = best[0]
        o = p["options"]
        if o != names or p["answer_value"] != ans or o[p["answer_index"]] != ans:
            errs.append("marked option is not the recomputed answer")
        big = [want_letters[k] for k in first if max(allv) in under(nodes, kids, k)]
        tot = {want_letters[k]: sum(under(nodes, kids, k)) for k in first}
        rnd = [x for x in names if tot[x] == max(tot.values())]
        want = {}
        if allv.count(max(allv)) == 1 and big[0] != ans:
            want.setdefault(big[0], set()).add("BIGGEST_BASKET")
        if len(rnd) == 1 and rnd[0] != ans:
            want.setdefault(rnd[0], set()).add("RACCOON_PICKS_RANDOMLY")
        if big[0] == ans or rnd[0] == ans:
            errs.append("a habit picks the right path")
        got = {d["option"]: d["misconceptions"] for d in p["distractors"]}
        if sorted(got) != sorted(x for x in o if x != ans):
            errs.append("every wrong option needs tags")
        for x, t in got.items():
            if not t or set(t) != want.get(x, set()):
                errs.append(f"path {x} tagged {t}, recomputed {sorted(want.get(x, []))}")
        if p["explanation"][-1] != f"So take path {ans}: you are sure to get {val['s']} acorns.":
            errs.append("the explanation does not end with the answer")

    elif q == "sure":
        if max(depth.values()) != 3:
            errs.append("a sure trail should be three forks deep")
        truth = val["s"]
        if p["answer_value"] != truth or p["entry"] != "number" or p["options"]:
            errs.append(f"answer {p['answer_value']} != recomputed {truth}")
        lasts = sorted((n for n in nodes if nodes[n]["turn"] == "you" and depth[n] == 2), key=lambda n: xy[n][0])
        if [nodes[n]["label"] for n in lasts] != [str(i + 1) for i in range(len(lasts))]:
            errs.append("your last forks are not numbered 1, 2, 3 ... from the left")
        bigside = [k for k in first if max(allv) in under(nodes, kids, k)]
        mist = {"BIGGEST_BASKET": max(allv),
                "ONE_STEP_AHEAD": val[bigside[0]],
                "RACCOON_PICKS_ALL": max(min(under(nodes, kids, k)) for k in first),
                "FLIPS_TURNS": solve_bottom_up(nodes, kids, {"you": min, "raccoon": max})[0]["s"]}
        if allv.count(max(allv)) != 1:
            errs.append("two baskets tie for the biggest")
        if mist["ONE_STEP_AHEAD"] == truth or mist["BIGGEST_BASKET"] == truth:
            errs.append("heading for the biggest basket gives the right answer")
        want = {}
        for tag, v in mist.items():
            if v != truth:
                want.setdefault(str(v), set()).add(tag)
        if {k: set(v) for k, v in p["value_tags"].items()} != want:
            errs.append(f"typed-number tags {p['value_tags']} differ from recomputed {want}")
        lines = " ".join(p["explanation"])
        for n in lasts:
            if f"fork {nodes[n]['label']}: {val[n]}" not in lines:
                errs.append(f"the explanation gives fork {nodes[n]['label']} the wrong value")
        if p["explanation"][-1] != f"So you can be sure of {truth} acorns.":
            errs.append("the explanation does not end with the answer")
    else:
        errs.append(f"unknown trail question {q}")
    return errs


# --------------------------------------------------------------------------
# Piles
# --------------------------------------------------------------------------

def parse_rule(root, errs):
    rule = [g for g in root.iter(NS + "g") if "rule" in classes(g)]
    if len(rule) != 1:
        errs.append("there should be exactly one rule sign")
        return None, None
    g = rule[0]
    moves = [int(x) for x in g.get("data-moves").split(",")]
    last = g.get("data-last")
    words = [t.text for t in g.iter(NS + "text")]
    if words != [f"Take {say_moves(moves)} each turn", f"Last acorn {last}"]:
        errs.append(f"the sign reads {words}")
    if last not in ("wins", "loses") or moves != sorted(set(moves)) or moves[0] != 1:
        errs.append("the rule is not a usable game")
    return moves, last


def mover_loses(n, moves, last):
    """True if the player about to move from a pile of n loses with best play (top-down)."""
    @lru_cache(None)
    def lost(p):
        if p == 0:
            return last == "wins"
        return not any(lost(p - m) for m in moves if m <= p)
    return lost(n)


def habits(n, moves, last):
    k = moves[-1]
    full = moves == list(range(1, k + 1))
    h = {"GRABS_MOST": k}
    if full and last == "wins":
        h["OFF_BY_ONE_PATTERN"] = next((m for m in moves if (n - m) % k == 0), None)
        h["MISERE_MIXUP"] = next((m for m in moves if (n - m) % (k + 1) == 1), None)
    elif full:
        h["OFF_BY_ONE_PATTERN"] = next((m for m in moves if (n - m) % k == 1), None)
        h["MISERE_MIXUP"] = next((m for m in moves if (n - m) % (k + 1) == 0), None)
    else:
        h["PLAIN_PATTERN"] = next((m for m in moves if (n - m) % (k + 1) == 0), None)
    return {t: m for t, m in h.items() if m is not None and m <= n}


def check_pile(p):
    errs = []
    root = ET.fromstring(p["svg"])
    moves, last = parse_rule(root, errs)
    if moves is None:
        return errs
    sc = p["scene"]
    if sc["moves"] != moves or sc["last"] != last:
        errs.append("scene rule differs from the sign")
    want_prompt = (f"must take {say_moves(moves)} acorns. Whoever takes the last acorn {last}. "
                   f"You go first, and the raccoon always plays its best.")
    if want_prompt not in p["prompt"]:
        errs.append("prompt does not match the sign")
    q = p["question_type"]

    if q == "first":
        n = sum(1 for g in root.iter(NS + "g") if "acorn" in classes(g))
        if n != sc["pile"]:
            errs.append(f"picture shows {n} acorns, scene says {sc['pile']}")
        m = re.fullmatch(r"The pile has (\d+) acorns\. How many should you take on your first turn, to be sure to win\?", p["question"])
        if not m or int(m.group(1)) != n:
            return errs + ["question does not match the picture"]
        if mover_loses(n, tuple(moves), last):
            return errs + ["you cannot win from this pile"]
        good = [x for x in moves if x <= n and mover_loses(n - x, tuple(moves), last)]
        if len(good) != 1:
            return errs + [f"{len(good)} first moves win"]
        truth = good[0]
        if p["answer_value"] != truth or p["entry"] != "number" or p["options"]:
            errs.append(f"answer {p['answer_value']} != recomputed {truth}")
        h = habits(n, moves, last)
        if truth in h.values():
            errs.append("a habit gives the right move")
        want = {}
        for tag, v in h.items():
            want.setdefault(str(v), set()).add(tag)
        if {k: set(v) for k, v in p["value_tags"].items()} != want:
            errs.append(f"typed-number tags {p['value_tags']} differ from recomputed {want}")
        if p["level"] == 5 and not ({"MISERE_MIXUP", "PLAIN_PATTERN"} & set(t for v in want.values() for t in v)):
            errs.append("level 5 needs its twist's trap")
        losers = [x for x in range(1, n + 1) if mover_loses(x, tuple(moves), last)]
        if not any(l.endswith(f": {', '.join(map(str, losers[:-1]))}{' and ' if len(losers) > 1 else ''}{losers[-1]}.")
                   for l in p["explanation"] if l.startswith("Lose-piles up to")):
            errs.append("the explanation lists the wrong lose-piles")
        if p["explanation"][-1] != f"So take {truth} acorn{'' if truth == 1 else 's'} first.":
            errs.append("the explanation does not end with the answer")

    elif q == "traps":
        sizes = sorted(int(g.get("data-n")) for g in root.iter(NS + "g") if "size" in classes(g))
        upto = sc["upto"]
        if sizes != list(range(1, upto + 1)) or last != "wins":
            errs.append("the pile sizes shown are not 1 to the limit")
        if not p["question"].endswith(f"Which piles from 1 to {upto} are lose-piles?"):
            errs.append("question does not match the picture")
        truth = [x for x in range(1, upto + 1) if mover_loses(x, tuple(moves), last)]
        o = p["options"]
        if p["answer_value"] != truth or o[p["answer_index"]] != truth or o.count(truth) != 1:
            errs.append("marked option is not the recomputed answer")
        k = moves[-1]
        mist = {"OFF_BY_ONE_PATTERN": [x for x in range(k, upto + 1, k)],
                "ONLY_FIRST_TRAP": truth[:1],
                "MISERE_MIXUP": [x for x in range(1, upto + 1, k + 1)],
                "EVEN_PILES_LOSE": [x for x in range(2, upto + 1, 2)]}
        got = {tuple(d["option"]): d["misconceptions"] for d in p["distractors"]}
        if sorted(got) != sorted(tuple(x) for x in o if x != truth) or len(o) != 4:
            errs.append("every wrong option needs tags, and there must be four options")
        for x, t in got.items():
            w = {tag for tag, v in mist.items() if tuple(v) == x}
            if not t or set(t) != w:
                errs.append(f"option {list(x)} tagged {t}, recomputed {sorted(w)}")
        lens = sorted(len(x) for x in o)
        if not lens[0] < len(truth) < lens[-1]:
            errs.append("the right list is the shortest or longest (guessable)")
        if p["explanation"][-1] != f"So the lose-piles are {', '.join(map(str, truth[:-1]))}{' and ' if len(truth) > 1 else ''}{truth[-1]}.":
            errs.append("the explanation does not end with the answer")
    else:
        errs.append(f"unknown pile question {q}")
    return errs


def check(p):
    if p["family"] != "best_play":
        return ["wrong family"]
    if p["question_type"] in ("path", "sure"):
        return check_trail(p)
    return check_pile(p)


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

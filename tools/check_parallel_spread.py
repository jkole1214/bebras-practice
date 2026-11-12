"""
Independent checker for parallel_spread (Paint Pipes) problems.

Does not import the generator. It rebuilds the network from the SVG picture
(tanks, pipes, the drawn colour of each starting tank and the legend), checks it
against the scene and the prompt, reads the question from its visible text, and
solves it again with a set-based simulation: each minute it works out which tanks
orange and blue can reach, and every tank that would then hold both becomes mud.

Usage: python3 check_parallel_spread.py L2-1000.js [...]   (files from paint-pipes/)
"""

import json
import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://www.w3.org/2000/svg}"
DRAWN = {"#e8862a": "orange", "#2f6fb5": "blue", "#f4f1ea": ""}


def parse(svg):
    root = ET.fromstring(svg)
    tanks, pipes, starts, errs = {}, set(), {}, []
    for g in root.iter(NS + "g"):
        cls = g.get("class")
        if cls == "tank":
            t = g.get("data-id")
            circle = g.find(NS + "circle")
            label = g.find(NS + "text").text
            if label != t:
                errs.append(f"tank {t} is labelled {label}")
            if (float(circle.get("cx")), float(circle.get("cy"))) != (float(g.get("data-x")), float(g.get("data-y"))):
                errs.append(f"tank {t} drawn away from its data position")
            drawn = DRAWN.get(circle.get("fill"), "?")
            if drawn != g.get("data-start"):
                errs.append(f"tank {t} drawn {drawn or 'empty'} but data says {g.get('data-start') or 'empty'}")
            tanks[t] = (float(g.get("data-x")), float(g.get("data-y")))
            if drawn:
                starts[t] = drawn
        elif cls == "pipe":
            pipes.add(frozenset((g.get("data-a"), g.get("data-b"))))
    legend = " ".join(t.text for t in root.iter(NS + "text") if t.text and "poured into" in t.text)
    for t, col in starts.items():
        if f"{col} poured into {t}" not in legend:
            errs.append(f"legend does not say {col} starts in {t}")
    return tanks, pipes, starts, errs


def spread(nbrs, starts, minutes=None):
    orange = {t for t, c in starts.items() if c == "orange"}
    blue = {t for t, c in starts.items() if c == "blue"}
    mud = set()
    n = 0
    while minutes is None or n < minutes:
        to_o = {v for u in orange for v in nbrs[u]} - mud
        to_b = {v for u in blue for v in nbrs[u]} - mud
        new_mud = (to_o & to_b) | (to_o & blue) | (to_b & orange)
        new_orange = (orange | to_o) - new_mud
        new_blue = (blue | to_b) - new_mud
        if (new_orange, new_blue) == (orange, blue) and not new_mud:
            break
        orange, blue, mud = new_orange, new_blue, mud | new_mud
        n += 1
        if n > 1000:
            raise RuntimeError("no steady state")
    return {"orange": orange, "blue": blue, "mud": mud}


def check(p):
    tanks, pipes, starts, errs = parse(p["svg"])
    sc = p["scene"]
    if {t: tuple(map(float, xy)) for t, xy in sc["tanks"].items()} != tanks:
        errs.append("scene tanks differ from the picture")
    if {frozenset(x) for x in sc["pipes"]} != pipes:
        errs.append("scene pipes differ from the picture")
    if sc["sources"] != starts:
        errs.append("scene starting tanks differ from the picture")
    for t, col in starts.items():
        if not re.search(rf"{col} paint (is poured )?into tank {t}\b", p["prompt"], re.I):
            errs.append(f"prompt does not say {col} starts in {t}")
    nbrs = {t: set() for t in tanks}
    for e in pipes:
        if len(e) != 2 or not e <= set(tanks):
            return errs + [f"pipe {sorted(e)} does not join two drawn tanks"]
        a, b = tuple(e)
        nbrs[a].add(b)
        nbrs[b].add(a)

    q = p["question"]
    m = re.match(r"After (\d+) minutes, how many tanks have orange paint in them\?$", q)
    if m:
        if list(starts.values()) != ["orange"]:
            errs.append("an 'after' question needs exactly one orange tank")
        truth = len(spread(nbrs, starts, int(m.group(1)))["orange"])
    else:
        m = re.match(r"When nothing changes any more, how many tanks (are orange|are blue|have turned to mud)\?$", q)
        if not m:
            return errs + [f"unknown question: {q}"]
        if sorted(starts.values()) != ["blue", "orange"]:
            errs.append("a 'final' question needs one orange and one blue tank")
        truth = len(spread(nbrs, starts)[m.group(1).split()[-1]])

    if p["answer_value"] != truth:
        errs.append(f"answer {p['answer_value']} != recomputed {truth}")
    if p["entry"] == "choice":
        o = p["options"]
        if not 0 <= p["answer_index"] < len(o) or o[p["answer_index"]] != truth:
            errs.append("marked option is not the recomputed answer")
        if o.count(truth) != 1:
            errs.append("the right answer appears more or less than once")
        if truth in (min(o), max(o)):
            errs.append("the right answer is the smallest or largest option (guessable)")
        d = {x["option"]: x["misconceptions"] for x in p["distractors"]}
        if sorted(d) != sorted(v for v in o if v != truth) or not all(d.values()):
            errs.append("every wrong option needs misconception tags")
    elif p["entry"] == "number":
        vt = p["value_tags"]
        if str(truth) in vt:
            errs.append("a tagged wrong value equals the answer")
        if not vt or not all(vt.values()):
            errs.append("typed answer needs tagged wrong values")
    else:
        errs.append(f"unexpected entry {p['entry']}")
    if f"So {truth} tanks" not in p["explanation"][-1] and f": {truth} tanks" not in p["explanation"][-1]:
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

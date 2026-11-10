"""
Problem family: logic_gates (signals through 'both', 'only one' and 'at least one' boxes).

Concept targets: LOGIC_GATES, BOOLEAN_AND.
Source task: Lights On (2022-23 practice; Benjamin C, Cadet B, Junior A).

Scenario (original wording): beavers stand on buttons; each button sends a
signal down a wire. Wires meet in boxes: a triangle passes a signal on only
if BOTH wires bring one, a square only if exactly ONE does, a circle if AT
LEAST ONE does. The last box feeds a light bulb.

Scene model: a full binary tree. A node is {"op": "AND"|"XOR"|"OR", "kids": [a, b]}
or {"in": k} for button k (numbered from the top, starting at 1). The picture
(SVG) is drawn from the tree, and the page grades press-the-buttons answers
by evaluating the same tree.

Question types:
  choose   which of four sets of pressed buttons turns the light on?
  press    press buttons so the light turns on (any working set is right)
  fewest   turn the light on with as few buttons as possible
  count    how many different sets of pressed buttons turn the light on? (typed)
"""

import itertools
import json
import random
from dataclasses import dataclass, field, asdict

LADDER = [
    {"level": 1, "question": "choose", "depth": 2, "ops": ["AND", "XOR"], "note": "Four buttons: which set of beavers lights the bulb?"},
    {"level": 2, "question": "press", "depth": 2, "ops": ["AND", "XOR"], "note": "Four buttons: press buttons to light the bulb"},
    {"level": 3, "question": "press", "depth": 3, "ops": ["AND", "XOR"], "note": "Eight buttons, like the Bebras task"},
    {"level": 4, "question": "fewest", "depth": 3, "ops": ["AND", "XOR", "OR"], "note": "Eight buttons, three kinds of box, fewest beavers"},
    {"level": 5, "question": "count", "depth": 2, "ops": ["AND", "XOR", "OR"], "note": "Count every set of buttons that lights the bulb (type the number)"},
]

MISCONCEPTIONS = {
    "XOR_AS_OR": {"concept": "LOGIC_GATES",
        "description": "Reads an 'only one' box as 'at least one' and turns on both of its wires.",
        "remediation": "Ask what an 'only one' box does when both of its wires bring a signal."},
    "BOTH_AS_EITHER": {"concept": "LOGIC_GATES",
        "description": "Reads a 'both' box as if one wire were enough.",
        "remediation": "Ask: does this box need one wire or both wires to send a signal on?"},
    "EXTRA_BUTTONS": {"concept": "LOGIC_GATES",
        "description": "Finds a set that works but uses more beavers than needed.",
        "remediation": "Work backward from the bulb and, at each box, choose the cheapest way to make it send a signal."},
    "ONE_ANSWER_ONLY": {"concept": "LOGIC_GATES",
        "description": "Finds one working set and stops, as if there were only one answer to count.",
        "remediation": "Ask: is there another set that also works? Try listing them in order."},
}

GATE_NAME = {"AND": "triangle (both)", "XOR": "square (only one)", "OR": "circle (at least one)"}
PROMPT = ("Each button sends a signal down its wire when a beaver stands on it. "
          "A triangle sends a signal on only if BOTH of its wires bring one. "
          "A square sends a signal on only if exactly ONE of its wires brings one.")
PROMPT_OR = " A circle sends a signal on if AT LEAST ONE of its wires brings one."


# --------------------------------------------------------------------------
# Solvers
# --------------------------------------------------------------------------

def evaluate(node, on, view=None):
    """Signal out of node with buttons `on` pressed. view: None, 'XOR_AS_OR' or 'BOTH_AS_EITHER'."""
    if "in" in node:
        return node["in"] in on
    a, b = (evaluate(k, on, view) for k in node["kids"])
    op = node["op"]
    if view == "XOR_AS_OR" and op == "XOR":
        op = "OR"
    if view == "BOTH_AS_EITHER" and op == "AND":
        op = "OR"
    return {"AND": a and b, "XOR": a != b, "OR": a or b}[op]


def all_sets(n):
    for r in range(n + 1):
        for c in itertools.combinations(range(1, n + 1), r):
            yield set(c)


def solutions(tree, n, view=None):
    return [s for s in all_sets(n) if evaluate(tree, s, view)]


def random_tree(rng, depth, ops):
    counter = itertools.count(1)

    def build(d):
        if d == 0:
            return {"in": next(counter)}
        return {"op": rng.choice(ops), "kids": [build(d - 1), build(d - 1)]}
    return build(depth)


def ops_used(node):
    return set() if "in" in node else {node["op"]} | ops_used(node["kids"][0]) | ops_used(node["kids"][1])


def leaves(node):
    return [node["in"]] if "in" in node else leaves(node["kids"][0]) + leaves(node["kids"][1])


def explain_backward(root, on):
    """Lines describing, from the bulb back, what each box receives with the answer set."""
    lines = []

    def name(nd):
        if nd is root:
            return "The last box"
        ls = leaves(nd)
        return f"The box for buttons {ls[0]}-{ls[-1]}"

    def walk(nd):
        if "in" in nd:
            return
        a, b = (evaluate(k, on) for k in nd["kids"])
        out = evaluate(nd, on)
        lines.append(f"• {name(nd)} is a {GATE_NAME[nd['op']]}: its wires bring "
                     f"{'a signal' if a else 'nothing'} and {'a signal' if b else 'nothing'}, "
                     f"so it {'sends a signal' if out else 'sends nothing'}.")
        for k in nd["kids"]:
            walk(k)
    walk(root)
    return lines


# --------------------------------------------------------------------------
# Picture
# --------------------------------------------------------------------------

def render_svg(tree, depth):
    n = 2 ** depth
    W, top, gap = 120 + depth * 110 + 80, 30, 56 if depth == 2 else 44
    H = top * 2 + gap * (n - 1)
    x_of = lambda lvl: 70 + lvl * 110          # lvl 0 = buttons
    parts, pos = [], {}

    def place(nd, lvl_from_top):
        if "in" in nd:
            k = nd["in"]
            pos[id(nd)] = (x_of(0), top + gap * (k - 1))
            return pos[id(nd)]
        ya = [place(k, lvl_from_top + 1)[1] for k in nd["kids"]]
        p = (x_of(depth - lvl_from_top), sum(ya) / 2)
        pos[id(nd)] = p
        return p
    place(tree, 0)

    def wires(nd):
        if "in" in nd:
            return
        x, y = pos[id(nd)]
        for k in nd["kids"]:
            kx, ky = pos[id(k)]
            mx = (kx + x) / 2
            parts.append(f'<path class="wire" d="M{kx + 14:.0f} {ky:.0f} H{mx:.0f} V{y:.0f} H{x - 14:.0f}"/>')
            wires(k)
    wires(tree)
    bx, by = pos[id(tree)]
    parts.append(f'<path class="wire" d="M{bx + 14:.0f} {by:.0f} H{W - 50:.0f}"/>')

    def gates(nd):
        if "in" in nd:
            k = nd["in"]
            x, y = pos[id(nd)]
            parts.append(f'<g class="btn" data-btn="{k}" tabindex="0" role="button" aria-label="button {k}">'
                         f'<circle cx="{x:.0f}" cy="{y:.0f}" r="15" class="pad"/>'
                         f'<text x="{x:.0f}" y="{y + 5:.0f}" text-anchor="middle">{k}</text></g>')
            return
        x, y = pos[id(nd)]
        op = nd["op"]
        if op == "AND":
            parts.append(f'<polygon class="gate g-and" data-op="AND" points="{x - 13:.0f},{y - 14:.0f} {x + 14:.0f},{y:.0f} {x - 13:.0f},{y + 14:.0f}"/>')
        elif op == "XOR":
            parts.append(f'<rect class="gate g-xor" data-op="XOR" x="{x - 12:.0f}" y="{y - 12:.0f}" width="24" height="24"/>')
        else:
            parts.append(f'<circle class="gate g-or" data-op="OR" cx="{x:.0f}" cy="{y:.0f}" r="13"/>')
        for k in nd["kids"]:
            gates(k)
    gates(tree)
    lx = W - 38
    parts.append(f'<g class="bulb"><circle cx="{lx}" cy="{by - 4:.0f}" r="14"/><rect x="{lx - 7}" y="{by + 9:.0f}" width="14" height="9" rx="2"/></g>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H:.0f}" width="{W}" height="{H:.0f}" '
            f'class="circuit" data-depth="{depth}" role="img" aria-label="circuit of {n} buttons">' + "".join(parts) + "</svg>")


# --------------------------------------------------------------------------
# Problem
# --------------------------------------------------------------------------

@dataclass
class Problem:
    family: str
    level: int
    question_type: str
    seed: int
    scene: dict
    svg: str
    prompt: str
    question: str
    options: list
    answer_index: int
    answer_value: object
    entry: str
    distractors: list
    value_tags: dict
    concepts: list
    explanation: list
    hints: list
    knobs: dict = field(default_factory=dict)


def label(s):
    return "nobody" if not s else ", ".join(str(x) for x in sorted(s))


def backward_hints(has_or):
    h = ["Start at the bulb. What does the last box need from its two wires?",
         "A triangle needs both wires on. A square needs one wire on and the other off."]
    if has_or:
        h[1] += " A circle needs at least one."
    h.append("Keep going back, box by box, until you reach the buttons.")
    return h


def make(rng, cfg, seed):
    n = 2 ** cfg["depth"]
    for _ in range(4000):
        tree = random_tree(rng, cfg["depth"], cfg["ops"])
        used = ops_used(tree)
        if "XOR" not in used or ("AND" not in used and cfg["question"] != "count"):
            continue
        if cfg["level"] >= 4 and "OR" not in used:
            continue
        good = solutions(tree, n)
        if not good or len(good) == 2 ** n:
            continue
        has_or = "OR" in used
        prompt = PROMPT + (PROMPT_OR if has_or else "")
        qt = cfg["question"]
        common = dict(family="logic_gates", level=cfg["level"], question_type=qt, seed=seed,
                      scene={"tree": tree, "buttons": n}, svg=render_svg(tree, cfg["depth"]), prompt=prompt,
                      concepts=["LOGIC_GATES", "BOOLEAN_AND"], knobs={"depth": cfg["depth"], "ops": sorted(used)})
        if qt == "choose":
            right = [s for s in good if 1 <= len(s) < n]
            wrongs = {}
            for view in ("XOR_AS_OR", "BOTH_AS_EITHER"):
                for s in solutions(tree, n, view):
                    if s not in good and s:
                        wrongs.setdefault(frozenset(s), set()).add(view)
            # need both misreadings represented
            by_tag = {t: [s for s, ts in wrongs.items() if t in ts] for t in ("XOR_AS_OR", "BOTH_AS_EITHER")}
            if not right or not all(by_tag.values()):
                continue
            ans = rng.choice(right)
            picks = [rng.choice(by_tag["XOR_AS_OR"])]
            rest = [s for s in by_tag["BOTH_AS_EITHER"] if s not in picks]
            if not rest:
                continue
            picks.append(rng.choice(rest))
            more = [s for s in wrongs if s not in picks]
            if not more:
                continue
            picks.append(rng.choice(more))
            sizes = [len(ans)] + [len(s) for s in picks]
            if sizes.count(max(sizes)) == 1 and sizes[0] == max(sizes):
                continue          # shortcut: the most beavers must not be the answer
            opts = [sorted(ans)] + [sorted(s) for s in picks]
            order = list(range(4))
            rng.shuffle(order)
            opts = [opts[i] for i in order]
            return Problem(**common, question="Which beavers should stand on buttons to turn the light on? (Only those buttons are pressed.)",
                           options=opts, answer_index=order.index(0), answer_value=sorted(ans), entry="choice",
                           distractors=[{"option": sorted(s), "misconceptions": sorted(wrongs[s])} for s in picks],
                           value_tags={},
                           explanation=[f"With buttons {label(ans)} pressed:"] + explain_backward(tree, ans)
                                       + ["Each other choice works only if you misread a box."],
                           hints=backward_hints(has_or))
        if qt in ("press", "fewest"):
            if len(good) > 2 ** n // 3:
                continue          # too easy to hit by pressing at random
            m = min(len(s) for s in good)
            mins = [s for s in good if len(s) == m]
            ex = rng.choice(mins)
            q = ("Press buttons (tap them) so the light turns on. Then check." if qt == "press" else
                 "Turn the light on using as FEW beavers as possible. Tap buttons, then check.")
            if qt == "fewest" and (m < 2 or len(mins) > 6 or m == len([s for s in good if len(s) == m + 1]) == 0):
                continue
            expl = [f"One way: press {label(ex)}."] + explain_backward(tree, ex)
            if qt == "fewest":
                expl.append(f"No set of fewer than {m} buttons works.")
            return Problem(**common, question=q, options=[], answer_index=-1,
                           answer_value=m if qt == "fewest" else sorted(ex), entry="press",
                           distractors=[], value_tags={}, explanation=expl, hints=backward_hints(has_or))
        if qt == "count":
            truth = len(good)
            vals = {}
            for view in ("XOR_AS_OR", "BOTH_AS_EITHER"):
                v = len(solutions(tree, n, view))
                if v != truth:
                    vals.setdefault(v, set()).add(view)
            if truth != 1:
                vals.setdefault(1, set()).add("ONE_ANSWER_ONLY")
            if truth < 2 or truth > 12 or "XOR_AS_OR" not in {t for ts in vals.values() for t in ts}:
                continue
            listing = "; ".join(label(s) for s in good)
            return Problem(**common, question=f"There are {2 ** n} different ways to press some of the {n} buttons (including pressing none). "
                                              "How many of them turn the light on?",
                           options=[], answer_index=-1, answer_value=truth, entry="number", distractors=[],
                           value_tags={str(v): sorted(t) for v, t in vals.items()},
                           explanation=["Work out, for each half of the circuit, which button pairs make it send a signal, then combine them at the last box.",
                                        f"The {truth} sets that work: {listing}."],
                           hints=["Look at each box that the buttons feed. Which of the 4 ways to press its two buttons make it send a signal?",
                                  "Now use the last box's rule to combine the two halves.",
                                  "Count every combination; do not stop at the first one."])
    raise RuntimeError(f"generation failed at level {cfg['level']}")


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    return make(random.Random(seed), cfg, seed)


if __name__ == "__main__":
    import sys
    print(json.dumps(asdict(generate(int(sys.argv[1]), int(sys.argv[2]))), indent=1)[:3000])

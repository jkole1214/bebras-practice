"""
Problem family: bead_grammar (rules that grow a string; can this string be built?).

Concept targets: GRAMMAR, RECURSION.
Source tasks: Sailor Necklace (Benjamin B, Cadet A) and Mysteria (Junior C,
Senior B), 2022-23 practice.

Two kinds of scene:
  necklace  A necklace starts as a few beads and grows by whole-necklace rules:
            ("R", "yy") add yy at the right end; ("L", "gg") add gg at the left
            end; ("W", "p") put one p at EACH end.
  wizard    A line of magic objects starts as one object; a rule turns one
            object of a kind into a short line of objects, in order. Objects
            that can still be changed stay in the line (Mysteria).
Bead and object letters: r b y g p are bead colours; X Y are changeable
objects (drawn as diamond and coin); a c are fixed objects (potion, dragon).

Question types:
  can     which of four can be built? (3 cannot; each would be buildable under
          one specific misreading of the rules)
  cannot  which one of four can NOT be built? (like the Bebras tasks)
  count   how many different necklaces of exactly N beads can be built? (typed)
"""

import itertools
import json
import random
from dataclasses import dataclass, field, asdict

LADDER = [
    {"level": 1, "question": "can", "kind": "necklace", "rules": ["R", "W"], "length": (6, 6), "note": "Two necklace rules: which one can be made?"},
    {"level": 2, "question": "can", "kind": "necklace", "rules": ["R", "L", "W"], "length": (8, 8), "note": "Three rules, longer necklaces"},
    {"level": 3, "question": "cannot", "kind": "necklace", "rules": ["R", "W"], "length": (8, 10), "note": "Which one can NOT be made? (like Sailor Necklace)"},
    {"level": 4, "question": "can", "kind": "wizard", "length": (4, 6), "note": "Wizard rules with objects that keep changing (like Mysteria)"},
    {"level": 5, "question": "count", "kind": "necklace", "rules": ["R1", "L", "W"], "rule_sets": [["R1", "W"], ["R1", "L"], ["R1", "L", "W"]], "length": (5, 7), "note": "How many different necklaces of a given length? (type the number)"},
]

MISCONCEPTIONS = {
    "GRAMMAR_WRONG_END": {"concept": "GRAMMAR",
        "description": "Adds beads at either end, when the rule says which end.",
        "remediation": "Read the rule again: which end do the new beads go on? Check the end of the necklace first."},
    "WRAP_ONE_END": {"concept": "GRAMMAR",
        "description": "Reads 'one bead at each end' as two beads on the same end.",
        "remediation": "Point to both ends of the necklace. The rule puts one new bead at each."},
    "GRAMMAR_ORDER_IGNORED": {"concept": "GRAMMAR",
        "description": "Lets a rule put its new objects in any order.",
        "remediation": "The rule's objects always come out in the order shown, left to right."},
    "GRAMMAR_ANY_OBJECT": {"concept": "GRAMMAR",
        "description": "Applies a rule to an object of the wrong kind.",
        "remediation": "Each rule changes only the kind of object on its left side. Which kind is this?"},
    "GRAMMAR_FORWARD_GUESS": {"concept": "GRAMMAR",
        "description": "Tries random forward derivations instead of undoing rules from the string.",
        "remediation": "Ask which rule could have produced the right-hand end, and undo it."},
    "COUNTS_SHORTER_TOO": {"concept": "GRAMMAR",
        "description": "Counts necklaces of every length up to N instead of exactly N beads.",
        "remediation": "Each necklace in the count must have exactly the number of beads asked for."},
}

PROMPT_NECK = "A sailor makes necklaces. She starts with the beads shown, then uses the rules below as many times as she likes, in any order."
PROMPT_WIZ = ("A wizard starts with one object. Each rule turns ONE object of the kind on the left into the objects on the right, "
              "in that order. The wizard can use any rule on any matching object, as often as he likes. "
              "Objects that a rule can still change may stay in the line.")


# --------------------------------------------------------------------------
# Solvers
# --------------------------------------------------------------------------

def neck_step(s, rule, view=None):
    k, x = rule
    out = []
    if k == "R":
        out.append(s + x)
        if view == "GRAMMAR_WRONG_END":
            out.append(x + s)
    elif k == "L":
        out.append(x + s)
        if view == "GRAMMAR_WRONG_END":
            out.append(s + x)
    elif k == "W":
        out.append(x + s + x)
        if view == "WRAP_ONE_END":
            out += [s + x + x, x + x + s]
    return out


def neck_reach(start, rules, maxlen, view=None):
    seen, frontier = {start}, [start]
    while frontier:
        nxt = []
        for s in frontier:
            for r in rules:
                for t in neck_step(s, r, view):
                    if len(t) <= maxlen and t not in seen:
                        seen.add(t)
                        nxt.append(t)
        frontier = nxt
    return seen


def neck_derivation(start, rules, target):
    """Rule steps from start to target (BFS), or None."""
    prev, frontier = {start: None}, [start]
    while frontier:
        nxt = []
        for s in frontier:
            for r in rules:
                t = neck_step(s, r)[0]
                if len(t) <= len(target) and t not in prev:
                    prev[t] = (s, r)
                    nxt.append(t)
        frontier = nxt
    if target not in prev:
        return None
    path, cur = [], target
    while prev[cur]:
        s, r = prev[cur]
        path.append((r, cur))
        cur = s
    return path[::-1]


def wiz_successors(s, rules, view=None):
    out = set()
    for i, ch in enumerate(s):
        for lhs, rhs in rules:
            if lhs != ch and not (view == "GRAMMAR_ANY_OBJECT" and ch in "XY"):
                continue
            outs = {rhs} if view != "GRAMMAR_ORDER_IGNORED" else {"".join(p) for p in itertools.permutations(rhs)}
            for o in outs:
                out.add(s[:i] + o + s[i + 1:])
    return out


def wiz_reach(start, rules, maxlen, view=None):
    seen, frontier = {start}, [start]
    while frontier:
        nxt = []
        for s in frontier:
            for t in wiz_successors(s, rules, view):
                if len(t) <= maxlen and t not in seen:      # rules never make a line shorter
                    seen.add(t)
                    nxt.append(t)
        frontier = nxt
    return seen


def wiz_derivation(start, rules, target):
    prev, frontier = {start: None}, [start]
    while frontier:
        nxt = []
        for s in frontier:
            for t in wiz_successors(s, rules):
                if len(t) <= len(target) and t not in prev:
                    prev[t] = s
                    nxt.append(t)
        frontier = nxt
    if target not in prev:
        return None
    path, cur = [target], target
    while prev[cur]:
        cur = prev[cur]
        path.append(cur)
    return path[::-1]


# --------------------------------------------------------------------------
# Random rule sets
# --------------------------------------------------------------------------

COLOURS = "rbygp"


def random_necklace(rng, kinds):
    cols = list(COLOURS)
    rng.shuffle(cols)
    start = cols[0] + cols[1]
    rules, used = [], 2
    for k in kinds:
        c = cols[used % len(cols)]
        used += 1
        if k == "R1":                       # a rule that adds ONE bead on the right
            rules.append(("R", c))
        elif k == "W":
            rules.append((k, c))
        else:
            rules.append((k, c + c if rng.random() < 0.6 else c + cols[(used + 1) % len(cols)]))
    return start, rules


def random_wizard(rng):
    """Two changeable kinds X, Y and fixed objects a, c. X is the start."""
    for _ in range(200):
        def rhs(lo, hi, pool):
            return "".join(rng.choice(pool) for _ in range(rng.randint(lo, hi)))
        rules = [("X", rhs(1, 2, "Yac")), ("X", rhs(2, 3, "XYac")), ("Y", rhs(2, 2, "ac")), ("Y", rhs(2, 3, "XYac"))]
        if not any("X" in r or "Y" in r for _, r in rules[1:2]) or not any(ch in "XY" for ch in rules[3][1]):
            continue
        if len({r for _, r in rules}) < 4:
            continue
        return "X", rules
    return None


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


RULE_WORDS = {"R": "add {{{{{x}}}}} at the right end", "L": "add {{{{{x}}}}} at the left end", "W": "put one {{{{{x}}}}} at each end"}


def rule_text(rule):
    k, x = rule
    return RULE_WORDS[k].format(x=x)


def neck_steps_text(start, rules, target):
    d = neck_derivation(start, rules, target)
    return [f"• start: {{{{{start}}}}}"] + [f"• {rule_text(r)}: {{{{{s}}}}}" for r, s in d]


def backward_hints():
    return ["Look at the ends of each necklace. Which rule could have made the last change?",
            "Undo that rule: take the added beads off. Is what is left a necklace she could have made?",
            "Keep undoing until you reach the starting beads, or get stuck."]


def make_necklace(rng, cfg, seed):
    lo, hi = cfg["length"]
    for _ in range(3000):
        start, rules = random_necklace(rng, rng.choice(cfg["rule_sets"]) if "rule_sets" in cfg else cfg["rules"])
        L = rng.choice([n for n in range(lo, hi + 1) if cfg["question"] == "count" or (n - 2) % 2 == 0])
        true = neck_reach(start, rules, L)
        true_L = sorted(s for s in true if len(s) == L)
        views = {v: neck_reach(start, rules, L, v) for v in ("GRAMMAR_WRONG_END", "WRAP_ONE_END")}
        tagged = {}
        for v, reach in views.items():
            for s in reach:
                if len(s) == L and s not in true:
                    tagged.setdefault(s, set()).add(v)
        qt = cfg["question"]
        base = dict(family="bead_grammar", level=cfg["level"], question_type=qt, seed=seed,
                    scene={"kind": "necklace", "start": start, "rules": [list(r) for r in rules], "length": L},
                    prompt=PROMPT_NECK, concepts=["GRAMMAR", "RECURSION"], knobs={"rules": len(rules), "length": L})
        if qt == "can":
            if not true_L or len({t for ts in tagged.values() for t in ts}) < 2 or len(tagged) < 3:
                continue
            ans = rng.choice(true_L)
            by = {v: [s for s, ts in tagged.items() if v in ts] for v in views}
            picks = [rng.choice(by["GRAMMAR_WRONG_END"]), rng.choice(by["WRAP_ONE_END"])]
            if picks[0] == picks[1]:
                continue
            rest = [s for s in tagged if s not in picks]
            if not rest:
                continue
            picks.append(rng.choice(rest))
            opts = [ans] + picks
            rng.shuffle(opts)
            return Problem(**base, question=f"Which of these necklaces can she make?",
                           options=opts, answer_index=opts.index(ans), answer_value=ans, entry="choice",
                           distractors=[{"option": s, "misconceptions": sorted(tagged[s])} for s in picks], value_tags={},
                           explanation=[f"{{{{{ans}}}}} can be made:"] + neck_steps_text(start, rules, ans)
                                       + ["Each of the others could only be made by putting beads on the wrong end, "
                                          "or both wrap beads on one end."],
                           hints=backward_hints())
        if qt == "cannot":
            hard = [s for s in true_L if len(neck_derivation(start, rules, s)) >= 3]
            if len(hard) < 3 or not tagged:
                continue
            ans = rng.choice(sorted(tagged))
            picks = rng.sample(hard, 3)
            opts = [ans] + picks
            rng.shuffle(opts)
            expl = [f"{{{{{ans}}}}} cannot be made. Work backward: no rule can be undone all the way to the start {{{{{start}}}}}."]
            for s in sorted(picks, key=lambda x: -len({r for r, _ in neck_derivation(start, rules, x)}))[:1]:
                expl += [f"For example, {{{{{s}}}}} can be made:"] + neck_steps_text(start, rules, s)
            return Problem(**base, question="Which of these necklaces can she NOT make?",
                           options=opts, answer_index=opts.index(ans), answer_value=ans, entry="choice",
                           distractors=[{"option": s, "misconceptions": ["GRAMMAR_FORWARD_GUESS"]} for s in picks], value_tags={},
                           explanation=expl, hints=backward_hints())
        if qt == "count":
            truth = len(true_L)
            upto = sum(1 for s in true if len(s) <= L and s != start)
            vals = {}
            we = sum(1 for s in views["GRAMMAR_WRONG_END"] if len(s) == L)
            if we != truth:
                vals.setdefault(we, set()).add("GRAMMAR_WRONG_END")
            if upto != truth:
                vals.setdefault(upto, set()).add("COUNTS_SHORTER_TOO")
            if not (4 <= truth <= 15) or len(vals) < 2:
                continue
            return Problem(**base, question=f"How many different necklaces with exactly {L} beads can she make?",
                           options=[], answer_index=-1, answer_value=truth, entry="number", distractors=[],
                           value_tags={str(v): sorted(t) for v, t in vals.items()},
                           explanation=[f"List them by length, using every rule on every necklace of the length before:",
                                        *[f"• {n} beads: " + " ".join("{{" + x + "}}" for x in sorted(s for s in true if len(s) == n))
                                          for n in range(len(start), L + 1) if any(len(s) == n for s in true)],
                                        f"So there are {truth} with exactly {L} beads."],
                           hints=["Start from the first necklace. Which necklaces can each rule make from it?",
                                  "Make a list for each number of beads, from small to big.",
                                  f"Only count the necklaces with exactly {L} beads."])
    raise RuntimeError(f"necklace generation failed at level {cfg['level']}")


def make_wizard(rng, cfg, seed):
    lo, hi = cfg["length"]
    for _ in range(3000):
        got = random_wizard(rng)
        if not got:
            continue
        start, rules = got
        true = wiz_reach(start, rules, hi)
        mixed = lambda s: any(ch in "ac" for ch in s) and any(ch in "XY" for ch in s) and len(set(s)) >= 3
        cands = [s for s in true if lo <= len(s) <= hi and mixed(s)]
        cands = [s for s in cands if len(wiz_derivation(start, rules, s)) >= 4]
        if len(cands) < 2 or len(true) > 400:
            continue
        tagged = {}
        for v in ("GRAMMAR_ORDER_IGNORED", "GRAMMAR_ANY_OBJECT"):
            for s in wiz_reach(start, rules, hi, v):
                if lo <= len(s) <= hi and s not in true and mixed(s):
                    tagged.setdefault(s, set()).add(v)
        by = {v: [s for s, ts in tagged.items() if v in ts] for v in ("GRAMMAR_ORDER_IGNORED", "GRAMMAR_ANY_OBJECT")}
        if not all(by.values()):
            continue
        ans = rng.choice(sorted(cands))
        p1 = rng.choice(sorted(by["GRAMMAR_ORDER_IGNORED"]))
        p2 = rng.choice(sorted(s for s in by["GRAMMAR_ANY_OBJECT"] if s != p1) or [p1])
        rest = sorted(s for s in tagged if s not in (p1, p2))
        if p1 == p2 or not rest:
            continue
        picks = [p1, p2, rng.choice(rest)]
        lens = [len(ans)] + [len(s) for s in picks]
        if lens.count(max(lens)) == 1 and lens[0] == max(lens):
            continue
        opts = [ans] + picks
        rng.shuffle(opts)
        path = wiz_derivation(start, rules, ans)
        return Problem(family="bead_grammar", level=cfg["level"], question_type="can", seed=seed,
                       scene={"kind": "wizard", "start": start, "rules": [list(r) for r in rules]},
                       prompt=PROMPT_WIZ, question="Which of these lines can the wizard make?",
                       options=opts, answer_index=opts.index(ans), answer_value=ans, entry="choice",
                       distractors=[{"option": s, "misconceptions": sorted(tagged[s])} for s in picks], value_tags={},
                       concepts=["GRAMMAR", "RECURSION"],
                       explanation=["This line can be made, one rule at a time:"] + [f"• {{{{{s}}}}}" for s in path]
                                   + ["The others need a rule's objects in a different order, or a rule used on the wrong kind of object."],
                       hints=["Find a group of objects in the line that one rule makes, in the same order.",
                              "Replace that group with the object it came from. Repeat.",
                              "If you get back to a single diamond, the line can be made."],
                       knobs={"length": len(ans)})
    raise RuntimeError("wizard generation failed")


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    rng = random.Random(seed)
    return (make_wizard if cfg["kind"] == "wizard" else make_necklace)(rng, cfg, seed)


if __name__ == "__main__":
    import sys
    print(json.dumps(asdict(generate(int(sys.argv[1]), int(sys.argv[2]))), indent=1))

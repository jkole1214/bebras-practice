"""
Problem family: pointer_lists (indirection: a value used as the next position).

Concept targets: INDIRECTION, FUNC_COMPOSITION.
Source task: Lists (2022-23 practice; Cadet C, Junior B, Senior A).

Scenario (original wording): rows of numbered boxes, each named by a letter.
(A 3) means "the number in box 3 of row A". Lookups can be nested:
(A (B 2)) means find (B 2) first, then use that number as a box in row A.

Scene model: {"lists": {name: [values]}, "expr": nested tuple}, where each
row is a shuffle of 1..n so every value is a valid position. The expression
is stored as a list of row names from outside to inside plus the starting
position: ["A", "B", "C", 3] means (A (B (C 3))).

Question types:
  lookup   evaluate the expression (multiple choice or typed)
  inverse  which starting position makes the expression equal a target?

Every distractor is the value a specific wrong habit produces; instances
where a wrong habit lands on the right answer are rejected, because such an
item cannot tell the habit apart from understanding.
"""

import json
import random
from dataclasses import dataclass, field, asdict

LADDER = [
    {"level": 1, "question": "lookup", "rows": 1, "depth": 1, "n": 5, "entry": "choice", "note": "One lookup: the number in a given box"},
    {"level": 2, "question": "lookup", "rows": 1, "depth": 2, "n": 5, "entry": "choice", "note": "A lookup inside a lookup, same row"},
    {"level": 3, "question": "lookup", "rows": 2, "depth": 2, "n": 5, "entry": "choice", "note": "Two rows, one inside the other"},
    {"level": 4, "question": "lookup", "rows": 3, "depth": 3, "n": 5, "entry": "choice", "note": "Three rows nested"},
    {"level": 5, "question": "lookup", "rows": 3, "depth": 4, "n": 7, "entry": "number", "note": "Four lookups, longer rows, a row used twice (type the number)"},
    {"level": 6, "question": "inverse", "rows": 2, "depth": 2, "n": 6, "entry": "choice", "note": "Work backward: which starting box gives the target?"},
]

MISCONCEPTIONS = {
    "ZERO_BASED_INDEX": {"concept": "INDIRECTION",
        "description": "Counts boxes from 0, so reads one box to the right.",
        "remediation": "Point to the small number above each box and read the box under that number."},
    "COUNTS_FROM_RIGHT": {"concept": "INDIRECTION",
        "description": "Counts box positions from the right-hand end of the row.",
        "remediation": "The box numbers are printed above the row; use them, starting from the left."},
    "POSITION_AS_ANSWER": {"concept": "INDIRECTION",
        "description": "Answers with the box number instead of the number inside the box.",
        "remediation": "Ask: is this the box's label, or what is written inside it?"},
    "STOPS_ONE_EARLY": {"concept": "INDIRECTION",
        "description": "Does the inner lookup and stops, missing the outer one.",
        "remediation": "Count the brackets: each pair is one lookup to do."},
    "INDIRECTION_OUTSIDE_IN": {"concept": "INDIRECTION",
        "description": "Evaluates a nested lookup from the outside in (left to right).",
        "remediation": "Ask which part of the expression can be worked out with what you already know."},
    "SAME_ROW_EVERY_STEP": {"concept": "INDIRECTION",
        "description": "Uses the innermost row for every step instead of switching rows.",
        "remediation": "Before each step, say which row's name is in front of the bracket."},
    "FORWARD_NOT_INVERSE": {"concept": "FUNC_COMPOSITION",
        "description": "Asked which start gives the target, runs the expression forward from the target instead of working backward.",
        "remediation": "Ask: which box of the outer row holds the target? Then where is that number in the inner row?"},
    "INVERSE_ONE_STEP": {"concept": "FUNC_COMPOSITION",
        "description": "Works backward through the outer row only and stops.",
        "remediation": "You found the box in the outer row. That box number came from the inner row: find it there."},
}

NAMES = "ABCD"
PROMPT = ("Each row of boxes has a letter name, and the boxes are numbered 1, 2, 3, ... from the left. "
          "(A 3) means the number inside box 3 of row A. In (A (B 2)), work out (B 2) first, then use that number as the box in row A.")


def expr_text(chain):
    *rows, start = chain
    s = str(start)
    for r in reversed(rows):
        s = f"({r} {s})"
    return s


def evaluate(lists, chain):
    *rows, start = chain
    v = start
    for r in reversed(rows):
        v = lists[r][v - 1]
    return v


def steps(lists, chain):
    *rows, start = chain
    v, out = start, []
    for r in reversed(rows):
        w = lists[r][v - 1]
        out.append(f"  ({r} {v}) = {w}")
        v = w
    return out


# misconception solvers

def m_zero_based(lists, chain):
    *rows, v = chain
    for r in reversed(rows):
        if v >= len(lists[r]):
            return None
        v = lists[r][v]
    return v


def m_from_right(lists, chain):
    *rows, v = chain
    for r in reversed(rows):
        v = lists[r][len(lists[r]) - v]
    return v


def m_position(lists, chain):
    """Answers with the box number of the last lookup instead of what is inside it."""
    *rows, start = chain
    return start if len(rows) == 1 else None   # deeper, this is the same value as STOPS_ONE_EARLY


def m_stops_early(lists, chain):
    *rows, start = chain
    if len(rows) < 2:
        return None
    return evaluate(lists, rows[1:] + [start])


def m_outside_in(lists, chain):
    *rows, start = chain
    if len(set(rows)) < 2:
        return None
    return evaluate(lists, list(reversed(rows)) + [start])


def m_same_row(lists, chain):
    *rows, start = chain
    if len(set(rows)) < 2:
        return None
    return evaluate(lists, [rows[-1]] * len(rows) + [start])


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
    answer_value: int
    entry: str
    distractors: list
    value_tags: dict
    concepts: list
    explanation: list
    hints: list
    knobs: dict = field(default_factory=dict)


def random_lists(rng, k, n):
    out = {}
    for name in NAMES[:k]:
        row = list(range(1, n + 1))
        while True:
            rng.shuffle(row)
            if all(row[i] != i + 1 for i in range(n)):      # no box holds its own number
                break
        out[name] = row[:]
    return out


def random_chain(rng, cfg, lists):
    names = list(lists)
    d = cfg["depth"]
    if cfg["rows"] == 1:
        rows = [names[0]] * d
    elif d == cfg["rows"]:
        rows = names[:]
        rng.shuffle(rows)
    else:  # a row used twice, never twice in a row
        while True:
            rows = [rng.choice(names) for _ in range(d)]
            if set(rows) == set(names) and all(a != b for a, b in zip(rows, rows[1:])):
                break
    return rows + [rng.randint(1, cfg["n"])]


def wrong_values(lists, chain, truth):
    vals = {}
    for tag, f in (("ZERO_BASED_INDEX", m_zero_based), ("COUNTS_FROM_RIGHT", m_from_right),
                   ("POSITION_AS_ANSWER", m_position), ("STOPS_ONE_EARLY", m_stops_early),
                   ("INDIRECTION_OUTSIDE_IN", m_outside_in), ("SAME_ROW_EVERY_STEP", m_same_row)):
        v = f(lists, chain)
        if v is None:
            continue
        vals.setdefault(v, set()).add(tag)
    return vals


def make_lookup(rng, cfg, seed):
    key_tag = {1: "ZERO_BASED_INDEX", 2: "STOPS_ONE_EARLY", 3: "INDIRECTION_OUTSIDE_IN",
               4: "INDIRECTION_OUTSIDE_IN", 5: "SAME_ROW_EVERY_STEP"}[cfg["level"]]
    for _ in range(5000):
        lists = random_lists(rng, cfg["rows"], cfg["n"])
        chain = random_chain(rng, cfg, lists)
        truth = evaluate(lists, chain)
        vals = wrong_values(lists, chain, truth)
        if truth in vals:
            continue      # a wrong habit gives the right answer: the item could not detect it
        if key_tag not in {t for ts in vals.values() for t in ts}:
            continue
        if cfg["entry"] == "choice":
            ranked = sorted(vals, key=lambda v: (key_tag not in vals[v], rng.random()))
            if len(ranked) < 3:
                continue
            opts = [truth] + ranked[:3]
            rng.shuffle(opts)
            ans = opts.index(truth)
            distractors = [{"option": v, "misconceptions": sorted(vals[v])} for v in opts if v != truth]
        else:
            opts, ans, distractors = [], -1, []
        e = expr_text(chain)
        expl = [f"Work from the inside out. {e}:"] + steps(lists, chain) + [f"So {e} = {truth}."]
        if "INDIRECTION_OUTSIDE_IN" in {t for ts in vals.values() for t in ts} and cfg["level"] >= 3:
            wrong = [v for v, ts in vals.items() if "INDIRECTION_OUTSIDE_IN" in ts][0]
            expl.append(f"Working from the outside in gives {wrong}, which is a different question.")
        hints = ["Find the innermost bracket. It has a row letter and a plain number.",
                 "Work that one out. Its answer is the box number for the next bracket out.",
                 "Keep going outward, using the row named in front of each bracket."]
        if cfg["depth"] == 1:
            hints = ["The small numbers above the row tell you which box is which.",
                     f"Find box {chain[-1]} in row {chain[0]}. What number is inside it?"]
        return Problem("pointer_lists", cfg["level"], "lookup", seed,
                       {"lists": lists, "chain": chain},
                       PROMPT, f"What is {e}?", opts, ans, truth, cfg["entry"], distractors,
                       {str(v): sorted(t) for v, t in vals.items()},
                       ["INDIRECTION", "FUNC_COMPOSITION"], expl, hints,
                       {"rows": cfg["rows"], "depth": cfg["depth"], "n": cfg["n"]})
    raise RuntimeError(f"lookup generation failed at level {cfg['level']}")


def make_inverse(rng, cfg, seed):
    for _ in range(5000):
        lists = random_lists(rng, cfg["rows"], cfg["n"])
        rows = list(lists)
        rng.shuffle(rows)
        target = rng.randint(1, cfg["n"])
        outer, inner = rows
        mid = lists[outer].index(target) + 1          # box of the outer row holding the target
        start = lists[inner].index(mid) + 1           # box of the inner row holding mid
        vals = {}
        fwd = evaluate(lists, rows + [target])
        vals.setdefault(fwd, set()).add("FORWARD_NOT_INVERSE")
        vals.setdefault(mid, set()).add("INVERSE_ONE_STEP")
        swapped = lists[outer].index(lists[inner].index(target) + 1) + 1   # backward but rows in the wrong order
        vals.setdefault(swapped, set()).add("INDIRECTION_OUTSIDE_IN")
        if start in vals or len(vals) < 3 or target == start:
            continue
        opts = [start] + list(vals)[:3]
        rng.shuffle(opts)
        e = expr_text(rows + ["?"])
        expl = [f"Work backward from the outside. {e} = {target}:",
                f"  In row {outer}, the number {target} is in box {mid}. So ({inner} ?) must be {mid}.",
                f"  In row {inner}, the number {mid} is in box {start}. So ? = {start}.",
                f"Check: {expr_text(rows + [start])} = {evaluate(lists, rows + [start])}."]
        return Problem("pointer_lists", cfg["level"], "inverse", seed,
                       {"lists": lists, "chain": rows + [start], "target": target},
                       PROMPT, f"Which number should replace ? so that {e} = {target}?",
                       opts, opts.index(start), start, "choice",
                       [{"option": v, "misconceptions": sorted(vals[v])} for v in opts if v != start],
                       {str(v): sorted(t) for v, t in vals.items()},
                       ["INDIRECTION", "FUNC_COMPOSITION"], expl,
                       [f"Start with the outer row, {outer}. Which box holds {target}?",
                        f"That box number is what ({inner} ?) has to be.",
                        f"Now find that number in row {inner}. Which box is it in?"],
                       {"rows": 2, "n": cfg["n"]})
    raise RuntimeError("inverse generation failed")


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    rng = random.Random(seed)
    return (make_inverse if cfg["question"] == "inverse" else make_lookup)(rng, cfg, seed)


if __name__ == "__main__":
    import sys
    print(json.dumps(asdict(generate(int(sys.argv[1]), int(sys.argv[2]))), indent=1))

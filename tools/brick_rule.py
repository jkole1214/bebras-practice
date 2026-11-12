"""
Problem family: brick_rule (Brick Pyramid). Folder: brick-pyramid.

Concept targets: CONSTRAINT_SAT, SEQ_EXEC (and ELIMINATION for the backward levels).

Scenario (original): bricks come in three colours: red, yellow and blue. In a pyramid every
brick rests on two bricks of the row below, and the builders follow one rule: a brick and
the two it rests on are either all the same colour or all different. So two matching
bricks get that colour on top, and two different bricks get the third colour.

This follows the idea of a three-colour tower task (a local rule applied row by row; it is
addition mod 3 in disguise); the wording, theme and pictures are our own.

One scene model (rows, the bricks shown, the bricks the student fills) drives both the SVG
picture and the solver. The picture carries each brick in data-* attributes; the independent
checker rebuilds the pyramid from the SVG and solves it again with arithmetic mod 3.

Bricks are named "r,c": row r counted from the bottom (0), brick c from the left. Brick
(r, c) rests on (r-1, c) and (r-1, c+1).

Question types:
  fill:    colour every empty brick (entry "bricks"; levels 1 and 3)
  count:   when the pyramid is finished, how many bricks are <colour>? (choice; level 2)
  hidden:  bottom bricks are hidden and some bricks above are shown; colour the hidden
           ones (entry "bricks"; levels 4-5). Exactly one colouring fits.

Misconceptions:
  COPIES_A_SUPPORT     when the two bricks below differ, copies one of them instead of the third colour
  MATCH_MEANS_CHANGE   when the two bricks below match, puts a different colour on top
  FORGETS_BOTTOM_ROW   counts only the bricks above the bottom row
For fill questions the server tags a wrong brick from the student's own bricks below it
(see engine.js); for count and hidden questions the tags come from whole-pyramid solvers.
"""

import json
import random
from dataclasses import dataclass, field, asdict
from itertools import product

COLS = "RYB"
NAME = {"R": "red", "Y": "yellow", "B": "blue"}


# --------------------------------------------------------------------------
# The rule and its misreadings
# --------------------------------------------------------------------------

def rule(a, b):
    return a if a == b else next(c for c in COLS if c not in (a, b))


def copy_left(a, b):
    return a if a == b else a          # different: copies the left brick


def copy_right(a, b):
    return b


def match_change(a, b):
    return COLS[(COLS.index(a) + 1) % 3] if a == b else rule(a, b)


def build(bottom, f=rule):
    rows = [list(bottom)]
    while len(rows[-1]) > 1:
        r = rows[-1]
        rows.append([f(r[i], r[i + 1]) for i in range(len(r) - 1)])
    return rows


def as_map(rows):
    return {f"{r},{c}": col for r, row in enumerate(rows) for c, col in enumerate(row)}


VARIANTS = {"COPIES_A_SUPPORT": [copy_left, copy_right], "MATCH_MEANS_CHANGE": [match_change]}

MISCONCEPTIONS = {
    "COPIES_A_SUPPORT": {"concept": "CONSTRAINT_SAT",
        "description": "When the two bricks below are different colours, copies one of them instead of using the third colour.",
        "remediation": "Point to two different bricks and ask: if the top must differ from both, which colour is left?"},
    "MATCH_MEANS_CHANGE": {"concept": "CONSTRAINT_SAT",
        "description": "When the two bricks below match, puts a different colour on top, as if every brick had to change.",
        "remediation": "Reread the rule: 'all the same' is allowed. Ask what goes on top of two red bricks."},
    "FORGETS_BOTTOM_ROW": {"concept": "SEQ_EXEC",
        "description": "Counts only the bricks the student worked out and leaves out the bottom row that was given.",
        "remediation": "Ask the student to point at every brick of that colour, starting with the bottom row."},
}

LADDER = [
    {"level": 1, "question": "fill", "width": 4, "note": "Colour a small pyramid row by row (4 bricks at the bottom)."},
    {"level": 2, "question": "count", "width": 5, "note": "Finish the pyramid in your head and count one colour."},
    {"level": 3, "question": "fill", "width": 6, "note": "Colour a bigger pyramid (6 bricks at the bottom)."},
    {"level": 4, "question": "hidden", "width": 5, "hide": 1, "top": True, "extra_rows": (2, 9),
     "note": "Work backward: one bottom brick is hidden, and only the top brick is shown."},
    {"level": 5, "question": "hidden", "width": 6, "hide": 2, "top": False, "extra_rows": (1, 2),
     "note": "Work backward: two bottom bricks are hidden and a few low bricks are shown; a brick and one brick under it fix the other."},
]


# --------------------------------------------------------------------------
# Problem assembly
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


PROMPT = ("Bricks come in three colours: red, yellow and blue. In this pyramid every brick rests on two bricks "
          "of the row below. The rule: a brick and the two it rests on are either all the same colour or all different.")


def pyramid_lines(rows):
    """Monospace picture, top row first: letters spaced so each brick sits between its two supports."""
    n = len(rows[0])
    return ["  " + " " * r + " ".join(rows[r]) for r in range(n - 1, -1, -1)]


def row_lines(rows):
    out = []
    for r in range(1, len(rows)):
        out.append(f"Row {r + 1} from the bottom: " + ", ".join(NAME[c] for c in rows[r]) + ".")
    return out


def first_example(rows):
    """One worked brick of each kind, from row 2."""
    out = []
    below = rows[0]
    done = set()
    for c, top in enumerate(rows[1]):
        a, b = below[c], below[c + 1]
        kind = a == b
        if kind in done:
            continue
        done.add(kind)
        if kind:
            out.append(f"On top of {NAME[a]} and {NAME[b]} goes {NAME[top]}: all the same.")
        else:
            out.append(f"On top of {NAME[a]} and {NAME[b]} goes {NAME[top]}, the third colour: all different.")
    return out


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    rng = random.Random(seed)
    make = {"fill": make_fill, "count": make_count, "hidden": make_hidden}[cfg["question"]]
    for _ in range(2000):
        bottom = "".join(rng.choice(COLS) for _ in range(cfg["width"]))
        rows = build(bottom)
        # both kinds of brick must appear above the bottom row, so both halves of the rule are used
        pairs = [(rows[r][c], rows[r][c + 1]) for r in range(len(rows) - 1) for c in range(len(rows[r]) - 1)]
        if not any(a == b for a, b in pairs) or sum(1 for a, b in pairs if a != b) < 2:
            continue
        p = make(rng, cfg, seed, bottom, rows)
        if p:
            return p
    raise RuntimeError(f"brick_rule generation failed at level {level}")


def make_fill(rng, cfg, seed, bottom, rows):
    n = cfg["width"]
    given = {f"0,{c}": bottom[c] for c in range(n)}
    edit = [f"{r},{c}" for r in range(1, n) for c in range(n - r)]
    expl = first_example(rows) + row_lines(rows) + pyramid_lines(rows)
    expl.append(f"So the top brick is {NAME[rows[-1][0]]}.")
    return Problem(
        family="brick_rule", level=cfg["level"], question_type="fill", seed=seed,
        scene={"rows": n, "given": given, "edit": edit}, svg=render_svg(n, given, edit, [], seed),
        prompt=PROMPT, question="Colour every empty brick. Tap a brick to change its colour.",
        options=[], answer_index=-1, answer_value={k: v for k, v in as_map(rows).items() if k in edit}, entry="bricks",
        distractors=[], value_tags={}, concepts=["CONSTRAINT_SAT", "SEQ_EXEC"], explanation=expl,
        hints=["Start with the row just above the bottom. Each brick there rests on two bottom bricks.",
               "Two bricks of the same colour: the brick on top is that colour too.",
               "Two different colours: the brick on top is the third colour, the one neither of them has."],
        knobs={"width": n},
    )


def make_count(rng, cfg, seed, bottom, rows):
    n = cfg["width"]
    cols = list(COLS)
    rng.shuffle(cols)
    for ask in cols:
        cnt = lambda rs: sum(row.count(ask) for row in rs)
        truth = cnt(rows)
        wrong = {}

        def add(v, tag):
            if v != truth and v >= 0:
                wrong.setdefault(v, [])
                if tag not in wrong[v]:
                    wrong[v].append(tag)
        for tag, fs in VARIANTS.items():
            for f in fs:
                add(cnt(build(bottom, f)), tag)
        add(truth - bottom.count(ask), "FORGETS_BOTTOM_ROW")
        if any(cnt(build(bottom, f)) == truth for f in VARIANTS["COPIES_A_SUPPORT"]):
            continue                         # the main mistake must not land on the right count
        under = [v for v in wrong if v < truth]
        over = [v for v in wrong if v > truth]
        if not under or not over or len(wrong) < 3:
            continue
        pick = [rng.choice(sorted(under)), rng.choice(sorted(over))]
        pick.append(rng.choice(sorted(v for v in wrong if v not in pick)))
        opts = sorted(pick + [truth])
        given = {f"0,{c}": bottom[c] for c in range(n)}
        expl = first_example(rows) + row_lines(rows) + pyramid_lines(rows)
        expl.append(f"{NAME[ask].capitalize()} bricks: {bottom.count(ask)} in the bottom row and "
                    f"{truth - bottom.count(ask)} above it. So {truth} bricks are {NAME[ask]}.")
        return Problem(
            family="brick_rule", level=cfg["level"], question_type="count", seed=seed,
            scene={"rows": n, "given": given, "edit": []}, svg=render_svg(n, given, [], [], seed),
            prompt=PROMPT, question=f"When the pyramid is finished, how many bricks are {NAME[ask]}?",
            options=opts, answer_index=opts.index(truth), answer_value=truth, entry="choice",
            distractors=[{"option": v, "misconceptions": sorted(wrong[v], key=lambda t: (t != "COPIES_A_SUPPORT", t))}
                         for v in opts if v != truth],
            value_tags={}, concepts=["CONSTRAINT_SAT", "SEQ_EXEC"], explanation=expl,
            hints=["Work out the row above the bottom first, then the next row, up to the top.",
                   "Two different colours below: the brick on top is the third colour.",
                   f"Count every {NAME[ask]} brick in the whole pyramid, the bottom row too."],
            knobs={"width": n, "ask": NAME[ask]},
        )
    return None


def make_hidden(rng, cfg, seed, bottom, rows):
    n, k = cfg["width"], cfg["hide"]
    hide = sorted(rng.sample(range(n), k))
    full = as_map(rows)
    upper = [f"{r},{c}" for r in range(1, n) for c in range(n - r)]
    shown = [f"{n - 1},0"] if cfg["top"] else []
    lo, hi = cfg["extra_rows"]
    edit = [f"0,{c}" for c in hide]

    def fits(fill, f=rule):
        b = list(bottom)
        for c, col in zip(hide, fill):
            b[c] = col
        m = as_map(build("".join(b), f))
        return all(m[s] == full[s] for s in shown)

    combos = ["".join(x) for x in product(COLS, repeat=k)]
    for _ in range(4):                       # show a few more bricks until exactly one colouring fits
        good = [x for x in combos if fits(x)]
        if len(good) == 1:
            break
        extra = [s for s in upper if s not in shown and lo <= int(s.split(",")[0]) <= hi]
        if not extra:
            return None
        shown.append(rng.choice(extra))
    good = [x for x in combos if fits(x)]
    if len(good) != 1 or len(shown) > k + 1 or not shown:
        return None
    truth = good[0]
    value_tags = {}
    for x in combos:
        if x == truth:
            continue
        tags = [t for t, fs in VARIANTS.items() if any(fits(x, f) for f in fs)]
        if tags:
            value_tags[x] = tags
    if not value_tags:
        return None
    given = {f"0,{c}": bottom[c] for c in range(n) if c not in hide}
    given.update({s: full[s] for s in shown})
    shown_txt = " and ".join(f"the {NAME[full[s]]} brick in row {int(s.split(',')[0]) + 1}" for s in sorted(shown, reverse=True))
    if not cfg["top"]:
        shown_txt = "the bricks that are shown"
    names_h = " and ".join(f"brick {c + 1}" for c in hide)
    if k == 1:
        tries = []
        for col in COLS:
            b = list(bottom)
            b[hide[0]] = col
            tries.append(f"a {NAME[col]} hidden brick makes the top {NAME[build(''.join(b))[-1][0]]}")
        expl = ["Try each colour for the hidden brick and build the pyramid up: " + "; ".join(tries) + ".",
                f"Only {NAME[truth]} gives the {NAME[full[shown[0]]]} top brick."]
    else:
        expl = ["Work down from a shown brick: if you know a brick and one of the two it rests on, the other one is "
                "forced (the same colour if the two you know match, otherwise the third colour)."]
        steps = backward_steps(n, bottom, hide, shown, full)
        if steps is None:
            return None
        expl += steps
        expl.append(f"Only one way fits every shown brick: {' and '.join(NAME[c] for c in truth)}.")
    expl += pyramid_lines(rows)
    expl.append("So the hidden " + ("brick is " + NAME[truth] if k == 1 else
                "bricks are " + " and ".join(NAME[c] for c in truth) + ", from left to right") + ".")
    return Problem(
        family="brick_rule", level=cfg["level"], question_type="hidden", seed=seed,
        scene={"rows": n, "given": given, "edit": edit}, svg=render_svg(n, given, edit, [], seed),
        prompt=PROMPT + f" Some bricks are hidden ({names_h} of the bottom row), and only some bricks above are shown.",
        question=("Which colour is the hidden brick? Tap it to change its colour." if k == 1 else
                  "Which colours are the hidden bricks? Tap them to change their colours."),
        options=[], answer_index=-1, answer_value={e: c for e, c in zip(edit, truth)}, entry="bricks",
        distractors=[], value_tags=value_tags, concepts=["CONSTRAINT_SAT", "SEQ_EXEC", "ELIMINATION"], explanation=expl,
        hints=(["Try a colour for the hidden brick and build the pyramid up from it.",
                "Build row by row with your try, and check it against the top brick that is shown.",
                "If a try gives a different top brick, cross it out and try the next colour."] if cfg["top"] else
               ["First colour every brick you can work out from the bottom bricks you know.",
                "Look at a shown brick. If you know one of the two bricks it rests on, the other one is forced.",
                "Two matching colours stay together; a brick and one different brick under it need the third colour on the other side."]),
        knobs={"width": n, "hidden": k, "shown": len(shown)},
    )


def backward_steps(n, bottom, hide, shown, full):
    """Plain-language deduction, or None when step-by-step reasoning cannot reach every hidden brick.
    Upward: two known supports give the brick on top. Downward: a known brick and one known support
    give the other support. Only the steps the hidden bricks depend on are kept."""
    known = {f"0,{c}": bottom[c] for c in range(n) if c not in hide}
    known.update({s: full[s] for s in shown})
    why = {}                                  # brick -> (sentence, bricks it came from)
    nm = lambda k: f"row {int(k.split(',')[0]) + 1}, brick {int(k.split(',')[1]) + 1}"
    for _ in range(60):
        moved = False
        for r in range(1, n):
            for c in range(n - r):
                k, a, b = f"{r},{c}", f"{r - 1},{c}", f"{r - 1},{c + 1}"
                if k not in known and a in known and b in known:
                    known[k] = rule(known[a], known[b])
                    why[k] = (f"{nm(k).capitalize()} rests on {NAME[known[a]]} and {NAME[known[b]]}, so it is {NAME[known[k]]}.", [a, b])
                    moved = True
                elif k in known and (a in known) != (b in known):
                    have, miss = (a, b) if a in known else (b, a)
                    known[miss] = rule(known[k], known[have])
                    label = f"hidden brick {int(miss.split(',')[1]) + 1}" if miss.startswith("0,") else nm(miss)
                    why[miss] = (f"{nm(k).capitalize()} is {NAME[known[k]]} and rests on a {NAME[known[have]]} brick, "
                                 f"so the other brick under it, {label}, must be {NAME[known[miss]]}.", [k, have])
                    moved = True
        if not moved:
            break
    if not all(f"0,{c}" in known for c in hide):
        return None
    need, stack = set(), [f"0,{c}" for c in hide]
    while stack:
        k = stack.pop()
        if k in why and k not in need:
            need.add(k)
            stack.extend(why[k][1])
    order = list(why)
    return [why[k][0] for k in order if k in need]


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

BW, BH, GAP = 64, 44, 4
FILL = {"R": "#d9534f", "Y": "#f2c14e", "B": "#3b6fd8", "": "#f4f1ea"}
INK = {"R": "#ffffff", "Y": "#1f2933", "B": "#ffffff", "": "#5a6880"}


def brick_xy(n, r, c):
    x = 16 + r * (BW + GAP) / 2 + c * (BW + GAP)
    y = 16 + (n - 1 - r) * (BH + GAP)
    return x, y


def render_svg(n, given, edit, _unused, seed):
    W = int(32 + n * (BW + GAP) - GAP)
    H = int(32 + n * (BH + GAP) - GAP)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="Helvetica, Arial, sans-serif" class="pyramid" data-family="brick_rule" data-seed="{seed}">',
           f'<rect x="0" y="0" width="{W}" height="{H}" rx="10" fill="#e7edf2"/>']
    for r in range(n):
        for c in range(n - r):
            k = f"{r},{c}"
            col = given.get(k, "")
            x, y = brick_xy(n, r, c)
            ed = k in edit
            label = col or ("?" if ed else "")
            dash = ' stroke-dasharray="5 4"' if ed else ""
            out.append(f'<g class="brick{" edit" if ed else ""}" data-k="{k}" data-col="{col}"'
                       f'{" tabindex=\"0\" role=\"button\"" if ed else ""} aria-label="row {r + 1}, brick {c + 1}, '
                       f'{NAME[col] if col else ("empty" if ed else "not shown")}">'
                       f'<rect x="{x:.0f}" y="{y:.0f}" width="{BW}" height="{BH}" rx="6" fill="{FILL[col]}" '
                       f'stroke="#33414e" stroke-width="2"{dash}/>'
                       f'<text x="{x + BW / 2:.0f}" y="{y + BH / 2 + 7:.0f}" font-size="20" font-weight="bold" '
                       f'text-anchor="middle" fill="{INK[col]}">{label}</text></g>')
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    import sys
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print(json.dumps({k: v for k, v in asdict(generate(lvl, sd)).items() if k != "svg"}, indent=2, ensure_ascii=False))

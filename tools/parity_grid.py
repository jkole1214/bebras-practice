"""
Problem family: parity_grid (even rows and columns; find what changed).

Concept targets: PARITY_CHECK, ELIMINATION.
Source task: Pantry Map (2022-23 practice; Benjamin B, Cadet A).

Scenario (original wording): a pantry map is a grid of shelves; a dot means
a jar is there. The map was made so every row and every column holds an
EVEN number of dots. Then something happened to the map.

Scene model: {"rows": R, "cols": C, "marks": [[r, c], ...] (what the map
shows now), "editable": [[r, c], ...] (fill level only)}. Rows and columns
are numbered from 0 in data and from 1 on screen.

Question types:
  erased1  one dot was rubbed out: click where it was
  erased2  two dots were rubbed out: click both (a crossing that already has
           a dot cannot be one of them)
  changed  one shelf was changed: a dot rubbed out OR a smudge added: click it
  fill     the last row and column are empty check cells: add dots so every
           row and column is even
"""

import json
import random
from dataclasses import dataclass, field, asdict

LADDER = [
    {"level": 1, "question": "erased1", "size": 5, "density": 0.4, "note": "One dot rubbed out of a small map"},
    {"level": 2, "question": "erased1", "size": 6, "density": 0.5, "note": "One dot rubbed out of a bigger, busier map"},
    {"level": 3, "question": "erased2", "size": 6, "density": 0.45, "note": "Two dots rubbed out (like Pantry Map)"},
    {"level": 4, "question": "changed", "size": 6, "density": 0.45, "note": "One shelf changed: rubbed out or smudged"},
    {"level": 5, "question": "fill", "size": 6, "density": 0.45, "note": "Fill in the check row and column yourself"},
]

MISCONCEPTIONS = {
    "PARITY_ANY_ODD_CELL": {"concept": "PARITY_CHECK",
        "description": "Picks a cell in an odd row without checking that its column is odd too.",
        "remediation": "Ask which rows AND which columns are odd, and look only where they cross."},
    "PARITY_MARKED_CROSSING": {"concept": "PARITY_CHECK",
        "description": "Picks a crossing that already holds a dot, when the question is where a dot was rubbed out.",
        "remediation": "A rubbed-out dot left an empty shelf. Can it be a shelf that still shows a dot?"},
    "PARITY_ROWS_ONLY": {"concept": "PARITY_CHECK",
        "description": "Makes every row even but forgets to check the columns.",
        "remediation": "Now count each column too, including the check row at the bottom."},
    "PARITY_COLS_ONLY": {"concept": "PARITY_CHECK",
        "description": "Makes every column even but forgets to check the rows.",
        "remediation": "Now count each row too, including the check column on the right."},
    "PARITY_CORNER": {"concept": "PARITY_CHECK",
        "description": "Fills the check row and column but gets the shared corner wrong.",
        "remediation": "The corner belongs to both the last row and the last column. Count both."},
}

PROMPT = ("This is a map of pantry shelves. A dot means a jar is on that shelf. "
          "When the map was made, every row and every column had an EVEN number of dots (0, 2, 4, ...).")


def even_grid(rng, R, C, density):
    """Random grid with every row and column even: fill the top-left, then fix the last row and column."""
    g = [[1 if rng.random() < density else 0 for _ in range(C)] for _ in range(R)]
    for r in range(R - 1):
        g[r][C - 1] = sum(g[r][:C - 1]) % 2
    for c in range(C):
        g[R - 1][c] = sum(g[r][c] for r in range(R - 1)) % 2
    return g


def odd_lines(g):
    rows = [r for r, row in enumerate(g) if sum(row) % 2]
    cols = [c for c in range(len(g[0])) if sum(g[r][c] for r in range(len(g))) % 2]
    return rows, cols


def marks(g):
    return [[r, c] for r in range(len(g)) for c in range(len(g[0])) if g[r][c]]


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
    pick: int = 0
    cell_tags: dict = field(default_factory=dict)
    knobs: dict = field(default_factory=dict)


def counts_text(g):
    rows, cols = odd_lines(g)
    rtxt = ", ".join(str(r + 1) for r in rows) or "none"
    ctxt = ", ".join(str(c + 1) for c in cols) or "none"
    return [f"  dots in each row:    " + " ".join(str(sum(row)) for row in g),
            f"  dots in each column: " + " ".join(str(sum(g[r][c] for r in range(len(g)))) for c in range(len(g[0]))),
            f"  odd rows: {rtxt}; odd columns: {ctxt}"]


def single_cell_tags(g, answer_cells, erased):
    rows, cols = odd_lines(g)
    tags = {}
    for r in range(len(g)):
        for c in range(len(g[0])):
            if [r, c] in answer_cells:
                continue
            t = []
            if (r in rows) != (c in cols):
                t.append("PARITY_ANY_ODD_CELL")
            if erased and r in rows and c in cols and g[r][c]:
                t.append("PARITY_MARKED_CROSSING")
            if t:
                tags[f"{r},{c}"] = t
    return tags


def make(rng, cfg, seed):
    R = C = cfg["size"]
    qt = cfg["question"]
    for _ in range(4000):
        full = even_grid(rng, R, C, cfg["density"])
        dots = marks(full)
        if len(dots) < R + 2:
            continue
        common = dict(family="parity_grid", level=cfg["level"], question_type=qt, seed=seed,
                      prompt=PROMPT, options=[], answer_index=-1, distractors=[], value_tags={},
                      concepts=["PARITY_CHECK", "ELIMINATION"], knobs={"size": R})
        if qt == "erased1":
            r, c = rng.choice(dots)
            g = [row[:] for row in full]
            g[r][c] = 0
            return Problem(**common, scene={"rows": R, "cols": C, "marks": marks(g)},
                           question="One dot was rubbed out. Tap the shelf where it was, then check.",
                           answer_value=[[r, c]], entry="cells", pick=1,
                           cell_tags=single_cell_tags(g, [[r, c]], True),
                           explanation=["Count the dots in each row and each column now:"] + counts_text(g)
                                       + [f"The rubbed-out dot was where odd row {r + 1} crosses odd column {c + 1}."],
                           hints=["Count the dots in each row. Which row has an odd number?",
                                  "Now count each column. Which column is odd?",
                                  "The missing dot is where that row and that column cross."])
        if qt == "erased2":
            for _ in range(60):
                a, b = rng.sample(dots, 2)
                if a[0] == b[0] or a[1] == b[1]:
                    continue
                g = [row[:] for row in full]
                g[a[0]][a[1]] = g[b[0]][b[1]] = 0
                other = [[a[0], b[1]], [b[0], a[1]]]
                if not (g[other[0][0]][other[0][1]] or g[other[1][0]][other[1][1]]):
                    continue        # both pairings possible: not unique
                ans = sorted([a, b])
                tags = single_cell_tags(g, ans, True)
                return Problem(**common, scene={"rows": R, "cols": C, "marks": marks(g)},
                               question="Two dots were rubbed out. Tap both shelves where they were, then check.",
                               answer_value=ans, entry="cells", pick=2, cell_tags=tags,
                               explanation=["Count the dots in each row and each column now:"] + counts_text(g)
                                           + [f"Two rows and two columns are odd, so the missing dots are at two of the four crossings, one in each odd row and each odd column.",
                                              f"That leaves two choices of pair. One of them uses a shelf that still shows a dot, so it is the other: "
                                              f"row {a[0] + 1} column {a[1] + 1}, and row {b[0] + 1} column {b[1] + 1}."],
                               hints=["Find the odd rows and the odd columns. How many of each?",
                                      "The missing dots are where odd rows cross odd columns, one per row and one per column.",
                                      "A shelf that still shows a dot cannot be where a dot was rubbed out."])
            continue
        if qt == "changed":
            r, c = rng.randrange(R), rng.randrange(C)
            g = [row[:] for row in full]
            g[r][c] ^= 1
            if g[r][c] == 0 and rng.random() < 0.5:
                continue      # keep added smudges about as common as rubbed-out dots
            what = "a smudge was added" if g[r][c] else "a dot was rubbed out"
            return Problem(**common, scene={"rows": R, "cols": C, "marks": marks(g)},
                           question="Someone changed ONE shelf: either rubbed out a dot or added a smudge that looks like a dot. Tap that shelf, then check.",
                           answer_value=[[r, c]], entry="cells", pick=1, cell_tags=single_cell_tags(g, [[r, c]], False),
                           explanation=["Count the dots in each row and each column now:"] + counts_text(g)
                                       + [f"The changed shelf is where odd row {r + 1} crosses odd column {c + 1}: {what}.",
                                          "Changing one shelf, either way, makes its row and its column odd."],
                           hints=["Find the odd row and the odd column.",
                                  "Adding a dot or taking one away both change a row from even to odd.",
                                  "The changed shelf is where they cross, whether it shows a dot or not."])
        if qt == "fill":
            g = [row[:] for row in full]
            check_cells = [[r, C - 1] for r in range(R)] + [[R - 1, c] for c in range(C - 1)]
            for r, c in check_cells:
                g[r][c] = 0
            ans = sorted([[r, c] for r, c in check_cells if full[r][c]])
            if not ans or full[R - 1][C - 1] == 0 and rng.random() < 0.6:
                continue        # make the corner matter more often
            return Problem(**common, scene={"rows": R, "cols": C, "marks": marks(g), "editable": check_cells},
                           question="The last row and last column are check shelves (dashed). Tap them to add dots so EVERY row and EVERY column is even. Then check.",
                           answer_value=ans, entry="cells", pick=0,
                           explanation=["Fill the check column first: give each row one more dot if it has an odd number.",
                                        "Then fill the check row: count each column, including the check column's new dots.",
                                        "The corner is part of both the last row and the last column; with the rest filled in, both agree.",
                                        "Answer: " + "; ".join(f"row {r + 1} column {c + 1}" for r, c in ans) + "."],
                           hints=["Start with row 1. Is its number of dots odd? Then it needs a dot in the check column.",
                                  "Do the same for each column, using the check row.",
                                  "Last, check the corner: count the last row and the last column."])
    raise RuntimeError(f"generation failed at level {cfg['level']}")


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    return make(random.Random(seed), cfg, seed)


if __name__ == "__main__":
    import sys
    print(json.dumps(asdict(generate(int(sys.argv[1]), int(sys.argv[2]))), indent=1))

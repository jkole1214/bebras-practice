"""
Independent checker for parity_grid problems. Does not import the generator.

For pick questions it tries every possible single change (or pair of
rubbed-out dots) and confirms the answer is the ONLY one that makes every
row and column even. For fill questions it brute-forces the check cells.
It also re-derives the tag of every tagged cell.
"""

import itertools
import json
import sys


def grid(sc):
    g = [[0] * sc["cols"] for _ in range(sc["rows"])]
    for r, c in sc["marks"]:
        g[r][c] = 1
    return g


def all_even(g):
    return all(sum(row) % 2 == 0 for row in g) and all(sum(g[r][c] for r in range(len(g))) % 2 == 0 for c in range(len(g[0])))


def check(p):
    errs = []
    sc, qt = p["scene"], p["question_type"]
    g = grid(sc)
    cells = [(r, c) for r in range(sc["rows"]) for c in range(sc["cols"])]
    if all_even(g) and qt != "fill":
        errs.append("map already all even")
    if qt in ("erased1", "changed"):
        fixes = []
        for r, c in cells:
            if qt == "erased1" and g[r][c]:
                continue
            h = [row[:] for row in g]
            h[r][c] ^= 1
            if all_even(h):
                fixes.append([r, c])
        if fixes != p["answer_value"]:
            errs.append(f"fixes {fixes} != answer {p['answer_value']}")
    elif qt == "erased2":
        empty = [x for x in cells if not g[x[0]][x[1]]]
        fixes = []
        for a, b in itertools.combinations(empty, 2):
            h = [row[:] for row in g]
            h[a[0]][a[1]] = h[b[0]][b[1]] = 1
            if all_even(h):
                fixes.append(sorted([list(a), list(b)]))
        if fixes != [p["answer_value"]]:
            errs.append(f"{len(fixes)} possible pairs, answer {p['answer_value']}")
    elif qt == "fill":
        ed = [tuple(x) for x in sc["editable"]]
        if any(g[r][c] for r, c in ed):
            errs.append("check cells are not empty")
        sols = []
        for bits in itertools.product((0, 1), repeat=len(ed)):
            h = [row[:] for row in g]
            for (r, c), b in zip(ed, bits):
                h[r][c] = b
            if all_even(h):
                sols.append(sorted([list(x) for x, b in zip(ed, bits) if b]))
        if sols != [p["answer_value"]]:
            errs.append(f"{len(sols)} fillings work")
    else:
        errs.append("unknown question type")
    rows = {r for r in range(sc["rows"]) if sum(g[r]) % 2}
    cols = {c for c in range(sc["cols"]) if sum(g[r][c] for r in range(sc["rows"])) % 2}
    for key, tags in p["cell_tags"].items():
        r, c = map(int, key.split(","))
        if [r, c] in p["answer_value"]:
            errs.append("answer cell is tagged as a mistake")
        if "PARITY_ANY_ODD_CELL" in tags and (r in rows) == (c in cols):
            errs.append(f"{key}: not in exactly one odd line")
        if "PARITY_MARKED_CROSSING" in tags and not (g[r][c] and r in rows and c in cols):
            errs.append(f"{key}: not a marked crossing")
    if p["pick"] != (len(p["answer_value"]) if qt != "fill" else 0):
        errs.append("pick count wrong")
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

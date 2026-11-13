"""
Problem family: bubble_passes (Bowl Belt). Folder: bowl-belt.

Concept targets: BUBBLE_SORT, SIMULATION.
Source task: Bowl Factory (Junior C, Senior B, 2015 examples).

Scenario (original): bowls of sizes 1 to N ride in a row on a belt. A worker walks along the
row once, in the direction the arrow shows. At each pair of neighbouring bowls, if the left one
is bigger, the worker swaps them, then steps on to the next pair. The goal is the bowls in order,
smallest on the left. A walk to the right carries the biggest bowl it meets all the way along,
but any other bowl moves at most one place to the left; a walk to the left is the mirror image.

This follows the idea of the source task (one pass of neighbour swaps; how many passes sort a
row); the story, wording, rows and pictures are our own.

One scene model drives both the SVG picture and the solver. The picture carries each bowl
(data-size, data-pos, drawn width and number), the walker arrow (data-dir) and a caption
(data-shows: the row before the workers, or after one worker). The independent checker
rebuilds the row from the picture and solves it again with different code.

Question types:
  after1   which row do you get after one worker? (choice)
  swaps    how many swaps does one worker make? (typed)
  afterk   which row do you get after 2 or 3 workers? (choice)
  workers  how many workers until the bowls are in order? (typed)
  start    the row after one worker is shown: which row did it start as? (choice)

Misconceptions:
  CARRY_STOPS          moves every bowl at most one place, even the one being carried along
  ONE_PASS_SORTS       thinks one worker puts the whole row in order
  PASS_WRONG_WAY       walks the row in the other direction
  ONLY_CARRIED_MOVES   moves the carried bowl to the end and leaves every other bowl where it was
  COUNTS_COMPARISONS   counts the pairs checked, not the swaps made
  SWAPS_FOR_PASSES     counts swaps when asked for workers
  FARTHEST_BOWL        counts how far the bowl furthest from its place must go, even if it moves the fast way
  COUNTS_CHECK_PASS    adds a last worker who only checks that the row is in order
"""

import json
import random
from dataclasses import dataclass, field, asdict
from itertools import permutations

CONCEPTS = {
    "after1": ["BUBBLE_SORT", "SIMULATION"],
    "swaps": ["BUBBLE_SORT", "SIMULATION"],
    "afterk": ["BUBBLE_SORT", "SIMULATION"],
    "workers": ["BUBBLE_SORT", "SIMULATION"],
    "start": ["BUBBLE_SORT", "SIMULATION"],
}

MISCONCEPTIONS = {
    "CARRY_STOPS": {"concept": "BUBBLE_SORT",
        "description": "Moves each bowl at most one place per worker, even the big bowl the worker keeps swapping along, so the carried bowl stops after one swap.",
        "remediation": "Follow one bowl with a finger. After it is swapped, it is in the next pair the worker checks."},
    "ONE_PASS_SORTS": {"concept": "BUBBLE_SORT",
        "description": "Thinks one worker walking along the row puts every bowl in order.",
        "remediation": "Do one walk slowly, pair by pair, and look at the row at the end. Is it in order yet?"},
    "PASS_WRONG_WAY": {"concept": "SIMULATION",
        "description": "Walks the row in the other direction from the one the arrow shows.",
        "remediation": "Find the arrow first and start at the end it points away from."},
    "ONLY_CARRIED_MOVES": {"concept": "SIMULATION",
        "description": "Moves the bowl the worker carries to the end and leaves every other bowl in its old order, forgetting the bowls it passes shift one place.",
        "remediation": "Each swap moves two bowls. Write the whole row again after every swap."},
    "COUNTS_COMPARISONS": {"concept": "BUBBLE_SORT",
        "description": "Counts every pair the worker checks, not only the pairs that are swapped.",
        "remediation": "Mark each pair as swap or keep. Count only the swaps."},
    "FARTHEST_BOWL": {"concept": "BUBBLE_SORT",
        "description": "Counts how far the bowl furthest from its place has to go, even when that bowl moves the fast way and can ride many places in one walk.",
        "remediation": "Ask which way a bowl can move many places in one walk, and which way only one place."},
    "COUNTS_CHECK_PASS": {"concept": "SIMULATION",
        "description": "Adds one more worker at the end who walks the row and finds nothing to swap.",
        "remediation": "Stop counting as soon as the row is in order. Does the last worker you counted change anything?"},
}
# already in the map (from the Bowl Factory analysis); this family is the first to use it
USES_EXISTING = ["SWAPS_FOR_PASSES"]

LADDER = [
    {"level": 1, "question": "after1", "n": 5, "entry": "choice",
     "note": "One worker walks along five bowls: pick the row it leaves. The bowl being carried keeps going."},
    {"level": 2, "question": "swaps", "n": 6, "entry": "number",
     "note": "Six bowls: type how many swaps one worker makes (not how many pairs it checks)."},
    {"level": 3, "question": "afterk", "n": 6, "workers": [2, 3], "entry": "choice",
     "note": "Two or three workers in a row: pick the row they leave. Bowls they pass shift too."},
    {"level": 4, "question": "workers", "n": 7, "entry": "number",
     "note": "Seven bowls: type how many workers it takes to put them in order. The slow bowl sets the count."},
    {"level": 5, "question": "start", "n": 6, "entry": "choice",
     "note": "Work backward: the row after one worker is shown; pick the row it started as."},
]

ORDER = {
    "after1": ["CARRY_STOPS", "ONE_PASS_SORTS", "PASS_WRONG_WAY", "ONLY_CARRIED_MOVES"],
    "swaps": ["COUNTS_COMPARISONS", "ONE_PASS_SORTS", "PASS_WRONG_WAY", "CARRY_STOPS"],
    "afterk": ["ONLY_CARRIED_MOVES", "ONE_PASS_SORTS", "PASS_WRONG_WAY", "CARRY_STOPS"],
    "workers": ["FARTHEST_BOWL", "SWAPS_FOR_PASSES", "COUNTS_CHECK_PASS", "PASS_WRONG_WAY"],
    "start": ["CARRY_STOPS", "PASS_WRONG_WAY", "ONLY_CARRIED_MOVES"],
}

WAY = {"right": "left to right", "left": "right to left"}
OTHER = {"right": "left", "left": "right"}


def prompt(n, d):
    return (f"Bowls of sizes 1 to {n} ride in a row on a belt. A worker walks along the row from {WAY[d]}. "
            f"At each pair of neighbouring bowls, if the left bowl is bigger than the right one, the worker swaps them, "
            f"then steps one bowl {d} to the next pair. The goal is the bowls in order, smallest on the left.")


def show(row):
    return " ".join(map(str, row))


def tagsort(q, tags):
    return sorted(set(tags), key=lambda t: (ORDER[q].index(t), t))


# --------------------------------------------------------------------------
# One worker, and the mistaken versions of one worker
# --------------------------------------------------------------------------

def pairs(n, d):
    return range(n - 1) if d == "right" else range(n - 2, -1, -1)


def walk(row, d, trace=None):
    a = list(row)
    for i in pairs(len(a), d):
        if a[i] > a[i + 1]:
            if trace is not None:
                trace.append((a[i], a[i + 1], True))
            a[i], a[i + 1] = a[i + 1], a[i]
        elif trace is not None:
            trace.append((a[i], a[i + 1], False))
        if trace is not None:
            trace[-1] = trace[-1] + (list(a),)
    return a


def walk_skip(row, d):
    """CARRY_STOPS: a bowl that was just swapped is not checked again on this walk."""
    a, n = list(row), len(row)
    i, step = (0, 1) if d == "right" else (n - 2, -1)
    while 0 <= i <= n - 2:
        if a[i] > a[i + 1]:
            a[i], a[i + 1] = a[i + 1], a[i]
            i += 2 * step
        else:
            i += step
    return a


def carried_only(row, d, k):
    """ONLY_CARRIED_MOVES: after k workers the k biggest (or smallest) bowls are at their end; the rest keep their order."""
    if d == "right":
        big = sorted(row)[-k:]
        return [x for x in row if x not in big] + big
    small = sorted(row)[:k]
    return small + [x for x in row if x not in small]


def walks(row, d, k, f=walk):
    for _ in range(k):
        row = f(row, d)
    return list(row)


def swaps(row, d):
    t = []
    walk(row, d, t)
    return sum(1 for x in t if x[2])


def inversions(row):
    return sum(1 for i in range(len(row)) for j in range(i + 1, len(row)) if row[i] > row[j])


def workers_needed(row, d):
    k = 0
    while list(row) != sorted(row):
        row = walk(row, d)
        k += 1
    return k


def farthest(row):
    return max(abs(i - (x - 1)) for i, x in enumerate(row))


def trace_lines(row, d):
    t = []
    walk(row, d, t)
    lines = [f"  start:      {show(row)}"]
    for a, b, sw, after in t:
        lines.append(f"  {a} > {b} swap: {show(after)}" if sw else f"  {a} < {b} keep")
    return lines


def slow_line(row, d):
    """Which bowl sets the number of workers, and why."""
    n = len(row)
    if d == "right":
        cnt = [sum(1 for y in row[:i] if y > x) for i, x in enumerate(row)]
        i = max(range(n), key=lambda j: (cnt[j], -j))
        return (f"Bowl {row[i]} has {cnt[i]} bigger bowl{'s' if cnt[i] != 1 else ''} to its left. Each worker carries only one of them "
                f"past it, so it needs {cnt[i]} worker{'s' if cnt[i] != 1 else ''}.")
    cnt = [sum(1 for y in row[i + 1:] if y < x) for i, x in enumerate(row)]
    i = max(range(n), key=lambda j: (cnt[j], j))
    return (f"Bowl {row[i]} has {cnt[i]} smaller bowl{'s' if cnt[i] != 1 else ''} to its right. Each worker carries only one of them "
            f"past it, so it needs {cnt[i]} worker{'s' if cnt[i] != 1 else ''}.")


# --------------------------------------------------------------------------
# Question makers
# --------------------------------------------------------------------------

def choose_options(rng, q, truth, wrong):
    """wrong: tag -> row. Merge equal rows, keep the three wrong rows whose first tag comes first."""
    if any(v == truth for v in wrong.values()):
        return None
    tagged = {}
    for tag, v in wrong.items():
        tagged.setdefault(tuple(v), []).append(tag)
    picks = sorted(tagged, key=lambda v: ORDER[q].index(tagsort(q, tagged[v])[0]))[:3]
    if len(picks) < 3 or ORDER[q][0] not in {t for v in picks for t in tagged[v]}:
        return None
    opts = [list(v) for v in picks] + [list(truth)]
    rng.shuffle(opts)
    return opts, opts.index(list(truth)), [{"option": o, "misconceptions": tagsort(q, tagged[tuple(o)])} for o in opts if o != list(truth)]


def problem(cfg, q, seed, scene, svg, question, **kw):
    return Problem(family="bubble_passes", level=cfg["level"], question_type=q, seed=seed, scene=scene, svg=svg,
                   prompt=prompt(cfg["n"], scene["dir"]), question=question, concepts=CONCEPTS[q], **kw)


def make_after1(rng, cfg, seed):
    n = cfg["n"]
    for _ in range(500):
        d = rng.choice(["right", "left"])
        row = rng.sample(range(1, n + 1), n)
        truth = walk(row, d)
        if truth == sorted(row) or row == truth:
            continue
        wrong = {"CARRY_STOPS": walk_skip(row, d), "ONE_PASS_SORTS": sorted(row),
                 "PASS_WRONG_WAY": walk(row, OTHER[d]), "ONLY_CARRIED_MOVES": carried_only(row, d, 1)}
        got = choose_options(rng, "after1", truth, wrong)
        if not got:
            continue
        opts, a, dis = got
        end = "right" if d == "right" else "left"
        ext = n if d == "right" else 1
        expl = [f"The worker starts at the {OTHER[d]} end and checks each pair in turn:"] + trace_lines(row, d)
        expl.append(f"Bowl {ext} always ends at the {end} end: once the worker meets it, it is swapped along every pair after that.")
        expl.append(f"Every other bowl moves at most one place to the {OTHER[d]}.")
        expl.append(f"So the row becomes {show(truth)}.")
        return problem(cfg, "after1", seed, {"row": row, "dir": d}, render(row, d, "start", seed),
                       "What does the row look like after the worker has walked along it once?",
                       options=opts, answer_index=a, answer_value=truth, entry="choice", distractors=dis, value_tags={},
                       explanation=expl,
                       hints=[f"Start at the {OTHER[d]} end and check one pair at a time.",
                              "After a swap, the bowl that moved is part of the next pair. Keep following it.",
                              "Write the whole row again after each swap."],
                       knobs={"n": n, "dir": d})
    return None


def make_swaps(rng, cfg, seed):
    n = cfg["n"]
    for _ in range(500):
        d = rng.choice(["right", "left"])
        row = rng.sample(range(1, n + 1), n)
        truth = swaps(row, d)
        if truth < 2:
            continue
        cnt = 0
        # CARRY_STOPS: the swaps a student makes who stops each carried bowl after one place
        a, i, step = list(row), (0 if d == "right" else n - 2), (1 if d == "right" else -1)
        while 0 <= i <= n - 2:
            if a[i] > a[i + 1]:
                a[i], a[i + 1] = a[i + 1], a[i]
                cnt += 1
                i += 2 * step
            else:
                i += step
        wrong = {"COUNTS_COMPARISONS": n - 1, "ONE_PASS_SORTS": inversions(row),
                 "PASS_WRONG_WAY": swaps(row, OTHER[d]), "CARRY_STOPS": cnt}
        if any(v == truth for v in wrong.values()):
            continue
        vt = {}
        for tag, v in wrong.items():
            vt.setdefault(v, []).append(tag)
        if len(vt) < 3:
            continue
        expl = [f"The worker starts at the {OTHER[d]} end and checks each pair in turn:"] + trace_lines(row, d)
        expl.append(f"The worker checks {n - 1} pairs but swaps only the ones out of order.")
        expl.append(f"So the worker makes {truth} swaps.")
        return problem(cfg, "swaps", seed, {"row": row, "dir": d}, render(row, d, "start", seed),
                       "How many swaps does the worker make on one walk along the row?",
                       options=[], answer_index=-1, answer_value=truth, entry="number", distractors=[],
                       value_tags={str(v): tagsort("swaps", t) for v, t in sorted(vt.items())},
                       explanation=expl,
                       hints=[f"Start at the {OTHER[d]} end. For each pair, say 'swap' or 'keep'.",
                              "A swap changes the row, so check the next pair in the new row.",
                              "Count only the swaps, not every pair."],
                       knobs={"n": n, "dir": d})
    return None


def make_afterk(rng, cfg, seed):
    n = cfg["n"]
    for _ in range(800):
        d = rng.choice(["right", "left"])
        k = rng.choice(cfg["workers"])
        row = rng.sample(range(1, n + 1), n)
        steps = [row]
        for _ in range(k):
            steps.append(walk(steps[-1], d))
        truth = steps[-1]
        if truth == sorted(row) or steps[-2] == truth:
            continue
        wrong = {"ONLY_CARRIED_MOVES": carried_only(row, d, k), "ONE_PASS_SORTS": sorted(row),
                 "PASS_WRONG_WAY": walks(row, OTHER[d], k), "CARRY_STOPS": walks(row, d, k, walk_skip)}
        got = choose_options(rng, "afterk", truth, wrong)
        if not got:
            continue
        opts, a, dis = got
        kind = "biggest" if d == "right" else "smallest"
        expl = [f"Walk the row once for each worker, starting at the {OTHER[d]} end each time:"]
        expl.append(f"  start:    {show(row)}")
        for i in range(1, k + 1):
            expl.append(f"  worker {i}: {show(steps[i])}")
        expl.append(f"Each worker carries the {kind} bowl it meets to its place, and every bowl it passes shifts one place.")
        expl.append(f"So after {k} workers the row is {show(truth)}.")
        return problem(cfg, "afterk", seed, {"row": row, "dir": d, "workers": k}, render(row, d, "start", seed),
                       f"{k} workers walk along the row one after another, each doing the same thing. What does the row look like after all {k}?",
                       options=opts, answer_index=a, answer_value=truth, entry="choice", distractors=dis, value_tags={},
                       explanation=expl,
                       hints=["Do one worker at a time, and write the row down after each one.",
                              "When the worker swaps a bowl along, the bowls it passes each move one place the other way.",
                              f"Each worker starts again at the {OTHER[d]} end."],
                       knobs={"n": n, "dir": d, "workers": k})
    return None


def make_workers(rng, cfg, seed):
    n = cfg["n"]
    for _ in range(2000):
        d = rng.choice(["right", "left"])
        row = rng.sample(range(1, n + 1), n)
        truth = workers_needed(row, d)
        if not 2 <= truth <= n - 2:
            continue
        wrong = {"FARTHEST_BOWL": farthest(row), "SWAPS_FOR_PASSES": inversions(row),
                 "COUNTS_CHECK_PASS": truth + 1, "PASS_WRONG_WAY": workers_needed(row, OTHER[d])}
        if any(v == truth for v in wrong.values()):
            continue
        if wrong["FARTHEST_BOWL"] < truth:
            continue          # the farthest bowl must be one that rides the fast way
        vt = {}
        for tag, v in wrong.items():
            vt.setdefault(v, []).append(tag)
        if len(vt) < 3:
            continue
        expl = [f"Walk the row once for each worker, starting at the {OTHER[d]} end each time:", f"  start:    {show(row)}"]
        r, i = row, 0
        while r != sorted(row):
            r = walk(r, d)
            i += 1
            expl.append(f"  worker {i}: {show(r)}")
        expl.append(slow_line(row, d))
        far = max(range(n), key=lambda j: abs(j - (row[j] - 1)))
        expl.append(f"Bowl {row[far]} is farthest from its place ({farthest(row)} places), but it moves to the {d}, "
                    f"the way the workers carry bowls, so it can ride many places on one walk.")
        expl.append(f"So {truth} workers are needed.")
        return problem(cfg, "workers", seed, {"row": row, "dir": d}, render(row, d, "start", seed),
                       "Workers walk along the row one after another until the bowls are in order. How many workers does it take?",
                       options=[], answer_index=-1, answer_value=truth, entry="number", distractors=[],
                       value_tags={str(v): tagsort("workers", t) for v, t in sorted(vt.items())},
                       explanation=expl,
                       hints=[f"Which way can a bowl ride many places in one walk? Which way can it move only one place?",
                              f"Look for a bowl that has to travel to the {OTHER[d]}. How many places can it move per worker?",
                              "Or walk the row worker by worker, and stop as soon as it is in order."],
                       knobs={"n": n, "dir": d})
    return None


def make_start(rng, cfg, seed):
    n = cfg["n"]
    perms = [list(p) for p in permutations(range(1, n + 1))]
    for _ in range(400):
        d = rng.choice(["right", "left"])
        start = rng.choice(perms)
        after = walk(start, d)
        if after == sorted(after) or inversions(start) < 4:
            continue
        models = {"CARRY_STOPS": lambda r: walk_skip(r, d), "PASS_WRONG_WAY": lambda r: walk(r, OTHER[d]),
                  "ONLY_CARRIED_MOVES": lambda r: carried_only(r, d, 1)}
        if any(f(start) == after for f in models.values()):
            continue          # a habit must not lead to the right row
        cands = {}
        for tag, f in models.items():
            pool = [p for p in perms if f(p) == after and walk(p, d) != after]
            if not pool:
                break
            cands[tag] = rng.choice(pool)
        if len(cands) < 3:
            continue
        rows = [cands[t] for t in ORDER["start"]]
        if len({tuple(r) for r in rows}) < 3:
            continue
        tagged = {tuple(r): [t for t, f in models.items() if f(r) == after] for r in rows}
        opts = rows + [start]
        rng.shuffle(opts)
        a = opts.index(start)
        expl = [f"Try each row with one worker walking from {WAY[d]}:"]
        for o in opts:
            expl.append(f"  {show(o)} → {show(walk(o, d))}{' ✓' if o == start else ''}")
        expl.append(f"Only {show(start)} becomes {show(after)}.")
        expl.append(f"So the row started as {show(start)}.")
        return problem(cfg, "start", seed, {"after": after, "dir": d}, render(after, d, "after1", seed),
                       "The picture shows the row after one worker walked along it. Which row did the worker start with?",
                       options=opts, answer_index=a, answer_value=start, entry="choice",
                       distractors=[{"option": o, "misconceptions": tagsort("start", tagged[tuple(o)])} for o in opts if o != start],
                       value_tags={}, explanation=expl,
                       hints=["You don't have to work backward. Try each row forward with one worker.",
                              f"Start each try at the {OTHER[d]} end, and keep following a bowl after it is swapped.",
                              "Only one row turns into the row in the picture."],
                       knobs={"n": n, "dir": d})
    return None


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


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    rng = random.Random(seed)
    make = {"after1": make_after1, "swaps": make_swaps, "afterk": make_afterk,
            "workers": make_workers, "start": make_start}[cfg["question"]]
    p = make(rng, cfg, seed)
    if not p:
        raise RuntimeError(f"bubble_passes generation failed at level {level}")
    return p


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

FONT = 'font-family="Helvetica, Arial, sans-serif"'
COLOURS = ["#e07a5f", "#f2cc8f", "#81b29a", "#6d9dc5", "#b388c9", "#e9a3b4", "#c9a66b"]
CAPTION = {"start": "The row before the workers", "after1": "The row after one worker"}


def bowl_width(s):
    return 20 + 4 * s


def render(row, d, shows, seed):
    n = len(row)
    W, H = 420, 176
    slot = (W - 40) / n
    base = 104
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" {FONT} '
           f'class="bowls" data-family="bubble_passes" data-seed="{seed}">',
           f'<rect x="0" y="0" width="{W}" height="{H}" rx="10" fill="#f4efe6"/>',
           f'<text class="caption" data-shows="{shows}" x="{W / 2}" y="26" font-size="14" font-weight="bold" '
           f'text-anchor="middle" fill="#1f2933">{CAPTION[shows]}</text>']
    out.append(f'<rect x="14" y="{base + 2}" width="{W - 28}" height="14" rx="7" fill="#5b6770"/>')
    for i in range(9):
        out.append(f'<circle cx="{30 + i * (W - 60) / 8:.1f}" cy="{base + 9}" r="4" fill="#9aa5b1"/>')
    for i, s in enumerate(row):
        cx = 20 + slot * (i + .5)
        w, h = bowl_width(s), 10 + 3 * s
        l, r = cx - w / 2, cx + w / 2
        top = base - h
        out.append(f'<g class="bowl" data-size="{s}" data-pos="{i}">'
                   f'<path d="M{l:.1f},{top:.1f} L{r:.1f},{top:.1f} Q{cx:.1f},{2 * base - top:.1f} {l:.1f},{top:.1f} Z" '
                   f'fill="{COLOURS[(s - 1) % len(COLOURS)]}" stroke="#3d405b" stroke-width="2"/>'
                   f'<text x="{cx:.1f}" y="{top - 6:.1f}" font-size="15" font-weight="bold" text-anchor="middle" fill="#1f2933">{s}</text></g>')
    y = 146
    x1, x2 = (60, W - 60) if d == "right" else (W - 60, 60)
    head = x2 - 12 if d == "right" else x2 + 12
    out.append(f'<g class="walker" data-dir="{d}">'
               f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" stroke="#1f2933" stroke-width="3" stroke-linecap="round"/>'
               f'<path d="M{x2},{y} L{head},{y - 7} L{head},{y + 7} Z" fill="#1f2933"/>'
               f'<text x="{W / 2}" y="{y + 22}" font-size="13" text-anchor="middle" fill="#1f2933">The worker walks this way</text></g>')
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    import sys
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print(json.dumps({k: v for k, v in asdict(generate(lvl, sd)).items() if k != "svg"}, indent=2, ensure_ascii=False))

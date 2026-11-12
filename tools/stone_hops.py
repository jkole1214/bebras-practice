"""
Problem family: stone_hops (Frog Hops). Folder: frog-hops.

Concept targets: BACKTRACKING, STATE_SEARCH.
Source task: Kangaroo (Senior C).

Scenario (original): a frog crosses a row of stepping stones. Every hop is exactly a spots
forward or exactly b spots back, must land on a stone (some spots are water), and never lands
on the same stone twice. The frog has to land on every stone. Most starts force the first few
hops; at a choice, one branch dead-ends, so the student must try a branch and back up.

This follows the idea of a jump-tour task (the source uses a different animal, plates and
lettered positions); the story, wording, rules and pictures are our own, and the water gaps are
our addition.

One scene model (spots, stones, the two hop sizes, the start) drives both the SVG picture and
the solver. The picture carries each spot (data-n, stone or water), the frog (data-at) and the
rule (data-fwd, data-back); the independent checker rebuilds the row from the SVG and searches
again.

Question types:
  check  which list of stones is a trip that follows the rules? (choice; level 1)
  last   which stone does the frog land on last? (choice; levels 2 and 4)
  tour   tap the stones in order (entry "hops", graded by playing the trip back; levels 3 and 5)

Misconceptions:
  STOPS_AT_DEAD_END     follows one branch until stuck and stops there, without backing up
  FAR_END_IS_LAST       assumes the frog finishes on the stone at the far right
  HOPS_WRONG_SIZE       makes a hop that is not one of the two allowed sizes
  SWAPS_HOP_DIRECTIONS  hops forward by the back size and back by the forward size
  LANDS_TWICE           lands on a stone it has already visited
"""

import json
import random
from itertools import combinations
from dataclasses import dataclass, field, asdict

CONCEPTS = ["BACKTRACKING", "STATE_SEARCH"]

MISCONCEPTIONS = {
    "STOPS_AT_DEAD_END": {"concept": "BACKTRACKING",
        "description": "Follows one choice of hop until the frog is stuck and stops there, instead of going back to the last choice and trying the other hop.",
        "remediation": "When the frog gets stuck with stones left, go back to the last stone where it had two hops and try the other one."},
    "FAR_END_IS_LAST": {"concept": "STATE_SEARCH",
        "description": "Assumes the frog must finish on the stone at the far end of the row.",
        "remediation": "Follow the hops one at a time and see where the frog really stops."},
    "HOPS_WRONG_SIZE": {"concept": "STATE_SEARCH",
        "description": "Makes a hop that is not one of the two allowed sizes, often one spot too short or too long.",
        "remediation": "Count the spots on every hop, water spots included, before moving on."},
    "SWAPS_HOP_DIRECTIONS": {"concept": "STATE_SEARCH",
        "description": "Mixes up the two hops: goes forward by the back size and back by the forward size.",
        "remediation": "Write the rule as two arrows (forward a, back b) and check each hop against it."},
    "LANDS_TWICE": {"concept": "STATE_SEARCH",
        "description": "Lets the frog land on a stone it has already visited.",
        "remediation": "Cross off each stone as the frog lands on it; a crossed-off stone cannot be used again."},
}

LADDER = [
    {"level": 1, "question": "check", "spots": [6, 7], "water": [0], "hop": 3, "choices": 0,
     "note": "Which list of stones follows the hop rule and lands on every stone? Six or seven stones."},
    {"level": 2, "question": "last", "spots": [7, 8, 9], "water": [0, 1, 2], "hop": 4, "choices": 1,
     "note": "Which stone does the frog land on last? It is not always the far end."},
    {"level": 3, "question": "tour", "spots": [8, 9], "water": [0, 1, 2], "hop": 4, "choices": 1,
     "note": "Tap the frog's whole trip. Back up when a choice gets stuck."},
    {"level": 4, "question": "last", "spots": [10, 11], "water": [1, 2, 3], "hop": 5, "choices": 1,
     "note": "Which stone is last? Ten or eleven spots, water gaps and longer hops."},
    {"level": 5, "question": "tour", "spots": [10, 11], "water": [1, 2, 3], "hop": 5, "choices": 2,
     "note": "Tap the whole trip on a longer row, with at least two choices to back out of."},
]

# --------------------------------------------------------------------------
# Search (stones: sorted list of spot numbers that hold a stone)
# --------------------------------------------------------------------------

def moves(stones, a, b, x):
    return [y for y in (x + a, x - b) if y in stones]


def tours(stones, a, b, s):
    out, k = [], len(stones)

    def dfs(p, seen):
        if len(p) == k:
            out.append(p[:])
            return
        for y in moves(stones, a, b, p[-1]):
            if y not in seen:
                p.append(y)
                seen.add(y)
                dfs(p, seen)
                seen.discard(y)
                p.pop()
    dfs([s], {s})
    return out


def longest(stones, a, b, path):
    """The longest trip that continues path (ties: the first found, trying forward first)."""
    best = path[:]

    def dfs(p, seen):
        nonlocal best
        if len(p) > len(best):
            best = p[:]
        for y in moves(stones, a, b, p[-1]):
            if y not in seen:
                p.append(y)
                seen.add(y)
                dfs(p, seen)
                seen.discard(y)
                p.pop()
    dfs(path[:], set(path))
    return best


def greedy(stones, a, b, s, forward_first):
    """Take the preferred hop whenever it lands on a fresh stone, else the other one, until stuck."""
    p, seen = [s], {s}
    while True:
        opts = [y for y in moves(stones, a, b, p[-1]) if y not in seen]
        if not opts:
            return p
        y = opts[0] if forward_first or len(opts) == 1 else opts[1]
        p.append(y)
        seen.add(y)


def choice_points(stones, a, b, tour):
    return [i for i in range(len(tour) - 1)
            if len([y for y in moves(stones, a, b, tour[i]) if y not in tour[:i + 1]]) == 2]


def seq_tags(stones, a, b, seq):
    """What is wrong with a list of stones that should be a trip (target tag first)."""
    tags = []
    hops = list(zip(seq, seq[1:]))
    if any(y - x not in (a, -b) for x, y in hops):
        tags.append("SWAPS_HOP_DIRECTIONS" if all(y - x in (b, -a) for x, y in hops) else "HOPS_WRONG_SIZE")
    if len(set(seq)) < len(seq):
        tags.append("LANDS_TWICE")
    return tags


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


def arrow(p):
    return " → ".join(str(x) for x in p)


def join(xs):
    xs = [str(x) for x in xs]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def spots_word(k):
    return f"{k} spot{'' if k == 1 else 's'}"


def prompt_for(sc):
    water = sorted(set(range(1, sc["spots"] + 1)) - set(sc["stones"]))
    wtxt = (f" Spot{'s' if len(water) > 1 else ''} {join(water)} {'are' if len(water) > 1 else 'is'} water, with no stone."
            if water else "")
    return (f"A row of stepping stones crosses a pond. The spots are numbered from 1 on the left.{wtxt} "
            f"The frog starts on stone {sc['start']}. Every hop goes exactly {spots_word(sc['fwd'])} forward (right) "
            f"or exactly {spots_word(sc['back'])} back (left), and must land on a stone. "
            f"The frog never lands on the same stone twice.")


def story(stones, a, b, tour):
    """How the search finds the trip: forced runs, and each choice with the branch that dead-ends."""
    lines, run = [], [tour[0]]

    def flush():
        if len(run) > 1:
            lines.append(f"From stone {run[0]}, each hop is forced: {arrow(run)}.")
    for i in range(len(tour) - 1):
        x = tour[i]
        opts = [y for y in moves(stones, a, b, x) if y not in tour[:i + 1]]
        if len(opts) == 1:
            run.append(tour[i + 1])
            continue
        flush()
        alt = opts[0] if opts[1] == tour[i + 1] else opts[1]
        dead = longest(stones, a, b, tour[:i + 1] + [alt])
        left = [y for y in stones if y not in dead]
        lines.append(f"At stone {x} the frog can hop to {opts[0]} or {opts[1]}. Every trip through {alt} gets stuck. "
                     f"The longest, {arrow(dead[i:])}, never reaches stone{'s' if len(left) > 1 else ''} {join(left)}. "
                     f"So the frog hops to {tour[i + 1]}.")
        run = [tour[i + 1]]
    flush()
    return lines


def fits(cfg, sc, tour):
    """Checks that need no random choices; the make_* functions do the rest."""
    stones, a, b, s = sc["stones"], sc["fwd"], sc["back"], sc["start"]
    hops = [y - x for x, y in zip(tour, tour[1:])]
    if a not in hops or -b not in hops:
        return False                          # a trip in one direction only is just counting along
    if cfg["question"] == "tour":
        return any(len(greedy(stones, a, b, s, f)) < len(stones) for f in (True, False))
    if cfg["question"] == "last":
        if s == max(stones):
            return False
        traps = last_traps(stones, a, b, s, tour[-1])
        opts = sorted(list(traps) + [tour[-1]])
        return (tour[-1] not in traps and any("STOPS_AT_DEAD_END" in t for t in traps.values())
                and tour[-1] not in (min(opts), max(opts)))
    return True


_CATALOGUE = {}


def catalogue(level):
    """Every row, rule and start for this level with exactly one trip, in a fixed shuffled order.
    The space is small (tens of puzzles per level), so seeds index into it instead of sampling,
    which keeps nearby seeds from repeating a puzzle."""
    if level not in _CATALOGUE:
        cfg = next(c for c in LADDER if c["level"] == level)
        h, out = cfg["hop"], []
        for m in cfg["spots"]:
            for w in cfg["water"]:
                for water in combinations(range(2, m), w):
                    stones = [x for x in range(1, m + 1) if x not in water]
                    for a in range(1, h + 1):
                        for b in range(1, h + 1):
                            if a == b:
                                continue
                            for s in stones:
                                ts = tours(stones, a, b, s)
                                if len(ts) != 1 or len(choice_points(stones, a, b, ts[0])) < cfg["choices"]:
                                    continue
                                sc = {"spots": m, "stones": stones, "fwd": a, "back": b, "start": s}
                                if fits(cfg, sc, ts[0]):
                                    out.append((sc, ts[0]))
        random.Random(f"stone_hops-{level}").shuffle(out)
        _CATALOGUE[level] = out
    return _CATALOGUE[level]


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    items = catalogue(level)
    rng = random.Random(seed)
    make = {"check": make_check, "last": make_last, "tour": make_tour}[cfg["question"]]
    for i in range(len(items)):
        sc, tour = items[(seed + i) % len(items)]
        p = make(rng, cfg, seed, dict(sc), tour)
        if p:
            return p
    raise RuntimeError(f"stone_hops generation failed at level {level}")


HINTS_SEARCH = [
    "From the start, which hops land on a stone? If there is only one, the frog must take it.",
    "When the frog has two hops, try one. If it gets stuck with stones left, go back and try the other.",
    "Stones at the ends and next to water have few ways in or out. Make sure the trip can still reach them.",
]


def base(cfg, seed, sc, qtype, question, tour, **kw):
    a, b = sc["fwd"], sc["back"]
    return Problem(family="stone_hops", level=cfg["level"], question_type=qtype, seed=seed, scene=sc,
                   svg=render_svg(sc, seed), prompt=prompt_for(sc), question=question,
                   concepts=CONCEPTS, knobs={"spots": sc["spots"], "stones": len(sc["stones"]), "fwd": a, "back": b,
                                             "choices": len(choice_points(sc["stones"], a, b, tour))}, **kw)


def wrong_size_lists(stones, a, b, s, rng):
    """Every-stone lists from s with exactly one hop of a wrong size, preferring hops one spot off."""
    out, k = [], len(stones)

    def dfs(p, seen, bad):
        if len(out) >= 400:
            return
        if len(p) == k:
            if bad:
                out.append(p[:])
            return
        for y in stones:
            if y in seen:
                continue
            ok = y - p[-1] in (a, -b)
            if not ok and bad:
                continue
            p.append(y)
            seen.add(y)
            dfs(p, seen, bad or not ok)
            seen.discard(y)
            p.pop()
    dfs([s], {s}, False)
    out = [p for p in out if seq_tags(stones, a, b, p) == ["HOPS_WRONG_SIZE"]]

    def near(p):
        d = [y - x for x, y in zip(p, p[1:]) if y - x not in (a, -b)][0]
        return abs(d - a) == 1 if d > 0 else abs(-d - b) == 1
    close = [p for p in out if near(p)]
    return close or out


def twice_lists(stones, a, b, s, rng):
    out = []
    for _ in range(300):
        p = [s]
        while len(p) < len(stones):
            opts = moves(stones, a, b, p[-1])
            if not opts:
                break
            p.append(rng.choice(opts))
        if len(p) == len(stones) and seq_tags(stones, a, b, p) == ["LANDS_TWICE"] and p not in out:
            out.append(p)
    return out


def make_check(rng, cfg, seed, sc, tour):
    stones, a, b, s = sc["stones"], sc["fwd"], sc["back"], sc["start"]
    sizes = wrong_size_lists(stones, a, b, s, rng)
    twice = twice_lists(stones, a, b, s, rng)
    swaps = [t for t in tours(stones, b, a, s) if seq_tags(stones, a, b, t) == ["SWAPS_HOP_DIRECTIONS"]]
    if not sizes or not twice:
        return None
    pick = [rng.choice(sizes), rng.choice(twice)]
    if swaps:
        pick.append(rng.choice(swaps))
    else:
        more = [p for p in sizes + twice if p not in pick]
        if not more:
            return None
        pick.append(rng.choice(more))
    opts = pick + [tour]
    rng.shuffle(opts)
    expl = []
    for o in opts:
        if o == tour:
            continue
        t = seq_tags(stones, a, b, o)
        if t[0] == "LANDS_TWICE":
            d = next(x for i, x in enumerate(o) if x in o[:i])
            expl.append(f"{arrow(o)}: lands on stone {d} twice.")
        else:
            x, y = next((x, y) for x, y in zip(o, o[1:]) if y - x not in (a, -b))
            how = f"{y - x} forward" if y > x else f"{x - y} back"
            extra = " (the forward and back sizes are swapped)" if t[0] == "SWAPS_HOP_DIRECTIONS" else ""
            expl.append(f"{arrow(o)}: the hop from {x} to {y} is {how}, which is not allowed{extra}.")
    expl.append(f"{arrow(tour)}: every hop is {a} forward or {b} back, and each stone is visited once.")
    expl.append(f"So the right list is {arrow(tour)}.")
    return base(cfg, seed, sc, "check", "Which list shows a trip that follows the rules and lands on every stone?", tour,
                options=opts, answer_index=opts.index(tour), answer_value=tour, entry="choice",
                distractors=[{"option": o, "misconceptions": seq_tags(stones, a, b, o)} for o in opts if o != tour],
                value_tags={}, explanation=expl,
                hints=[f"Check each list one hop at a time. Is every hop exactly {a} forward or {b} back?",
                       "Does any stone appear twice? Is every stone in the list once?",
                       "Only one list passes every check."])


def last_traps(stones, a, b, s, truth):
    """Stone -> tags a student with each habit would give for the last stone."""
    k, traps = len(stones), {}
    traps.setdefault(max(stones), []).append("FAR_END_IS_LAST")
    for fwd in (True, False):
        g = greedy(stones, a, b, s, fwd)
        if len(g) < k and "STOPS_AT_DEAD_END" not in traps.get(g[-1], []):
            traps.setdefault(g[-1], []).append("STOPS_AT_DEAD_END")
    sw = {t[-1] for t in tours(stones, b, a, s)}
    if len(sw) == 1:
        traps.setdefault(sw.pop(), []).append("SWAPS_HOP_DIRECTIONS")
    return traps


def make_last(rng, cfg, seed, sc, tour):
    stones, a, b, s = sc["stones"], sc["fwd"], sc["back"], sc["start"]
    truth = tour[-1]
    if s == max(stones):
        return None
    traps = last_traps(stones, a, b, s, truth)
    if truth in traps:
        return None                           # a habit would give the right stone
    if not any("STOPS_AT_DEAD_END" in t for t in traps.values()):
        return None
    opts = sorted(list(traps) + [truth])
    if truth in (min(opts), max(opts)):
        return None
    g = next(greedy(stones, a, b, s, f) for f in (True, False) if len(greedy(stones, a, b, s, f)) < len(stones))
    expl = story(stones, a, b, tour)
    expl.append(f"The trip is {arrow(tour)}. It does not end at stone {max(stones)}, the far end.")
    expl.append(f"Just taking hops until stuck can end early: {arrow(g)} misses "
                f"{join([y for y in stones if y not in g])}.")
    expl.append(f"So the frog lands on stone {truth} last.")
    tags_order = ("STOPS_AT_DEAD_END", "FAR_END_IS_LAST", "SWAPS_HOP_DIRECTIONS")
    return base(cfg, seed, sc, "last", "The frog lands on every stone. Which stone does it land on last?", tour,
                options=opts, answer_index=opts.index(truth), answer_value=truth, entry="choice",
                distractors=[{"option": o, "misconceptions": sorted(traps[o], key=tags_order.index)} for o in opts if o != truth],
                value_tags={}, explanation=expl, hints=HINTS_SEARCH)


def make_tour(rng, cfg, seed, sc, tour):
    stones, a, b, s = sc["stones"], sc["fwd"], sc["back"], sc["start"]
    if all(len(greedy(stones, a, b, s, f)) == len(stones) for f in (True, False)):
        return None
    expl = story(stones, a, b, tour) + [f"So the frog's trip is {arrow(tour)}."]
    return base(cfg, seed, sc, "tour", "Tap the stones in the order the frog lands on them, so that it lands on every stone.", tour,
                options=[], answer_index=-1, answer_value=tour, entry="hops", distractors=[], value_tags={},
                explanation=expl, hints=HINTS_SEARCH)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

GAP, LEFT, ROW, R = 36, 32, 98, 15


MIN_W = 360


def render_svg(sc, seed):
    m = sc["spots"]
    span = GAP * (m - 1)
    W, H = max(span + 2 * LEFT, MIN_W), 186
    x0 = (W - span) / 2                       # short rows are centred, so the rule line always fits

    def spot_x(n):
        return x0 + GAP * (n - 1)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="Helvetica, Arial, sans-serif" class="hops" data-family="stone_hops" data-seed="{seed}">',
           f'<rect x="0" y="0" width="{W}" height="{H}" rx="10" fill="#d6ebf5"/>',
           '<g class="hoplayer"></g>']
    for n in range(1, m + 1):
        x = spot_x(n)
        if n in sc["stones"]:
            out.append(f'<g class="spot stone" data-n="{n}" aria-label="stone {n}">'
                       f'<circle cx="{x}" cy="{ROW}" r="{R}" fill="#c3c9cf" stroke="#4a5563" stroke-width="2"/>'
                       f'<text x="{x}" y="{ROW + 5.5}" font-size="15" font-weight="bold" text-anchor="middle" fill="#1f2933">{n}</text></g>')
        else:
            out.append(f'<g class="spot water" data-n="{n}" aria-label="spot {n}, water">'
                       f'<circle cx="{x}" cy="{ROW}" r="{R}" fill="none" stroke="#7fb3cf" stroke-width="1.5" stroke-dasharray="3 3"/>'
                       f'<text x="{x}" y="{ROW + 5}" font-size="13" text-anchor="middle" fill="#5f8fa8">{n}</text></g>')
    fx = spot_x(sc["start"])
    out.append(f'<g class="frog" data-at="{sc["start"]}" aria-label="the frog, on stone {sc["start"]}">'
               f'<ellipse cx="{fx}" cy="{ROW - 30}" rx="13" ry="9" fill="#3f9b4f" stroke="#245c2e" stroke-width="1.5"/>'
               f'<circle cx="{fx - 6}" cy="{ROW - 39}" r="4" fill="#ffffff" stroke="#245c2e" stroke-width="1.5"/>'
               f'<circle cx="{fx + 6}" cy="{ROW - 39}" r="4" fill="#ffffff" stroke="#245c2e" stroke-width="1.5"/>'
               f'<circle cx="{fx - 6}" cy="{ROW - 39}" r="1.6" fill="#1f2933"/>'
               f'<circle cx="{fx + 6}" cy="{ROW - 39}" r="1.6" fill="#1f2933"/></g>')
    out.append(f'<g class="rule" data-fwd="{sc["fwd"]}" data-back="{sc["back"]}">'
               f'<text x="{W / 2:.0f}" y="{H - 14}" font-size="15" text-anchor="middle" fill="#1f2933">'
               f'Each hop: {spots_word(sc["fwd"])} forward or {spots_word(sc["back"])} back</text></g>')
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    import sys
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print(json.dumps({k: v for k, v in asdict(generate(lvl, sd)).items() if k != "svg"}, indent=2, ensure_ascii=False))

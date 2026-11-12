"""
Problem family: parallel_spread (Paint Pipes). Folder: paint-pipes.

Concept targets: PARALLEL_SPREAD, SIMULATION, GRAPH_NEIGHBORHOOD.

Scenario (original): tanks are joined by pipes. Orange paint is poured into one
tank (and, from level 2, blue paint into another). Every minute each orange or
blue tank pushes its colour through all of its pipes, all at the same moment,
using the colour it had when the minute began. A tank that holds both colours,
even one that already had a colour, turns to mud, and mud never flows.

This follows the idea of a two-source spreading task (synchronous multi-source
BFS where meeting points become walls); the wording, theme and pictures are our own.

One scene model (tanks with coordinates, pipes, starting tanks) drives both the
SVG picture and the solver. The picture carries the scene in data-* attributes;
the independent checker rebuilds the network from the SVG and simulates again.

Question types:
  after:  one colour; how many tanks have paint after k minutes? (choice)
  final:  two colours; when nothing changes any more, how many tanks are orange,
          blue, or mud? (choice for levels 2-4, typed number for level 5)

Misconception solvers (each gives a full wrong answer):
  MINUTE_OFF_BY_ONE    counts one minute too few or too many
  FLOWS_ALL_THE_WAY    lets paint run through the whole network, ignoring time
  FORGETS_START        leaves out the tank the paint was poured into
  SEQUENTIAL_SPREAD    runs one colour all the way first, then the other
  FIRST_COLOR_STAYS    only same-minute meetings make mud; a coloured tank never changes
  PROTECTED_SOURCES    the two starting tanks never change
  MUD_STILL_FLOWS      mud tanks keep pushing both colours
  COUNTS_MUD           counts the mud tanks as the asked colour
"""

import json
import math
import random
from dataclasses import dataclass, field, asdict

W, H = 560, 400
TOP, BOTTOM = 40, 340          # tanks live between these y values; legend below
R = 22
LETTERS = "ABCDEFGHJKLMN"
O, B, M = "O", "B", "M"
COLOR_NAME = {O: "orange", B: "blue", M: "mud"}


# --------------------------------------------------------------------------
# Geometry and network
# --------------------------------------------------------------------------

def seg_cross(p1, p2, p3, p4):
    def orient(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)
    if p1 in (p3, p4) or p2 in (p3, p4):
        return False
    return (orient(p1, p2, p3) * orient(p1, p2, p4) < 0 and
            orient(p3, p4, p1) * orient(p3, p4, p2) < 0)


def point_seg_dist(p, a, b):
    (ax, ay), (bx, by), (px, py) = a, b, p
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(ax + t * dx - px, ay + t * dy - py)


def random_network(rng, n, density):
    pts = []
    for _ in range(5000):
        if len(pts) == n:
            break
        p = (rng.randint(50, W - 50), rng.randint(TOP + 20, BOTTOM - 20))
        if all(math.dist(p, q) > 92 for q in pts):
            pts.append(p)
    if len(pts) < n:
        return None
    pts.sort(key=lambda p: (p[1] // 90, p[0]))       # letters roughly read left to right, top to bottom
    tanks = {LETTERS[i]: p for i, p in enumerate(pts)}
    ids = list(tanks)
    cands = sorted((math.dist(tanks[a], tanks[b]), a, b) for i, a in enumerate(ids) for b in ids[i + 1:])
    pipes, deg = [], {t: 0 for t in ids}
    for d, a, b in cands:
        if d > 190:
            break
        if deg[a] >= 4 or deg[b] >= 4:
            continue
        connected_already = reach(adjacency(ids, pipes), a) >= {a, b}
        if connected_already and rng.random() > density:
            continue
        pa, pb = tanks[a], tanks[b]
        if any(seg_cross(pa, pb, tanks[x], tanks[y]) for x, y in pipes):
            continue
        if any(point_seg_dist(tanks[t], pa, pb) < R + 12 for t in ids if t not in (a, b)):
            continue
        pipes.append((a, b))
        deg[a] += 1
        deg[b] += 1
    if reach(adjacency(ids, pipes), ids[0]) != set(ids):
        return None
    return tanks, sorted(pipes)


def adjacency(ids, pipes):
    g = {t: [] for t in ids}
    for a, b in pipes:
        g[a].append(b)
        g[b].append(a)
    for t in g:
        g[t].sort()
    return g


def reach(g, s, blocked=()):
    seen, stack = {s}, [s]
    while stack:
        u = stack.pop()
        for v in g[u]:
            if v not in seen and v not in blocked:
                seen.add(v)
                stack.append(v)
    return seen


def hops(g, s):
    d, q = {s: 0}, [s]
    for u in q:
        for v in g[u]:
            if v not in d:
                d[v] = d[u] + 1
                q.append(v)
    return d


# --------------------------------------------------------------------------
# Simulation: the true rule and its misconception variants
# --------------------------------------------------------------------------

def simulate(g, sources, minutes=None, protect=False, keep_first=False, mud_flows=False):
    """sources: {tank: colour}. Returns (final state, list of per-minute change dicts)."""
    state = {t: None for t in g}
    state.update(sources)
    history = []
    limit = minutes if minutes is not None else 4 * len(g)
    for _ in range(limit):
        incoming = {t: set() for t in g}
        for u, s in state.items():
            push = {s} if s in (O, B) else ({O, B} if s == M and mud_flows else set())
            for v in g[u]:
                incoming[v] |= push
        new = dict(state)
        for v in g:
            s = state[v]
            if s == M or (protect and v in sources) or (keep_first and s is not None):
                continue
            cols = ({s} if s else set()) | incoming[v]
            new[v] = M if len(cols) == 2 else (next(iter(cols)) if cols else None)
        changes = {v: new[v] for v in g if new[v] != state[v]}
        if not changes:
            break
        history.append(changes)
        state = new
    return state, history


def sequential(g, sources, first):
    """One colour floods every clean tank it can reach, then the other does."""
    state = {t: None for t in g}
    state.update(sources)
    for col in (first, O if first == B else B):
        src = [t for t, c in sources.items() if c == col]
        if not src:
            continue
        for t in reach(g, src[0], blocked={x for x, c in state.items() if c is not None and x != src[0]}):
            if state[t] is None:
                state[t] = col
    return state


def count(state, col):
    return sum(1 for s in state.values() if s == col)


def names(state, col):
    return [t for t in sorted(state) if state[t] == col]


# --------------------------------------------------------------------------
# Misconception texts (added to coach.js when the map lacks them)
# --------------------------------------------------------------------------

MISCONCEPTIONS = {
    "MINUTE_OFF_BY_ONE": {"concept": "SIMULATION",
        "description": "Runs the spread for one minute too few or one too many.",
        "remediation": "Have the student write 'minute 1', 'minute 2' and so on, and list what changes under each."},
    "FLOWS_ALL_THE_WAY": {"concept": "SIMULATION",
        "description": "Lets the paint run through every connected tank at once, ignoring that it moves one pipe per minute.",
        "remediation": "Ask how far the paint can get in the very first minute."},
    "FORGETS_START": {"concept": "SIMULATION",
        "description": "Counts only the tanks the paint flowed into and leaves out the tank it was poured into.",
        "remediation": "Ask what colour the starting tank is at the end."},
    "SEQUENTIAL_SPREAD": {"concept": "PARALLEL_SPREAD",
        "description": "Spreads one colour all the way first and then the other, instead of both together, minute by minute.",
        "remediation": "Have the student colour both fronts for minute 1, then for minute 2."},
    "FIRST_COLOR_STAYS": {"concept": "PARALLEL_SPREAD",
        "description": "Thinks a tank that already has a colour can never change, so only tanks reached by both colours in the same minute turn to mud.",
        "remediation": "Find two neighbouring tanks of different colours and ask what flows into each one in the next minute."},
    "PROTECTED_SOURCES": {"concept": "PARALLEL_SPREAD",
        "description": "Treats the two starting places as safe even when both colours reach them.",
        "remediation": "Ask what flows into each starting tank in the first minute."},
    "MUD_STILL_FLOWS": {"concept": "PARALLEL_SPREAD",
        "description": "Lets mud keep pushing colour into its neighbours, so mud spreads.",
        "remediation": "Reread the rule about mud with the student, then redo the minute where the first mud appears."},
    "COUNTS_MUD": {"concept": "SIMULATION",
        "description": "Counts the mud tanks as if they still had the asked colour.",
        "remediation": "Ask the student to name each tank they counted and say its colour at the end."},
}


LADDER = [
    {"level": 1, "question": "after", "tanks": (6, 7), "density": 0.5, "minutes": 2,
     "note": "One colour. Count the tanks with paint after 2 minutes; paint moves one pipe per minute."},
    {"level": 2, "question": "final", "tanks": (7, 8), "density": 0.45, "apart": (3, 99),
     "require": ["SEQUENTIAL_SPREAD"], "note": "Two colours start far apart and meet in the middle; count one colour at the end."},
    {"level": 3, "question": "final", "tanks": (8, 9), "density": 0.45, "apart": (3, 99),
     "require": ["FIRST_COLOR_STAYS"], "note": "The colours meet across a pipe, so two tanks that already had a colour turn to mud."},
    {"level": 4, "question": "final", "tanks": (8, 9), "density": 0.45, "apart": (1, 1),
     "require": ["PROTECTED_SOURCES"], "note": "The two starting tanks are joined by a pipe, so both turn to mud in the first minute."},
    {"level": 5, "question": "final", "tanks": (10, 11), "density": 0.4, "apart": (1, 3),
     "require": ["FIRST_COLOR_STAYS"], "entry": "number",
     "note": "A bigger network, with a typed answer instead of choices."},
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
    answer_value: int
    entry: str
    distractors: list
    value_tags: dict
    concepts: list
    explanation: list
    hints: list
    knobs: dict = field(default_factory=dict)


def tank_list(ts):
    return ", ".join(ts) if ts else "none"


def minute_lines(history):
    lines = []
    for m, ch in enumerate(history, 1):
        parts = []
        for col in (O, B, M):
            ts = sorted(t for t, c in ch.items() if c == col)
            if ts:
                who = ts[0] if len(ts) == 1 else ", ".join(ts[:-1]) + " and " + ts[-1]
                verb = "turns" if len(ts) == 1 else "turn"
                parts.append(f"{who} {verb} {'to mud' if col == M else COLOR_NAME[col]}")
        lines.append(f"Minute {m}: " + "; ".join(parts) + ".")   # plain text so long minutes wrap on a phone
    return lines


def choose_options(rng, truth, wrong):
    """wrong: {value: [tags]}. Three distractors with the right answer neither smallest nor largest."""
    under = [v for v in wrong if v < truth]
    over = [v for v in wrong if v > truth]
    if not under or not over or len(wrong) < 3:
        return None
    pick = [rng.choice(under), rng.choice(over)]
    pick.append(rng.choice([v for v in wrong if v not in pick]))
    opts = sorted([truth] + pick)
    return opts


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    rng = random.Random(seed)
    for _ in range(4000):
        net = random_network(rng, rng.randint(*cfg["tanks"]), cfg["density"])
        if not net:
            continue
        tanks, pipes = net
        g = adjacency(list(tanks), pipes)
        p = (make_after if cfg["question"] == "after" else make_final)(rng, cfg, seed, tanks, pipes, g)
        if p:
            return p
    raise RuntimeError(f"parallel_spread generation failed at level {level}")


PROMPT_ONE = ("Tanks are joined by pipes. Orange paint is poured into tank {s}. Every minute, each tank that has paint "
              "pushes it through all of its pipes into the tanks next to it, all at the same moment.")
PROMPT_TWO = ("Tanks are joined by pipes. Orange paint is poured into tank {o} and blue paint into tank {b}. "
              "Every minute, each orange or blue tank pushes its colour through all of its pipes, all at the same moment, "
              "using the colour it had when the minute began. A tank that gets both colours turns to mud, even if it "
              "already had a colour. Mud is stuck: it never flows anywhere.")


def make_after(rng, cfg, seed, tanks, pipes, g):
    s = rng.choice(list(tanks))
    k = cfg["minutes"]
    d = hops(g, s)
    if max(d.values()) < k + 2:
        return None                  # the paint must still be travelling after k+1 minutes
    at = lambda m: sum(1 for v in d.values() if v <= m)
    truth = at(k)
    wrong = {}
    for v, tag in ((at(k - 1), "MINUTE_OFF_BY_ONE"), (at(k + 1), "MINUTE_OFF_BY_ONE"),
                   (len(tanks), "FLOWS_ALL_THE_WAY"), (truth - 1, "FORGETS_START")):
        if v != truth:
            wrong.setdefault(v, [])
            if tag not in wrong[v]:
                wrong[v].append(tag)
    if len(set(t for ts in wrong.values() for t in ts)) < 3:
        return None
    opts = choose_options(rng, truth, wrong)
    if not opts:
        return None
    state, history = simulate(g, {s: O}, minutes=k)
    painted = names(state, O)
    expl = [f"Paint moves one pipe each minute, from every orange tank at once. Start: {s} is orange."]
    expl += minute_lines(history)
    expl.append(f"After {k} minutes the orange tanks are {tank_list(painted)}: {truth} tanks, counting {s}.")
    return Problem(
        family="parallel_spread", level=cfg["level"], question_type="after", seed=seed,
        scene=scene_dict(tanks, pipes, {s: O}), svg=render_svg(tanks, pipes, {s: O}, seed),
        prompt=PROMPT_ONE.format(s=s), question=f"After {k} minutes, how many tanks have orange paint in them?",
        options=opts, answer_index=opts.index(truth), answer_value=truth, entry="choice",
        distractors=[{"option": v, "misconceptions": sorted(wrong[v])} for v in opts if v != truth],
        value_tags={}, concepts=["SIMULATION", "GRAPH_NEIGHBORHOOD"], explanation=expl,
        hints=["Start with the orange tank. Which tanks are joined to it by a pipe? Those turn orange in minute 1.",
               "For minute 2, every tank that was orange when the minute began pushes paint into its neighbours.",
               "Count every orange tank at the end, including the one the paint was poured into."],
        knobs={"tanks": len(tanks), "pipes": len(pipes), "minutes": k},
    )


def make_final(rng, cfg, seed, tanks, pipes, g):
    ids = list(tanks)
    o = rng.choice(ids)
    d = hops(g, o)
    lo, hi = cfg["apart"]
    far = [t for t in ids if lo <= d[t] <= hi]
    if not far:
        return None
    b = rng.choice(far)
    sources = {o: O, b: B}
    state, history = simulate(g, sources)
    if count(state, M) == 0 or count(state, O) == 0 and count(state, B) == 0:
        return None
    variants = {
        "SEQUENTIAL_SPREAD": [sequential(g, sources, O), sequential(g, sources, B)],
        "FIRST_COLOR_STAYS": [simulate(g, sources, keep_first=True)[0]],
        "PROTECTED_SOURCES": [simulate(g, sources, protect=True)[0]],
        "MUD_STILL_FLOWS": [simulate(g, sources, mud_flows=True)[0]],
    }
    adjacent = b in g[o]
    asks = [O, B, M]
    rng.shuffle(asks)
    for ask in asks:
        truth = count(state, ask)
        if ask != M and truth == 0:
            continue
        wrong = {}
        def add(v, tag):
            if v != truth and v >= 0:
                wrong.setdefault(v, [])
                if tag not in wrong[v]:
                    wrong[v].append(tag)
        for tag, sts in variants.items():
            for st in sts:
                add(count(st, ask), tag)
        if ask != M:
            add(truth + count(state, M), "COUNTS_MUD")
            src = o if ask == O else b
            if state[src] == ask:
                add(truth - 1, "FORGETS_START")
        got = {t for ts in wrong.values() for t in ts}
        if not all(r in got for r in cfg["require"]):
            continue
        if adjacent and "PROTECTED_SOURCES" not in got:
            continue                 # with joined starting tanks, the protected-sources trap must show
        # a targeted misconception must never reproduce the right answer (Sequential has two orders: both must miss)
        if any(count(st, ask) == truth for tag, sts in variants.items() if tag in cfg["require"] for st in sts):
            continue
        # list the mistake this level targets first, so the page's "look again" question asks about it
        first = cfg["require"] + (["PROTECTED_SOURCES"] if adjacent else [])
        order = lambda ts: sorted(ts, key=lambda t: (t not in first, first.index(t) if t in first else 0, t))
        entry = cfg.get("entry", "choice")
        if entry == "choice":
            opts = choose_options(rng, truth, wrong)
            if not opts:
                continue
            ans, distractors, value_tags = opts.index(truth), [{"option": v, "misconceptions": order(wrong[v])} for v in opts if v != truth], {}
        else:
            if len(wrong) < 3:
                continue
            opts, ans, distractors = [], -1, []
            value_tags = {str(v): order(t) for v, t in sorted(wrong.items())}
        what = "have turned to mud" if ask == M else f"are {COLOR_NAME[ask]}"
        question = f"When nothing changes any more, how many tanks {what}?"
        expl = [f"Start: {o} is orange and {b} is blue. Each minute, use the colours from the start of that minute."]
        if adjacent:
            expl.append(f"{o} and {b} are joined, so in minute 1 each pushes its colour into the other: both turn to mud, "
                        "but they still pushed paint into their other neighbours that minute.")
        expl += minute_lines(history)
        expl.append(f"After minute {len(history)} nothing changes.")
        for col in (O, B, M):
            expl.append(f"  {COLOR_NAME[col].capitalize()}: {tank_list(names(state, col))} ({count(state, col)})")
        expl.append(f"So {truth} tanks {what}.")
        h = ["Go one minute at a time. Write down which tanks change in each minute.",
             "Use only the colours the tanks had when the minute began. Both colours move in the same minute."]
        if adjacent:
            h.append(f"What flows into {o} and into {b} in the very first minute?")
        if "FIRST_COLOR_STAYS" in cfg["require"]:
            h.append("Look for an orange tank and a blue tank joined by a pipe. What does each push into the other next minute?")
        h.append("Mud never flows. Once a tank is mud, it is a wall.")
        return Problem(
            family="parallel_spread", level=cfg["level"], question_type="final", seed=seed,
            scene=scene_dict(tanks, pipes, sources), svg=render_svg(tanks, pipes, sources, seed),
            prompt=PROMPT_TWO.format(o=o, b=b), question=question,
            options=opts, answer_index=ans, answer_value=truth, entry=entry,
            distractors=distractors, value_tags=value_tags,
            concepts=["PARALLEL_SPREAD", "SIMULATION", "GRAPH_NEIGHBORHOOD"], explanation=expl, hints=h,
            knobs={"tanks": len(tanks), "pipes": len(pipes), "ask": COLOR_NAME[ask], "adjacent": adjacent,
                   "minutes": len(history)},
        )
    return None


def scene_dict(tanks, pipes, sources):
    return {"tanks": {t: list(p) for t, p in tanks.items()}, "pipes": [list(p) for p in pipes],
            "sources": {t: COLOR_NAME[c] for t, c in sources.items()}}


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

FILL = {O: "#e8862a", B: "#2f6fb5", None: "#f4f1ea"}
TEXT = {O: "#ffffff", B: "#ffffff", None: "#1f2933"}


def render_svg(tanks, pipes, sources, seed):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="Helvetica, Arial, sans-serif" data-family="parallel_spread" data-seed="{seed}">',
           f'<rect x="0" y="0" width="{W}" height="{H}" rx="10" fill="#e7edf2"/>']
    for a, b in pipes:
        (x1, y1), (x2, y2) = tanks[a], tanks[b]
        out.append(f'<g class="pipe" data-a="{a}" data-b="{b}">'
                   f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#6b7a88" stroke-width="10" stroke-linecap="round"/>'
                   f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#aab6c1" stroke-width="4" stroke-linecap="round"/></g>')
    for t, (x, y) in tanks.items():
        c = sources.get(t)
        start = COLOR_NAME[c] if c else ""
        out.append(f'<g class="tank" data-id="{t}" data-x="{x}" data-y="{y}" data-start="{start}">'
                   f'<circle cx="{x}" cy="{y}" r="{R}" fill="{FILL[c]}" stroke="#33414e" stroke-width="2.5"/>'
                   f'<text x="{x}" y="{y + 6}" font-size="20" font-weight="bold" text-anchor="middle" fill="{TEXT[c]}">{t}</text></g>')
    ly = BOTTOM + 34
    o_t = next((t for t, c in sources.items() if c == O), None)
    b_t = next((t for t, c in sources.items() if c == B), None)
    x = 24
    for col, t in ((O, o_t), (B, b_t)):
        if not t:
            continue
        out.append(f'<circle cx="{x + 10}" cy="{ly - 6}" r="11" fill="{FILL[col]}" stroke="#33414e" stroke-width="2"/>'
                   f'<text x="{x + 28}" y="{ly + 1}" font-size="21" fill="#1f2933">{COLOR_NAME[col]} poured into {t}</text>')
        x += 270
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    import sys
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print(json.dumps({k: v for k, v in asdict(generate(lvl, sd)).items() if k != "svg"}, indent=2, ensure_ascii=False))

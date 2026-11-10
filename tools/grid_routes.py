"""
Problem family: grid_routes (counting shortest routes on a grid with obstacles).

Concept targets: COUNTING_DP, SHORTEST_PATH, GRAPH_MODEL.
Source task: Building a Chip (Senior C, 2015).

Scenario (original): a delivery robot drives along a street grid from the
bakery to the library. Some intersections are closed for roadwork. The robot
only ever takes a shortest route.

One scene model (grid size, closed intersections, start, goal) drives both the
SVG picture and the solver. The picture carries the scene in data-* attributes
and in visible marks; the checker rebuilds the grid from the picture.

Question types:
  length  how many blocks long is the shortest route?
  count   how many different shortest routes are there?
"""

import json
import random
from collections import deque
from dataclasses import dataclass, field, asdict

SP = 64           # pixel spacing between intersections
PAD = 56


def neighbors(r, c, R, C):
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        rr, cc = r + dr, c + dc
        if 0 <= rr < R and 0 <= cc < C:
            yield rr, cc


def bfs(R, C, closed, s):
    dist, ways = {s: 0}, {s: 1}
    q = deque([s])
    while q:
        u = q.popleft()
        for v in neighbors(*u, R, C):
            if v in closed:
                continue
            if v not in dist:
                dist[v] = dist[u] + 1
                ways[v] = ways[u]
                q.append(v)
            elif dist[v] == dist[u] + 1:
                ways[v] += ways[u]
    return dist, ways


def shortest_paths(R, C, closed, s, t, limit=2000):
    dist, _ = bfs(R, C, closed, s)
    if t not in dist:
        return []
    out = []

    def back(u, acc):
        if len(out) >= limit:
            return
        if u == s:
            out.append(list(reversed(acc)))
            return
        for v in neighbors(*u, R, C):
            if v in dist and dist[v] == dist[u] - 1:
                acc.append(v)
                back(v, acc)
                acc.pop()
    back(t, [t])
    return out


def turns(path):
    dirs = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:])]
    return sum(1 for x, y in zip(dirs, dirs[1:]) if x != y)


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def greedy_length(R, C, closed, s, t):
    """Drive toward the goal; when blocked, step sideways; never revisit."""
    u, seen, steps = s, {s}, 0
    while u != t and steps < R * C:
        opts = [v for v in neighbors(*u, R, C) if v not in closed and v not in seen]
        if not opts:
            return None
        opts.sort(key=lambda v: manhattan(v, t))
        u = opts[0]
        seen.add(u)
        steps += 1
    return steps if u == t else None


# Misconceptions -----------------------------------------------------------

def m_length_for_count(R, C, closed, s, t):
    return bfs(R, C, closed, s)[0][t]


def m_ignores_closed(R, C, closed, s, t):
    return bfs(R, C, set(), s)[1][t]


def m_few_turns(R, C, closed, s, t):
    return sum(1 for p in shortest_paths(R, C, closed, s, t) if turns(p) <= 2)


def m_box_dots(R, C, closed, s, t):
    """Counts the open intersections in the rectangle between bakery and library."""
    r0, r1 = sorted((s[0], t[0])); c0, c1 = sorted((s[1], t[1]))
    return sum(1 for r in range(r0, r1 + 1) for c in range(c0, c1 + 1) if (r, c) not in closed)


COUNT_MISCONCEPTIONS = {
    "LENGTH_FOR_COUNT": m_length_for_count,
    "COUNTS_BOX_INTERSECTIONS": m_box_dots,
    "IGNORES_CLOSED": m_ignores_closed,
    "FEW_TURNS_ONLY": m_few_turns,
}


def m_nodes_not_blocks(R, C, closed, s, t):
    return bfs(R, C, closed, s)[0][t] + 1


def m_straight_line(R, C, closed, s, t):
    return manhattan(s, t)


def m_greedy(R, C, closed, s, t):
    return greedy_length(R, C, closed, s, t)


LENGTH_MISCONCEPTIONS = {
    "COUNTS_INTERSECTIONS": m_nodes_not_blocks,
    "IGNORES_CLOSED_LENGTH": m_straight_line,
    "GREEDY_ROUTE": m_greedy,
}

MISCONCEPTIONS = {
    "COUNTS_BOX_INTERSECTIONS": {"concept": "COUNTING_DP",
        "description": "Counts the intersections between the start and the goal instead of the routes.",
        "remediation": "Have the student trace two different routes that pass through the same intersections in a different order."},
    "IGNORES_CLOSED": {"concept": "COUNTING_DP",
        "description": "Counts routes as if no intersections were closed.",
        "remediation": "Have the student cross out every closed intersection and write 0 there before counting."},
    "FEW_TURNS_ONLY": {"concept": "COUNTING_DP",
        "description": "Finds the routes with one or two turns and misses the ones that zigzag.",
        "remediation": "Show one zigzag route of the same length and ask whether it is also shortest."},
    "COUNTS_INTERSECTIONS": {"concept": "SHORTEST_PATH",
        "description": "Counts the intersections on the route instead of the blocks between them (off by one).",
        "remediation": "Ask the student to count the street pieces the robot drives along, not the corners."},
    "IGNORES_CLOSED_LENGTH": {"concept": "SHORTEST_PATH",
        "description": "Gives the distance as if the robot could drive straight through closed intersections.",
        "remediation": "Ask the student to trace the route with a finger and stop at the first closed intersection."},
    "GREEDY_ROUTE": {"concept": "SHORTEST_PATH",
        "description": "Always drives toward the goal and detours only when blocked, which can make a longer route.",
        "remediation": "Ask the student to write the distance from the start at every intersection, nearest first."},
}

LADDER = [
    {"level": 1, "question": "length", "rows": (4, 5), "cols": (5, 6), "closed": (3, 5), "detour": True,
     "note": "How long is the shortest route? Closed intersections force a detour."},
    {"level": 2, "question": "count", "rows": (3, 3), "cols": (3, 4), "closed": (0, 0), "detour": False,
     "target": (3, 10), "entry": "choice", "note": "Count the shortest routes on a small grid with nothing closed."},
    {"level": 3, "question": "count", "rows": (4, 5), "cols": (4, 6), "closed": (2, 3), "detour": False,
     "target": (4, 16), "entry": "choice", "note": "Count shortest routes when some intersections are closed."},
    {"level": 4, "question": "count", "rows": (5, 6), "cols": (6, 7), "closed": (4, 7), "detour": True,
     "target": (3, 24), "entry": "number", "note": "Closed intersections force a detour; type the count."},
    {"level": 5, "question": "count", "rows": (6, 6), "cols": (8, 9), "closed": (6, 10), "detour": True,
     "target": (10, 80), "entry": "number", "note": "Large grid, many closures. Matches the 2015 Senior task."},
]


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


PROMPT = ("A delivery robot drives along the streets from the bakery (square) to the library (diamond). "
          "Intersections marked with an X are closed for roadwork and cannot be driven through. "
          "The robot always takes a shortest route.")


def render_svg(R, C, closed, s, t, seed):
    W, H = PAD * 2 + SP * (C - 1), PAD * 2 + SP * (R - 1)
    xy = lambda r, c: (PAD + c * SP, PAD + r * SP)
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
         f'font-family="Helvetica, Arial, sans-serif" data-family="grid_routes" data-rows="{R}" data-cols="{C}" data-seed="{seed}">']
    o.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="14" fill="#e9eef3"/>')
    # city blocks (decorative, behind streets)
    for r in range(R - 1):
        for c in range(C - 1):
            x, y = xy(r, c)
            o.append(f'<rect x="{x + 9}" y="{y + 9}" width="{SP - 18}" height="{SP - 18}" rx="6" fill="#d3dce6"/>')
    # streets
    for r in range(R):
        for c in range(C):
            for rr, cc in ((r, c + 1), (r + 1, c)):
                if rr < R and cc < C:
                    (x1, y1), (x2, y2) = xy(r, c), xy(rr, cc)
                    o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#8a97a8" stroke-width="6" stroke-linecap="round"/>')
    # intersections
    for r in range(R):
        for c in range(C):
            x, y = xy(r, c)
            st = "closed" if (r, c) in closed else "start" if (r, c) == s else "goal" if (r, c) == t else "open"
            g = f'<g class="node" data-r="{r}" data-c="{c}" data-state="{st}">'
            if st == "open":
                g += f'<circle cx="{x}" cy="{y}" r="7" fill="#ffffff" stroke="#55657a" stroke-width="2"/>'
            elif st == "closed":
                g += (f'<circle cx="{x}" cy="{y}" r="15" fill="#f6d36b" stroke="#7a5a00" stroke-width="2"/>'
                      f'<path class="xmark" d="M{x - 7},{y - 7} L{x + 7},{y + 7} M{x + 7},{y - 7} L{x - 7},{y + 7}" '
                      f'stroke="#3a2a00" stroke-width="4" stroke-linecap="round"/>')
            elif st == "start":
                g += (f'<rect class="startmark" x="{x - 13}" y="{y - 13}" width="26" height="26" rx="4" fill="#2f5dff"/>'
                      f'<text x="{x}" y="{y - 20}" font-size="14" font-weight="bold" text-anchor="middle" fill="#16233b">Bakery</text>')
            else:
                g += (f'<path class="goalmark" d="M{x},{y - 16} L{x + 16},{y} L{x},{y + 16} L{x - 16},{y} Z" fill="#1e8a5a"/>'
                      f'<text x="{x}" y="{y + 32}" font-size="14" font-weight="bold" text-anchor="middle" fill="#16233b">Library</text>')
            o.append(g + "</g>")
    o.append("</svg>")
    return "".join(o)


def count_grid_text(R, C, closed, s, t):
    dist, ways = bfs(R, C, closed, s)
    D = dist[t]
    rows = []
    for r in range(R):
        cells = []
        for c in range(C):
            v = (r, c)
            if v in closed:
                cells.append("X")
            elif v in dist and dist[v] + manhattan_dist_to(v, t, R, C, closed) == D:
                cells.append(str(ways[v]))
            else:
                cells.append("·")
        rows.append("  ".join(f"{x:>2}" for x in cells))
    return rows


def manhattan_dist_to(v, t, R, C, closed, _cache={}):
    key = (t, R, C, frozenset(closed))
    if key not in _cache:
        _cache[key] = bfs(R, C, closed, t)[0]
    return _cache[key].get(v, 10 ** 6)


def explanation(R, C, closed, s, t, qt):
    dist, ways = bfs(R, C, closed, s)
    D = dist[t]
    if qt == "length":
        return [f"Write the distance from the bakery at each intersection, nearest first, going around closed ones.",
                f"The library is reached first at distance {D}, so the shortest route is {D} blocks."]
    lines = [f"The shortest route is {D} blocks long.",
             "At each intersection on a shortest route, write how many shortest ways reach it: add the numbers "
             "from the neighbors one block closer to the bakery. Closed intersections count as 0.",
             "Numbers on the shortest routes (X = closed, · = not on any shortest route):"]
    lines += ["  " + row for row in count_grid_text(R, C, closed, s, t)]
    lines.append(f"The library gets {ways[t]}, so there are {ways[t]} shortest routes.")
    return lines


def hints(cfg):
    if cfg["question"] == "length":
        return ["Can the robot drive straight there, or is something in the way?",
                "Count the street pieces, not the intersections.",
                "Write the distance from the bakery at each intersection, nearest first."]
    h = ["First find how long a shortest route is.",
         "At the bakery write 1. At each next intersection, add the numbers from the neighbors one step closer.",
         "A closed intersection gets 0: no route can pass through it."]
    if cfg["detour"]:
        h.append("Some shortest routes have to go around. Do they all go the same way around?")
    return h


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    rng = random.Random(seed)
    for _ in range(6000):
        R = rng.randint(*cfg["rows"]); C = rng.randint(*cfg["cols"])
        s = (rng.randrange(R), 0); t = (rng.randrange(R), C - 1)
        if cfg["question"] == "count" and level == 2:
            s, t = (0, 0), (R - 1, C - 1)
        cells = [(r, c) for r in range(R) for c in range(C) if (r, c) not in (s, t)]
        closed = set(rng.sample(cells, rng.randint(*cfg["closed"])))
        dist, ways = bfs(R, C, closed, s)
        if t not in dist:
            continue
        D = dist[t]
        detour = D > manhattan(s, t)
        if detour != cfg["detour"]:
            continue
        if cfg["question"] == "length":
            truth = D
            vals = {}
            for k, f in LENGTH_MISCONCEPTIONS.items():
                v = f(R, C, closed, s, t)
                if v is not None and v != truth:
                    vals.setdefault(v, []).append(k)
            if len(vals) < 3 or not any(v < truth for v in vals) or not any(v > truth for v in vals):
                continue
        else:
            truth = ways[t]
            lo, hi = cfg["target"]
            if not lo <= truth <= hi:
                continue
            vals = {}
            for k, f in COUNT_MISCONCEPTIONS.items():
                v = f(R, C, closed, s, t)
                if v is not None and v > 0 and v != truth:
                    vals.setdefault(v, []).append(k)
            if "LENGTH_FOR_COUNT" not in {k for ks in vals.values() for k in ks}:
                continue
            if level >= 3 and "IGNORES_CLOSED" not in {k for ks in vals.values() for k in ks}:
                continue
        entry = cfg.get("entry", "choice")
        if entry == "choice":
            under = [v for v in vals if v < truth]; over = [v for v in vals if v > truth]
            if not under or not over:
                continue
            chosen = {rng.choice(under), rng.choice(over)}
            rest = [v for v in vals if v not in chosen]
            if rest:
                chosen.add(rng.choice(rest))
            opts = sorted(chosen | {truth})
            if opts[0] == truth or opts[-1] == truth or len(opts) < 3:
                continue
            ans = opts.index(truth)
            distractors = [{"option": v, "misconceptions": sorted(vals[v])} for v in opts if v != truth]
        else:
            opts, ans, distractors = [], -1, []
        q = ("How many blocks long is the shortest route?" if cfg["question"] == "length"
             else "How many different shortest routes can the robot take?")
        return Problem(
            family="grid_routes", level=level, question_type=cfg["question"], seed=seed,
            scene={"rows": R, "cols": C, "closed": sorted(map(list, closed)), "start": list(s), "goal": list(t)},
            svg=render_svg(R, C, closed, s, t, seed),
            prompt=PROMPT, question=q,
            options=opts, answer_index=ans, answer_value=truth, entry=entry,
            distractors=distractors, value_tags={str(v): sorted(ks) for v, ks in vals.items()},
            concepts=(["SHORTEST_PATH", "GRAPH_MODEL"] if cfg["question"] == "length"
                      else ["COUNTING_DP", "SHORTEST_PATH", "GRAPH_MODEL"]),
            explanation=explanation(R, C, closed, s, t, cfg["question"]),
            hints=hints(cfg),
            knobs={"rows": R, "cols": C, "closed": len(closed), "length": D, "detour": detour},
        )
    raise RuntimeError(f"grid_routes generation failed at level {level}")


if __name__ == "__main__":
    import sys
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    d = asdict(generate(lvl, seed))
    print(json.dumps({k: v for k, v in d.items() if k != "svg"}, indent=2, ensure_ascii=False))

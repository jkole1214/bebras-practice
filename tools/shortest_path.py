"""
Problem family: shortest_path (cheapest crossing of a lake via islands).

Concept targets: SHORTEST_PATH, GRAPH_MODEL, PATH_TRACE.

Scenario (original): a chain of floating walkways must connect the north
shore to the south shore, hopping between islands. Each drawn walkway shows
how many planks it needs. Find the cheapest crossing.

One scene model (islands with coordinates, walkways with plank counts) drives
both the SVG picture and the solver. The picture carries the scene in
data-* attributes AND in its visible labels; the independent checker rebuilds
the graph from the SVG and compares the visible labels to the data, so the
answer key cannot drift from what a student sees.

Question types:
  compare: three complete routes are listed by island letter; which is cheapest?
  cost:    what is the fewest planks needed? (numeric multiple choice)
  build:   select the walkways for the cheapest crossing (interactive);
           answer is the edge set; wrong submissions are matched to
           misconception paths for diagnosis.
"""

import heapq
import itertools
import json
import math
import random
from dataclasses import dataclass, field, asdict

W, H = 640, 440
NORTH_Y, SOUTH_Y = 60, 380          # shoreline y-coordinates
ISLAND_R = 24
LABEL_W, LABEL_H = 22, 18
N, S = "N", "S"
LETTERS = "ABCDEFGHJK"


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------

def seg_intersect(p1, p2, p3, p4):
    """Proper intersection of segments p1p2 and p3p4 (shared endpoints ignored)."""
    def orient(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)
    if p1 in (p3, p4) or p2 in (p3, p4):
        return False
    o1, o2 = orient(p1, p2, p3), orient(p1, p2, p4)
    o3, o4 = orient(p3, p4, p1), orient(p3, p4, p2)
    return o1 * o2 < 0 and o3 * o4 < 0


def rect_hits_segment(rect, a, b):
    x0, y0, x1, y1 = rect
    def inside(p):
        return x0 <= p[0] <= x1 and y0 <= p[1] <= y1
    if inside(a) or inside(b):
        return True
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return any(seg_intersect(a, b, corners[i], corners[(i + 1) % 4]) for i in range(4))


def rect_overlap(r1, r2, pad=2):
    return not (r1[2] + pad < r2[0] or r2[2] + pad < r1[0] or r1[3] + pad < r2[1] or r2[3] + pad < r1[1])


def rect_hits_circle(rect, c, r):
    cx = min(max(c[0], rect[0]), rect[2])
    cy = min(max(c[1], rect[1]), rect[3])
    return (cx - c[0]) ** 2 + (cy - c[1]) ** 2 < r * r


def point_seg_dist(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(ax + t * dx - px, ay + t * dy - py)


# --------------------------------------------------------------------------
# Scene
# --------------------------------------------------------------------------

@dataclass
class Scene:
    islands: dict           # id -> (x, y)
    edges: list             # [a, b, w]
    shapes: dict = field(default_factory=dict)  # id -> polygon points

    def endpoints(self, a, b):
        """Drawn segment for an edge. Shore edges drop vertically to the shore."""
        if a in (N, S) or b in (N, S):
            isl, shore = (b, a) if a in (N, S) else (a, b)
            x, y = self.islands[isl]
            return (x, NORTH_Y if shore == N else SOUTH_Y), (x, y)
        return self.islands[a], self.islands[b]

    def adj(self):
        g = {}
        for a, b, w in self.edges:
            g.setdefault(a, []).append((b, w))
            g.setdefault(b, []).append((a, w))
        return g


def label_rect(scene, a, b):
    p, q = scene.endpoints(a, b)
    mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
    return (mx - LABEL_W / 2, my - LABEL_H / 2, mx + LABEL_W / 2, my + LABEL_H / 2)


def layout_ok(scene):
    """Picture validity: no crossing walkways, labels clear of islands,
    other walkways and other labels, walkways not grazing other islands."""
    segs = {(a, b): scene.endpoints(a, b) for a, b, _ in scene.edges}
    keys = list(segs)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            if seg_intersect(*segs[keys[i]], *segs[keys[j]]):
                return False
    rects = {k: label_rect(scene, *k) for k in keys}
    for k, r in rects.items():
        for iid, c in scene.islands.items():
            if rect_hits_circle(r, c, ISLAND_R + 2):
                return False
        for k2, s in segs.items():
            if k2 != k and rect_hits_segment(r, *s):
                return False
        for k2, r2 in rects.items():
            if k2 != k and rect_overlap(r, r2):
                return False
    for k, (p, q) in segs.items():
        for iid, c in scene.islands.items():
            if iid in k:
                continue
            if point_seg_dist(c, p, q) < ISLAND_R + 6:
                return False
    return True


def random_islands(rng, n):
    pts = []
    for _ in range(4000):
        if len(pts) == n:
            break
        p = (rng.randint(60, W - 60), rng.randint(NORTH_Y + 55, SOUTH_Y - 55))
        if all(math.dist(p, q) > 95 for q in pts):
            pts.append(p)
    if len(pts) < n:
        return None
    pts.sort(key=lambda p: (p[1], p[0]))
    return {LETTERS[i]: p for i, p in enumerate(pts)}


def blob(rng, c, r):
    k = 9
    pts = []
    for i in range(k):
        ang = 2 * math.pi * i / k + rng.uniform(-0.15, 0.15)
        rr = r * rng.uniform(0.85, 1.12)
        pts.append((round(c[0] + rr * math.cos(ang), 1), round(c[1] + rr * 0.8 * math.sin(ang), 1)))
    return pts


def candidate_edges(islands, max_len):
    ids = list(islands)
    cands = []
    for a, b in itertools.combinations(ids, 2):
        d = math.dist(islands[a], islands[b])
        if d <= max_len:
            cands.append((d, a, b))
    for a in ids:
        x, y = islands[a]
        if y - NORTH_Y <= 150:
            cands.append((y - NORTH_Y, N, a))
        if SOUTH_Y - y <= 150:
            cands.append((SOUTH_Y - y, a, S))
    cands.sort()
    return cands


def build_scene(rng, n_islands, edge_density):
    islands = random_islands(rng, n_islands)
    if not islands:
        return None
    scene = Scene(islands=islands, edges=[])
    for d, a, b in candidate_edges(islands, 210):
        if rng.random() > edge_density:
            continue
        trial = Scene(islands, scene.edges + [[a, b, 0]])
        if layout_ok(trial):
            scene.edges.append([a, b, 0])
    # every island must be on some N-S route and degree >= 2
    g = scene.adj()
    if N not in g or S not in g:
        return None
    for iid in islands:
        if len(g.get(iid, [])) < 2:
            return None
    scene.shapes = {iid: blob(rng, c, ISLAND_R) for iid, c in islands.items()}
    return scene


# --------------------------------------------------------------------------
# Solvers: true optimum and misconceptions
# --------------------------------------------------------------------------

def path_cost(scene, path):
    wt = {frozenset((a, b)): w for a, b, w in scene.edges}
    return sum(wt[frozenset(p)] for p in zip(path, path[1:]))


def all_simple_paths(scene, limit=20000):
    g = scene.adj()
    out = []
    def dfs(u, seen, path):
        if len(out) >= limit:
            return
        if u == S:
            out.append(list(path))
            return
        for v, _ in g.get(u, []):
            if v not in seen and v != N:
                seen.add(v); path.append(v)
                dfs(v, seen, path)
                path.pop(); seen.discard(v)
    dfs(N, {N}, [N])
    return out


def dijkstra(scene, src=N):
    g = scene.adj()
    dist = {src: 0}
    order = []
    pq = [(0, src)]
    done = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in done:
            continue
        done.add(u); order.append((u, d))
        for v, w in g.get(u, []):
            if d + w < dist.get(v, 1e9):
                dist[v] = d + w
                heapq.heappush(pq, (d + w, v))
    return dist, order


def greedy_walk(scene, start, goal):
    """Always take the cheapest walkway to a place not yet visited."""
    g = scene.adj()
    path, seen, u = [start], {start}, start
    while u != goal:
        opts = sorted((w, v) for v, w in g.get(u, []) if v not in seen and v not in (N, S) or v == goal)
        opts = [(w, v) for w, v in opts if v not in seen]
        if not opts:
            return None
        w, u = opts[0]
        path.append(u); seen.add(u)
    return path if start == N else list(reversed(path))


def is_monotone(scene, path):
    ys = [NORTH_Y if p == N else SOUTH_Y if p == S else scene.islands[p][1] for p in path]
    # a step counts as going back north only if it is clearly visible (30px+)
    return all(b >= a - 30 for a, b in zip(ys, ys[1:]))


def misconception_results(scene, paths, opt_path, opt_cost):
    """Return {name: (cost, path_or_None)} for each misconception."""
    res = {}
    gN = greedy_walk(scene, N, S)
    if gN:
        res["GREEDY_FROM_START"] = (path_cost(scene, gN), gN)
    gS = greedy_walk(scene, S, N)
    if gS:
        res["GREEDY_FROM_END"] = (path_cost(scene, gS), gS)
    fewest = min(paths, key=lambda p: (len(p), path_cost(scene, p)))
    res["FEWEST_WALKWAYS"] = (path_cost(scene, fewest), fewest)
    mono = [p for p in paths if is_monotone(scene, p)]
    if mono:
        bm = min(mono, key=lambda p: path_cost(scene, p))
        res["NO_BACKTRACKING"] = (path_cost(scene, bm), bm)
    # undercounts: forgetting a shore walkway on the optimal route
    wt = {frozenset((a, b)): w for a, b, w in scene.edges}
    last = wt[frozenset((opt_path[-2], opt_path[-1]))]
    res["DROPS_SHORE_WALKWAY"] = (opt_cost - last, None)
    shore_n = min(w for a, b, w in scene.edges if N in (a, b))
    shore_s = min(w for a, b, w in scene.edges if S in (a, b))
    res["SHORES_ONLY"] = (shore_n + shore_s, None)
    return res


MISCONCEPTIONS = {
    "GREEDY_FROM_START": {"concept": "SHORTEST_PATH", "direction": "over",
        "description": "Starts at the north shore and always takes the cheapest walkway available next, never reconsidering.",
        "remediation": "Show the greedy route's total next to the best route's total; ask where the cheap first step cost them later."},
    "GREEDY_FROM_END": {"concept": "SHORTEST_PATH", "direction": "over",
        "description": "Same greedy habit, working back from the south shore.",
        "remediation": "Same as greedy from the start; point out that starting from the other side does not fix the habit."},
    "FEWEST_WALKWAYS": {"concept": "GRAPH_MODEL", "direction": "over",
        "description": "Assumes the route with the fewest walkways is cheapest; counts hops instead of adding plank numbers.",
        "remediation": "Ask the student to add the numbers on a short-looking route and on a longer one."},
    "NO_BACKTRACKING": {"concept": "SHORTEST_PATH", "direction": "over",
        "description": "Only considers routes that always head toward the far shore; never tries going back north to reach a cheaper walkway.",
        "remediation": "Ask: is any rule saying you can never step back toward the start?"},
    "DROPS_SHORE_WALKWAY": {"concept": "PATH_TRACE", "direction": "under",
        "description": "Finds the right route but leaves out the walkway onto the far shore when adding.",
        "remediation": "Have the student point to each walkway while adding, including the ones touching the shores."},
    "SHORES_ONLY": {"concept": "GRAPH_MODEL", "direction": "under",
        "description": "Adds the cheapest walkway from each shore without checking that they connect through islands.",
        "remediation": "Ask the student to trace the route they priced with a finger from shore to shore."},
}


LADDER = [
    {"level": 1, "question": "compare", "islands": (3, 4), "density": 0.9,
     "require": [], "note": "Three listed routes; add the numbers on each and pick the cheapest. The cheapest is not the one with fewest walkways."},
    {"level": 2, "question": "cost", "islands": (4, 5), "density": 0.85,
     "require": [], "note": "Find the cheapest crossing yourself; small map."},
    {"level": 3, "question": "cost", "islands": (5, 6), "density": 0.85,
     "require": ["greedy_trap"], "note": "Greedy from the north shore gives a worse total."},
    {"level": 4, "question": "build", "islands": (7, 8), "density": 0.8,
     "require": ["greedy_trap", "near_tie"], "note": "Build the route; a runner-up costs only one plank more."},
    {"level": 5, "question": "build", "islands": (8, 9), "density": 0.8,
     "require": ["greedy_trap", "backtrack"], "note": "The cheapest route steps back toward the north shore at least once."},
    {"level": 6, "question": "count_routes", "islands": (6, 7), "density": 0.85, "weights": (2, 5),
     "require": [], "note": "How many different cheapest crossings are there? Two to four routes tie; type the number."},
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
    options: list
    answer_index: int
    answer_path: list
    answer_cost: int
    distractors: list
    misconception_paths: dict
    concepts: list
    explanation: list
    hints: list
    knobs: dict
    answer_value: int = None
    optimal_paths: list = field(default_factory=list)
    entry: str = "choice"
    value_tags: dict = field(default_factory=dict)


def name(p):
    return {N: "north shore", S: "south shore"}.get(p, p)


def route_text(path):
    return " → ".join(name(p) for p in path)


def explanation(scene, opt_path, opt_cost):
    dist, order = dijkstra(scene)
    lines = ["Work out the cheapest way to reach each place from the north shore, closest first:"]
    for u, d in order:
        if u != N:
            lines.append(f"  {name(u)}: {d} planks")
    lines.append(f"Cheapest crossing: {route_text(opt_path)} = {opt_cost} planks.")
    return lines


def hints(cfg):
    h = ["Write the cheapest known cost to reach each island, starting from the north shore."]
    if "greedy_trap" in cfg["require"]:
        h.append("The cheapest first walkway is not always on the cheapest crossing. Check where it leads.")
    if "backtrack" in cfg["require"]:
        h.append("Nothing says you must always head south. Could stepping back north reach a cheaper walkway?")
    h.append("When you think you are done, add up your route again, including both shore walkways.")
    return h


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    rng = random.Random(seed)
    for _ in range(3000):
        n = rng.randint(*cfg["islands"])
        scene = build_scene(rng, n, cfg["density"])
        if not scene:
            continue
        for e in scene.edges:
            e[2] = rng.randint(*cfg.get("weights", (2, 9)))
        paths = all_simple_paths(scene)
        if len(paths) < 3:
            continue
        costs = sorted((path_cost(scene, p), p) for p in paths)
        opt_cost, opt_path = costs[0]
        if cfg["question"] == "count_routes":
            p = make_count_routes(rng, cfg, seed, scene, paths, costs)
            if p:
                return p
            continue
        if len(costs) > 1 and costs[1][0] == opt_cost:
            continue  # unique optimum required
        mis = misconception_results(scene, paths, opt_path, opt_cost)
        if "greedy_trap" in cfg["require"]:
            if "GREEDY_FROM_START" not in mis or mis["GREEDY_FROM_START"][0] <= opt_cost:
                continue
        if "near_tie" in cfg["require"] and costs[1][0] != opt_cost + 1:
            continue
        if "backtrack" in cfg["require"]:
            if is_monotone(scene, opt_path) or "NO_BACKTRACKING" not in mis:
                continue
        # the cheapest must not be the one with fewest walkways at any level
        if mis["FEWEST_WALKWAYS"][1] == opt_path:
            continue
        p = assemble(rng, cfg, seed, scene, paths, opt_path, opt_cost, mis)
        if p:
            return p
    raise RuntimeError(f"shortest_path generation failed at level {level}")


def assemble(rng, cfg, seed, scene, paths, opt_path, opt_cost, mis):
    opt_t = tuple(opt_path)
    misc_paths = {k: v[1] for k, v in mis.items() if v[1] is not None and tuple(v[1]) != opt_t}
    if cfg["question"] == "compare":
        wrong = {}
        for k, pth in misc_paths.items():
            wrong.setdefault(tuple(pth), []).append(k)
        if len(wrong) < 2:
            return None
        picks = rng.sample(sorted(wrong), 2)
        # shortcut: the cheapest must not be the visually shortest drawn route
        def drawn_len(pth):
            return sum(math.dist(*scene.endpoints(a, b)) for a, b in zip(pth, pth[1:]))
        lens = [drawn_len(opt_path)] + [drawn_len(list(p)) for p in picks]
        if min(lens) == lens[0]:
            return None
        opts = [list(opt_path)] + [list(p) for p in picks]
        order = list(range(3)); rng.shuffle(order)
        opts = [opts[i] for i in order]
        ans = order.index(0)
        distractors = [{"option": o, "cost": path_cost(scene, o), "misconceptions": sorted(wrong[tuple(o)])}
                       for o in opts if o != list(opt_path)]
        prompt = ("Floating walkways will connect the north shore to the south shore, hopping between islands. "
                  "Each number is how many planks that walkway needs. Which of these crossings needs the fewest planks?")
        options = [route_text(o) for o in opts]
        option_payload = opts
    elif cfg["question"] == "cost":
        vals = {}
        for k, (c, _) in mis.items():
            if c != opt_cost and c > 0:
                vals.setdefault(c, []).append(k)
        under = [v for v in vals if v < opt_cost]
        over = [v for v in vals if v > opt_cost]
        if not under or not over or len(vals) < 3:
            return None
        chosen = [rng.choice(under), rng.choice(over)]
        rest = [v for v in vals if v not in chosen]
        chosen.append(rng.choice(rest))
        opts = sorted([opt_cost] + chosen)
        # shortcut: correct must be neither the smallest nor the largest option
        if opts[0] == opt_cost or opts[-1] == opt_cost:
            return None
        ans = opts.index(opt_cost)
        distractors = [{"option": v, "misconceptions": sorted(vals[v])} for v in opts if v != opt_cost]
        prompt = ("Floating walkways will connect the north shore to the south shore, hopping between islands. "
                  "Each number is how many planks that walkway needs. What is the fewest planks needed for a complete crossing?")
        options = opts
        option_payload = opts
    else:  # build
        prompt = ("Floating walkways will connect the north shore to the south shore, hopping between islands. "
                  "Each number is how many planks that walkway needs. Choose the walkways for a complete crossing "
                  "that uses the fewest planks.")
        options, option_payload, ans = [], [], -1
        distractors = []
    svg = render_svg(scene, seed)
    return Problem(
        family="shortest_path", level=cfg["level"], question_type=cfg["question"], seed=seed,
        scene={"islands": {k: list(v) for k, v in scene.islands.items()}, "edges": scene.edges,
               "shores": {"north_y": NORTH_Y, "south_y": SOUTH_Y}},
        svg=svg, prompt=prompt, options=options, answer_index=ans,
        answer_path=list(opt_path), answer_cost=opt_cost,
        distractors=distractors,
        misconception_paths={k: v for k, v in misc_paths.items()},
        concepts=["SHORTEST_PATH", "GRAPH_MODEL", "PATH_TRACE"],
        explanation=explanation(scene, opt_path, opt_cost),
        hints=hints(cfg),
        knobs={"islands": len(scene.islands), "walkways": len(scene.edges), "require": cfg["require"]},
    )


COUNT_MISCONCEPTIONS = {
    "ONE_CHEAPEST_ONLY": {"concept": "COUNTING_DP",
        "description": "Finds one cheapest crossing and assumes it is the only one.",
        "remediation": "Ask the student to look for a different route with the same total."},
    "COUNTS_ALL_CROSSINGS": {"concept": "COUNTING_DP",
        "description": "Counts every possible crossing instead of only the cheapest ones.",
        "remediation": "Have the student write each route's total next to it and cross out the expensive ones."},
    "COUNTS_NEAR_CHEAPEST": {"concept": "SHORTEST_PATH",
        "description": "Counts routes that are close to the cheapest as if they tied.",
        "remediation": "Ask the student to add up the plank numbers exactly for each candidate route."},
}


def make_count_routes(rng, cfg, seed, scene, paths, costs):
    opt_cost = costs[0][0]
    opt = [p for c, p in costs if c == opt_cost]
    k = len(opt)
    if not 2 <= k <= 4:
        return None
    if k == 2 and rng.random() < 0.6:
        return None          # two-way ties are common; keep them from dominating
    near = sum(1 for c, _ in costs if c <= opt_cost + 1)
    vals = {1: ["ONE_CHEAPEST_ONLY"]}
    for v, tag in ((len(paths), "COUNTS_ALL_CROSSINGS"), (near, "COUNTS_NEAR_CHEAPEST"), (opt_cost, "LENGTH_FOR_COUNT")):
        if v != k:
            vals.setdefault(v, []).append(tag)
    if len(vals) < 2:
        return None
    opts, ans = [], -1        # typed answer: no option list to guess from
    lines = explanation(scene, opt[0], opt_cost)[:-1]
    lines.append(f"The cheapest crossing costs {opt_cost} planks. These routes all cost exactly {opt_cost}:")
    lines += ["  " + route_text(p) for p in opt]
    lines.append(f"So there are {k} cheapest crossings.")
    svg = render_svg(scene, seed)
    return Problem(
        family="shortest_path", level=cfg["level"], question_type="count_routes", seed=seed,
        scene={"islands": {i: list(v) for i, v in scene.islands.items()}, "edges": scene.edges,
               "shores": {"north_y": NORTH_Y, "south_y": SOUTH_Y}},
        svg=svg,
        prompt=("Floating walkways will connect the north shore to the south shore, hopping between islands. "
                "Each number is how many planks that walkway needs. How many different crossings use the fewest planks?"),
        options=opts, answer_index=ans, answer_path=list(opt[0]), answer_cost=opt_cost,
        distractors=[],
        misconception_paths={}, concepts=["SHORTEST_PATH", "COUNTING_DP", "GRAPH_MODEL"],
        explanation=lines,
        hints=["First find the cheapest total.",
               "Write the cheapest cost to reach each island. Where two ways tie, keep both.",
               "Count only crossings whose total is exactly the cheapest."],
        knobs={"islands": len(scene.islands), "walkways": len(scene.edges), "ties": k},
        answer_value=k, optimal_paths=[list(p) for p in opt], entry="number",
        value_tags={str(v): sorted(t) for v, t in vals.items()},
    )


def grade_build(problem, submitted_edges):
    """Grade an interactive submission (list of [a, b] walkways).
    Returns verdict plus any misconception whose path matches."""
    sub = {frozenset(e) for e in submitted_edges}
    opt = {frozenset(e) for e in zip(problem["answer_path"], problem["answer_path"][1:])}
    if sub == opt:
        return {"correct": True, "misconceptions": []}
    tags = [k for k, pth in problem["misconception_paths"].items()
            if sub == {frozenset(e) for e in zip(pth, pth[1:])}]
    return {"correct": False, "misconceptions": tags}


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render_svg(scene, seed):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="Helvetica, Arial, sans-serif" data-family="shortest_path" data-seed="{seed}">']
    out.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#cfe6f2"/>')
    # wavy water lines for texture (decorative only, light)
    for y in range(NORTH_Y + 20, SOUTH_Y - 10, 28):
        d = " ".join(f"{'M' if x == 0 else 'L'}{x},{y + 3 * math.sin(x / 18)}" for x in range(0, W + 1, 12))
        out.append(f'<path d="{d}" stroke="#b7d7e8" stroke-width="1.2" fill="none"/>')
    out.append(f'<rect class="shore" data-id="N" x="0" y="0" width="{W}" height="{NORTH_Y}" fill="#7f9c6b"/>')
    out.append(f'<rect class="shore" data-id="S" x="0" y="{SOUTH_Y}" width="{W}" height="{H - SOUTH_Y}" fill="#7f9c6b"/>')
    out.append(f'<text x="14" y="38" font-size="18" fill="#ffffff" font-weight="bold">NORTH SHORE</text>')
    out.append(f'<text x="14" y="{SOUTH_Y + 36}" font-size="18" fill="#ffffff" font-weight="bold">SOUTH SHORE</text>')
    for a, b, w in scene.edges:
        p, q = scene.endpoints(a, b)
        r = label_rect(scene, a, b)
        cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        out.append(f'<g class="walkway" data-a="{a}" data-b="{b}" data-w="{w}">'
                   f'<line x1="{p[0]}" y1="{p[1]}" x2="{q[0]}" y2="{q[1]}" stroke="#8a5a2b" stroke-width="7" stroke-linecap="round"/>'
                   f'<line x1="{p[0]}" y1="{p[1]}" x2="{q[0]}" y2="{q[1]}" stroke="#c49a6c" stroke-width="3" stroke-dasharray="4 3"/>'
                   f'<rect x="{r[0]}" y="{r[1]}" width="{LABEL_W}" height="{LABEL_H}" rx="4" fill="#ffffff" stroke="#333333" stroke-width="1"/>'
                   f'<text class="w" x="{cx}" y="{cy + 5}" font-size="14" font-weight="bold" text-anchor="middle" fill="#111111">{w}</text>'
                   f'</g>')
    for iid, (x, y) in scene.islands.items():
        pts = " ".join(f"{px},{py}" for px, py in scene.shapes[iid])
        out.append(f'<g class="island" data-id="{iid}" data-x="{x}" data-y="{y}">'
                   f'<polygon points="{pts}" fill="#a7c47f" stroke="#5d7a3e" stroke-width="2"/>'
                   f'<text x="{x}" y="{y + 6}" font-size="17" font-weight="bold" text-anchor="middle" fill="#1f2d12">{iid}</text>'
                   f'</g>')
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    import sys
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    p = generate(lvl, seed)
    d = asdict(p)
    print(json.dumps({k: v for k, v in d.items() if k != "svg"}, indent=2, ensure_ascii=False))

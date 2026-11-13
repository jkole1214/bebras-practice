"""
Problem family: layered_maze (Mole Tunnels). Folder: mole-tunnels.

Concept targets: SHORTEST_PATH, STATE (the state is a square plus a level).
Source task: Maze (Junior C, Senior C, 2022-23 practice).

Scenario (original): a mole's burrow has two levels of tunnels, drawn side by side. Each square
is tunnel or solid earth. A step to a neighbouring tunnel square on the same level takes 1 minute.
Where both levels have a tunnel at the same square (a climb spot), the mole can climb up or down
there, which takes k minutes. The trip goes from S (upper level) to G.

This follows the idea of the source task (shortest time on two floors where changing floor costs
extra, so a detour through the other floor is only sometimes worth it); the story, wording, rules
(squares of earth instead of walls) and pictures are our own.

One scene model drives both the SVG picture and the solver. The picture carries every square
(data-level, data-r, data-c, data-open and its fill), the S and G marks, the lettered spots and
the climb time. The independent checker rebuilds the burrow from the picture and solves it again
with a 0-1 breadth-first search where a climb is a chain of one-minute links (the generator uses
Dijkstra with a heap).

Question types:
  down     G is on the lower level: fewest minutes? (typed)
  detour   S and G on the upper level; the fastest trip goes down and back up (typed)
  compare  the same, but the climb is dear: sometimes staying on top wins (typed)
  where    at which lettered square does the fastest trip climb down? (choice)
  limit    the climb time is unknown: the largest that keeps the lower route faster (typed)

Misconceptions:
  SWITCH_FREE           adds up the steps of the right route but leaves out the climbs
  SWITCH_AT_ENDS        climbs only at S or G, never partway along
  MERGES_FLOORS         walks the two levels as one map, stepping between them for free
  THROUGH_ROCK          counts the straight distance, as if the mole could dig through earth
  ONE_SWITCH_COST       counts the climb once for a trip that goes down and back up
  ONE_FLOOR             stays on the upper level without checking the lower one
  GOES_DOWN_ANYWAY      takes the lower shortcut even when two climbs cost more than it saves
  FIRST_CLIMB           climbs down at the first climb spot it reaches
  UP_FOR_DOWN           gives the square where the mole climbs back up
  DEAD_END_BELOW        climbs down where the lower tunnel leads nowhere
  TIE_COUNTS_AS_FASTER  takes the climb time at which both ways tie as still faster
"""

import heapq
import json
import random
from collections import deque
from dataclasses import dataclass, field, asdict

CONCEPTS = {q: ["SHORTEST_PATH", "STATE"] for q in ("down", "detour", "compare", "where", "limit")}

MISCONCEPTIONS = {
    "SWITCH_FREE": {"concept": "SHORTEST_PATH",
        "description": "Adds up the steps of the route but leaves out the minutes spent climbing between the levels.",
        "remediation": "Write the trip as pieces: walk, climb, walk. Every piece takes time, the climbs too."},
    "SWITCH_AT_ENDS": {"concept": "STATE",
        "description": "Only thinks of changing level at the start or at the goal, not at a spot partway along the trip.",
        "remediation": "List every square that is tunnel on both levels. Each one is a place the trip could change level."},
    "MERGES_FLOORS": {"concept": "STATE",
        "description": "Treats the two levels as one map, stepping from a tunnel on one level into a tunnel on the other without climbing.",
        "remediation": "Keep a finger on the level the mole is on. It can only change level by climbing at a square that is tunnel on both."},
    "THROUGH_ROCK": {"concept": "SHORTEST_PATH",
        "description": "Counts the straight across-and-down distance, as if the mole could walk through solid earth.",
        "remediation": "Trace the trip square by square through tunnel only, and count the steps you really take."},
    "ONE_FLOOR": {"concept": "STATE",
        "description": "Stays on the starting level the whole way and never checks whether a trip through the other level is faster.",
        "remediation": "Work out both: the time staying on top, and the time with a trip through the lower level. Then compare."},
    "GOES_DOWN_ANYWAY": {"concept": "SHORTEST_PATH",
        "description": "Takes a shortcut through the other level even when the two climbs cost more time than the shortcut saves.",
        "remediation": "Add both climbs to the shortcut, then compare it with staying on one level."},
    "FIRST_CLIMB": {"concept": "SHORTEST_PATH",
        "description": "Changes level at the first climb spot it reaches instead of the spot that makes the whole trip fastest.",
        "remediation": "For each climb spot, add up the whole trip through it. The nearest spot is not always the best."},
    "UP_FOR_DOWN": {"concept": "STATE",
        "description": "Mixes up the square where the trip climbs down with the square where it climbs back up.",
        "remediation": "Follow the trip from the start. Which climb comes first?"},
    "DEAD_END_BELOW": {"concept": "REACHABILITY",
        "description": "Climbs down where the tunnel below looks handy without checking that it leads anywhere.",
        "remediation": "Before climbing down, follow the lower tunnel from there. Can the mole climb back up anywhere else?"},
    "TIE_COUNTS_AS_FASTER": {"concept": "SHORTEST_PATH",
        "description": "Gives the value at which the two ways take exactly the same time, as if a tie were faster.",
        "remediation": "Try that value: do both ways take the same time? Then one is not faster than the other."},
}
# already in the map (from the Maze analysis); this family is the first to use it
USES_EXISTING = ["ONE_SWITCH_COST"]

LADDER = [
    {"level": 1, "question": "down", "n": 5, "climb": [3], "entry": "number",
     "note": "G is on the lower level: find the fastest way down, and count the climb as well as the steps."},
    {"level": 2, "question": "detour", "n": 6, "climb": [3, 4], "entry": "number",
     "note": "S and G are both on top, and a shortcut runs underneath: going down and coming back up are two climbs."},
    {"level": 3, "question": "compare", "n": 6, "climb": [4, 5], "entry": "number",
     "note": "Climbs take longer: work out both ways and see whether the shortcut underneath still pays."},
    {"level": 4, "question": "where", "n": 6, "climb": [3, 4], "entry": "choice",
     "note": "Pick the square where the fastest trip climbs down. The nearest climb spot is not always it."},
    {"level": 5, "question": "limit", "n": 6, "entry": "number",
     "note": "The climb time is unknown: find the longest climb that still makes the trip underneath faster."},
]

ORDER = {
    "down": ["SWITCH_FREE", "SWITCH_AT_ENDS", "MERGES_FLOORS", "THROUGH_ROCK"],
    "detour": ["ONE_SWITCH_COST", "ONE_FLOOR", "SWITCH_FREE", "MERGES_FLOORS", "THROUGH_ROCK"],
    "compare": ["GOES_DOWN_ANYWAY", "ONE_FLOOR", "ONE_SWITCH_COST", "SWITCH_FREE", "MERGES_FLOORS", "THROUGH_ROCK"],
    "where": ["FIRST_CLIMB", "UP_FOR_DOWN", "DEAD_END_BELOW"],
    "limit": ["ONE_SWITCH_COST", "TIE_COUNTS_AS_FASTER"],
}

LEVEL_NAME = ["upper", "lower"]
LETTERS = ["W", "X", "Y", "Z"]
MAXM = 6


def tagsort(q, tags):
    return sorted(set(tags), key=lambda t: (ORDER[q].index(t), t))


def name(cell):
    r, c = cell
    return f"{'abcdef'[c]}{r + 1}"


def prompt(k):
    climb = f"which takes {k} minutes" if k else "which takes the same number of minutes at every square"
    return ("A mole's burrow has two levels of tunnels, drawn side by side: the upper level and the lower level. "
            "Dark squares are solid earth. The mole can step to a neighbouring tunnel square on the same level "
            "(up, down, left or right) in 1 minute. Where both levels have a tunnel at the same square, "
            f"the mole can climb up or down there, {climb}.")


# --------------------------------------------------------------------------
# The burrow and its distances
# --------------------------------------------------------------------------

def nbrs(cell, n):
    r, c = cell
    for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if 0 <= r + dr < n and 0 <= c + dc < n:
            yield (r + dr, c + dc)


def spots(open_):
    n = len(open_[0])
    return {(r, c) for r in range(n) for c in range(n) if open_[0][r][c] and open_[1][r][c]}


def level_dist(open_, lv, src):
    """Steps on one level from src to every tunnel square it can reach."""
    n = len(open_[0])
    if not open_[lv][src[0]][src[1]]:
        return {}
    d, q = {src: 0}, deque([src])
    while q:
        u = q.popleft()
        for v in nbrs(u, n):
            if open_[lv][v[0]][v[1]] and v not in d:
                d[v] = d[u] + 1
                q.append(v)
    return d


def merged_dist(open_, s, g):
    n = len(open_[0])
    ok = lambda v: open_[0][v[0]][v[1]] or open_[1][v[0]][v[1]]
    d, q = {s: 0}, deque([s])
    while q:
        u = q.popleft()
        for v in nbrs(u, n):
            if ok(v) and v not in d:
                d[v] = d[u] + 1
                q.append(v)
    return d.get(g)


def times(open_, s, g, glv, down, up, climb_at=None):
    """Dijkstra over (level, square, climbs so far): fewest minutes to G for each number of climbs."""
    n = len(open_[0])
    cl = spots(open_) if climb_at is None else climb_at & spots(open_)
    start = (0, s, 0)
    best = {start: 0}
    pq = [(0, 0, s, 0)]
    out = {}
    while pq:
        t, lv, u, m = heapq.heappop(pq)
        if best.get((lv, u, m)) != t:
            continue
        if lv == glv and u == g and m not in out:
            out[m] = t
        moves = [((lv, v, m), 1) for v in nbrs(u, n) if open_[lv][v[0]][v[1]]]
        if u in cl and m < MAXM:
            moves.append(((1 - lv, u, m + 1), down if lv == 0 else up))
        for st, w in moves:
            if t + w < best.get(st, 10 ** 9):
                best[st] = t + w
                heapq.heappush(pq, (t + w, st[0], st[1], st[2]))
    return out


# --------------------------------------------------------------------------
# Scene making
# --------------------------------------------------------------------------

def random_burrow(rng, n, p=(0.62, 0.58)):
    return [[[rng.random() < p[lv] for _ in range(n)] for _ in range(n)] for lv in range(2)]


def place(rng, open_, n, glv):
    tops = [(r, c) for r in range(n) for c in range(n) if open_[0][r][c]]
    goals = [(r, c) for r in range(n) for c in range(n) if open_[glv][r][c]]
    if not tops or not goals:
        return None
    s, g = rng.choice(tops), rng.choice(goals)
    if abs(s[0] - g[0]) + abs(s[1] - g[1]) < n - 1:
        return None
    return s, g


def habits_common(open_, s, g, glv, k, ts):
    """Values every question can use; None where a habit does not apply."""
    truth = min(ts.values())
    ms = {m for m, t in ts.items() if t == truth}
    m = next(iter(ms)) if len(ms) == 1 else None
    return truth, m, {
        "SWITCH_FREE": truth - m * k if m else None,
        "MERGES_FLOORS": merged_dist(open_, s, g),
        "THROUGH_ROCK": abs(s[0] - g[0]) + abs(s[1] - g[1]) + (k if glv else 0),
    }


def legs_lines(legs, k_text):
    """legs: list of ('walk', level, a, b, steps) / ('climb', dir, cell). Returns lines and the numbers added."""
    lines, nums = [], []
    for leg in legs:
        if leg[0] == "walk":
            _, lv, a, b, st = leg
            if st == 0:
                continue
            lines.append(f"  walk {LEVEL_NAME[lv]} {name(a)}→{name(b)}: {st}")
            nums.append(str(st))
        else:
            _, d, cell = leg
            lines.append(f"  climb {d} at {name(cell)}: {k_text}")
            nums.append(k_text)
    return lines, nums


def route_down(open_, s, g, k):
    """Best one-climb route from S (upper) to G (lower): (time, x)."""
    top, low = level_dist(open_, 0, s), level_dist(open_, 1, g)
    c = [(top[x] + k + low[x], x) for x in sorted(spots(open_)) if x in top and x in low]
    return min(c) if c else None


def route_pairs(open_, s, g, k):
    """Every down-at-x, up-at-y trip (S and G upper): {(x, y): time}."""
    top_s, top_g = level_dist(open_, 0, s), level_dist(open_, 0, g)
    out = {}
    for x in sorted(spots(open_)):
        if x not in top_s:
            continue
        low = level_dist(open_, 1, x)
        for y in sorted(spots(open_)):
            if y != x and y in low and y in top_g:
                out[(x, y)] = top_s[x] + k + low[y] + k + top_g[y]
    return out


def pair_legs(open_, s, g, x, y, k_text):
    top_s, top_g, low = level_dist(open_, 0, s), level_dist(open_, 0, g), level_dist(open_, 1, x)
    return legs_lines([("walk", 0, s, x, top_s[x]), ("climb", "down", x), ("walk", 1, x, y, low[y]),
                       ("climb", "up", y), ("walk", 0, y, g, top_g[y])], k_text)


def value_tags(q, truth, wrong):
    vt = {}
    for tag, v in wrong.items():
        if v is None:
            continue
        if v == truth:
            return None
        vt.setdefault(v, []).append(tag)
    return {str(v): tagsort(q, t) for v, t in sorted(vt.items())}


def problem(cfg, q, seed, scene, k, question, **kw):
    svg = render(scene, k, seed)
    return Problem(family="layered_maze", level=cfg["level"], question_type=q, seed=seed, scene=scene, svg=svg,
                   prompt=prompt(k), question=question, concepts=CONCEPTS[q], **kw)


def scene_of(open_, s, g, glv, k, spots_=None):
    sc = {"n": len(open_[0]), "upper": [[int(x) for x in row] for row in open_[0]],
          "lower": [[int(x) for x in row] for row in open_[1]], "start": list(s), "goal": list(g),
          "goal_level": glv, "climb": k}
    if spots_:
        sc["spots"] = {l: list(c) for l, c in spots_.items()}
    return sc


def make_down(rng, cfg, seed):
    n = cfg["n"]
    for _ in range(4000):
        k = rng.choice(cfg["climb"])
        open_ = random_burrow(rng, n)
        sg = place(rng, open_, n, 1)
        if not sg:
            continue
        s, g = sg
        ts = times(open_, s, g, 1, k, k)
        if not ts:
            continue
        truth, m, wrong = habits_common(open_, s, g, 1, k, ts)
        if m != 1 or truth < 6:
            continue
        ends = times(open_, s, g, 1, k, k, climb_at={s, g})
        wrong["SWITCH_AT_ENDS"] = min(ends.values()) if ends else None
        if wrong["SWITCH_AT_ENDS"] is None:
            continue
        vt = value_tags("down", truth, wrong)
        if not vt or len(vt) < 3:
            continue
        t, x = route_down(open_, s, g, k)
        assert t == truth
        top, low = level_dist(open_, 0, s), level_dist(open_, 1, g)
        lines, nums = legs_lines([("walk", 0, s, x, top[x]), ("climb", "down", x), ("walk", 1, x, g, low[x])], str(k))
        expl = ["G is on the lower level, so the mole must climb down once. Try each climb spot and keep the fastest:"]
        expl += lines + [f"  total {' + '.join(nums)} = {truth}"]
        if wrong["SWITCH_AT_ENDS"] is not None and x not in (s, g):
            expl.append(f"Climbing at {'S' if s in spots(open_) else 'G'} instead takes {wrong['SWITCH_AT_ENDS']} minutes.")
        expl.append(f"So the fastest way takes {truth} minutes.")
        return problem(cfg, "down", seed, scene_of(open_, s, g, 1, k), k,
                       "The mole starts at S on the upper level and wants to reach G on the lower level. "
                       "What is the fewest minutes the trip can take?",
                       options=[], answer_index=-1, answer_value=truth, entry="number", distractors=[], value_tags=vt,
                       explanation=expl,
                       hints=["Find the squares that are tunnel on both levels. Those are the only places to climb down.",
                              "For each climb spot: steps on top to reach it, plus the climb, plus steps below to G.",
                              "Don't forget to add the minutes for the climb."],
                       knobs={"n": n, "climb": k})
    return None


def walled_burrow(rng, n):
    """Upper level with a wall of earth across it and one gap near an edge, so the trip on top bends round."""
    open_ = random_burrow(rng, n, (0.78, 0.6))
    b = rng.randrange(2, n - 2)
    gap = rng.choice([0, 1, n - 2, n - 1])
    across = rng.random() < 0.5
    for i in range(n):
        r, c = (b, i) if across else (i, b)
        open_[0][r][c] = i == gap
    far = [i for i in range(n) if abs(i - gap) >= n // 2]
    cc = rng.choice(far)
    for j in range(b - 1, b + 2):          # a lower tunnel that passes under the wall
        r, c = (j, cc) if across else (cc, j)
        open_[1][r][c] = True
        if j != b:
            open_[0][r][c] = True
    sides = ([(r, c) for r in range(b) for c in far], [(r, c) for r in range(b + 1, n) for c in far])
    if not across:
        sides = tuple([(c, r) for r, c in side] for side in sides)
    return open_, sides


def detour_scene(rng, cfg, n, k, want):
    """S and G on the upper level, on either side of a wall of earth."""
    open_, sides = walled_burrow(rng, n)
    a = [x for x in sides[0] if open_[0][x[0]][x[1]]]
    z = [x for x in sides[1] if open_[0][x[0]][x[1]]]
    if not a or not z:
        return None
    s, g = rng.choice(a), rng.choice(z)
    if rng.random() < 0.5:
        s, g = g, s
    ts = times(open_, s, g, 0, k, k)
    if 0 not in ts or not any(m >= 2 for m in ts):
        return None
    return open_, s, g, ts


def detour_expl(open_, s, g, k, ts, truth):
    stay = ts[0]
    pairs = route_pairs(open_, s, g, k)
    (x, y) = min(pairs, key=lambda p: (pairs[p], p))
    under = pairs[(x, y)]
    lines, nums = pair_legs(open_, s, g, x, y, str(k))
    expl = [f"Staying on the upper level takes {stay} minutes.",
            "The fastest trip through the lower tunnels climbs down and back up:"]
    expl += lines + [f"  total {' + '.join(nums)} = {under}"]
    if under < stay:
        expl.append(f"{under} is less than {stay}, so the trip underneath is faster, even with two climbs.")
    else:
        expl.append(f"{under} is more than {stay}: the two climbs cost more than the shortcut saves, so the mole stays on top.")
    expl.append(f"So the fastest way takes {truth} minutes.")
    return expl, (x, y)


def make_detour(rng, cfg, seed):
    n = cfg["n"]
    for _ in range(6000):
        k = rng.choice(cfg["climb"])
        got = detour_scene(rng, cfg, n, k, "detour")
        if not got:
            continue
        open_, s, g, ts = got
        truth, m, wrong = habits_common(open_, s, g, 0, k, ts)
        if m != 2 or ts[0] - truth < 2:
            continue
        one = times(open_, s, g, 0, k, 0)
        wrong.update({"ONE_FLOOR": ts[0], "ONE_SWITCH_COST": min(one.values())})
        vt = value_tags("detour", truth, wrong)
        if not vt or len(vt) < 3:
            continue
        expl, _ = detour_expl(open_, s, g, k, ts, truth)
        return problem(cfg, "detour", seed, scene_of(open_, s, g, 0, k), k,
                       "The mole starts at S and wants to reach G. Both are on the upper level. "
                       "What is the fewest minutes the trip can take?",
                       options=[], answer_index=-1, answer_value=truth, entry="number", distractors=[], value_tags=vt,
                       explanation=expl,
                       hints=["First count the steps if the mole stays on the upper level.",
                              "Now look below: is there a shorter way through the lower tunnels between two climb spots?",
                              "A trip underneath climbs down and then climbs back up: that is two climbs."],
                       knobs={"n": n, "climb": k})
    return None


def make_compare(rng, cfg, seed):
    n = cfg["n"]
    want = "stay" if rng.random() < 0.5 else "detour"
    for _ in range(8000):
        k = rng.choice(cfg["climb"])
        got = detour_scene(rng, cfg, n, k, want)
        if not got:
            continue
        open_, s, g, ts = got
        truth, m, wrong = habits_common(open_, s, g, 0, k, ts)
        one = min(times(open_, s, g, 0, k, 0).values())
        under = min(t for mm, t in ts.items() if mm >= 2)
        if want == "stay":
            if m != 0 or not one < truth:
                continue
            wrong.update({"GOES_DOWN_ANYWAY": under, "ONE_SWITCH_COST": one})
        else:
            if m != 2 or ts[0] - truth > 2:
                continue
            wrong.update({"ONE_FLOOR": ts[0], "ONE_SWITCH_COST": one})
        vt = value_tags("compare", truth, wrong)
        if not vt or len(vt) < 3:
            continue
        expl, _ = detour_expl(open_, s, g, k, ts, truth)
        return problem(cfg, "compare", seed, scene_of(open_, s, g, 0, k), k,
                       "The mole starts at S and wants to reach G. Both are on the upper level. "
                       "What is the fewest minutes the trip can take?",
                       options=[], answer_index=-1, answer_value=truth, entry="number", distractors=[], value_tags=vt,
                       explanation=expl,
                       hints=["Work out two trips: one that stays on the upper level, and the best one that goes underneath.",
                              "The trip underneath pays for two climbs, down and back up.",
                              "Pick whichever trip is faster."],
                       knobs={"n": n, "climb": k, "best": want})
    return None


def where_tags(open_, s, cell, first, up):
    t = []
    if cell == first:
        t.append("FIRST_CLIMB")
    if cell == up:
        t.append("UP_FOR_DOWN")
    low = level_dist(open_, 1, cell)
    if not (spots(open_) - {cell}) & set(low):
        t.append("DEAD_END_BELOW")
    return t


def make_where(rng, cfg, seed):
    n = cfg["n"]
    for _ in range(20000):
        k = rng.choice(cfg["climb"])
        got = detour_scene(rng, cfg, n, k, "detour")
        if not got:
            continue
        open_, s, g, ts = got
        open_[1][s[0]][s[1]] = open_[1][g[0]][g[1]] = False     # no climbing at S or G
        ts = times(open_, s, g, 0, k, k)
        if 0 not in ts:
            continue
        truth, m, _ = habits_common(open_, s, g, 0, k, ts)
        cl = spots(open_)
        if m != 2:
            continue
        pairs = route_pairs(open_, s, g, k)
        best = [p for p, t in pairs.items() if t == truth]
        downs, ups = {p[0] for p in best}, {p[1] for p in best}
        if len(downs) != 1 or len(ups) != 1:
            continue
        x, y = best[0]
        top = level_dist(open_, 0, s)
        reach = sorted((top[c], c) for c in cl if c in top)
        if len(reach) < 2 or reach[0][0] == reach[1][0]:
            continue
        first = reach[0][1]
        if first == x:
            continue
        cand = {c: where_tags(open_, s, c, first, y) for c in cl if c in top and c != x}
        cand = {c: t for c, t in cand.items() if t}
        if len(cand) < 3 or not any("DEAD_END_BELOW" in t for t in cand.values()):
            continue
        pick = [first] + ([y] if y != first else [])
        rest = sorted(c for c in cand if c not in pick)
        rng.shuffle(rest)
        rest.sort(key=lambda c: "DEAD_END_BELOW" not in cand[c])
        pick += rest[:3 - len(pick)]
        if not any("DEAD_END_BELOW" in cand[c] for c in pick):
            continue
        chosen = sorted(pick + [x])
        rng.shuffle(chosen)             # letters at random, so the answer's letter tells nothing
        letters = dict(zip(LETTERS, chosen))
        lab = {c: l for l, c in letters.items()}
        lines, nums = pair_legs(open_, s, g, x, y, str(k))
        expl = [f"Staying on the upper level takes {ts[0]} minutes. The fastest trip goes underneath:"]
        expl += lines + [f"  total {' + '.join(nums)} = {truth}"]
        if first != y:
            fl = level_dist(open_, 1, first)
            onward = [pairs[(first, z)] for z in cl if (first, z) in pairs]
            if onward:
                expl.append(f"Climbing down at {lab[first]}, the nearest spot, the best trip takes {min(onward)} minutes.")
            else:
                expl.append(f"{lab[first]} is the nearest spot, but the tunnel below it leads to no other climb spot.")
        expl.append(f"{lab[y]} is where the mole climbs back up." if y in lab else "")
        expl = [e for e in expl if e]
        expl.append(f"So the mole climbs down at {lab[x]}.")
        opts = LETTERS[:]
        return problem(cfg, "where", seed, scene_of(open_, s, g, 0, k, letters), k,
                       "S and G are both on the upper level. The fastest trip climbs down once and back up once. "
                       "At which lettered square does the mole climb down?",
                       options=opts, answer_index=opts.index(lab[x]), answer_value=lab[x], entry="choice",
                       distractors=[{"option": lab[c], "misconceptions": tagsort("where", cand[c])} for c in chosen if c != x],
                       value_tags={}, explanation=expl,
                       hints=["The letters are on both levels. Each lettered square is a place to climb.",
                              "For a letter, follow the lower tunnel from it: where can the mole climb back up?",
                              "Add up the whole trip for each letter: walk, climb down, walk, climb up, walk."],
                       knobs={"n": n, "climb": k})
    return None


def make_limit(rng, cfg, seed):
    n = cfg["n"]
    for _ in range(20000):
        got = detour_scene(rng, cfg, n, 1, "detour")
        if not got:
            continue
        open_, s, g, ts = got
        two = ts.get(2)
        if two is None or any(t < two for mm, t in ts.items() if mm >= 2):
            continue        # with more climbs the trip must never be cheaper, at any climb time
        if any(t == two for mm, t in ts.items() if mm > 2):
            continue
        steps = two - 2
        gap = ts[0] - steps
        if gap % 2 or not 4 <= gap <= 12:
            continue
        truth = gap // 2 - 1
        wrong = {"ONE_SWITCH_COST": gap - 1, "TIE_COUNTS_AS_FASTER": gap // 2}
        vt = {str(truth + 1): ["TIE_COUNTS_AS_FASTER"], str(gap - 1): ["ONE_SWITCH_COST"],
              str(gap): ["ONE_SWITCH_COST", "TIE_COUNTS_AS_FASTER"]}
        if len(vt) < 3:
            continue
        pairs = route_pairs(open_, s, g, 0)
        x, y = min(pairs, key=lambda p: (pairs[p], p))
        assert pairs[(x, y)] == steps
        lines, nums = pair_legs(open_, s, g, x, y, "?")
        walk = [v for v in nums if v != "?"]
        expl = [f"Staying on the upper level takes {ts[0]} minutes.",
                "The shortest trip underneath, with ? for one climb:"] + lines
        expl.append(f"  {' + '.join(walk) + ' = ' if len(walk) > 1 else ''}{steps} steps, plus 2 climbs")
        expl.append(f"It is faster when {steps} + 2 × climb < {ts[0]}, so 2 × climb < {gap}.")
        expl.append(f"A {gap // 2}-minute climb ties: {steps} + {gap} = {ts[0]}, which is not faster.")
        expl.append(f"So the longest climb is {truth} minutes.")
        return problem(cfg, "limit", seed, scene_of(open_, s, g, 0, None), None,
                       "S and G are both on the upper level. The mole can stay on the upper level or go through the lower "
                       "tunnels. What is the longest a climb can take, in whole minutes, for the trip underneath to still be faster?",
                       options=[], answer_index=-1, answer_value=truth, entry="number", distractors=[], value_tags=vt,
                       explanation=expl,
                       hints=["Count the steps staying on the upper level.",
                              "Count the steps of the shortest trip underneath. It climbs twice: down and back up.",
                              "The trip underneath must take fewer minutes, not the same."],
                       knobs={"n": n, "gap": gap})
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
    make = {"down": make_down, "detour": make_detour, "compare": make_compare,
            "where": make_where, "limit": make_limit}[cfg["question"]]
    p = make(rng, cfg, seed)
    if not p:
        raise RuntimeError(f"layered_maze generation failed at level {level}")
    return p


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

FONT = 'font-family="Helvetica, Arial, sans-serif"'
TUNNEL, EARTH = "#f3e2bd", "#6f5440"
GRID = 168


def render(sc, k, seed):
    n = sc["n"]
    cs = GRID / n
    W, H = 420, 252
    x0s = [30, 236]
    y0 = 52
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" {FONT} '
           f'class="tunnels" data-family="layered_maze" data-n="{n}" data-seed="{seed}">',
           f'<rect x="0" y="0" width="{W}" height="{H}" rx="10" fill="#e9dcc6"/>']
    lab = {tuple(c): l for l, c in (sc.get("spots") or {}).items()}
    for lv in range(2):
        x0 = x0s[lv]
        grid = sc["upper" if lv == 0 else "lower"]
        out.append(f'<text x="{x0 + GRID / 2}" y="20" font-size="14" font-weight="bold" text-anchor="middle" '
                   f'fill="#1f2933">{LEVEL_NAME[lv].capitalize()} level</text>')
        for c in range(n):
            out.append(f'<text x="{x0 + cs * (c + .5):.1f}" y="{y0 - 6}" font-size="11" text-anchor="middle" fill="#52606d">{"abcdef"[c]}</text>')
        for r in range(n):
            out.append(f'<text x="{x0 - 8}" y="{y0 + cs * (r + .5) + 4:.1f}" font-size="11" text-anchor="middle" fill="#52606d">{r + 1}</text>')
        for r in range(n):
            for c in range(n):
                o = grid[r][c]
                out.append(f'<rect class="cell" data-level="{lv}" data-r="{r}" data-c="{c}" data-open="{o}" '
                           f'x="{x0 + c * cs:.1f}" y="{y0 + r * cs:.1f}" width="{cs:.1f}" height="{cs:.1f}" '
                           f'fill="{TUNNEL if o else EARTH}" stroke="#4a3728" stroke-width="1"/>')
        for nm, cell, mlv, col in (("S", sc["start"], 0, "#2f5dff"), ("G", sc["goal"], sc["goal_level"], "#1e8a5a")):
            if mlv != lv:
                continue
            cx, cy = x0 + cs * (cell[1] + .5), y0 + cs * (cell[0] + .5)
            out.append(f'<g class="mark" data-name="{nm}" data-level="{lv}" data-r="{cell[0]}" data-c="{cell[1]}">'
                       f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{cs * .36:.1f}" fill="{col}"/>'
                       f'<text x="{cx:.1f}" y="{cy + 5:.1f}" font-size="14" font-weight="bold" text-anchor="middle" fill="#ffffff">{nm}</text></g>')
        for cell, l in sorted(lab.items()):
            cx, cy = x0 + cs * (cell[1] + .5), y0 + cs * (cell[0] + .5)
            out.append(f'<g class="spot" data-letter="{l}" data-level="{lv}" data-r="{cell[0]}" data-c="{cell[1]}">'
                       f'<rect x="{cx - cs * .34:.1f}" y="{cy - cs * .34:.1f}" width="{cs * .68:.1f}" height="{cs * .68:.1f}" rx="4" '
                       f'fill="#f2a541" stroke="#7a4a00" stroke-width="1.5"/>'
                       f'<text x="{cx:.1f}" y="{cy + 5:.1f}" font-size="14" font-weight="bold" text-anchor="middle" fill="#1f2933">{l}</text></g>')
    kt = "?" if k is None else str(k)
    out.append(f'<text class="climb" data-climb="{kt}" x="{W / 2}" y="{H - 14}" font-size="13" text-anchor="middle" '
               f'fill="#1f2933">Step: 1 minute · Climb up or down: {kt} minute{"" if k == 1 else "s"}</text>')
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    import sys
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print(json.dumps({k: v for k, v in asdict(generate(lvl, sd)).items() if k not in ("svg", "scene")}, indent=2, ensure_ascii=False))

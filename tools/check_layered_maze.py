"""
Independent checker for layered_maze (Mole Tunnels) problems.

Does not import the generator. It rebuilds the burrow from the SVG picture (every square's
data-level, data-r, data-c, data-open and its fill colour; the S and G marks; the lettered spots;
the climb time) and solves again with different code: a 0-1 breadth-first search in which a climb
of k minutes is a chain of k one-minute links (the generator runs Dijkstra with a heap). Every
habit is re-derived by running the same search on a changed burrow or with changed climb costs:
  MERGES_FLOORS   one level that is tunnel wherever either level is
  THROUGH_ROCK    both levels all tunnel
  SWITCH_AT_ENDS  climbing allowed only at S's and G's squares
  ONE_SWITCH_COST climbing down costs k, climbing up costs nothing
For the climb-time limit it tries climb times 1, 2, 3, ... in turn instead of using the formula.
It also follows the walk and climb lines of the explanation and checks each against the burrow.

Usage: python3 check_layered_maze.py L1-1000.js [...]   (files from mole-tunnels/)
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import deque

NS = "{http://www.w3.org/2000/svg}"
TUNNEL, EARTH = "#f3e2bd", "#6f5440"
LV = {"upper": 0, "lower": 1}
INF = 10 ** 9


def parse(svg, errs):
    root = ET.fromstring(svg)
    n = int(root.get("data-n"))
    grid = [[[None] * n for _ in range(n)] for _ in range(2)]
    marks, spots = {}, {}
    climb = None
    for el in root.iter():
        cls = (el.get("class") or "").split()
        if el.tag == NS + "rect" and "cell" in cls:
            lv, r, c, o = (int(el.get(a)) for a in ("data-level", "data-r", "data-c", "data-open"))
            if el.get("fill") != (TUNNEL if o else EARTH):
                errs.append(f"square {lv},{r},{c} is drawn in the wrong colour")
            if grid[lv][r][c] is not None:
                errs.append("a square is drawn twice")
            grid[lv][r][c] = bool(o)
        elif el.tag == NS + "g" and "mark" in cls:
            marks[el.get("data-name")] = (int(el.get("data-level")), (int(el.get("data-r")), int(el.get("data-c"))))
            if el.find(NS + "text").text != el.get("data-name"):
                errs.append("a mark shows the wrong letter")
        elif el.tag == NS + "g" and "spot" in cls:
            spots.setdefault(el.get("data-letter"), set()).add((int(el.get("data-level")), int(el.get("data-r")), int(el.get("data-c"))))
            if el.find(NS + "text").text != el.get("data-letter"):
                errs.append("a spot shows the wrong letter")
        elif el.tag == NS + "text" and "climb" in cls:
            climb = el.get("data-climb")
            if not el.text.endswith(f"Climb up or down: {climb} minute{'' if climb == '1' else 's'}"):
                errs.append("the climb time text differs from data-climb")
    if any(x is None for lv in grid for row in lv for x in row):
        errs.append("a square is missing from the picture")
    cells = {}
    for l, at in spots.items():
        cs = {(r, c) for _, r, c in at}
        if len(cs) != 1 or {lv for lv, _, _ in at} != {0, 1}:
            errs.append(f"spot {l} is not on the same square on both levels")
        cells[l] = next(iter(cs))
    return n, grid, marks, cells, climb


def solve(grid, start, goal, kd, ku, allowed=None, maxm=6):
    """0-1 BFS. start, goal: (level, (r, c)). Returns {climbs: fewest minutes} at goal."""
    n = len(grid[0])
    both = {(r, c) for r in range(n) for c in range(n) if grid[0][r][c] and grid[1][r][c]}
    if allowed is not None:
        both &= allowed
    lv0, s = start
    first = ("p", lv0, s, 0, 0)
    dist = {first: 0}
    dq = deque([first])
    out = {}
    while dq:
        node = dq.popleft()
        t = dist[node]
        kind, lv, (r, c), m, left = node
        nxt = []
        if kind == "c":
            nxt.append((("p", lv, (r, c), m, 0) if left == 0 else ("c", lv, (r, c), m, left - 1), 0 if left == 0 else 1))
        else:
            if (lv, (r, c)) == goal:
                out[m] = min(out.get(m, INF), t)
            for rr, cc in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
                if 0 <= rr < n and 0 <= cc < n and grid[lv][rr][cc]:
                    nxt.append((("p", lv, (rr, cc), m, 0), 1))
            if (r, c) in both and m < maxm:
                cost = kd if lv == 0 else ku
                nxt.append((("p", 1 - lv, (r, c), m + 1, 0), 0) if cost == 0 else (("c", 1 - lv, (r, c), m + 1, cost - 1), 1))
        for v, w in nxt:
            if t + w < dist.get(v, INF):
                dist[v] = t + w
                (dq.appendleft if w == 0 else dq.append)(v)
    return out


def steps(grid, lv, a, b):
    """Steps on one level only (a search with climbing switched off)."""
    got = solve(grid, (lv, a), (lv, b), 1, 1, allowed=set())
    return got.get(0)


def flood(grid, lv, a):
    n = len(grid[0])
    seen, st = {a}, [a]
    while st:
        r, c = st.pop()
        for v in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if 0 <= v[0] < n and 0 <= v[1] < n and grid[lv][v[0]][v[1]] and v not in seen:
                seen.add(v)
                st.append(v)
    return seen


def cell(name):
    return (int(name[1:]) - 1, "abcdef".index(name[0]))


def check_legs(expl, grid, s, goal, k, errs):
    """Follow the walk/climb lines; they must join S to the goal. Returns the numbers they add."""
    n = len(grid[0])
    pos, nums = (0, s), []
    for line in expl:
        w = re.fullmatch(r"  walk (upper|lower) ([a-f]\d)→([a-f]\d): (\d+)", line)
        c = re.fullmatch(r"  climb (down|up) at ([a-f]\d): (\S+)", line)
        if w:
            lv, a, b, st = LV[w.group(1)], cell(w.group(2)), cell(w.group(3)), int(w.group(4))
            if pos != (lv, a) or steps(grid, lv, a, b) != st or st == 0:
                errs.append(f"explanation line '{line.strip()}' does not fit the burrow")
            pos = (lv, b)
            nums.append(str(st))
        elif c:
            lv, at = (0 if c.group(1) == "down" else 1), cell(c.group(2))
            if pos != (lv, at) or not (grid[0][at[0]][at[1]] and grid[1][at[0]][at[1]]) or c.group(3) != k:
                errs.append(f"explanation line '{line.strip()}' does not fit the burrow")
            pos = (1 - lv, at)
            nums.append(c.group(3))
    if pos != goal:
        errs.append("the explanation's trip does not end at G")
    return nums


def tags_of(wrong, truth, errs):
    out = {}
    for tag, v in wrong.items():
        if v is None:
            continue
        if v == truth:
            errs.append(f"habit {tag} gives the right answer")
        out.setdefault(str(v), set()).add(tag)
    return out


def check(p):
    try:
        return check_one(p)
    except (ValueError, KeyError, TypeError, AttributeError, ET.ParseError) as e:
        return [f"could not check: {e!r}"]


def check_one(p):
    if p["family"] != "layered_maze":
        return ["wrong family"]
    errs = []
    n, grid, marks, letters, climb = parse(p["svg"], errs)
    sc, q, expl = p["scene"], p["question_type"], p["explanation"]
    if set(marks) != {"S", "G"} or marks["S"][0] != 0:
        return errs + ["S and G marks are missing or S is not on the upper level"]
    s = marks["S"][1]
    goal = marks["G"]
    if (sc["upper"] != [[int(x) for x in row] for row in grid[0]] or sc["lower"] != [[int(x) for x in row] for row in grid[1]]
            or tuple(sc["start"]) != s or tuple(sc["goal"]) != goal[1] or sc["goal_level"] != goal[0]):
        errs.append("scene differs from the picture")
    if str(sc["climb"] if sc["climb"] is not None else "?") != climb:
        errs.append("scene climb time differs from the picture")
    if {l: tuple(c) for l, c in (sc.get("spots") or {}).items()} != letters:
        errs.append("scene spots differ from the picture")
    k = None if climb == "?" else int(climb)
    if k is not None and f"which takes {k} minutes" not in p["prompt"]:
        errs.append("prompt climb time differs from the picture")
    if (goal[0] == 1) != (q == "down"):
        errs.append("G is on the wrong level for this question")

    if q in ("down", "detour", "compare"):
        ts = solve(grid, (0, s), goal, k, k)
        truth = min(ts.values())
        ms = {m for m, t in ts.items() if t == truth}
        if p["answer_value"] != truth or p["entry"] != "number" or p["options"]:
            errs.append(f"answer {p['answer_value']} != recomputed {truth}")
        if len(ms) != 1:
            return errs + ["fastest trips differ in how many climbs they make"]
        m = ms.pop()
        union = [[[a or b for a, b in zip(r0, r1)] for r0, r1 in zip(grid[0], grid[1])], [[False] * n for _ in range(n)]]
        allopen = [[[True] * n for _ in range(n)] for _ in range(2)]
        wrong = {"SWITCH_FREE": truth - m * k if m else None,
                 "MERGES_FLOORS": min(solve(union, (0, s), (0, goal[1]), 0, 0).values()),
                 "THROUGH_ROCK": min(solve(allopen, (0, s), goal, k, k).values())}
        if q == "down":
            if m != 1:
                errs.append("the fastest trip should climb once")
            ends = solve(grid, (0, s), goal, k, k, allowed={s, goal[1]})
            wrong["SWITCH_AT_ENDS"] = min(ends.values()) if ends else None
        else:
            one = min(solve(grid, (0, s), goal, k, 0).values())
            under = min(t for mm, t in ts.items() if mm >= 2)
            if q == "detour" and m != 2:
                errs.append("the fastest trip should go underneath")
            if q == "compare" and m not in (0, 2):
                errs.append("the fastest trip should stay on top or go down once and back")
            if m == 0:
                wrong.update({"GOES_DOWN_ANYWAY": under, "ONE_SWITCH_COST": one})
            else:
                wrong.update({"ONE_FLOOR": ts[0], "ONE_SWITCH_COST": one})
        want = tags_of(wrong, truth, errs)
        if {v: set(t) for v, t in p["value_tags"].items()} != want:
            errs.append(f"typed-number tags {p['value_tags']} differ from recomputed {want}")
        nums = check_legs(expl, grid, s, goal, str(k), errs)
        tot = [l for l in expl if l.startswith("  total ")]
        if len(tot) != 1 or tot[0] != f"  total {' + '.join(nums)} = {sum(map(int, nums))}":
            errs.append("the explanation's total does not add up")
        if sum(map(int, nums)) != (truth if m else wrong["GOES_DOWN_ANYWAY"]):
            errs.append("the explanation's trip is not the fastest")
        if q != "down" and f"Staying on the upper level takes {ts[0]} minutes." not in expl:
            errs.append("the explanation does not give the time on top")
        if expl[-1] != f"So the fastest way takes {truth} minutes.":
            errs.append("the explanation does not end with the answer")

    elif q == "where":
        ts = solve(grid, (0, s), goal, k, k)
        truth = min(ts.values())
        if {m for m, t in ts.items() if t == truth} != {2}:
            errs.append("the fastest trip should climb down once and back up once")
        if p["options"] != sorted(letters) or len(letters) != 4:
            errs.append("options are not the four lettered spots")
        both = {(r, c) for r in range(n) for c in range(n) if grid[0][r][c] and grid[1][r][c]}
        top = {x: steps(grid, 0, s, x) for x in both}
        via = {}
        for l, x in letters.items():
            if x not in both:
                errs.append(f"spot {l} is not a climb spot")
                continue
            rest = solve(grid, (1, x), goal, k, k)
            via[l] = top[x] + k + min(rest.values()) if top[x] is not None and rest else INF
        ans = [l for l, t in via.items() if t == truth]
        if len(ans) != 1:
            return errs + [f"{len(ans)} lettered spots start a fastest trip"]
        a = ans[0]
        if p["answer_value"] != a or p["options"][p["answer_index"]] != a:
            errs.append("marked option is not the recomputed spot")
        others = [x for x in both if x != letters[a] and top[x] is not None
                  and top[x] + k + min(solve(grid, (1, x), goal, k, k).values() or [INF]) == truth]
        if others:
            errs.append("an unlettered spot also starts a fastest trip")
        x = letters[a]
        ups = [y for y in both if y != x and top[x] + k + (steps(grid, 1, x, y) or INF) + k + (steps(grid, 0, y, goal[1]) or INF) == truth]
        reach = sorted((d, y) for y, d in top.items() if d is not None)
        first = reach[0][1] if len(reach) > 1 and reach[0][0] < reach[1][0] else None
        if len(ups) != 1 or first is None:
            errs.append("the climb-up spot or the nearest spot is not unique")
        got = {d["option"]: set(d["misconceptions"]) for d in p["distractors"]}
        if set(got) != set(letters) - {a}:
            errs.append("every wrong option needs tags")
        for l, t in got.items():
            y = letters[l]
            w = set()
            if y == first:
                w.add("FIRST_CLIMB")
            if ups and y == ups[0]:
                w.add("UP_FOR_DOWN")
            if not (both - {y}) & flood(grid, 1, y):
                w.add("DEAD_END_BELOW")
            if not t or t != w:
                errs.append(f"option {l} tagged {sorted(t)}, recomputed {sorted(w)}")
        check_legs(expl, grid, s, goal, str(k), errs)
        if expl[-1] != f"So the mole climbs down at {a}.":
            errs.append("the explanation does not end with the answer")

    elif q == "limit":
        stay = solve(grid, (0, s), goal, 1, 1).get(0)
        faster, tie, one_f, one_t = [], [], [], []
        for kk in range(1, 30):
            under = min([t for mm, t in solve(grid, (0, s), goal, kk, kk).items() if mm >= 2] or [INF])
            once = min([t for mm, t in solve(grid, (0, s), goal, kk, 0).items() if mm >= 2] or [INF])
            faster += [kk] if under < stay else []
            tie += [kk] if under <= stay else []
            one_f += [kk] if once < stay else []
            one_t += [kk] if once <= stay else []
            if under > stay and once > stay:
                break           # longer climbs only make both trips underneath slower
        if not faster or faster != list(range(1, max(faster) + 1)):
            return errs + ["no climb time makes the trip underneath faster"]
        truth = max(faster)
        if p["answer_value"] != truth or p["entry"] != "number":
            errs.append(f"answer {p['answer_value']} != recomputed {truth}")
        want = {}
        for v, tag in ((max(tie), {"TIE_COUNTS_AS_FASTER"}), (max(one_f), {"ONE_SWITCH_COST"}),
                       (max(one_t), {"ONE_SWITCH_COST", "TIE_COUNTS_AS_FASTER"})):
            if v == truth:
                errs.append(f"habit {sorted(tag)} gives the right answer")
            want.setdefault(str(v), set()).update(tag)
        if {v: set(t) for v, t in p["value_tags"].items()} != want:
            errs.append(f"typed-number tags {p['value_tags']} differ from recomputed {want}")
        check_legs(expl, grid, s, goal, "?", errs)
        if f"Staying on the upper level takes {stay} minutes." not in expl:
            errs.append("the explanation does not give the time on top")
        if expl[-1] != f"So the longest climb is {truth} minutes.":
            errs.append("the explanation does not end with the answer")
    else:
        errs.append(f"unknown question {q}")
    return errs


if __name__ == "__main__":
    bad = 0
    for path in sys.argv[1:]:
        text = open(path).read()
        rec = json.loads(text[text.index("{"):text.rindex("}") + 1])
        e = check(rec)
        if e:
            bad += 1
            print(path, e)
    print(f"{len(sys.argv) - 1 - bad} ok, {bad} bad")

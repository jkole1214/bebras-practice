"""
Independent checker for grid_routes problems.

Does not import the generator. It rebuilds the grid from the SVG picture:
each intersection's state comes from its drawn mark (X for closed, square for
the bakery, diamond for the library), and is compared with data-state. The
grid graph is rebuilt with networkx and the shortest-route length and count
are recomputed by enumerating all shortest paths.
"""

import json
import sys
import xml.etree.ElementTree as ET
import networkx as nx

NS = "{http://www.w3.org/2000/svg}"


def parse(svg):
    root = ET.fromstring(svg)
    R, C = int(root.get("data-rows")), int(root.get("data-cols"))
    nodes, errs = {}, []
    for g in root.iter(NS + "g"):
        if g.get("class") != "node":
            continue
        r, c = int(g.get("data-r")), int(g.get("data-c"))
        marks = {e.get("class") for e in g if e.get("class")}
        drawn = ("closed" if "xmark" in marks else "start" if "startmark" in marks
                 else "goal" if "goalmark" in marks else "open")
        if drawn != g.get("data-state"):
            errs.append(f"({r},{c}) drawn as {drawn} but data says {g.get('data-state')}")
        nodes[(r, c)] = drawn
    if len(nodes) != R * C:
        errs.append(f"expected {R * C} intersections, found {len(nodes)}")
    return R, C, nodes, errs


def check(p):
    R, C, nodes, errs = parse(p["svg"])
    starts = [v for v, s in nodes.items() if s == "start"]
    goals = [v for v, s in nodes.items() if s == "goal"]
    if len(starts) != 1 or len(goals) != 1:
        return errs + ["need exactly one bakery and one library"]
    s, t = starts[0], goals[0]
    closed = {v for v, st in nodes.items() if st == "closed"}
    if sorted(map(list, closed)) != p["scene"]["closed"] or list(s) != p["scene"]["start"] or list(t) != p["scene"]["goal"]:
        errs.append("scene differs from the picture")
    G = nx.grid_2d_graph(R, C)
    G.remove_nodes_from(closed)
    try:
        paths = list(nx.all_shortest_paths(G, s, t))
    except nx.NetworkXNoPath:
        return errs + ["no route exists in the picture"]
    length, count = len(paths[0]) - 1, len(paths)
    truth = length if p["question_type"] == "length" else count
    if p["answer_value"] != truth:
        errs.append(f"answer {p['answer_value']} != recomputed {truth}")
    if p["entry"] == "choice":
        o = p["options"]
        if o[p["answer_index"]] != truth:
            errs.append("option key wrong")
        if len(set(o)) != len(o):
            errs.append("duplicate options")
        if min(o) == truth or max(o) == truth:
            errs.append("shortcut: answer is smallest or largest option")
        for d in p["distractors"]:
            if not d["misconceptions"]:
                errs.append(f"untagged distractor {d['option']}")
    if str(truth) in p["value_tags"]:
        errs.append("a misconception value equals the answer")
    if any(int(v) <= 0 for v in p["value_tags"]):
        errs.append("non-positive misconception value")
    # recompute two misconception values independently
    tag = {k: v for v, ks in p["value_tags"].items() for k in ks}
    if p["question_type"] == "count":
        if tag.get("LENGTH_FOR_COUNT") not in (None, str(length)):
            errs.append("length-for-count value wrong")
        free = len(list(nx.all_shortest_paths(nx.grid_2d_graph(R, C), s, t)))
        if "IGNORES_CLOSED" in tag and tag["IGNORES_CLOSED"] != str(free):
            errs.append("ignores-closed value wrong")
    else:
        if tag.get("COUNTS_INTERSECTIONS") not in (None, str(length + 1)):
            errs.append("counts-intersections value wrong")
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

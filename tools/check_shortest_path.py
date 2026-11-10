"""
Independent checker for shortest_path problems.

Does not import the generator. It rebuilds the problem from the SVG picture:
  * the graph comes from the drawn walkway groups, and each walkway's plank
    count is read from its VISIBLE label text, then compared to data-w;
  * geometry is re-checked from the drawn line coordinates (no crossings,
    labels clear of islands, other walkways and other labels);
  * the optimum is re-solved with networkx and compared to the answer key;
  * options, uniqueness, shortcuts and misconception tags are re-verified.
"""

import json
import math
import sys
import xml.etree.ElementTree as ET
import itertools
import networkx as nx

NS = "{http://www.w3.org/2000/svg}"
ISLAND_R = 24


def parse_svg(svg):
    root = ET.fromstring(svg)
    islands, walkways = {}, []
    for g in root.iter(NS + "g"):
        cls = g.get("class")
        if cls == "island":
            label = g.find(NS + "text").text
            if label != g.get("data-id"):
                raise ValueError(f"island label {label} != data-id {g.get('data-id')}")
            islands[label] = (float(g.get("data-x")), float(g.get("data-y")))
        elif cls == "walkway":
            lines = g.findall(NS + "line")
            rect = g.find(NS + "rect")
            text = g.find(NS + "text")
            shown = int(text.text)
            walkways.append({
                "a": g.get("data-a"), "b": g.get("data-b"),
                "data_w": int(g.get("data-w")), "shown_w": shown,
                "p": (float(lines[0].get("x1")), float(lines[0].get("y1"))),
                "q": (float(lines[0].get("x2")), float(lines[0].get("y2"))),
                "rect": (float(rect.get("x")), float(rect.get("y")),
                         float(rect.get("x")) + float(rect.get("width")),
                         float(rect.get("y")) + float(rect.get("height"))),
            })
    return islands, walkways


def cross(p1, p2, p3, p4):
    def o(a, b, c):
        v = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        return 0 if abs(v) < 1e-9 else (1 if v > 0 else -1)
    if len({p1, p2} & {p3, p4}):
        return False
    return o(p1, p2, p3) * o(p1, p2, p4) < 0 and o(p3, p4, p1) * o(p3, p4, p2) < 0


def seg_rect(a, b, r):
    x0, y0, x1, y1 = r
    if any(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in (a, b)):
        return True
    cs = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return any(cross(a, b, cs[i], cs[(i + 1) % 4]) for i in range(4))


def check(p):
    errs = []
    islands, walks = parse_svg(p["svg"])

    # 1. picture vs data
    for w in walks:
        if w["shown_w"] != w["data_w"]:
            errs.append(f"label {w['shown_w']} != data {w['data_w']} on {w['a']}-{w['b']}")
        for end in (w["a"], w["b"]):
            if end not in ("N", "S") and end not in islands:
                errs.append(f"walkway touches unknown island {end}")
    scene_edges = {frozenset((a, b)): wt for a, b, wt in p["scene"]["edges"]}
    pic_edges = {frozenset((w["a"], w["b"])): w["shown_w"] for w in walks}
    if scene_edges != pic_edges:
        errs.append("scene edges differ from drawn walkways")

    # 2. geometry from drawn coordinates
    for w1, w2 in itertools.combinations(walks, 2):
        if cross(w1["p"], w1["q"], w2["p"], w2["q"]):
            errs.append(f"walkways cross: {w1['a']}-{w1['b']} and {w2['a']}-{w2['b']}")
        if seg_rect(w2["p"], w2["q"], w1["rect"]) or seg_rect(w1["p"], w1["q"], w2["rect"]):
            errs.append(f"label overlaps walkway: {w1['a']}-{w1['b']} / {w2['a']}-{w2['b']}")
    for w in walks:
        r = w["rect"]
        for iid, c in islands.items():
            nx_ = min(max(c[0], r[0]), r[2]); ny_ = min(max(c[1], r[1]), r[3])
            if math.hypot(nx_ - c[0], ny_ - c[1]) < ISLAND_R:
                errs.append(f"label of {w['a']}-{w['b']} overlaps island {iid}")

    # 3. re-solve from the picture
    G = nx.Graph()
    for w in walks:
        G.add_edge(w["a"], w["b"], weight=w["shown_w"])
    try:
        best = nx.shortest_path_length(G, "N", "S", weight="weight")
    except nx.NetworkXNoPath:
        return errs + ["no crossing exists in picture"]
    optimal = [pth for pth in nx.all_simple_paths(G, "N", "S")
               if nx.path_weight(G, pth, "weight") == best]
    if p["question_type"] == "count_routes":
        if len(optimal) != p["answer_value"]:
            errs.append(f"count key {p['answer_value']} != {len(optimal)} cheapest routes")
        if p["entry"] == "choice":
            if p["options"][p["answer_index"]] != len(optimal):
                errs.append("count option key wrong")
            if max(p["options"]) == len(optimal) or min(p["options"]) == len(optimal):
                errs.append("shortcut: answer is smallest or largest option")
        if str(len(optimal)) in p["value_tags"]:
            errs.append("a misconception value equals the answer")
        if sorted(map(tuple, p["optimal_paths"])) != sorted(map(tuple, optimal)):
            errs.append("listed cheapest routes differ from solved")
        allp = len(list(nx.all_simple_paths(G, "N", "S")))
        tagged_all = [v for v, ks in p["value_tags"].items() if "COUNTS_ALL_CROSSINGS" in ks]
        if tagged_all and tagged_all != [str(allp)]:
            errs.append("all-crossings misconception value wrong")
    elif len(optimal) != 1:
        errs.append(f"optimum not unique: {len(optimal)} routes cost {best}")
    if best != p["answer_cost"]:
        errs.append(f"answer_cost {p['answer_cost']} != solved {best}")
    if p["question_type"] != "count_routes" and optimal and optimal[0] != p["answer_path"]:
        errs.append("answer_path differs from solved optimum")

    # 4. question-specific checks
    qt = p["question_type"]
    if qt == "cost":
        opts = p["options"]
        if opts[p["answer_index"]] != best:
            errs.append("cost answer key wrong")
        if len(set(opts)) != len(opts):
            errs.append("duplicate options")
        if min(opts) == best or max(opts) == best:
            errs.append("shortcut: correct is the smallest or largest option")
    elif qt == "compare":
        # options are route strings; rebuild from distractor payloads + answer path
        costs = []
        for d in p["distractors"]:
            c = nx.path_weight(G, d["option"], "weight")
            if c != d["cost"]:
                errs.append("distractor cost mismatch")
            if c <= best:
                errs.append("distractor route not more expensive than answer")
            costs.append(c)
        hops = {len(d["option"]) for d in p["distractors"]}
        if len(p["answer_path"]) < min(hops):
            errs.append("shortcut: answer has the fewest walkways")
    for d in p["distractors"]:
        if not d["misconceptions"]:
            errs.append(f"untagged distractor {d['option']}")
    for k, pth in p["misconception_paths"].items():
        if any(not G.has_edge(a, b) for a, b in zip(pth, pth[1:])):
            errs.append(f"misconception path {k} uses a walkway not in the picture")
        elif pth[0] != "N" or pth[-1] != "S":
            errs.append(f"misconception path {k} is not a full crossing")
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

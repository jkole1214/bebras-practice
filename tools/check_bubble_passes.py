"""
Independent checker for bubble_passes (Bowl Belt) problems.

Does not import the generator. It rebuilds the row from the SVG picture (each bowl's
data-size, its number, its drawn width and its place left to right), the walker arrow
(data-dir, and which way the arrowhead points) and the caption (data-shows), then solves
again with different code:
  one walk:  a "carry" walk to the right (hold the biggest bowl met so far, drop each smaller
             one behind it); a walk to the left is the same walk on the mirrored row
             (reverse it and turn size s into N+1-s). The generator swaps pair by pair.
  workers:   a counting formula, not simulation: on walks to the right, each worker carries
             exactly one bigger bowl past any bowl that still has one to its left, so the
             count is the most bigger bowls any bowl has to its left.
Wrong answers' tags are re-derived from the checker's own version of each mistake.

Usage: python3 check_bubble_passes.py L1-1000.js [...]   (files from bowl-belt/)
"""

import json
import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://www.w3.org/2000/svg}"
OTHER = {"right": "left", "left": "right"}
WAY = {"right": "left to right", "left": "right to left"}
CAPTION = {"start": "The row before the workers", "after1": "The row after one worker"}
SHOWS = {"after1": "start", "swaps": "start", "afterk": "start", "workers": "start", "start": "after1"}


def classes(el):
    return (el.get("class") or "").split()


def mirror(row):
    n = len(row)
    return [n + 1 - x for x in reversed(row)]


def carry_right(row):
    """One walk to the right, as a carry: returns (new row, swaps)."""
    out, hold, sw = [], row[0], 0
    for x in row[1:]:
        if hold > x:
            out.append(x)
            sw += 1
        else:
            out.append(hold)
            hold = x
    return out + [hold], sw


def one(row, d):
    if d == "right":
        return carry_right(row)
    r, sw = carry_right(mirror(row))
    return mirror(r), sw


def skip_right(row):
    a, i = list(row), 0
    while i < len(a) - 1:
        if a[i] > a[i + 1]:
            a[i], a[i + 1] = a[i + 1], a[i]
            i += 2
        else:
            i += 1
    return a


def stops(row, d):
    """CARRY_STOPS for one walk: a bowl just swapped is not checked again."""
    return skip_right(row) if d == "right" else mirror(skip_right(mirror(row)))


def stops_count(row, d):
    r = row if d == "right" else mirror(row)
    a, i, c = list(r), 0, 0
    while i < len(a) - 1:
        if a[i] > a[i + 1]:
            a[i], a[i + 1] = a[i + 1], a[i]
            c += 1
            i += 2
        else:
            i += 1
    return c


def carried(row, d, k):
    """ONLY_CARRIED_MOVES after k workers."""
    r = row if d == "right" else mirror(row)
    n = len(r)
    out = [x for x in r if x <= n - k] + list(range(n - k + 1, n + 1))
    return out if d == "right" else mirror(out)


def need(row, d):
    r = row if d == "right" else mirror(row)
    return max(sum(1 for y in r[:i] if y > x) for i, x in enumerate(r))


def disorder(row):
    return sum(sum(1 for y in row[:i] if y > x) for i, x in enumerate(row))


def far(row):
    return max(abs(i + 1 - x) for i, x in enumerate(row))


def k_walks(row, d, k, f):
    for _ in range(k):
        row = f(row, d)
    return list(row)


def parse(svg, errs):
    root = ET.fromstring(svg)
    bowls = []
    for g in root.iter(NS + "g"):
        c = classes(g)
        if "bowl" in c:
            s = int(g.get("data-size"))
            if g.find(NS + "text").text != str(s):
                errs.append(f"bowl {s} shows a different number")
            nums = [float(x) for x in re.findall(r"-?\d+\.?\d*", g.find(NS + "path").get("d"))]
            left, top, right = nums[0], nums[1], nums[2]
            bowls.append((left, right - left, s, int(g.get("data-pos")), top))
        elif "walker" in c:
            d = g.get("data-dir")
            ln = g.find(NS + "line")
            x1, x2 = float(ln.get("x1")), float(ln.get("x2"))
            if (x2 > x1) != (d == "right") or d not in OTHER:
                errs.append("the arrow points the other way from data-dir")
            walker = d
    bowls.sort()
    row = [b[2] for b in bowls]
    if [b[3] for b in bowls] != list(range(len(bowls))):
        errs.append("bowls are not in data-pos order left to right")
    widths = {b[2]: b[1] for b in bowls}
    if any(widths[a] >= widths[b] for a, b in zip(sorted(widths), sorted(widths)[1:])):
        errs.append("a bigger bowl is not drawn wider")
    if sorted(row) != list(range(1, len(row) + 1)):
        errs.append("bowl sizes are not 1 to N")
    cap = [t for t in root.iter(NS + "text") if "caption" in classes(t)]
    shows = cap[0].get("data-shows") if len(cap) == 1 else None
    if shows not in CAPTION or cap[0].text != CAPTION[shows]:
        errs.append("caption does not match data-shows")
    return row, walker, shows


def tags_for(wrong, truth):
    out = {}
    for tag, v in wrong.items():
        out.setdefault(json.dumps(v), set()).add(tag)
    return out


def check(p):
    if p["family"] != "bubble_passes":
        return ["wrong family"]
    errs = []
    row, d, shows = parse(p["svg"], errs)
    q, sc = p["question_type"], p["scene"]
    n = len(row)
    if shows != SHOWS.get(q):
        errs.append("the caption is wrong for this question")
    if sc["dir"] != d:
        errs.append("scene direction differs from the arrow")
    if (sc.get("after") if q == "start" else sc.get("row")) != row:
        errs.append("scene row differs from the picture")
    want_prompt = (f"Bowls of sizes 1 to {n} ride in a row on a belt. A worker walks along the row from {WAY[d]}. "
                   f"At each pair of neighbouring bowls, if the left bowl is bigger than the right one, the worker swaps them, "
                   f"then steps one bowl {d} to the next pair.")
    if not p["prompt"].startswith(want_prompt):
        errs.append("prompt does not match the arrow")
    show = lambda r: " ".join(map(str, r))
    expl = p["explanation"]

    if q in ("after1", "afterk"):
        k = 1 if q == "after1" else sc["workers"]
        if q == "afterk" and not p["question"].startswith(f"{k} workers walk along the row"):
            errs.append("question does not say how many workers")
        truth = k_walks(row, d, k, lambda r, dd: one(r, dd)[0])
        o = p["options"]
        if p["answer_value"] != truth or o[p["answer_index"]] != truth or o.count(truth) != 1 or len(o) != 4:
            errs.append("marked option is not the recomputed row")
        if truth == sorted(row):
            errs.append("the workers already finish the job")
        wrong = {"CARRY_STOPS": k_walks(row, d, k, stops), "ONE_PASS_SORTS": sorted(row),
                 "PASS_WRONG_WAY": k_walks(row, OTHER[d], k, lambda r, dd: one(r, dd)[0]),
                 "ONLY_CARRIED_MOVES": carried(row, d, k)}
        if truth in wrong.values():
            errs.append("a habit gives the right row")
        want = tags_for(wrong, truth)
        lead = "CARRY_STOPS" if q == "after1" else "ONLY_CARRIED_MOVES"
        if lead not in {t for d_ in p["distractors"] for t in d_["misconceptions"]}:
            errs.append(f"no option for {lead}")
        got = {json.dumps(x["option"]): x["misconceptions"] for x in p["distractors"]}
        if sorted(got) != sorted(json.dumps(x) for x in o if x != truth):
            errs.append("every wrong option needs tags")
        for x, t in got.items():
            if not t or set(t) != want.get(x, set()):
                errs.append(f"option {x} tagged {t}, recomputed {sorted(want.get(x, []))}")
        end = f"So the row becomes {show(truth)}." if q == "after1" else f"So after {k} workers the row is {show(truth)}."
        if expl[-1] != end:
            errs.append("the explanation does not end with the answer")

    elif q == "swaps":
        truth = one(row, d)[1]
        if p["answer_value"] != truth or p["entry"] != "number" or p["options"]:
            errs.append(f"answer {p['answer_value']} != recomputed {truth}")
        wrong = {"COUNTS_COMPARISONS": n - 1, "ONE_PASS_SORTS": disorder(row),
                 "PASS_WRONG_WAY": one(row, OTHER[d])[1], "CARRY_STOPS": stops_count(row, d)}
        if truth in wrong.values():
            errs.append("a habit gives the right count")
        if {k: set(v) for k, v in p["value_tags"].items()} != tags_for(wrong, truth):
            errs.append(f"typed-number tags {p['value_tags']} differ from recomputed")
        if expl[-1] != f"So the worker makes {truth} swaps.":
            errs.append("the explanation does not end with the answer")

    elif q == "workers":
        truth = need(row, d)
        if p["answer_value"] != truth or p["entry"] != "number" or p["options"]:
            errs.append(f"answer {p['answer_value']} != recomputed {truth}")
        wrong = {"FARTHEST_BOWL": far(row), "SWAPS_FOR_PASSES": disorder(row),
                 "COUNTS_CHECK_PASS": truth + 1, "PASS_WRONG_WAY": need(row, OTHER[d])}
        if truth in wrong.values():
            errs.append("a habit gives the right count")
        if far(row) < truth:
            errs.append("the farthest bowl is not one that rides the fast way")
        if {k: set(v) for k, v in p["value_tags"].items()} != tags_for(wrong, truth):
            errs.append(f"typed-number tags {p['value_tags']} differ from recomputed")
        rows = [l.split(":", 1)[1].split("(")[0].split() for l in expl if l.startswith("  worker ")]
        r = row
        for i, shown in enumerate(rows):
            r = one(r, d)[0]
            if shown != [str(x) for x in r]:
                errs.append(f"the explanation's worker {i + 1} row is wrong")
        if len(rows) != truth:
            errs.append("the explanation shows the wrong number of workers")
        if expl[-1] != f"So {truth} workers are needed.":
            errs.append("the explanation does not end with the answer")

    elif q == "start":
        after = row
        o = p["options"]
        good = [x for x in o if one(x, d)[0] == after]
        if len(good) != 1 or len(o) != 4 or len({json.dumps(x) for x in o}) != 4:
            return errs + [f"{len(good)} options become the row shown"]
        truth = good[0]
        if p["answer_value"] != truth or o[p["answer_index"]] != truth:
            errs.append("marked option is not the recomputed start")
        models = {"CARRY_STOPS": lambda r: stops(r, d), "PASS_WRONG_WAY": lambda r: one(r, OTHER[d])[0],
                  "ONLY_CARRIED_MOVES": lambda r: carried(r, d, 1)}
        if any(f(truth) == after for f in models.values()):
            errs.append("a habit leads to the right row")
        got = {json.dumps(x["option"]): x["misconceptions"] for x in p["distractors"]}
        if sorted(got) != sorted(json.dumps(x) for x in o if x != truth):
            errs.append("every wrong option needs tags")
        for x, t in got.items():
            w = {tag for tag, f in models.items() if f(json.loads(x)) == after}
            if not t or set(t) != w:
                errs.append(f"option {x} tagged {t}, recomputed {sorted(w)}")
        if expl[-1] != f"So the row started as {show(truth)}.":
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

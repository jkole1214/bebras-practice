"""
Independent checker for circle_steps (Round and Round). Does not import the generator.

It rebuilds each problem from the SVG picture and solves it another way, without modular arithmetic:
  step    puts the squares in clockwise order by their angle in the drawing and walks the counter
          one square at a time
  label   matches every string's ends to pins in the drawing and counts pins between them both ways
  visits  follows the drawn first string, then keeps walking round pin by pin until it lands on pin 1
  turns   turns a list of the cars one place at a time, both ways, until the next car is at the platform
  meet    follows the data-next arrows on the track square by square for both karts
Every habit tag is re-derived the same way, and the explanation's lines are replayed.

    python3 tools/check_circle_steps.py        # checks seeds 1000-1039 at every level
"""

import math
import re
import sys

GOLD = "#ffd166"


def attrs(tag):
    return dict(re.findall(r'([\w-]+)="([^"]*)"', tag))


def svg_root(svg):
    return attrs(re.match(r"<svg [^>]*>", svg).group(0))


def groups(svg, cls):
    """<g class=cls ...>...</g> blocks (these never nest)."""
    return [(attrs(m.group(1)), m.group(2)) for m in re.finditer(rf'<g class="{cls}" ([^>]*)>(.*?)</g>', svg)]


def disc(body):
    c = attrs(re.search(r"<circle [^>]*>", body).group(0))
    text = re.search(r"<text [^>]*>([^<]*)</text>", body)
    return float(c["cx"]), float(c["cy"]), c.get("fill"), text.group(1) if text else None


def ring(items, centre, start_deg):
    """Labels sorted clockwise by angle, starting from the direction start_deg (SVG: y grows downward)."""
    cx, cy = centre

    def ang(it):
        a = math.degrees(math.atan2(it[1] - cy, it[0] - cx)) - start_deg
        return a % 360
    return [it[2] for it in sorted(items, key=ang)]


def centre_of(pts):
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def walk(order, frm, steps):
    i = order.index(frm)
    return order[(i + steps) % len(order)] if steps >= 0 else None


def clockwise_steps(order, a, b):
    if a not in order or b not in order:
        raise ValueError("not on the ring")
    i, s = order.index(a), 0
    while order[i] != b:
        i, s = (i + 1) % len(order), s + 1
    return s


def tagmap(wrong, truth):
    vt = {}
    for tag, v in wrong.items():
        if v == truth or v < 1:
            return None
        vt.setdefault(str(v), set()).add(tag)
    return vt


def check_one(p):
    errs = []
    svg, sc, q, expl = p["svg"], p["scene"], p["question_type"], p["explanation"]
    root = svg_root(svg)
    if root.get("data-family") != "circle_steps" or root.get("data-kind") != q:
        return ["picture is for another family or kind"]
    if p["entry"] != "number" or p["options"] or p["distractors"]:
        errs.append("every question here is typed")
    tv = None

    if q == "step":
        n, s, k = int(root["data-n"]), int(root["data-start"]), int(root["data-move"])
        spots = []
        for a, body in groups(svg, "spot"):
            x, y, fill, label = disc(body)
            if label != a["data-spot"]:
                errs.append("square label differs from data")
            if (fill == GOLD) != (a["data-counter"] == "1"):
                errs.append("counter colour differs from data")
            spots.append((x, y, int(a["data-spot"]), a["data-counter"] == "1"))
        order = ring(spots, centre_of(spots), -90)
        if order != list(range(1, n + 1)) or len(spots) != n:
            errs.append("squares are not numbered 1 to n clockwise from the top")
        here = [sp[2] for sp in spots if sp[3]]
        if here != [s]:
            errs.append("counter is not on the start square")
        if f">Move {k}<" not in svg:
            errs.append("picture shows a different move")
        if sc != {"n": n, "start": s, "move": k}:
            errs.append("scene differs from picture")
        if f"on square {s}. You move it {k} squares clockwise" not in p["question"] or f"numbered 1 to {n}." not in p["prompt"]:
            errs.append("question differs from picture")
        truth = walk(order, s, k)
        # the habits: no wrap goes on counting past n; counting the start square takes one step fewer;
        # not counting the step from n to 1 goes one square further once it wraps
        i, steps, crossed = order.index(s), 0, False
        while steps < k:
            j = (i + 1) % n
            if j == 0 and not crossed:
                crossed = True              # this step "doesn't count"
            else:
                steps += 1
            i = j
        tv = tagmap({"NO_WRAP": s + k, "COUNTS_START_SQUARE": walk(order, s, k - 1), "WRAP_NOT_A_STEP": order[i]}, truth)
        steps_shown = [f"  {s} + {k} = {s + k}, but the board only goes up to {n}",
                       f"  after square {n} comes square 1: {s + k} − {n} = {truth}"]
        ending = f"So the counter lands on square {truth}."

    elif q in ("label", "visits"):
        n = int(root["data-n"])
        pins = {}
        for a, body in groups(svg, "pin"):
            x, y, _, _ = disc(body)
            label = re.search(r"<text [^>]*>([^<]*)</text>", body).group(1)
            if label != a["data-pin"]:
                errs.append("pin label differs from data")
            pins[int(a["data-pin"])] = (x, y)
        order = ring([(x, y, i) for i, (x, y) in pins.items()], centre_of(list(pins.values())), -90)
        if order != list(range(1, n + 1)):
            errs.append("pins are not numbered 1 to n clockwise from the top")
        lines = []
        for m in re.finditer(r'<line class="string" [^>]*>', svg):
            a = attrs(m.group(0))
            f, t = int(a["data-from"]), int(a["data-to"])
            x0, y0, x1, y1 = (float(a[c]) for c in ("x1", "y1", "x2", "y2"))
            if math.hypot(x0 - pins[f][0], y0 - pins[f][1]) > 0.5:
                errs.append("a string does not start at its pin")
            # the end may stop short (arrowhead); it must point straight at its pin
            ex, ey = pins[t][0] - x0, pins[t][1] - y0
            if abs(ex * (y1 - y0) - ey * (x1 - x0)) > 2 * math.hypot(ex, ey) or math.hypot(x1 - pins[t][0], y1 - pins[t][1]) > 12:
                errs.append("a string does not end at its pin")
            lines.append([f, t])

        if q == "label":
            kinds = set()
            for f, t in lines:
                cw, ccw = clockwise_steps(order, f, t), clockwise_steps(order, t, f)
                kinds.add(min(cw, ccw))
            if len(kinds) != 1 or len(lines) != n:
                return errs + ["the strings don't all go the same number of places"]
            truth = kinds.pop()
            if 2 * truth >= n:
                errs.append("step is not the short way")
            ends = {}
            for f, t in lines:
                ends.setdefault(f, set()).add(t)
                ends.setdefault(t, set()).add(f)
            if any(len(v) != 2 for v in ends.values()) or len(ends) != n:
                errs.append("a pin does not have two strings")
            if sc != {"n": n, "k": truth, "lines": lines}:
                errs.append("scene differs from picture")
            between = clockwise_steps(order, 1, walk(order, 1, truth)) - 1      # pins skipped over
            tv = tagmap({"COUNTS_SKIPPED_PINS": between, "LONG_WAY_ROUND": clockwise_steps(order, walk(order, 1, truth), 1),
                         "COUNTS_BOTH_ENDS": between + 2}, truth)
            back = walk(order, 1, -truth % n)
            steps_shown = [f"  pin 1 → pin {walk(order, 1, truth)}: {truth} steps clockwise",
                           f"  pin 1 → pin {back}: {clockwise_steps(order, back, 1)} steps the other way",
                           f"  the long way round would be {n} − {truth} = {n - truth} steps"]
            ending = f"So each string goes {truth} places round."
        else:
            if len(lines) != 1 or lines[0][0] != 1:
                return errs + ["the first string should start at pin 1"]
            k = clockwise_steps(order, 1, lines[0][1])
            if int(root["data-k"]) != k or f"to the pin {k} places clockwise" not in p["question"]:
                errs.append("question differs from the drawn string")
            if sc != {"n": n, "k": k, "lines": lines}:
                errs.append("scene differs from picture")
            seen, x, travelled, first_lap = [1], 1, 0, None
            while len(seen) <= n:
                x = walk(order, x, k)
                travelled += k
                if first_lap is None and travelled >= n:
                    first_lap = len(seen)       # pins landed on before going past pin 1
                if x == 1:
                    break
                seen.append(x)
            truth = len(seen)
            tv = tagmap({"EVERY_PIN": n, "ONE_LAP": first_lap, "COUNTS_START_TWICE": truth + 1}, truth)
            steps_shown = ["  " + " → ".join(map(str, seen + [1]))]
            ending = f"So the loop touches {truth} pins."

    elif q == "turns":
        n = int(root["data-n"])
        cars, at = [], []
        for a, body in groups(svg, "car"):
            x, y, fill, label = disc(body)
            if label != a["data-car"]:
                errs.append("car label differs from data")
            if (fill == GOLD) != (a["data-platform"] == "1"):
                errs.append("platform colour differs from data")
            if a["data-platform"] == "1":
                at.append(int(a["data-car"]))
            cars.append((x, y, int(a["data-car"])))
        wheel = ring(cars, centre_of(cars), 90)          # clockwise from the bottom, where the platform is
        if len(cars) != n or sorted(wheel) != list(range(1, n + 1)):
            errs.append("wrong cars on the wheel")
        if at != [wheel[0]] or at != [1]:
            errs.append("car 1 is not at the platform")
        stops = []
        for a, body in groups(svg, "stop"):
            if re.search(r"<text [^>]*>([^<]*)</text>", body).group(1) != a["data-car"]:
                errs.append("order label differs from data")
            stops.append(int(a["data-car"]))
        if [int(a["data-step"]) for a, _ in groups(svg, "stop")] != list(range(1, len(stops) + 1)):
            errs.append("order out of sequence")
        if root["data-order"] != " ".join(map(str, stops)) or sc != {"n": n, "order": stops}:
            errs.append("scene differs from picture")
        if f"order: cars {', '.join(map(str, stops))}." not in p["question"]:
            errs.append("question differs from picture")

        def presses(wh, target):
            """turn one car at a time each way; return (fewer, other way)"""
            if target not in wh:
                raise ValueError("car not on the wheel")
            a, b, cw = list(wh), list(wh), 0
            while a[0] != target:
                a = a[1:] + a[:1]
                cw += 1
            ccw = 0
            while b[0] != target:
                b = b[-1:] + b[:-1]
                ccw += 1
            return min(cw, ccw), max(cw, ccw)
        wh, total, lines, prev, parts = list(wheel), 0, [], 1, []
        upward = 0
        for c in stops:
            best, other = presses(wh, c)
            total += best
            parts.append(str(best))
            lines.append(f"  car {prev} to car {c}: {best} presses (the other way is {other})")
            # always turning so the numbers come up in order: count cars from prev upward to c
            u = 0
            while (prev - 1 + u) % n + 1 != c:
                u += 1
                if u > n:
                    raise ValueError("car number not on the wheel")
            upward += u
            while wh[0] != c:
                wh = wh[1:] + wh[:1]
            prev = c
        fixed = sum(presses(wheel, c)[0] for c in stops)
        straight = sum(abs(b - a) for a, b in zip([1] + stops, stops))
        truth = total
        tv = tagmap({"FROM_START_EACH_TIME": fixed, "ONE_WAY_ONLY": upward, "NO_WRAP": straight}, truth)
        steps_shown = lines + ["  " + " + ".join(parts) + f" = {truth}"]
        ending = f"So the fewest is {truth} presses."

    elif q == "meet":
        cells, nxt = {}, {}
        for a, body in groups(svg, "cell"):
            x, y, fill, label = disc(body)
            if label != a["data-cell"]:
                errs.append("square label differs from data")
            if (fill == GOLD) != (a["data-cell"] == root["data-start"]):
                errs.append("start colour differs from data")
            nxt[int(a["data-cell"])] = int(a["data-next"])
        start = int(root["data-start"])
        into = {}
        for c, d in nxt.items():
            into.setdefault(d, []).append(c)
        entry = [c for c, v in into.items() if len(v) == 2]
        if len(entry) != 1 or start in into or any(d not in nxt for d in nxt.values()):
            return errs + ["the track is not a road into one loop"]
        lead, loop = entry[0] - 1, len(nxt) - entry[0] + 1
        if sc != {"lead": lead, "loop": loop}:
            errs.append("scene differs from picture")
        if ("(square 1)" if lead == 1 else f"(squares 1 to {lead})") not in p["prompt"] or f"(squares {lead + 1} to {lead + loop})" not in p["prompt"]:
            errs.append("prompt differs from picture")
        slow = fast = start
        rows = []
        while len(rows) <= 2 * len(nxt):
            slow = nxt[slow]
            fast = nxt[nxt[fast]]
            rows.append(f"  second {len(rows) + 1}: slow on {slow}, fast on {fast}")
            if slow == fast:
                break
        truth = slow
        tv = tagmap({"LOOP_ENTRANCE": entry[0], "BACK_TO_START": start}, truth)
        steps_shown = rows
        ending = f"So they first meet on square {truth}."
    else:
        return [f"unknown question type {q}"]

    if p["answer_value"] != truth or p["answer_index"] != -1:
        errs.append(f"answer should be {truth}")
    if tv is None:
        errs.append("a habit gives the right answer")
    elif {v: set(t) for v, t in p["value_tags"].items()} != tv:
        errs.append(f"value tags should be {tv}")
    if [l for l in expl if l.startswith("  ")] != steps_shown:
        errs.append("explanation steps are wrong")
    if expl[-1] != ending:
        errs.append("explanation ending is wrong")
    return errs


def check(p):
    try:
        return check_one(p)
    except Exception as e:      # a corrupted picture must fail, not crash the build
        return [f"checker error: {type(e).__name__}: {e}"]


if __name__ == "__main__":
    sys.path.insert(0, __import__("os").path.dirname(__file__))
    from dataclasses import asdict
    import circle_steps as G
    bad = 0
    for L in range(1, 6):
        for s in range(1000, 1040):
            e = check(asdict(G.generate(L, s)))
            if e:
                bad += 1
                print(L, s, e)
    print("failures:", bad)

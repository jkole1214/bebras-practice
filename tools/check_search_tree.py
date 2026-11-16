"""
Independent checker for search_tree (Rabbit Warren). Does not import the generator.

It rebuilds each problem from the SVG picture and solves it another way:
  find    rebuilds the warren from the drawing (a room lower down and to the left of the room its tunnel
          comes from is the left child), checks the left-smaller/right-bigger rule by reading the rooms
          left to right, and counts the rooms by climbing up from the jar to the top
  insert  the new room hangs below whichever of the jar's two nearest numbers is lower in the warren
  build   works out each jar's rooms above it without building the tree: a jar is above another when
          it arrived first and no number between the two arrived before it
  order   an order is right when every jar arrives after the jar in the room just above it
  pack    reads the plan and the cards from the picture and checks every card against every rule
Every habit tag is re-derived, and the explanation's lines are replayed.

    python3 tools/check_search_tree.py        # checks seeds 1000-1039 at every level
"""

import re
import sys

ORDER = {
    "find": ["COUNTS_BRANCHES", "ROW_BY_ROW", "DOWN_TO_THE_BOTTOM"],
    "insert": ["NEAREST_NUMBER", "FIRST_TURN_ONLY", "SWAPS_LEFT_RIGHT"],
    "rows": ["ALWAYS_BALANCED", "EACH_NEW_ROW", "COUNTS_BRANCHES"],
    "order": ["CHILD_BEFORE_PARENT", "READS_LEFT_TO_RIGHT", "BOTTOM_UP"],
    "pack": ["FORGETS_REQUIRED", "TOP_LEVEL_ONLY", "IGNORES_NESTING"],
}
CONCEPTS = {"find": ["TREE", "BST"], "insert": ["BST", "TREE"], "rows": ["BST", "ORDERING"],
            "order": ["BST", "ORDERING"], "pack": ["SCHEMA", "TREE"]}
LEVEL_OF = {"find": 1, "insert": 2, "rows": 3, "order": 4, "pack": 5}


def attrs(tag):
    return dict(re.findall(r'([\w-]+)="([^"]*)"', tag))


def svg_root(svg):
    return attrs(re.match(r"<svg [^>]*>", svg).group(0))


def groups(svg, cls):
    return [(attrs(m.group(1)), m.group(2)) for m in re.finditer(rf'<g class="{cls}" ([^>]*)>(.*?)</g>', svg)]


def texts(body):
    return re.findall(r"<text [^>]*>([^<]*)</text>", body)


def tagmap(q, wrong, truth):
    vt = {}
    for tag, v in wrong.items():
        if v == truth or v < 1:
            return None
        vt.setdefault(str(v), []).append(tag)
    return {v: sorted(t, key=ORDER[q].index) for v, t in vt.items()}


# --------------------------------------------------------------------------
# The warren from the picture
# --------------------------------------------------------------------------

class Warren:
    def __init__(self, svg):
        self.errs = []
        self.at = {}
        for a, body in groups(svg, "room"):
            k = int(a["data-key"])
            c = attrs(re.search(r"<circle [^>]*>", body).group(0))
            self.at[k] = (float(c["cx"]), float(c["cy"]))
            if texts(body) != [str(k)]:
                self.errs.append(f"room {k} is labelled {texts(body)}")
        self.parent, self.left, self.right = {}, {}, {}
        for m in re.finditer(r'<line class="tunnel" ([^>]*)/>', svg):
            a = attrs(m.group(1))
            p, c = int(a["data-from"]), int(a["data-to"])
            if p not in self.at or c not in self.at:
                self.errs.append(f"tunnel {p}-{c} ends at no room")
                continue
            ends = [(float(a["x1"]), float(a["y1"])), (float(a["x2"]), float(a["y2"]))]
            if any(abs(e[0] - q[0]) > .6 or abs(e[1] - q[1]) > .6 for e, q in zip(ends, (self.at[p], self.at[c]))):
                self.errs.append(f"tunnel {p}-{c} is not drawn between its rooms")
            if self.at[c][1] <= self.at[p][1]:
                self.errs.append(f"tunnel {p}-{c} does not lead down")
            if c in self.parent:
                self.errs.append(f"room {c} has two tunnels from above")
            self.parent[c] = p
            side = self.left if self.at[c][0] < self.at[p][0] else self.right
            if p in side:
                self.errs.append(f"room {p} has two tunnels on one side")
            side[p] = c
        tops = [k for k in self.at if k not in self.parent]
        if len(tops) != 1:
            self.errs.append(f"{len(tops)} top rooms")
            self.root = None
            return
        self.root = tops[0]
        if min(y for _, y in self.at.values()) != self.at[self.root][1]:
            self.errs.append("the top room is not at the top")
        if self.inorder(self.root) != sorted(self.at):
            self.errs.append("the rooms break the left-smaller, right-bigger rule (or are not all joined)")

    def inorder(self, k, depth=0):
        if k is None or depth > 40:
            return []
        return self.inorder(self.left.get(k), depth + 1) + [k] + self.inorder(self.right.get(k), depth + 1)

    def chain(self, k):
        """k and every room above it, top room first."""
        out = [k]
        while out[-1] in self.parent and len(out) < 40:
            out.append(self.parent[out[-1]])
        return out[::-1]

    def rows(self):
        return len({y for _, y in self.at.values()})

    def row_by_row(self):
        return [k for k, _ in sorted(self.at.items(), key=lambda kv: (kv[1][1], kv[1][0]))]

    def flipped_end(self, x):
        y = self.root
        for _ in range(40):
            nxt = (self.right if x < y else self.left).get(y)
            if nxt is None:
                return y
            y = nxt
        return None

    def same_way_end(self, x):
        side = self.left if x < self.root else self.right
        y = self.root
        while y in side:
            y = side[y]
        return y

    def kids_map(self):
        return {str(k): [self.left.get(k), self.right.get(k)] for k in self.at}


def rel(x, y):
    return "smaller" if x < y else "bigger"


def way(x, y):
    return "left" if x < y else "right"


# --------------------------------------------------------------------------
# Level 3: rooms above a jar, from the arrival order alone
# --------------------------------------------------------------------------

def above(order, k):
    """Jars in rooms above k, in arrival order: each arrived before k, with nothing between them arriving earlier."""
    when = {v: i for i, v in enumerate(order)}
    out = []
    for a in order[:when[k]]:
        lo, hi = min(a, k), max(a, k)
        if all(when[b] > when[a] for b in order if lo < b < hi):
            out.append(a)
    return out


# --------------------------------------------------------------------------
# Level 5: the plan
# --------------------------------------------------------------------------

def plural(w):
    if w.endswith("y"):
        return w[:-1] + "ies"
    if w.endswith(("sh", "ch", "s", "x")):
        return w + "es"
    return w + "s"


def say(c, w):
    return f"no {plural(w)}" if c == 0 else f"{c} {w if c == 1 else plural(w)}"


def read_plan(svg, errs):
    rules = {}
    for a, body in groups(svg, "rule"):
        name = a["data-name"]
        lo, hi = int(a["data-min"]), int(a["data-max"])
        want = [name] if not a["data-parent"] else [name, f"{lo}" if lo == hi else f"{lo}–{hi}"]
        if texts(body) != want:
            errs.append(f"plan part {name} reads {texts(body)}")
        rules[name] = {"parent": a["data-parent"], "min": lo, "max": hi}
    return rules


def read_cards(svg, errs):
    cards = {}
    for m in re.finditer(r'<rect class="card" data-option="(\w)"', svg):
        cards[m.group(1)] = {"top": {}, "boxes": [], "lines": []}
    for m in re.finditer(r'<text class="line" ([^>]*)>([^<]*)</text>', svg):
        a, shown = attrs(m.group(1)), m.group(2)
        card = cards.get(a["data-option"])
        if card is None:
            errs.append("a line belongs to no card")
            continue
        if a["data-kind"] == "box":
            items = [(nm, int(n)) for nm, n in (s.split(":") for s in a["data-items"].split())]
            stuff = [say(n, nm) for nm, n in items if n]
            want = f"{a['data-name']}: " + (", ".join(stuff) if stuff else "empty")
            card["boxes"].append({"type": a["data-name"], "items": dict(items)})
        else:
            n = int(a["data-count"])
            want = say(n, a["data-name"])
            if a["data-name"] in card["top"]:
                errs.append(f"card {a['data-option']} lists {a['data-name']} twice")
            card["top"][a["data-name"]] = n
        if shown != want:
            errs.append(f"card {a['data-option']} line reads {shown!r}, its data says {want!r}")
        card["lines"].append(shown)
    return cards


def judge(rules, card):
    """(habit that misses it, words) for every broken rule."""
    out = []
    for name, r in rules.items():
        if r["parent"] == "basket":
            is_box = any(q["parent"] == name for q in rules.values())
            c = sum(b["type"] == name for b in card["boxes"]) if is_box else card["top"].get(name, 0)
            if c < r["min"]:
                out.append(("FORGETS_REQUIRED", f"{say(c, name)} in the basket, but it needs at least {r['min']}"))
            if c > r["max"]:
                out.append(("OVER_TOP", f"{say(c, name)} in the basket, but it holds at most {r['max']}"))
    for name, c in card["top"].items():
        if c and rules.get(name, {}).get("parent") != "basket":
            out.append(("IGNORES_NESTING", f"{say(c, name)} loose in the basket, but {plural(name)} only go in a "
                                           f"{rules[name]['parent'] if name in rules else '?'}"))
    for b in card["boxes"]:
        if b["type"] not in rules:
            out.append(("UNKNOWN", b["type"]))
            continue
        for nm, n in b["items"].items():
            if rules.get(nm, {}).get("parent") != b["type"]:
                out.append(("UNKNOWN", nm))
        for name, r in rules.items():
            if r["parent"] != b["type"]:
                continue
            c = b["items"].get(name, 0)
            if c < r["min"]:
                out.append(("FORGETS_REQUIRED", f"a {b['type']} with {say(c, name)}, but each {b['type']} needs "
                                                f"at least {r['min']}"))
            if c > r["max"]:
                out.append(("TOP_LEVEL_ONLY", f"a {b['type']} with {say(c, name)}, but a {b['type']} holds "
                                              f"at most {r['max']}"))
    return out


# --------------------------------------------------------------------------

def check_one(p):
    errs = []
    q = p["question_type"]
    if q not in ORDER:
        return [f"unknown question type {q}"]
    root = svg_root(p["svg"])
    if root.get("data-kind") != q or root.get("data-family") != "search_tree":
        errs.append("picture is for another question")
    if p["level"] != LEVEL_OF[q] or p["concepts"] != CONCEPTS[q]:
        errs.append("level or concepts do not match the question")
    expl = p["explanation"]
    vt = p["value_tags"]

    if q in ("find", "insert", "order"):
        w = Warren(p["svg"])
        errs += w.errs
        if w.errs or w.root is None:
            return errs
        sc = p["scene"]
        if sc.get("root") != w.root or {str(k): v for k, v in sc["kids"].items()} != w.kids_map():
            errs.append("scene does not match the picture")

    if q == "find":
        x = int(root["data-target"])
        if f"wants jar {x}." not in p["question"] or x not in w.at:
            errs.append("question and picture name different jars")
            return errs
        path = w.chain(x)
        truth = len(path)
        wrong = {"COUNTS_BRANCHES": truth - 1, "ROW_BY_ROW": w.row_by_row().index(x) + 1,
                 "DOWN_TO_THE_BOTTOM": w.rows()}
        want = ["Start at the top room and use the rule at each room:"]
        want += [f"  room {a}: {x} is {rel(x, a)}, go {way(x, a)}" for a in path[:-1]]
        want += [f"  room {x}: found it", f"That is {truth} rooms, counting the top room and room {x}.",
                 f"So the rabbit looks in {truth} rooms."]
    elif q == "insert":
        jars = groups(p["svg"], "newjar")
        if len(jars) != 1:
            return errs + ["no new jar in the picture"]
        x = int(jars[0][0]["data-key"])
        if texts(jars[0][1]) != [str(x)] or f"number {x}, arrives" not in p["question"] or x in w.at:
            errs.append("the new jar is drawn or named wrong")
        lower = [k for k in w.at if k < x]
        upper = [k for k in w.at if k > x]
        near = [k for k in (max(lower) if lower else None, min(upper) if upper else None) if k is not None]
        near.sort(key=lambda k: -len(w.chain(k)))
        truth = near[0]
        if len(near) == 2 and len(w.chain(near[0])) == len(w.chain(near[1])):
            errs.append("both neighbours at one depth")
        other = near[1] if len(near) == 2 else None
        if other is None or abs(other - x) >= abs(truth - x):
            errs.append("the nearest-number trap is not a trap")
            return errs
        wrong = {"NEAREST_NUMBER": other, "FIRST_TURN_ONLY": w.same_way_end(x), "SWAPS_LEFT_RIGHT": w.flipped_end(x)}
        path = w.chain(truth)
        want = ["Start at the top room and use the rule at each room:"]
        want += [f"  room {a}: {x} is {rel(x, a)}, go {way(x, a)}" for a in path[:-1]]
        want += [f"  room {truth}: {x} is {rel(x, truth)}, but there is no {way(x, truth)} tunnel",
                 f"Room {other} has a closer number, but the rule takes the jar past it.",
                 f"So the new room is dug below room {truth}."]
    elif q == "rows":
        jars = sorted(groups(p["svg"], "jar"), key=lambda g: int(g[0]["data-pos"]))
        order = [int(a["data-key"]) for a, _ in jars]
        if [int(a["data-pos"]) for a, _ in jars] != list(range(1, len(order) + 1)) or len(set(order)) != len(order):
            errs.append("the queue is out of order")
        for a, body in jars:
            if texts(body) != [a["data-key"]]:
                errs.append(f"jar {a['data-key']} is labelled {texts(body)}")
        if p["scene"].get("order") != order:
            errs.append("scene does not match the picture")
        ups = {k: above(order, k) for k in order}
        truth = max(len(v) for v in ups.values()) + 1
        n, least = len(order), 1
        while 2 ** least - 1 < n:
            least += 1
        wrong = {"ALWAYS_BALANCED": least, "EACH_NEW_ROW": n, "COUNTS_BRANCHES": truth - 1}
        want = ["Add the jars one at a time, each by the rule from the top room:", f"  {order[0]}: top room, row 1"]
        want += [f"  {k}: " + ", ".join(f"{way(k, a)} at {a}" for a in ups[k]) + f", row {len(ups[k]) + 1}"
                 for k in order[1:]]
        want += [f"The lowest room is in row {truth}.", f"So there are {truth} rows."]

    if q in ("find", "insert", "rows"):
        if p["entry"] != "number" or p["options"] or p["distractors"]:
            errs.append("typed question with options")
        if p["answer_value"] != truth:
            errs.append(f"answer {p['answer_value']}, checker says {truth}")
        got = tagmap(q, wrong, truth)
        if got is None:
            errs.append("a habit gives the right answer")
        elif vt != got:
            errs.append(f"value_tags {vt}, checker says {got}")
        elif len(got) < (3 if q == "find" else 2):
            errs.append("too few wrong values")

    if q == "order":
        par = w.parent
        keys = sorted(w.at)
        good = []
        for o in p["options"]:
            seq = [int(s) for s in o.split(", ")]
            if sorted(seq) != keys:
                errs.append(f"option {o} is not the jars in the picture")
                return errs
            if all(k == w.root or seq.index(par[k]) < seq.index(k) for k in seq):
                good.append(o)
        if len(good) != 1:
            errs.append(f"{len(good)} orders build the warren")
            return errs
        seq = [int(s) for s in good[0].split(", ")]
        if any(above(seq, k)[-1:] != ([par[k]] if k in par else []) for k in seq):
            errs.append("the right order does not build this warren")
        if p["options"][p["answer_index"]] != good[0] or p["answer_value"] != good[0] or p["entry"] != "choice":
            errs.append("answer is not the one right order")
        left_right = ", ".join(map(str, sorted(w.at, key=lambda k: w.at[k][0])))
        bottom_up = ", ".join(map(str, [k for k, _ in sorted(w.at.items(), key=lambda kv: (-kv[1][1], kv[1][0]))]))

        def one_swap_fixes(o):
            s = [int(v) for v in o.split(", ")]
            for c, pp in par.items():
                t = s[:]
                i, j = t.index(c), t.index(pp)
                t[i], t[j] = t[j], t[i]
                if all(k == w.root or t.index(par[k]) < t.index(k) for k in t):
                    return True
            return False
        dis = {d["option"]: d["misconceptions"] for d in p["distractors"]}
        if set(dis) != set(p["options"]) - {good[0]}:
            errs.append("distractors are not the other options")
        for o, tags in dis.items():
            fit = [t for t, ok in (("CHILD_BEFORE_PARENT", one_swap_fixes(o)), ("READS_LEFT_TO_RIGHT", o == left_right),
                                   ("BOTTOM_UP", o == bottom_up)) if ok]
            if not tags or not set(tags) <= set(fit):
                errs.append(f"option {o} tagged {tags}, fits {fit}")
            elif tags != sorted(tags, key=ORDER[q].index):
                errs.append("tags out of order")
        want = ["A new room can only be dug below a room that is already there. So each jar must arrive after the jar "
                "in the room just above it."]
        for o in p["options"]:
            s = [int(v) for v in o.split(", ")]
            bad = next((k for k in s if k in par and s.index(par[k]) > s.index(k)), None)
            want.append(f"  {o}: {bad} comes before {par[bad]}, the room above it" if bad is not None
                        else f"  {o}: every jar comes after the room above it")
        want.append(f"So the answer is {good[0]}.")

    if q == "pack":
        rules = read_plan(p["svg"], errs)
        cards = read_cards(p["svg"], errs)
        if list(cards) != ["A", "B", "C", "D"] or p["options"] != ["A", "B", "C", "D"] or p["entry"] != "choice":
            errs.append("the cards are not A to D")
            return errs
        if "basket" not in rules or any(r["parent"] and r["parent"] not in rules for r in rules.values()):
            errs.append("the plan is not one tree under the basket")
            return errs
        if rules.pop("basket") != {"parent": "", "min": 1, "max": 1}:
            errs.append("the plan's top is not one basket")
        verdict = {o: judge(rules, c) for o, c in cards.items()}
        good = [o for o, f in verdict.items() if not f]
        if len(good) != 1:
            errs.append(f"{len(good)} baskets follow the plan")
            return errs
        if p["options"][p["answer_index"]] != good[0] or p["answer_value"] != good[0]:
            errs.append("answer is not the basket that follows the plan")
        dis = {d["option"]: d["misconceptions"] for d in p["distractors"]}
        if set(dis) != set(cards) - set(good):
            errs.append("distractors are not the other baskets")
        for o, tags in dis.items():
            kinds = [k for k, _ in verdict[o]]
            if len(kinds) != 1 or tags != kinds:
                errs.append(f"basket {o} tagged {tags}, breaks {kinds}")
        sizes = sorted(len(c["lines"]) for c in cards.values())
        mine = len(cards[good[0]]["lines"])
        if (mine == sizes[0] and sizes[1] > mine) or (mine == sizes[-1] and sizes[-2] < mine):
            errs.append("the right basket is the only shortest or longest")
        for sc in p["scene"]["cards"]:
            c = cards[sc["option"]]
            if {k: v for k, v in sc["top"].items() if v} != {k: v for k, v in c["top"].items() if v} or \
                    sorted(map(str, sc["boxes"])) != sorted(map(str, c["boxes"])):
                errs.append(f"scene card {sc['option']} does not match the picture")
        want = ["Check every card against the plan: the fewest and the most of each thing, inside every bag and tin "
                "too, and that each thing is in its place."]
        want += [f"  {o}: " + (verdict[o][0][1] if verdict[o] else "follows every rule") for o in cards]
        want.append(f"So the answer is {good[0]}.")

    if expl != want:
        errs.append("explanation does not replay")
    if q in ("order", "pack") and vt:
        errs.append("choice question with value_tags")
    return errs


def check(p):
    try:
        return check_one(p)
    except (KeyError, ValueError, IndexError, TypeError, AttributeError) as e:
        return [f"checker could not read the problem: {e!r}"]


if __name__ == "__main__":
    sys.path.insert(0, __file__.rsplit("/", 1)[0])
    from dataclasses import asdict
    import importlib
    gen = importlib.import_module("search_tree")
    bad = 0
    for level in range(1, 6):
        for seed in range(1000, 1040):
            e = check(asdict(gen.generate(level, seed)))
            if e:
                bad += 1
                print(level, seed, e)
    print("failures:", bad)

"""
Problem family: search_tree (Rabbit Warren). Folder: rabbit-warren.

Concept targets: TREE, BST, SCHEMA (and ORDERING, which BST builds on).
Source tasks: Binary Hotel (a search tree explored one room at a time), Beaver Lunch (a tree diagram
with allowed counts that a lunch tray must follow), with Beaver Dam, Super Power Family and Mobiles
as other tree tasks in the map. Trees were the largest group of concepts with no family.

Scenario (original): a rabbit keeps numbered jars in the rooms of its warren, one jar per room. From
each room at most two tunnels lead down, one to the left and one to the right, and the rabbit keeps
to one rule: at each room a smaller number goes down the left tunnel and a bigger number down the
right one. So the warren is a binary search tree, which the student is told rather than left to
discover. Level 5 is a picnic-basket packing plan drawn as a tree with allowed counts. Our own
stories, wording, question types and pictures.

One scene model drives both the SVG picture and the solver. Rooms carry their number (data-key) at
their place in the drawing, tunnels carry their ends (data-from, data-to), arriving jars carry
their place in the queue (data-pos), the plan's parts carry their name, parent and counts, and each
line of a basket card carries what it shows. The independent checker rebuilds the warren from the
geometry (a child below and to the left of its room is the left child) and solves every question
another way.

Question types:
  find    the rabbit looks for a jar by the rule: how many rooms does it look in? (typed)
  insert  a new jar gets a new room by the rule: which room is it dug below? (typed)
  build   jars arrive in a given order into an empty warren: how many rows of rooms? (typed)
  order   which arrival order could have built this warren? (choice)
  pack    which picnic basket follows every rule of the packing plan? (choice of four cards)

Misconceptions:
  COUNTS_BRANCHES      counts the tunnels walked instead of the rooms (or rows)
  ROW_BY_ROW           looks in every room row by row instead of using the rule
  DOWN_TO_THE_BOTTOM   counts every row down to the bottom of the warren
  NEAREST_NUMBER       puts a new jar below the room with the closest number
  FIRST_TURN_ONLY      decides left or right at the top, then keeps going that way
  SWAPS_LEFT_RIGHT     sends bigger numbers left and smaller numbers right
  ALWAYS_BALANCED      assumes the rows fill up evenly, whatever the order
  EACH_NEW_ROW         thinks every new jar starts a new row
  READS_LEFT_TO_RIGHT  takes the numbers in the picture from left to right as the arrival order
  BOTTOM_UP            thinks the bottom rooms were dug first
  CHILD_BEFORE_PARENT  lets a jar arrive before the room it hangs below
  FORGETS_REQUIRED     checks only the most allowed, not the fewest
  TOP_LEVEL_ONLY       checks the counts in the basket but not inside the bags and tins
  IGNORES_NESTING      counts a thing wherever it is, not only where the plan puts it
"""

import json
import random
from dataclasses import dataclass, field, asdict

CONCEPTS = {"find": ["TREE", "BST"], "insert": ["BST", "TREE"], "rows": ["BST", "ORDERING"],
            "order": ["BST", "ORDERING"], "pack": ["SCHEMA", "TREE"]}

MISCONCEPTIONS = {
    "COUNTS_BRANCHES": {"concept": "TREE",
        "description": "Counts the tunnels (edges) between rooms instead of the rooms (nodes), so the count is one too few.",
        "remediation": "Point to each room on the way, the top one too, and count the rooms, not the tunnels between them."},
    "ROW_BY_ROW": {"concept": "BST",
        "description": "Looks in every room row by row, left to right, instead of using the rule to go straight down to the jar.",
        "remediation": "At each room the rule says which way to go. Which rooms does the rabbit never need to look in?"},
    "DOWN_TO_THE_BOTTOM": {"concept": "TREE",
        "description": "Counts every row down to the bottom of the tree, even though the search stops when it finds the jar.",
        "remediation": "The rabbit stops as soon as it finds the jar. Which row is the jar in?"},
    "NEAREST_NUMBER": {"concept": "BST",
        "description": "Puts a new number below the room with the closest number, instead of following the rule from the top.",
        "remediation": "Start at the top room and follow the rule one room at a time until there is no tunnel the way you need to go."},
    "FIRST_TURN_ONLY": {"concept": "BST",
        "description": "Compares with the top room only, then keeps going the same way to the bottom.",
        "remediation": "Compare the number with every room on the way down, not just the top one."},
    "SWAPS_LEFT_RIGHT": {"concept": "BST",
        "description": "Sends bigger numbers down the left tunnel and smaller numbers down the right.",
        "remediation": "Look at a room and the room down its left tunnel. Which number is smaller?"},
    "ALWAYS_BALANCED": {"concept": "BST",
        "description": "Assumes the tree fills each row before starting the next, so it is as short as it can be, whatever the order the numbers arrive in.",
        "remediation": "Add the jars one at a time and draw each new room. Does every row fill up before the next one starts?"},
    "EACH_NEW_ROW": {"concept": "BST",
        "description": "Thinks every new number starts a new row, as if the tree were a list.",
        "remediation": "Add the jars one at a time. Can two jars end up side by side in the same row?"},
    "READS_LEFT_TO_RIGHT": {"concept": "ORDERING",
        "description": "Takes the numbers in the picture from left to right (smallest to largest) as the order they arrived in.",
        "remediation": "Jars arriving smallest first would all go down the right tunnel, one below the other. Does this warren look like that?"},
    "BOTTOM_UP": {"concept": "ORDERING",
        "description": "Thinks the rooms at the bottom were made first and the top room last.",
        "remediation": "A new room is always dug below a room that is already there. Which room had to come first?"},
    "CHILD_BEFORE_PARENT": {"concept": "BST",
        "description": "Lets a number arrive before the number in the room it hangs below.",
        "remediation": "For each jar, find the room just above it. Did that jar arrive earlier?"},
    "FORGETS_REQUIRED": {"concept": "SCHEMA",
        "description": "Checks only the most of each thing the plan allows, not the fewest, so misses something required.",
        "remediation": "Find the parts of the plan whose smaller number is not 0. Is each of them really there?"},
    "TOP_LEVEL_ONLY": {"concept": "SCHEMA",
        "description": "Checks the counts at the top of the plan but not inside the containers lower down.",
        "remediation": "The plan has rules for what goes inside each bag and tin too. Check every one of them."},
    "IGNORES_NESTING": {"concept": "SCHEMA",
        "description": "Counts a thing wherever it is, not only in the place the plan puts it.",
        "remediation": "Each thing in the plan sits under the only place it may go. Is everything in its place?"},
}

LADDER = [
    {"level": 1, "question": "find", "n": [9, 10, 11, 12], "rows": [4, 5], "entry": "number",
     "note": "Start at the top room. At each room compare the numbers and go left for smaller, right for bigger, counting the rooms."},
    {"level": 2, "question": "insert", "n": [7, 8, 9, 10], "rows": [3, 4, 5], "entry": "number",
     "note": "Follow the rule from the top room until there is no tunnel the way you need to go. The new room is dug there."},
    {"level": 3, "question": "rows", "n": [6, 7, 8], "entry": "number",
     "note": "Add the jars one at a time, each by the rule from the top room, and draw each new room as you go."},
    {"level": 4, "question": "order", "n": [6, 7], "rows": [3, 4], "entry": "choice",
     "note": "A room can only be dug below a room that is already there, so every jar arrives after the jar just above it."},
    {"level": 5, "question": "pack", "entry": "choice",
     "note": "Check every rule in the plan: the fewest as well as the most, inside every bag and tin too, and that each thing is in its place."},
]

ORDER = {
    "find": ["COUNTS_BRANCHES", "ROW_BY_ROW", "DOWN_TO_THE_BOTTOM"],
    "insert": ["NEAREST_NUMBER", "FIRST_TURN_ONLY", "SWAPS_LEFT_RIGHT"],
    "rows": ["ALWAYS_BALANCED", "EACH_NEW_ROW", "COUNTS_BRANCHES"],
    "order": ["CHILD_BEFORE_PARENT", "READS_LEFT_TO_RIGHT", "BOTTOM_UP"],
    "pack": ["FORGETS_REQUIRED", "TOP_LEVEL_ONLY", "IGNORES_NESTING"],
}

LETTERS = ["A", "B", "C", "D"]


def tagsort(q, tags):
    return sorted(set(tags), key=lambda t: (ORDER[q].index(t), t))


def value_tags(q, truth, wrong):
    vt = {}
    for tag, v in wrong.items():
        if v is None:
            continue
        if v == truth or v < 1:
            return None
        vt.setdefault(v, []).append(tag)
    return {str(v): tagsort(q, t) for v, t in sorted(vt.items())}


# --------------------------------------------------------------------------
# The warren: a binary search tree, kids[key] = [left, right]
# --------------------------------------------------------------------------

def build_tree(order):
    root, kids = None, {}
    for k in order:
        kids[k] = [None, None]
        if root is None:
            root = k
            continue
        x = root
        while True:
            side = 0 if k < x else 1
            if kids[x][side] is None:
                kids[x][side] = k
                break
            x = kids[x][side]
    return root, kids


def depths(root, kids):
    d, todo = {root: 0}, [root]
    while todo:
        x = todo.pop()
        for c in kids[x]:
            if c is not None:
                d[c] = d[x] + 1
                todo.append(c)
    return d


def rows_of(root, kids):
    return max(depths(root, kids).values()) + 1


def level_order(root, kids):
    out, q = [], [root]
    while q:
        x = q.pop(0)
        out.append(x)
        q += [c for c in kids[x] if c is not None]
    return out


def search(root, kids, x, flip=False):
    """Rooms looked in on the way to x, or to the spot where x would go. Returns (path, side at the end)."""
    path, y = [], root
    while True:
        path.append(y)
        if y == x:
            return path, None
        side = 0 if x < y else 1
        if flip:
            side = 1 - side
        if kids[y][side] is None:
            return path, side
        y = kids[y][side]


def way(x, y):
    return "left" if x < y else "right"


def rel(x, y):
    return "smaller" if x < y else "bigger"


def order_text(order):
    return ", ".join(map(str, order))


WARREN = ("A rabbit keeps numbered jars in the rooms of its warren, one jar in each room. From each room at most two "
          "tunnels lead down, one to the left and one to the right. The rabbit always follows one rule: at each room, "
          "a smaller number goes down the left tunnel and a bigger number goes down the right tunnel.")


# --------------------------------------------------------------------------
# Level 1: find a jar
# --------------------------------------------------------------------------

def make_find(rng, cfg, seed):
    for _ in range(4000):
        n = rng.choice(cfg["n"])
        keys = rng.sample(range(10, 100), n)
        root, kids = build_tree(keys)
        R = rows_of(root, kids)
        if R not in cfg["rows"]:
            continue
        dep = depths(root, kids)
        cands = sorted(k for k in keys if dep[k] >= 1 and dep[k] + 1 < R)
        if not cands:
            continue
        x = rng.choice(cands)
        truth = dep[x] + 1
        wrong = {"COUNTS_BRANCHES": truth - 1, "ROW_BY_ROW": level_order(root, kids).index(x) + 1,
                 "DOWN_TO_THE_BOTTOM": R}
        vt = value_tags("find", truth, wrong)
        if not vt or len(vt) < 3:
            continue
        path, _ = search(root, kids, x)
        expl = ["Start at the top room and use the rule at each room:"]
        expl += [f"  room {a}: {x} is {rel(x, a)}, go {way(x, a)}" for a in path[:-1]]
        expl += [f"  room {x}: found it",
                 f"That is {truth} rooms, counting the top room and room {x}.",
                 f"So the rabbit looks in {truth} rooms."]
        scene = {"keys": keys, "root": root, "kids": kids, "target": x}
        return problem(cfg, "find", seed, scene, render_warren(scene, seed, "find"), WARREN,
                       f"The rabbit wants jar {x}. It starts at the top room and follows the rule. How many rooms "
                       f"does it look in, counting the top room and the room with jar {x}?",
                       truth, vt, expl,
                       [f"Compare {x} with the number in the top room. Which tunnel does the rabbit take?",
                        "Do the same at the next room, and the next, until you reach the jar.",
                        "Count the rooms on the way, not the tunnels between them."],
                       {"n": n, "rows": R})
    return None


# --------------------------------------------------------------------------
# Level 2: where does a new room go?
# --------------------------------------------------------------------------

def make_insert(rng, cfg, seed):
    for _ in range(4000):
        n = rng.choice(cfg["n"])
        keys = rng.sample(range(10, 100), n)
        root, kids = build_tree(keys)
        R = rows_of(root, kids)
        if R not in cfg["rows"]:
            continue
        x = rng.choice([k for k in range(10, 100) if k not in kids])
        path, side = search(root, kids, x)
        if len(path) < 3 or len(path) + 1 > max(cfg["rows"]):
            continue
        parent = path[-1]
        below = [k for k in keys if k < x]
        above = [k for k in keys if k > x]
        pred, succ = (max(below) if below else None), (min(above) if above else None)
        other = succ if parent == pred else pred
        if other is None or abs(x - other) >= abs(x - parent):
            continue                    # the closest number must be a real trap
        d, y = (0 if x < root else 1), root
        while kids[y][d] is not None:
            y = kids[y][d]
        flipped, _ = search(root, kids, x, flip=True)
        wrong = {"NEAREST_NUMBER": other, "FIRST_TURN_ONLY": y, "SWAPS_LEFT_RIGHT": flipped[-1]}
        vt = value_tags("insert", parent, wrong)
        if not vt or len(vt) < 2:
            continue
        expl = ["Start at the top room and use the rule at each room:"]
        expl += [f"  room {a}: {x} is {rel(x, a)}, go {way(x, a)}" for a in path[:-1]]
        expl.append(f"  room {parent}: {x} is {rel(x, parent)}, but there is no {way(x, parent)} tunnel")
        expl.append(f"Room {other} has a closer number, but the rule takes the jar past it.")
        expl.append(f"So the new room is dug below room {parent}.")
        scene = {"keys": keys, "root": root, "kids": kids, "new": x}
        return problem(cfg, "insert", seed, scene, render_warren(scene, seed, "insert"), WARREN,
                       f"A new jar, number {x}, arrives. The rabbit starts at the top room and follows the rule until "
                       "there is no tunnel the way it needs to go. There it digs a new room for the jar. Which room is "
                       "the new room dug below?",
                       parent, vt, expl,
                       [f"Compare {x} with the top room. Left or right?",
                        "Keep going room by room. Compare with every room on the way, not just the first.",
                        "Stop when the tunnel you need is not there. Which room are you in?"],
                       {"n": n, "rows": R})
    return None


# --------------------------------------------------------------------------
# Level 3: how tall does an arrival order make the warren?
# --------------------------------------------------------------------------

def make_build(rng, cfg, seed):
    for _ in range(4000):
        n = rng.choice(cfg["n"])
        keys = rng.sample(range(10, 100), n)
        root, kids = build_tree(keys)
        R = rows_of(root, kids)
        least = n.bit_length()          # the fewest rows n rooms can fit in
        if not least < R < n or R > 5:
            continue
        wrong = {"ALWAYS_BALANCED": least, "EACH_NEW_ROW": n, "COUNTS_BRANCHES": R - 1}
        vt = value_tags("rows", R, wrong)
        if not vt or len(vt) < 2:
            continue
        expl = ["Add the jars one at a time, each by the rule from the top room:", f"  {keys[0]}: top room, row 1"]
        sub_root, sub_kids = build_tree(keys[:1])
        for i, k in enumerate(keys[1:], 1):
            path, _ = search(sub_root, sub_kids, k)
            expl.append(f"  {k}: " + ", ".join(f"{way(k, a)} at {a}" for a in path) + f", row {len(path) + 1}")
            sub_root, sub_kids = build_tree(keys[:i + 1])
        expl.append(f"The lowest room is in row {R}.")
        expl.append(f"So there are {R} rows.")
        scene = {"order": keys}
        return problem(cfg, "rows", seed, scene, render_queue(scene, seed), WARREN,
                       "The warren is empty. These jars arrive one at a time, in this order, and each one gets a new "
                       "room by the rule. When they have all arrived, how many rows of rooms are there, counting the "
                       "top room as row 1?",
                       R, vt, expl,
                       ["The first jar gets the top room. Where does the second one go?",
                        "Draw the warren as it grows, one jar at a time.",
                        "Some rows may not fill up. Count the rows from the top room to the lowest room."],
                       {"n": n})
    return None


# --------------------------------------------------------------------------
# Level 4: which arrival order built this warren?
# --------------------------------------------------------------------------

def parent_map(kids):
    return {c: p for p, cs in kids.items() for c in cs if c is not None}


def first_too_early(order, par):
    seen = set()
    for k in order:
        if k in par and par[k] not in seen:
            return k
        seen.add(k)
    return None


def make_order(rng, cfg, seed):
    for _ in range(4000):
        n = rng.choice(cfg["n"])
        keys = rng.sample(range(10, 100), n)
        root, kids = build_tree(keys)
        R = rows_of(root, kids)
        if R not in cfg["rows"]:
            continue
        good, ready = [], [root]
        while ready:                    # any order with each jar after the room above it
            k = ready.pop(rng.randrange(len(ready)))
            good.append(k)
            ready += [c for c in kids[k] if c is not None]
        par = parent_map(kids)
        dep = depths(root, kids)
        lo = level_order(root, kids)
        bottom_up = [k for d in range(R - 1, -1, -1) for k in lo if dep[k] == d]
        c = rng.choice(sorted(par))
        swapped = good[:]
        i, j = swapped.index(c), swapped.index(par[c])
        swapped[i], swapped[j] = swapped[j], swapped[i]
        cand = {"READS_LEFT_TO_RIGHT": sorted(keys), "BOTTOM_UP": bottom_up, "CHILD_BEFORE_PARENT": swapped}
        texts = [order_text(good)] + [order_text(v) for v in cand.values()]
        if len(set(texts)) != 4:
            continue
        if any(build_tree(v)[1] == kids for v in cand.values()):
            continue
        opts = texts[:]
        rng.shuffle(opts)
        tags = {order_text(v): [t] for t, v in cand.items()}
        expl = ["A new room can only be dug below a room that is already there. So each jar must arrive after the jar "
                "in the room just above it."]
        for o in opts:
            ords = [int(s) for s in o.split(", ")]
            bad = first_too_early(ords, par)
            expl.append(f"  {o}: {bad} comes before {par[bad]}, the room above it" if bad is not None
                        else f"  {o}: every jar comes after the room above it")
        expl.append(f"So the answer is {order_text(good)}.")
        scene = {"keys": keys, "root": root, "kids": kids}
        return problem(cfg, "order", seed, scene, render_warren(scene, seed, "order"), WARREN,
                       "The rabbit started with an empty warren. Jars arrived one at a time, and each got a new room by "
                       "the rule. In which order could the jars have arrived to make this warren?",
                       order_text(good), {}, expl,
                       ["Which jar must have arrived first?",
                        "A room can only be dug below a room that is already there.",
                        "For each order, check every jar: did the jar just above it arrive earlier?"],
                       {"n": n, "rows": R},
                       options=opts, answer_index=opts.index(order_text(good)),
                       distractors=[{"option": o, "misconceptions": tagsort("order", tags[o])}
                                    for o in opts if o != order_text(good)])
    return None


# --------------------------------------------------------------------------
# Level 5: the picnic plan
# --------------------------------------------------------------------------

CONTAINERS = ["bag", "tin", "pot"]
THINGS = ["carrot", "apple", "radish", "pear", "napkin", "cup", "spoon", "berry"]
PLURAL = {"carrot": "carrots", "apple": "apples", "radish": "radishes", "pear": "pears", "napkin": "napkins",
          "cup": "cups", "spoon": "spoons", "berry": "berries", "bag": "bags", "tin": "tins", "pot": "pots"}
BOX_BOUNDS = [(0, 1), (1, 1), (1, 2), (0, 2)]
THING_BOUNDS = [(0, 1), (0, 2), (1, 1), (1, 2), (0, 3)]


def count_words(c, name):
    return f"no {PLURAL[name]}" if c == 0 else f"{c} {name if c == 1 else PLURAL[name]}"


def badge(lo, hi):
    return f"{lo}" if lo == hi else f"{lo}–{hi}"


def make_plan(rng):
    c1, c2 = rng.sample(CONTAINERS, 2)
    t = rng.sample(THINGS, 6)
    rules = [{"name": c1, "parent": "basket", "box": True}, {"name": t[0], "parent": "basket", "box": False},
             {"name": t[1], "parent": "basket", "box": False}, {"name": c2, "parent": "basket", "box": True},
             {"name": t[2], "parent": c1, "box": False}, {"name": t[3], "parent": c1, "box": False},
             {"name": t[4], "parent": c2, "box": False}, {"name": t[5], "parent": c2, "box": False}]
    for r in rules:
        r["min"], r["max"] = rng.choice(BOX_BOUNDS if r["box"] else THING_BOUNDS)
    return rules


def kids_of(rules, name):
    return [r for r in rules if r["parent"] == name]


def pack(rng, rules):
    top, boxes = {}, []
    for r in kids_of(rules, "basket"):
        if r["box"]:
            for _ in range(rng.randint(r["min"], r["max"])):
                boxes.append({"type": r["name"], "items": {j["name"]: rng.randint(j["min"], j["max"])
                                                          for j in kids_of(rules, r["name"])}})
        else:
            top[r["name"]] = rng.randint(r["min"], r["max"])
    return {"top": top, "boxes": boxes}


def faults(rules, pk):
    """Every broken rule as (kind, words for the explanation)."""
    out = []
    byname = {r["name"]: r for r in rules}
    for r in kids_of(rules, "basket"):
        c = (sum(b["type"] == r["name"] for b in pk["boxes"]) if r["box"] else pk["top"].get(r["name"], 0))
        if c < r["min"]:
            out.append(("under", f"{count_words(c, r['name'])} in the basket, but it needs at least {r['min']}"))
        if c > r["max"]:
            out.append(("over", f"{count_words(c, r['name'])} in the basket, but it holds at most {r['max']}"))
    for name, c in pk["top"].items():
        if c and byname[name]["parent"] != "basket":
            out.append(("place", f"{count_words(c, name)} loose in the basket, but "
                                 f"{PLURAL[name]} only go in a {byname[name]['parent']}"))
    for b in pk["boxes"]:
        for j in kids_of(rules, b["type"]):
            c = b["items"].get(j["name"], 0)
            if c < j["min"]:
                out.append(("under", f"a {b['type']} with {count_words(c, j['name'])}, but each {b['type']} needs "
                                     f"at least {j['min']}"))
            if c > j["max"]:
                out.append(("inside", f"a {b['type']} with {count_words(c, j['name'])}, but a {b['type']} holds "
                                      f"at most {j['max']}"))
    return out


def card_lines(rules, pk):
    order = [r["name"] for r in kids_of(rules, "basket")]
    lines = []
    for b in sorted(pk["boxes"], key=lambda b: order.index(b["type"])):
        stuff = [count_words(c, nm) for nm, c in b["items"].items() if c]
        lines.append(("box", b, f"{b['type']}: " + (", ".join(stuff) if stuff else "empty")))
    for nm, c in sorted(pk["top"].items(), key=lambda kv: (order.index(kv[0]) if kv[0] in order else 99, kv[0])):
        if c:
            lines.append(("item", (nm, c), count_words(c, nm)))
    return lines


def spoil(rng, rules, pk, tag):
    """Break exactly one kind of rule in a copy of pk, the kind the habit misses."""
    pk = json.loads(json.dumps(pk))
    if tag == "FORGETS_REQUIRED":
        need = [r for r in rules if r["min"] >= 1]
        r = rng.choice(need)
        if r["parent"] == "basket" and r["box"]:
            keep = [b for b in pk["boxes"] if b["type"] != r["name"]]
            mine = [b for b in pk["boxes"] if b["type"] == r["name"]][:r["min"] - 1]
            pk["boxes"] = keep + mine
        elif r["parent"] == "basket":
            pk["top"][r["name"]] = r["min"] - 1
        else:
            mine = [b for b in pk["boxes"] if b["type"] == r["parent"]]
            if not mine:
                return None
            rng.choice(mine)["items"][r["name"]] = r["min"] - 1
        kind = "under"
    elif tag == "TOP_LEVEL_ONLY":
        inner = [r for r in rules if r["parent"] != "basket" and r["max"] <= 2
                 and any(b["type"] == r["parent"] for b in pk["boxes"])]
        if not inner:
            return None
        r = rng.choice(inner)
        rng.choice([b for b in pk["boxes"] if b["type"] == r["parent"]])["items"][r["name"]] = r["max"] + 1
        kind = "inside"
    else:
        inner = [r for r in rules if r["parent"] != "basket"]
        r = rng.choice(inner)
        pk["top"][r["name"]] = 1
        kind = "place"
    f = faults(rules, pk)
    return pk if [k for k, _ in f] == [kind] else None


def make_pack(rng, cfg, seed):
    for _ in range(4000):
        rules = make_plan(rng)
        if sum(r["min"] >= 1 for r in rules) < 2:
            continue
        good = pack(rng, rules)
        if faults(rules, good):
            continue
        cards = {"OK": good}
        for tag in ORDER["pack"]:
            got = spoil(rng, rules, pack(rng, rules), tag)
            if not got:
                break
            cards[tag] = got
        if len(cards) != 4:
            continue
        texts = {k: tuple(t for _, _, t in card_lines(rules, v)) for k, v in cards.items()}
        if len(set(texts.values())) != 4:
            continue
        sizes = sorted(len(t) for t in texts.values())
        mine = len(texts["OK"])
        if (mine == sizes[0] and sizes[1] > mine) or (mine == sizes[-1] and sizes[-2] < mine):
            continue                    # the right card must not be the only shortest or longest
        if max(sizes) > 6 or min(sizes) < 2:
            continue
        keys = list(cards)
        rng.shuffle(keys)
        letter = {k: LETTERS[i] for i, k in enumerate(keys)}
        expl = ["Check every card against the plan: the fewest and the most of each thing, inside every bag and tin "
                "too, and that each thing is in its place."]
        for k in keys:
            f = faults(rules, cards[k])
            expl.append(f"  {letter[k]}: " + (f[0][1] if f else "follows every rule"))
        expl.append(f"So the answer is {letter['OK']}.")
        scene = {"rules": rules, "cards": [{"option": letter[k], **cards[k]} for k in keys]}
        return problem(cfg, "pack", seed, scene, render_plan(scene, seed),
                       "The rabbit packs picnic baskets from a plan. The plan is a tree: each part says what may go "
                       "inside the thing above it, and its numbers say how many. 0–2 means none, 1 or 2; 1 means "
                       "exactly 1. Nothing else may go in.",
                       "Which basket follows every rule in the plan?",
                       letter["OK"], {}, expl,
                       ["Start at the top of the plan. What must every basket have, and how many?",
                        "Now look inside each bag or tin. Does it follow the numbers under it in the plan?",
                        "Each thing in the plan sits under the only place it may go. Is everything in its place?"],
                       {},
                       options=LETTERS[:], answer_index=LETTERS.index(letter["OK"]),
                       distractors=[{"option": letter[k], "misconceptions": [k]} for k in keys if k != "OK"])
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


def problem(cfg, q, seed, scene, svg, prompt, question, truth, vt, expl, hints, knobs,
            options=None, answer_index=-1, distractors=None):
    return Problem(family="search_tree", level=cfg["level"], question_type=q, seed=seed, scene=scene, svg=svg,
                   prompt=prompt, question=question, options=options or [], answer_index=answer_index,
                   answer_value=truth, entry=cfg["entry"], distractors=distractors or [], value_tags=vt,
                   concepts=CONCEPTS[q], explanation=expl, hints=hints, knobs=knobs)


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    rng = random.Random(seed)
    make = {"find": make_find, "insert": make_insert, "rows": make_build, "order": make_order,
            "pack": make_pack}[cfg["question"]]
    p = make(rng, cfg, seed)
    if not p:
        raise RuntimeError(f"search_tree generation failed at level {level}")
    return p


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

FONT = 'font-family="Helvetica, Arial, sans-serif"'
BG, INK, SOFT = "#f4ece1", "#1f2933", "#52606d"
GRASS, SOIL, TUNNEL, ROOM, ROOM_EDGE = "#8fbf6a", "#e6d5bf", "#a47148", "#ffffff", "#7b5e43"
GOLD, GOLD_EDGE = "#ffd166", "#b7791f"
W = 420
ROW = 62
TOP = 64


def head(h, seed, kind, extra=""):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" {FONT} '
            f'class="warren" data-family="search_tree" data-kind="{kind}" data-seed="{seed}"{extra}>',
            f'<rect x="0" y="0" width="{W}" height="{h}" rx="10" fill="{BG}"/>']


def ground(out, x_hole):
    out.append(f'<path d="M0,10 a10,10 0 0 1 10,-10 h{W - 20} a10,10 0 0 1 10,10 v18 h-{W} z" fill="{GRASS}"/>')
    out.append(f'<rect x="{x_hole - 13}" y="16" width="26" height="16" rx="8" fill="{TUNNEL}"/>')


def jar(x, y, label, cls, attrs, gold=False):
    fill, edge = (GOLD, GOLD_EDGE) if gold else (ROOM, ROOM_EDGE)
    return (f'<g class="{cls}" {attrs}><rect x="{x - 17}" y="{y - 15}" width="34" height="30" rx="7" fill="{fill}" '
            f'stroke="{edge}" stroke-width="2"/><rect x="{x - 12}" y="{y - 20}" width="24" height="6" rx="2" '
            f'fill="{edge}"/><text x="{x}" y="{y + 5}" font-size="14" font-weight="bold" text-anchor="middle" '
            f'fill="{INK}">{label}</text></g>')


def render_warren(sc, seed, kind):
    root, kids = sc["root"], sc["kids"]
    dep = depths(root, kids)
    keys = sorted(kids)
    gap = (W - 60) / (len(keys) - 1)
    pos = {k: (30 + i * gap, TOP + dep[k] * ROW) for i, k in enumerate(keys)}
    R = max(dep.values()) + 1
    h = TOP + (R - 1) * ROW + 54
    extra = f' data-target="{sc["target"]}"' if kind == "find" else ""
    out = head(h, seed, kind, extra)
    ground(out, pos[root][0])
    out.append(f'<line x1="{pos[root][0]:.1f}" y1="28" x2="{pos[root][0]:.1f}" y2="{TOP - 16}" stroke="{TUNNEL}" '
               'stroke-width="7" stroke-linecap="round"/>')
    for p in keys:
        for c in kids[p]:
            if c is None:
                continue
            (x0, y0), (x1, y1) = pos[p], pos[c]
            out.append(f'<line class="tunnel" data-from="{p}" data-to="{c}" x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" '
                       f'y2="{y1:.1f}" stroke="{TUNNEL}" stroke-width="7" stroke-linecap="round"/>')
    for k in keys:
        x, y = pos[k]
        out.append(f'<g class="room" data-key="{k}"><circle cx="{x:.1f}" cy="{y:.1f}" r="16" fill="{ROOM}" '
                   f'stroke="{ROOM_EDGE}" stroke-width="2"/><text x="{x:.1f}" y="{y + 5:.1f}" font-size="13" '
                   f'font-weight="bold" text-anchor="middle" fill="{INK}">{k}</text></g>')
    if kind == "insert":
        out.append(jar(W - 40, 54, sc["new"], "newjar", f'data-key="{sc["new"]}"', gold=True))
        out.append(f'<text x="{W - 40}" y="{88}" font-size="11" text-anchor="middle" fill="{SOFT}">new jar</text>')
    out.append(f'<text x="{W / 2}" y="{h - 10}" font-size="12" text-anchor="middle" fill="{SOFT}">'
               'Down the left tunnel: smaller. Down the right tunnel: bigger.</text>')
    out.append("</svg>")
    return "".join(out)


def render_queue(sc, seed):
    order = sc["order"]
    h = 190
    out = head(h, seed, "rows", f' data-n="{len(order)}"')
    ground(out, W / 2)
    out.append(f'<circle cx="{W / 2}" cy="{TOP}" r="16" fill="none" stroke="{ROOM_EDGE}" stroke-width="2" '
               'stroke-dasharray="4 3"/>')
    out.append(f'<text x="{W / 2 + 26}" y="{TOP + 4}" font-size="12" fill="{SOFT}">empty warren</text>')
    out.append(f'<text x="20" y="{TOP + 44}" font-size="13" fill="{INK}">Jars arrive in this order:</text>')
    step = min(48, (W - 40) / len(order))
    x0 = W / 2 - step * (len(order) - 1) / 2
    for i, k in enumerate(order):
        out.append(jar(x0 + i * step, TOP + 84, k, "jar", f'data-pos="{i + 1}" data-key="{k}"'))
    out.append(f'<text x="{x0}" y="{h - 8}" font-size="11" text-anchor="middle" fill="{SOFT}">first</text>')
    out.append(f'<text x="{x0 + step * (len(order) - 1)}" y="{h - 8}" font-size="11" text-anchor="middle" '
               f'fill="{SOFT}">last</text>')
    out.append("</svg>")
    return "".join(out)


PLAN_X = {0: 60, 1: 160, 2: 260, 3: 360}
INNER_X = [48, 142, 278, 372]


def plan_box(x, y, w, label, sub, attrs):
    return (f'<g class="rule" {attrs}><rect x="{x - w / 2}" y="{y - 18}" width="{w}" height="38" rx="7" fill="{ROOM}" '
            f'stroke="{ROOM_EDGE}" stroke-width="1.5"/><text x="{x}" y="{y - 2 if sub else y + 5}" font-size="13" font-weight="bold" '
            f'text-anchor="middle" fill="{INK}">{label}</text>' +
            (f'<text x="{x}" y="{y + 14}" font-size="12" text-anchor="middle" fill="{SOFT}">{sub}</text>' if sub else "")
            + "</g>")


def render_plan(sc, seed):
    rules, cards = sc["rules"], sc["cards"]
    lines = {c["option"]: card_lines(rules, c) for c in cards}
    tops = kids_of(rules, "basket")
    where = {"basket": (W / 2, 30)}
    for i, r in enumerate(tops):
        where[r["name"]] = (PLAN_X[i], 104)
    inner = [r for r in rules if r["parent"] != "basket"]
    for i, r in enumerate(inner):
        where[r["name"]] = (INNER_X[i], 172)
    row_h = [max(len(lines[c["option"]]) for c in cards[:2]), max(len(lines[c["option"]]) for c in cards[2:])]
    card_h = [34 + 18 * n for n in row_h]
    y_cards = 222
    h = y_cards + card_h[0] + 10 + card_h[1] + 12
    out = head(h, seed, "pack")
    for r in rules:
        (x0, y0), (x1, y1) = where[r["parent"]], where[r["name"]]
        out.append(f'<line x1="{x0}" y1="{y0 + 20}" x2="{x1}" y2="{y1 - 18}" stroke="{ROOM_EDGE}" stroke-width="1.5"/>')
    out.append(plan_box(W / 2, 30, 96, "basket", "", 'data-name="basket" data-parent="" data-min="1" data-max="1"'))
    for r in rules:
        x, y = where[r["name"]]
        out.append(plan_box(x, y, 84, r["name"], badge(r["min"], r["max"]),
                            f'data-name="{r["name"]}" data-parent="{r["parent"]}" data-min="{r["min"]}" '
                            f'data-max="{r["max"]}"'))
    for i, c in enumerate(cards):
        col, row = i % 2, i // 2
        x = 12 + col * 202
        y = y_cards + (0 if row == 0 else card_h[0] + 10)
        out.append(f'<rect class="card" data-option="{c["option"]}" x="{x}" y="{y}" width="194" height="{card_h[row]}" '
                   f'rx="8" fill="{ROOM}" stroke="{ROOM_EDGE}" stroke-width="1.5"/>')
        out.append(f'<text x="{x + 12}" y="{y + 22}" font-size="15" font-weight="bold" fill="{INK}">{c["option"]}</text>')
        out.append(f'<text x="{x + 30}" y="{y + 22}" font-size="12" fill="{SOFT}">basket</text>')
        for j, (kind, what, text) in enumerate(lines[c["option"]]):
            if kind == "box":
                data = (f'data-kind="box" data-name="{what["type"]}" data-items="' +
                        " ".join(f"{nm}:{n}" for nm, n in what["items"].items()) + '"')
            else:
                data = f'data-kind="item" data-name="{what[0]}" data-count="{what[1]}"'
            out.append(f'<text class="line" data-option="{c["option"]}" {data} x="{x + 16}" y="{y + 44 + 18 * j}" '
                       f'font-size="12" fill="{INK}">{text}</text>')
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    import sys
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print(json.dumps({k: v for k, v in asdict(generate(lvl, sd)).items() if k not in ("svg",)}, indent=2, ensure_ascii=False))

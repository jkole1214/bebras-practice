"""
Problem family: gossip_rounds (Map Pieces). Folder: map-pieces.

Concept targets: PARALLEL_SPREAD, SIMULATION, LOWER_BOUND, IMPOSSIBILITY_PROOF.
Source task: Spies (Senior C).

Scenario (original): each friend holds one piece of a treasure map, marked with the first letter
of their name. The friends meet in rounds. In a round each friend meets at most one other friend,
and when two friends meet they copy each other's pieces, so both leave with every piece either had.
A friend can only pass on what they have, so a piece travels at most one meeting per round. A
meeting joins two piles, so the biggest pile, and the number of friends holding any one piece,
can at most double in a round.

This follows the idea of a parallel-gossip task (the source uses spies sharing secrets and asks
for the fewest rounds when everyone can meet everyone); the story, wording, names and pictures are
our own. We add a meeting plan to trace, a last round to choose, and friend networks where only
friends joined by a line can meet, which is what makes the fewest-rounds question vary.

One scene model (friends in a ring, the links between them, the meeting plan) drives both the SVG
picture and the solver. The picture carries each friend (data-name, data-piece), each link (data-a,
data-b) and each meeting (data-r, data-a, data-b); the independent checker rebuilds everything from
the SVG and solves it again with its own code.

Question types:
  trace   after the plan, how many pieces does one friend have? (choice at level 1, typed at level 2)
  finish  which meetings in the last round give everyone every piece? (choice; level 3)
  fewest  what is the fewest rounds until everyone has every piece? (choice at 4, typed at 5)

Misconceptions:
  PARTNERS_OWN_PIECE_ONLY    gets only each partner's own piece, not what the partner collected
  LEAVES_OUT_OWN_PIECE       forgets to count the friend's own piece
  IGNORES_ROUND_ORDER        lets a piece travel back through a meeting that happened earlier
  COUNTS_SHARED_PIECES_TWICE adds both piles together, counting shared pieces twice
  NEW_FACES_FIRST            pairs friends who have not met yet instead of checking their pieces
  WASTED_MEETING             pairs two friends who already have exactly the same pieces
  IGNORES_LINKS              answers as if everyone could meet everyone
  ODD_ONE_OUT_FREE           forgets that with an odd group someone sits out each round
  FARTHEST_PAIR_ONLY         counts only how far apart the two farthest friends are
  ONE_PIECE_PER_ROUND        thinks a friend gains one new piece per round
  FIRST_PLAN_IS_BEST         takes the first plan that works as the fewest
"""

import json
import math
import random
from dataclasses import dataclass, field, asdict
from itertools import combinations

NAMES = ["Ava", "Ben", "Cal", "Dee", "Eli", "Fay", "Gus", "Hal", "Ivy", "Jon", "Kim", "Leo",
         "Mia", "Ned", "Ola", "Pip", "Rex", "Sam", "Tia", "Uma", "Vic", "Wes", "Zoe"]

CONCEPTS = {"trace": ["PARALLEL_SPREAD", "SIMULATION"],
            "finish": ["PARALLEL_SPREAD", "SIMULATION"],
            "fewest": ["PARALLEL_SPREAD", "LOWER_BOUND", "IMPOSSIBILITY_PROOF"]}

MISCONCEPTIONS = {
    "PARTNERS_OWN_PIECE_ONLY": {"concept": "PARALLEL_SPREAD",
        "description": "Gives a friend only each partner's own piece, forgetting that the partner also hands over pieces they collected in earlier rounds.",
        "remediation": "Write what each friend has after every round, and copy the whole pile at each meeting."},
    "LEAVES_OUT_OWN_PIECE": {"concept": "SIMULATION",
        "description": "Counts the pieces a friend got from others but forgets the friend's own piece.",
        "remediation": "Start each friend's list with their own letter before any meeting."},
    "IGNORES_ROUND_ORDER": {"concept": "PARALLEL_SPREAD",
        "description": "Lets a piece travel through a meeting that happened before the friend had that piece, as if all meetings happened at once.",
        "remediation": "Go round by round. A meeting can only pass on pieces the friends already have at that moment."},
    "COUNTS_SHARED_PIECES_TWICE": {"concept": "SIMULATION",
        "description": "Adds the two friends' piles together at a meeting, so a piece both already had is counted twice.",
        "remediation": "List the letters, not just how many. A letter both friends have counts once."},
    "NEW_FACES_FIRST": {"concept": "PARALLEL_SPREAD",
        "description": "Pairs up friends who have not met yet, assuming that brings new pieces, instead of checking which pieces each one is missing.",
        "remediation": "For each friend, list the missing letters, then find a partner who has all of them."},
    "WASTED_MEETING": {"concept": "PARALLEL_SPREAD",
        "description": "Pairs two friends who already have exactly the same pieces, so the meeting gives neither of them anything.",
        "remediation": "Before pairing two friends, compare their letters. If they match, the meeting is wasted."},
    "IGNORES_LINKS": {"concept": "LOWER_BOUND",
        "description": "Gives the fewest rounds as if any two friends could meet, ignoring that only friends joined by a line can.",
        "remediation": "Try to write the fast plan using only the lines in the picture. Where does it get stuck?"},
    "ODD_ONE_OUT_FREE": {"concept": "IMPOSSIBILITY_PROOF",
        "description": "Uses only the doubling count and forgets that with an odd number of friends someone sits out every round, including the last.",
        "remediation": "Ask who sits out in the last round. That friend must already have every piece one round earlier."},
    "FARTHEST_PAIR_ONLY": {"concept": "LOWER_BOUND",
        "description": "Counts only how many meetings apart the two farthest friends are, as if pieces could travel every way at once.",
        "remediation": "Distance is one limit, but each friend meets only one other per round. Try to write a plan that short."},
    "ONE_PIECE_PER_ROUND": {"concept": "PARALLEL_SPREAD",
        "description": "Thinks a friend gains only one new piece per round, so it takes one round for each other friend.",
        "remediation": "Show a meeting where a friend with two pieces meets another friend with two: both end with four."},
    "FIRST_PLAN_IS_BEST": {"concept": "LOWER_BOUND",
        "description": "Finds one plan that works and gives its number of rounds as the fewest, without trying to do better.",
        "remediation": "After finding a plan, ask whether any round was weak, and try to do the same with one round fewer."},
}

LADDER = [
    {"level": 1, "question": "trace", "people": [5], "rounds": 2, "pairs": [2], "entry": "choice",
     "note": "Follow a two-round meeting plan for five friends and count one friend's pieces (multiple choice)."},
    {"level": 2, "question": "trace", "people": [6, 7], "rounds": 3, "pairs": [2, 3], "entry": "number",
     "note": "Follow a three-round plan for six or seven friends and type how many pieces one friend has."},
    {"level": 3, "question": "finish", "people": [6], "sizes": [3, 2], "entry": "choice",
     "note": "Two rounds are done. Pick the third round that gives everyone all six pieces."},
    {"level": 4, "question": "fewest", "people": [6, 7], "gap": 2, "entry": "choice",
     "note": "Only friends joined by a line can meet. What is the fewest rounds? Six or seven friends."},
    {"level": 5, "question": "fewest", "people": [7, 8], "gap": 3, "entry": "number",
     "note": "Fewest rounds for seven or eight friends, typed. The lines slow things down."},
]

PROMPT = ("Each friend has one piece of a treasure map, marked with the first letter of their name. "
          "The friends meet in rounds. In each round, a friend meets at most one other friend. "
          "When two friends meet, they copy each other's pieces, so both end up with every piece "
          "that either of them had.")
LINKS_NOTE = " Only friends joined by a line live close enough to meet."


# --------------------------------------------------------------------------
# Spreading pieces
# --------------------------------------------------------------------------

def play(names, rounds):
    """Each friend's pieces (a set of initials) after the plan."""
    have = {x: {x[0]} for x in names}
    for r in rounds:
        new = dict(have)
        for a, b in r:
            new[a] = new[b] = have[a] | have[b]
        have = new
    return have


def partners_only(names, rounds, x):
    return 1 + len({b if a == x else a for r in rounds for a, b in r if x in (a, b)})


def all_at_once(names, rounds, x):
    """Size of x's group if every meeting could pass pieces either way at any time."""
    seen, todo = {x}, [x]
    pairs = [m for r in rounds for m in r]
    while todo:
        y = todo.pop()
        for a, b in pairs:
            for p, q in ((a, b), (b, a)):
                if p == y and q not in seen:
                    seen.add(q)
                    todo.append(q)
    return len(seen)


def doubled(names, rounds, x):
    c = {y: 1 for y in names}
    for r in rounds:
        new = dict(c)
        for a, b in r:
            new[a] = new[b] = c[a] + c[b]
        c = new
    return c[x]


TRACE_MISTAKES = {
    "PARTNERS_OWN_PIECE_ONLY": lambda names, rounds, x, t: partners_only(names, rounds, x),
    "LEAVES_OUT_OWN_PIECE": lambda names, rounds, x, t: t - 1,
    "IGNORES_ROUND_ORDER": lambda names, rounds, x, t: all_at_once(names, rounds, x),
    "COUNTS_SHARED_PIECES_TWICE": lambda names, rounds, x, t: doubled(names, rounds, x),
}


# --------------------------------------------------------------------------
# Fewest rounds (breadth-first over who-has-what; maximal meeting sets suffice,
# since an extra meeting never takes a piece away)
# --------------------------------------------------------------------------

def maximal_matchings(n, edges):
    out = []

    def rec(i, used, cur):
        if i == len(edges):
            if all(a in used or b in used for a, b in edges):
                out.append(tuple(cur))
            return
        a, b = edges[i]
        if a not in used and b not in used:
            rec(i + 1, used | {a, b}, cur + [(a, b)])
        rec(i + 1, used, cur)
    rec(0, frozenset(), [])
    return out


def fewest(n, edges, cap=8, limit=300000):
    """(rounds, plan, layers) for the fastest plan, or None if the search is too big."""
    full = (1 << n) - 1
    ms = maximal_matchings(n, edges)
    start = tuple(1 << i for i in range(n))
    layer = {start: None}
    layers = [layer]
    for r in range(cap + 1):
        done = [s for s in layer if all(k == full for k in s)]
        if done:
            plan, s = [], done[0]
            for back in range(r, 0, -1):
                prev, m = layers[back][s]
                plan.append(m)
                s = prev
            return r, plan[::-1], layers
        nxt = {}
        for s in layer:
            for m in ms:
                k = list(s)
                for a, b in m:
                    k[a] = k[b] = s[a] | s[b]
                k = tuple(k)
                if k not in nxt:
                    nxt[k] = (s, m)
        if len(nxt) > limit:
            return None
        layer = nxt
        layers.append(layer)
    return None


def distances(n, edges):
    adj = {i: set() for i in range(n)}
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    d = {}
    for s in range(n):
        dist, q = {s: 0}, [s]
        for x in q:
            for y in adj[x]:
                if y not in dist:
                    dist[y] = dist[x] + 1
                    q.append(y)
        if len(dist) < n:
            return None
        d[s] = dist
    return d


def greedy(n, edges, cap=12):
    """A natural first plan: each round, keep pairing the two free friends who would gain the most."""
    have = [1 << i for i in range(n)]
    full = (1 << n) - 1
    for r in range(1, cap + 1):
        free, new = set(range(n)), list(have)
        while True:
            best = None
            for a, b in edges:
                if a in free and b in free:
                    g = bin(have[a] | have[b]).count("1") * 2 - bin(have[a]).count("1") - bin(have[b]).count("1")
                    if g > 0 and (best is None or g > best[0]):
                        best = (g, a, b)
            if not best:
                break
            _, a, b = best
            free -= {a, b}
            new[a] = new[b] = have[a] | have[b]
        if new == have:
            return None
        have = new
        if all(k == full for k in have):
            return r
    return None


def log2up(n):
    return math.ceil(math.log2(n))


def everyone_can_meet(n):
    return log2up(n) + n % 2


# --------------------------------------------------------------------------
# Layout and graphs
# --------------------------------------------------------------------------

CX, R_RING, NODE = 200, 140, 24


def positions(n, cy, radius):
    return [(CX + radius * math.cos(-math.pi / 2 + 2 * math.pi * i / n),
             cy + radius * math.sin(-math.pi / 2 + 2 * math.pi * i / n)) for i in range(n)]


def crosses(p, q, r, s):
    def o(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return o(p, q, r) * o(p, q, s) < 0 and o(r, s, p) * o(r, s, q) < 0


def make_links(rng, n, gap):
    for _ in range(300):
        edges = set()
        for i in range(n):
            for d in range(1, gap + 1):
                j = (i + d) % n
                if d >= n - d and j < i:
                    continue
                if rng.random() < (0.7 if d == 1 else 0.4 if d == 2 else 0.25):
                    edges.add((min(i, j), max(i, j)))
        deg = [sum(1 for e in edges if i in e) for i in range(n)]
        if min(deg) < 1:
            continue
        if not distances(n, edges):
            continue
        pos = positions(n, 0, R_RING)
        el = sorted(edges)
        cross = sum(1 for x in range(len(el)) for y in range(x + 1, len(el))
                    if not set(el[x]) & set(el[y]) and crosses(pos[el[x][0]], pos[el[x][1]], pos[el[y][0]], pos[el[y][1]]))
        if cross > n // 2:
            continue
        return el
    return None


def random_round(rng, names, k, avoid):
    for _ in range(50):
        pool = names[:]
        rng.shuffle(pool)
        r = [tuple(sorted(pool[2 * i:2 * i + 2], key=names.index)) for i in range(k)]
        if not any(frozenset(m) in avoid for m in r):
            return sorted(r, key=lambda m: names.index(m[0]))
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


def join(xs):
    xs = list(xs)
    if not xs:
        return "nobody"
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def letters(s):
    return " ".join(sorted(s))


def pieces(k):
    return f"{k} piece{'' if k == 1 else 's'}"


def rounds_word(k):
    return f"{k} round{'' if k == 1 else 's'}"


def meet_text(r, names):
    pairs = ", ".join(f"{a} & {b}" for a, b in r)
    out = sorted(set(names) - {x for m in r for x in m}, key=names.index)
    return pairs + (f" ({join(out)} {'sits' if len(out) == 1 else 'sit'} out)" if out else "")


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    rng = random.Random(seed)
    make = {"trace": make_trace, "finish": make_finish, "fewest": make_fewest}[cfg["question"]]
    for _ in range(400):
        names = rng.sample(NAMES, rng.choice(cfg["people"]))
        p = make(rng, cfg, seed, names)
        if p:
            return p
    raise RuntimeError(f"gossip_rounds generation failed at level {level}")


def round_lines(names, rounds):
    """What changes in each round, meeting by meeting."""
    out, have = [], {x: {x[0]} for x in names}
    for i, r in enumerate(rounds, 1):
        new = dict(have)
        parts = []
        for a, b in r:
            new[a] = new[b] = have[a] | have[b]
            parts.append(f"{a} and {b} both have {letters(new[a])}")
        sit = sorted(set(names) - {x for m in r for x in m}, key=names.index)
        line = f"Round {i}: " + "; ".join(parts) + "."
        if sit:
            line += f" {join(sit)} {'sits' if len(sit) == 1 else 'sit'} out."
        out.append(line)
        have = new
    return out, have


def make_trace(rng, cfg, seed, names):
    rounds, met = [], set()
    for _ in range(cfg["rounds"]):
        r = random_round(rng, names, rng.choice(cfg["pairs"]), met)
        if not r:
            return None
        rounds.append(r)
        met |= {frozenset(m) for m in r}
    have = play(names, rounds)
    order = names[:]
    rng.shuffle(order)
    n = len(names)
    for x in order:
        truth = len(have[x])
        if not 2 < truth < n:
            continue                          # someone must still be missing a piece
        wrong = {}
        for tag, f in TRACE_MISTAKES.items():
            v = f(names, rounds, x, truth)
            if v != truth:
                wrong.setdefault(v, []).append(tag)
        if partners_only(names, rounds, x) == truth:
            continue                          # the main trap must not give the right count
        if cfg["entry"] == "choice":
            ok = {v: t for v, t in wrong.items() if 0 < v <= n}
            over = [v for v in ok if v > truth]
            trap = partners_only(names, rounds, x)
            if not over or trap not in ok:
                continue
            pick = [trap, rng.choice(sorted(over))]
            rest = sorted(v for v in ok if v not in pick)
            if rest:
                pick.append(rng.choice(rest))
            opts = sorted(pick + [truth])
            distractors = [{"option": v, "misconceptions": order_tags(ok[v], "PARTNERS_OWN_PIECE_ONLY")} for v in opts if v != truth]
            entry, idx, vt = "choice", opts.index(truth), {}
        else:
            opts, distractors, entry, idx = [], [], "number", -1
            vt = {str(v): order_tags(t, "PARTNERS_OWN_PIECE_ONLY") for v, t in sorted(wrong.items()) if v >= 0}
        lines, _ = round_lines(names, rounds)
        last = len(rounds)
        expl = ["Go round by round. At each meeting, both friends get the whole pile of the other, "
                "including pieces they picked up earlier."] + lines
        expl.append(f"So after round {last}, {x} has {letters(have[x])}: {pieces(truth)}.")
        return Problem(
            family="gossip_rounds", level=cfg["level"], question_type="trace", seed=seed,
            scene={"people": names, "links": [], "rounds": [[list(m) for m in r] for r in rounds], "ask": x},
            svg=render_svg(names, [], rounds, x, seed), prompt=PROMPT,
            question=f"After round {last}, how many map pieces does {x} have? Count {x}'s own piece too.",
            options=opts, answer_index=idx, answer_value=truth, entry=entry,
            distractors=distractors, value_tags=vt, concepts=CONCEPTS["trace"], explanation=expl,
            hints=["Go one round at a time. Write the letters each friend has after round 1.",
                   "When two friends meet, each gets the other's whole pile, including pieces from earlier meetings.",
                   f"After the last round, count {x}'s letters once each, with {x}'s own."],
            knobs={"people": n, "rounds": last},
        )
    return None


def order_tags(tags, first):
    return sorted(tags, key=lambda t: (t != first, t))


def perfect_matchings(xs):
    if not xs:
        yield []
        return
    a = xs[0]
    for i in range(1, len(xs)):
        rest = xs[1:i] + xs[i + 1:]
        for m in perfect_matchings(rest):
            yield [(a, xs[i])] + m


def finish_tags(have, met, m):
    t = []
    if all(frozenset(p) not in met for p in m):
        t.append("NEW_FACES_FIRST")
    if any(have[a] == have[b] for a, b in m):
        t.append("WASTED_MEETING")
    return t


def pair_label(m):
    return ", ".join(f"{a} & {b}" for a, b in m)


def make_finish(rng, cfg, seed, names):
    n = len(names)
    rounds, met = [], set()
    for k in cfg["sizes"]:
        r = random_round(rng, names, k, met)
        if not r:
            return None
        rounds.append(r)
        met |= {frozenset(m) for m in r}
    have = play(names, rounds)
    full = {x[0] for x in names}
    alls = [sorted(m, key=lambda p: names.index(p[0])) for m in perfect_matchings(names)]
    good = [m for m in alls if all(have[a] | have[b] == full for a, b in m)]
    good = [m for m in good if any(frozenset(p) in met for p in m)]
    if not good:
        return None
    ans = rng.choice(good)
    bad = {}
    for m in alls:
        if all(have[a] | have[b] == full for a, b in m):
            continue
        t = finish_tags(have, met, m)
        if t:
            bad[pair_label(m)] = (m, t)
    news = [k for k, (m, t) in bad.items() if "NEW_FACES_FIRST" in t]
    waste = [k for k, (m, t) in bad.items() if "WASTED_MEETING" in t and k not in news]
    if not news or len(bad) < 3:
        return None
    pick = [rng.choice(sorted(news))]
    if waste:
        pick.append(rng.choice(sorted(waste)))
    rest = sorted(k for k in bad if k not in pick)
    rng.shuffle(rest)
    pick += rest[:3 - len(pick)]
    opts = [bad[k][0] for k in pick] + [ans]
    opts.sort(key=pair_label)
    opts = [[list(p) for p in m] for m in opts]
    ansl = [list(p) for p in ans]
    lines, _ = round_lines(names, rounds)
    expl = ["First work out what everyone has after round 2."] + lines
    expl.append(f"In round 3, each friend needs a partner who has every piece they are missing.")
    for a, b in ans:
        miss = full - have[a]
        expl.append(f"{a} is missing {letters(miss)}, and {b} has {letters(have[b])}, so both end with every piece.")
    for m in opts:
        if m == ansl:
            continue
        for a, b in m:
            left = full - (have[a] | have[b])
            if left:
                why = " (they already have the same pieces)" if have[a] == have[b] else ""
                expl.append(f"With {pair_label([tuple(p) for p in m])}: {a} and {b} would still miss {letters(left)}{why}.")
                break
    expl.append(f"So round 3 should be {pair_label(ans)}.")
    return Problem(
        family="gossip_rounds", level=cfg["level"], question_type="finish", seed=seed,
        scene={"people": names, "links": [], "rounds": [[list(m) for m in r] for r in rounds], "ask": ""},
        svg=render_svg(names, [], rounds, "", seed), prompt=PROMPT,
        question="Rounds 1 and 2 are done. Which meetings in round 3 give every friend all six pieces?",
        options=opts, answer_index=opts.index(ansl), answer_value=ansl, entry="choice",
        distractors=[{"option": m, "misconceptions": bad[pair_label([tuple(p) for p in m])][1]} for m in opts if m != ansl],
        value_tags={}, concepts=CONCEPTS["finish"], explanation=expl,
        hints=["Write the letters each friend has after round 2.",
               "For each friend, which letters are still missing?",
               "Meeting someone new is not enough. The partner must have every missing letter."],
        knobs={"people": n},
    )


def fewest_values(n, edges, truth):
    d = distances(n, edges)
    diam = max(max(v.values()) for v in d.values())
    vals = {"IGNORES_LINKS": everyone_can_meet(n), "FARTHEST_PAIR_ONLY": diam, "ONE_PIECE_PER_ROUND": n - 1}
    if n % 2:
        vals["ODD_ONE_OUT_FREE"] = log2up(n)
    g = greedy(n, edges)
    if g:
        vals["FIRST_PLAN_IS_BEST"] = g
    return vals, diam, d


def make_fewest(rng, cfg, seed, names):
    n = len(names)
    edges = make_links(rng, n, cfg["gap"])
    if not edges:
        return None
    res = fewest(n, edges)
    if not res:
        return None
    truth, plan, layers = res
    vals, diam, dist = fewest_values(n, edges, truth)
    if truth <= everyone_can_meet(n) or truth <= diam or truth >= n - 1:
        return None                           # the lines must matter, and the quick bounds must not settle it
    wrong = {}
    for tag, v in vals.items():
        if v != truth:
            wrong.setdefault(v, []).append(tag)
    first = "ODD_ONE_OUT_FREE" if n % 2 else "IGNORES_LINKS"
    if cfg["entry"] == "choice":
        under = sorted(v for v in wrong if v < truth)
        over = sorted(v for v in wrong if v > truth)
        if not under or not over:
            return None
        pick = [everyone_can_meet(n), rng.choice(over)]
        rest = sorted(v for v in wrong if v not in pick)
        if not rest:
            return None
        pick.append(rng.choice(rest))
        opts = sorted(pick + [truth])
        distractors = [{"option": v, "misconceptions": order_tags(wrong[v], first)} for v in opts if v != truth]
        entry, idx, vt = "choice", opts.index(truth), {}
    else:
        opts, distractors, entry, idx = [], [], "number", -1
        vt = {str(v): order_tags(t, first) for v, t in sorted(wrong.items())}
    ties = [(names[a], names[b]) for a, b in edges]
    plan_named = [[(names[a], names[b]) for a, b in m] for m in plan]
    far = max(((a, b) for a in range(n) for b in range(n) if a < b), key=lambda p: dist[p[0]][p[1]])
    # the best that one round fewer can do: fewest pieces still missing in total
    full = (1 << n) - 1
    short = min(sum(n - bin(k).count("1") for k in s) for s in layers[truth - 1])
    expl = [f"There are {n} friends, so everyone needs {n} pieces."]
    expl.append("Doubling: a meeting joins two piles, so the biggest pile can at most double each round. After 1, 2, 3 "
                f"rounds nobody has more than 2, 4, 8 pieces. Reaching {n} takes at least {rounds_word(log2up(n))}.")
    if n % 2:
        expl.append(f"Odd group: with {n} friends, someone sits out the last round, so that friend needs all {n} "
                    f"pieces one round earlier. That makes it at least {rounds_word(log2up(n) + 1)}, even if everyone could meet.")
    expl.append(f"Distance: {names[far[0]]} and {names[far[1]]} are {diam} lines apart, and a piece moves along one "
                f"line per round, so at least {rounds_word(diam)}.")
    expl.append(f"Here the lines get in the way. Trying every plan with {rounds_word(truth - 1)} shows none works: "
                f"even the best one ends with {pieces(short)} still missing, counting every friend's missing pieces together.")
    expl.append(f"A plan with {rounds_word(truth)}:")
    have = {x: {x[0]} for x in names}
    for i, m in enumerate(plan_named, 1):
        new = dict(have)
        for a, b in m:
            new[a] = new[b] = have[a] | have[b]
        have = new
        expl.append(f"Plan round {i}: {meet_text(m, names)}.")
    expl.append(f"So the fewest is {rounds_word(truth)}.")
    q = f"What is the fewest number of rounds until every friend has all {n} pieces?"
    return Problem(
        family="gossip_rounds", level=cfg["level"], question_type="fewest", seed=seed,
        scene={"people": names, "links": [list(t) for t in ties], "rounds": [], "ask": ""},
        svg=render_svg(names, ties, [], "", seed), prompt=PROMPT + LINKS_NOTE,
        question=q, options=opts, answer_index=idx, answer_value=truth, entry=entry,
        distractors=distractors, value_tags=vt, concepts=CONCEPTS["fewest"], explanation=expl,
        hints=["A meeting joins two piles, so the biggest pile can at most double each round. How many rounds until anyone could have every piece?",
               "A piece moves along one line per round, and each friend meets only one other per round. Who is hard to reach?",
               "Write a plan round by round using only the lines. Then try to do it with one round fewer."],
        knobs={"people": n, "links": len(edges), "plan": [len(m) for m in plan]},
    )


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render_svg(names, ties, rounds, ask, seed):
    n = len(names)
    W = 400
    if rounds:
        radius, cy = 82, 118
        ROW = 34
        H = cy + radius + 50 + ROW * len(rounds) + 8
    else:
        radius, cy = R_RING, 182
        H = 370
    pos = dict(zip(names, positions(n, cy, radius)))
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="Helvetica, Arial, sans-serif" class="pieces" data-family="gossip_rounds" data-seed="{seed}">',
           f'<rect x="0" y="0" width="{W}" height="{H}" rx="10" fill="#efe8d8"/>']
    for a, b in ties:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        out.append(f'<line class="link" data-a="{a}" data-b="{b}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                   f'stroke="#6b5a45" stroke-width="3" stroke-linecap="round"/>')
    for x in names:
        cx, cy0 = pos[x]
        s = x == ask
        out.append(f'<g class="friend{" ask" if s else ""}" data-name="{x}" data-piece="{x[0]}" '
                   f'aria-label="{x}, has piece {x[0]}">'
                   f'<circle cx="{cx:.1f}" cy="{cy0:.1f}" r="{NODE}" fill="{"#f2c14e" if s else "#ffffff"}" '
                   f'stroke="#3d3428" stroke-width="{3 if s else 2}"/>'
                   f'<text x="{cx:.1f}" y="{cy0 + 5.5:.1f}" font-size="16" font-weight="bold" text-anchor="middle" fill="#1f2933">{x}</text>'
                   f'<rect class="piece" x="{cx + 13:.1f}" y="{cy0 - 31:.1f}" width="18" height="18" rx="3" fill="#d9b77a" stroke="#6b5a45" stroke-width="1.5"/>'
                   f'<text x="{cx + 22:.1f}" y="{cy0 - 17.5:.1f}" font-size="12" font-weight="bold" text-anchor="middle" fill="#3d3428">{x[0]}</text></g>')
    if rounds:
        y0 = cy + radius + 46
        out.append(f'<text x="16" y="{y0 - 12:.1f}" font-size="14" font-weight="bold" fill="#3d3428">Meeting plan</text>')
        for i, r in enumerate(rounds, 1):
            y = y0 + (i - 1) * 34
            out.append(f'<g class="round" data-r="{i}"><text x="16" y="{y + 18:.1f}" font-size="14" fill="#3d3428">Round {i}</text>')
            x = 84
            for a, b in r:
                label = f"{a} &amp; {b}"
                w = 92
                out.append(f'<g class="meet" data-a="{a}" data-b="{b}"><rect x="{x}" y="{y}" width="{w}" height="26" rx="13" '
                           f'fill="#ffffff" stroke="#6b5a45" stroke-width="1.5"/>'
                           f'<text x="{x + w / 2:.1f}" y="{y + 18:.1f}" font-size="14" text-anchor="middle" fill="#1f2933">{label}</text></g>')
                x += w + 8
            out.append('</g>')
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    import sys
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print(json.dumps({k: v for k, v in asdict(generate(lvl, sd)).items() if k != "svg"}, indent=2, ensure_ascii=False))

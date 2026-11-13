"""
Problem family: best_play (Acorn Game). Folder: acorn-game.

Concept targets: GAME_TREE, WORST_CASE, INVARIANT, PERIODIC.
Source tasks: Seashells and Pebbles (2022-23 practice), Pirate Hunters (Junior C, Senior C).

Scenario (original): you play against a raccoon, a character in the story that always makes
its best move. There is no second player: the student reasons about an opponent who never
makes a mistake.

  Trail (levels 1-2): a forked trail ends at baskets of acorns. At a yellow fork you choose
  the way; at a grey fork the raccoon chooses, always the way that leaves you the fewest
  acorns. You keep the basket at the end.
  Pile (levels 3-5): you and the raccoon take turns taking acorns from one pile; the move
  sizes allowed are on a sign. Whoever takes the last acorn wins (or, at level 5 sometimes,
  loses). You go first.

This follows the idea of the source tasks (find the move that wins against every reply); the
games, story, wording, names and pictures are our own.

One scene model drives both the SVG picture and the solver. The trail picture carries each
fork (data-id, data-turn), each basket (data-id, data-acorns) and each trail (data-a, data-b);
the pile picture carries each acorn and the rule sign (data-moves, data-last). The independent
checker rebuilds the game from the picture and solves it again with different code.

Question types:
  path    which path should you take at the first fork? (trail, two forks deep; choice)
  sure    how many acorns can you be sure to get? (trail, three forks deep; typed)
  first   how many acorns should you take first to be sure to win? (pile; typed)
  traps   which piles from 1 to R are lose-piles? (pile; choice)

Misconceptions:
  BIGGEST_BASKET          heads for the biggest basket, ignoring the raccoon's choices
  RACCOON_PICKS_RANDOMLY  picks the path with the most acorns in all, as if the raccoon chose at random
  ONE_STEP_AHEAD          heads first toward the biggest basket, then plays well from there
  RACCOON_PICKS_ALL       lets the raccoon choose at every fork, even yours
  FLIPS_TURNS             mixes up whose fork is whose
  GRABS_MOST              takes as many acorns as allowed
  OFF_BY_ONE_PATTERN      thinks lose-piles come every (biggest move) acorns, not every (biggest move + 1)
  MISERE_MIXUP            uses the pattern for the other ending (last acorn wins vs loses)
  PLAIN_PATTERN           uses the "every biggest move + 1" pattern when the moves allowed have gaps
  EVEN_PILES_LOSE         thinks even piles are the lose-piles
  ONLY_FIRST_TRAP         finds the first lose-pile but not that the pattern repeats
"""

import json
import random
from dataclasses import dataclass, field, asdict

CONCEPTS = {
    "path": ["GAME_TREE", "WORST_CASE"],
    "sure": ["GAME_TREE", "WORST_CASE"],
    "first": ["GAME_TREE", "INVARIANT"],
    "traps": ["GAME_TREE", "INVARIANT", "PERIODIC"],
}

MISCONCEPTIONS = {
    "BIGGEST_BASKET": {"concept": "GAME_TREE",
        "description": "Heads for the biggest basket on the trail, forgetting that the raccoon chooses at its forks and will not let you reach it.",
        "remediation": "Play the raccoon's side yourself: at each grey fork, which way would you send your opponent?"},
    "RACCOON_PICKS_RANDOMLY": {"concept": "WORST_CASE",
        "description": "Picks the path with the most acorns in all its baskets, as if the raccoon chose at random instead of choosing its best.",
        "remediation": "Ask which single basket the raccoon would leave you on each path. The others do not count."},
    "ONE_STEP_AHEAD": {"concept": "GAME_TREE",
        "description": "Chooses the first way toward the biggest basket, then plays well from there, without checking what the raccoon does on that side.",
        "remediation": "Work back from the baskets, fork by fork, before choosing the first way."},
    "RACCOON_PICKS_ALL": {"concept": "GAME_TREE",
        "description": "Lets the raccoon choose at every fork after the first, even at forks where it is your turn to choose.",
        "remediation": "Mark each fork with whose turn it is before working out any values."},
    "FLIPS_TURNS": {"concept": "GAME_TREE",
        "description": "Mixes up whose fork is whose, taking the smaller basket at your own forks and the bigger at the raccoon's.",
        "remediation": "Colour the forks: at yours take the most, at the raccoon's expect the least."},
    "GRABS_MOST": {"concept": "GAME_TREE",
        "description": "Takes as many acorns as allowed, as if getting the pile smaller fast were the goal.",
        "remediation": "After your move, ask what the raccoon can do. Can it reach a pile that is bad for you?"},
    "OFF_BY_ONE_PATTERN": {"concept": "INVARIANT",
        "description": "Thinks the lose-piles come every (biggest move) acorns, instead of every (biggest move + 1).",
        "remediation": "Check the smallest case: with the biggest move 3, can the player to move win from a pile of 3?"},
    "MISERE_MIXUP": {"concept": "GAME_TREE",
        "description": "Uses the pattern for the other ending: plays as if the last acorn wins when it loses, or the other way round.",
        "remediation": "Reread the sign, then work out piles 1 and 2 by hand before using any pattern."},
    "PLAIN_PATTERN": {"concept": "INVARIANT",
        "description": "Uses the 'every biggest move + 1' pattern even though some move sizes are missing from the sign, which breaks that pattern.",
        "remediation": "Build the win and lose list from pile 1 upward with only the moves on the sign."},
    "EVEN_PILES_LOSE": {"concept": "PERIODIC",
        "description": "Guesses that even piles are the lose-piles, as if each player could take only one acorn.",
        "remediation": "Try pile 2 by hand: can the player to move take both acorns?"},
    "ONLY_FIRST_TRAP": {"concept": "PERIODIC",
        "description": "Finds the first lose-pile but does not see that the pattern repeats further up.",
        "remediation": "After the first lose-pile, keep going: which pile is next where every move leaves a win-pile?"},
}

LADDER = [
    {"level": 1, "question": "path", "paths": 3, "baskets": [2, 3], "entry": "choice",
     "note": "Pick the first path on a trail where the raccoon chooses next. The path with the biggest basket is a trap."},
    {"level": 2, "question": "sure", "entry": "number",
     "note": "Three forks deep (you, the raccoon, you): type how many acorns you can be sure of."},
    {"level": 3, "question": "first", "moves": [[1, 2, 3], [1, 2, 3, 4]], "pile": [6, 13], "last": ["wins"], "entry": "number",
     "note": "A small pile: type how many acorns to take first so you are sure to win."},
    {"level": 4, "question": "traps", "moves": [[1, 2], [1, 2, 3], [1, 2, 3, 4]], "upto": [12, 15], "entry": "choice",
     "note": "Find every lose-pile from 1 up: the pattern repeats."},
    {"level": 5, "question": "first", "moves": [[1, 2, 3], [1, 2, 3, 4], [1, 2, 4], [1, 3, 4], [1, 2, 3, 5], [1, 2, 3, 6], [1, 2, 4, 6], [1, 2, 3, 4, 6]],
     "pile": [14, 28], "last": ["wins", "loses"], "entry": "number",
     "note": "A big pile with a twist (moves with gaps, or the last acorn loses): type the winning first move."},
]

ORDER = {
    "path": ["BIGGEST_BASKET", "RACCOON_PICKS_RANDOMLY"],
    "sure": ["ONE_STEP_AHEAD", "BIGGEST_BASKET", "RACCOON_PICKS_ALL", "FLIPS_TURNS"],
    "first": ["MISERE_MIXUP", "PLAIN_PATTERN", "GRABS_MOST", "OFF_BY_ONE_PATTERN"],
    "traps": ["OFF_BY_ONE_PATTERN", "ONLY_FIRST_TRAP", "MISERE_MIXUP", "EVEN_PILES_LOSE"],
}

TRAIL_PROMPT = ("You and a raccoon walk down a forked trail to a basket of acorns. At a yellow fork, you choose "
                "the way. At a grey fork, the raccoon chooses, and it always picks the way that leaves you the "
                "fewest acorns in the end. You keep the basket at the end of the trail.")


def moves_text(moves):
    m = [str(x) for x in moves]
    return m[0] if len(m) == 1 else ", ".join(m[:-1]) + " or " + m[-1]


def pile_prompt(moves, last):
    return (f"You and a raccoon take turns taking acorns from one pile. On each turn you must take "
            f"{moves_text(moves)} acorns. Whoever takes the last acorn {last}. You go first, and the raccoon "
            f"always plays its best.")


def join(xs):
    xs = [str(x) for x in xs]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def tagsort(q, tags, order=None):
    order = order or ORDER[q]
    return sorted(set(tags), key=lambda t: (order.index(t), t))


# --------------------------------------------------------------------------
# Trails: a tree of nodes {id: {"turn": you|raccoon|end, "kids": [...], "acorns": n}}
# --------------------------------------------------------------------------

def value(tree, n, ops):
    """Value of node n when each turn picks with ops[turn] (max or min)."""
    t = tree[n]
    if t["turn"] == "end":
        return t["acorns"]
    return ops[t["turn"]](value(tree, k, ops) for k in t["kids"])


BEST = {"you": max, "raccoon": min}


def leaves(tree, n):
    t = tree[n]
    return [t["acorns"]] if t["turn"] == "end" else [a for k in t["kids"] for a in leaves(tree, k)]


def make_tree(rng, shape, values):
    """shape: list of branching per depth, e.g. [3, 2]. Turns alternate you, raccoon, you, ..."""
    tree, vals = {}, iter(values)

    def build(nid, depth):
        if depth == len(shape):
            tree[nid] = {"turn": "end", "kids": [], "acorns": next(vals)}
            return
        kids = [f"{nid}{i}" for i in range(shape[depth])]
        tree[nid] = {"turn": "you" if depth % 2 == 0 else "raccoon", "kids": kids}
        for k in kids:
            build(k, depth + 1)
    build("s", 0)
    return tree


def path_letter(i):
    return "ABCD"[i]


def make_path(rng, cfg, seed):
    for _ in range(400):
        nb = rng.choice(cfg["baskets"])
        tree = make_tree(rng, [cfg["paths"], nb], rng.sample(range(1, 21), cfg["paths"] * nb))
        kids = tree["s"]["kids"]
        sure = [value(tree, k, BEST) for k in kids]
        total = [sum(leaves(tree, k)) for k in kids]
        big = [max(leaves(tree, k)) for k in kids]

        def only(xs):
            top = [i for i, v in enumerate(xs) if v == max(xs)]
            return top[0] if len(top) == 1 else None
        a, b, r = only(sure), only(big), only(total)
        if a is None or b is None or r is None or len({a, b, r}) != 3:
            continue
        letters = [path_letter(i) for i in range(len(kids))]
        tagged = {letters[b]: ["BIGGEST_BASKET"], letters[r]: ["RACCOON_PICKS_RANDOMLY"]}
        ans = letters[a]
        expl = ["The raccoon chooses last on every path, so on each path it leaves you the smallest basket:"]
        for i, k in enumerate(kids):
            expl.append(f"Path {letters[i]}: the baskets hold {join(leaves(tree, k))}, so the raccoon leaves you {sure[i]}.")
        expl.append(f"Path {letters[b]} has the biggest basket ({big[b]}), but the raccoon would never let you have it.")
        expl.append(f"Path {letters[r]} has the most acorns in all ({total[r]}), but you only get one basket, and the raccoon picks it.")
        expl.append(f"So take path {ans}: you are sure to get {sure[a]} acorns.")
        return Problem(
            family="best_play", level=cfg["level"], question_type="path", seed=seed,
            scene={"tree": tree}, svg=render_trail(tree, seed), prompt=TRAIL_PROMPT,
            question="Which path should you take at the first fork, to be sure of the most acorns?",
            options=letters, answer_index=a, answer_value=ans, entry="choice",
            distractors=[{"option": x, "misconceptions": tagged[x]} for x in letters if x != ans],
            value_tags={}, concepts=CONCEPTS["path"], explanation=expl,
            hints=["You choose first, but on every path the raccoon chooses after you.",
                   "For each path, which basket would the raccoon leave you?",
                   "Compare those baskets, one per path. The biggest basket on the trail does not matter."],
            knobs={"paths": len(kids), "baskets": nb},
        )
    return None


def make_sure(rng, cfg, seed):
    for _ in range(600):
        tree = make_tree(rng, [2, 2, 2], [rng.randint(1, 20) for _ in range(8)])
        kids = tree["s"]["kids"]
        truth = value(tree, "s", BEST)
        allv = leaves(tree, "s")
        if allv.count(max(allv)) != 1:
            continue
        bigk = next(k for k in kids if max(allv) in leaves(tree, k))
        wrong = {
            "BIGGEST_BASKET": max(allv),
            "ONE_STEP_AHEAD": value(tree, bigk, BEST),
            "RACCOON_PICKS_ALL": max(min(leaves(tree, k)) for k in kids),
            "FLIPS_TURNS": value(tree, "s", {"you": min, "raccoon": max}),
        }
        if wrong["ONE_STEP_AHEAD"] == truth or wrong["BIGGEST_BASKET"] == truth:
            continue
        vt = {}
        for tag, v in wrong.items():
            if v != truth:
                vt.setdefault(v, []).append(tag)
        if len(vt) < 3:
            continue
        # your last forks are numbered 1-4 in the picture, left to right
        mine = [g for k in kids for g in tree[k]["kids"]]
        num = {g: i + 1 for i, g in enumerate(mine)}
        for g in mine:
            tree[g]["label"] = str(num[g])
        for i, k in enumerate(kids):
            tree[k]["label"] = path_letter(i)
        expl = ["Work back from the baskets. At each of your last forks you take the bigger basket:"]
        expl.append(", ".join(f"fork {num[g]}: {max(leaves(tree, g))}" for g in mine) + ".")
        for i, k in enumerate(kids):
            g1, g2 = tree[k]["kids"]
            v1, v2 = value(tree, g1, BEST), value(tree, g2, BEST)
            expl.append(f"On path {path_letter(i)} the raccoon chooses between fork {num[g1]} ({v1}) and fork {num[g2]} ({v2}), "
                        f"so it sends you to the one worth {min(v1, v2)}.")
        best_i = max(range(2), key=lambda i: value(tree, kids[i], BEST))
        expl.append(f"At the first fork, take path {path_letter(best_i)}.")
        expl.append(f"The {max(allv)} basket is the biggest, but the raccoon can always keep you away from it.")
        expl.append(f"So you can be sure of {truth} acorns.")
        return Problem(
            family="best_play", level=cfg["level"], question_type="sure", seed=seed,
            scene={"tree": tree}, svg=render_trail(tree, seed), prompt=TRAIL_PROMPT,
            question="If you play your best, how many acorns can you be sure to get?",
            options=[], answer_index=-1, answer_value=truth, entry="number",
            distractors=[], value_tags={str(v): tagsort("sure", t) for v, t in sorted(vt.items())},
            concepts=CONCEPTS["sure"], explanation=expl,
            hints=["Start at the bottom. At a yellow fork near the baskets, which basket would you take?",
                   "Write that number on the fork. Then at each grey fork, the raccoon picks the smaller number.",
                   "Keep going up to the first fork, where you pick the bigger number again."],
            knobs={"leaves": 8},
        )
    return None


# --------------------------------------------------------------------------
# Piles
# --------------------------------------------------------------------------

def lose_table(n, moves, last):
    """lose[p]: the player about to move from a pile of p loses with best play on both sides."""
    lose = [last == "wins"]          # pile 0: the other player just took the last acorn
    for p in range(1, n + 1):
        lose.append(all(not lose[p - m] for m in moves if m <= p))
    return lose


def mistake_moves(n, moves, last):
    """The first move a student with each habit would make from a pile of n."""
    k = max(moves)
    plain = list(moves) == list(range(1, k + 1))
    out = {"GRABS_MOST": k}
    if plain:
        if last == "wins":
            out["OFF_BY_ONE_PATTERN"] = n % k or k          # leave a multiple of k
            out["MISERE_MIXUP"] = (n - 1) % (k + 1)
        else:
            out["OFF_BY_ONE_PATTERN"] = (n - 1) % k or k
            out["MISERE_MIXUP"] = n % (k + 1)
    else:
        out["PLAIN_PATTERN"] = n % (k + 1)
    return {t: m for t, m in out.items() if m in moves and m <= n}


def first_order(moves, last):
    """The trap each game is about comes first, so the page asks about it."""
    if last == "loses":
        return ["MISERE_MIXUP", "OFF_BY_ONE_PATTERN", "GRABS_MOST", "PLAIN_PATTERN"]
    if moves != list(range(1, max(moves) + 1)):
        return ["PLAIN_PATTERN", "GRABS_MOST", "OFF_BY_ONE_PATTERN", "MISERE_MIXUP"]
    return ["OFF_BY_ONE_PATTERN", "GRABS_MOST", "MISERE_MIXUP", "PLAIN_PATTERN"]


def make_first(rng, cfg, seed):
    last = rng.choice(cfg["last"])                  # level 5: half the time the last acorn loses
    for _ in range(2000):
        plain_sets = [m for m in cfg["moves"] if m == list(range(1, max(m) + 1))]
        if cfg["level"] == 5 and last == "wins":
            moves = rng.choice([m for m in cfg["moves"] if m not in plain_sets])   # the twist: moves with gaps
        else:
            moves = rng.choice(plain_sets)          # level 5 twists one thing at a time
        n = rng.randint(*cfg["pile"])
        lose = lose_table(n, moves, last)
        wins = [m for m in moves if m <= n and lose[n - m]]
        if len(wins) != 1:
            continue
        truth = wins[0]
        wrong = mistake_moves(n, moves, last)
        if any(v == truth for v in wrong.values()):
            continue                  # a habit must not land on the right move
        vt = {}
        for tag, v in wrong.items():
            vt.setdefault(v, []).append(tag)
        main = "MISERE_MIXUP" if last == "loses" else "PLAIN_PATTERN"
        if cfg["level"] == 5 and main not in wrong:
            continue
        if len(vt) < 2:
            continue
        losers = [p for p in range(1, n + 1) if lose[p]]
        plain = moves == list(range(1, max(moves) + 1))
        k = max(moves)
        expl = [f"Work up from small piles. A pile is a lose-pile if every move from it leaves a win-pile for the other player, "
                f"and a win-pile if some move leaves a lose-pile."]
        if last == "loses":
            expl.append("A pile of 1 is a lose-pile: you must take the last acorn, and taking the last acorn loses.")
        else:
            expl.append(f"Piles of {moves_text([m for m in moves])} are win-piles: you take them all and win.")
        expl.append(f"Lose-piles up to {n}: {join(losers)}.")
        steps = {b - a for a, b in zip(losers, losers[1:])}
        if plain:
            gap = k + 1
            expl.append(f"They come every {gap} acorns: whatever one player takes, the other can take enough to make {gap} together.")
        elif len(steps) == 1 and len(losers) > 1:
            expl.append(f"Here they come every {steps.pop()} acorns, not every {k + 1}, because some move sizes are missing from the sign.")
        expl.append(f"From {n}, taking {truth} leaves {n - truth}, a lose-pile for the raccoon.")
        others = [m for m in moves if m <= n and m != truth]
        if others:
            expl.append(f"Taking {join(others).replace(' and ', ' or ')} would leave "
                        f"{join([n - m for m in others]).replace(' and ', ' or ')}, "
                        f"{'each a win-pile' if len(others) > 1 else 'a win-pile'} for the raccoon.")
        expl.append(f"So take {truth} acorn{'s' if truth != 1 else ''} first.")
        return Problem(
            family="best_play", level=cfg["level"], question_type="first", seed=seed,
            scene={"pile": n, "moves": moves, "last": last}, svg=render_pile(n, moves, last, seed),
            prompt=pile_prompt(moves, last),
            question=f"The pile has {n} acorns. How many should you take on your first turn, to be sure to win?",
            options=[], answer_index=-1, answer_value=truth, entry="number", distractors=[],
            value_tags={str(v): tagsort("first", t, first_order(moves, last)) for v, t in sorted(vt.items())},
            concepts=CONCEPTS["first"], explanation=expl,
            hints=["Taking the most is not always best. Think about what pile the raccoon will face.",
                   "Start tiny: from a pile of 1, 2, 3 ..., can the player whose turn it is win?",
                   "Find the piles where every move loses. Then leave the raccoon one of those."],
            knobs={"pile": n, "moves": moves, "last": last},
        )
    return None


def make_traps(rng, cfg, seed):
    for _ in range(200):
        moves = rng.choice(cfg["moves"])
        k = max(moves)
        upto = rng.randint(*cfg["upto"])
        lose = lose_table(upto, moves, "wins")
        truth = [p for p in range(1, upto + 1) if lose[p]]
        if len(truth) < 2:
            continue
        cands = {
            "OFF_BY_ONE_PATTERN": [p for p in range(1, upto + 1) if p % k == 0],
            "ONLY_FIRST_TRAP": truth[:1],
            "MISERE_MIXUP": [p for p in range(1, upto + 1) if p % (k + 1) == 1],
            "EVEN_PILES_LOSE": [p for p in range(1, upto + 1) if p % 2 == 0],
        }
        tagged = {}
        for tag, v in cands.items():
            if v != truth:
                tagged.setdefault(tuple(v), []).append(tag)
        wrong = sorted(tagged, key=lambda v: ORDER["traps"].index(tagsort("traps", tagged[v])[0]))[:3]
        if len(wrong) < 3:
            continue
        opts = [list(v) for v in wrong] + [truth]
        lens = [len(o) for o in opts]
        if not min(lens) < len(truth) < max(lens):
            continue                  # the right list must be neither the shortest nor the longest
        rng.shuffle(opts)
        a = opts.index(truth)
        gap = k + 1
        expl = [f"Piles of {moves_text(moves)} are win-piles: you take them all and win.",
                f"Pile {gap}: every move ({moves_text(moves)}) leaves {moves_text([gap - m for m in moves])}, "
                f"and the other player takes the rest. So {gap} is a lose-pile.",
                f"Piles {join(range(gap + 1, min(2 * gap - 1, upto) + 1))} are win-piles: take enough to leave {gap}.",
                f"The pattern repeats every {gap} acorns: whatever one player takes, the other can take enough to make {gap} together.",
                f"So the lose-piles are {join(truth)}."]
        return Problem(
            family="best_play", level=cfg["level"], question_type="traps", seed=seed,
            scene={"moves": moves, "last": "wins", "upto": upto}, svg=render_strip(upto, moves, seed),
            prompt=pile_prompt(moves, "wins"),
            question=(f"A lose-pile is a pile where whoever's turn it is will lose if the other player plays their best. "
                      f"Which piles from 1 to {upto} are lose-piles?"),
            options=opts, answer_index=a, answer_value=truth, entry="choice",
            distractors=[{"option": o, "misconceptions": tagsort("traps", tagged[tuple(o)])} for o in opts if o != truth],
            value_tags={}, concepts=CONCEPTS["traps"], explanation=expl,
            hints=["Start with tiny piles. From 1 acorn, can the player whose turn it is win?",
                   f"Find the first pile where every move ({moves_text(moves)}) leaves a pile the other player can win.",
                   "Once you have the first lose-pile, look for the next one. Does the gap repeat?"],
            knobs={"moves": moves, "upto": upto},
        )
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
    make = {"path": make_path, "sure": make_sure, "first": make_first, "traps": make_traps}[cfg["question"]]
    p = make(rng, cfg, seed)
    if not p:
        raise RuntimeError(f"best_play generation failed at level {level}")
    return p


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

FONT = 'font-family="Helvetica, Arial, sans-serif"'


def svg_open(w, h, cls, seed):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" {FONT} '
            f'class="{cls}" data-family="best_play" data-seed="{seed}">',
            f'<rect x="0" y="0" width="{w}" height="{h}" rx="10" fill="#eef2e6"/>']


def render_trail(tree, seed):
    W = 400
    depth = {"s": 0}
    order = ["s"]
    for nid in order:
        for k in tree[nid]["kids"]:
            depth[k] = depth[nid] + 1
            order.append(k)
    leaves_ = [n for n in order if tree[n]["turn"] == "end"]
    maxd = max(depth.values())
    top, step = 62, (218 if maxd == 2 else 236) / maxd
    gap = (W - 40) / len(leaves_)
    pos = {n: (20 + gap * (i + .5), top + step * depth[n]) for i, n in enumerate(leaves_)}
    for n in reversed(order):
        if tree[n]["turn"] != "end":
            xs = [pos[k][0] for k in tree[n]["kids"]]
            pos[n] = (sum(xs) / len(xs), top + step * depth[n])
    H = int(top + step * maxd + 38)
    out = svg_open(W, H, "trail", seed)
    out.append('<g class="key" font-size="13" fill="#2b3a2b">'
               '<circle cx="28" cy="22" r="9" fill="#f2c14e" stroke="#33414e" stroke-width="2"/>'
               '<text x="43" y="27">You choose</text>'
               '<circle cx="150" cy="22" r="9" fill="#9aa5b1" stroke="#33414e" stroke-width="2"/>'
               '<text x="165" y="27">Raccoon chooses</text></g>')
    for n in order:
        for k in tree[n]["kids"]:
            (x1, y1), (x2, y2) = pos[n], pos[k]
            out.append(f'<line class="trail" data-a="{n}" data-b="{k}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                       f'stroke="#8a6d3b" stroke-width="4" stroke-linecap="round"/>')
    for i, k in enumerate(tree["s"]["kids"]):
        (x1, y1), (x2, y2) = pos["s"], pos[k]
        mx, my = x1 + (x2 - x1) * .55, y1 + (y2 - y1) * .55
        out.append(f'<g class="path" data-for="{k}"><circle cx="{mx:.1f}" cy="{my:.1f}" r="11" fill="#ffffff" stroke="#8a6d3b" stroke-width="1.5"/>'
                   f'<text x="{mx:.1f}" y="{my + 4.5:.1f}" font-size="13" font-weight="bold" text-anchor="middle" fill="#1f2933">{path_letter(i)}</text></g>')
    for n in order:
        t = tree[n]
        x, y = pos[n]
        if t["turn"] == "end":
            out.append(f'<g class="basket" data-id="{n}" data-acorns="{t["acorns"]}">'
                       f'<rect x="{x - 17:.1f}" y="{y - 4:.1f}" width="34" height="28" rx="6" fill="#c98a4b" stroke="#6b4423" stroke-width="2"/>'
                       f'<text x="{x:.1f}" y="{y + 15.5:.1f}" font-size="15" font-weight="bold" text-anchor="middle" fill="#ffffff">{t["acorns"]}</text></g>')
        else:
            you = t["turn"] == "you"
            lab = t.get("label", "") if you else ""
            la = f' data-label="{lab}"' if lab else ""
            out.append(f'<g class="fork" data-id="{n}" data-turn="{t["turn"]}"{la}>'
                       f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{12 if lab or n == "s" else 10}" fill="{"#f2c14e" if you else "#9aa5b1"}" '
                       f'stroke="#33414e" stroke-width="2"/>'
                       + (f'<text x="{x:.1f}" y="{y + 4.5:.1f}" font-size="13" font-weight="bold" text-anchor="middle" fill="#1f2933">{lab}</text>' if lab else "")
                       + '</g>')
    out.append("</svg>")
    return "".join(out)


def acorn(x, y):
    return (f'<g class="acorn"><ellipse cx="{x:.1f}" cy="{y + 4:.1f}" rx="9" ry="11" fill="#b5733a"/>'
            f'<path d="M{x - 11:.1f},{y - 2:.1f} Q{x:.1f},{y - 14:.1f} {x + 11:.1f},{y - 2:.1f} Z" fill="#6b4423"/>'
            f'<line x1="{x:.1f}" y1="{y - 8:.1f}" x2="{x + 2:.1f}" y2="{y - 13:.1f}" stroke="#6b4423" stroke-width="2.5" stroke-linecap="round"/></g>')


def sign(moves, last, y):
    return (f'<g class="rule" data-moves="{",".join(map(str, moves))}" data-last="{last}">'
            f'<rect x="60" y="{y}" width="280" height="50" rx="8" fill="#ffffff" stroke="#6b4423" stroke-width="2"/>'
            f'<text x="200" y="{y + 21}" font-size="15" font-weight="bold" text-anchor="middle" fill="#1f2933">Take {moves_text(moves)} each turn</text>'
            f'<text x="200" y="{y + 41}" font-size="14" text-anchor="middle" fill="#1f2933">Last acorn {last}</text></g>')


def render_pile(n, moves, last, seed):
    W, per = 400, 10
    rows = (n + per - 1) // per
    H = 84 + rows * 34
    out = svg_open(W, H, "acorns", seed)
    out.append(sign(moves, last, 12))
    out.append(f'<g class="pile" data-count="{n}">')
    for i in range(n):
        r, c = divmod(i, per)
        out.append(acorn(47 + c * 34, 90 + r * 34))
    out.append("</g></svg>")
    return "".join(out)


def render_strip(upto, moves, seed):
    W, per = 400, 8
    rows = (upto + per - 1) // per
    H = 84 + rows * 46
    out = svg_open(W, H, "acorns", seed)
    out.append(sign(moves, "wins", 12))
    for p in range(1, upto + 1):
        r, c = divmod(p - 1, per)
        x, y = 30 + c * 44, 78 + r * 46
        out.append(f'<g class="size" data-n="{p}"><rect x="{x}" y="{y}" width="38" height="38" rx="6" fill="#ffffff" stroke="#8a6d3b" stroke-width="1.5"/>'
                   f'<text x="{x + 19}" y="{y + 25}" font-size="16" font-weight="bold" text-anchor="middle" fill="#1f2933">{p}</text></g>')
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    import sys
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print(json.dumps({k: v for k, v in asdict(generate(lvl, sd)).items() if k != "svg"}, indent=2, ensure_ascii=False))

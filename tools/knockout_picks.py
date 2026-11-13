"""
Problem family: knockout_picks (Puppy Picks). Folder: puppy-picks.

Concept targets: TOURNAMENT_MAX, LOWER_BOUND (and ELIMINATION at level 1).
Source task: Favorite Gem (Junior C, Senior B, 2022-23 practice).

Scenario (original): a puppy has one favourite toy but can't say which. In a round you put a few
toys in front of it and it grabs the one it likes best; it always likes the same toys best. A round
can include the winner of an earlier round ("W2" is the toy grabbed in round 2). Each round leaves
behind at most (size - 1) toys, and every toy but the favourite has to be left behind once, so
q rounds of k toys find the favourite among at most 1 + q(k - 1) toys; a knockout reaches it.

This follows the idea of the source task (counting eliminations per question, carrying the winner
forward); the story, wording, question types and pictures are our own.

One scene model drives both the SVG picture and the solver. The picture carries every round and
toy (data-round, data-toy, data-grabbed), every basket size (data-size) and every plan slot
(data-plan, data-round, data-item). The independent checker rebuilds the problem from the picture
and solves it another way: crossing out toys for level 1, a game search over (toys never shown,
toys shown and never left behind) for the counting levels, and trying every toy as the favourite
for the plans.

Question types:
  who      rounds and grabs are shown: which toy is the favourite? (choice)
  fewest   n toys, up to k a round: the fewest rounds that always find it (typed)
  most     q rounds of up to k toys: the most toys it can always be found among (typed)
  plan     which of four plans always finds the favourite? (choice)
  mixed    rounds of different sizes: the most toys (typed)

Misconceptions:
  LAST_ROUND_DECIDES      gives the toy grabbed in the last round shown
  MOST_WINS               gives the toy grabbed in the most rounds
  FIRST_ROUND_DECIDES     gives the toy grabbed in the first round
  WINNER_NOT_CARRIED      counts k new toys a round, forgetting the winner takes a place (in the map already)
  FAVOURITE_RULED_OUT     counts the favourite among the toys that must be left behind
  GROUPS_THEN_FINAL       plays separate groups first and then a final of the winners
  ROUNDS_DOWN             rounds the number of rounds down, leaving toys never shown
  WINNER_DROPPED          accepts a plan where an earlier winner never plays again
  TOY_LEFT_OUT            accepts a plan that never shows one of the toys
  CARRIES_TOY_NOT_WINNER  accepts a plan that carries a named toy forward instead of the winner
  BIGGEST_ROUND_ONLY      treats every round as the size of the biggest one
"""

import json
import random
from dataclasses import dataclass, field, asdict

CONCEPTS = {"who": ["ELIMINATION", "TOURNAMENT_MAX"], "fewest": ["TOURNAMENT_MAX", "LOWER_BOUND"],
            "most": ["TOURNAMENT_MAX", "LOWER_BOUND"], "plan": ["TOURNAMENT_MAX", "ELIMINATION"],
            "mixed": ["TOURNAMENT_MAX", "LOWER_BOUND"]}

MISCONCEPTIONS = {
    "LAST_ROUND_DECIDES": {"concept": "ELIMINATION",
        "description": "Takes the toy grabbed in the last round shown as the favourite, even though it was left behind in another round.",
        "remediation": "The order of the rounds doesn't matter. Cross out every toy that was left behind in any round."},
    "MOST_WINS": {"concept": "ELIMINATION",
        "description": "Takes the toy grabbed in the most rounds as the favourite, even though it was left behind once.",
        "remediation": "One round where a toy is left behind is enough to rule it out, however often it was grabbed."},
    "FIRST_ROUND_DECIDES": {"concept": "ELIMINATION",
        "description": "Takes the toy grabbed in the first round as the favourite without checking the later rounds.",
        "remediation": "Check every round. Was that toy left behind anywhere?"},
    "FAVOURITE_RULED_OUT": {"concept": "TOURNAMENT_MAX",
        "description": "Counts every toy as needing to be left behind, the favourite too, so the count is off by one toy.",
        "remediation": "The favourite is never left behind. Only the other toys need to be ruled out."},
    "GROUPS_THEN_FINAL": {"concept": "TOURNAMENT_MAX",
        "description": "Plays separate groups first and then a final of the winners, which wastes places when the groups don't fill the rounds.",
        "remediation": "Count what each round leaves behind. A round with empty places rules out fewer toys."},
    "ROUNDS_DOWN": {"concept": "LOWER_BOUND",
        "description": "Rounds the number of rounds down, so some toys are never left behind.",
        "remediation": "If the division doesn't come out even, the leftover toys still need a round."},
    "WINNER_DROPPED": {"concept": "TOURNAMENT_MAX",
        "description": "Accepts a plan where the winner of an earlier round never plays again, so the favourite could be lost there.",
        "remediation": "Pretend the winner of that round is the favourite. Does it reach the last round?"},
    "TOY_LEFT_OUT": {"concept": "ELIMINATION",
        "description": "Accepts a plan that never shows the puppy one of the toys.",
        "remediation": "Check off every toy. A toy that is never shown could be the favourite."},
    "CARRIES_TOY_NOT_WINNER": {"concept": "TOURNAMENT_MAX",
        "description": "Carries a named toy from one round into the next instead of the toy the puppy grabbed.",
        "remediation": "Only the grabbed toy is still in the running. Which toy goes on: a named one, or the winner?"},
    "BIGGEST_ROUND_ONLY": {"concept": "TOURNAMENT_MAX",
        "description": "Treats every round as if it were as big as the biggest one.",
        "remediation": "Work out each round on its own: how many toys does that round leave behind?"},
}
# already in the map (from the Favorite Gem analysis); this family is the first to use it
USES_EXISTING = ["WINNER_NOT_CARRIED"]

LADDER = [
    {"level": 1, "question": "who", "toys": [6, 7, 8], "rounds": [4, 5], "k": 3, "entry": "choice",
     "note": "Follow the rounds: a toy left behind in any round is not the favourite, whatever order the rounds come in."},
    {"level": 2, "question": "fewest", "toys": list(range(7, 16)), "k": [2, 3, 3], "entry": "number",
     "note": "Each round leaves behind at most all but one of its toys. How many rounds to rule out every toy but one?"},
    {"level": 3, "question": "most", "q": [3, 4, 5], "k": [2, 3, 4, 5], "entry": "number",
     "note": "Turn it round: with a set number of rounds, how many toys can you handle? The winner takes a place each time."},
    {"level": 4, "question": "plan", "q": [3, 4], "k": [3], "entry": "choice",
     "note": "Check a plan by pretending each toy is the favourite: is it shown, and does every winner play on?"},
    {"level": 5, "question": "mixed", "q": [3, 4], "sizes": [2, 3, 4, 5], "entry": "number",
     "note": "Rounds of different sizes: add up what each round leaves behind, then add the favourite."},
]

ORDER = {
    "who": ["LAST_ROUND_DECIDES", "MOST_WINS", "FIRST_ROUND_DECIDES"],
    "fewest": ["WINNER_NOT_CARRIED", "FAVOURITE_RULED_OUT", "ROUNDS_DOWN"],
    "most": ["WINNER_NOT_CARRIED", "FAVOURITE_RULED_OUT", "GROUPS_THEN_FINAL"],
    "plan": ["WINNER_DROPPED", "TOY_LEFT_OUT", "CARRIES_TOY_NOT_WINNER"],
    "mixed": ["BIGGEST_ROUND_ONLY", "WINNER_NOT_CARRIED", "FAVOURITE_RULED_OUT"],
}

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWX"


def tagsort(q, tags):
    return sorted(set(tags), key=lambda t: (ORDER[q].index(t), t))


def toys(m):
    return f"{m} toy" + ("" if m == 1 else "s")


def ceil_div(a, b):
    return -(-a // b)


PROMPT = ("A puppy has one favourite toy, but it can't tell you which. In a round you put a few toys in front of it, "
          "and it grabs the one it likes best of those. It always likes the same toys best: if it grabs one toy "
          "over another once, it would do it again.")
PROMPT_W = PROMPT + " A round can include the winner of an earlier round: W2 means the toy the puppy grabbed in round 2."


# --------------------------------------------------------------------------
# The bound and a plan that reaches it
# --------------------------------------------------------------------------

def most_toys(sizes):
    return 1 + sum(s - 1 for s in sizes)


def chain_plan(sizes, n):
    """A knockout for n toys in rounds of these sizes: each round after the first starts with the last winner."""
    rounds, nxt = [], 0
    for i, s in enumerate(sizes):
        items = [] if i == 0 else [f"W{i}"]
        while len(items) < s and nxt < n:
            items.append(LETTERS[nxt])
            nxt += 1
        rounds.append(items)
    assert nxt == n
    return rounds


def plan_lines(rounds):
    return [f"  Round {i + 1}: {' '.join(r)}" for i, r in enumerate(rounds)]


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
# Level 1: who is the favourite?
# --------------------------------------------------------------------------

def make_who(rng, cfg, seed):
    for _ in range(20000):
        n = rng.choice(cfg["toys"])
        nr = rng.choice(cfg["rounds"])
        toys = list(LETTERS[:n])
        like = toys[:]
        rng.shuffle(like)                       # like[0] is the favourite
        rank = {t: i for i, t in enumerate(like)}
        rounds = []
        for _ in range(nr):
            size = rng.choice([2, 3, 3, 3]) if cfg["k"] >= 3 else 2
            items = sorted(rng.sample(toys, size))
            rounds.append({"toys": items, "grabbed": min(items, key=rank.get)})
        left = {t for r in rounds for t in r["toys"] if t != r["grabbed"]}
        shown = {t for r in rounds for t in r["toys"]}
        if shown != set(toys):
            continue
        never = [t for t in toys if t not in left]
        if never != [like[0]]:
            continue
        fav = like[0]
        wins = {t: sum(r["grabbed"] == t for r in rounds) for t in toys}
        top = max(wins.values())
        most = [t for t in toys if wins[t] == top]
        tags = {}
        last, first = rounds[-1]["grabbed"], rounds[0]["grabbed"]
        if len(most) != 1 or most[0] == fav or last == fav or first == fav:
            continue
        tags.setdefault(last, []).append("LAST_ROUND_DECIDES")
        tags.setdefault(most[0], []).append("MOST_WINS")
        tags.setdefault(first, []).append("FIRST_ROUND_DECIDES")
        if len(tags) != 3:
            continue
        opts = sorted([fav] + list(tags))
        expl = ["In each round, the toys the puppy did not grab are not its favourite."]
        for i, r in enumerate(rounds):
            out = [t for t in r["toys"] if t != r["grabbed"]]
            expl.append(f"  Round {i + 1}: grabbed {r['grabbed']}, so not {', '.join(out)}")
        expl.append(f"  Never left behind: {fav}")
        expl.append(f"So the favourite is {fav}.")
        scene = {"toys": toys, "rounds": rounds}
        return problem(cfg, "who", seed, scene, render_who(scene, seed),
                       "Here is what the puppy grabbed in each round. Which toy is its favourite?",
                       options=opts, answer_index=opts.index(fav), answer_value=fav, entry="choice",
                       distractors=[{"option": t, "misconceptions": tagsort("who", tags[t])} for t in opts if t != fav],
                       value_tags={}, explanation=expl,
                       hints=["The puppy grabs the toy it likes best in that round. What does that tell you about the others?",
                              "Cross out every toy that was left behind in some round.",
                              "The order of the rounds doesn't matter. Which toy is never left behind?"],
                       knobs={"toys": n, "rounds": nr})
    return None


# --------------------------------------------------------------------------
# Levels 2, 3, 5: counting
# --------------------------------------------------------------------------

def make_fewest(rng, cfg, seed):
    for _ in range(2000):
        n, k = rng.choice(cfg["toys"]), rng.choice(cfg["k"])
        if k == 2 and n > 10:
            continue                    # keeps the knockout in the explanation short
        truth = ceil_div(n - 1, k - 1)
        g = ceil_div(n, k)
        wrong = {"WINNER_NOT_CARRIED": g,
                 "FAVOURITE_RULED_OUT": ceil_div(n, k - 1),
                 "ROUNDS_DOWN": (n - 1) // (k - 1) if (n - 1) % (k - 1) else None}
        vt = value_tags("fewest", truth, wrong)
        if not vt or len(vt) < 2:
            continue
        sizes = [k] * truth
        rounds = chain_plan(sizes[:-1] + [n - most_toys(sizes[:-1]) + 1], n) if truth > 1 else [list(LETTERS[:n])]
        expl = [f"Each round leaves behind at most {toys(k - 1)}: all but the one the puppy grabs.",
                f"Every toy but the favourite must be left behind once: {n} − 1 = {n - 1} toys.",
                f"  {n - 1} ÷ {k - 1} = {(n - 1) / (k - 1):g}, so at least {truth} rounds"]
        expl += [f"{truth} rounds are enough: each round after the first takes the last winner and new toys."]
        expl += plan_lines(rounds)
        expl.append(f"So the fewest is {truth} rounds.")
        scene = {"n": n, "k": k}
        return problem(cfg, "fewest", seed, scene, render_count(scene, seed),
                       f"There are {n} toys, {LETTERS[0]} to {LETTERS[n - 1]}. Each round can have up to {k} toys, and a "
                       "round can include the winner of an earlier round. What is the fewest rounds that always finds "
                       "the favourite, whichever toy it is?",
                       options=[], answer_index=-1, answer_value=truth, entry="number", distractors=[], value_tags=vt,
                       explanation=expl,
                       hints=[f"In a round of {k} toys, how many toys can you be sure are not the favourite afterwards?",
                              "How many toys have to be ruled out in all? Not the favourite.",
                              "Try it: round 1 with new toys, then each round keeps the winner and adds new toys."],
                       knobs={"n": n, "k": k})
    return None


def make_most(rng, cfg, seed):
    for _ in range(2000):
        q, k = rng.choice(cfg["q"]), rng.choice(cfg["k"])
        truth = 1 + q * (k - 1)
        if truth > len(LETTERS):
            continue
        wrong = {"WINNER_NOT_CARRIED": q * k, "FAVOURITE_RULED_OUT": q * (k - 1),
                 "GROUPS_THEN_FINAL": (q - 1) * k if q - 1 <= k else None}
        vt = value_tags("most", truth, wrong)
        if not vt or len(vt) < 2:
            continue
        sizes = [k] * q
        expl = [f"Each round leaves behind at most {toys(k - 1)}: all but the one the puppy grabs.",
                f"  {q} rounds × {k - 1} = {q * (k - 1)} toys left behind at most",
                f"Every toy but the favourite must be left behind, so there can be at most {q * (k - 1)} + 1 = {truth} toys.",
                f"A knockout reaches it: each round after the first keeps the winner and adds {k - 1} new {toys(k - 1).split()[1]}."]
        expl += plan_lines(chain_plan(sizes, truth))
        expl.append(f"So the largest is {truth} toys.")
        scene = {"sizes": sizes}
        return problem(cfg, "most", seed, scene, render_rounds(scene, seed),
                       f"You have {q} rounds, and each round can have up to {k} toys. A round can include the winner of an "
                       "earlier round. What is the largest number of toys you can have and still always find the favourite?",
                       options=[], answer_index=-1, answer_value=truth, entry="number", distractors=[], value_tags=vt,
                       explanation=expl,
                       hints=[f"In a round of {k} toys, how many are left behind?",
                              "Add up what all the rounds leave behind. Which toy is never left behind?",
                              "Do the winners of different rounds have to meet? Where does each winner go next?"],
                       knobs={"q": q, "k": k})
    return None


def make_mixed(rng, cfg, seed):
    for _ in range(2000):
        q = rng.choice(cfg["q"])
        sizes = [rng.choice(cfg["sizes"]) for _ in range(q)]
        if len(set(sizes)) < 2:
            continue
        truth = most_toys(sizes)
        if truth > len(LETTERS):
            continue
        wrong = {"BIGGEST_ROUND_ONLY": 1 + q * (max(sizes) - 1), "WINNER_NOT_CARRIED": sum(sizes),
                 "FAVOURITE_RULED_OUT": truth - 1}
        vt = value_tags("mixed", truth, wrong)
        if not vt or len(vt) < 3:
            continue
        expl = ["Each round leaves behind all but the one toy the puppy grabs.",
                f"  {' + '.join(f'({s} − 1)' for s in sizes)} = {truth - 1} toys left behind at most",
                f"Every toy but the favourite must be left behind, so there can be at most {truth - 1} + 1 = {truth} toys.",
                "A knockout reaches it:"]
        expl += plan_lines(chain_plan(sizes, truth))
        expl.append(f"So the largest is {truth} toys.")
        scene = {"sizes": sizes}
        return problem(cfg, "mixed", seed, scene, render_rounds(scene, seed),
                       f"You have {q} rounds, and they are different sizes: the picture shows how many toys fit in each. "
                       "A round can include the winner of an earlier round. What is the largest number of toys you can "
                       "have and still always find the favourite?",
                       options=[], answer_index=-1, answer_value=truth, entry="number", distractors=[], value_tags=vt,
                       explanation=expl,
                       hints=["Look at one round at a time: how many toys does it leave behind?",
                              "Add those up. Which toy is never left behind?",
                              "Each round after the first can start with the toy grabbed in the round before."],
                       knobs={"sizes": sizes})
    return None


# --------------------------------------------------------------------------
# Level 4: which plan works?
# --------------------------------------------------------------------------

def valid_plan(rng, q, k, n):
    """A random plan that always works: q rounds of up to k toys, every winner but the last plays once more.
    The places left over (q(k-1) + 1 - n of them) are a gap or a toy shown again, which does no harm."""
    for _ in range(200):
        rs, pend = [], 0
        for i in range(q - 1):
            rs.append(rng.randint(0, min(pend, k - 1)) if i else 0)
            pend += 1 - rs[-1]
        rs.append(pend)
        if not 1 <= rs[-1] <= k:
            continue
        free = [(i, j) for i, r in enumerate(rs) for j in range(k - r)]
        spare = set(rng.sample(free, len(free) - n))
        rounds, waiting, nxt = [], [], 0
        for i, r in enumerate(rs):
            rng.shuffle(waiting)
            refs, waiting = sorted(waiting[:r]), waiting[r:]
            items = [f"W{j}" for j in refs]
            for j in range(k - r):
                if (i, j) in spare:
                    items.append(None)
                else:
                    items.append(LETTERS[nxt])
                    nxt += 1
            rounds.append(items)
            waiting.append(i + 1)
        return rounds
    return None


def pad(rng, rounds):
    """Fill each spare place (None) with a gap or a toy from an earlier round; drop the gaps."""
    for i, r in enumerate(rounds):
        for j, x in enumerate(r):
            if x is None:
                again = [y for rr in rounds[:i] for y in rr if y and not y.startswith("W") and y not in r]
                r[j] = rng.choice(again) if again and rng.random() < 0.5 else None
        rounds[i] = sorted((x for x in r if x), key=lambda x: (not x.startswith("W"), x))
    return rounds


def toys_in(rounds):
    return [x for r in rounds for x in r if x and not x.startswith("W")]


def flawed(rng, rounds, kind):
    if kind == "TOY_LEFT_OUT":
        slots = [(i, j) for i, r in enumerate(rounds) for j, x in enumerate(r) if x and not x.startswith("W")]
        i, j = rng.choice(slots)
        rounds[i][j] = None
    elif kind == "WINNER_DROPPED":
        slots = [(i, j) for i, r in enumerate(rounds) for j, x in enumerate(r) if x and x.startswith("W")]
        i, j = rng.choice(slots)
        rounds[i][j] = None
    else:   # CARRIES_TOY_NOT_WINNER: every W is a named toy from that round instead
        for i, r in enumerate(rounds):
            for j, x in enumerate(r):
                if x and x.startswith("W"):
                    src = [y for y in rounds[int(x[1:]) - 1] if y and not y.startswith("W") and y not in r]
                    if not src:
                        return None
                    r[j] = rng.choice(src)
    return rounds


def works(rounds, toys_):
    for t in toys_:
        won = set()
        for i, r in enumerate(rounds):
            if t in r or any(x.startswith("W") and int(x[1:]) in won for x in r):
                won.add(i + 1)
        if len(rounds) not in won:
            return False
    return True


def make_plan(rng, cfg, seed):
    kinds = ["WINNER_DROPPED", "TOY_LEFT_OUT", "CARRIES_TOY_NOT_WINNER"]
    for _ in range(5000):
        q, k = rng.choice(cfg["q"]), rng.choice(cfg["k"])
        n = q * (k - 1) + 1 - rng.choice([1, 2])
        toys = list(LETTERS[:n])
        good = valid_plan(rng, q, k, n)
        if not good:
            continue
        good = pad(rng, good)
        if not works(good, toys) or any(len(r) < 2 for r in good):
            continue
        bad = {}
        for kd in kinds:
            base = valid_plan(rng, q, k, n)
            p = base and flawed(rng, base, kd)
            if not p:
                break
            p = pad(rng, p)
            if works(p, toys) or any(len(set(r)) != len(r) or len(r) < 2 for r in p):
                break
            bad[kd] = p
        if len(bad) != 3:
            continue
        order = [("ok", good)] + list(bad.items())
        rng.shuffle(order)
        plans = [p for _, p in order]
        if len({json.dumps(p) for p in plans}) != 4:
            continue
        ans = next(i for i, (kd, _) in enumerate(order) if kd == "ok")
        opts = ["1", "2", "3", "4"]
        expl = []
        for i, (kd, p) in enumerate(order):
            if kd == "ok":
                expl.append(f"  Plan {i + 1}: every toy is shown, and every winner plays on to round {q}")
            elif kd == "TOY_LEFT_OUT":
                miss = [t for t in toys if t not in toys_in(p)]
                expl.append(f"  Plan {i + 1}: toy {miss[0]} is never shown")
            elif kd == "WINNER_DROPPED":
                used = {int(x[1:]) for r in p for x in r if x.startswith("W")}
                lost = [j for j in range(1, q) if j not in used]
                expl.append(f"  Plan {i + 1}: the winner of round {lost[0]} never plays again")
            else:
                expl.append(f"  Plan {i + 1}: it carries named toys, not winners, so the winners never meet")
        expl.insert(0, "Pretend each toy in turn is the favourite: it must be shown, and then win every round up to the last.")
        expl.append(f"So Plan {ans + 1} always finds the favourite.")
        scene = {"n": n, "k": k, "q": q, "plans": plans}
        return problem(cfg, "plan", seed, scene, render_plans(scene, seed),
                       f"There are {n} toys, {LETTERS[0]} to {LETTERS[n - 1]}, and {q} rounds of up to {k} toys. The favourite is "
                       f"the toy grabbed in round {q}. Which plan always finds the favourite, whichever toy it is?",
                       options=opts, answer_index=ans, answer_value=opts[ans], entry="choice",
                       distractors=[{"option": opts[i], "misconceptions": [kd]} for i, (kd, _) in enumerate(order) if kd != "ok"],
                       value_tags={}, explanation=expl,
                       hints=["Is every toy shown at least once in the plan?",
                              "W2 is the toy grabbed in round 2. Does every winner play again, until the last round?",
                              "Pretend one toy is the favourite. Follow it through the plan: does it get to round " + str(q) + "?"],
                       knobs={"q": q, "k": k}, prompt=PROMPT_W)
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


def problem(cfg, q, seed, scene, svg, question, prompt=None, **kw):
    pr = prompt or (PROMPT if q == "who" else PROMPT_W)
    return Problem(family="knockout_picks", level=cfg["level"], question_type=q, seed=seed, scene=scene, svg=svg,
                   prompt=pr, question=question, concepts=CONCEPTS[q], **kw)


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    rng = random.Random(seed)
    make = {"who": make_who, "fewest": make_fewest, "most": make_most, "plan": make_plan,
            "mixed": make_mixed}[cfg["question"]]
    p = make(rng, cfg, seed)
    if not p:
        raise RuntimeError(f"knockout_picks generation failed at level {level}")
    return p


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

FONT = 'font-family="Helvetica, Arial, sans-serif"'
BG, INK, SOFT = "#f4ecdf", "#1f2933", "#52606d"
TOY, TOY_EDGE, WIN, WIN_EDGE, SLOT = "#ffffff", "#7b8794", "#ffd166", "#b7791f", "#e4d8c4"
W = 420


def head(h, seed, kind, extra=""):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" {FONT} '
            f'class="picks" data-family="knockout_picks" data-kind="{kind}" data-seed="{seed}"{extra}>',
            f'<rect x="0" y="0" width="{W}" height="{h}" rx="10" fill="{BG}"/>']


def tile(x, y, s, label, cls, attrs, fill=TOY, edge=TOY_EDGE, sw=1.5, fs=15):
    return (f'<g class="{cls}" {attrs}><rect x="{x:.1f}" y="{y:.1f}" width="{s}" height="{s}" rx="7" fill="{fill}" '
            f'stroke="{edge}" stroke-width="{sw}"/><text x="{x + s / 2:.1f}" y="{y + s / 2 + fs * .36:.1f}" font-size="{fs}" '
            f'font-weight="bold" text-anchor="middle" fill="{INK}">{label}</text></g>')


def render_who(sc, seed):
    rows = sc["rounds"]
    h = 40 + 46 * len(rows) + 30
    out = head(h, seed, "who", f' data-toys="{"".join(sc["toys"])}"')
    out.append(f'<text x="{W / 2}" y="26" font-size="14" font-weight="bold" text-anchor="middle" fill="{INK}">'
               f'Toys: {" ".join(sc["toys"])}</text>')
    for i, r in enumerate(rows):
        y = 44 + 46 * i
        out.append(f'<g class="round" data-round="{i + 1}"><text x="40" y="{y + 24}" font-size="13" fill="{SOFT}">Round {i + 1}</text>')
        for j, t in enumerate(r["toys"]):
            g = t == r["grabbed"]
            out.append(tile(120 + 50 * j, y, 36, t, "toy", f'data-toy="{t}" data-grabbed="{int(g)}"',
                            WIN if g else TOY, WIN_EDGE if g else TOY_EDGE, 3 if g else 1.5))
        out.append(f'<text x="290" y="{y + 24}" font-size="13" fill="{INK}">grabbed {r["grabbed"]}</text></g>')
    out.append(f'<text x="{W / 2}" y="{h - 12}" font-size="12" text-anchor="middle" fill="{SOFT}">'
               'Gold: the toy the puppy grabbed in that round</text>')
    out.append("</svg>")
    return "".join(out)


def render_count(sc, seed):
    n, k = sc["n"], sc["k"]
    per = 10
    rows = ceil_div(n, per)
    h = 30 + 40 * rows + 110
    out = head(h, seed, "fewest", f' data-n="{n}" data-k="{k}"')
    out.append(f'<text x="{W / 2}" y="22" font-size="14" font-weight="bold" text-anchor="middle" fill="{INK}">{n} toys</text>')
    for i in range(n):
        r, c = divmod(i, per)
        cnt = min(per, n - r * per)
        x0 = W / 2 - (cnt * 38 - 6) / 2
        out.append(tile(x0 + 38 * c, 32 + 40 * r, 32, LETTERS[i], "toy", f'data-toy="{LETTERS[i]}"', fs=14))
    y = 32 + 40 * rows + 20
    out.append(f'<text x="{W / 2}" y="{y}" font-size="13" text-anchor="middle" fill="{INK}">One round: up to {k} toys</text>')
    out.append(basket(W / 2, y + 12, k, None))
    out.append("</svg>")
    return "".join(out)


def basket(cx, y, k, rnd):
    w = k * 38 + 10
    x = cx - w / 2
    attrs = f'data-size="{k}"' + (f' data-round="{rnd}"' if rnd else "")
    s = [f'<g class="basket" {attrs}><rect x="{x:.1f}" y="{y}" width="{w}" height="44" rx="10" fill="#c8a165" stroke="#7a5a2b" stroke-width="2"/>']
    for j in range(k):
        s.append(f'<rect x="{x + 8 + 38 * j:.1f}" y="{y + 7}" width="32" height="30" rx="6" fill="{SLOT}" stroke="#7a5a2b" stroke-dasharray="3 2"/>')
    s.append("</g>")
    return "".join(s)


def render_rounds(sc, seed):
    sizes = sc["sizes"]
    h = 20 + 54 * len(sizes) + 20
    out = head(h, seed, "rounds", f' data-q="{len(sizes)}"')
    for i, k in enumerate(sizes):
        y = 20 + 54 * i
        out.append(f'<text x="30" y="{y + 27}" font-size="13" fill="{SOFT}">Round {i + 1}</text>')
        out.append(basket(110 + (k * 38 + 10) / 2, y, k, i + 1))
        out.append(f'<text x="{130 + k * 38}" y="{y + 27}" font-size="13" fill="{INK}">up to {k} toys</text>')
    out.append("</svg>")
    return "".join(out)


def render_plans(sc, seed):
    q, k, plans = sc["q"], sc["k"], sc["plans"]
    ph = 30 + 36 * q
    h = 40 + 2 * (ph + 10)
    out = head(h, seed, "plan", f' data-n="{sc["n"]}" data-k="{k}" data-q="{q}"')
    out.append(f'<text x="{W / 2}" y="24" font-size="13" text-anchor="middle" fill="{INK}">'
               f'Toys {LETTERS[0]} to {LETTERS[sc["n"] - 1]} · W2 = the toy grabbed in round 2</text>')
    for p, rounds in enumerate(plans):
        px, py = 8 + (p % 2) * 206, 36 + (p // 2) * (ph + 10)
        out.append(f'<g class="plan" data-plan="{p + 1}"><rect x="{px}" y="{py}" width="198" height="{ph}" rx="10" '
                   f'fill="#fffaf1" stroke="#c9b79c"/><text x="{px + 99}" y="{py + 20}" font-size="14" font-weight="bold" '
                   f'text-anchor="middle" fill="{INK}">Plan {p + 1}</text>')
        for i, r in enumerate(rounds):
            y = py + 28 + 36 * i
            out.append(f'<g class="round" data-round="{i + 1}"><text x="{px + 10}" y="{y + 20}" font-size="12" fill="{SOFT}">R{i + 1}</text>')
            for j, x in enumerate(r):
                w = x.startswith("W")
                out.append(tile(px + 38 + 38 * j, y, 30, x, "slot", f'data-item="{x}"', WIN if w else TOY,
                                WIN_EDGE if w else TOY_EDGE, 1.5, 13 if w else 14))
            out.append("</g>")
        out.append("</g>")
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    import sys
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print(json.dumps({k: v for k, v in asdict(generate(lvl, sd)).items() if k not in ("svg",)}, indent=2, ensure_ascii=False))

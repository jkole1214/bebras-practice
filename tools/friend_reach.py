"""
Problem family: friend_reach (Pass It On). Folder: pass-it-on.

Concept targets: GRAPH_NEIGHBORHOOD, GRAPH_MODEL.
Source task: Popularity (Junior C, Senior B), 2015.

Scenario (original): a group of friends shares news in exactly two steps. Whoever has news
tells all of their friends, and each of those friends tells all of their own friends. Nobody
passes it on a third time. So a person's news reaches everyone within two steps of them, and
the person with the most friends is not always the one whose news reaches the most people.

This follows the idea of a two-step reach task (the source uses photos on friends' pages);
the story, wording, names and pictures are our own.

One scene model (people, friendships, the sender) drives both the SVG picture and the solver.
The picture carries each person (data-name) and each friendship (data-a, data-b); the
independent checker rebuilds the graph from the SVG and solves it again with breadth-first search.

Question types:
  reach     how many people hear one person's news? (choice at level 1, typed at level 3)
  who       whose news reaches the most people? (choice; levels 2 and 4)
  befriend  which one new friendship makes one person's news reach everyone? (choice; level 5)

Misconceptions:
  ONE_STEP_ONLY          counts only direct friends
  ONLY_SECOND_STEP       counts only the people reached in step two
  COUNTS_SENDER          counts the person who had the news
  PASSES_IT_ON_TOO_FAR   lets the news travel a third step
  COUNTS_REPEATS         counts someone again each time they hear it
  MOST_FRIENDS_WINS      picks the person with the most friends
  JOINS_A_MISSED_PERSON  befriends someone the news misses, which fixes only that one person
"""

import json
import math
import random
from dataclasses import dataclass, field, asdict

NAMES = ["Ava", "Ben", "Cal", "Dee", "Eli", "Fay", "Gus", "Hal", "Ivy", "Jon", "Kim", "Leo",
         "Mia", "Ned", "Ola", "Pip", "Rex", "Sam", "Tia", "Uma", "Vic", "Wes", "Zoe"]


# --------------------------------------------------------------------------
# Measures (adjacency: name -> set of friends)
# --------------------------------------------------------------------------

def within(adj, x, steps):
    seen, front = {x}, {x}
    for _ in range(steps):
        front = {f for p in front for f in adj[p]} - seen
        seen |= front
    return seen - {x}


def reach(adj, x):
    return len(within(adj, x, 2))


def friends(adj, x):
    return len(adj[x])


def second_step(adj, x):
    return reach(adj, x) - len(adj[x])


def three_steps(adj, x):
    return len(within(adj, x, 3))


def repeats(adj, x):
    """Every telling counted, as if each friend's friends were all new people."""
    return len(adj[x]) + sum(len(adj[f] - {x}) for f in adj[x])


# value a student with each habit would give for "how many hear x's news?"
REACH_MISTAKES = {
    "ONE_STEP_ONLY": friends,
    "ONLY_SECOND_STEP": second_step,
    "COUNTS_SENDER": lambda adj, x: reach(adj, x) + 1,
    "PASSES_IT_ON_TOO_FAR": three_steps,
    "COUNTS_REPEATS": repeats,
}

# the score a student with each habit would maximise for "whose news reaches the most?"
WHO_MISTAKES = {
    "MOST_FRIENDS_WINS": friends,
    "PASSES_IT_ON_TOO_FAR": three_steps,
    "COUNTS_REPEATS": repeats,
    "ONLY_SECOND_STEP": second_step,
}

MISCONCEPTIONS = {
    "ONE_STEP_ONLY": {"concept": "GRAPH_NEIGHBORHOOD",
        "description": "Counts only the sender's own friends and forgets that each friend passes the news on.",
        "remediation": "Ask what each friend does with the news after hearing it."},
    "ONLY_SECOND_STEP": {"concept": "GRAPH_NEIGHBORHOOD",
        "description": "Counts only the people reached in the second step and leaves out the friends who heard it first.",
        "remediation": "Have the student list step one and step two separately, then add both lists."},
    "COUNTS_SENDER": {"concept": "GRAPH_NEIGHBORHOOD",
        "description": "Counts the person who had the news as one of the people who hear it.",
        "remediation": "Reread the question: does the sender hear their own news from someone?"},
    "PASSES_IT_ON_TOO_FAR": {"concept": "GRAPH_NEIGHBORHOOD",
        "description": "Lets the news travel a third step (or further), past the friends of friends.",
        "remediation": "Reread the rule: nobody passes the news on a third time. Mark where step two ends."},
    "COUNTS_REPEATS": {"concept": "GRAPH_NEIGHBORHOOD",
        "description": "Adds up every friend's friends without noticing that some people hear the news twice, or are the sender.",
        "remediation": "Have the student tick each person once, the first time they hear it."},
    "MOST_FRIENDS_WINS": {"concept": "GRAPH_NEIGHBORHOOD",
        "description": "Assumes the person with the most friends spreads news the furthest.",
        "remediation": "Count two steps out from the most-friended person and from another person, and compare."},
    "JOINS_A_MISSED_PERSON": {"concept": "GRAPH_NEIGHBORHOOD",
        "description": "Makes friends with a person the news misses, which reaches that one person but not the others it misses.",
        "remediation": "Ask: a new friend tells their own friends too. Whose friends cover everyone who is missed?"},
}

LADDER = [
    {"level": 1, "question": "reach", "people": 6, "gap": 2, "entry": "choice",
     "note": "How many people hear one person's news? Six friends (multiple choice)."},
    {"level": 2, "question": "who", "people": 8, "gap": 2,
     "note": "Whose news reaches the most people? The one with the most friends is a trap."},
    {"level": 3, "question": "reach", "people": 8, "gap": 3, "entry": "number",
     "note": "Count who hears one person's news in a bigger group (type the number)."},
    {"level": 4, "question": "who", "people": 9, "gap": 3,
     "note": "Whose news reaches the most people? Nine friends, more lines to follow."},
    {"level": 5, "question": "befriend", "people": 8, "gap": 3,
     "note": "Which one new friend makes a person's news reach everyone?"},
]

PROMPT = ("News spreads through this group of friends in two steps. Whoever has news tells all of their "
          "friends. Then each of those friends tells all of their own friends. Nobody passes it on a third "
          "time. A line joins two friends.")


# --------------------------------------------------------------------------
# Graphs on a circle
# --------------------------------------------------------------------------

CX, CY, R, NODE = 200, 185, 145, 26


def positions(n, turn):
    return [(CX + R * math.cos(turn + 2 * math.pi * i / n), CY + R * math.sin(turn + 2 * math.pi * i / n))
            for i in range(n)]


def crosses(p, q, r, s):
    def o(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return o(p, q, r) * o(p, q, s) < 0 and o(r, s, p) * o(r, s, q) < 0


def make_graph(rng, n, gap):
    """People on a circle; friendships only between near neighbours on the circle, so the picture stays readable."""
    for _ in range(500):
        edges = set()
        for i in range(n):
            for d in range(1, gap + 1):
                j = (i + d) % n
                if d >= n - d and j < i:
                    continue
                if rng.random() < (0.55 if d == 1 else 0.38 if d == 2 else 0.22):
                    edges.add((min(i, j), max(i, j)))
        deg = [sum(1 for e in edges if i in e) for i in range(n)]
        if min(deg) < 1 or max(deg) > 5:
            continue
        adj = {i: {b if a == i else a for a, b in edges if i in (a, b)} for i in range(n)}
        if len(within(adj, 0, n)) != n - 1:
            continue
        pos = positions(n, 0)
        el = sorted(edges)
        cross = sum(1 for x in range(len(el)) for y in range(x + 1, len(el))
                    if not set(el[x]) & set(el[y]) and crosses(pos[el[x][0]], pos[el[x][1]], pos[el[y][0]], pos[el[y][1]]))
        if cross > n // 2 + 1:
            continue
        return el
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


def people(k):
    return f"{k} {'person' if k == 1 else 'people'}"


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    rng = random.Random(seed)
    make = {"reach": make_reach, "who": make_who, "befriend": make_befriend}[cfg["question"]]
    for _ in range(400):
        n = cfg["people"]
        el = make_graph(rng, n, cfg["gap"])
        if not el:
            continue
        names = sorted(rng.sample(NAMES, n))
        rng.shuffle(names)
        ties = sorted(tuple(sorted((names[a], names[b]))) for a, b in el)
        adj = {x: set() for x in names}
        for a, b in ties:
            adj[a].add(b)
            adj[b].add(a)
        p = make(rng, cfg, seed, names, ties, adj)
        if p:
            return p
    raise RuntimeError(f"friend_reach generation failed at level {level}")


def spread_lines(adj, x):
    """Step one, step two, and who is left out."""
    s1 = sorted(adj[x])
    s2 = sorted(within(adj, x, 2) - set(s1))
    out = [f"Step 1: {x} tells every friend: {join(s1)} ({people(len(s1))})."]
    if s2:
        out.append(f"Step 2: {join(s1)} tell their own friends. New people: {join(s2)} ({people(len(s2))}). "
                   f"Anyone who already heard, and {x}, is not counted again.")
    else:
        out.append(f"Step 2: {join(s1)} tell their own friends, but everyone they know has already heard.")
    far = sorted(set(adj) - within(adj, x, 2) - {x})
    if far:
        out.append(f"Nobody passes it on a third time, so {join(far)} {'does' if len(far) == 1 else 'do'} not hear it.")
    return out


def picture(names, ties, sender, seed):
    return render_svg(names, ties, sender, seed)


def make_reach(rng, cfg, seed, names, ties, adj):
    order = names[:]
    rng.shuffle(order)
    for x in order:
        truth = reach(adj, x)
        if three_steps(adj, x) <= truth or friends(adj, x) < 2:
            continue                          # someone must be out of reach, and step one must matter
        wrong = {}
        for tag, f in REACH_MISTAKES.items():
            v = f(adj, x)
            if v != truth:
                wrong.setdefault(v, []).append(tag)
        if repeats(adj, x) == truth:
            continue                          # nobody hears it twice: the main counting trap would be right
        if cfg["entry"] == "choice":
            under = [v for v in wrong if v < truth]
            over = [v for v in wrong if v > truth]
            if not under or not over or len(wrong) < 3:
                continue
            pick = [rng.choice(sorted(under)), rng.choice(sorted(over))]
            pick.append(rng.choice(sorted(v for v in wrong if v not in pick)))
            opts = sorted(pick + [truth])
            distractors = [{"option": v, "misconceptions": wrong[v]} for v in opts if v != truth]
            entry, idx, vt = "choice", opts.index(truth), {}
        else:
            opts, distractors, entry, idx = [], [], "number", -1
            vt = {str(v): t for v, t in sorted(wrong.items())}
        expl = spread_lines(adj, x) + [f"So {people(truth)} hear {x}'s news."]
        return Problem(
            family="friend_reach", level=cfg["level"], question_type="reach", seed=seed,
            scene={"people": names, "ties": [list(t) for t in ties], "sender": x},
            svg=picture(names, ties, x, seed), prompt=PROMPT,
            question=f"{x} has news. How many people hear it? Do not count {x}.",
            options=opts, answer_index=idx, answer_value=truth, entry=entry,
            distractors=distractors, value_tags=vt, concepts=["GRAPH_NEIGHBORHOOD", "GRAPH_MODEL"],
            explanation=expl,
            hints=[f"Put a finger on {x}. Who is joined to {x} by a line? They hear it first.",
                   "Now each of those friends tells their own friends. Who is new?",
                   f"Count each person once. Leave out {x}, and anyone three steps away."],
            knobs={"people": len(names), "ties": len(ties)},
        )
    return None


def make_who(rng, cfg, seed, names, ties, adj):
    score = {x: reach(adj, x) for x in names}
    best = max(score.values())
    top = [x for x in names if score[x] == best]
    if len(top) != 1:
        return None
    ans = top[0]
    tagged = {}
    for tag, f in WHO_MISTAKES.items():
        s = {x: f(adj, x) for x in names}
        mx = [x for x in names if s[x] == max(s.values())]
        if ans in mx:
            if tag in ("MOST_FRIENDS_WINS", "COUNTS_REPEATS"):
                return None                   # the main traps must not land on the answer
            continue
        for x in mx:
            tagged.setdefault(x, []).append(tag)
    traps = [x for x, t in tagged.items() if "MOST_FRIENDS_WINS" in t]
    if not traps or len(tagged) < 2:
        return None
    pick = [rng.choice(sorted(traps))]
    rest = sorted(x for x in tagged if x not in pick)
    rng.shuffle(rest)
    pick += rest[:2]
    opts = sorted(pick + [ans])
    rows = [f"  {x:<4} {friends(adj, x)} friend{'' if friends(adj, x) == 1 else 's'}, news reaches {score[x]}" for x in sorted(names)]
    trap = pick[0]
    expl = ["For each person, count the friends (step 1) and the new friends of friends (step 2):"] + rows
    expl.append(f"{trap} has the most friends ({friends(adj, trap)}), but {trap}'s news reaches only "
                f"{people(score[trap])}.")
    expl += spread_lines(adj, ans)
    expl.append(f"So {ans}'s news reaches the most people: {score[ans]}.")
    return Problem(
        family="friend_reach", level=cfg["level"], question_type="who", seed=seed,
        scene={"people": names, "ties": [list(t) for t in ties], "sender": ""},
        svg=picture(names, ties, "", seed), prompt=PROMPT,
        question="Whose news reaches the most people?",
        options=opts, answer_index=opts.index(ans), answer_value=ans, entry="choice",
        distractors=[{"option": x, "misconceptions": sorted(tagged[x], key=lambda t: (t != "MOST_FRIENDS_WINS", t))}
                     for x in opts if x != ans],
        value_tags={}, concepts=["GRAPH_NEIGHBORHOOD", "GRAPH_MODEL"], explanation=expl,
        hints=["Having the most friends is not the same as reaching the most people.",
               "For one person, list the friends, then the friends of friends who are new.",
               "Do that for each choice and compare. Count each person once, and stop after two steps."],
        knobs={"people": len(names), "ties": len(ties)},
    )


def make_befriend(rng, cfg, seed, names, ties, adj):
    order = names[:]
    rng.shuffle(order)
    n = len(names)
    for x in order:
        missed = sorted(set(names) - within(adj, x, 2) - {x})
        if len(missed) < 2:
            continue
        cands = sorted(set(names) - adj[x] - {x})

        def with_friend(p):
            a2 = {k: set(v) for k, v in adj.items()}
            a2[x].add(p)
            a2[p].add(x)
            return a2
        works = [p for p in cands if reach(with_friend(p), x) == n - 1]
        if len(works) != 1 or works[0] in missed:
            continue
        ans = works[0]
        most = max(friends(adj, p) for p in cands)
        tagged = {}
        for p in cands:
            if p == ans:
                continue
            if friends(adj, p) == most:
                tagged.setdefault(p, []).append("MOST_FRIENDS_WINS")
            if p in missed:
                tagged.setdefault(p, []).append("JOINS_A_MISSED_PERSON")
            if three_steps(with_friend(p), x) == n - 1:
                tagged.setdefault(p, []).append("PASSES_IT_ON_TOO_FAR")
        if friends(adj, ans) == most:
            continue                          # befriending the most-friended person must not be right
        joins = [p for p, t in tagged.items() if "JOINS_A_MISSED_PERSON" in t]
        if not joins or len(tagged) < 2:
            continue
        pick = [rng.choice(sorted(joins))]
        rest = sorted(p for p in tagged if p not in pick)
        rng.shuffle(rest)
        pick += rest[:2]
        opts = sorted(pick + [ans])
        expl = spread_lines(adj, x)
        expl.append(f"A new friend hears the news in step 1 and tells all of their own friends in step 2. "
                    f"So {x} needs a friend who is friends with {join(missed)}.")
        expl.append(f"{ans} is friends with {join(sorted(adj[ans]))}, which covers everyone who was missed.")
        for p in opts:
            if p != ans:
                still = sorted(set(names) - within(with_friend(p), x, 2) - {x})
                expl.append(f"With {p} as a new friend, the news would still miss {join(still)}.")
        expl.append(f"So {x} should make friends with {ans}.")
        return Problem(
            family="friend_reach", level=cfg["level"], question_type="befriend", seed=seed,
            scene={"people": names, "ties": [list(t) for t in ties], "sender": x},
            svg=picture(names, ties, x, seed), prompt=PROMPT,
            question=f"{x} wants news to reach everyone. Which one new friend should {x} make?",
            options=opts, answer_index=opts.index(ans), answer_value=ans, entry="choice",
            distractors=[{"option": p, "misconceptions": sorted(tagged[p], key=lambda t: (t != "JOINS_A_MISSED_PERSON", t))}
                         for p in opts if p != ans],
            value_tags={}, concepts=["GRAPH_NEIGHBORHOOD", "GRAPH_MODEL"], explanation=expl,
            hints=[f"First find who {x}'s news misses right now.",
                   "A new friend hears it in step 1, then tells all of their own friends in step 2.",
                   "Look for one person who is friends with everyone that is missed."],
            knobs={"people": n, "ties": len(ties), "missed": len(missed)},
        )
    return None


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render_svg(names, ties, sender, seed):
    n = len(names)
    pos = dict(zip(names, positions(n, -math.pi / 2)))
    W, H = 400, 370
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'font-family="Helvetica, Arial, sans-serif" class="friends" data-family="friend_reach" data-seed="{seed}">',
           f'<rect x="0" y="0" width="{W}" height="{H}" rx="10" fill="#e7edf2"/>']
    for a, b in ties:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        out.append(f'<line class="tie" data-a="{a}" data-b="{b}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                   f'stroke="#5a6880" stroke-width="3" stroke-linecap="round"/>')
    for x in names:
        cx, cy = pos[x]
        s = x == sender
        out.append(f'<g class="person{" sender" if s else ""}" data-name="{x}" aria-label="{x}{", has the news" if s else ""}">'
                   f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{NODE}" fill="{"#f2c14e" if s else "#ffffff"}" '
                   f'stroke="#33414e" stroke-width="{3 if s else 2}"/>'
                   f'<text x="{cx:.1f}" y="{cy + 5.5:.1f}" font-size="16" font-weight="bold" text-anchor="middle" '
                   f'fill="#1f2933">{x}</text></g>')
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    import sys
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print(json.dumps({k: v for k, v in asdict(generate(lvl, sd)).items() if k != "svg"}, indent=2, ensure_ascii=False))

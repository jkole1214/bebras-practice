"""
Problem family: circle_steps (Round and Round). Folder: round-and-round.

Concept targets: SEQUENCES_CYCLIC, MODULAR_ARITHMETIC, CYCLE_DETECTION.
Source tasks: Drawing Stars, Hangar Carousel, Cipher 8 and Tortoise and Hare (several years of
practice challenges). None of them had a family; this one covers the "going round in circles" group.

Scenario (original, a fun fair): counting squares round a ring-shaped game board; string-art stars
on a round board of pins; a Ferris wheel that turns one car per press; two go-karts on a track
that leads into a loop. The ideas of the source tasks are kept (stepping k places round n spots
wraps past n back to 1; joining every k-th pin makes loops of n / gcd(n, k) pins; the distance
round a circle is the shorter way, from where you are now; a slow and a fast runner on a loop
meet inside it), with our own stories, wording, question types and pictures.

One scene model drives both the SVG picture and the solver. Every spot, pin, car and square is in
the picture with its number and position (data-spot, data-pin, data-car, data-cell), lines carry
their ends (data-from, data-to) and the track squares carry where they lead (data-next). The
independent checker rebuilds each problem from the picture and solves it again by stepping round
it one square or pin at a time, ordering the spots by their angle in the drawing.

Question types:
  step    a counter moves k squares clockwise round a board of n: which square? (typed)
  label   a finished string-art star: each pin is joined to the pin k places round. What is k? (typed)
  visits  keep joining every k-th pin, starting at pin 1: how many pins does the loop touch? (typed)
  turns   a Ferris wheel lets riders off at the platform in a set order: fewest presses? (typed)
  meet    a slow and a fast kart on a track that leads into a loop: where do they first meet? (typed)

Misconceptions:
  NO_WRAP              treats the circle as a straight line, never going past n back to 1
  COUNTS_START_SQUARE  counts the square you start on as the first step
  WRAP_NOT_A_STEP      doesn't count the step from n back to 1
  COUNTS_SKIPPED_PINS  counts the pins skipped over instead of the step
  COUNTS_BOTH_ENDS     counts the pins at both ends of a line as well as the step
  LONG_WAY_ROUND       counts the step the long way round
  EVERY_PIN            assumes the loop always reaches every pin
  ONE_LAP              stops when the loop first goes past pin 1, not when it lands on it
  COUNTS_START_TWICE   counts pin 1 again when the loop gets back to it
  ONE_WAY_ONLY         always turns the wheel the same way
  FROM_START_EACH_TIME measures each car from where the wheel started, not from where it is now
  LOOP_ENTRANCE        thinks the karts meet where the loop begins
  BACK_TO_START        thinks the loop leads back to the start of the track
"""

import json
import math
import random
from dataclasses import dataclass, field, asdict

CONCEPTS = {"step": ["SEQUENCES_CYCLIC", "MODULAR_ARITHMETIC"], "label": ["MODULAR_ARITHMETIC", "SEQUENCES_CYCLIC"],
            "visits": ["MODULAR_ARITHMETIC"], "turns": ["MODULAR_ARITHMETIC", "SEQUENCES_CYCLIC"],
            "meet": ["CYCLE_DETECTION", "SIMULATION", "MODULAR_ARITHMETIC"]}

MISCONCEPTIONS = {
    "NO_WRAP": {"concept": "SEQUENCES_CYCLIC",
        "description": "Treats a circle of numbered spots as a straight line, so a count never goes past the last number back to 1.",
        "remediation": "Point to the last number on the circle. What comes after it? Keep counting from there."},
    "COUNTS_START_SQUARE": {"concept": "SEQUENCES_CYCLIC",
        "description": "Counts the square the counter starts on as the first step, so it lands one square short.",
        "remediation": "The first step takes the counter off its square. Count the squares it lands on, not the one it leaves."},
    "WRAP_NOT_A_STEP": {"concept": "MODULAR_ARITHMETIC",
        "description": "Doesn't count the step from the last number back to 1, so it lands one square too far.",
        "remediation": "Going from the last square to square 1 is a step like any other. Count it."},
    "COUNTS_SKIPPED_PINS": {"concept": "MODULAR_ARITHMETIC",
        "description": "Counts the pins a line skips over instead of how many places on it goes, one too few.",
        "remediation": "Count the steps from the pin where the line starts to the pin where it ends, landing on each pin in between."},
    "COUNTS_BOTH_ENDS": {"concept": "MODULAR_ARITHMETIC",
        "description": "Counts the pins from one end of a line to the other, both ends included, one too many.",
        "remediation": "Put a finger on the start pin and count each move to the next pin. The start pin is not a move."},
    "LONG_WAY_ROUND": {"concept": "MODULAR_ARITHMETIC",
        "description": "Counts from one end of a line to the other the long way round the circle.",
        "remediation": "A line joins two pins. Count the steps between them the short way round."},
    "EVERY_PIN": {"concept": "MODULAR_ARITHMETIC",
        "description": "Assumes that joining every k-th pin always reaches every pin, which is only true when k and the number of pins share no factor.",
        "remediation": "Follow the lines and write down each pin you land on. Do you come back to 1 before you have been everywhere?"},
    "ONE_LAP": {"concept": "MODULAR_ARITHMETIC",
        "description": "Stops when the loop first goes past pin 1, rather than when it lands on pin 1 again.",
        "remediation": "The pencil only stops when it lands on pin 1. Going past it doesn't count; keep going round."},
    "COUNTS_START_TWICE": {"concept": "MODULAR_ARITHMETIC",
        "description": "Counts pin 1 again when the loop gets back to it, so the count is one too many.",
        "remediation": "Pin 1 is where the loop begins and ends. Count it once."},
    "ONE_WAY_ONLY": {"concept": "MODULAR_ARITHMETIC",
        "description": "Always turns the circle the same way, even when the other way is shorter.",
        "remediation": "For each move, count both ways round and take the shorter one."},
    "FROM_START_EACH_TIME": {"concept": "MODULAR_ARITHMETIC",
        "description": "Measures every move from where the circle started, not from where it is now.",
        "remediation": "After each move the circle stays where it stopped. Measure the next move from there."},
    "LOOP_ENTRANCE": {"concept": "CYCLE_DETECTION",
        "description": "Thinks a slow and a fast runner meet where the loop begins.",
        "remediation": "Move both runners one second at a time and write down where each one is. Stop when they share a square."},
    "BACK_TO_START": {"concept": "CYCLE_DETECTION",
        "description": "Thinks the loop leads back to the start of the track, so the runners meet where they began.",
        "remediation": "Follow the arrows from the last square of the loop. Where does it lead: back to the start, or round the loop again?"},
}

LADDER = [
    {"level": 1, "question": "step", "n": [8, 9, 10, 11, 12], "entry": "number",
     "note": "Count round the board one square at a time. After the last square comes square 1 again."},
    {"level": 2, "question": "label", "n": [7, 8, 9, 10, 11, 12], "entry": "number",
     "note": "Follow one line from pin 1 and count the steps round to its other end, the short way."},
    {"level": 3, "question": "visits", "n": [8, 9, 10, 12, 14, 15], "entry": "number",
     "note": "Keep jumping k pins until you land on pin 1 again. The loop can come back before it has been everywhere."},
    {"level": 4, "question": "turns", "n": [6, 7, 8, 9, 10], "stops": 4, "entry": "number",
     "note": "Each move starts from where the wheel is now. Count both ways round and take the shorter one."},
    {"level": 5, "question": "meet", "lead": [1, 2, 3, 4, 5, 6], "loop": [4, 5, 6, 7, 8, 9], "entry": "number",
     "note": "Move both karts one second at a time and write down their squares until they share one."},
]

ORDER = {
    "step": ["NO_WRAP", "COUNTS_START_SQUARE", "WRAP_NOT_A_STEP"],
    "label": ["COUNTS_SKIPPED_PINS", "LONG_WAY_ROUND", "COUNTS_BOTH_ENDS"],
    "visits": ["EVERY_PIN", "ONE_LAP", "COUNTS_START_TWICE"],
    "turns": ["FROM_START_EACH_TIME", "ONE_WAY_ONLY", "NO_WRAP"],
    "meet": ["LOOP_ENTRANCE", "BACK_TO_START"],
}


def tagsort(q, tags):
    return sorted(set(tags), key=lambda t: (ORDER[q].index(t), t))


def ceil_div(a, b):
    return -(-a // b)


def wrap(x, n):
    """x on a circle numbered 1..n."""
    return (x - 1) % n + 1


def around(a, b, n):
    """Steps clockwise (up the numbers) from a to b."""
    return (b - a) % n


def short(a, b, n):
    return min(around(a, b, n), around(b, a, n))


def value_tags(q, truth, wrong):
    vt = {}
    for tag, v in wrong.items():
        if v is None:
            continue
        if v == truth or v < 1:
            return None
        vt.setdefault(v, []).append(tag)
    return {str(v): tagsort(q, t) for v, t in sorted(vt.items())}


def sq(m, word="square"):
    return f"{m} {word}" + ("" if m == 1 else "s")


# --------------------------------------------------------------------------
# Level 1: where does the counter land?
# --------------------------------------------------------------------------

def make_step(rng, cfg, seed):
    for _ in range(2000):
        n = rng.choice(cfg["n"])
        truth = rng.randint(1, n - 2)               # chosen first so the answers spread evenly
        s = rng.randint(truth + 1, n)
        k = n - s + truth                           # always goes past square n
        if k < 2 or wrap(s + k, n) != truth:
            continue
        wrong = {"NO_WRAP": s + k, "COUNTS_START_SQUARE": wrap(truth - 1, n), "WRAP_NOT_A_STEP": wrap(truth + 1, n)}
        vt = value_tags("step", truth, wrong)
        if not vt or len(vt) < 3:
            continue
        expl = [f"Count {sq(k)} clockwise, starting on square {s} (that square is not a step).",
                f"  {s} + {k} = {s + k}, but the board only goes up to {n}",
                f"  after square {n} comes square 1: {s + k} − {n} = {truth}",
                f"So the counter lands on square {truth}."]
        scene = {"n": n, "start": s, "move": k}
        return problem(cfg, "step", seed, scene, render_step(scene, seed),
                       "A game board is a ring of squares numbered 1 to " + str(n) + ". After square " + str(n) +
                       " comes square 1 again.",
                       f"Your counter is on square {s}. You move it {k} squares clockwise. Which square does it land on?",
                       truth, vt, expl,
                       ["Put your finger on the counter. The first step takes it to the next square.",
                        f"What comes after square {n}?",
                        f"Add {k} to {s}. If that is past {n}, how far past is it?"],
                       {"n": n, "k": k})
    return None


# --------------------------------------------------------------------------
# Levels 2 and 3: string-art stars
# --------------------------------------------------------------------------

STAR_PROMPT = ("String art: pins stand in a circle, numbered 1 to {n} clockwise. A string goes from each pin "
               "to a pin a set number of places further round.")


def make_label(rng, cfg, seed):
    for _ in range(2000):
        n = rng.choice(cfg["n"])
        k = rng.randint(2, (n - 1) // 2)
        wrong = {"COUNTS_SKIPPED_PINS": k - 1, "LONG_WAY_ROUND": n - k, "COUNTS_BOTH_ENDS": k + 1}
        vt = value_tags("label", k, wrong)
        if not vt or len(vt) < 2:
            continue
        g = math.gcd(n, k)
        expl = ["Pin 1 has two strings. Follow either one and count the steps round, the short way.",
                f"  pin 1 → pin {1 + k}: {sq(k, 'step')} clockwise",
                f"  pin 1 → pin {n + 1 - k}: {sq(k, 'step')} the other way",
                f"  the long way round would be {n} − {k} = {n - k} steps"]
        if g > 1:
            expl.append(f"The strings make {g} separate loops, but every string still goes {sq(k, 'place')}.")
        expl.append(f"So each string goes {k} places round.")
        scene = {"n": n, "k": k, "lines": [[i, wrap(i + k, n)] for i in range(1, n + 1)]}
        return problem(cfg, "label", seed, scene, render_star(scene, seed, "label"),
                       STAR_PROMPT.format(n=n),
                       "Every string in this picture goes the same number of places round, counting the short way. "
                       "How many places is that?",
                       k, vt, expl,
                       ["Find pin 1. Where do its strings go?",
                        "Count the moves from pin 1 to the other end of one string. Pin 1 itself is not a move.",
                        "Count the short way round. The two ways round add up to " + str(n) + "."],
                       {"n": n, "k": k})
    return None


def loop_from_1(n, k):
    pins, x = [1], wrap(1 + k, n)
    while x != 1:
        pins.append(x)
        x = wrap(x + k, n)
    return pins


def make_visits(rng, cfg, seed):
    for _ in range(2000):
        n = rng.choice(cfg["n"])
        k = rng.randint(2, n - 2)
        truth = n // math.gcd(n, k)
        wrong = {"EVERY_PIN": n, "ONE_LAP": ceil_div(n, k), "COUNTS_START_TWICE": truth + 1}
        vt = value_tags("visits", truth, wrong)
        if not vt or len(vt) < 3:
            continue
        pins = loop_from_1(n, k)
        expl = [f"Start at pin 1 and keep going {k} pins clockwise. After pin {n} comes pin 1.",
                "  " + " → ".join(str(p) for p in pins + [1]),
                f"The loop lands on pin 1 again after {sq(truth, 'pin')}; the other pins are never reached.",
                f"So the loop touches {truth} pins."]
        scene = {"n": n, "k": k, "lines": [[1, wrap(1 + k, n)]]}
        return problem(cfg, "visits", seed, scene, render_star(scene, seed, "visits"),
                       STAR_PROMPT.format(n=n),
                       f"Start at pin 1. Run the string to the pin {k} places clockwise, then on another {k} places, and so "
                       f"on, until you land on pin 1 again. How many different pins does the string touch, pin 1 included?",
                       truth, vt, expl,
                       ["The first string is drawn. Where does the next one go?",
                        f"Write down each pin you land on. After pin {n} keep counting from pin 1.",
                        "Stop only when you land on pin 1 exactly. Going past it doesn't count."],
                       {"n": n, "k": k})
    return None


# --------------------------------------------------------------------------
# Level 4: the Ferris wheel
# --------------------------------------------------------------------------

def make_turns(rng, cfg, seed):
    for _ in range(4000):
        n = rng.choice(cfg["n"])
        stops = rng.sample(range(2, n + 1), cfg["stops"])
        path = [1] + stops
        moves = list(zip(path, path[1:]))
        truth = sum(short(a, b, n) for a, b in moves)
        if any(short(a, b, n) == 1 for a, b in moves):
            continue                    # a one-car move teaches nothing
        wrong = {"FROM_START_EACH_TIME": sum(short(1, b, n) for b in stops),
                 "ONE_WAY_ONLY": sum(around(a, b, n) for a, b in moves),
                 "NO_WRAP": sum(abs(b - a) for a, b in moves)}
        vt = value_tags("turns", truth, wrong)
        if not vt or len(vt) < 3:
            continue
        expl = ["Each move starts from the car at the platform now. Count both ways round and take the shorter."]
        for a, b in moves:
            up, down = around(a, b, n), around(b, a, n)
            expl.append(f"  car {a} to car {b}: {min(up, down)} presses (the other way is {max(up, down)})")
        expl.append("  " + " + ".join(str(short(a, b, n)) for a, b in moves) + f" = {truth}")
        expl.append(f"So the fewest is {truth} presses.")
        scene = {"n": n, "order": stops}
        return problem(cfg, "turns", seed, scene, render_wheel(scene, seed),
                       f"A Ferris wheel has {n} cars, numbered 1 to {n}. Riders can only get off from the car at the "
                       "platform. Each press of the button turns the wheel one car, either way. Car 1 is at the platform now.",
                       f"The riders get off in this order: cars {', '.join(map(str, stops))}. What is the fewest presses "
                       "it takes?",
                       truth, vt, expl,
                       ["After the first riders get off, which car is at the platform?",
                        "For each move, count both ways round the wheel.",
                        "Take the shorter way each time, then add up the presses."],
                       {"n": n})
    return None


# --------------------------------------------------------------------------
# Level 5: two karts
# --------------------------------------------------------------------------

def track(lead, loop):
    """next square for squares 1..lead+loop: a straight road 1..lead into a loop lead+1..lead+loop."""
    last = lead + loop
    return {c: (c + 1 if c < last else lead + 1) for c in range(1, last + 1)}


def make_meet(rng, cfg, seed):
    for _ in range(2000):
        lead, loop = rng.choice(cfg["lead"]), rng.choice(cfg["loop"])
        nxt = track(lead, loop)
        slow = fast = 1
        rows = []
        for t in range(1, 4 * (lead + loop)):
            slow = nxt[slow]
            fast = nxt[nxt[fast]]
            rows.append((t, slow, fast))
            if slow == fast:
                break
        truth = slow
        if len(rows) > 12:
            continue                    # keeps the table in the explanation short
        wrong = {"LOOP_ENTRANCE": lead + 1, "BACK_TO_START": 1}
        vt = value_tags("meet", truth, wrong)
        if not vt or len(vt) < 2:
            continue
        expl = ["Move both karts one second at a time:"]
        expl += [f"  second {t}: slow on {s}, fast on {f}" for t, s, f in rows]
        expl.append(f"So they first meet on square {truth}.")
        scene = {"lead": lead, "loop": loop}
        return problem(cfg, "meet", seed, scene, render_track(scene, seed),
                       f"A go-kart track has a straight road ({'square 1' if lead == 1 else f'squares 1 to {lead}'}) that leads into a loop (squares {lead + 1} "
                       f"to {lead + loop}). After square {lead + loop} the karts go round the loop again. Two karts start "
                       "together on square 1. The slow kart moves 1 square each second, the fast kart 2 squares.",
                       "On which square are the karts together again for the first time?",
                       truth, vt, expl,
                       ["Where is each kart after 1 second? After 2 seconds?",
                        f"After square {lead + loop}, follow the arrow. Where does it lead?",
                        "Make a table: second, slow kart's square, fast kart's square. Stop when they match."],
                       {"lead": lead, "loop": loop})
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


def problem(cfg, q, seed, scene, svg, prompt, question, truth, vt, expl, hints, knobs):
    return Problem(family="circle_steps", level=cfg["level"], question_type=q, seed=seed, scene=scene, svg=svg,
                   prompt=prompt, question=question, options=[], answer_index=-1, answer_value=truth, entry="number",
                   distractors=[], value_tags=vt, concepts=CONCEPTS[q], explanation=expl, hints=hints, knobs=knobs)


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    rng = random.Random(seed)
    make = {"step": make_step, "label": make_label, "visits": make_visits, "turns": make_turns,
            "meet": make_meet}[cfg["question"]]
    p = make(rng, cfg, seed)
    if not p:
        raise RuntimeError(f"circle_steps generation failed at level {level}")
    return p


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

FONT = 'font-family="Helvetica, Arial, sans-serif"'
BG, INK, SOFT = "#eef3f8", "#1f2933", "#52606d"
SPOT, EDGE, GOLD, GOLD_EDGE, STRING = "#ffffff", "#7b8794", "#ffd166", "#b7791f", "#c2410c"
W = 420


def head(h, seed, kind, extra=""):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" width="{W}" height="{h}" {FONT} '
            f'class="rings" data-family="circle_steps" data-kind="{kind}" data-seed="{seed}"{extra}>',
            f'<rect x="0" y="0" width="{W}" height="{h}" rx="10" fill="{BG}"/>']


def on_circle(cx, cy, r, i, n, start=-90):
    a = math.radians(start + 360 * i / n)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def disc(x, y, r, label, cls, attrs, fill=SPOT, edge=EDGE, sw=1.5, fs=14):
    return (f'<g class="{cls}" {attrs}><circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="{edge}" '
            f'stroke-width="{sw}"/><text x="{x:.1f}" y="{y + fs * .36:.1f}" font-size="{fs}" font-weight="bold" '
            f'text-anchor="middle" fill="{INK}">{label}</text></g>')


def arrow_defs():
    return (f'<defs><marker id="cs-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{SOFT}"/></marker></defs>')


def clockwise_arc(cx, cy, r):
    x0, y0 = on_circle(cx, cy, r, -1, 8)
    x1, y1 = on_circle(cx, cy, r, 1, 8)
    return (f'<path d="M{x0:.1f},{y0:.1f} A{r},{r} 0 0 1 {x1:.1f},{y1:.1f}" fill="none" stroke="{SOFT}" '
            f'stroke-width="2" marker-end="url(#cs-arrow)"/>')


def render_step(sc, seed):
    n, s, k = sc["n"], sc["start"], sc["move"]
    h, cx, cy, r = 352, W / 2, 168, 130
    out = head(h, seed, "step", f' data-n="{n}" data-start="{s}" data-move="{k}"')
    out.append(arrow_defs())
    for i in range(n):
        x, y = on_circle(cx, cy, r, i, n)
        here = i + 1 == s
        out.append(disc(x, y, 19, i + 1, "spot", f'data-spot="{i + 1}" data-counter="{int(here)}"',
                        GOLD if here else SPOT, GOLD_EDGE if here else EDGE, 3 if here else 1.5))
    out.append(clockwise_arc(cx, cy, 62))
    out.append(f'<text x="{cx}" y="{cy - 6}" font-size="14" font-weight="bold" text-anchor="middle" fill="{INK}">Move {k}</text>')
    out.append(f'<text x="{cx}" y="{cy + 14}" font-size="12" text-anchor="middle" fill="{SOFT}">clockwise</text>')
    out.append(f'<text x="{W / 2}" y="{h - 8}" font-size="12" text-anchor="middle" fill="{SOFT}">'
               'Gold: the square your counter is on</text>')
    out.append("</svg>")
    return "".join(out)


def render_star(sc, seed, kind):
    n = sc["n"]
    h, cx, cy, r = 360, W / 2, 178, 140
    out = head(h, seed, kind, f' data-n="{n}"' + (f' data-k="{sc["k"]}"' if kind == "visits" else ""))
    out.append(f'<defs><marker id="cs-str" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="8" markerHeight="8" '
               f'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{STRING}"/></marker></defs>')
    pos = {i + 1: on_circle(cx, cy, r, i, n) for i in range(n)}
    for a, b in sc["lines"]:
        (x0, y0), (x1, y1) = pos[a], pos[b]
        if kind == "visits":            # stop short of the pin so the arrowhead shows
            d = math.hypot(x1 - x0, y1 - y0)
            x1, y1 = x1 - (x1 - x0) * 9 / d, y1 - (y1 - y0) * 9 / d
        out.append(f'<line class="string" data-from="{a}" data-to="{b}" x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" '
                   f'y2="{y1:.1f}" stroke="{STRING}" stroke-width="2"' +
                   (' marker-end="url(#cs-str)"' if kind == "visits" else "") + "/>")
    for i in range(1, n + 1):
        x, y = pos[i]
        lx, ly = on_circle(cx, cy, r + 20, i - 1, n)
        out.append(f'<g class="pin" data-pin="{i}"><circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{INK}"/>'
                   f'<text x="{lx:.1f}" y="{ly + 5:.1f}" font-size="14" font-weight="bold" text-anchor="middle" '
                   f'fill="{INK}">{i}</text></g>')
    out.append("</svg>")
    return "".join(out)


def render_wheel(sc, seed):
    n, order = sc["n"], sc["order"]
    h, cx, cy, r = 380, W / 2, 160, 120
    out = head(h, seed, "turns", f' data-n="{n}" data-order="{" ".join(map(str, order))}"')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{EDGE}" stroke-width="3"/>')
    out.append(f'<circle cx="{cx}" cy="{cy}" r="8" fill="{EDGE}"/>')
    for i in range(n):
        x, y = on_circle(cx, cy, r, i, n, start=90)
        out.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="{EDGE}" stroke-width="1.5"/>')
    for i in range(n):
        x, y = on_circle(cx, cy, r, i, n, start=90)
        here = i == 0
        out.append(disc(x, y, 19, i + 1, "car", f'data-car="{i + 1}" data-platform="{int(here)}"',
                        GOLD if here else SPOT, GOLD_EDGE if here else EDGE, 3 if here else 1.5))
    py = cy + r + 22
    out.append(f'<rect class="platform" x="{cx - 50}" y="{py}" width="100" height="10" rx="3" fill="#7a5a2b"/>')
    out.append(f'<text x="{cx}" y="{py + 28}" font-size="12" text-anchor="middle" fill="{SOFT}">Platform</text>')
    oy = h - 26
    out.append(f'<text x="40" y="{oy + 5}" font-size="13" fill="{INK}">Order:</text>')
    for j, c in enumerate(order):
        out.append(f'<g class="stop" data-step="{j + 1}" data-car="{c}"><rect x="{96 + 44 * j}" y="{oy - 14}" width="34" '
                   f'height="28" rx="6" fill="{SPOT}" stroke="{EDGE}"/><text x="{113 + 44 * j}" y="{oy + 5}" font-size="14" '
                   f'font-weight="bold" text-anchor="middle" fill="{INK}">{c}</text></g>')
    out.append("</svg>")
    return "".join(out)


def render_track(sc, seed):
    lead, loop = sc["lead"], sc["loop"]
    nxt = track(lead, loop)
    R = max(64, round(46 * loop / (2 * math.pi)))
    cx, cy = W / 2, R + 34
    pos = {}
    for j in range(loop):                    # the loop entrance is at the bottom, then clockwise
        pos[lead + 1 + j] = on_circle(cx, cy, R, j, loop, start=90)
    for c in range(1, lead + 1):
        pos[c] = (cx, cy + R + 44 * (lead + 1 - c))
    h = int(cy + R + 44 * lead + 46)
    out = head(h, seed, "meet", f' data-start="1" data-slow="1" data-fast="2"')
    out.append(arrow_defs())
    for c, d in nxt.items():
        (x0, y0), (x1, y1) = pos[c], pos[d]
        dist = math.hypot(x1 - x0, y1 - y0)
        ux, uy = (x1 - x0) / dist, (y1 - y0) / dist
        out.append(f'<line x1="{x0 + ux * 18:.1f}" y1="{y0 + uy * 18:.1f}" x2="{x1 - ux * 19:.1f}" y2="{y1 - uy * 19:.1f}" '
                   f'stroke="{SOFT}" stroke-width="2" marker-end="url(#cs-arrow)"/>')
    for c in sorted(pos):
        x, y = pos[c]
        st = c == 1
        out.append(disc(x, y, 16, c, "cell", f'data-cell="{c}" data-next="{nxt[c]}"',
                        GOLD if st else SPOT, GOLD_EDGE if st else EDGE, 3 if st else 1.5, 13))
    x1, y1 = pos[1]
    out.append(f'<text x="{x1 + 26}" y="{y1 + 5}" font-size="12" fill="{SOFT}">Start: both karts</text>')
    out.append(f'<text x="{cx}" y="{cy + 5}" font-size="12" text-anchor="middle" fill="{SOFT}">Loop</text>')
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    import sys
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print(json.dumps({k: v for k, v in asdict(generate(lvl, sd)).items() if k not in ("svg",)}, indent=2, ensure_ascii=False))

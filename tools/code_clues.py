"""
Problem family: code_clues (Code Lock). Folder: code-lock.

Concept targets: CONSTRAINT_SAT, ELIMINATION.

Scenario (original): a treasure chest has a lock with three or four wheels. Each
wheel shows one symbol, and the code uses different symbols on every wheel. Some
guesses were tried; next to each guess it says how many of its symbols are right
and in the right spot, and how many are right but in a wrong spot. Find the code.

This follows the idea of a "crack the code from feedback" task (Mastermind-style
consistency checking); the wording, theme, symbols and pictures are our own.

One scene model (wheels, the symbols a wheel can show, and the clues) drives both
what the page draws and the solver. The independent checker recomputes every
clue's feedback from the answer, enumerates every possible code to confirm that
exactly one fits, and re-derives each wrong answer's tags.

Question types:
  choose:  which of four codes opens the lock? (choice; levels 1-3)
  crack:   build the code yourself by tapping symbols (entry "code"; levels 4-5).
           The clues leave exactly one code.

Misconception solvers (each accepts a wrong code):
  SKIPS_EMPTY_CLUE        ignores a "nothing is right" clue, so a crossed-out symbol stays in
  CLUE_POSITION_IGNORED   counts how many symbols match but not whether they are in the right spot
  CLUE_FEEDBACK_SWAPPED   reads "right spot" as "wrong spot" and the other way round
  SKIPS_A_CLUE            checks the code against all the clues but one
"""

import json
import random
from dataclasses import dataclass, field, asdict
from itertools import permutations

SYMBOLS = {"S": "sun", "M": "moon", "T": "star", "H": "heart", "L": "leaf", "D": "drop", "Z": "bolt", "B": "bell"}
ORDER = "SMTHLDZB"
WORDS = {3: "three", 4: "four"}


# --------------------------------------------------------------------------
# Feedback and the misconception readings of it
# --------------------------------------------------------------------------

def feedback(guess, code):
    """(right symbol in the right spot, right symbol in a wrong spot). Symbols are all different."""
    exact = sum(1 for g, c in zip(guess, code) if g == c)
    return exact, len(set(guess) & set(code)) - exact


def fits(code, clue):
    guess, e, m = clue
    return feedback(guess, code) == (e, m)


def fits_all(code, clues):
    return all(fits(code, c) for c in clues)


def broken(code, clues):
    return [i for i, c in enumerate(clues) if not fits(code, c)]


def is_empty(clue):
    return clue[1] == 0 and clue[2] == 0


def misreadings(code, clues):
    """Tags of the mistaken readings under which this (wrong) code would look right."""
    tags = []
    bad = broken(code, clues)
    if not bad:
        return tags
    if all(is_empty(clues[i]) for i in bad):
        tags.append("SKIPS_EMPTY_CLUE")
    if all(sum(feedback(g, code)) == e + m for g, e, m in clues):
        tags.append("CLUE_POSITION_IGNORED")
    if all(feedback(g, code) == (m, e) for g, e, m in clues):
        tags.append("CLUE_FEEDBACK_SWAPPED")
    if len(bad) == 1:
        tags.append("SKIPS_A_CLUE")
    return tags


MISCONCEPTIONS = {
    "SKIPS_EMPTY_CLUE": {"concept": "ELIMINATION",
        "description": "Ignores a clue that says nothing is right, so a symbol that clue rules out stays in the code.",
        "remediation": "Start with the 'nothing is right' clue: have the student cross out every symbol in it before using any other clue."},
    "CLUE_POSITION_IGNORED": {"concept": "CONSTRAINT_SAT",
        "description": "Checks how many symbols a guess shares with the code, but not whether each one is in the right spot.",
        "remediation": "For each clue, have the student point to each shared symbol and say whether it sits in the same spot in both."},
    "CLUE_FEEDBACK_SWAPPED": {"concept": "CONSTRAINT_SAT",
        "description": "Mixes up the two counts: reads 'right spot' as 'wrong spot' and the other way round.",
        "remediation": "Have the student say each clue in full words ('one symbol is in exactly the right spot') before testing a code."},
    "SKIPS_A_CLUE": {"concept": "ELIMINATION",
        "description": "Stops checking a code before trying it against every clue, so a code that breaks one clue looks right.",
        "remediation": "Have the student tick off each clue as they test a code, and only accept a code with every clue ticked."},
}

LADDER = [
    {"level": 1, "question": "choose", "slots": 3, "pool": 6, "empty": True, "clues": (3, 4),
     "require": ["SKIPS_EMPTY_CLUE"], "note": "Three wheels. One clue says nothing is right; pick the code from four."},
    {"level": 2, "question": "choose", "slots": 3, "pool": 6, "empty": False, "clues": (4, 5),
     "require": ["CLUE_POSITION_IGNORED"], "note": "Three wheels. A wrong choice shares the right symbols but puts one in a spot a clue rules out."},
    {"level": 3, "question": "choose", "slots": 4, "pool": 8, "empty": False, "clues": (4, 6),
     "require": ["SKIPS_A_CLUE"], "note": "Four wheels and more clues; one wrong choice breaks just one clue."},
    {"level": 4, "question": "crack", "slots": 3, "pool": 6, "empty": True, "clues": (4, 5),
     "require": [], "note": "Three wheels, no choices: build the only code that fits every clue."},
    {"level": 5, "question": "crack", "slots": 4, "pool": 8, "empty": False, "clues": (5, 6),
     "require": [], "note": "Four wheels, no choices: build the only code that fits every clue."},
]


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
    prompt: str
    question: str
    options: list
    answer_index: int
    answer_value: str
    entry: str
    distractors: list
    value_tags: dict
    concepts: list
    explanation: list
    hints: list
    knobs: dict = field(default_factory=dict)


def names(code):
    return ", ".join(SYMBOLS[c] for c in code)


def join(words, last="and"):
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + f" {last} " + words[-1]


def fb_text(e, m):
    if e == 0 and m == 0:
        return "nothing is right"
    parts = []
    if e:
        parts.append(f"{e} in the right spot")
    if m:
        parts.append(f"{m} in a wrong spot")
    return " and ".join(parts)


def all_codes(pool, slots):
    return ["".join(p) for p in permutations(pool, slots)]


def make_clues(rng, cfg, pool, secret, codes):
    """Guesses until exactly one code fits, then drop any clue the others make unnecessary."""
    slots = cfg["slots"]
    clues = []
    if cfg["empty"]:
        out = [s for s in pool if s not in secret]
        if len(out) < slots:
            return None
        g = "".join(rng.sample(out, slots))
        clues.append((g, 0, 0))
    left = [c for c in codes if fits_all(c, clues)]
    for _ in range(16):
        if len(left) == 1:
            break
        tries = []
        for _ in range(40):
            g = "".join(rng.sample(pool, slots))
            e, m = feedback(g, secret)
            if g == secret or e == slots or any(g == c[0] for c in clues) or (e == 0 and m == 0):
                continue
            n = sum(1 for c in left if feedback(g, c) == (e, m))
            if n < len(left):
                tries.append((n, g, e, m))
        if not tries:
            return None
        n, g, e, m = rng.choice(tries)              # any guess that helps; the best ones would leave too few clues
        clues.append((g, e, m))
        left = [c for c in left if fits(c, clues[-1])]
    if len(left) != 1:
        return None
    # prune: a clue the others make unnecessary is dropped (the empty clue stays when the level wants one)
    order = list(range(len(clues)))
    rng.shuffle(order)
    keep = list(clues)
    for i in order:
        c = clues[i]
        if cfg["empty"] and is_empty(c) and sum(1 for x in keep if is_empty(x)) == 1:
            continue
        trial = [x for x in keep if x != c]
        if sum(1 for code in codes if fits_all(code, trial)) == 1:
            keep = trial
    lo, hi = cfg["clues"]
    if not lo <= len(keep) <= hi:
        return None
    rng.shuffle(keep)
    return keep


def why_wrong(code, clues):
    i = broken(code, clues)[0]
    g, e, m = clues[i]
    got = feedback(g, code)
    return (f"{names(code)} breaks clue {i + 1}: against {names(g)} it would give {fb_text(*got)}, "
            f"but the clue says {fb_text(e, m)}.")


def clue_check(i, clue, code):
    g, e, m = clue
    same = [SYMBOLS[a] for a, b in zip(g, code) if a == b]
    moved = [SYMBOLS[a] for a in g if a in code and a not in [x for x, y in zip(g, code) if x == y]]
    if not same and not moved:
        return f"Clue {i + 1} ({names(g)}): none of these symbols is in the code. Nothing is right. ✓"
    bits = []
    if same:
        bits.append(f"{join(same)} in the same spot" + ("s" if len(same) > 1 else ""))
    if moved:
        bits.append(f"{join(moved)} in " + ("different spots" if len(moved) > 1 else "a different spot"))
    return f"Clue {i + 1} ({names(g)}): the code has {' and '.join(bits)}, so {fb_text(e, m)}. ✓"


PROMPT = ("A treasure chest has a lock with {w} wheels. Each wheel shows one symbol, and the code uses {w} "
          "different symbols. Some guesses were tried. Next to each guess it says how many of its symbols are in "
          "the code and in the right spot, and how many are in the code but in a wrong spot.")


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    rng = random.Random(seed)
    pool = ORDER[:cfg["pool"]]
    codes = all_codes(pool, cfg["slots"])
    for _ in range(400):
        secret = rng.choice(codes)
        clues = make_clues(rng, cfg, pool, secret, codes)
        if not clues:
            continue
        p = (make_choose if cfg["question"] == "choose" else make_crack)(rng, cfg, seed, pool, secret, clues, codes)
        if p:
            return p
    raise RuntimeError(f"code_clues generation failed at level {level}")


def scene_dict(cfg, pool, clues):
    return {"slots": cfg["slots"], "pool": list(pool), "clues": [[g, e, m] for g, e, m in clues]}


def hints_for(cfg, clues, choose):
    h = []
    if any(is_empty(c) for c in clues):
        h.append("Start with the clue that says nothing is right. Cross out every symbol in it.")
    else:
        h.append("Start with the clue that has the most symbols right. Which symbols must be in the code?")
    h.append("'Wrong spot' means the symbol is in the code, but not on the wheel where that guess put it.")
    if choose:
        h.append("Test each choice against every clue, one clue at a time. A code that breaks even one clue is out.")
    else:
        h.append("Choose one clue and try each way it could be true. Check each try against all the other clues.")
    return h


def order_tags(tags, first):
    return sorted(tags, key=lambda t: (t not in first, first.index(t) if t in first else 0, t))


def make_choose(rng, cfg, seed, pool, secret, clues, codes):
    tagged = {}
    for c in codes:
        if c != secret:
            t = misreadings(c, clues)
            if t:
                tagged[c] = t
    need = cfg["require"]
    first_pool = [c for c in tagged if all(r in tagged[c] for r in need)]
    if not first_pool:
        return None
    pick = [rng.choice(sorted(first_pool))]
    rest = sorted(c for c in tagged if c not in pick)
    rng.shuffle(rest)
    # prefer wrong choices that show different mistakes, and codes that share symbols with the answer
    rest.sort(key=lambda c: (tagged[c][0] in {tagged[x][0] for x in pick}, -len(set(c) & set(secret))))
    for c in rest:
        if len(pick) == 3:
            break
        if tagged[c][0] not in {tagged[x][0] for x in pick} or len(rest) < 6:
            pick.append(c)
    for c in rest:
        if len(pick) == 3:
            break
        if c not in pick:
            pick.append(c)
    if len(pick) < 3:
        return None
    # not guessable: every symbol of the answer also appears in some wrong choice
    if not all(any(s in d for d in pick) for s in secret):
        return None
    opts = pick + [secret]
    rng.shuffle(opts)
    ans = opts.index(secret)
    expl = ["Test each code against every clue. A code that breaks one clue cannot be right."]
    for o in opts:
        if o != secret:
            expl.append(why_wrong(o, clues))
    expl += [clue_check(i, c, secret) for i, c in enumerate(clues)]
    expl.append(f"So the code is {names(secret)}.")
    return Problem(
        family="code_clues", level=cfg["level"], question_type="choose", seed=seed,
        scene=scene_dict(cfg, pool, clues), prompt=PROMPT.format(w=WORDS[cfg["slots"]]),
        question="Which code opens the lock?",
        options=opts, answer_index=ans, answer_value=secret, entry="choice",
        distractors=[{"option": o, "misconceptions": order_tags(tagged[o], need)} for o in opts if o != secret],
        value_tags={}, concepts=["CONSTRAINT_SAT", "ELIMINATION"], explanation=expl,
        hints=hints_for(cfg, clues, True),
        knobs={"clues": len(clues), "slots": cfg["slots"], "pool": len(pool)},
    )


def make_crack(rng, cfg, seed, pool, secret, clues, codes):
    value_tags = {}
    for c in codes:
        if c != secret:
            t = misreadings(c, clues)
            if t:
                value_tags[c] = t
    if len({t[0] for t in value_tags.values()}) < 2:
        return None
    empties = [c for c in clues if is_empty(c)]
    expl = []
    left = codes
    if empties:
        gone = sorted({s for g, _, _ in empties for s in g}, key=ORDER.index)
        left = [c for c in codes if not set(c) & set(gone)]
        ks = ", ".join(str(clues.index(c) + 1) for c in empties)
        expl.append(f"Clue {ks} says nothing is right, so the code has no {join([SYMBOLS[s] for s in gone], 'or')}. "
                    f"That leaves {len(left)} possible codes.")
    expl.append(f"Testing {'those codes against the other clues' if empties else 'codes against the clues'} leaves only one: "
                f"{names(secret)}. Check it against every clue:")
    expl += [clue_check(i, c, secret) for i, c in enumerate(clues)]
    expl.append(f"So the code is {names(secret)}.")
    return Problem(
        family="code_clues", level=cfg["level"], question_type="crack", seed=seed,
        scene=scene_dict(cfg, pool, clues), prompt=PROMPT.format(w=WORDS[cfg["slots"]]),
        question="What is the code? Tap a symbol to put it on the next empty wheel.",
        options=[], answer_index=-1, answer_value=secret, entry="code",
        distractors=[], value_tags={k: v for k, v in sorted(value_tags.items())},
        concepts=["CONSTRAINT_SAT", "ELIMINATION"], explanation=expl,
        hints=hints_for(cfg, clues, False),
        knobs={"clues": len(clues), "slots": cfg["slots"], "pool": len(pool), "tagged_codes": len(value_tags)},
    )


if __name__ == "__main__":
    import sys
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sd = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print(json.dumps(asdict(generate(lvl, sd)), indent=2, ensure_ascii=False))

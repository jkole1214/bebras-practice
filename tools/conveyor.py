"""
Problem family: conveyor (matching with a running count or a stack).

Concept targets: STACK_MATCHING, STATE.
Source task: Nuts and Bolts (2022-23 practice; Benjamin C, Cadet B, Junior A).

Scenario (original wording): a worker takes parts off a belt one at a time.
A nut goes into the bucket; a bolt is screwed into a nut taken from the
bucket and the pair is put away. Things go wrong if a bolt arrives and the
bucket has no nut, or the belt ends with nuts still in the bucket.
At the higher levels there are small and big parts: a bolt must fit the nut
on TOP of the stack of nuts (the most recent one put in).

Scene model: the belt, a list of tokens.
  "n" small nut   "b" small bolt   "N" big nut   "B" big bolt
Single-size levels use only n and b.

Question types:
  valid    which of four belts works? (one size)
  depth    what is the most nuts ever in the bucket at once? (typed)
  stack    which of four belts works? (two sizes, the bucket is a stack)
  repair   fewest parts to add so the belt works (typed)
"""

import json
import random
from dataclasses import dataclass, field, asdict

LADDER = [
    {"level": 1, "question": "valid", "length": (6, 8), "note": "Which belt works? Short belts, one size"},
    {"level": 2, "question": "valid", "length": (10, 12), "note": "Which belt works? Longer belts that go wrong late"},
    {"level": 3, "question": "depth", "length": (10, 14), "note": "Most nuts in the bucket at once (type the number)"},
    {"level": 4, "question": "stack", "length": (8, 10), "note": "Two sizes: a bolt must fit the nut on top"},
    {"level": 5, "question": "repair", "length": (9, 13), "note": "Fewest parts to add so the belt works (type the number)"},
]

MISCONCEPTIONS = {
    "TOTALS_ONLY_MATCHING": {"concept": "STACK_MATCHING",
        "description": "Accepts a belt because it has as many bolts as nuts, missing a moment when a bolt finds the bucket empty.",
        "remediation": "Write the number of nuts in the bucket under every part, left to right."},
    "IGNORES_LEFTOVERS": {"concept": "STACK_MATCHING",
        "description": "Checks only that no bolt finds the bucket empty, forgetting that nuts left over at the end are also a failure.",
        "remediation": "Ask how many nuts are in the bucket when the belt is empty."},
    "CHECKS_START_ONLY": {"concept": "STACK_MATCHING",
        "description": "Checks the first few parts and stops, missing a problem near the end of the belt.",
        "remediation": "Keep the running count all the way to the last part."},
    "TOTAL_NUTS_FOR_DEPTH": {"concept": "STATE",
        "description": "Answers 'most nuts in the bucket at once' with the total number of nuts on the belt.",
        "remediation": "Bolts take nuts out as you go. Track the bucket after each part."},
    "LONGEST_RUN_FOR_DEPTH": {"concept": "STATE",
        "description": "Looks only at the longest row of nuts in a row, forgetting nuts already waiting in the bucket.",
        "remediation": "Start each run of nuts from the number already in the bucket."},
    "ENDING_COUNT_FOR_DEPTH": {"concept": "STATE",
        "description": "Gives the number of nuts in the bucket at the end of the belt instead of the most at any moment.",
        "remediation": "Ask: when was the bucket fullest?"},
    "SIZES_SEPARATELY": {"concept": "STACK_MATCHING",
        "description": "Checks small parts and big parts separately, missing that a bolt must fit the nut on top of the pile.",
        "remediation": "Draw the pile of nuts and only let a bolt take the top one."},
    "DIFFERENCE_FOR_REPAIR": {"concept": "STACK_MATCHING",
        "description": "Adds only enough parts to make the totals equal, ignoring bolts that came too early.",
        "remediation": "Count the bolts that found an empty bucket and the nuts left at the end separately."},
    "SHORTFALL_ONLY": {"concept": "STACK_MATCHING",
        "description": "Counts only the extra nuts needed for early bolts and forgets nuts left over at the end.",
        "remediation": "After fixing the early bolts, how many nuts are still in the bucket at the end?"},
    "LEFTOVER_ONLY": {"concept": "STACK_MATCHING",
        "description": "Counts only the nuts left at the end and forgets bolts that found the bucket empty.",
        "remediation": "Run the count from the start: does it ever go below zero?"},
}

NAME = {"n": "small nut", "b": "small bolt", "N": "big nut", "B": "big bolt"}
PROMPT = ("Benoit takes parts off the belt from left to right. A nut goes into his bucket. "
          "A bolt is screwed into a nut from the bucket. It goes wrong if a bolt comes and the bucket is empty, "
          "or if nuts are left in the bucket when the belt is done.")
PROMPT_STACK = ("Now there are small and big parts. Benoit's nuts sit in a pile in the bucket, and he can only reach the "
                "nut on top (the last one he put in). A bolt must be the same size as that top nut. It also goes wrong "
                "if the bucket is empty when a bolt comes, or if nuts are left at the end.")


# --------------------------------------------------------------------------
# Solvers
# --------------------------------------------------------------------------

def run_counts(belt):
    """Bucket count after each part (one size); may go negative."""
    c, out = 0, []
    for t in belt:
        c += 1 if t in "nN" else -1
        out.append(c)
    return out


def first_failure(belt):
    """(index, reason) of the first thing that goes wrong, or None (stack rules; one size is a special case)."""
    pile = []
    for i, t in enumerate(belt):
        if t in "nN":
            pile.append(t)
        else:
            if not pile:
                return i, "empty"
            top = pile.pop()
            if (t == "b") != (top == "n"):
                return i, "size"
    if pile:
        return len(belt), "leftover"
    return None


def works(belt):
    return first_failure(belt) is None


def max_depth(belt):
    return max([0] + run_counts(belt))


def repair_count(belt):
    """Fewest parts to add (one size): bolts that hit an empty bucket + nuts left at the end."""
    c, short = 0, 0
    for t in belt:
        if t == "n":
            c += 1
        elif c == 0:
            short += 1
        else:
            c -= 1
    return short + c


# Misconception views

def m_totals_only(belt):
    return belt.count("n") + belt.count("N") == belt.count("b") + belt.count("B")


def m_ignores_leftovers(belt):
    return min([0] + run_counts(belt)) >= 0


def m_checks_start(belt, k=4):
    return min([0] + run_counts(belt[:k])) >= 0


def m_sizes_separately(belt):
    for small in (True, False):
        sub = [t.lower() for t in belt if (t.islower() == small)]
        if min([0] + run_counts(sub)) < 0 or (run_counts(sub) or [0])[-1] != 0:
            return False
    return True


def m_total_nuts(belt):
    return sum(t in "nN" for t in belt)


def m_longest_run(belt):
    best = cur = 0
    for t in belt:
        cur = cur + 1 if t == "n" else 0
        best = max(best, cur)
    return best


def m_ending(belt):
    return max(0, run_counts(belt)[-1])


def m_difference(belt):
    return abs(belt.count("n") - belt.count("b"))


def m_shortfall_leftover(belt):
    c = 0
    for t in belt:
        c = c + 1 if t == "n" else max(0, c - 1)
    return c


def m_leftover_only(belt):
    return max(0, run_counts(belt)[-1])


# --------------------------------------------------------------------------
# Random belts
# --------------------------------------------------------------------------

def dyck(rng, pairs, sizes="n"):
    """A random belt that works, with `pairs` nut-bolt pairs."""
    while True:
        seq, pile, opened = [], [], 0
        while len(seq) < 2 * pairs:
            can_open = opened < pairs
            can_close = bool(pile)
            if can_open and (not can_close or rng.random() < 0.55):
                s = rng.choice(sizes)
                seq.append(s)
                pile.append(s)
                opened += 1
            else:
                s = pile.pop()
                seq.append("b" if s == "n" else "B")
        return seq


def nested_mixed(belt):
    """True if some nut sits on top of a nut of the other size (sizes really nest)."""
    pile = []
    for t in belt:
        if t in "nN":
            if pile and pile[-1] != t:
                return True
            pile.append(t)
        else:
            pile.pop()
    return False


def show(belt):
    return "".join(belt)


def trace_lines(belt):
    lines = ["Write the number of nuts in the bucket after each part (N = nut, B = bolt):"]
    cnt = run_counts(belt)
    lines.append("  " + " ".join(f"{NAME[t].split()[1][0].upper():>2}" for t in belt))
    lines.append("  " + " ".join(f"{c:>2}" for c in cnt))
    return lines


def stack_lines(belt):
    lines = ["Keep the pile of nuts after each part (top of the pile on the right):"]
    pile = []
    for t in belt:
        if t in "nN":
            pile.append(t)
            lines.append(f"  {NAME[t]:<10} pile: {''.join(pile) or '(empty)'}")
        else:
            if not pile:
                lines.append(f"  {NAME[t]:<10} bucket empty: goes wrong")
                return lines
            top = pile[-1]
            if (t == "b") != (top == "n"):
                lines.append(f"  {NAME[t]:<10} top nut is a {NAME[top]}: goes wrong")
                return lines
            pile.pop()
            lines.append(f"  {NAME[t]:<10} pile: {''.join(pile) or '(empty)'}")
    if pile:
        lines.append(f"  belt done, {len(pile)} nut(s) left: goes wrong")
    return lines


# --------------------------------------------------------------------------
# Problem
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
    answer_value: object
    entry: str
    distractors: list
    value_tags: dict
    concepts: list
    explanation: list
    hints: list
    knobs: dict = field(default_factory=dict)


def mutate_totals(rng, belt):
    """Equal totals, but a bolt comes too early: swap one nut-bolt so the count dips below 0."""
    for _ in range(50):
        s = belt[:]
        i = rng.randrange(len(s) - 1)
        j = rng.randrange(i + 1, len(s))
        if s[i] == "n" and s[j] == "b":
            s[i], s[j] = "b", "n"
            if min(run_counts(s)) < 0:
                return s
    return None


def mutate_leftover(rng, belt):
    """No bolt ever finds the bucket empty, but nuts are left: turn a late bolt into a nut."""
    idx = [i for i, t in enumerate(belt) if t == "b"]
    for _ in range(20):
        i = rng.choice(idx[len(idx) // 2:])
        s = belt[:]
        s[i] = "n"
        if min(run_counts(s)) >= 0:
            # keep the length even-looking: also change one early nut to bolt? no: lengths may differ
            return s
    return None


def mutate_late(rng, belt):
    """Fails only near the end: first problem after position 4."""
    for _ in range(80):
        s = belt[:]
        i = rng.randrange(len(s) // 2, len(s) - 1)
        j = i + 1
        s[i], s[j] = s[j], s[i]
        f = first_failure(s)
        if f and f[1] == "empty" and f[0] >= 4:
            return s
    return None


def make_valid(rng, cfg, seed):
    for _ in range(3000):
        n = rng.randint(*cfg["length"]) // 2
        good = dyck(rng, n)
        if max_depth(good) < 2 or good[:2] == ["n", "b"] and rng.random() < 0.5:
            continue
        a = mutate_totals(rng, dyck(rng, n))
        b = mutate_leftover(rng, dyck(rng, n))
        c = mutate_late(rng, dyck(rng, n)) if cfg["level"] >= 2 else mutate_totals(rng, dyck(rng, n))
        if not (a and b and c):
            continue
        bad = [a, b, c]
        if len({show(x) for x in bad + [good]}) < 4:
            continue
        tags = []
        for x in bad:
            t = []
            if m_totals_only(x):
                t.append("TOTALS_ONLY_MATCHING")
            if m_ignores_leftovers(x):
                t.append("IGNORES_LEFTOVERS")
            if m_checks_start(x):
                t.append("CHECKS_START_ONLY")
            tags.append(sorted(t))
        if not all(tags):
            continue
        if cfg["level"] >= 2 and not any(first_failure(x)[0] >= len(x) - 3 for x in bad):
            continue
        opts = [good] + bad
        order = list(range(4))
        rng.shuffle(order)
        opts = [opts[i] for i in order]
        ans = order.index(0)
        # shortcut: the working belt must not be the only one with an even length
        if [len(o) % 2 for o in opts].count(0) == 1:
            continue
        expl = ["The working belt never runs out of nuts and ends with an empty bucket."] + trace_lines(good)
        for x in bad:
            i, why = first_failure(x)
            expl.append(f"{show_words(x)}: " + ("a bolt comes when the bucket is empty (part " + str(i + 1) + ")."
                                               if why == "empty" else "nuts are left in the bucket at the end."))
        return Problem("conveyor", cfg["level"], "valid", seed, {"belts": [show(o) for o in opts]},
                       PROMPT, "Which belt can Benoit finish without anything going wrong?",
                       [show(o) for o in opts], ans, show(good), "choice",
                       [{"option": show(x), "misconceptions": t} for x, t in zip(bad, tags)], {},
                       ["STACK_MATCHING", "STATE"], expl,
                       ["Pretend to be Benoit. How many nuts are in the bucket after each part?",
                        "If the count ever goes below zero, a bolt came too early.",
                        "The count must also end at zero."],
                       {"length": len(good)})
    raise RuntimeError("valid generation failed")


def show_words(belt):
    return "".join(belt).replace("n", "N").replace("b", "B") if all(t in "nb" for t in belt) else "".join(belt)


def make_depth(rng, cfg, seed):
    for _ in range(3000):
        n = rng.randint(*cfg["length"]) // 2
        belt = dyck(rng, n)
        truth = max_depth(belt)
        vals = {}
        for tag, f in (("TOTAL_NUTS_FOR_DEPTH", m_total_nuts), ("LONGEST_RUN_FOR_DEPTH", m_longest_run)):
            v = f(belt)
            if v != truth and v > 0:
                vals.setdefault(v, []).append(tag)
        if "LONGEST_RUN_FOR_DEPTH" not in {t for ts in vals.values() for t in ts}:
            continue
        if truth < 3:
            continue
        cnt = run_counts(belt)
        peak = cnt.index(truth)
        expl = trace_lines(belt) + [f"The highest number is {truth}, after part {peak + 1}."]
        return Problem("conveyor", cfg["level"], "depth", seed, {"belt": show(belt)},
                       PROMPT, "This belt works. What is the most nuts that are ever in the bucket at the same time?",
                       [], -1, truth, "number", [], {str(v): sorted(t) for v, t in vals.items()},
                       ["STACK_MATCHING", "STATE"], expl,
                       ["Bolts take nuts out of the bucket as you go.",
                        "Write the number of nuts in the bucket under every part.",
                        "Which number is the biggest?"],
                       {"length": len(belt), "depth": truth})
    raise RuntimeError("depth generation failed")


def make_stack(rng, cfg, seed):
    for _ in range(5000):
        n = rng.randint(*cfg["length"]) // 2
        good = dyck(rng, n, "nN")
        if len(set(good)) < 4 or not nested_mixed(good):
            continue
        # crossed: sizes balanced separately but bolt meets wrong top nut
        crossed = None
        for _ in range(60):
            s = dyck(rng, n, "nN")
            i = rng.randrange(len(s) - 1)
            if s[i] in "bB" and s[i + 1] in "bB" and s[i] != s[i + 1]:
                s[i], s[i + 1] = s[i + 1], s[i]
                f = first_failure(s)
                if f and f[1] == "size" and m_sizes_separately(s):
                    crossed = s
                    break
        if not crossed:
            continue
        early = None
        for _ in range(60):
            s = dyck(rng, n, "nN")
            i = rng.randrange(1, len(s))
            if s[i] in "bB" and s[i - 1] in "nN":
                s[i - 1], s[i] = s[i], s[i - 1]
                f = first_failure(s)
                if f and f[1] == "empty":
                    early = s
                    break
        leftover = dyck(rng, n, "nN")
        j = max(i for i, t in enumerate(leftover) if t in "bB")
        leftover = leftover[:j] + leftover[j + 1:]
        if not early or first_failure(leftover)[1] != "leftover" or len(set(leftover)) < 3:
            continue
        bad = [crossed, early, leftover]
        tags = [["SIZES_SEPARATELY"], ["TOTALS_ONLY_MATCHING"] if m_totals_only(early) else ["CHECKS_START_ONLY"],
                ["IGNORES_LEFTOVERS"]]
        if len({show(x) for x in bad + [good]}) < 4:
            continue
        opts = [good] + bad
        order = list(range(4))
        rng.shuffle(order)
        opts = [opts[i] for i in order]
        ans = order.index(0)
        expl = ["Only one belt matches every bolt with the nut on top of the pile and ends with an empty bucket."]
        expl += stack_lines(good)
        expl += ["The belt with the sizes crossed is the trap: it has the right number of each size, "
                 "but a bolt meets a nut of the other size on top:"] + stack_lines(crossed)[1:]
        return Problem("conveyor", cfg["level"], "stack", seed, {"belts": [show(o) for o in opts]},
                       PROMPT_STACK, "Which belt can Benoit finish without anything going wrong?",
                       [show(o) for o in opts], ans, show(good), "choice",
                       [{"option": show(x), "misconceptions": t} for x, t in zip(bad, tags)], {},
                       ["STACK_MATCHING", "STATE"], expl,
                       ["Keep a pile of nuts. A new nut goes on top.",
                        "A bolt can only use the nut on top of the pile.",
                        "Having the right number of each size is not enough."],
                       {"length": len(good)})
    raise RuntimeError("stack generation failed")


def make_repair(rng, cfg, seed):
    for _ in range(4000):
        L = rng.randint(*cfg["length"])
        belt = [rng.choice("nb") for _ in range(L)]
        truth = repair_count(belt)
        short = truth - m_shortfall_leftover(belt)
        left = m_shortfall_leftover(belt)
        if short < 1 or left < 1 or truth > 6:
            continue
        vals = {}
        for tag, v in (("DIFFERENCE_FOR_REPAIR", m_difference(belt)), ("SHORTFALL_ONLY", short), ("LEFTOVER_ONLY", left)):
            if v != truth and v > 0:
                vals.setdefault(v, []).append(tag)
        if "DIFFERENCE_FOR_REPAIR" not in {t for ts in vals.values() for t in ts}:
            continue
        expl = ["Run the count. When a bolt finds the bucket empty, Benoit needs one extra nut there; when the belt ends, every nut left needs a bolt. (N = nut, B = bolt, +1 = add a nut here.)"]
        c, ln = 0, []
        for t in belt:
            if t == "n":
                c += 1
                ln.append(f"{c}")
            elif c == 0:
                ln.append("+1")
            else:
                c -= 1
                ln.append(f"{c}")
        expl.append("  " + " ".join(f"{('N' if t == 'n' else 'B'):>2}" for t in belt))
        expl.append("  " + " ".join(f"{x:>2}" for x in ln))
        expl.append(f"{short} bolt(s) came with an empty bucket and {left} nut(s) are left at the end: {short} + {left} = {truth} parts.")
        return Problem("conveyor", cfg["level"], "repair", seed, {"belt": show(belt)},
                       PROMPT, "Benoit may add parts anywhere on the belt. What is the fewest parts he must add so nothing goes wrong?",
                       [], -1, truth, "number", [], {str(v): sorted(t) for v, t in vals.items()},
                       ["STACK_MATCHING", "STATE"], expl,
                       ["Run the bucket count. Where does it go below zero?",
                        "Each time a bolt finds the bucket empty, one nut must be added before it.",
                        "Then count the nuts left at the end: each needs a bolt."],
                       {"length": L, "short": short, "left": left})
    raise RuntimeError("repair generation failed")


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    rng = random.Random(seed)
    return {"valid": make_valid, "depth": make_depth, "stack": make_stack, "repair": make_repair}[cfg["question"]](rng, cfg, seed)


if __name__ == "__main__":
    import sys
    print(json.dumps(asdict(generate(int(sys.argv[1]), int(sys.argv[2]))), indent=1))

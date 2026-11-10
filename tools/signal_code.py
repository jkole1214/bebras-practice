"""
Problem family: signal_code (counting the readings of an ambiguous code).

Concept targets: AMBIGUOUS_CODES, COUNTING_DP, ENCODING_CIPHER.
Source task: Hard Fireworks / Fireworks (Junior C, Senior B), 2015.

Scenario (original): a ship's lamp sends words as short and long flashes,
with no pause between words. Some codes start with other codes, so one
signal can mean more than one message.

Scene model: a codebook {word: code} over the symbols S (short) and L (long),
plus a signal. Prompt, answer, options, explanation and hints all come from
this model.

Question types:
  decode   one reading only (prefix-free code); which message was sent?
  count    how many different messages could this signal be?
  inverse  which of these signals has exactly k meanings?
"""

import json
import random
from dataclasses import dataclass, field, asdict
from functools import lru_cache

SYM = {"S": "●", "L": "▬"}        # short = dot, long = bar
WORD_POOL = ["dock", "sail", "storm", "east", "west", "home", "help", "fog",
             "north", "south", "wait", "fish", "rope", "tide", "wind", "port"]


# --------------------------------------------------------------------------
# Solvers
# --------------------------------------------------------------------------

def readings(code, signal, limit=5000):
    """All word sequences whose codes concatenate to the signal."""
    items = sorted(code.items())
    out = []

    def go(i, acc):
        if len(out) >= limit:
            return
        if i == len(signal):
            out.append(tuple(acc))
            return
        for w, c in items:
            if signal.startswith(c, i):
                acc.append(w)
                go(i + len(c), acc)
                acc.pop()
    go(0, [])
    return out


def count_table(code, signal, exclude=()):
    """ways[i] = number of ways to read the first i symbols (the DP)."""
    ways = [0] * (len(signal) + 1)
    ways[0] = 1
    for i in range(1, len(signal) + 1):
        for w, c in code.items():
            if w in exclude:
                continue
            j = i - len(c)
            if j >= 0 and signal[j:i] == c:
                ways[i] += ways[j]
    return ways


def true_count(code, signal):
    return count_table(code, signal)[-1]


# Misconception solvers: each returns the number a student with that habit
# would give, or None if the habit gives no answer.

def m_first_parse(code, signal):
    """Reads the signal one way and stops: answer is 1 if any reading exists."""
    return 1 if true_count(code, signal) else None


def m_misses_short(code, signal):
    """Never considers the shortest word(s)."""
    shortest = min(len(c) for c in code.values())
    excl = {w for w, c in code.items() if len(c) == shortest}
    return count_table(code, signal, exclude=excl)[-1]


def m_counts_dead_ends(code, signal):
    """Counts every reading attempt, including ones that get stuck."""
    @lru_cache(None)
    def leaves(i):
        if i == len(signal):
            return 1
        kids = [i + len(c) for c in code.values() if signal.startswith(c, i)]
        if not kids:
            return 1          # stuck: a dead end still counted as an attempt
        return sum(leaves(k) for k in kids)
    return leaves(0)


def m_counts_word_sets(code, signal):
    """Treats readings with the same words in a different order as one."""
    return len({tuple(sorted(r)) for r in readings(code, signal)})


COUNT_MISCONCEPTIONS = {
    "FIRST_PARSE_ONLY": m_first_parse,
    "MISSES_SHORT_WORD": m_misses_short,
    "COUNTS_DEAD_ENDS": m_counts_dead_ends,
    "COUNTS_WORD_SETS": m_counts_word_sets,
}

MISCONCEPTIONS = {
    "FIRST_PARSE_ONLY": {"concept": "AMBIGUOUS_CODES",
        "description": "Finds one way to read the signal and assumes it is the only one.",
        "remediation": "Ask for a second reading that starts with a different first word."},
    "MISSES_SHORT_WORD": {"concept": "AMBIGUOUS_CODES",
        "description": "Never tries the shortest code word, so misses every reading that uses it.",
        "remediation": "At each point in the signal, have the student check every code word, shortest first."},
    "COUNTS_DEAD_ENDS": {"concept": "COUNTING_DP",
        "description": "Counts every reading attempt, including ones that get stuck before the end.",
        "remediation": "Ask: does this reading use up the whole signal? Only complete readings count."},
    "COUNTS_WORD_SETS": {"concept": "COUNTING_DP",
        "description": "Treats two messages with the same words in a different order as the same message.",
        "remediation": "Ask whether 'east, fog' and 'fog, east' mean the same thing to the sailor."},
    "ORDER_SWAP": {"concept": "ENCODING_CIPHER",
        "description": "Decodes the right words but puts them in the wrong order.",
        "remediation": "Have the student mark where each word starts in the signal, left to right."},
    "MISREAD_SYMBOL": {"concept": "ENCODING_CIPHER",
        "description": "Misreads one flash (short for long or the reverse) while decoding.",
        "remediation": "Have the student write the signal as S and L letters before decoding."},
    "DROPS_WORD": {"concept": "ENCODING_CIPHER",
        "description": "Loses their place and skips a word.",
        "remediation": "Have the student encode their answer back into flashes and compare lengths."},
}


# --------------------------------------------------------------------------
# Codebooks
# --------------------------------------------------------------------------

def is_prefix_free(code):
    cs = list(code.values())
    return not any(a != b and b.startswith(a) for a in cs for b in cs)


def prefix_pairs(code):
    cs = list(code.values())
    return sum(1 for a in cs for b in cs if a != b and b.startswith(a))


def random_codebook(rng, n_words, lengths, prefix_free):
    for _ in range(2000):
        words = rng.sample(WORD_POOL, n_words)
        codes = set()
        while len(codes) < n_words:
            L = rng.choice(lengths)
            codes.add("".join(rng.choice("SL") for _ in range(L)))
        code = dict(zip(words, sorted(codes, key=lambda c: (len(c), c))))
        # every word must actually be usable in some signal: trivially true
        if prefix_free != is_prefix_free(code):
            continue
        return code
    return None


def encode(code, msg):
    return "".join(code[w] for w in msg)


def show(signal):
    return " ".join(SYM[s] for s in signal)


# --------------------------------------------------------------------------
# Ladder
# --------------------------------------------------------------------------

LADDER = [
    {"level": 1, "question": "decode", "words": 5, "lengths": [2, 3, 3, 4], "prefix_free": True,
     "msg_words": (3, 4), "note": "Learn the code: only one reading is possible. Which message was sent?"},
    {"level": 2, "question": "count", "words": 5, "lengths": [1, 2, 3], "prefix_free": False,
     "msg_words": (3, 4), "target": (2, 3), "entry": "choice",
     "note": "Count the readings of a short signal; two or three are possible."},
    {"level": 3, "question": "count", "words": 5, "lengths": [1, 2, 3], "prefix_free": False,
     "msg_words": (4, 5), "target": (3, 6), "entry": "number",
     "note": "Longer signal, type the number. Matches the 2015 Junior task."},
    {"level": 4, "question": "count", "words": 6, "lengths": [1, 2, 2, 3], "prefix_free": False,
     "msg_words": (5, 7), "target": (6, 14), "min_prefix_pairs": 3, "entry": "number",
     "note": "Many codes start with other codes; too many readings to list easily, so keep running counts."},
    {"level": 5, "question": "inverse", "words": 5, "lengths": [1, 2, 3], "prefix_free": False,
     "msg_words": (3, 5), "target": (3, 5),
     "note": "Reverse question: which of four signals has exactly the given number of meanings?"},
]


@dataclass
class Problem:
    family: str
    level: int
    question_type: str
    seed: int
    scene: dict
    prompt: str
    question: str
    codebook: list
    signal: str
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


PROMPT_HEAD = ("A ship's lamp sends words as short flashes (●) and long flashes (▬), "
               "one word after another with no pause between words. The crew use this code:")


def codebook_rows(code):
    return [[w, c] for w, c in sorted(code.items(), key=lambda x: (len(x[1]), x[1]))]


def dp_explanation(code, signal):
    ways = count_table(code, signal)
    rs = readings(code, signal)
    lines = ["Count the ways to read the signal one flash at a time. Under each position, write how many ways "
             "there are to read everything up to there: add the counts from every code word that could end there."]
    lines.append("Running counts after each flash: " + ", ".join(str(w) for w in ways[1:]) + ".")
    lines.append(f"So the whole signal has {ways[-1]} reading{'s' if ways[-1] != 1 else ''}.")
    if len(rs) <= 8:
        for r in rs:
            lines.append("  " + ", ".join(r))
    return lines


def count_hints(cfg, code):
    h = ["Does any code word begin with another code word? That is where a signal can split two ways."]
    h.append("Start at the first flash. Which words could the message start with? Try each one.")
    if cfg["level"] >= 3:
        h.append("Instead of listing every reading, write under each flash how many ways reach it.")
    h.append("Only count readings that use up the whole signal.")
    return h


def make_decode(rng, cfg, seed):
    for _ in range(500):
        code = random_codebook(rng, cfg["words"], cfg["lengths"], True)
        if not code:
            continue
        n = rng.randint(*cfg["msg_words"])
        msg = [rng.choice(list(code)) for _ in range(n)]
        if len(set(msg)) < 3:
            continue
        sig = encode(code, msg)
        wrong = {}
        # order swap of two adjacent different words
        for i in range(n - 1):
            if msg[i] != msg[i + 1]:
                s = msg[:]
                s[i], s[i + 1] = s[i + 1], s[i]
                wrong.setdefault(tuple(s), "ORDER_SWAP")
                break
        # misread one flash: decode a one-symbol-off signal that still decodes
        for i in rng.sample(range(len(sig)), len(sig)):
            alt = sig[:i] + ("L" if sig[i] == "S" else "S") + sig[i + 1:]
            r = readings(code, alt)
            if len(r) == 1 and r[0] != tuple(msg):
                wrong.setdefault(r[0], "MISREAD_SYMBOL")
                break
        # drop a word
        j = rng.randrange(n)
        dropped = tuple(msg[:j] + msg[j + 1:])
        wrong.setdefault(dropped, "DROPS_WORD")
        wrong.pop(tuple(msg), None)
        if len(wrong) < 3:
            continue
        opts = [tuple(msg)] + list(wrong)[:3]
        order = list(range(len(opts)))
        rng.shuffle(order)
        opts = [opts[i] for i in order]
        ans = order.index(0)
        return Problem(
            family="signal_code", level=cfg["level"], question_type="decode", seed=seed,
            scene={"code": code, "signal": sig},
            prompt=PROMPT_HEAD, question="Which message did the lamp send?",
            codebook=codebook_rows(code), signal=sig,
            options=[", ".join(o) for o in opts], answer_index=ans, answer_value=", ".join(msg),
            entry="choice",
            distractors=[{"option": ", ".join(o), "misconceptions": [wrong[o]]} for o in opts if o != tuple(msg)],
            value_tags={},
            concepts=["ENCODING_CIPHER", "AMBIGUOUS_CODES"],
            explanation=["No code word begins with another, so there is only one way to read the signal.",
                         "Split it from the left: " + " | ".join(f"{show(code[w])} = {w}" for w in msg) + "."],
            hints=["Find the first code word that matches the start of the signal.",
                   "Write the signal as letters (S and L) and mark where each word ends.",
                   "Check your answer by turning it back into flashes."],
            knobs={k: cfg[k] for k in ("words", "lengths", "prefix_free")},
        )
    raise RuntimeError("decode generation failed")


def count_values(code, sig):
    truth = true_count(code, sig)
    vals = {}
    for k, f in COUNT_MISCONCEPTIONS.items():
        v = f(code, sig)
        if v is not None and v != truth:
            vals.setdefault(v, []).append(k)
    return truth, vals


def make_count(rng, cfg, seed):
    lo, hi = cfg["target"]
    for _ in range(4000):
        code = random_codebook(rng, cfg["words"], cfg["lengths"], False)
        if not code or prefix_pairs(code) < cfg.get("min_prefix_pairs", 1):
            continue
        n = rng.randint(*cfg["msg_words"])
        msg = [rng.choice(list(code)) for _ in range(n)]
        sig = encode(code, msg)
        truth, vals = count_values(code, sig)
        if not (lo <= truth <= hi):
            continue
        # every listed misconception must give a distinct wrong value
        need = {"FIRST_PARSE_ONLY", "COUNTS_DEAD_ENDS"}
        tagged = {k for ks in vals.values() for k in ks}
        if not need <= tagged:
            continue
        if cfg["entry"] == "choice":
            under = [v for v in vals if v < truth]
            over = [v for v in vals if v > truth]
            if not under or not over:
                continue
            chosen = {1, min(over)}
            rest = [v for v in vals if v not in chosen]
            if rest:
                chosen.add(rng.choice(rest))
            opts = sorted(chosen | {truth})
            if len(opts) < 3 or opts[0] == truth or opts[-1] == truth:
                continue
            ans = opts.index(truth)
            distractors = [{"option": v, "misconceptions": sorted(vals[v])} for v in opts if v != truth]
        else:
            opts, ans, distractors = [], -1, []
        return Problem(
            family="signal_code", level=cfg["level"], question_type="count", seed=seed,
            scene={"code": code, "signal": sig},
            prompt=PROMPT_HEAD, question="How many different messages could this signal mean?",
            codebook=codebook_rows(code), signal=sig,
            options=opts, answer_index=ans, answer_value=truth, entry=cfg["entry"],
            distractors=distractors,
            value_tags={str(v): sorted(ks) for v, ks in vals.items()},
            concepts=["AMBIGUOUS_CODES", "COUNTING_DP"],
            explanation=dp_explanation(code, sig),
            hints=count_hints(cfg, code),
            knobs={"words": cfg["words"], "signal_length": len(sig), "prefix_pairs": prefix_pairs(code)},
        )
    raise RuntimeError(f"count generation failed at level {cfg['level']}")


def make_inverse(rng, cfg, seed):
    lo, hi = cfg["target"]
    for _ in range(4000):
        code = random_codebook(rng, cfg["words"], cfg["lengths"], False)
        if not code or prefix_pairs(code) < 2:
            continue
        k = rng.randint(lo, hi)
        pool = {}
        for _ in range(300):
            n = rng.randint(*cfg["msg_words"])
            sig = encode(code, [rng.choice(list(code)) for _ in range(n)])
            if 5 <= len(sig) <= 10:
                pool[sig] = true_count(code, sig)
        right = [s for s, c in pool.items() if c == k]
        if not right:
            continue
        tagged = {}
        for s, c in pool.items():
            if c == k:
                continue
            tags = sorted(m for m, f in COUNT_MISCONCEPTIONS.items()
                          if m != "FIRST_PARSE_ONLY" and f(code, s) == k)
            if tags:
                tagged[s] = tags
        if len(tagged) < 3:
            continue
        correct = rng.choice(right)
        # spread distractors over misconceptions, prefer single-tag ones
        picks, used = [], set()
        for s in sorted(tagged, key=lambda s: (len(tagged[s]), rng.random())):
            if tagged[s][0] not in used or len(picks) + (3 - len(used)) < 3:
                picks.append(s)
                used.update(tagged[s])
            if len(picks) == 3:
                break
        if len(picks) < 3:
            continue
        opts = [correct] + picks
        lens = [len(s) for s in opts]
        if lens.count(max(lens)) == 1 and lens.index(max(lens)) == 0:
            continue           # shortcut: longest signal must not be the answer
        order = list(range(4))
        rng.shuffle(order)
        opts = [opts[i] for i in order]
        ans = order.index(0)
        return Problem(
            family="signal_code", level=cfg["level"], question_type="inverse", seed=seed,
            scene={"code": code, "target": k},
            prompt=PROMPT_HEAD, question=f"Which of these signals could mean exactly {k} different messages?",
            codebook=codebook_rows(code), signal="",
            options=opts, answer_index=ans, answer_value=correct, entry="choice",
            distractors=[{"option": s, "meanings": pool[s], "misconceptions": tagged[s]} for s in opts if s != correct],
            value_tags={},
            concepts=["AMBIGUOUS_CODES", "COUNTING_DP"],
            explanation=[f"Count the readings of each signal. Only {show(correct)} has exactly {k}."]
                        + dp_explanation(code, correct)[1:]
                        + [f"The others have {', '.join(str(pool[s]) for s in opts if s != correct)}."],
            hints=["Count the readings of each signal separately.",
                   "Write a running count under each flash for each signal.",
                   "Only complete readings count, and order matters."],
            knobs={"words": cfg["words"], "target": k},
        )
    raise RuntimeError("inverse generation failed")


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    rng = random.Random(seed)
    return {"decode": make_decode, "count": make_count, "inverse": make_inverse}[cfg["question"]](rng, cfg, seed)


if __name__ == "__main__":
    import sys
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print(json.dumps(asdict(generate(lvl, seed)), indent=2, ensure_ascii=False))

"""
Independent checker for bead_grammar problems. Does not import the generator.

Decides membership by working BACKWARD from each option (undoing rules),
which is a different algorithm from the generator's forward search, and
re-derives the misreading tags by checking membership under the relaxed
rules. Counts are redone by forward enumeration with its own code.
"""

import itertools
import json
import sys
from functools import lru_cache


def neck_member(start, rules, s, view=None):
    @lru_cache(None)
    def ok(t):
        if t == start:
            return True
        if len(t) <= len(start):
            return False
        for k, x in rules:
            n = len(x)
            ends = []
            if k == "R" or (k == "L" and view == "WRONG_END"):
                ends.append("R")
            if k == "L" or (k == "R" and view == "WRONG_END"):
                ends.append("L")
            for e in ends:
                if e == "R" and t.endswith(x) and ok(t[:-n]):
                    return True
                if e == "L" and t.startswith(x) and ok(t[n:]):
                    return True
            if k == "W":
                if len(t) >= 2 + len(start) and t[0] == x and t[-1] == x and ok(t[1:-1]):
                    return True
                if view == "WRAP_ONE_END" and (t.endswith(x * 2) and ok(t[:-2]) or t.startswith(x * 2) and ok(t[2:])):
                    return True
        return False
    return ok(s)


def wiz_member(start, rules, s, view=None):
    """Backward: replace any occurrence of a rule's right side by its left side."""
    @lru_cache(None)
    def ok(t):
        if t == start:
            return True
        for lhs, rhs in rules:
            rs = {rhs} if view != "ORDER" else {"".join(p) for p in itertools.permutations(rhs)}
            ls = {lhs} if view != "ANY" else {"X", "Y"}
            for r in rs:
                i = t.find(r)
                while i != -1:
                    for l in ls:
                        u = t[:i] + l + t[i + len(r):]
                        if len(u) < len(t) or (len(u) == len(t) and u < t):
                            if ok(u):
                                return True
                    i = t.find(r, i + 1)
        return False
    if any(len(r) == 1 for _, r in rules):
        # a rule of length 1 keeps the length the same; guard against cycles by depth
        return _wiz_forward(start, rules, s, view)
    return ok(s)


def _wiz_forward(start, rules, s, view):
    seen, todo = {start}, [start]
    while todo:
        t = todo.pop()
        if t == s:
            return True
        for i, ch in enumerate(t):
            for lhs, rhs in rules:
                if lhs != ch and not (view == "ANY" and ch in "XY"):
                    continue
                for r in ({rhs} if view != "ORDER" else {"".join(p) for p in itertools.permutations(rhs)}):
                    u = t[:i] + r + t[i + 1:]
                    if len(u) <= len(s) and u not in seen:
                        seen.add(u)
                        todo.append(u)
    return False


def check(p):
    errs = []
    sc = p["scene"]
    rules = [tuple(r) for r in sc["rules"]]
    if sc["kind"] == "necklace":
        member = lambda s, v=None: neck_member(sc["start"], rules, s, v)
        views = {"GRAMMAR_WRONG_END": "WRONG_END", "WRAP_ONE_END": "WRAP_ONE_END"}
    else:
        member = lambda s, v=None: wiz_member(sc["start"], rules, s, v)
        views = {"GRAMMAR_ORDER_IGNORED": "ORDER", "GRAMMAR_ANY_OBJECT": "ANY"}
    qt = p["question_type"]
    if qt in ("can", "cannot"):
        o = p["options"]
        if len(set(o)) != 4:
            errs.append("need 4 distinct options")
        ins = [member(s) for s in o]
        want = [s for s, m in zip(o, ins) if m == (qt == "can")]
        if len(want) != 1 or o[p["answer_index"]] != want[0]:
            errs.append(f"{qt}: options in the language {ins}; key {p['answer_index']}")
        for d in p["distractors"]:
            if not d["misconceptions"]:
                errs.append("untagged distractor")
            for t in d["misconceptions"]:
                if t in views and not member(d["option"], views[t]):
                    errs.append(f"{d['option']} tagged {t} but not buildable under that reading")
        if qt == "cannot" and not any(member(p["answer_value"], v) for v in views.values()):
            errs.append("the impossible necklace is not even a plausible misreading")
    elif qt == "count":
        L = sc["length"]
        cols = sorted(set(sc["start"] + "".join(x for _, x in rules)))
        n = sum(1 for t in itertools.product(cols, repeat=L) if member("".join(t)))
        if n != p["answer_value"]:
            errs.append(f"count {p['answer_value']} != {n}")
        if str(n) in p["value_tags"]:
            errs.append("a misconception value equals the answer")
    else:
        errs.append("unknown question type")
    if not p["explanation"] or not p["hints"]:
        errs.append("missing explanation or hints")
    return errs


if __name__ == "__main__":
    probs = json.load(open(sys.argv[1]))
    bad = 0
    for p in probs:
        e = check(p)
        if e:
            bad += 1
            print(p["level"], p["seed"], e[:3])
    print(f"{len(probs) - bad}/{len(probs)} problems pass")

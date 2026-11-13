"""
Independent checker for gossip_rounds (Map Pieces) problems.

Does not import the generator. It rebuilds the friends, their pieces, the links and the meeting
plan from the SVG picture, checks them against the scene and the prompt, then solves again with
its own code: pieces are bitmasks, plans are replayed meeting by meeting, and the fewest rounds
come from a depth-first search that cuts any branch where the biggest pile, or the friends holding
some piece, could not reach everyone even by doubling in every remaining round. The plan printed in the explanation is replayed too.
Wrong answers' tags are re-derived from its own versions of each mistake.

Usage: python3 check_gossip_rounds.py L1-1000.js [...]   (files from map-pieces/)
"""

import json
import re
import sys
import xml.etree.ElementTree as ET

NS = "{http://www.w3.org/2000/svg}"


def parse(svg):
    root = ET.fromstring(svg)
    friends, links, rounds, errs = [], [], {}, []
    for g in root.iter(NS + "g"):
        cls = (g.get("class") or "").split()
        if "friend" in cls:
            name = g.get("data-name")
            texts = [t.text for t in g.iter(NS + "text")]
            if g.get("data-piece") != name[:1] or texts != [name, name[:1]]:
                errs.append(f"friend {name} is drawn with the wrong labels")
            friends.append((name, "ask" in cls))
        elif "round" in cls:
            rounds[int(g.get("data-r"))] = [(m.get("data-a"), m.get("data-b"))
                                            for m in g.iter(NS + "g") if "meet" in (m.get("class") or "")]
    for ln in root.iter(NS + "line"):
        if "link" in (ln.get("class") or ""):
            links.append((ln.get("data-a"), ln.get("data-b")))
    return friends, links, [rounds[k] for k in sorted(rounds)], errs


def masks(names, rounds):
    ix = {x: i for i, x in enumerate(names)}
    k = [1 << i for i in range(len(names))]
    for r in rounds:
        nk = k[:]
        for a, b in r:
            nk[ix[a]] = nk[ix[b]] = k[ix[a]] | k[ix[b]]
        k = nk
    return {x: k[ix[x]] for x in names}


def bits(v):
    return bin(v).count("1")


def trace_values(names, rounds, x, truth):
    out = {}
    partners = {a if b == x else b for r in rounds for a, b in r if x in (a, b)}
    out["PARTNERS_OWN_PIECE_ONLY"] = 1 + len(partners)
    out["LEAVES_OUT_OWN_PIECE"] = truth - 1
    # every meeting at once: flood fill over all meetings, ignoring time
    group = {x}
    changed = True
    while changed:
        changed = False
        for r in rounds:
            for a, b in r:
                if (a in group) != (b in group):
                    group |= {a, b}
                    changed = True
    out["IGNORES_ROUND_ORDER"] = len(group)
    cnt = dict.fromkeys(names, 1)
    for r in rounds:
        nc = dict(cnt)
        for a, b in r:
            nc[a] = nc[b] = cnt[a] + cnt[b]
        cnt = nc
    out["COUNTS_SHARED_PIECES_TWICE"] = cnt[x]
    return out


def tag_map(vals, truth):
    m = {}
    for t, v in vals.items():
        if v != truth:
            m.setdefault(v, set()).add(t)
    return m


def meetings(n, adj):
    """Every maximal set of meetings (no two free friends joined by a link are left apart)."""
    out = []

    def rec(i, used, cur):
        if i == n:
            if all(used >> a & 1 or used >> b & 1 for a in range(n) for b in adj[a]):
                out.append(cur)
            return
        if used >> i & 1:
            rec(i + 1, used, cur)
            return
        rec(i + 1, used, cur)
        for j in adj[i]:
            if j > i and not used >> j & 1:
                rec(i + 1, used | 1 << i | 1 << j, cur + [(i, j)])
    rec(0, 0, [])
    return out


def can_finish(n, adj, rounds):
    full = (1 << n) - 1
    ms = meetings(n, adj)
    dead = set()

    def go(state, left):
        if all(k == full for k in state):
            return True
        # a meeting joins two piles, so the biggest pile, and the number of friends holding any one
        # piece, can at most double each round
        if left == 0 or max(bits(k) for k in state) << left < n or (state, left) in dead:
            return False
        if min(sum(k >> i & 1 for k in state) for i in range(n)) << left < n:
            return False
        for m in ms:
            k = list(state)
            for a, b in m:
                k[a] = k[b] = state[a] | state[b]
            if go(tuple(k), left - 1):
                return True
        dead.add((state, left))
        return False
    return go(tuple(1 << i for i in range(n)), rounds)


def far(n, adj):
    d = [[0 if i == j else 99 for j in range(n)] for i in range(n)]
    for a in range(n):
        for b in adj[a]:
            d[a][b] = 1
    for k in range(n):
        for i in range(n):
            for j in range(n):
                d[i][j] = min(d[i][j], d[i][k] + d[k][j])
    return max(max(r) for r in d)


def first_plan(n, pairs):
    """A greedy plan: each round, repeatedly pair the two free linked friends who gain the most."""
    have = [1 << i for i in range(n)]
    full = (1 << n) - 1
    for r in range(1, 13):
        free = set(range(n))
        new = have[:]
        while True:
            gains = [(2 * bits(have[a] | have[b]) - bits(have[a]) - bits(have[b]), -pairs.index((a, b)), a, b)
                     for a, b in pairs if a in free and b in free]
            gains = [g for g in gains if g[0] > 0]
            if not gains:
                break
            _, _, a, b = max(gains)
            free -= {a, b}
            new[a] = new[b] = have[a] | have[b]
        if new == have:
            return None
        have = new
        if all(k == full for k in have):
            return r
    return None


def ceil_log2(n):
    k = 0
    while 1 << k < n:
        k += 1
    return k


def check_choice_numbers(p, truth, want, errs, cap=None):
    o = p["options"]
    if p["entry"] != "choice" or o[p["answer_index"]] != truth or o.count(truth) != 1 or len(o) < 3:
        errs.append("marked option is not the recomputed answer")
    if truth in (min(o), max(o)):
        errs.append("the right answer is the smallest or largest option (guessable)")
    if cap and max(o) > cap:
        errs.append("an option is more pieces than exist")
    got = {x["option"]: x["misconceptions"] for x in p["distractors"]}
    if sorted(got) != sorted(x for x in o if x != truth):
        errs.append("every wrong option needs tags")
    for x, t in got.items():
        if not t or set(t) != want.get(x, set()):
            errs.append(f"option {x} tagged {t}, recomputed {sorted(want.get(x, []))}")


def check_typed(p, truth, want, errs):
    if p["entry"] != "number" or p["options"] or p["answer_value"] != truth:
        errs.append("typed answer is not the recomputed answer")
    got = {int(k): set(v) for k, v in p["value_tags"].items()}
    if got != {v: t for v, t in want.items() if v >= 0}:
        errs.append(f"value_tags {p['value_tags']} differ from recomputed {want}")


def check(p):
    friends, links, rounds, errs = parse(p["svg"])
    sc = p["scene"]
    names = [f for f, _ in friends]
    n = len(names)
    if names != sc["people"] or len(set(n[:1] for n in names)) != n:
        return errs + ["friends differ from the scene, or two share a letter"]
    ask = [f for f, a in friends if a]
    if ask != ([sc["ask"]] if sc["ask"] else []):
        errs.append("the highlighted friend is not the one asked about")
    if [list(m) for m in links] != sc["links"] or [[list(m) for m in r] for r in rounds] != sc["rounds"]:
        errs.append("links or meeting plan differ from the scene")
    for r in rounds:
        used = [x for m in r for x in m]
        if len(set(used)) != len(used) or not set(used) <= set(names):
            errs.append("someone meets twice in one round")
    pr = p["prompt"]
    for s in ("meets at most one other friend", "copy each other's pieces", "first letter of their name"):
        if s not in pr:
            errs.append("prompt does not state the rule")
    q = p["question_type"]
    if (q == "fewest") != ("joined by a line" in pr):
        errs.append("prompt and links disagree")

    if q == "trace":
        x = sc["ask"]
        have = masks(names, rounds)
        truth = bits(have[x])
        if p["answer_value"] != truth:
            errs.append("answer differs from the replayed plan")
        if not 2 < truth < n:
            errs.append("the count is trivial (everything or almost nothing)")
        vals = trace_values(names, rounds, x, truth)
        if vals["PARTNERS_OWN_PIECE_ONLY"] == truth:
            errs.append("counting only partners' own pieces gives the right answer")
        want = tag_map(vals, truth)
        if p["entry"] == "choice":
            check_choice_numbers(p, truth, want, errs, cap=n)
        else:
            check_typed(p, truth, want, errs)
        if f"After round {len(rounds)}, how many map pieces does {x} have?" not in p["question"]:
            errs.append("question does not match the plan")
        if not p["explanation"][-1].startswith(f"So after round {len(rounds)}, {x} has ") or \
                not p["explanation"][-1].endswith(f": {truth} piece{'s' if truth != 1 else ''}."):
            errs.append("the explanation does not end with the answer")

    elif q == "finish":
        have = masks(names, rounds)
        full = (1 << n) - 1
        met = {frozenset(m) for r in rounds for m in r}
        o = [[tuple(m) for m in opt] for opt in p["options"]]
        works = [all(have[a] | have[b] == full for a, b in m) for m in o]
        if p["entry"] != "choice" or works.count(True) != 1 or not works[p["answer_index"]] or len(o) < 3:
            errs.append("exactly one option must give everyone every piece, and it must be the marked one")
        if [list(m) for m in o[p["answer_index"]]] != p["answer_value"]:
            errs.append("answer_value differs from the marked option")
        for m in o:
            used = [x for pr_ in m for x in pr_]
            if sorted(used) != sorted(names):
                errs.append("an option does not pair every friend exactly once")
        if not any(frozenset(m) in met for m in o[p["answer_index"]]):
            errs.append("the right round meets only new faces, so that trap would be right")
        got = {json.dumps(x["option"]): set(x["misconceptions"]) for x in p["distractors"]}
        for i, m in enumerate(o):
            if i == p["answer_index"]:
                continue
            want = set()
            if all(frozenset(pr_) not in met for pr_ in m):
                want.add("NEW_FACES_FIRST")
            if any(have[a] == have[b] for a, b in m):
                want.add("WASTED_MEETING")
            g = got.get(json.dumps(p["options"][i]))
            if not want or g != want:
                errs.append(f"option {i} tagged {g}, recomputed {sorted(want)}")
        if len(got) != len(o) - 1:
            errs.append("every wrong option needs tags")
        if not any("NEW_FACES_FIRST" in t for t in got.values()):
            errs.append("no new-faces trap among the options")
        if not p["explanation"][-1].startswith("So round 3 should be "):
            errs.append("the explanation does not end with the answer")

    elif q == "fewest":
        ix = {x: i for i, x in enumerate(names)}
        adj = {i: set() for i in range(n)}
        pairs = []
        for a, b in links:
            adj[ix[a]].add(ix[b])
            adj[ix[b]].add(ix[a])
            pairs.append((ix[a], ix[b]))
        d = far(n, adj)
        if d >= 99:
            return errs + ["not every friend can be reached"]
        truth = p["answer_value"]
        if not can_finish(n, adj, truth):
            errs.append(f"no plan finishes in {truth} rounds")
        if can_finish(n, adj, truth - 1):
            errs.append(f"a plan finishes in {truth - 1} rounds")
        quick = ceil_log2(n) + n % 2
        if truth <= quick or truth <= d or truth >= n - 1:
            errs.append("a quick bound or the one-piece count already gives the answer")
        vals = {"IGNORES_LINKS": quick, "FARTHEST_PAIR_ONLY": d, "ONE_PIECE_PER_ROUND": n - 1}
        if n % 2:
            vals["ODD_ONE_OUT_FREE"] = ceil_log2(n)
        g = first_plan(n, pairs)
        if g:
            vals["FIRST_PLAN_IS_BEST"] = g
        want = tag_map(vals, truth)
        if p["entry"] == "choice":
            check_choice_numbers(p, truth, want, errs)
        else:
            check_typed(p, truth, want, errs)
        plan = [ln[:-1] for ln in p["explanation"] if re.match(r"Plan round \d+: .*\.$", ln)]
        rounds_ = []
        for ln in plan:
            body = re.sub(r" \(.*\)$", "", ln.split(": ", 1)[1])
            rounds_.append([tuple(x.split(" & ")) for x in body.split(", ")])
        ok = len(rounds_) == truth
        for r in rounds_:
            used = [x for m in r for x in m]
            if len(set(used)) != len(used) or any(ix.get(b) not in adj.get(ix.get(a), ()) for a, b in r):
                ok = False
        if not ok or any(v != (1 << n) - 1 for v in masks(names, rounds_).values()):
            errs.append("the plan in the explanation does not work")
        if p["explanation"][-1] != f"So the fewest is {truth} rounds.":
            errs.append("the explanation does not end with the answer")
    else:
        errs.append(f"unknown question type {q}")
    return errs


if __name__ == "__main__":
    bad = 0
    for path in sys.argv[1:]:
        text = open(path).read()
        rec = json.loads(text[text.index("{"):text.rindex("}") + 1])
        e = check(rec)
        if e:
            bad += 1
            print(path, e)
    print(f"{len(sys.argv) - 1 - bad} ok, {bad} bad")

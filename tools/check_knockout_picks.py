"""
Independent checker for knockout_picks (Puppy Picks). Does not import the generator.

It rebuilds each problem from the SVG picture and solves it another way:
  who     crosses out every toy left behind in a round (and checks the grabs fit one order of liking)
  fewest  searches over (toys never shown, toys shown and never left behind) for the fewest rounds
  most    the same search, for the most toys the rounds can handle
  mixed   the same, with the round sizes read from the baskets
  plan    tries every toy as the favourite and follows it through each plan
Every habit tag is re-derived the same way, and the explanation's rounds and plans are replayed.

    python3 tools/check_knockout_picks.py        # checks seeds 1000-1039 at every level
"""

import re
import sys
from functools import lru_cache

WIN_FILL = "#ffd166"


def attrs(tag):
    return dict(re.findall(r'([\w-]+)="([^"]*)"', tag))


def svg_root(svg):
    return attrs(re.match(r"<svg [^>]*>", svg).group(0))


def groups(svg, cls):
    """Top-level <g class=cls ...> blocks (no nesting of the same class)."""
    out = []
    for m in re.finditer(rf'<g class="{cls}" ([^>]*)>', svg):
        depth, i = 1, m.end()
        while depth:
            o, c = svg.find("<g ", i), svg.find("</g>", i)
            if o != -1 and o < c:
                depth, i = depth + 1, o + 3
            else:
                depth, i = depth - 1, c + 4
        out.append((attrs(m.group(1)), svg[m.end():i - 4]))
    return out


def tile(body):
    fill = re.search(r'<rect [^>]*fill="([^"]+)"', body).group(1)
    text = re.search(r"<text [^>]*>([^<]*)</text>", body).group(1)
    return fill, text


# --------------------------------------------------------------------------
# Counting by search
# --------------------------------------------------------------------------

def finds(n, sizes):
    """Can these rounds always single out the favourite among n toys? Search over (never shown, still in it)."""
    @lru_cache(maxsize=None)
    def go(u, c, i):
        if u + c == 1:
            return True
        if i == len(sizes):
            return False
        s = sizes[i]
        if go(u, c, i + 1):
            return True
        for a in range(min(c, s) + 1):
            for b in range(min(u, s - a) + 1):
                if a + b >= 2 and go(u - b, c - a + 1, i + 1):
                    return True
        return False
    return go(n, 0, 0)


def most_by_search(sizes):
    best = None
    for n in range(1, sum(sizes) + 3):
        if finds(n, tuple(sizes)):
            best = n
    return best


def fewest_by_search(n, k):
    r = 0
    while not finds(n, tuple([k] * r)):
        r += 1
    return r


def counted_rounds(n, per):
    """Rounds needed if each round must deal with `per` toys that are new."""
    r, left = 0, n
    while left > 0:
        left -= per
        r += 1
    return r


# --------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------

def favourite_reaches_end(rounds, t):
    won = set()
    for i, r in enumerate(rounds):
        if t in r or any(x[0] == "W" and int(x[1:]) in won for x in r):
            won.add(i + 1)
    return len(rounds) in won


def plan_ok(rounds, toys):
    return all(favourite_reaches_end(rounds, t) for t in toys)


def plan_flaw(rounds, toys):
    shown = {x for r in rounds for x in r if x[0] != "W"}
    if set(toys) - shown:
        return "TOY_LEFT_OUT", sorted(set(toys) - shown)
    used = {int(x[1:]) for r in rounds for x in r if x[0] == "W"}
    if not used:
        return "CARRIES_TOY_NOT_WINNER", None
    lost = [j for j in range(1, len(rounds)) if j not in used]
    return ("WINNER_DROPPED", lost) if lost else (None, None)


def replay_lines(lines, start):
    """Parse '  Round i: x y z' lines from position start."""
    rounds = []
    for l in lines[start:]:
        m = re.fullmatch(r"  Round (\d+): (.+)", l)
        if not m:
            break
        if int(m.group(1)) != len(rounds) + 1:
            raise ValueError("explanation rounds out of order")
        rounds.append(m.group(2).split())
    return rounds


def check_knockout(rounds, n, sizes_ok):
    """An explanation plan: each Wj refers back, sizes fit, and it finds the favourite among n toys."""
    toys = [chr(65 + i) for i in range(n)]
    for i, r in enumerate(rounds):
        if not sizes_ok(i, len(r)):
            return False
        for x in r:
            if x[0] == "W" and not 1 <= int(x[1:]) <= i:
                return False
            if x[0] != "W" and x not in toys:
                return False
    return plan_ok(rounds, toys)


# --------------------------------------------------------------------------

def value_tag_map(truth, wrong):
    vt = {}
    for tag, v in wrong.items():
        if v is None:
            continue
        if v == truth or v < 1:
            return None
        vt.setdefault(str(v), set()).add(tag)
    return vt


def check_one(p):
    errs = []
    svg, q, sc = p["svg"], p["question_type"], p["scene"]
    root = svg_root(svg)
    if root.get("data-family") != "knockout_picks":
        return ["wrong family in picture"]
    expl = p["explanation"]

    if q == "who":
        rounds = []
        for a, body in groups(svg, "round"):
            toys = []
            for ta, tb in groups(body, "toy"):
                fill, text = tile(tb)
                if text != ta["data-toy"]:
                    errs.append("toy label differs from data")
                if (fill == WIN_FILL) != (ta["data-grabbed"] == "1"):
                    errs.append("grabbed colour differs from data")
                toys.append((ta["data-toy"], ta["data-grabbed"] == "1"))
            g = [t for t, w in toys if w]
            if len(g) != 1:
                return errs + ["a round without exactly one grab"]
            if f"grabbed {g[0]}<" not in body:
                errs.append("round caption differs from the grab")
            rounds.append({"toys": [t for t, _ in toys], "grabbed": g[0]})
        all_toys = list(root["data-toys"])
        if [{"toys": sorted(r["toys"]), "grabbed": r["grabbed"]} for r in rounds] != sc["rounds"]:
            errs.append("scene differs from picture")
        # the grabs must fit one order of liking: no cycle in "grabbed over"
        over = {t: set() for t in all_toys}
        for r in rounds:
            for t in r["toys"]:
                if t != r["grabbed"]:
                    over[r["grabbed"]].add(t)
        seen, stack = set(), set()

        def cyc(t):
            if t in stack:
                return True
            if t in seen:
                return False
            seen.add(t); stack.add(t)
            bad = any(cyc(x) for x in over[t])
            stack.discard(t)
            return bad
        if any(cyc(t) for t in all_toys):
            errs.append("grabs contradict each other")
        out = {t for r in rounds for t in r["toys"] if t != r["grabbed"]}
        alive = [t for t in all_toys if t not in out]
        if len(alive) != 1:
            return errs + [f"{len(alive)} toys never left behind"]
        fav = alive[0]
        if p["answer_value"] != fav or p["options"][p["answer_index"]] != fav:
            errs.append(f"answer should be {fav}")
        wins = {t: sum(r["grabbed"] == t for r in rounds) for t in all_toys}
        most = [t for t in all_toys if wins[t] == max(wins.values())]
        want = {}
        want.setdefault(rounds[-1]["grabbed"], set()).add("LAST_ROUND_DECIDES")
        want.setdefault(rounds[0]["grabbed"], set()).add("FIRST_ROUND_DECIDES")
        if len(most) == 1:
            want.setdefault(most[0], set()).add("MOST_WINS")
        if fav in want:
            errs.append("a habit gives the right answer")
        got = {d["option"]: set(d["misconceptions"]) for d in p["distractors"]}
        if got != want:
            errs.append(f"distractor tags {got} should be {want}")
        if sorted(p["options"]) != sorted([fav] + list(want)):
            errs.append("options are not the answer plus the tagged toys")
        for i, r in enumerate(rounds):
            line = f"  Round {i + 1}: grabbed {r['grabbed']}, so not {', '.join(t for t in r['toys'] if t != r['grabbed'])}"
            if line not in expl:
                errs.append(f"explanation round {i + 1} is wrong")
        if expl[-2:] != [f"  Never left behind: {fav}", f"So the favourite is {fav}."]:
            errs.append("explanation ending is wrong")

    elif q == "fewest":
        n, k = int(root["data-n"]), int(root["data-k"])
        toys = groups(svg, "toy")
        if len(toys) != n or [tile(b)[1] for _, b in toys] != [chr(65 + i) for i in range(n)]:
            errs.append("toy tiles differ from data-n")
        bs = groups(svg, "basket")
        if len(bs) != 1 or int(bs[0][0]["data-size"]) != k or bs[0][1].count("<rect") - 1 != k:
            errs.append("basket differs from data-k")
        if sc != {"n": n, "k": k}:
            errs.append("scene differs from picture")
        if f"There are {n} toys" not in p["question"] or f"up to {k} toys" not in p["question"]:
            errs.append("question differs from picture")
        truth = fewest_by_search(n, k)
        if p["answer_value"] != truth:
            errs.append(f"answer should be {truth}")
        ruled_all = 0
        while ruled_all * (k - 1) < n:
            ruled_all += 1
        down = 0
        while (down + 1) * (k - 1) <= n - 1:
            down += 1
        wrong = {"WINNER_NOT_CARRIED": counted_rounds(n, k), "FAVOURITE_RULED_OUT": ruled_all,
                 "ROUNDS_DOWN": down if down * (k - 1) != n - 1 else None}
        vt = value_tag_map(truth, wrong)
        if vt is None:
            errs.append("a habit gives the right answer")
        elif {v: set(t) for v, t in p["value_tags"].items()} != vt:
            errs.append(f"value tags should be {vt}")
        rs = replay_lines(expl, next((i for i, l in enumerate(expl) if l.startswith("  Round 1:")), len(expl)))
        if len(rs) != truth or not check_knockout(rs, n, lambda i, s: 2 <= s <= k):
            errs.append("explanation plan does not work")
        if f"  {n - 1} ÷ {k - 1} = {(n - 1) / (k - 1):g}, so at least {truth} rounds" not in expl:
            errs.append("explanation division is wrong")
        if expl[-1] != f"So the fewest is {truth} rounds.":
            errs.append("explanation ending is wrong")

    elif q in ("most", "mixed"):
        bs = groups(svg, "basket")
        sizes = []
        for i, (a, body) in enumerate(bs):
            if int(a["data-round"]) != i + 1 or body.count("<rect") - 1 != int(a["data-size"]):
                errs.append("basket differs from its data")
            sizes.append(int(a["data-size"]))
        if sc != {"sizes": sizes} or int(root["data-q"]) != len(sizes):
            errs.append("scene differs from picture")
        if f"You have {len(sizes)} rounds" not in p["question"]:
            errs.append("question differs from picture")
        if q == "most" and (len(set(sizes)) != 1 or f"up to {sizes[0]} toys" not in p["question"]):
            errs.append("question differs from picture")
        truth = most_by_search(sizes)
        if p["answer_value"] != truth:
            errs.append(f"answer should be {truth}")
        wrong = {"WINNER_NOT_CARRIED": sum(sizes), "FAVOURITE_RULED_OUT": truth - 1}
        if q == "most":
            k, qq = sizes[0], len(sizes)
            wrong["GROUPS_THEN_FINAL"] = (qq - 1) * k if qq - 1 <= k else None
        else:
            wrong["BIGGEST_ROUND_ONLY"] = most_by_search([max(sizes)] * len(sizes))
        vt = value_tag_map(truth, wrong)
        if vt is None:
            errs.append("a habit gives the right answer")
        elif {v: set(t) for v, t in p["value_tags"].items()} != vt:
            errs.append(f"value tags should be {vt}")
        rs = replay_lines(expl, next((i for i, l in enumerate(expl) if l.startswith("  Round 1:")), len(expl)))
        if len(rs) != len(sizes) or not check_knockout(rs, truth, lambda i, s: 2 <= s <= sizes[i]):
            errs.append("explanation plan does not work")
        if q == "most":
            sum_line = f"  {len(sizes)} rounds × {sizes[0] - 1} = {truth - 1} toys left behind at most"
        else:
            sum_line = f"  {' + '.join(f'({s} − 1)' for s in sizes)} = {truth - 1} toys left behind at most"
        if sum_line not in expl:
            errs.append("explanation sum is wrong")
        if expl[-1] != f"So the largest is {truth} toys.":
            errs.append("explanation ending is wrong")

    elif q == "plan":
        n, k, qq = int(root["data-n"]), int(root["data-k"]), int(root["data-q"])
        toys = [chr(65 + i) for i in range(n)]
        plans = []
        for i, (a, body) in enumerate(groups(svg, "plan")):
            if int(a["data-plan"]) != i + 1:
                errs.append("plans out of order")
            rounds = []
            for ra, rb in groups(body, "round"):
                items = []
                for sa, sb in groups(rb, "slot"):
                    if tile(sb)[1] != sa["data-item"]:
                        errs.append("slot label differs from data")
                    items.append(sa["data-item"])
                if not 2 <= len(items) <= k or len(set(items)) != len(items):
                    errs.append("a round has the wrong number of toys")
                rounds.append(items)
            if len(rounds) != qq:
                errs.append("a plan has the wrong number of rounds")
            plans.append(rounds)
        if sc != {"n": n, "k": k, "q": qq, "plans": plans}:
            errs.append("scene differs from picture")
        good = [i for i, pl in enumerate(plans) if plan_ok(pl, toys)]
        if len(good) != 1:
            return errs + [f"{len(good)} plans work"]
        ans = good[0]
        if p["answer_index"] != ans or p["answer_value"] != str(ans + 1) or p["options"] != ["1", "2", "3", "4"]:
            errs.append(f"answer should be plan {ans + 1}")
        got = {d["option"]: d["misconceptions"] for d in p["distractors"]}
        for i, pl in enumerate(plans):
            if i == ans:
                if f"  Plan {i + 1}: every toy is shown, and every winner plays on to round {qq}" not in expl:
                    errs.append("explanation for the right plan is wrong")
                continue
            flaw, what = plan_flaw(pl, toys)
            if got.get(str(i + 1)) != [flaw]:
                errs.append(f"plan {i + 1} should be tagged {flaw}")
            line = {"TOY_LEFT_OUT": f"  Plan {i + 1}: toy {what[0] if what else ''} is never shown",
                    "WINNER_DROPPED": f"  Plan {i + 1}: the winner of round {what[0] if what else ''} never plays again",
                    "CARRIES_TOY_NOT_WINNER": f"  Plan {i + 1}: it carries named toys, not winners, so the winners never meet"}.get(flaw)
            if line not in expl:
                errs.append(f"explanation for plan {i + 1} is wrong")
        if expl[-1] != f"So Plan {ans + 1} always finds the favourite.":
            errs.append("explanation ending is wrong")
    else:
        errs.append(f"unknown question type {q}")
    return errs


def check(p):
    try:
        return check_one(p)
    except Exception as e:      # a corrupted picture must fail, not crash the build
        return [f"checker error: {type(e).__name__}: {e}"]


if __name__ == "__main__":
    sys.path.insert(0, __import__("os").path.dirname(__file__))
    from dataclasses import asdict
    import knockout_picks as G
    bad = 0
    for L in range(1, 6):
        for s in range(1000, 1040):
            e = check(asdict(G.generate(L, s)))
            if e:
                bad += 1
                print(L, s, e)
    print("failures:", bad)

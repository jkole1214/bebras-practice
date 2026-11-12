"""
Findings from the students' own answers, written back to the knowledge map.

Input is the parent export from the progress page (/api/export.json), or the
server's SQLite file. Output is a printed report and a patch file that
merge_patch.py adds to the map as `data_observations` (a snapshot: each merge
replaces the last one). Student names never go into the patch.

    python3 tools/observe.py kerbopple-export.json
    python3 tools/observe.py data/bebras.db
    python3 tools/merge_patch.py tools/bebras_knowledge_map.json tools/observations_patch.json

What it looks for:
  level difficulty   first-try rate, median time and hint use per family level
  level order        a level that looks easier than the one before it
  unpicked           misconceptions offered as distractors many times but never picked
                     (rare for these students, or a badly built distractor)
  untagged misses    wrong answers no misconception explains (a missing distractor
                     solver, or a mistake the map does not name yet)
These describe a handful of students. They are notes for the analyst, not a
calibration of Bebras difficulty.
"""

import argparse
import datetime
import json
import os
import re
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MIN_N = 8          # first tries needed before a level is compared or a distractor is judged
ORDER_GAP = 0.15   # a later level this much easier than the one before is flagged
LIVE = {"press": ["XOR_AS_OR", "BOTH_AS_EITHER", "EXTRA_BUTTONS"],
        "fill": ["PARITY_CORNER", "PARITY_ROWS_ONLY", "PARITY_COLS_ONLY"]}


def load_bank():
    fams = re.findall(r'data-fam="([a-z-]+)"', open(os.path.join(ROOT, "index.html")).read())
    bank = {}
    for f in fams:
        for name in os.listdir(os.path.join(ROOT, f)):
            if not re.match(r"L\d+-\d+\.js$", name):
                continue
            t = open(os.path.join(ROOT, f, name)).read()
            p = json.loads(t[t.index("{", t.index(",")):t.rindex(")")])
            bank[(f, p["level"], p["seed"])] = p
    return fams, bank


def offered_tags(p):
    s = set()
    for d in p.get("distractors") or []:
        s.update(d.get("misconceptions", []))
    for v in (p.get("value_tags") or {}).values():
        s.update(v)
    for v in (p.get("cell_tags") or {}).values():
        s.update(v)
    s.update((p.get("misconception_paths") or {}).keys())
    if p.get("entry") == "press":
        s.update(LIVE["press"])
    if p.get("entry") == "cells" and p.get("question_type") == "fill":
        s.update(LIVE["fill"])
    return s


def load_attempts(path):
    if path.endswith(".json"):
        d = json.load(open(path))
        # puzzles reopened from the Progress page are left out, as the tutor leaves them out
        return [a for a in d["attempts"] if a.get("served") != "lookback"]
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    out = []
    cols = {c[1] for c in con.execute("PRAGMA table_info(attempts)")}
    where = " WHERE served_as IS NOT 'lookback'" if "served_as" in cols else ""
    for r in con.execute(f"SELECT * FROM attempts{where} ORDER BY user_id, created_at, id"):
        out.append({"user": r["user_id"], "fam": r["family"], "level": r["level"], "seed": r["seed"],
                    "try": r["try_number"], "correct": bool(r["correct"]), "tags": json.loads(r["misconceptions"] or "[]"),
                    "hints": r["hints_shown"], "ms": r["ms_on_problem"], "t": r["created_at"]})
    return out


def first_tries(attempts):
    """One record per puzzle shown, with its first try and how many tries it took."""
    out, last = [], {}
    for a in sorted(attempts, key=lambda a: (a["user"], a["t"])):
        k = (a["user"], a["fam"], a["level"], a["seed"])
        if a["try"] == 1:
            rec = dict(a, tries=1)
            out.append(rec)
            last[k] = rec
        elif k in last:
            last[k]["tries"] += 1
    return out


def analyse(fams, bank, firsts):
    items = []
    by_level = defaultdict(list)
    for e in firsts:
        by_level[(e["fam"], e["level"])].append(e)

    # 1. difficulty per level
    rate = {}
    for (f, l), es in sorted(by_level.items(), key=lambda x: (fams.index(x[0][0]) if x[0][0] in fams else 99, x[0][1])):
        n = len(es)
        r = sum(e["correct"] for e in es) / n
        rate[(f, l)] = (r, n)
        ms = [e["ms"] for e in es if e.get("ms")]
        items.append({"id": f"difficulty:{f}:L{l}", "kind": "level_difficulty", "family": f, "level": l,
                      "first_tries": n, "students": len({e["user"] for e in es}),
                      "first_try_right": round(r, 2),
                      "median_seconds": round(statistics.median(ms) / 1000) if ms else None,
                      "hint_before_first_try": round(sum(1 for e in es if e.get("hints")) / n, 2),
                      "small_sample": n < MIN_N})

    # 2. level order
    for f in fams:
        levels = sorted(l for (ff, l) in rate if ff == f)
        for a, b in zip(levels, levels[1:]):
            (ra, na), (rb, nb) = rate[(f, a)], rate[(f, b)]
            if b == a + 1 and na >= MIN_N and nb >= MIN_N and rb - ra > ORDER_GAP:
                items.append({"id": f"order:{f}:L{a}-L{b}", "kind": "level_order", "family": f, "levels": [a, b],
                              "first_try_right": [round(ra, 2), round(rb, 2)], "first_tries": [na, nb],
                              "note": f"Level {b} went better than level {a} on the first try. Check whether the ladder order fits these students."})

    # 3. distractors offered but never picked, and 4. misses no tag explains
    offered, picked = Counter(), Counter()
    untagged = defaultdict(lambda: [0, 0])     # (fam, level) -> [untagged misses, misses]
    missing = 0
    for e in firsts:
        p = bank.get((e["fam"], e["level"], e["seed"]))
        if p is None:
            missing += 1
            continue
        tags = offered_tags(p)
        for t in tags:
            offered[(e["fam"], t)] += 1
        if not e["correct"]:
            untagged[(e["fam"], e["level"])][1] += 1
            if not e["tags"]:
                untagged[(e["fam"], e["level"])][0] += 1
            for t in e["tags"]:
                picked[(e["fam"], t)] += 1
    for (f, t), n in sorted(offered.items()):
        if n >= MIN_N * 2 and picked[(f, t)] == 0:
            items.append({"id": f"unpicked:{f}:{t}", "kind": "unpicked_misconception", "family": f, "misconception": t,
                          "offered": n, "picked": 0,
                          "note": "Offered many times and never chosen: rare for these students, or the distractor is easy to rule out."})
    for (f, t), n in sorted(picked.items(), key=lambda x: -x[1]):
        items.append({"id": f"picked:{f}:{t}", "kind": "misconception_rate", "family": f, "misconception": t,
                      "offered": offered[(f, t)], "picked": n,
                      "rate_when_offered": round(n / offered[(f, t)], 2) if offered[(f, t)] else None})
    for (f, l), (u, m) in sorted(untagged.items()):
        if m >= 4 and u / m >= 0.4:
            items.append({"id": f"untagged:{f}:L{l}", "kind": "untagged_misses", "family": f, "level": l,
                          "untagged": u, "misses": m,
                          "note": "Many wrong first answers match no named misconception. Look at the answers for a mistake the map does not name yet."})
    return items, missing


def report(items, firsts, missing):
    print(f"{len(firsts)} first tries from {len({e['user'] for e in firsts})} students")
    if missing:
        print(f"({missing} first tries are on puzzles no longer in the bank; they count for difficulty only)")
    print("\nLevel difficulty (first-try right, n, median s, hints):")
    for it in items:
        if it["kind"] == "level_difficulty":
            flag = "  (small sample)" if it["small_sample"] else ""
            print(f"  {it['family']:15} L{it['level']}  {it['first_try_right']:.0%}  n={it['first_tries']:<4} "
                  f"{it['median_seconds'] if it['median_seconds'] is not None else '-':>4}s  hints {it['hint_before_first_try']:.0%}{flag}")
    for kind, title in (("level_order", "Levels that look out of order"),
                        ("unpicked_misconception", "Distractors never picked"),
                        ("untagged_misses", "Misses no misconception explains"),
                        ("misconception_rate", "Misconceptions picked")):
        rows = [it for it in items if it["kind"] == kind]
        print(f"\n{title}:" + ("" if rows else " none"))
        for it in rows:
            if kind == "level_order":
                print(f"  {it['family']} L{it['levels'][0]} {it['first_try_right'][0]:.0%} vs L{it['levels'][1]} {it['first_try_right'][1]:.0%}")
            elif kind == "unpicked_misconception":
                print(f"  {it['family']} {it['misconception']}: offered {it['offered']} times")
            elif kind == "untagged_misses":
                print(f"  {it['family']} L{it['level']}: {it['untagged']} of {it['misses']} misses")
            else:
                print(f"  {it['family']} {it['misconception']}: {it['picked']} of {it['offered']} times offered")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="kerbopple-export.json from the progress page, or the server's .db file")
    ap.add_argument("--out", default=os.path.join(HERE, "observations_patch.json"))
    a = ap.parse_args()
    fams, bank = load_bank()
    firsts = first_tries(load_attempts(a.source))
    if not firsts:
        sys.exit("No answers in that file yet.")
    items, missing = analyse(fams, bank, firsts)
    report(items, firsts, missing)
    days = [datetime.datetime.fromtimestamp(e["t"] / 1000, datetime.timezone.utc).date().isoformat() for e in firsts]
    patch = {
        "patch_id": "data-observations",
        "built": datetime.date.today().isoformat(),
        "method": "tools/observe.py over the students' own first tries (analyst notes by Claude; no student names).",
        "data_observations": {
            "from": min(days), "to": max(days),
            "students": len({e["user"] for e in firsts}), "first_tries": len(firsts),
            "min_n": MIN_N, "items": items,
        },
    }
    json.dump(patch, open(a.out, "w"), indent=2)
    print(f"\nWrote {os.path.relpath(a.out)}. Merge it with:\n  python3 tools/merge_patch.py tools/bebras_knowledge_map.json {os.path.relpath(a.out)}")

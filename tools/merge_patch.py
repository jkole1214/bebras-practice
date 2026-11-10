"""
Merge a patch file (e.g. junior_senior_patch.json) into bebras_knowledge_map.json.

Safe to run more than once: items already present (same id or key) are
updated in place, not duplicated.

Usage:
    python3 merge_patch.py bebras_knowledge_map.json junior_senior_patch.json [out.json]
If out.json is omitted the map is rewritten in place.
"""

import json
import sys


def by(lst, key):
    return {x[key]: x for x in lst}


def merge(m, p):
    # sources
    have = {(s["age_group"], s.get("set", "2015 examples")) for s in m["meta"]["source_sets"]}
    for s in p.get("source_sets", []):
        if (s["age_group"], s.get("set", "2015 examples")) not in have:
            m["meta"]["source_sets"].append(s)

    # domains
    dom = by(m["domains"], "id")
    for d in p.get("domains", []):
        dom[d["id"]] = d
    m["domains"] = list(dom.values())

    # concepts (new ones appended; existing ids replaced)
    con = by(m["concepts"], "id")
    for c in p.get("concepts", []):
        con[c["id"]] = c
    m["concepts"] = list(con.values())
    for u in p.get("concept_updates", []):
        c = con.get(u["id"])
        if c is not None:
            notes = c.setdefault("notes", [])
            if u["add_note"] not in notes:
                notes.append(u["add_note"])

    # tasks
    tasks = by(m["tasks"], "key")
    for t in p.get("tasks", []):
        tasks[t["key"]] = t
    for a in p.get("appearances_for_existing_tasks", []):
        t = tasks[a["key"]]
        seen = {(x["age_group"], x.get("grq_id")) for x in t["appearances"]}
        for x in a["add"]:
            if (x["age_group"], x.get("grq_id")) not in seen:
                t["appearances"].append(x)
    order = ["Benjamin", "Cadet", "Junior", "Senior"]
    for t in tasks.values():
        t["appearances"].sort(key=lambda x: order.index(x["age_group"]))
    m["tasks"] = list(tasks.values())

    # misconceptions
    mis = by(m.get("misconceptions", []), "id")
    for x in p.get("misconceptions", []):
        mis.setdefault(x["id"], x)
    m["misconceptions"] = list(mis.values())

    # progression and generator candidates
    prog = m.setdefault("progression", {})
    prog.setdefault("observations", [])
    pp = p.get("progression", {})
    if pp.get("mode") == "append":
        # later patches add a dated section instead of replacing the 2015 findings
        sec = {k: v for k, v in pp.items() if k != "mode"}
        sec["patch_id"] = p["patch_id"]
        prog["observations"] = [o for o in prog["observations"]
                                if not (isinstance(o, dict) and o.get("patch_id") == p["patch_id"])] + [sec]
    else:
        for k in ("reuse", "what_changes_with_age", "implications_for_the_tutor"):
            if k in pp:
                prog[k] = pp[k]
    if "generator_candidates" in p:
        if p.get("generator_candidates_mode") == "append":
            have = {g["source_task"] for g in m.get("generator_candidates", [])}
            m.setdefault("generator_candidates", []).extend(
                g for g in p["generator_candidates"] if g["source_task"] not in have)
        else:
            m["generator_candidates"] = p["generator_candidates"]

    # formats used by new tasks
    m["formats"].setdefault("number_entry", "Type a number and save.")
    for k, v in p.get("formats", {}).items():
        m["formats"].setdefault(k, v)

    # meta
    counts = {}
    for g in order:
        counts[g.lower() + "_tasks"] = sum(1 for t in m["tasks"] for a in t["appearances"] if a["age_group"] == g)
    counts["distinct_tasks"] = len(m["tasks"])
    counts["tasks_in_more_than_one_group"] = sum(1 for t in m["tasks"] if len({a["age_group"] for a in t["appearances"]}) > 1)
    m["meta"]["counts"] = counts
    m["meta"]["title"] = p.get("map_title", m["meta"].get("title",
        "Bebras 2015 example sets (Benjamin, Cadet, Junior, Senior): knowledge map"))
    patches = m["meta"].setdefault("patches", [])
    entry = {"id": p["patch_id"], "built": p["built"], "method": p["method"]}
    m["meta"]["patches"] = [x for x in patches if x["id"] != p["patch_id"]] + [entry]
    m["meta"]["tier_meaning"] = ("Each set lists tasks in three tiers, A, B and C, five per tier. Tiers track difficulty "
                                 "within an age group: A easiest, C hardest. A task reused by an older group usually "
                                 "drops one tier.")
    return m


def validate(m):
    errs = []
    cids = {c["id"] for c in m["concepts"]}
    keys = {t["key"] for t in m["tasks"]}
    for c in m["concepts"]:
        for pr in c["prerequisites"]:
            if pr["id"] not in cids:
                errs.append(f"{c['id']}: unknown prerequisite {pr['id']}")
    for t in m["tasks"]:
        for x in t["concepts"]:
            if x not in cids:
                errs.append(f"{t['key']}: unknown concept {x}")
    for x in m["misconceptions"]:
        if x["concept"] not in cids:
            errs.append(f"misconception {x['id']}: unknown concept {x['concept']}")
    for r in m.get("reasoning_moves", []):
        for k in r["used_in"]:
            if k not in keys:
                errs.append(f"reasoning move {r['id']}: unknown task {k}")
    # acyclic prerequisites
    g = {c["id"]: [p["id"] for p in c["prerequisites"]] for c in m["concepts"]}
    state = {}

    def dfs(u):
        if state.get(u) == 1:
            raise ValueError("prerequisite cycle at " + u)
        if state.get(u) == 2:
            return
        state[u] = 1
        for v in g[u]:
            dfs(v)
        state[u] = 2
    for u in g:
        dfs(u)
    return errs


if __name__ == "__main__":
    src, patch = sys.argv[1], sys.argv[2]
    out = sys.argv[3] if len(sys.argv) > 3 else src
    m = merge(json.load(open(src)), json.load(open(patch)))
    e = validate(m)
    if e:
        print("\n".join(e))
        sys.exit(1)
    json.dump(m, open(out, "w"), indent=2, ensure_ascii=False)
    print(json.dumps(m["meta"]["counts"]))

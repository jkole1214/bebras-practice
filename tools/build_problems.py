"""
Regenerate the problem files.

Writes one file per problem into each family's folder (see FAMILIES),
runs each problem through its independent checker, skips any that fail,
and rewrites each folder's manifest.js plus ../coach.js.

Problem files are JSON wrapped in a single function call so the page can load
them straight from disk (browsers block fetch() on file:// pages, but allow
<script> tags).

Usage (from anywhere):
    python3 tools/build_problems.py                 # 12 per level, seeds from 1000
    python3 tools/build_problems.py --per-level 30 --seed 5000
Requires: Python 3.9+, networkx (pip install networkx) for the Lake Crossing checker.
"""

import argparse
import json
import os
import sys
from dataclasses import asdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import conditional_trace as ct          # noqa: E402
import shortest_path as sp              # noqa: E402
import check_conditional_trace as ck1   # noqa: E402
import check_shortest_path as ck2       # noqa: E402
import signal_code as scg               # noqa: E402
import check_signal_code as ck3         # noqa: E402
import grid_routes as grg               # noqa: E402
import check_grid_routes as ck4         # noqa: E402
import conveyor as cvg                  # noqa: E402
import check_conveyor as ck5            # noqa: E402
import pointer_lists as plg             # noqa: E402
import check_pointer_lists as ck6       # noqa: E402
import logic_gates as lgg               # noqa: E402
import check_logic_gates as ck7         # noqa: E402
import bead_grammar as bgg              # noqa: E402
import check_bead_grammar as ck8        # noqa: E402
import parity_grid as pgg               # noqa: E402
import check_parity_grid as ck9         # noqa: E402

FAMILIES = {
    "rule-tracer": {
        "module": ct, "checker": ck1, "levels": len(ct.LADDER), "title": "Rule Tracer",
        "keep": ["family", "level", "question_type", "seed", "scene", "prompt", "rule_text", "options",
                 "answer_index", "answer_value", "entry", "value_tags", "distractors", "concepts",
                 "explanation", "hints"],
    },
    "lake-crossing": {
        "module": sp, "checker": ck2, "levels": len(sp.LADDER), "title": "Lake Crossing",
        "keep": ["family", "level", "question_type", "seed", "prompt", "svg", "options",
                 "answer_index", "answer_path", "answer_cost", "distractors",
                 "misconception_paths", "concepts", "explanation", "hints",
                 "answer_value", "optimal_paths", "entry", "value_tags"],
    },
    "signal-lamp": {
        "module": scg, "checker": ck3, "levels": len(scg.LADDER), "title": "Signal Lamp",
        "keep": ["family", "level", "question_type", "seed", "scene", "prompt", "question", "codebook", "signal", "options",
                 "answer_index", "answer_value", "entry", "distractors", "value_tags", "concepts",
                 "explanation", "hints"],
    },
    "robot-routes": {
        "module": grg, "checker": ck4, "levels": len(grg.LADDER), "title": "Robot Routes",
        "keep": ["family", "level", "question_type", "seed", "scene", "svg", "prompt", "question", "options",
                 "answer_index", "answer_value", "entry", "distractors", "value_tags", "concepts",
                 "explanation", "hints"],
    },
    "nuts-and-bolts": {
        "module": cvg, "checker": ck5, "levels": len(cvg.LADDER), "title": "Nuts and Bolts",
        "keep": ["family", "level", "question_type", "seed", "scene", "prompt", "question", "options",
                 "answer_index", "answer_value", "entry", "distractors", "value_tags", "concepts",
                 "explanation", "hints"],
    },
    "lights-on": {
        "module": lgg, "checker": ck7, "levels": len(lgg.LADDER), "title": "Lights On",
        "keep": ["family", "level", "question_type", "seed", "scene", "prompt", "question", "options",
                 "answer_index", "answer_value", "entry", "distractors", "value_tags", "concepts",
                 "explanation", "hints", "svg"],
    },
    "bead-rules": {
        "module": bgg, "checker": ck8, "levels": len(bgg.LADDER), "title": "Bead Rules",
        "keep": ["family", "level", "question_type", "seed", "scene", "prompt", "question", "options",
                 "answer_index", "answer_value", "entry", "distractors", "value_tags", "concepts",
                 "explanation", "hints"],
    },
    "pantry-map": {
        "module": pgg, "checker": ck9, "levels": len(pgg.LADDER), "title": "Pantry Map",
        "keep": ["family", "level", "question_type", "seed", "scene", "prompt", "question", "options",
                 "answer_index", "answer_value", "entry", "distractors", "value_tags", "concepts",
                 "explanation", "hints", "pick", "cell_tags"],
    },
    "box-rows": {
        "module": plg, "checker": ck6, "levels": len(plg.LADDER), "title": "Box Rows",
        "keep": ["family", "level", "question_type", "seed", "scene", "prompt", "question", "options",
                 "answer_index", "answer_value", "entry", "distractors", "value_tags", "concepts",
                 "explanation", "hints"],
    },
}


def build(per_level, seed0):
    report = {}
    for folder, f in FAMILIES.items():
        out_dir = os.path.join(ROOT, folder)
        os.makedirs(out_dir, exist_ok=True)
        for name in os.listdir(out_dir):
            if name.endswith(".js"):
                os.remove(os.path.join(out_dir, name))
        files, failed = [], 0
        for level in range(1, f["levels"] + 1):
            made, seed = 0, seed0
            while made < per_level and seed < seed0 + per_level * 20:
                try:
                    p = asdict(f["module"].generate(level, seed))
                except RuntimeError:
                    seed += 1
                    continue
                if f["checker"].check(p):
                    failed += 1
                    seed += 1
                    continue
                rec = {k: p[k] for k in f["keep"]}
                fname = f"L{level}-{seed}.js"
                with open(os.path.join(out_dir, fname), "w") as fh:
                    fh.write(f'BEBRAS.add("{folder}", '
                             + json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + ");\n")
                files.append(fname)
                made += 1
                seed += 1
        with open(os.path.join(out_dir, "manifest.js"), "w") as fh:
            fh.write(f'BEBRAS.manifest("{folder}", {json.dumps(files)});\n')
        report[folder] = {"written": len(files), "rejected_by_checker": failed}

    m = json.load(open(os.path.join(HERE, "bebras_knowledge_map.json")))
    extra = {**scg.MISCONCEPTIONS, **grg.MISCONCEPTIONS, **sp.COUNT_MISCONCEPTIONS, **ct.COUNT_EXTRA_MISCONCEPTIONS,
             **cvg.MISCONCEPTIONS, **plg.MISCONCEPTIONS, **lgg.MISCONCEPTIONS, **bgg.MISCONCEPTIONS,
             **pgg.MISCONCEPTIONS}
    for k, v in extra.items():
        if k not in {x["id"] for x in m["misconceptions"]}:
            m["misconceptions"].append({"id": k, **v})
    coach = {
        "titles": {k: v["title"] for k, v in FAMILIES.items()},
        "misconceptions": {x["id"]: {"concept": x["concept"], "description": x["description"],
                                     "remediation": x["remediation"]} for x in m["misconceptions"]},
        "concepts": {c["id"]: c["name"] for c in m["concepts"]},
        "ladders": {"rule-tracer": [l["note"] for l in ct.LADDER],
                    "lake-crossing": [l["note"] for l in sp.LADDER],
                    "signal-lamp": [l["note"] for l in scg.LADDER],
                    "robot-routes": [l["note"] for l in grg.LADDER],
                    "nuts-and-bolts": [l["note"] for l in cvg.LADDER],
                    "box-rows": [l["note"] for l in plg.LADDER],
                    "lights-on": [l["note"] for l in lgg.LADDER],
                    "bead-rules": [l["note"] for l in bgg.LADDER],
                    "pantry-map": [l["note"] for l in pgg.LADDER]},
    }
    with open(os.path.join(ROOT, "coach.js"), "w") as fh:
        fh.write("BEBRAS.coach(" + json.dumps(coach, ensure_ascii=False) + ");\n")
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-level", type=int, default=12)
    ap.add_argument("--seed", type=int, default=1000)
    a = ap.parse_args()
    print(json.dumps(build(a.per_level, a.seed), indent=2))

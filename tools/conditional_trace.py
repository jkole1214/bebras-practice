"""
Problem family: conditional_trace (nested IF/ELSE over dice rolls).

Concept targets: CONDITIONALS, NESTED_CONDITIONALS, NEGATION_BOUNDARY.

A problem is generated from a single scene model (the rule tree plus the
rolls). The rendered text, the answer key, the distractor tags and the
explanation are all derived from that model, so they cannot disagree.

Two question types:
  trace: given a roll, which outcome does the rule pick?  (easier)
  find:  which of these rolls leads to a given outcome?    (harder)

Every wrong option is tagged with the misconception(s) that would pick it.
"""

import itertools
import json
import random
from dataclasses import dataclass, field, asdict
from typing import Optional, Union

# --------------------------------------------------------------------------
# Scene model
# --------------------------------------------------------------------------

ORDINALS = ["first", "second", "third", "fourth"]
OPS = {
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
}
OP_WORDS = {
    ">": "is greater than",
    "<": "is less than",
    ">=": "is greater than or equal to",
    "<=": "is less than or equal to",
}
OUTCOME_POOL = ["the library", "the garden", "the workshop", "the attic", "the boathouse"]
DIE_FACES = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}


@dataclass
class Cond:
    left: int   # die index
    op: str
    right: int  # die index (ignored when const is set)
    const: int = None  # compare the left die with this number instead of another die


@dataclass
class Node:
    cond: Cond
    then: Union["Node", str]
    els: Union["Node", str]


def leaves(node):
    if isinstance(node, str):
        return [node]
    return leaves(node.then) + leaves(node.els)


def depth(node):
    if isinstance(node, str):
        return 0
    return 1 + max(depth(node.then), depth(node.els))


def path_to(node, target, acc=None):
    """List of (cond, branch_taken) from root to the target leaf."""
    acc = acc or []
    if isinstance(node, str):
        return acc if node == target else None
    p = path_to(node.then, target, acc + [(node.cond, True)])
    if p is not None:
        return p
    return path_to(node.els, target, acc + [(node.cond, False)])


# --------------------------------------------------------------------------
# Evaluators: the true semantics and one per misconception
# --------------------------------------------------------------------------

def test(cond, roll, op_override=None, idx_map=None):
    l, r = cond.left, cond.right
    if idx_map:
        l, r = idx_map.get(l, l), idx_map.get(r, r)
    op = op_override(cond.op) if op_override else cond.op
    rhs = cond.const if cond.const is not None else roll[r]
    return OPS[op](roll[l], rhs)


def evaluate(node, roll, op_override=None, idx_map=None):
    while not isinstance(node, str):
        node = node.then if test(node.cond, roll, op_override, idx_map) else node.els
    return node


def flip_strictness(op):
    return {">": ">=", "<": "<=", ">=": ">", "<=": "<"}[op]


def reverse_direction(op):
    return {">": "<", "<": ">", ">=": "<=", "<=": ">="}[op]


def eval_ties_flipped(tree, roll, target=None):
    return evaluate(tree, roll, op_override=flip_strictness)


def eval_reversed(tree, roll, target=None):
    return evaluate(tree, roll, op_override=reverse_direction)


def eval_skips_outer(tree, roll, target=None):
    """Student evaluates only the innermost IF that matters, ignoring the
    tests above it. For find questions that is the IF guarding the target;
    for trace questions, the deepest IF in the tree."""
    if target is not None:
        p = path_to(tree, target)
        if p is None or len(p) < 2:
            return evaluate(tree, roll)
        # walk to the parent of the target without testing ancestors
        node = tree
        for cond, branch in p[:-1]:
            node = node.then if branch else node.els
        return evaluate(node, roll)
    node = tree
    while not isinstance(node, str):
        if isinstance(node.then, Node):
            node = node.then
        elif isinstance(node.els, Node):
            node = node.els
        else:
            return evaluate(node, roll)
    return node


def eval_index_confusion(tree, roll, target=None):
    if len(roll) < 3:
        return evaluate(tree, roll)
    return evaluate(tree, roll, idx_map={1: 2, 2: 1})


MISCONCEPTIONS = {
    "TIES_FLIPPED": {
        "concept": "NEGATION_BOUNDARY",
        "description": "Handles ties the wrong way: treats 'greater than' as 'greater than or equal to' (and the reverse). Typically from reading 'not greater than' as 'less than'.",
        "evaluator": eval_ties_flipped,
        "remediation": "Show a roll with two equal dice and ask whether each test is true or false.",
    },
    "REVERSED_COMPARISON": {
        "concept": "CONDITIONALS",
        "description": "Reads the comparison backwards: checks whether the second-named die is greater instead of the first.",
        "evaluator": eval_reversed,
        "remediation": "Have the student say each test aloud with the actual numbers substituted in, left to right.",
    },
    "SKIPS_OUTER_TEST": {
        "concept": "NESTED_CONDITIONALS",
        "description": "Checks only the innermost IF and forgets that the outer test must have failed to get there.",
        "evaluator": eval_skips_outer,
        "remediation": "Ask: to reach this line, which earlier test had to be false? Trace from the top with a finger.",
    },
    "INDEX_CONFUSION": {
        "concept": "CONDITIONALS",
        "description": "Mixes up which die is the second and which is the third.",
        "evaluator": eval_index_confusion,
        "remediation": "Label each die with its position number before evaluating any test.",
    },
}

# --------------------------------------------------------------------------
# Difficulty ladder (ordered easiest to hardest within the family)
# --------------------------------------------------------------------------

LADDER = [
    {"level": 1, "question": "trace", "dice": 2, "depth": 1, "ops": [">", "<"], "ties": "none",
     "note": "Single IF/ELSE, read forward, no equal dice."},
    {"level": 2, "question": "trace", "dice": 3, "depth": 2, "ops": [">", "<"], "ties": "none",
     "note": "One nested IF, read forward."},
    {"level": 3, "question": "trace", "dice": 3, "depth": 2, "ops": [">", "<"], "ties": "decisive",
     "note": "Nested IF, and the roll has two equal dice that a test compares."},
    {"level": 4, "question": "find", "dice": 3, "depth": 1, "ops": [">", "<"], "ties": "none",
     "note": "First inverse question: which roll leads to a given outcome. Single IF/ELSE, three dice. "
             "Uses 3 options when only two misconceptions can produce distinct wrong answers."},
    {"level": 5, "question": "find", "dice": 3, "depth": 2, "ops": [">", "<"], "ties": "none",
     "note": "Inverse question through a nested IF; target needs an outer test to fail."},
    {"level": 6, "question": "find", "dice": 3, "depth": 2, "ops": [">", "<"], "ties": "decisive",
     "note": "Same, and the correct roll depends on a tie. Matches the 2015 Cadet C task."},
    {"level": 7, "question": "find", "dice": 4, "depth": 3, "ops": [">", "<", ">=", "<="], "ties": "decisive",
     "note": "Three levels of nesting, mixed strict and non-strict tests, ties."},
    {"level": 8, "question": "count", "dice": 3, "depth": (2, 3), "ops": [">", "<", ">=", "<="], "ties": "any",
     "note": "Counting: how many of the 216 possible rolls send the piece to a given place? Too many to check one by one."},
]

# --------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------

def random_tree(rng, n_dice, d, ops, outcomes, const_prob=0.0):
    """Random tree of exact depth d with distinct outcome labels at leaves."""
    outcomes = list(outcomes)

    def cond():
        a, b = rng.sample(range(n_dice), 2)
        if rng.random() < const_prob:
            return Cond(a, rng.choice(ops), b, rng.randint(2, 5))
        return Cond(a, rng.choice(ops), b)

    def build(level):
        if level == 0:
            return outcomes.pop()
        # one child carries the remaining depth, the other is a leaf
        deep_then = rng.random() < 0.3
        child = build(level - 1)
        leaf = outcomes.pop()
        return Node(cond(), child if deep_then else leaf, leaf if deep_then else child)

    return build(d)


def compared_pairs(tree):
    out = set()
    stack = [tree]
    while stack:
        n = stack.pop()
        if isinstance(n, Node):
            out.add(tuple(sorted((n.cond.left, n.cond.right))))
            stack += [n.then, n.els]
    return out


def has_decisive_tie(tree, roll):
    """A tie on a pair the rule actually tests along the taken path."""
    node = tree
    while isinstance(node, Node):
        c = node.cond
        if roll[c.left] == roll[c.right]:
            return True
        node = node.then if test(c, roll) else node.els
    return False


def any_tie_in_compared(tree, roll):
    return any(roll[a] == roll[b] for a, b in compared_pairs(tree))


def all_rolls(n):
    return list(itertools.product(range(1, 7), repeat=n))


def wrong_tags(tree, roll, target_for_find=None):
    """Which misconceptions produce which outcome for this roll."""
    out = {}
    for name, m in MISCONCEPTIONS.items():
        out[name] = m["evaluator"](tree, roll, target_for_find)
    return out


# Surface heuristics a student might use instead of reasoning. A valid find
# problem must not let any of these single out the correct option.
def shortcut_features(roll):
    return {
        "all_equal": len(set(roll)) == 1,
        "strictly_ascending": all(a < b for a, b in zip(roll, roll[1:])),
        "strictly_descending": all(a > b for a, b in zip(roll, roll[1:])),
        "has_repeat": len(set(roll)) < len(roll),
        "contains_six": 6 in roll,
        "contains_one": 1 in roll,
    }


def shortcut_hits(options, correct_idx):
    hits = []
    feats = [shortcut_features(o) for o in options]
    for k in feats[0]:
        holders = [i for i, f in enumerate(feats) if f[k]]
        if holders == [correct_idx]:
            hits.append(k)
    sums = [sum(o) for o in options]
    if sums.count(max(sums)) == 1 and sums.index(max(sums)) == correct_idx:
        hits.append("max_sum")
    if sums.count(min(sums)) == 1 and sums.index(min(sums)) == correct_idx:
        hits.append("min_sum")
    return hits


@dataclass
class Problem:
    family: str
    level: int
    question_type: str
    seed: int
    scene: dict
    prompt: str
    rule_text: str
    options: list
    answer_index: int
    distractors: list
    concepts: list
    explanation: list
    hints: list
    knobs: dict = field(default_factory=dict)
    answer_value: int = None
    entry: str = "choice"
    value_tags: dict = field(default_factory=dict)


def tree_to_dict(n):
    if isinstance(n, str):
        return {"outcome": n}
    cond = {"left": n.cond.left, "op": n.cond.op, "right": n.cond.right}
    if n.cond.const is not None:
        cond["const"] = n.cond.const
    return {"if": cond,
            "then": tree_to_dict(n.then), "else": tree_to_dict(n.els)}


def render_rule(tree, indent=0):
    pad = "    " * indent
    if isinstance(tree, str):
        return [f"{pad}go to {tree}"]
    c = tree.cond
    rhs = str(c.const) if c.const is not None else f"the {ORDINALS[c.right]} roll"
    lines = [f"{pad}IF the {ORDINALS[c.left]} roll {OP_WORDS[c.op]} {rhs}"]
    lines.append(f"{pad}THEN")
    lines += render_rule(tree.then, indent + 1)
    lines.append(f"{pad}ELSE")
    lines += render_rule(tree.els, indent + 1)
    return lines


def roll_text(roll):
    return ", ".join(f"{v} {DIE_FACES[v]}" for v in roll)


def trace_steps(tree, roll):
    steps = []
    node = tree
    while isinstance(node, Node):
        c = node.cond
        a, b = roll[c.left], roll[c.right]
        res = test(c, roll)
        steps.append(f"Is the {ORDINALS[c.left]} roll ({a}) {OP_WORDS[c.op].removeprefix('is ')} the {ORDINALS[c.right]} roll ({b})? "
                     f"{'Yes' if res else 'No'}, so take the {'THEN' if res else 'ELSE'} branch.")
        node = node.then if res else node.els
    steps.append(f"Result: {node}.")
    return steps


def make_trace(rng, cfg, seed):
    outcomes = rng.sample(OUTCOME_POOL, cfg["depth"] + 1)
    for _ in range(500):
        tree = random_tree(rng, cfg["dice"], cfg["depth"], cfg["ops"], outcomes)
        rolls = all_rolls(cfg["dice"])
        rng.shuffle(rolls)
        for roll in rolls:
            if cfg["ties"] == "none" and any_tie_in_compared(tree, roll):
                continue
            if cfg["ties"] == "decisive" and not has_decisive_tie(tree, roll):
                continue
            truth = evaluate(tree, roll)
            tags = wrong_tags(tree, roll)
            wrong = {o for o in tags.values() if o != truth}
            # every wrong outcome option should be reachable by a misconception
            need = len(leaves(tree)) - 1 if cfg["depth"] > 1 else 1
            if len(wrong) < need:
                continue
            if cfg["ties"] == "decisive" and tags["TIES_FLIPPED"] == truth:
                continue
            options = leaves(tree)
            rng.shuffle(options)
            ans = options.index(truth)
            distractors = [{"option": o, "misconceptions": sorted(k for k, v in tags.items() if v == o)}
                           for o in options if o != truth]
            return Problem(
                family="conditional_trace", level=cfg["level"], question_type="trace", seed=seed,
                scene={"dice": cfg["dice"], "tree": tree_to_dict(tree), "roll": list(roll)},
                prompt=f"A game decides where your piece goes by rolling a die {cfg['dice']} times and following "
                       f"the rule below. The rolls are {roll_text(roll)}. Where does the piece go?",
                rule_text="\n".join(render_rule(tree)),
                options=options, answer_index=ans, distractors=distractors,
                concepts=concepts_for(cfg),
                explanation=trace_steps(tree, roll),
                hints=hints_for(cfg, tree, truth),
                knobs={k: cfg[k] for k in ("dice", "depth", "ops", "ties")},
            )
    raise RuntimeError("trace generation failed")


def make_find(rng, cfg, seed):
    outcomes = rng.sample(OUTCOME_POOL, cfg["depth"] + 1)
    for _ in range(500):
        tree = random_tree(rng, cfg["dice"], cfg["depth"], cfg["ops"], outcomes)
        # target: the deepest ELSE-reached leaf when possible (needs a failed test)
        cands = [l for l in leaves(tree) if any(not b for _, b in path_to(tree, l))]
        cands.sort(key=lambda l: -len(path_to(tree, l)))
        target = cands[0] if cands else leaves(tree)[-1]
        rolls = all_rolls(cfg["dice"])
        correct_pool = [r for r in rolls if evaluate(tree, r) == target]
        if cfg["ties"] == "none":
            correct_pool = [r for r in correct_pool if not any_tie_in_compared(tree, r)]
        else:
            correct_pool = [r for r in correct_pool if has_decisive_tie(tree, r)]
        if not correct_pool:
            continue
        # distractor pools: rolls a misconception sends to the target but truth does not
        pools = {}
        for name, m in MISCONCEPTIONS.items():
            pool = [r for r in rolls
                    if evaluate(tree, r) != target and m["evaluator"](tree, r, target) == target]
            if cfg["ties"] == "none" and name != "TIES_FLIPPED":
                pool = [r for r in pool if not any_tie_in_compared(tree, r)]
            if pool:
                pools[name] = pool
        min_pools = 2 if cfg["depth"] == 1 else 3
        if len(pools) < min_pools:
            continue
        for _attempt in range(60):
            correct = rng.choice(correct_pool)
            names = rng.sample(sorted(pools), min(3, len(pools)))
            # tie levels must include the tie misconception
            if cfg["ties"] == "decisive" and "TIES_FLIPPED" in pools and "TIES_FLIPPED" not in names:
                names[0] = "TIES_FLIPPED"
            chosen = []
            ok = True
            for name in names:
                pool = [r for r in pools[name] if r != correct and r not in chosen]
                # prefer distractors only this misconception explains
                unique = [r for r in pool
                          if sum(MISCONCEPTIONS[o]["evaluator"](tree, r, target) == target
                                 for o in MISCONCEPTIONS) == 1]
                pick_from = unique or pool
                if not pick_from:
                    ok = False
                    break
                chosen.append(rng.choice(pick_from))
            if not ok:
                continue
            options = [list(correct)] + [list(c) for c in chosen]
            order = list(range(len(options)))
            rng.shuffle(order)
            options = [options[i] for i in order]
            ans = order.index(0)
            if shortcut_hits(options, ans):
                continue
            distractors = []
            for o in options:
                if o == list(correct):
                    continue
                tags = sorted(k for k, m in MISCONCEPTIONS.items()
                              if m["evaluator"](tree, tuple(o), target) == target)
                distractors.append({"option": o, "goes_to": evaluate(tree, tuple(o)), "misconceptions": tags})
            return Problem(
                family="conditional_trace", level=cfg["level"], question_type="find", seed=seed,
                scene={"dice": cfg["dice"], "tree": tree_to_dict(tree), "target": target},
                prompt=f"A game decides where your piece goes by rolling a die {cfg['dice']} times and following "
                       f"the rule below. Which rolls send the piece to {target}?",
                rule_text="\n".join(render_rule(tree)),
                options=options, answer_index=ans, distractors=distractors,
                concepts=concepts_for(cfg),
                explanation=find_explanation(tree, target, correct),
                hints=hints_for(cfg, tree, target),
                knobs={k: cfg[k] for k in ("dice", "depth", "ops", "ties")},
            )
    raise RuntimeError("find generation failed")


def find_explanation(tree, target, correct):
    p = path_to(tree, target)
    need = []
    for c, b in p:
        phrase = f"the {ORDINALS[c.left]} roll {OP_WORDS[c.op]} the {ORDINALS[c.right]} roll"
        need.append(("it must be true that " if b else "it must be FALSE that ") + phrase)
    return ([f"To reach {target}: " + "; and ".join(need) + "."] +
            [f"Check the correct rolls ({', '.join(map(str, correct))}):"] + trace_steps(tree, correct))


def concepts_for(cfg):
    c = ["CONDITIONALS"]
    if cfg["depth"] > 1:
        c.append("NESTED_CONDITIONALS")
    if cfg["ties"] != "none" or cfg["question"] == "find":
        c.append("NEGATION_BOUNDARY")
    return c


def hints_for(cfg, tree, target):
    if cfg["question"] == "trace":
        h = ["Start at the top line and test only that one comparison first.",
             "Write the actual numbers into the test before deciding yes or no."]
        if cfg["ties"] != "none":
            h.append("Two of the rolls are equal. Is 'greater than' true when the numbers are the same?")
        return h
    p = path_to(tree, target)
    h = [f"Which tests must be true, and which must be false, to reach {target}?"]
    if any(not b for _, b in p):
        h.append("If a test must be false, what does that allow? 'Not greater than' includes equal.")
    h.append("Check each option against every test on the path, top to bottom.")
    return h


def path_dice(tree, target):
    return sorted({d for c, _ in path_to(tree, target) for d in ((c.left,) if c.const is not None else (c.left, c.right))})


def m_forgets_free_die(tree, target, n):
    """Counts only over the dice tested on the way to the target; forgets the others can be anything."""
    used = path_dice(tree, target)
    if len(used) == n:
        return None
    sub = 0
    for vals in itertools.product(range(1, 7), repeat=len(used)):
        roll = [1] * n
        for d, v in zip(used, vals):
            roll[d] = v
        if evaluate(tree, roll) == target:
            sub += 1
    return sub


COUNT_EXTRA_MISCONCEPTIONS = {
    "FORGETS_FREE_DIE": {"concept": "COUNTING_DP",
        "description": "Counts only the dice that the tests mention and forgets that an untested die can show any of 6 faces.",
        "remediation": "Ask: does the rule ever look at this die? Then how many faces can it show for each roll you counted?"},
}


def make_count(rng, cfg, seed):
    n = cfg["dice"]
    rolls = all_rolls(n)
    for _ in range(500):
        d = rng.randint(*cfg["depth"])
        outcomes = rng.sample(OUTCOME_POOL, d + 1)
        tree = random_tree(rng, n, d, cfg["ops"], outcomes, const_prob=0.35)
        target = rng.choice(leaves(tree))
        truth = sum(1 for r in rolls if evaluate(tree, r) == target)
        if not 15 <= truth <= 150:
            continue
        if len(path_to(tree, target)) == 1 and rng.random() < 0.75:
            continue          # one-test targets give the same few totals; keep them rare
        vals = {}
        for name, m in MISCONCEPTIONS.items():
            v = sum(1 for r in rolls if m["evaluator"](tree, r, target) == target)
            if v != truth and v > 0:
                vals.setdefault(v, []).append(name)
        v = m_forgets_free_die(tree, target, n)
        if v is not None and v != truth:
            vals.setdefault(v, []).append("FORGETS_FREE_DIE")
        if "TIES_FLIPPED" not in {k for ks in vals.values() for k in ks}:
            continue
        p = path_to(tree, target)
        need = "; and ".join(("" if b else "NOT ") + f"{ORDINALS[c.left]} {OP_WORDS[c.op].removeprefix('is ')} "
                             + (str(c.const) if c.const is not None else ORDINALS[c.right]) for c, b in p)
        expl = [f"To reach {target}: {need}.",
                "Count systematically instead of checking 216 rolls. For two dice, 'first greater than second' "
                "happens in 15 of the 36 pairs, 'equal' in 6, and 'less' in 15. A test against a number, "
                "like 'greater than 4', just limits which faces one die can show.",
                "Fix the dice the tests compare, count the pairs or triples that pass every test on the path, "
                "then multiply by 6 for any die the path never looks at."]
        used = path_dice(tree, target)
        free = [d for d in range(n) if d not in used]
        if free:
            expl.append(f"Here the path never looks at the {', '.join(ORDINALS[d] for d in free)} roll, so multiply by 6.")
        expl.append(f"Total: {truth} of the 216 rolls go to {target}.")
        return Problem(
            family="conditional_trace", level=cfg["level"], question_type="count", seed=seed,
            scene={"dice": n, "tree": tree_to_dict(tree), "target": target},
            prompt=(f"A game decides where your piece goes by rolling a die {n} times and following the rule below. "
                    f"There are 216 possible sets of rolls. How many of them send the piece to {target}?"),
            rule_text="\n".join(render_rule(tree)),
            options=[], answer_index=-1, distractors=[],
            concepts=["CONDITIONALS", "NESTED_CONDITIONALS", "NEGATION_BOUNDARY", "COUNTING_DP"],
            explanation=expl,
            hints=[f"Which tests must be true and which must be false to reach {target}?",
                   "With two dice, how many of the 36 pairs have the first greater than the second? How many are equal?",
                   "Does the path to this place ever look at every die? A die it ignores can be anything."],
            knobs={"dice": n, "depth": d},
            answer_value=truth, entry="number", value_tags={str(v): sorted(k) for v, k in vals.items()},
        )
    raise RuntimeError("count generation failed")


def generate(level, seed):
    cfg = next(c for c in LADDER if c["level"] == level)
    rng = random.Random(seed)
    if cfg["question"] == "count":
        return make_count(rng, cfg, seed)
    return (make_trace if cfg["question"] == "trace" else make_find)(rng, cfg, seed)


if __name__ == "__main__":
    import sys
    lvl = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    p = generate(lvl, seed=int(sys.argv[2]) if len(sys.argv) > 2 else 1)
    print(json.dumps(asdict(p), indent=2, ensure_ascii=False))

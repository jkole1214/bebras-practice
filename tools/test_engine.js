// Tests for engine.js against the real problem bank: answer checking, what the page
// is sent, levels and the tutor detour.
//   node tools/test_engine.js
"use strict";
const path = require("node:path"), assert = require("node:assert/strict");
const E = require(path.join(__dirname, "..", "engine.js"));
const B = E.load(path.join(__dirname, ".."));

let passed = 0;
function test(name, fn) { fn(); passed++; console.log("ok  " + name); }
const all = [];
for (const f of B.fams) for (const l of B.levels[f]) for (const p of B.bank[f][l]) all.push([f, p]);

// a right answer in the shape the page sends, for any problem
function rightAnswer(p) {
  if (p.question_type === "build") { const e = []; for (let i = 0; i < p.answer_path.length - 1; i++) e.push(p.answer_path[i] + "|" + p.answer_path[i + 1]); return { edges: e }; }
  if (p.entry === "press") return { buttons: p.question_type === "fewest" ? fewest(p) : p.answer_value };
  if (p.entry === "cells") return { cells: p.answer_value.map(x => x.join(",")) };
  if (p.entry === "number") return { value: p.answer_value };
  if (p.entry === "code") return { code: p.answer_value };
  if (p.entry === "bricks") return { bricks: { ...p.answer_value } };
  if (p.entry === "hops") return { hops: p.answer_value.slice(1) };
  return { choice: p.answer_index };
}
function subsets(n) { const out = []; for (let m = 0; m < 1 << n; m++) out.push([...Array(n).keys()].filter(i => m >> i & 1).map(i => i + 1)); return out; }
function fewest(p) { return subsets(p.scene.buttons).find(s => s.length === p.answer_value && E.check(p, { buttons: s }).lit); }

test(`all ${all.length} problems load, in ${B.fams.length} puzzle types`, () => {
  assert.equal(B.fams.length, 20);
  assert.ok(all.length >= 1260, String(all.length));
});

test("the right answer is graded right for every problem", () => {
  for (const [f, p] of all) {
    const r = E.check(p, rightAnswer(p));
    assert.ok(r.correct && !r.invalid, `${f} L${p.level}-${p.seed} ${p.question_type}`);
  }
});

test("every tagged distractor and typed wrong value is graded wrong with its tags", () => {
  let n = 0;
  for (const [f, p] of all) {
    const id = `${f} L${p.level}-${p.seed}`;
    if (p.entry === "choice" && p.question_type !== "build") {
      p.options.forEach((o, i) => {
        if (i === p.answer_index) return;
        const r = E.check(p, { choice: i });
        assert.equal(r.correct, false, id);
        assert.ok(r.tags.length, `${id} option ${i} has no tags`); n++;
      });
    }
    if (p.entry === "number") for (const [v, tags] of Object.entries(p.value_tags || {})) {
      const r = E.check(p, { value: +v });
      assert.equal(r.correct, false, id); assert.deepEqual(r.tags, tags, id); n++;
    }
    if (p.entry === "code") for (const [c, tags] of Object.entries(p.value_tags || {})) {
      const r = E.check(p, { code: c });
      assert.equal(r.correct, false, id); assert.deepEqual(r.tags, tags, id); n++;
    }
    if (p.entry === "bricks" && p.question_type === "hidden") for (const [c, tags] of Object.entries(p.value_tags || {})) {
      const r = E.check(p, { bricks: Object.fromEntries(p.scene.edit.map((k, i) => [k, c[i]])) });
      assert.equal(r.correct, false, id); assert.deepEqual(r.tags, tags, id); n++;
    }
    if (p.question_type === "build") for (const [tag, pth] of Object.entries(p.misconception_paths || {})) {
      const e = []; for (let i = 0; i < pth.length - 1; i++) e.push(pth[i] + "|" + pth[i + 1]);
      const r = E.check(p, { edges: e });
      assert.equal(r.correct, false, id); assert.ok(r.tags.includes(tag), id); n++;
    }
    if (p.entry === "cells" && p.question_type !== "fill") for (const [k, tags] of Object.entries(p.cell_tags || {})) {
      const others = p.answer_value.map(x => x.join(",")).filter(c => c !== k).slice(0, p.pick - 1);
      if (others.length !== p.pick - 1 || others.includes(k)) continue;
      const r = E.check(p, { cells: [k, ...others] });
      if (r.correct) continue;
      assert.ok(tags.every(t => r.tags.includes(t)), id); n++;
    }
  }
  assert.ok(n > 1000, String(n));
});

test("pyramids: a wrong brick is tagged from the student's own bricks under it", () => {
  for (const [, p] of all.filter(([, p]) => p.entry === "bricks" && p.question_type === "fill")) {
    const sc = p.scene, low = sc.edit.find(k => k.startsWith("1,")), [, c] = low.split(",").map(Number);
    const x = sc.given[`0,${c}`], y = sc.given[`0,${c + 1}`];
    for (const v of "RYB") {
      if (v === p.answer_value[low]) continue;
      const r = E.check(p, { bricks: { ...p.answer_value, [low]: v } });
      assert.equal(r.correct, false);
      assert.ok(r.tags.includes(x === y ? "MATCH_MEANS_CHANGE" : "COPIES_A_SUPPORT"), `${p.seed} ${low}`);
    }
    assert.ok(E.check(p, { bricks: {} }).invalid);
  }
});

test("frog trips: played back from the start, with dead ends, wrong hops and repeats tagged", () => {
  const trips = all.filter(([, p]) => p.entry === "hops");
  assert.ok(trips.length >= 24);
  for (const [, p] of trips) {
    const sc = p.scene, stones = new Set(sc.stones), seq = p.answer_value.slice(1);
    for (const fwdFirst of [true, false]) {   // always taking the preferred hop gets stuck on some run
      const path = [sc.start];
      for (;;) {
        const at = path[path.length - 1], opts = (fwdFirst ? [at + sc.fwd, at - sc.back] : [at - sc.back, at + sc.fwd]).filter(y => stones.has(y) && !path.includes(y));
        if (!opts.length) break;
        path.push(opts[0]);
      }
      if (path.length < stones.size) assert.deepEqual(E.check(p, { hops: path.slice(1) }).tags, ["STOPS_AT_DEAD_END"]);
    }
    assert.ok(E.check(p, { hops: seq.slice(0, 1) }).invalid || E.check(p, { hops: seq.slice(0, 1) }).tags[0] === "STOPS_AT_DEAD_END");
    assert.deepEqual(E.check(p, { hops: [...seq, sc.start] }).tags, sc.stones.includes(sc.start) && [sc.fwd, -sc.back].includes(sc.start - seq[seq.length - 1]) ? ["LANDS_TWICE"] : ["HOPS_WRONG_SIZE", "LANDS_TWICE"]);
    if (stones.has(sc.start + sc.back)) assert.deepEqual(E.check(p, { hops: [sc.start + sc.back] }).tags, ["SWAPS_HOP_DIRECTIONS"]);
    const water = [...Array(sc.spots).keys()].map(i => i + 1).find(n => !stones.has(n));
    if (water) assert.ok(E.check(p, { hops: [water] }).invalid);
    assert.ok(E.check(p, { hops: [] }).invalid);
  }
});

test("acorn game: the marked answer is best play, worked out again here", () => {
  const acorns = all.filter(([f]) => f === "acorn-game").map(([, p]) => p);
  assert.equal(acorns.length, 60);
  const trail = (t, n) => t[n].turn === "end" ? t[n].acorns
    : (t[n].turn === "you" ? Math.max : Math.min)(...t[n].kids.map(k => trail(t, k)));
  const loses = (n, moves, last) => {
    const L = [last === "wins"];
    for (let x = 1; x <= n; x++) L.push(moves.filter(m => m <= x).every(m => !L[x - m]));
    return L;
  };
  for (const p of acorns) {
    const sc = p.scene;
    if (p.question_type === "path") {
      const v = sc.tree.s.kids.map(k => trail(sc.tree, k));
      assert.equal(p.answer_index, v.indexOf(Math.max(...v)));
      assert.equal(v.filter(x => x === Math.max(...v)).length, 1);
    } else if (p.question_type === "sure") {
      assert.equal(p.answer_value, trail(sc.tree, "s"));
    } else if (p.question_type === "first") {
      const L = loses(sc.pile, sc.moves, sc.last);
      assert.equal(JSON.stringify(sc.moves.filter(m => m <= sc.pile && L[sc.pile - m])), JSON.stringify([p.answer_value]));
    } else {
      const L = loses(sc.upto, sc.moves, "wins");
      assert.equal(JSON.stringify(p.options[p.answer_index]), JSON.stringify([...Array(sc.upto).keys()].map(i => i + 1).filter(x => L[x])));
    }
    assert.ok(!E.publicPuzzle("acorn-game", p).svg.includes("answer"));
  }
});

test("bowl belt: walking the rows here gives the marked answer", () => {
  const bowls = all.filter(([f]) => f === "bowl-belt").map(([, p]) => p);
  assert.equal(bowls.length, 60);
  const walk = (row, d) => {
    const a = [...row], n = a.length, idx = d === "right" ? [...Array(n - 1).keys()] : [...Array(n - 1).keys()].reverse();
    let swaps = 0;
    for (const i of idx) if (a[i] > a[i + 1]) { [a[i], a[i + 1]] = [a[i + 1], a[i]]; swaps++; }
    return { a, swaps };
  };
  const sorted = (r) => r.every((x, i) => i === 0 || r[i - 1] < x);
  const same = (x, y) => JSON.stringify(x) === JSON.stringify(y);
  for (const p of bowls) {
    const sc = p.scene;
    if (p.question_type === "after1" || p.question_type === "afterk") {
      let r = sc.row;
      for (let k = 0; k < (sc.workers || 1); k++) r = walk(r, sc.dir).a;
      assert.ok(same(p.options[p.answer_index], r));
    } else if (p.question_type === "swaps") {
      assert.equal(p.answer_value, walk(sc.row, sc.dir).swaps);
    } else if (p.question_type === "workers") {
      let r = sc.row, k = 0;
      while (!sorted(r)) { r = walk(r, sc.dir).a; k++; }
      assert.equal(p.answer_value, k);
    } else {
      const hits = p.options.filter(o => same(walk(o, sc.dir).a, sc.after));
      assert.equal(hits.length, 1);
      assert.ok(same(hits[0], p.options[p.answer_index]));
    }
    const pub = E.publicPuzzle("bowl-belt", p);
    assert.ok(pub.answer_value === undefined && pub.answer_index === undefined);
  }
});

test("mole tunnels: a search over square and level gives the marked answer", () => {
  const moles = all.filter(([f]) => f === "mole-tunnels").map(([, p]) => p);
  assert.equal(moles.length, 60);
  // Bellman-Ford style relaxation over (level, row, col, climbs); small enough to run to a fixed point.
  const fastest = (sc, kDown, kUp, onlyStay, from = [0, ...sc.start]) => {
    const n = sc.n, L = [sc.upper, sc.lower], key = (l, r, c, m) => `${l},${r},${c},${m}`, d = new Map();
    d.set(key(from[0], from[1], from[2], 0), 0);
    for (let changed = true; changed;) {
      changed = false;
      for (const [k, t] of [...d]) {
        const [l, r, c, m] = k.split(",").map(Number), next = [];
        for (const [dr, dc] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
          const rr = r + dr, cc = c + dc;
          if (rr >= 0 && rr < n && cc >= 0 && cc < n && L[l][rr][cc]) next.push([key(l, rr, cc, m), t + 1]);
        }
        if (!onlyStay && L[0][r][c] && L[1][r][c] && m < 6) next.push([key(1 - l, r, c, m + 1), t + (l === 0 ? kDown : kUp)]);
        for (const [v, tv] of next) if (!d.has(v) || tv < d.get(v)) { d.set(v, tv); changed = true; }
      }
    }
    const byM = {};
    for (const [k, t] of d) { const [l, r, c, m] = k.split(",").map(Number); if (l === sc.goal_level && r === sc.goal[0] && c === sc.goal[1]) byM[m] = t; }
    return byM;
  };
  const best = (o) => Math.min(...Object.values(o));
  const under = (o) => Math.min(...Object.entries(o).filter(([m]) => m >= 2).map(([, t]) => t));
  for (const p of moles) {
    const sc = p.scene;
    if (p.question_type === "limit") {
      const stay = fastest(sc, 1, 1, true)[0];
      let k = 1;
      while (under(fastest(sc, k + 1, k + 1)) < stay) k++;
      assert.ok(under(fastest(sc, k, k)) < stay);
      assert.equal(p.answer_value, k);
    } else if (p.question_type === "where") {
      const t = best(fastest(sc, sc.climb, sc.climb));
      // each letter's trip: walk on top to it, climb down, then the fastest way on to G
      const via = Object.fromEntries(Object.entries(sc.spots).map(([l, [r, c]]) => {
        const walk = fastest({ ...sc, goal: [r, c], goal_level: 0 }, 0, 0, true)[0];
        return [l, walk === undefined ? Infinity : walk + sc.climb + best(fastest(sc, sc.climb, sc.climb, false, [1, r, c]))];
      }));
      const winners = Object.keys(via).filter(l => via[l] === t);
      assert.deepEqual(winners, [p.answer_value]);
      assert.equal(p.options[p.answer_index], p.answer_value);
    } else {
      assert.equal(p.answer_value, best(fastest(sc, sc.climb, sc.climb)));
    }
    const pub = E.publicPuzzle("mole-tunnels", p);
    assert.ok(pub.answer_value === undefined && pub.answer_index === undefined);
  }
});

test("puppy picks: crossing out, greedy counting and following each favourite give the marked answer", () => {
  const pups = all.filter(([f]) => f === "puppy-picks").map(([, p]) => p);
  assert.equal(pups.length, 60);
  // greedy: the first round takes `s` new toys, each later round keeps the winner and takes s - 1 new ones
  const handled = (sizes) => sizes.reduce((t, s, i) => t + (i ? s - 1 : s), 0);
  const reaches = (rounds, t) => {
    const won = new Set();
    rounds.forEach((r, i) => { if (r.includes(t) || r.some(x => x[0] === "W" && won.has(+x.slice(1)))) won.add(i + 1); });
    return won.has(rounds.length);
  };
  for (const p of pups) {
    const sc = p.scene;
    if (p.question_type === "who") {
      const out = new Set(sc.rounds.flatMap(r => r.toys.filter(t => t !== r.grabbed)));
      assert.deepEqual([...sc.toys].filter(t => !out.has(t)), [p.answer_value]);
    } else if (p.question_type === "fewest") {
      let r = 1;
      while (handled(Array(r).fill(sc.k)) < sc.n) r++;
      assert.equal(p.answer_value, r);
    } else if (p.question_type === "plan") {
      const toys = [...Array(sc.n)].map((_, i) => String.fromCharCode(65 + i));
      const ok = [...sc.plans].map(pl => toys.every(t => reaches(pl, t)));
      assert.deepEqual(ok.map((v, i) => v ? i : -1).filter(i => i >= 0), [p.answer_index]);
    } else {
      assert.equal(p.answer_value, handled(sc.sizes));
    }
    const pub = E.publicPuzzle("puppy-picks", p);
    assert.ok(pub.answer_value === undefined && pub.answer_index === undefined);
  }
});

test("round and round: counting one place at a time gives the marked answer", () => {
  const rings = all.filter(([f]) => f === "round-and-round").map(([, p]) => p);
  assert.equal(rings.length, 60);
  // step from a round a ring of 1..n, one place at a time
  const step = (a, k, n) => { let x = a; for (let i = 0; i < k; i++) x = x === n ? 1 : x + 1; return x; };
  const dist = (a, b, n) => { let up = 0; while (step(a, up, n) !== b) up++; return Math.min(up, n - up); };
  for (const p of rings) {
    const sc = p.scene;
    if (p.question_type === "step") {
      assert.equal(p.answer_value, step(sc.start, sc.move, sc.n));
    } else if (p.question_type === "label") {
      const ks = new Set([...sc.lines].map(([a, b]) => dist(a, b, sc.n)));
      assert.deepEqual([...ks], [p.answer_value]);
    } else if (p.question_type === "visits") {
      const seen = new Set([1]);
      for (let x = step(1, sc.k, sc.n); x !== 1; x = step(x, sc.k, sc.n)) seen.add(x);
      assert.equal(p.answer_value, seen.size);
    } else if (p.question_type === "turns") {
      let at = 1, total = 0;
      for (const c of sc.order) { total += dist(at, c, sc.n); at = c; }
      assert.equal(p.answer_value, total);
    } else {
      const next = (c) => c < sc.lead + sc.loop ? c + 1 : sc.lead + 1;
      let slow = 1, fast = 1;
      do { slow = next(slow); fast = next(next(fast)); } while (slow !== fast);
      assert.equal(p.answer_value, slow);
    }
    assert.ok(!(String(p.answer_value) in p.value_tags));
    const pub = E.publicPuzzle("round-and-round", p);
    assert.ok(pub.answer_value === undefined && pub.answer_index === undefined && pub.value_tags === undefined);
  }
});

test("map pieces: replaying each plan gives the stored count, and only the marked last round finishes", () => {
  const play = (names, rounds) => {
    let have = Object.fromEntries(names.map(x => [x, new Set([x[0]])]));
    for (const r of rounds) {
      const next = { ...have };
      for (const [a, b] of r) next[a] = next[b] = new Set([...have[a], ...have[b]]);
      have = next;
    }
    return have;
  };
  const maps = all.filter(([f]) => f === "map-pieces").map(([, p]) => p);
  assert.equal(maps.length, 60);
  for (const p of maps.filter(p => p.question_type === "trace")) {
    assert.equal(play(p.scene.people, p.scene.rounds)[p.scene.ask].size, p.answer_value);
  }
  for (const p of maps.filter(p => p.question_type === "finish")) {
    const n = p.scene.people.length;
    const done = p.options.map(o => Object.values(play(p.scene.people, [...p.scene.rounds, o])).every(s => s.size === n));
    assert.deepEqual(done.map((d, i) => d === (i === p.answer_index)), done.map(() => true));
    assert.ok(!E.publicPuzzle("map-pieces", p).svg.includes("answer"));
  }
});

test("circuits: wrong presses are tagged, and a lit bulb with too many buttons is EXTRA_BUTTONS", () => {
  for (const [, p] of all.filter(([, p]) => p.entry === "press")) {
    const r = E.check(p, { buttons: [] });
    assert.equal(r.correct, false);
    if (p.question_type === "fewest") {
      const more = subsets(p.scene.buttons).find(s => s.length > p.answer_value && E.check(p, { buttons: s }).lit);
      if (more) assert.deepEqual(E.check(p, { buttons: more }).tags, ["EXTRA_BUTTONS"]);
    }
  }
});

test("answers that are not real tries are refused without grading", () => {
  const b = all.find(([, p]) => p.question_type === "build")[1];
  assert.ok(E.check(b, { edges: ["N|A"] }).invalid);
  const c = all.find(([, p]) => p.entry === "cells" && p.question_type !== "fill")[1];
  assert.ok(E.check(c, { cells: [] }).invalid);
  const m = all.find(([, p]) => p.entry === "choice" && p.question_type !== "build")[1];
  assert.ok(E.check(m, { choice: 99 }).invalid);
  assert.ok(E.check(m, null).invalid);
  const v = all.find(([, p]) => p.entry === "number")[1];
  assert.ok(E.check(v, { value: "7" }).invalid);
  const k = all.find(([, p]) => p.entry === "code")[1], kc = k.answer_value;
  assert.ok(E.check(k, { code: kc.slice(1) }).invalid, "too few wheels");
  assert.ok(E.check(k, { code: kc[0].repeat(kc.length) }).invalid, "a symbol used twice");
  assert.ok(E.check(k, { code: "Q".repeat(kc.length) }).invalid, "not a symbol on the wheels");
  assert.ok(E.check(k, {}).invalid);
});

test("the page is never sent an answer, distractor tags or the explanation", () => {
  for (const [f, p] of all) {
    const pub = E.publicPuzzle(f, p), json = JSON.stringify(pub);
    for (const k of ["answer_index", "answer_value", "answer_path", "answer_cost", "optimal_paths", "distractors", "value_tags", "cell_tags", "misconception_paths", "explanation"])
      assert.ok(!(k in pub), `${f} ${k}`);
    assert.ok(!/answer|misconception/i.test(json.replace(/"(prompt|question|hints)":("([^"\\]|\\.)*"|\[[^\]]*\])/g, "")), `${f} L${p.level}-${p.seed}`);
    if (p.entry === "choice" && p.question_type !== "build") assert.deepEqual(pub.options, p.options);
  }
});

test("every misconception tag a wrong answer can carry has a look-again question", () => {
  const tags = new Set(["EXTRA_BUTTONS", "XOR_AS_OR", "BOTH_AS_EITHER", "PARITY_CORNER", "PARITY_ROWS_ONLY", "PARITY_COLS_ONLY",
    "COPIES_A_SUPPORT", "MATCH_MEANS_CHANGE", "STOPS_AT_DEAD_END", "HOPS_WRONG_SIZE", "SWAPS_HOP_DIRECTIONS", "LANDS_TWICE"]);
  for (const [, p] of all) {
    (p.distractors || []).forEach(d => d.misconceptions.forEach(t => tags.add(t)));
    Object.values(p.value_tags || {}).flat().forEach(t => tags.add(t));
    Object.keys(p.misconception_paths || {}).forEach(t => tags.add(t));
    Object.values(p.cell_tags || {}).flat().forEach(t => tags.add(t));
  }
  const missing = [...tags].filter(t => !(B.coach.misconceptions[t] || {}).look_again);
  assert.deepEqual(missing, []);
});

test("look again prefers a question not yet shown on this puzzle, and stays quiet without tags", () => {
  const cur = {};
  const a = E.lookAgain(B, cur, ["SEQUENTIAL_SPREAD", "PROTECTED_SOURCES"]);
  const b = E.lookAgain(B, cur, ["SEQUENTIAL_SPREAD", "PROTECTED_SOURCES"]);
  assert.equal(a, B.coach.misconceptions.SEQUENTIAL_SPREAD.look_again);
  assert.equal(b, B.coach.misconceptions.PROTECTED_SOURCES.look_again);
  assert.equal(E.lookAgain(B, cur, ["SEQUENTIAL_SPREAD", "PROTECTED_SOURCES"]), a);
  assert.equal(E.lookAgain(B, {}, []), null);
  assert.equal(E.lookAgain(B, {}, ["NOT_A_TAG"]), null);
});

const firstTry = (st, correct) => { E.afterFirstTry(B, st, correct, []); };
test("two first-try wins move up a level, two misses move down; off when auto is unchecked", () => {
  const st = E.freshState(B); st.mode = "box-rows";
  E.serve(B, st, []); firstTry(st, true); E.serve(B, st, []); firstTry(st, true);
  assert.equal(st.level["box-rows"], 2);
  E.serve(B, st, []); firstTry(st, false); E.serve(B, st, []); firstTry(st, false);
  assert.equal(st.level["box-rows"], 1);
  st.auto = false;
  E.serve(B, st, []); firstTry(st, true); E.serve(B, st, []); firstTry(st, true);
  assert.equal(st.level["box-rows"], 1);
});

test("a repeated misconception in Practice starts a detour that serves the easier level", () => {
  const st = E.freshState(B); st.level["box-rows"] = 5;
  let t = 1e12;
  const ev = [{ fam: "box-rows", level: 5, correct: false, tags: ["INDIRECTION_OUTSIDE_IN"], t: t++, hints: 0 }];
  E.setCurrent(st, "box-rows", B.bank["box-rows"][5][0], "ladder", "");
  E.afterFirstTry(B, st, false, ev);
  assert.equal(st.tutor.remedy, null);
  ev.push({ fam: "box-rows", level: 5, correct: false, tags: ["INDIRECTION_OUTSIDE_IN"], t: t++, hints: 0 });
  E.setCurrent(st, "box-rows", B.bank["box-rows"][5][1], "ladder", "");
  E.afterFirstTry(B, st, false, ev);
  assert.equal(st.tutor.remedy.level, 3);
  E.serve(B, st, ev);
  assert.deepEqual([st.current.fam, st.current.level, st.current.servedAs], ["box-rows", 3, "remedy"]);
  for (let i = 0; i < 2; i++) { E.afterFirstTry(B, st, true, ev); E.serve(B, st, ev); }
  assert.equal(st.tutor.remedy, null, "two wins end the detour");
});

test("puzzles are not repeated until a level's puzzles run out", () => {
  const st = E.freshState(B); st.mode = "signal-lamp"; st.auto = false;
  const n = B.bank["signal-lamp"][1].length, seeds = new Set();
  for (let i = 0; i < n; i++) { E.serve(B, st, []); seeds.add(st.current.seed); }
  assert.equal(seeds.size, n);
  E.serve(B, st, []);
  assert.ok(seeds.has(st.current.seed));
});

test("old page-owned state keeps levels and tutor plans, and drops the rest", () => {
  const st = E.migrate(B, { fam: "lights-on", lastFam: "lights-on", level: { "lights-on": 4, "box-rows": 99 }, streak: { "lights-on": 1 },
    seen: { "lights-on4": [0, 1] }, log: [{}], tally: { right: 1, total: 2 }, tutor: { remedy: null, ended: { X: 1 }, recent: ["box-rows"] } });
  assert.deepEqual([st.mode, st.level["lights-on"], st.level["box-rows"], st.streak["lights-on"], st.tutor.ended.X], ["lights-on", 4, 1, 1, 1]);
  assert.deepEqual(st.seen, {});
  assert.ok(!("log" in st) && !("tally" in st));
});

console.log(`${passed} passed`);

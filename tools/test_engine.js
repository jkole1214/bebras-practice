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
  return { choice: p.answer_index };
}
function subsets(n) { const out = []; for (let m = 0; m < 1 << n; m++) out.push([...Array(n).keys()].filter(i => m >> i & 1).map(i => i + 1)); return out; }
function fewest(p) { return subsets(p.scene.buttons).find(s => s.length === p.answer_value && E.check(p, { buttons: s }).lit); }

test(`all ${all.length} problems load, in ${B.fams.length} puzzle types`, () => {
  assert.equal(B.fams.length, 13);
  assert.ok(all.length >= 840, String(all.length));
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
    "COPIES_A_SUPPORT", "MATCH_MEANS_CHANGE"]);
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

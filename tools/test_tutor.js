// Tests for tutor.js against the real problem bank.
//   node tools/test_tutor.js
"use strict";
const fs = require("node:fs"), path = require("node:path"), assert = require("node:assert/strict");
const ROOT = path.join(__dirname, "..");
const Tutor = require(path.join(ROOT, "tutor.js"));

// load coach.js and every problem file the way the page does
const bank = {}; let coach;
global.BEBRAS = { coach(d) { coach = d; }, manifest() {}, add(fam, p) { ((bank[fam] = bank[fam] || {})[p.level] = bank[fam][p.level] || []).push(p); } };
require(path.join(ROOT, "coach.js"));
const fams = [...fs.readFileSync(path.join(ROOT, "index.html"), "utf8").matchAll(/data-fam="([a-z-]+)"/g)].map(m => m[1]);
for (const f of fams) for (const file of fs.readdirSync(path.join(ROOT, f))) if (/^L\d+-\d+\.js$/.test(file)) require(path.join(ROOT, f, file));
const X = Tutor.index(bank, coach);

let t = 1e12;
const ev = (fam, level, correct, tags = [], hints = 0) => ({ fam, level, correct, tags, hints, t: (t += 60e3) });
const levelOf = (lv = {}) => (f) => lv[f] || 1;
let passed = 0;
function test(name, fn) { fn(); passed++; console.log("ok  " + name); }

test("every family level has concepts, and live-graded levels can catch their tags", () => {
  for (const f of fams) for (const l of X.order[f]) assert.ok(X.levels[f][l].concepts.length, `${f} L${l}`);
  assert.ok(X.levels["lights-on"][2].tags.XOR_AS_OR >= 0.5);
  assert.ok(X.levels["pantry-map"][5].tags.PARITY_ROWS_ONLY >= 0.5);
});

test("all tags the problems can catch have coach text", () => {
  for (const f of fams) for (const l of X.order[f]) for (const tag of Object.keys(X.levels[f][l].tags))
    assert.ok(coach.misconceptions[tag], `${tag} (${f} L${l}) has no coach entry`);
});

test("no history: every concept is new and the pick is a new family", () => {
  const M = Tutor.model([], X);
  assert.ok(Object.values(M.concepts).every(c => c.status === "new"));
  assert.equal(Tutor.choose(M, X, { levelOf: levelOf() }).kind, "new");
});

test("six clean first tries at Rule Tracer L1 show CONDITIONALS; misses at L1 make it shaky", () => {
  const good = Array.from({ length: 6 }, () => ev("rule-tracer", 1, true));
  assert.equal(Tutor.model(good, X).concepts.CONDITIONALS.status, "shown");
  const bad = Array.from({ length: 4 }, () => ev("rule-tracer", 1, false, ["REVERSED_COMPARISON"]));
  assert.equal(Tutor.model(bad, X).concepts.CONDITIONALS.status, "shaky");
  const hinted = Array.from({ length: 6 }, () => ev("rule-tracer", 1, true, [], 2));
  assert.ok(Tutor.model(hinted, X).concepts.CONDITIONALS.score < Tutor.model(good, X).concepts.CONDITIONALS.score, "hints count for less");
});

test("recent results outweigh old ones", () => {
  const oldBad = [...Array.from({ length: 8 }, () => ev("box-rows", 2, false)), ...Array.from({ length: 8 }, () => ev("box-rows", 2, true))];
  const oldGood = [...Array.from({ length: 8 }, () => ev("box-rows", 2, true)), ...Array.from({ length: 8 }, () => ev("box-rows", 2, false))];
  assert.ok(Tutor.model(oldBad, X).concepts.INDIRECTION.score > Tutor.model(oldGood, X).concepts.INDIRECTION.score);
});

test("repeated INDIRECTION_OUTSIDE_IN at Box Rows L5 steps back to L3", () => {
  const h = [ev("box-rows", 5, false, ["INDIRECTION_OUTSIDE_IN"]), ev("lights-on", 1, true), ev("box-rows", 5, false, ["INDIRECTION_OUTSIDE_IN"])];
  const r = Tutor.remedyFor(Tutor.model(h, X), X, { levelOf: levelOf({ "box-rows": 5 }) });
  assert.deepEqual([r.kind, r.fam, r.level, r.tag], ["easier", "box-rows", 3, "INDIRECTION_OUTSIDE_IN"]);
});

test("one miss is not enough, and a finished detour is not triggered again by the same misses", () => {
  const one = [ev("box-rows", 5, false, ["INDIRECTION_OUTSIDE_IN"])];
  assert.equal(Tutor.remedyFor(Tutor.model(one, X), X, { levelOf: levelOf() }), null);
  const h = [ev("box-rows", 5, false, ["INDIRECTION_OUTSIDE_IN"]), ev("box-rows", 5, false, ["INDIRECTION_OUTSIDE_IN"])];
  const ended = { INDIRECTION_OUTSIDE_IN: h[0].t };
  assert.equal(Tutor.remedyFor(Tutor.model(h, X), X, { levelOf: levelOf(), ended }), null);
});

test("SKIPS_OUTER_TEST at Rule Tracer L2 (no easier level catches it) goes back to the prerequisite CONDITIONALS", () => {
  const h = [ev("rule-tracer", 2, false, ["SKIPS_OUTER_TEST"]), ev("rule-tracer", 2, false, ["SKIPS_OUTER_TEST"])];
  const r = Tutor.remedyFor(Tutor.model(h, X), X, { levelOf: levelOf({ "rule-tracer": 2 }) });
  assert.deepEqual([r.kind, r.prereq, r.fam, r.level], ["prereq", "CONDITIONALS", "rule-tracer", 1]);
});

test("a family whose cross-family prerequisite is not shown is picked less often", () => {
  // Pantry Map tests ELIMINATION, which needs BOOLEAN_AND (Lights On); both families tried once
  const base = [ev("pantry-map", 1, false), ev("lights-on", 1, false), ev("rule-tracer", 1, true)];
  const shown = base.concat(Array.from({ length: 8 }, () => ev("lights-on", 5, true)));
  const share = (h) => {
    const M = Tutor.model(h, X); let n = 0, seed = 1;
    const random = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < 2000; i++) if (Tutor.choose(M, X, { levelOf: levelOf(), random }).fam === "pantry-map") n++;
    return n;
  };
  assert.ok(share(base) < share(shown), `${share(base)} vs ${share(shown)}`);
});

test("simulated student: varied sessions, never three in a row, review shows up once things are shown", () => {
  let seed = 7; const random = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const lv = {}, recent = [], events = [], kinds = {};
  let run = 1, maxRun = 1;
  for (let i = 0; i < 400; i++) {
    const M = Tutor.model(events, X);
    const c = Tutor.choose(M, X, { levelOf: levelOf(lv), recentFams: recent, now: t, random });
    kinds[c.kind] = (kinds[c.kind] || 0) + 1;
    if (recent.length && recent[recent.length - 1] === c.fam) run++; else run = 1;
    maxRun = Math.max(maxRun, run);
    recent.push(c.fam);
    const p = 0.95 - 0.08 * (c.level - 1);          // harder levels are missed more
    const ok = random() < p;
    events.push(ev(c.fam, c.level, ok, ok ? [] : Object.keys(X.levels[c.fam][c.level].tags).slice(0, 1)));
    if (ok && random() < 0.5) lv[c.fam] = Math.min((lv[c.fam] || 1) + 1, X.order[c.fam].slice(-1)[0]);
    if (!ok && random() < 0.5) lv[c.fam] = Math.max((lv[c.fam] || 1) - 1, 1);
    t += 3 * 3600e3;                                // spread over weeks
  }
  assert.ok(maxRun <= 2, "max run " + maxRun);
  assert.equal(new Set(recent).size, fams.length, "every family came up");
  assert.ok(kinds.review > 0, JSON.stringify(kinds));
  if (process.env.VERBOSE) console.log(kinds, recent.slice(0, 30).join(" "));
});

test("why lines are short and never empty", () => {
  for (const kind of ["easier", "prereq", "again", "review", "new", "practice"]) {
    const s = Tutor.why({ kind, fam: "box-rows", prereq: "CONDITIONALS", concepts: ["INDIRECTION"] }, coach);
    assert.ok(s.length > 10 && s.length < 120, s);
  }
});

console.log(`${passed} passed`);

// The practice engine, run by server.js (never served to the page).
//
// It holds the problem bank, checks answers, moves levels and runs the tutor
// (tutor.js) for each student, so answer keys never reach the browser. The page
// gets a puzzle without its answer, sends each try here, and asks for the next one.
//
//   load(root)           reads coach.js and every problem file once, at startup
//   freshState / migrate  the per-student state kept in the progress table
//   serve(st, events, o)  picks the next puzzle (tutor in Practice mode, the ladder otherwise)
//   check(p, answer)      grades one try: right or wrong, the misconceptions it shows
//   afterFirstTry(...)    moves levels and starts or ends a tutor detour
//   progressView(...)     what the Progress page shows, computed from the answers

"use strict";
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const Tutor = require("./tutor.js");

const PRACTICE = "practice";

function load(root) {
  // the puzzle types, in the order the page lists them
  const fams = [...fs.readFileSync(path.join(root, "index.html"), "utf8").matchAll(/data-fam="([a-z-]+)"/g)].map(m => m[1]);
  let coach = null;
  const bank = {}, byKey = new Map(), files = {};
  const sandbox = { BEBRAS: { coach(d) { coach = d; }, manifest(f, list) { files[f] = list; }, add(fam, p) { ((bank[fam] = bank[fam] || {})[p.level] = bank[fam][p.level] || []).push(p); byKey.set(`${fam}|${p.level}|${p.seed}`, p); } } };
  vm.createContext(sandbox);
  vm.runInContext(fs.readFileSync(path.join(root, "coach.js"), "utf8"), sandbox);
  for (const f of fams) {
    bank[f] = {};
    // each folder's manifest.js (written by tools/build_problems.py) lists its problem files
    vm.runInContext(fs.readFileSync(path.join(root, f, "manifest.js"), "utf8"), sandbox);
    for (const file of files[f] || []) {
      if (/^L\d+-\d+\.js$/.test(file)) vm.runInContext(fs.readFileSync(path.join(root, f, file), "utf8"), sandbox);
    }
  }
  if (!coach) throw new Error("coach.js did not load");
  const X = Tutor.index(bank, coach);
  const levels = Object.fromEntries(fams.map(f => [f, Object.keys(bank[f]).map(Number).sort((a, b) => a - b)]));
  return { fams, bank, coach, X, levels, problem: (fam, level, seed) => byKey.get(`${fam}|${level}|${seed}`) || null };
}

// ---------- per-student state
function freshState(B) {
  return {
    v: 2, mode: PRACTICE, lastFam: null, auto: true,
    level: Object.fromEntries(B.fams.map(f => [f, B.levels[f][0]])),
    streak: Object.fromEntries(B.fams.map(f => [f, 0])), misses: Object.fromEntries(B.fams.map(f => [f, 0])),
    seen: {}, tutor: { remedy: null, ended: {}, recent: [] }, current: null
  };
}
// Keeps levels, streaks and tutor plans from older saved states (the page used to own this state).
function migrate(B, saved) {
  const st = freshState(B);
  if (!saved || typeof saved !== "object") return st;
  const fam = saved.mode || saved.fam;
  st.mode = fam === PRACTICE || B.fams.includes(fam) ? fam : PRACTICE;
  st.lastFam = B.fams.includes(saved.lastFam) ? saved.lastFam : null;
  st.auto = saved.auto !== false;
  for (const f of B.fams) {
    const lv = saved.level && saved.level[f];
    if (B.levels[f].includes(lv)) st.level[f] = lv;
    st.streak[f] = Number.isInteger(saved.streak && saved.streak[f]) ? saved.streak[f] : 0;
    st.misses[f] = Number.isInteger(saved.misses && saved.misses[f]) ? saved.misses[f] : 0;
  }
  if (saved.tutor && typeof saved.tutor === "object") st.tutor = { remedy: saved.tutor.remedy || null, ended: saved.tutor.ended || {}, recent: saved.tutor.recent || [] };
  // seen used to hold list positions; now it holds seeds
  if (saved.v === 2) { st.seen = saved.seen || {}; st.current = saved.current || null; }
  return st;
}

// ---------- choosing a puzzle
// preferTag: during a tutor detour, only problems that can catch that misconception
function pick(B, st, fam, level, preferTag) {
  const list = (B.bank[fam] || {})[level] || [];
  if (!list.length) return null;
  const key = fam + "|" + level, seen = st.seen[key] || [];
  const fits = list.filter(p => !preferTag || Tutor.problemTags(p).has(preferTag));
  const all = fits.length ? fits : list;
  let pool = all.filter(p => !seen.includes(p.seed));
  if (!pool.length) { st.seen[key] = seen.filter(s => !all.some(p => p.seed === s)); pool = all; }
  const p = pool[Math.floor(Math.random() * pool.length)];
  st.seen[key] = (st.seen[key] || []).concat(p.seed);
  return p;
}

function setCurrent(st, fam, p, servedAs, why) {
  st.current = { fam, level: p.level, seed: p.seed, servedAs, why, tries: 0, hints: 0, solved: false, shownAt: Date.now() };
}

// events: this student's first tries, oldest first, in the shape tutor.js reads
function serve(B, st, events) {
  if (st.mode === PRACTICE) {
    const r = st.tutor.remedy;
    let p = r && B.bank[r.fam] && B.bank[r.fam][r.level] ? pick(B, st, r.fam, r.level, r.tag) : null;
    if (p) setCurrent(st, r.fam, p, "remedy", Tutor.why(r, B.coach));
    else {
      st.tutor.remedy = null;
      const c = Tutor.choose(Tutor.model(events, B.X), B.X, { levelOf: f => st.level[f], recentFams: st.tutor.recent });
      p = pick(B, st, c.fam, c.level);
      setCurrent(st, c.fam, p, "ladder", Tutor.why(c, B.coach));
    }
    st.tutor.recent = st.tutor.recent.concat(st.current.fam).slice(-10);
  } else {
    const fam = st.mode;
    setCurrent(st, fam, pick(B, st, fam, st.level[fam]), "ladder", "");
  }
}

// A puzzle as the page gets it: everything needed to draw it, nothing that gives the answer away.
const SCENE_KEYS = { conveyor: ["belt"], pointer_lists: ["lists"], bead_grammar: ["kind", "start", "rules"], parity_grid: ["rows", "cols", "marks", "editable"], code_clues: ["slots", "pool", "clues"], brick_rule: ["rows", "edit"] };
function publicPuzzle(fam, p) {
  const out = { fam, family: p.family, level: p.level, seed: p.seed, question_type: p.question_type, entry: p.entry,
    prompt: p.prompt, hints: p.hints || [], concepts: p.concepts || [] };
  for (const k of ["question", "svg", "rule_text", "codebook", "signal", "pick"]) if (p[k] !== undefined) out[k] = p[k];
  if (p.entry === "choice" && p.question_type !== "build") out.options = p.options;
  const keys = SCENE_KEYS[p.family];
  if (keys && p.scene) out.scene = Object.fromEntries(keys.filter(k => p.scene[k] !== undefined).map(k => [k, p.scene[k]]));
  return out;
}

// ---------- checking answers
const routeText = (path) => path.map(x => x === "N" ? "north shore" : x === "S" ? "south shore" : x).join(" → ");
function edgeSet(path) { const s = new Set(); for (let i = 0; i < path.length - 1; i++) s.add([path[i], path[i + 1]].sort().join("|")); return s; }
const sameSet = (a, b) => a.size === b.size && [...a].every(x => b.has(x));
function gateEval(node, on, swap) {
  if (node.in !== undefined) return on.has(node.in);
  const a = gateEval(node.kids[0], on, swap), b = gateEval(node.kids[1], on, swap);
  let op = node.op;
  if (swap && op === swap[0]) op = swap[1];
  return op === "AND" ? a && b : op === "XOR" ? a !== b : a || b;
}

// answer shapes: { choice: i } | { value: n } | { edges: ["A|B", ...] } | { buttons: [1, 2] } | { cells: ["r,c", ...] } | { code: "SMT" } | { bricks: { "r,c": "R" } }
// Returns { invalid: message } for an answer that is not a real try (it does not count),
// otherwise { correct, tags, stored } plus { lit } for circuits. stored is what goes in the attempts table.
function check(p, a) {
  a = a && typeof a === "object" ? a : {};
  if (p.question_type === "build") {
    const sub = new Set((Array.isArray(a.edges) ? a.edges : []).slice(0, 100).map(k => String(k).split("|").sort().join("|")));
    const deg = {}; sub.forEach(k => k.split("|").forEach(n => deg[n] = (deg[n] || 0) + 1));
    let ok = deg.N === 1 && deg.S === 1 && Object.entries(deg).every(([n, d]) => (n === "N" || n === "S") ? d === 1 : d === 2);
    if (ok) {   // the degree test alone allows a separate loop of islands
      const adj = {}; sub.forEach(k => { const [x, y] = k.split("|"); (adj[x] = adj[x] || []).push(y); (adj[y] = adj[y] || []).push(x); });
      const seen = new Set(["N"]), stack = ["N"];
      while (stack.length) { const u = stack.pop(); (adj[u] || []).forEach(v => { if (!seen.has(v)) { seen.add(v); stack.push(v); } }); }
      ok = seen.size === Object.keys(deg).length;
    }
    if (!sub.size || !ok) return { invalid: "That is not one complete crossing yet. Pick walkways that make a single unbroken line from the north shore to the south shore." };
    const correct = sameSet(sub, edgeSet(p.answer_path));
    const tags = correct ? [] : Object.entries(p.misconception_paths || {}).filter(([, path]) => sameSet(sub, edgeSet(path))).map(([k]) => k);
    return { correct, tags, stored: [...sub] };
  }
  if (p.entry === "press") {
    const on = new Set((Array.isArray(a.buttons) ? a.buttons : []).filter(Number.isInteger));
    const tree = p.scene.tree, lit = gateEval(tree, on);
    const correct = lit && (p.question_type !== "fewest" || on.size === p.answer_value);
    let tags = [];
    if (!correct) {
      if (lit) tags = ["EXTRA_BUTTONS"];
      else {
        if (gateEval(tree, on, ["XOR", "OR"])) tags.push("XOR_AS_OR");
        if (gateEval(tree, on, ["AND", "OR"])) tags.push("BOTH_AS_EITHER");
      }
    }
    return { correct, tags, lit, stored: [...on].sort((x, y) => x - y) };
  }
  if (p.entry === "cells") {
    const fill = p.question_type === "fill", sc = p.scene;
    const valid = (k) => /^\d+,\d+$/.test(k) && +k.split(",")[0] < sc.rows && +k.split(",")[1] < sc.cols;
    const sel = new Set((Array.isArray(a.cells) ? a.cells : []).map(String).filter(valid));
    if (fill) { const ed = new Set((sc.editable || []).map(x => x.join(","))); [...sel].forEach(k => { if (!ed.has(k)) sel.delete(k); }); }
    if (!fill && sel.size !== p.pick) return { invalid: `Choose ${p.pick} shel${p.pick > 1 ? "ves" : "f"} first.` };
    const want = new Set(p.answer_value.map(x => x.join(",")));
    const correct = sameSet(sel, want);
    let tags = [];
    if (!correct && !fill) tags = [...new Set([...sel].flatMap(k => (p.cell_tags || {})[k] || []))];
    if (!correct && fill) {
      const g = Array.from({ length: sc.rows }, () => Array(sc.cols).fill(0));
      sc.marks.forEach(([r, c]) => g[r][c] = 1);
      sel.forEach(k => { const [r, c] = k.split(",").map(Number); g[r][c] = 1; });
      const rowsEven = g.every(row => row.reduce((x, y) => x + y) % 2 === 0);
      const colsEven = g[0].every((_, c) => g.reduce((x, row) => x + row[c], 0) % 2 === 0);
      const corner = (sc.rows - 1) + "," + (sc.cols - 1);
      const offByCorner = [...want].filter(k => k !== corner).every(k => sel.has(k)) && [...sel].filter(k => k !== corner).every(k => want.has(k));
      if (offByCorner) tags = ["PARITY_CORNER"];
      else if (rowsEven && !colsEven) tags = ["PARITY_ROWS_ONLY"];
      else if (colsEven && !rowsEven) tags = ["PARITY_COLS_ONLY"];
    }
    return { correct, tags, stored: [...sel].sort() };
  }
  if (p.entry === "bricks") {
    const sc = p.scene, got = a.bricks && typeof a.bricks === "object" ? a.bricks : {}, vals = {};
    for (const k of sc.edit) {
      if (!["R", "Y", "B"].includes(got[k])) return { invalid: p.question_type === "fill" ? "Colour every empty brick first. Tap a brick to change its colour." : "Tap each hidden brick to choose its colour first." };
      vals[k] = got[k];
    }
    const correct = sc.edit.every(k => vals[k] === p.answer_value[k]), stored = sc.edit.map(k => vals[k]).join("");
    let tags = [];
    if (!correct && p.question_type === "fill") {   // judge each wrong brick by the student's own two bricks under it
      const col = { ...sc.given, ...vals }, t = new Set();
      for (const k of sc.edit) {
        const [r, c] = k.split(",").map(Number), x = col[`${r - 1},${c}`], y = col[`${r - 1},${c + 1}`];
        const want = x === y ? x : "RYB".replace(x, "").replace(y, "");
        if (vals[k] !== want) t.add(x === y ? "MATCH_MEANS_CHANGE" : "COPIES_A_SUPPORT");
      }
      tags = [...t];
    } else if (!correct) tags = (p.value_tags || {})[stored] || [];
    return { correct, tags, stored };
  }
  if (p.entry === "code") {
    const sc = p.scene, code = typeof a.code === "string" ? a.code : "";
    if (code.length !== sc.slots || ![...code].every(ch => sc.pool.includes(ch))) return { invalid: "Put a symbol on every wheel first." };
    if (new Set(code).size !== code.length) return { invalid: "The code uses a different symbol on each wheel." };
    const correct = code === p.answer_value;
    return { correct, tags: correct ? [] : ((p.value_tags || {})[code] || []), stored: code };
  }
  if (p.entry === "number") {
    if (typeof a.value !== "number" || !Number.isFinite(a.value)) return { invalid: "Type a whole number, then press Check." };
    const v = Math.round(a.value), correct = v === p.answer_value;
    return { correct, tags: correct ? [] : ((p.value_tags || {})[String(v)] || []), stored: v };
  }
  const i = a.choice;
  if (!Number.isInteger(i) || i < 0 || i >= p.options.length) return { invalid: "Pick one of the answers." };
  const correct = i === p.answer_index, o = p.options[i];
  let tags = [];
  if (!correct) {
    const d = (p.distractors || []).find(d => JSON.stringify(d.option) === JSON.stringify(o) || (p.question_type === "compare" && routeText(d.option) === o));
    tags = d ? d.misconceptions : [];
  }
  return { correct, tags, stored: { choice: i, option: o } };
}

// ---------- after a first try
// Two first-try wins move up a level and two misses move down (on the student's own ladder only).
// In Practice mode a repeated misconception starts a short detour; a detour ends after two wins or four puzzles.
function afterFirstTry(B, st, correct, events) {
  const cur = st.current, fam = cur.fam;
  if (cur.servedAs === "ladder") {
    if (correct) { st.streak[fam]++; st.misses[fam] = 0; } else { st.misses[fam]++; st.streak[fam] = 0; }
    if (st.mode === PRACTICE || st.auto) {
      const lv = B.levels[fam], max = lv[lv.length - 1], min = lv[0];
      if (st.streak[fam] >= 2 && st.level[fam] < max) { st.level[fam] = lv[lv.indexOf(st.level[fam]) + 1]; st.streak[fam] = 0; }
      if (st.misses[fam] >= 2 && st.level[fam] > min) { st.level[fam] = lv[lv.indexOf(st.level[fam]) - 1]; st.misses[fam] = 0; }
    }
  }
  if (st.mode !== PRACTICE) return;
  const t = st.tutor;
  if (cur.servedAs === "remedy" && t.remedy) {
    t.remedy.served = (t.remedy.served || 0) + 1;
    if (correct) t.remedy.right = (t.remedy.right || 0) + 1;
    if (t.remedy.right >= 2 || t.remedy.served >= 4) { t.ended[t.remedy.tag] = Date.now(); t.remedy = null; }
  } else if (!correct && cur.servedAs === "ladder") {
    const plan = Tutor.remedyFor(Tutor.model(events, B.X), B.X, { levelOf: f => st.level[f], ended: t.ended });
    if (plan) t.remedy = { ...plan, served: 0, right: 0, started: Date.now() };
  }
}

// ---------- the Progress page
const place = (x) => x === "N" ? "north shore" : x === "S" ? "south shore" : x;
const SYMBOL = { S: "sun", M: "moon", T: "star", H: "heart", L: "leaf", D: "drop", Z: "bolt", B: "bell" };
const BRICK = { R: "red", Y: "yellow", B: "blue" };
const brickText = (p, s) => p.question_type === "fill"
  ? `${[...String(s)].filter((v, i) => v !== p.answer_value[p.scene.edit[i]]).length} of ${p.scene.edit.length} bricks wrong`
  : [...String(s)].map(v => BRICK[v] || v).join(", ");
const codeText = (c) => [...String(c)].map(ch => SYMBOL[ch] || ch).join(", ");
const cellName = (k) => { const [r, c] = String(k).split(",").map(Number); return `row ${r + 1}, column ${c + 1}`; };
function optionText(o) {
  if (Array.isArray(o)) return o.every(v => typeof v === "number") ? o.join(", ") : o.map(place).join(" → ");
  return String(o);
}
function answerText(p, a) {
  if (a === null || a === undefined) return "not recorded";
  if (typeof a === "number") return String(a);
  if (p.family === "code_clues") return codeText(typeof a === "string" ? a : a.option);
  if (p.entry === "bricks") return brickText(p, a);
  if (a && a.option !== undefined) return p.family === "logic_gates" ? (a.option.length ? "buttons " + a.option.join(", ") : "nobody") : optionText(a.option);
  if (Array.isArray(a)) {
    if (p.question_type === "build") return "walkways " + a.map(k => k.split("|").map(place).join("–")).join(", ");
    if (p.entry === "press") return a.length ? "buttons " + a.join(", ") : "no buttons";
    if (p.entry === "cells") return a.map(cellName).join("; ") || "nothing";
  }
  return JSON.stringify(a);
}
function rightText(p) {
  if (p.question_type === "build") return (p.answer_path || []).map(place).join(" → ");
  if (p.entry === "press") return p.question_type === "fewest" ? `any ${p.answer_value} buttons that light the bulb` : "any buttons that light the bulb";
  if (p.entry === "cells") return (p.answer_value || []).map(x => cellName(x.join(","))).join("; ");
  if (p.entry === "number") return String(p.answer_value);
  if (p.family === "code_clues") return codeText(p.answer_value);
  if (p.entry === "bricks") return p.question_type === "fill" ? "every brick by the rule" : brickText(p, p.scene.edit.map(k => p.answer_value[k]).join(""));
  const o = p.options[p.answer_index];
  return p.family === "logic_gates" ? (o.length ? "buttons " + o.join(", ") : "nobody") : optionText(o);
}

// tries: this student's tries (not look-backs), oldest first: { fam, level, seed, try, correct, answer, tags, hints, ms, t }
// showAnswers: also give the right answer for puzzles the student never solved (parents get it; kids only once solved)
function progressView(B, st, tries, showAnswers) {
  const list = [];   // one record per puzzle shown
  tries.forEach(a => {
    if (a.try === 1) list.push({ fam: a.fam, level: a.level, seed: a.seed, t: a.t, tries: [a] });
    else for (let i = list.length - 1; i >= Math.max(0, list.length - 5); i--) {
      const x = list[i];
      if (x.fam === a.fam && x.level === a.level && x.seed === a.seed) { x.tries.push(a); break; }
    }
  });
  const events = list.map(i => ({ fam: i.fam, level: i.level, correct: i.tries[0].correct, tags: i.tries[0].tags || [], hints: i.tries[0].hints || 0, t: i.t }));
  const M = Tutor.model(events, B.X);
  const right = events.filter(e => e.correct).length;
  const concepts = [...B.X.covered].map(c => { const m = M.concepts[c]; return { id: c, status: m.status, score: m.score, n: m.n, right: m.right }; });
  const focus = concepts.filter(c => c.status === "shaky" || c.status === "learning").sort((a, b) => a.score - b.score).slice(0, 3).map(c => c.id);
  const tags = Object.values(M.tags).sort((a, b) => b.weight - a.weight).slice(0, 6).map(t => ({ id: t.id, count: t.count, last: t.last }));
  const missed = list.filter(i => !i.tries[0].correct).reverse().slice(0, 200).map(i => {
    const p = B.problem(i.fam, i.level, i.seed), last = i.tries[i.tries.length - 1];
    return { fam: i.fam, level: i.level, seed: i.seed, t: i.t, tags: i.tries[0].tags || [], tries: i.tries.length, solved: last.correct,
      available: !!p, first: p ? answerText(p, i.tries[0].answer) : null, right: p && (last.correct || showAnswers) ? rightText(p) : null };
  });
  const grid = {};
  list.forEach(i => { const k = i.fam + "|" + i.level, c = grid[k] = grid[k] || { n: 0, r: 0, ms: 0, hints: 0 };
    c.n++; if (i.tries[0].correct) c.r++; c.ms += Math.min(15 * 60e3, i.tries[i.tries.length - 1].ms || 0); if (i.tries[0].hints) c.hints++; });
  return {
    puzzles: list.length, right, week: events.filter(e => e.t > Date.now() - 7 * 864e5).length,
    ms: list.reduce((s, i) => s + Math.min(15 * 60e3, Math.max(0, ...i.tries.map(t => t.ms || 0))), 0),
    remedy: st.tutor.remedy, focus, concepts, tags, missed, grid, levels: B.levels
  };
}

// ---------- look again
// After a wrong try with misconception tags: one short question for the student about the likely
// mistake. Prefers a tag whose question has not been shown on this puzzle yet. Notes it in cur.looked.
function lookAgain(B, cur, tags) {
  const M = B.coach.misconceptions, have = (tags || []).filter(t => M[t] && M[t].look_again);
  if (!have.length) return null;
  cur.looked = cur.looked || [];
  const tag = have.find(t => !cur.looked.includes(t)) || have[0];
  if (!cur.looked.includes(tag)) cur.looked.push(tag);
  return M[tag].look_again;
}

module.exports = { PRACTICE, load, freshState, migrate, serve, setCurrent, publicPuzzle, check, afterFirstTry, lookAgain, progressView };

// Bebras Practice: loads problem files from each family folder (FAMS),
// then runs the practice loop. Works from file:// (no server needed) because
// problem files are loaded as <script> tags that call BEBRAS.add(...).

const FACES = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"];
const FAMS = ["rule-tracer", "lake-crossing", "signal-lamp", "robot-routes", "nuts-and-bolts", "box-rows", "lights-on", "bead-rules", "pantry-map"];
const FLASH = { S: "\u25cf", L: "\u25ac" };
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
};

let DATA, state, cur = null, tries = 0, hintsShown = 0, solved = false, selected = new Set(), lastTags = [];

function loadScript(src) {
  return new Promise((resolve) => {
    const s = document.createElement("script");
    s.src = src; s.onload = () => resolve(true); s.onerror = () => resolve(false);
    document.head.appendChild(s);
  });
}

async function loadAll() {
  const missing = [];
  for (const fam of FAMS) {
    const files = BEBRAS.files[fam];
    if (!files) { missing.push(`${fam}/manifest.js`); continue; }
    const results = await Promise.all(files.map(f => loadScript(`${fam}/${f}`)));
    results.forEach((ok, i) => { if (!ok) missing.push(`${fam}/${files[i]}`); });
  }
  const bank = {};
  for (const fam of FAMS) {
    bank[fam] = {};
    (BEBRAS.problems[fam] || []).forEach(p => { (bank[fam][p.level] = bank[fam][p.level] || []).push(p); });
  }
  return { bank, missing };
}

function defaultState() {
  return {
    fam: "rule-tracer", level: Object.fromEntries(FAMS.map(f => [f, 1])),
    streak: Object.fromEntries(FAMS.map(f => [f, 0])), misses: Object.fromEntries(FAMS.map(f => [f, 0])),
    seen: {}, done: {}, log: [], tally: { right: 0, total: 0 }, misconceptionCounts: {}
  };
}
function save() { store.set("bebras-practice-local", state); }
function levels(fam) { return Object.keys(DATA.bank[fam]).map(Number).sort((a, b) => a - b); }

function pick(fam, level) {
  const list = DATA.bank[fam][level] || [];
  const key = fam + level, seen = state.seen[key] || [];
  let pool = list.map((p, i) => i).filter(i => !seen.includes(i));
  if (!pool.length) { state.seen[key] = []; pool = list.map((p, i) => i); }
  const i = pool[Math.floor(Math.random() * pool.length)];
  state.seen[key] = (state.seen[key] || []).concat(i);
  return list[i];
}

function renderTabs() {
  document.querySelectorAll(".tab").forEach(t => t.setAttribute("aria-selected", t.dataset.fam === state.fam));
  const rungs = $("#rungs"); rungs.innerHTML = "";
  levels(state.fam).forEach(i => {
    const b = document.createElement("button");
    b.className = "rung" + (i === state.level[state.fam] ? " on" : "") + ((state.done[state.fam + i] || 0) >= 2 ? " done" : "");
    b.textContent = i; b.title = (DATA.coach.ladders[state.fam] || [])[i - 1] || "";
    b.addEventListener("click", () => { state.level[state.fam] = i; state.streak[state.fam] = 0; state.misses[state.fam] = 0; save(); next(); });
    rungs.appendChild(b);
  });
}

function ruleHTML(text) {
  return esc(text).replace(/\b(IF|THEN|ELSE)\b/g, '<span class="k">$1</span>').replace(/go to (the [a-z]+)/g, 'go to <span class="o">$1</span>');
}
function flashHTML(code) {
  return `<span class="flashes" aria-label="${code.split("").map(c => c === "S" ? "short" : "long").join(" ")}">${code.split("").map(c => `<span class="fl fl-${c}">${FLASH[c]}</span>`).join("")}</span>`;
}
// Nuts and Bolts: one drawn part per token. n/b small nut/bolt, N/B big ones.
function partSVG(t) {
  const big = t === "N" || t === "B", s = big ? 1 : 0.72, cls = big ? "pt big" : "pt";
  const body = (t === "n" || t === "N")
    ? `<polygon points="12,2 21,7 21,17 12,22 3,17 3,7" class="nut"/><circle cx="12" cy="12" r="4" class="hole"/>`
    : `<rect x="4" y="2" width="16" height="6" rx="1.5" class="bolt"/><rect x="9" y="8" width="6" height="14" class="bolt"/>`
      + `<path d="M9 11h6M9 14h6M9 17h6M9 20h6" class="thread"/>`;
  const name = { n: "small nut", b: "small bolt", N: "big nut", B: "big bolt" }[t];
  return `<svg class="${cls}" viewBox="0 0 24 24" width="${Math.round(30 * s)}" height="${Math.round(30 * s)}" role="img" aria-label="${name}">${body}</svg>`;
}
function beltHTML(belt, numbered) {
  return `<div class="belt">${belt.split("").map((t, i) => `<span class="part">${partSVG(t)}${numbered ? `<span class="pi">${i + 1}</span>` : ""}</span>`).join("")}</div>`;
}
// Box Rows: each row with its letter, box numbers above, values inside.
function rowsHTML(lists) {
  const rows = Object.entries(lists).map(([name, vals]) =>
    `<tr><th scope="row">${esc(name)}</th>${vals.map(v => `<td>${v}</td>`).join("")}</tr>`).join("");
  const n = Object.values(lists)[0].length;
  return `<table class="boxrows"><thead><tr><th></th>${Array.from({ length: n }, (_, i) => `<th>${i + 1}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table>`;
}
// Bead Rules: beads (necklace) and magic objects (wizard).
const BEAD = { r: ["#d9534f", "red"], b: ["#3b6fd8", "blue"], y: ["#e8b600", "yellow"], g: ["#2e9e5b", "green"], p: ["#8e44ad", "purple"] };
function tokenSVG(ch) {
  if (BEAD[ch]) return `<svg class="bead" viewBox="0 0 24 24" width="24" height="24" role="img" aria-label="${BEAD[ch][1]} bead"><circle cx="12" cy="12" r="10" fill="${BEAD[ch][0]}"/><text x="12" y="16.5" text-anchor="middle">${ch.toUpperCase()}</text></svg>`;
  const shape = {
    X: ['diamond', '<polygon points="12,2 22,12 12,22 2,12" class="ob-x"/>'],
    Y: ['coin', '<circle cx="12" cy="12" r="10" class="ob-y"/><circle cx="12" cy="12" r="5" class="ob-yi"/>'],
    a: ['potion', '<path d="M9 2h6v5l5 13H4L9 7z" class="ob-a"/>'],
    c: ['dragon', '<path d="M3 20 8 6l4 6 4-8 5 16z" class="ob-c"/>'] }[ch];
  return `<svg class="bead" viewBox="0 0 24 24" width="26" height="26" role="img" aria-label="${shape[0]}">${shape[1]}</svg>`;
}
function tokensHTML(str) { return `<span class="tokens">${str.split("").map(tokenSVG).join("")}</span>`; }
function grammarHTML(sc) {
  const rule = (r) => sc.kind === "wizard"
    ? `<li>${tokensHTML(r[0])}<span class="arrow">→</span>${tokensHTML(r[1])}</li>`
    : `<li>${{ R: "Add " + tokensHTML(r[1]) + " to the <b>right</b> end",
              L: "Add " + tokensHTML(r[1]) + " to the <b>left</b> end",
              W: "Put one " + tokensHTML(r[1]) + " at <b>each</b> end" }[r[0]]}</li>`;
  return `<div class="grammar"><div class="nums">${sc.kind === "wizard" ? "Start with" : "Start"}</div>${tokensHTML(sc.start)}
    <div class="nums">Rules</div><ol class="rules">${sc.rules.map(rule).join("")}</ol></div>`;
}
// Pantry Map: a grid of shelves.
function shelvesHTML(p) {
  const sc = p.scene, on = new Set(sc.marks.map(x => x.join(","))), ed = new Set((sc.editable || []).map(x => x.join(",")));
  let h = `<div class="shelves" style="--cols:${sc.cols}" id="shelves">`;
  for (let r = 0; r < sc.rows; r++) for (let c = 0; c < sc.cols; c++) {
    const k = r + "," + c;
    h += `<button class="shelf${on.has(k) ? " dot" : ""}${ed.has(k) ? " edit" : ""}" data-k="${k}" aria-label="row ${r + 1} column ${c + 1}${on.has(k) ? ", dot" : ""}"></button>`;
  }
  return h + `</div>`;
}
function optionHTML(o) {
  if (cur && cur.family === "conveyor") return beltHTML(o, false);
  if (cur && cur.family === "bead_grammar") return tokensHTML(o);
  if (cur && cur.family === "logic_gates") return esc(o.length ? "Buttons " + o.join(", ") : "Nobody");
  if (Array.isArray(o)) return `<span class="dice" aria-hidden="true">${o.map(v => FACES[v]).join("")}</span><span class="nums">${o.join(", ")}</span>`;
  if (cur && cur.family === "signal_code" && cur.question_type === "inverse") return flashHTML(o);
  if (typeof o === "number") return esc(cur && cur.family === "shortest_path" && cur.question_type === "cost" ? o + " planks"
    : cur && cur.family === "grid_routes" && cur.question_type === "length" ? o + " blocks" : String(o));
  return esc(o);
}
function codebookHTML(p) {
  const rows = p.codebook.map(([w, c]) => `<tr><td>${esc(w)}</td><td>${flashHTML(c)}</td></tr>`).join("");
  let h = `<table class="codebook"><thead><tr><th>Word</th><th>Flashes</th></tr></thead><tbody>${rows}</tbody></table>`;
  if (p.signal) h += `<div class="signal"><span class="nums">Signal received</span>${flashHTML(p.signal)}</div>`;
  if (p.question) h += `<p class="prompt"><b>${esc(p.question)}</b></p>`;
  return h;
}
function routeText(path) { return path.map(x => x === "N" ? "north shore" : x === "S" ? "south shore" : x).join(" → "); }

function next() {
  renderTabs();
  cur = pick(state.fam, state.level[state.fam]);
  tries = 0; hintsShown = 0; solved = false; selected = new Set(); lastTags = [];
  save(); render();
}

function render() {
  const p = cur, card = $("#card");
  if (!p) { card.innerHTML = `<p class="loaderr">No problems found for this level. Run tools/build_problems.py to create them.</p>`; return; }
  const kind = { trace: "Trace the rule", find: "Find the roll", compare: "Compare routes", cost: "Cheapest crossing", build: "Build the crossing",
    decode: "Decode the signal", count: "Count", inverse: "Find the signal", length: "Shortest route", count_routes: "Count cheapest crossings",
    valid: "Which belt works", depth: "Fullest bucket", stack: "Two sizes", repair: "Fix the belt", lookup: "Look it up",
    choose: "Which beavers", press: "Light the bulb", fewest: "Fewest beavers", can: "Can it be made", cannot: "Which cannot",
    erased1: "Find the missing dot", erased2: "Find two missing dots", changed: "Find the change", fill: "Fill the checks" }[p.question_type];
  const kindShown = p.family === "pointer_lists" && p.question_type === "inverse" ? "Work backward"
    : p.family === "logic_gates" && p.question_type === "count" ? "Count the ways"
    : p.family === "bead_grammar" && p.question_type === "count" ? "Count the necklaces" : kind;
  let body = `<div class="meta"><span>Level ${p.level}</span><span>${kindShown}</span></div><p class="prompt">${esc(p.prompt)}</p>`;
  if (p.rule_text) body += `<pre class="rule">${ruleHTML(p.rule_text)}</pre>`;
  if (p.codebook) body += codebookHTML(p);
  if (p.family === "conveyor" && p.scene.belt) body += beltHTML(p.scene.belt, true);
  if (p.family === "pointer_lists") body += rowsHTML(p.scene.lists);
  if (p.family === "bead_grammar") body += grammarHTML(p.scene);
  if (p.family === "parity_grid") body += shelvesHTML(p);
  if (["conveyor", "pointer_lists", "bead_grammar", "parity_grid"].includes(p.family) && p.question) body += `<p class="prompt"><b>${esc(p.question)}</b></p>`;
  if (p.svg) body += `<div class="map${p.question_type === "build" || p.entry === "press" ? " build" : ""}" id="map">${p.svg}</div>`;
  if (p.svg && p.question) body += `<p class="prompt"><b>${esc(p.question)}</b></p>`;
  if (p.question_type === "build") {
    body += `<p class="nums" style="margin:0">Tap walkways to select them. Tap again to remove one.</p>
      <div class="row"><button class="btn" id="submit">Check my crossing</button><button class="btn ghost" id="clear">Clear</button><span class="nums" id="selsum"></span></div>`;
  } else if (p.entry === "press" || p.entry === "cells") {
    body += `<div class="row"><button class="btn" id="submit">Check</button><button class="btn ghost" id="clear">Clear</button><span class="nums" id="selsum"></span></div>`;
  } else if (p.entry === "number") {
    body += `<form class="row" id="numform"><input id="numans" type="number" inputmode="numeric" min="0" class="numin" aria-label="Your answer"><button class="btn" type="submit">Check</button></form>`;
  } else {
    body += `<div class="options${["signal_code", "conveyor", "bead_grammar"].includes(p.family) ? " wide" : ""}">${p.options.map((o, i) => `<button class="opt" data-i="${i}">${optionHTML(o)}</button>`).join("")}</div>`;
  }
  body += `<div id="fb"></div><div class="row"><button class="btn ghost" id="hint">Show a hint</button><button class="btn" id="next" hidden>Next puzzle</button><span class="tally">${state.tally.right} of ${state.tally.total} right on the first try</span></div>`;
  card.innerHTML = body;
  card.querySelectorAll(".opt").forEach(b => b.addEventListener("click", () => answerMC(+b.dataset.i, b)));
  $("#hint").addEventListener("click", showHint);
  $("#next").addEventListener("click", next);
  if (p.question_type === "build") setupBuild();
  if (p.entry === "press") setupPress();
  if (p.entry === "cells") setupCells();
  if (p.entry === "number") $("#numform").addEventListener("submit", e => { e.preventDefault(); answerNumber(); });
  renderCoach();
}

function wrongTags(i) {
  const o = cur.options[i];
  const d = cur.distractors.find(d => JSON.stringify(d.option) === JSON.stringify(o) || (cur.question_type === "compare" && routeText(d.option) === o));
  return d ? d.misconceptions : [];
}

function record(correct, tags) {
  const fam = state.fam;
  if (tries === 1) {
    state.tally.total++; if (correct) state.tally.right++;
    state.log.push({ fam, level: cur.level, seed: cur.seed, correct, tags, t: Date.now() });
    if (state.log.length > 500) state.log = state.log.slice(-500);
    if (correct) { state.streak[fam]++; state.misses[fam] = 0; state.done[fam + cur.level] = (state.done[fam + cur.level] || 0) + 1; }
    else { state.misses[fam]++; state.streak[fam] = 0; }
    const lv = levels(fam), max = lv[lv.length - 1], min = lv[0];
    if ($("#auto").checked) {
      if (state.streak[fam] >= 2 && state.level[fam] < max) { state.level[fam]++; state.streak[fam] = 0; }
      if (state.misses[fam] >= 2 && state.level[fam] > min) { state.level[fam]--; state.misses[fam] = 0; }
    }
  }
  const tally = document.querySelector(".tally");
  if (tally) tally.textContent = `${state.tally.right} of ${state.tally.total} right on the first try`;
  tags.forEach(t => state.misconceptionCounts[t] = (state.misconceptionCounts[t] || 0) + 1);
  if (tags.length) lastTags = tags;
  save();
}

function answerMC(i, btn) {
  if (solved) return;
  tries++;
  const ok = i === cur.answer_index, tags = ok ? [] : wrongTags(i);
  record(ok, tags);
  if (ok) {
    btn.classList.add("right"); solved = true;
    document.querySelectorAll(".opt").forEach(b => b.disabled = true);
    finish();
  } else {
    btn.classList.add("wrong"); btn.disabled = true;
    $("#fb").innerHTML = `<div class="feedback bad">Not quite. Try again${hintsShown < cur.hints.length ? ", or take a hint" : ""}.</div>`;
    renderCoach();
  }
}

function answerNumber() {
  if (solved) return;
  const raw = $("#numans").value.trim();
  if (raw === "" || isNaN(+raw)) { $("#fb").innerHTML = `<div class="feedback bad">Type a whole number, then press Check.</div>`; return; }
  tries++;
  const v = Math.round(+raw), ok = v === cur.answer_value;
  const tags = ok ? [] : (cur.value_tags[String(v)] || []);
  record(ok, tags);
  if (ok) { solved = true; $("#numans").disabled = true; finish(); return; }
  $("#fb").innerHTML = `<div class="feedback bad">${v} is not right. Try again${hintsShown < cur.hints.length ? ", or take a hint" : ""}.</div>`;
  renderCoach();
}

function finish() {
  $("#fb").innerHTML = `<div class="feedback good">${tries === 1 ? "Right on the first try." : "Got it."}</div>
    <div class="explain">${cur.explanation.map(l => `<p${l.startsWith("  ") ? ' class="mono"' : ""}>${esc(l).replace(/\{\{([A-Za-z]+)\}\}/g, (_, t) => tokensHTML(t))}</p>`).join("")}</div>`;
  $("#next").hidden = false; $("#hint").hidden = true;
  renderTabs(); renderCoach();
}

function showHint() {
  if (hintsShown >= cur.hints.length) return;
  hintsShown++;
  let box = $("#hintbox");
  if (!box) { box = document.createElement("div"); box.className = "hintbox"; box.id = "hintbox"; $("#fb").before(box); }
  box.innerHTML = cur.hints.slice(0, hintsShown).map(h => `<div>${esc(h)}</div>`).join("");
  if (hintsShown >= cur.hints.length) $("#hint").disabled = true;
}

function setupBuild() {
  const groups = document.querySelectorAll("#map g.walkway");
  const updateSum = () => {
    const sel = [...document.querySelectorAll("#map g.walkway.sel")];
    const sum = sel.reduce((s, x) => s + +x.dataset.w, 0);
    $("#selsum").textContent = sel.length ? `${sel.length} walkways, ${sum} planks` : "";
  };
  groups.forEach(g => {
    g.setAttribute("tabindex", "0"); g.setAttribute("role", "button");
    g.setAttribute("aria-label", `Walkway ${g.dataset.a} to ${g.dataset.b}, ${g.dataset.w} planks`);
    const toggle = () => {
      if (solved) return;
      const k = g.dataset.a + "|" + g.dataset.b;
      if (selected.has(k)) { selected.delete(k); g.classList.remove("sel"); } else { selected.add(k); g.classList.add("sel"); }
      updateSum();
    };
    g.addEventListener("click", toggle);
    g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
  });
  $("#clear").addEventListener("click", () => { selected.clear(); groups.forEach(g => g.classList.remove("sel")); updateSum(); });
  $("#submit").addEventListener("click", submitBuild);
}

function edgeSet(path) { const s = new Set(); for (let i = 0; i < path.length - 1; i++) s.add([path[i], path[i + 1]].sort().join("|")); return s; }
function sameSet(a, b) { return a.size === b.size && [...a].every(x => b.has(x)); }

function submitBuild() {
  if (solved) return;
  const sub = new Set([...selected].map(k => k.split("|").sort().join("|")));
  const deg = {}; sub.forEach(k => k.split("|").forEach(n => deg[n] = (deg[n] || 0) + 1));
  const isChain = deg.N === 1 && deg.S === 1 && Object.entries(deg).every(([n, d]) => (n === "N" || n === "S") ? d === 1 : d === 2);
  // degree test alone allows a separate loop of islands; also require connectivity from N
  let connected = false;
  if (isChain) {
    const adj = {}; sub.forEach(k => { const [a, b] = k.split("|"); (adj[a] = adj[a] || []).push(b); (adj[b] = adj[b] || []).push(a); });
    const seen = new Set(["N"]), stack = ["N"];
    while (stack.length) { const u = stack.pop(); (adj[u] || []).forEach(v => { if (!seen.has(v)) { seen.add(v); stack.push(v); } }); }
    connected = seen.size === Object.keys(deg).length;
  }
  if (!sub.size || !isChain || !connected) {
    $("#fb").innerHTML = `<div class="feedback bad">That is not one complete crossing yet. Pick walkways that make a single unbroken line from the north shore to the south shore.</div>`;
    return;
  }
  tries++;
  const ok = sameSet(sub, edgeSet(cur.answer_path));
  const tags = ok ? [] : Object.entries(cur.misconception_paths).filter(([k, p]) => sameSet(sub, edgeSet(p))).map(([k]) => k);
  record(ok, tags);
  if (ok) { solved = true; finish(); return; }
  const sum = [...document.querySelectorAll("#map g.walkway.sel")].reduce((s, x) => s + +x.dataset.w, 0);
  $("#fb").innerHTML = `<div class="feedback bad">That crossing works, but it uses ${sum} planks. A cheaper one exists. Try again${hintsShown < cur.hints.length ? ", or take a hint" : ""}.</div>`;
  renderCoach();
}

// ---- Lights On: tap buttons in the circuit, then check
function gateEval(node, on, swap) {
  if (node.in !== undefined) return on.has(node.in);
  const a = gateEval(node.kids[0], on, swap), b = gateEval(node.kids[1], on, swap);
  let op = node.op;
  if (swap && op === swap[0]) op = swap[1];
  return op === "AND" ? a && b : op === "XOR" ? a !== b : a || b;
}
function setupPress() {
  const btns = document.querySelectorAll("#map g.btn");
  const update = () => { $("#selsum").textContent = selected.size ? `${selected.size} beaver${selected.size > 1 ? "s" : ""}` : ""; };
  btns.forEach(g => {
    const flip = () => {
      if (solved) return;
      const k = +g.dataset.btn;
      if (selected.has(k)) { selected.delete(k); g.classList.remove("sel"); } else { selected.add(k); g.classList.add("sel"); }
      update();
    };
    g.addEventListener("click", flip);
    g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); flip(); } });
  });
  $("#submit").addEventListener("click", () => {
    if (solved) return;
    tries++;
    const tree = cur.scene.tree, lit = gateEval(tree, selected);
    const ok = lit && (cur.question_type !== "fewest" || selected.size === cur.answer_value);
    let tags = [];
    if (!ok) {
      if (lit) tags = ["EXTRA_BUTTONS"];
      else {
        if (gateEval(tree, selected, ["XOR", "OR"])) tags.push("XOR_AS_OR");
        if (gateEval(tree, selected, ["AND", "OR"])) tags.push("BOTH_AS_EITHER");
      }
    }
    record(ok, tags);
    if (ok) { solved = true; document.querySelector("#map .bulb").classList.add("lit"); finish(); return; }
    $("#fb").innerHTML = `<div class="feedback bad">${lit ? `The light is on, but it can be done with fewer than ${selected.size} beavers.` : "The light stays off."} Try again${hintsShown < cur.hints.length ? ", or take a hint" : ""}.</div>`;
    renderCoach();
  });
  $("#clear").addEventListener("click", () => { if (solved) return; selected.clear(); btns.forEach(g => g.classList.remove("sel")); update(); });
}

// ---- Pantry Map: tap shelves, then check
function setupCells() {
  const fill = cur.question_type === "fill", cells = document.querySelectorAll("#shelves .shelf");
  const editable = new Set((cur.scene.editable || []).map(x => x.join(",")));
  const update = () => { $("#selsum").textContent = fill ? "" : `${selected.size} of ${cur.pick} chosen`; };
  cells.forEach(b => b.addEventListener("click", () => {
    if (solved) return;
    const k = b.dataset.k;
    if (fill && !editable.has(k)) return;
    if (selected.has(k)) { selected.delete(k); b.classList.remove("sel"); }
    else {
      if (!fill && selected.size >= cur.pick) { const first = [...selected][0]; selected.delete(first); document.querySelector(`.shelf[data-k="${first}"]`).classList.remove("sel"); }
      selected.add(k); b.classList.add("sel");
    }
    update();
  }));
  update();
  $("#submit").addEventListener("click", () => {
    if (solved) return;
    if (!fill && selected.size !== cur.pick) { $("#fb").innerHTML = `<div class="feedback bad">Choose ${cur.pick} shel${cur.pick > 1 ? "ves" : "f"} first.</div>`; return; }
    tries++;
    const want = new Set(cur.answer_value.map(x => x.join(",")));
    const ok = selected.size === want.size && [...selected].every(k => want.has(k));
    let tags = [];
    if (!ok && !fill) tags = [...new Set([...selected].flatMap(k => cur.cell_tags[k] || []))];
    if (!ok && fill) {
      const sc = cur.scene, g = Array.from({ length: sc.rows }, () => Array(sc.cols).fill(0));
      sc.marks.forEach(([r, c]) => g[r][c] = 1);
      selected.forEach(k => { const [r, c] = k.split(",").map(Number); g[r][c] = 1; });
      const rowsEven = g.every(row => row.reduce((a, b) => a + b) % 2 === 0);
      const colsEven = g[0].every((_, c) => g.reduce((a, row) => a + row[c], 0) % 2 === 0);
      const corner = (sc.rows - 1) + "," + (sc.cols - 1);
      const offByCorner = [...want].filter(k => k !== corner).every(k => selected.has(k)) && [...selected].filter(k => k !== corner).every(k => want.has(k));
      if (offByCorner) tags = ["PARITY_CORNER"];
      else if (rowsEven && !colsEven) tags = ["PARITY_ROWS_ONLY"];
      else if (colsEven && !rowsEven) tags = ["PARITY_COLS_ONLY"];
    }
    record(ok, tags);
    if (ok) { solved = true; cells.forEach(b => { if (want.has(b.dataset.k)) b.classList.add("right"); }); finish(); return; }
    $("#fb").innerHTML = `<div class="feedback bad">Not quite. Try again${hintsShown < cur.hints.length ? ", or take a hint" : ""}.</div>`;
    renderCoach();
  });
  $("#clear").addEventListener("click", () => { if (solved) return; selected.clear(); cells.forEach(b => b.classList.remove("sel")); update(); });
}

function renderCoach() {
  const C = DATA.coach;
  const counts = Object.entries(state.misconceptionCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);
  let h = cur ? `<p style="margin:8px 0 0">Tests: ${cur.concepts.map(c => esc(C.concepts[c] || c)).join(", ")}. Problem file: <span class="tag">${state.fam}/L${cur.level}-${cur.seed}.js</span></p>` : "";
  if (lastTags.length) {
    h += `<p style="margin:8px 0 0"><b>Last wrong answer matched:</b></p><ul>` + lastTags.map(t => {
      const m = C.misconceptions[t];
      return m ? `<li><span class="tag">${t}</span> ${esc(m.description)} <i>Try:</i> ${esc(m.remediation)}</li>` : "";
    }).join("") + `</ul>`;
  }
  if (counts.length) h += `<p style="margin:10px 0 0"><b>Most frequent so far:</b> ${counts.map(([k, v]) => `<span class="tag">${k}</span> ×${v}`).join(", ")}</p>`;
  h += `<div class="row" style="margin-top:10px"><button class="btn ghost" id="reset">Reset progress</button><span id="resetMsg"></span></div>`;
  $("#coachBody").innerHTML = h;
  $("#reset").addEventListener("click", () => {
    const m = $("#resetMsg");
    if (m.dataset.armed) { try { localStorage.removeItem("bebras-practice-local"); } catch (e) {} location.reload(); }
    m.dataset.armed = "1"; m.textContent = "Click again to clear levels and history.";
  });
}

(async function start() {
  if (!BEBRAS.coachData || FAMS.some(f => !BEBRAS.files[f])) {
    $("#card").innerHTML = `<p class="loaderr">Could not find coach.js or a manifest.js in ${FAMS.join("/, ")}/. Keep index.html in the same folder as those, or run tools/build_problems.py to recreate them.</p>`;
    return;
  }
  const { bank, missing } = await loadAll();
  DATA = { bank, coach: BEBRAS.coachData };
  const saved = store.get("bebras-practice-local", {}), base = defaultState();
  state = Object.assign(base, saved);
  ["level", "streak", "misses"].forEach(k => { state[k] = Object.assign(defaultState()[k], saved[k] || {}); });
  FAMS.forEach(f => { const lv = levels(f); if (!lv.includes(state.level[f])) state.level[f] = lv[0]; });
  document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => { state.fam = t.dataset.fam; save(); next(); }));
  next();
  if (missing.length) $("#card").insertAdjacentHTML("afterbegin", `<p class="loaderr">${missing.length} problem file(s) listed in a manifest could not be loaded, starting with ${esc(missing[0])}.</p>`);
})();

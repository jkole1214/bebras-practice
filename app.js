// Kerbopple: the practice page. The server (server.js with engine.js) picks each
// puzzle and sends it without its answer; this page draws it, sends each try to
// /api/answer and shows what comes back. Levels, the tutor and every answer live
// on the server.

const FACES = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"];
const PRACTICE = "practice";   // the mixed mode: the tutor picks the puzzle type and level
const FLASH = { S: "\u25cf", L: "\u25ac" };
const $ = (s) => document.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

// COACH: titles, ladders, concept and misconception text (coach.js). page: levels, counts and mode from the server.
// cur: the puzzle on screen (no answer in it). servedAs: "ladder", "remedy" (a tutor detour) or "lookback".
let COACH, page = null, cur = null, servedAs = "ladder", why = "", tries = 0, hintsShown = 0, solved = false, busy = false, selected = new Set(), lastTags = [], look = null;

async function api(url, body) {
  try { return await Account.call("POST", url, body || {}); }
  catch (e) {
    if (e.status === 401) { location.reload(); return null; }   // signed out elsewhere: sign in again
    throw e;
  }
}
const OFFLINE = "Could not reach the server. Check your connection and try again.";
function problemMsg(e) { return e && e.status ? e.message : OFFLINE; }

// Loads a puzzle from the server: {} for the next one, { resume: true }, { mode }, { level }.
async function next(body = {}) {
  Progress.close(false);
  if (busy) return;
  busy = true;
  try { show(await api("/api/next", body)); }
  catch (e) { $("#card").innerHTML = `<p class="loaderr">${esc(problemMsg(e))}</p><div class="row"><button class="btn" id="retry">Try again</button></div>`; $("#retry").addEventListener("click", () => next(body)); }
  finally { busy = false; }
}

// Shows one exact puzzle again (from the Progress page). Its tries do not move levels.
async function openProblem(fam, level, seed) {
  Progress.close(false);
  try { show(await api("/api/open", { fam, level, seed })); return true; }
  catch (e) { $("#card").innerHTML = `<p class="loaderr">${esc(problemMsg(e))}</p>`; return false; }
}

function show(d) {
  if (!d) return;
  cur = d.puzzle; servedAs = d.servedAs; why = d.why || ""; tries = d.tries || 0; hintsShown = d.hints || 0;
  solved = false; selected = new Set(); lastTags = []; look = null; page = d.page;
  renderTabs(); render();
  for (let i = 0; i < hintsShown; i++) drawHints();
}

function renderTabs() {
  const mode = page.mode;
  document.querySelectorAll(".tab").forEach(t => t.setAttribute("aria-pressed", t.dataset.fam === mode));
  document.querySelectorAll(".mode").forEach(m => m.setAttribute("aria-pressed", (m.dataset.mode === PRACTICE) === (mode === PRACTICE)));
  $("#famTabs").hidden = mode === PRACTICE;
  $(".ladder").hidden = mode === PRACTICE;
  $("#auto").checked = page.auto;
  if (mode === PRACTICE) return;
  const rungs = $("#rungs"); rungs.innerHTML = "";
  (page.levels[mode] || []).forEach(i => {
    const b = document.createElement("button");
    b.className = "rung" + (i === page.level[mode] ? " on" : "") + ((page.done[mode] || []).includes(i) ? " done" : "");
    b.textContent = i; b.title = (COACH.ladders[mode] || [])[i - 1] || "";
    b.addEventListener("click", () => next({ level: i }));
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
// Code Lock: symbols on wheel faces, the clues, and the wheels the student fills.
const SYM = {
  S: ["sun", '<circle cx="12" cy="12" r="5" class="sy-sun"/><path d="M12 1.5v4M12 18.5v4M1.5 12h4M18.5 12h4M4.6 4.6l2.8 2.8M16.6 16.6l2.8 2.8M4.6 19.4l2.8-2.8M16.6 7.4l2.8-2.8" class="sy-ray"/>'],
  M: ["moon", '<path d="M15.5 2.5a9.5 9.5 0 1 0 6 16.5A8 8 0 0 1 15.5 2.5z" class="sy-moon"/>'],
  T: ["star", '<polygon points="12,1.8 14.9,8.4 22,9.1 16.6,13.9 18.2,21 12,17.3 5.8,21 7.4,13.9 2,9.1 9.1,8.4" class="sy-star"/>'],
  H: ["heart", '<path d="M12 21 3.6 12.6A5.2 5.2 0 0 1 12 6.2a5.2 5.2 0 0 1 8.4 6.4z" class="sy-heart"/>'],
  L: ["leaf", '<path d="M4 20C4 9.5 10 3.5 20.5 3.5 20.5 14 14.5 20 4 20z" class="sy-leaf"/><path d="M4 20 15 9" class="sy-rib"/>'],
  D: ["drop", '<path d="M12 2s-7 8-7 12.5a7 7 0 0 0 14 0C19 10 12 2 12 2z" class="sy-drop"/>'],
  Z: ["bolt", '<polygon points="14.5,1.5 4.5,13.5 11,13.5 8.5,22.5 19.5,9.5 13,9.5" class="sy-bolt"/>'],
  B: ["bell", '<path d="M12 2.5a6.5 6.5 0 0 0-6.5 6.5v5l-2.2 3.5h17.4L18.5 14V9A6.5 6.5 0 0 0 12 2.5z" class="sy-bell"/><circle cx="12" cy="20" r="2.2" class="sy-bell"/>'],
};
const symSVG = (ch) => `<span class="sym" title="${SYM[ch][0]}"><svg viewBox="0 0 24 24" width="26" height="26" role="img" aria-label="${SYM[ch][0]}">${SYM[ch][1]}</svg></span>`;
const codeHTML = (code) => `<span class="code">${[...code].map(symSVG).join("")}</span>`;
function cluePills(e, m) {
  if (!e && !m) return `<span class="pill none">nothing right</span>`;
  return (e ? `<span class="pill spot">${e} right spot</span>` : "") + (m ? `<span class="pill moved">${m} wrong spot</span>` : "");
}
function lockHTML(p) {
  const sc = p.scene;
  const clues = sc.clues.map(([g, e, m], i) => `<li><span class="nums">${i + 1}</span>${codeHTML(g)}<span class="pills">${cluePills(e, m)}</span></li>`).join("");
  return `<div class="lock">${p.entry === "choice" ? `<div class="nums">The wheels can show</div>${codeHTML(sc.pool.join(""))}` : ""}
    <div class="nums">Guesses tried</div><ol class="clues">${clues}</ol></div>`;
}
function optionHTML(o) {
  if (cur && cur.family === "code_clues") return codeHTML(o);
  if (cur && cur.family === "conveyor") return beltHTML(o, false);
  if (cur && cur.family === "bead_grammar") return tokensHTML(o);
  if (cur && cur.family === "stone_hops") return Array.isArray(o) ? `<span class="trip">${o.join(" → ")}</span>` : "Stone " + o;
  if (cur && cur.family === "gossip_rounds") return Array.isArray(o) ? o.map(m => `<span class="pair">${esc(m.join(" & "))}</span>`).join("") : esc(o + (cur.question_type === "fewest" ? " rounds" : " pieces"));
  if (cur && cur.family === "bubble_passes") return `<span class="bowlrow">${o.map(v => `<span>${v}</span>`).join("")}</span>`;
  if (cur && cur.family === "best_play") return Array.isArray(o) ? `<span class="nums">${o.join(", ")}</span>` : esc("Path " + o);
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

function render() {
  const p = cur, card = $("#card");
  const kind = { trace: "Trace the rule", find: "Find the roll", compare: "Compare routes", cost: "Cheapest crossing", build: "Build the crossing",
    decode: "Decode the signal", count: "Count", inverse: "Find the signal", length: "Shortest route", count_routes: "Count cheapest crossings",
    valid: "Which belt works", depth: "Fullest bucket", stack: "Two sizes", repair: "Fix the belt", lookup: "Look it up",
    choose: "Which beavers", press: "Light the bulb", fewest: "Fewest beavers", can: "Can it be made", cannot: "Which cannot",
    erased1: "Find the missing dot", erased2: "Find two missing dots", changed: "Find the change", fill: "Fill the checks",
    after: "Follow the paint", final: "When the paint stops" }[p.question_type];
  const kindShown = p.family === "pointer_lists" && p.question_type === "inverse" ? "Work backward"
    : p.family === "logic_gates" && p.question_type === "count" ? "Count the ways"
    : p.family === "bead_grammar" && p.question_type === "count" ? "Count the necklaces"
    : p.family === "code_clues" ? { choose: "Pick the code", crack: "Crack the code" }[p.question_type]
    : p.family === "brick_rule" ? { fill: "Build the pyramid", count: "Count the bricks", hidden: "Work backward" }[p.question_type]
    : p.family === "friend_reach" ? { reach: "Who hears it", who: "Whose news spreads most", befriend: "One new friend" }[p.question_type]
    : p.family === "stone_hops" ? { check: "Check the trip", last: "Last stone", tour: "Tap the trip" }[p.question_type]
    : p.family === "gossip_rounds" ? { trace: "Count the pieces", finish: "Plan the last round", fewest: "Fewest rounds" }[p.question_type]
    : p.family === "best_play" ? { path: "Pick a path", sure: "Sure acorns", first: "First move", traps: "Lose-piles" }[p.question_type]
    : p.family === "bubble_passes" ? { after1: "One worker", swaps: "Count the swaps", afterk: "Several workers", workers: "How many workers", start: "Work backward" }[p.question_type] : kind;
  const famTitle = page.mode === PRACTICE || servedAs !== "ladder" ? `<span>${esc(COACH.titles[p.fam])}</span>` : "";
  let body = `<div class="meta">${famTitle}<span>Level ${p.level}</span><span>${kindShown}</span></div>`
    + (why ? `<p class="why">${esc(why)}</p>` : "") + `<p class="prompt">${esc(p.prompt)}</p>`;
  if (p.rule_text) body += `<pre class="rule">${ruleHTML(p.rule_text)}</pre>`;
  if (p.codebook) body += codebookHTML(p);
  if (p.family === "conveyor" && p.scene && p.scene.belt) body += beltHTML(p.scene.belt, true);
  if (p.family === "pointer_lists") body += rowsHTML(p.scene.lists);
  if (p.family === "bead_grammar") body += grammarHTML(p.scene);
  if (p.family === "parity_grid") body += shelvesHTML(p);
  if (p.family === "code_clues") body += lockHTML(p);
  if (["conveyor", "pointer_lists", "bead_grammar", "parity_grid", "code_clues"].includes(p.family) && p.question) body += `<p class="prompt"><b>${esc(p.question)}</b></p>`;
  if (p.svg) body += `<div class="map${p.question_type === "build" || p.entry === "press" || p.entry === "bricks" || p.entry === "hops" ? " build" : ""}" id="map">${p.svg}</div>`;
  if (p.svg && p.question) body += `<p class="prompt"><b>${esc(p.question)}</b></p>`;
  if (p.question_type === "build") {
    body += `<p class="nums" style="margin:0">Tap walkways to select them. Tap again to remove one.</p>
      <div class="row"><button class="btn" id="submit">Check my crossing</button><button class="btn ghost" id="clear">Clear</button><span class="nums" id="selsum"></span></div>`;
  } else if (p.entry === "press" || p.entry === "cells" || p.entry === "bricks") {
    body += `<div class="row"><button class="btn" id="submit">Check</button><button class="btn ghost" id="clear">Clear</button><span class="nums" id="selsum"></span></div>`;
  } else if (p.entry === "hops") {
    body += `<p class="nums" style="margin:0">Tap stones in the order the frog lands on them.</p>
      <div class="row"><button class="btn" id="submit">Check my trip</button><button class="btn ghost" id="undo">Undo</button><button class="btn ghost" id="clear">Clear</button></div>
      <p class="nums trip" id="selsum"></p>`;
  } else if (p.entry === "code") {
    body += `<div class="wheels" id="wheels">${Array.from({ length: p.scene.slots }, (_, i) => `<button class="wheel" data-w="${i}" aria-label="wheel ${i + 1}, empty"></button>`).join("")}</div>
      <div class="palette">${p.scene.pool.map(ch => `<button class="symbtn" data-s="${ch}" aria-label="${SYM[ch][0]}">${symSVG(ch)}</button>`).join("")}</div>
      <div class="row"><button class="btn" id="submit">Try this code</button><button class="btn ghost" id="clear">Clear</button></div>`;
  } else if (p.entry === "number") {
    body += `<form class="row" id="numform"><input id="numans" type="number" inputmode="numeric" min="0" class="numin" aria-label="Your answer"><button class="btn" type="submit">Check</button></form>`;
  } else {
    body += `<div class="options${["signal_code", "conveyor", "bead_grammar"].includes(p.family) || (p.family === "stone_hops" && p.question_type === "check") || (p.family === "gossip_rounds" && p.question_type === "finish") ? " wide" : ""}">${p.options.map((o, i) => `<button class="opt" data-i="${i}">${optionHTML(o)}</button>`).join("")}</div>`;
  }
  body += `<div id="fb"></div><div class="row"><button class="btn ghost" id="hint">Show a hint</button><button class="btn" id="next" hidden>Next puzzle</button><span class="tally"></span></div>`;
  card.innerHTML = body;
  drawTally();
  card.querySelectorAll(".opt").forEach(b => b.addEventListener("click", () => answerMC(+b.dataset.i, b)));
  $("#hint").addEventListener("click", showHint);
  $("#next").addEventListener("click", () => next());
  if (p.question_type === "build") setupBuild();
  if (p.entry === "press") setupPress();
  if (p.entry === "cells") setupCells();
  if (p.entry === "code") setupCode();
  if (p.entry === "bricks") setupBricks();
  if (p.entry === "hops") setupHops();
  if (p.entry === "number") $("#numform").addEventListener("submit", e => { e.preventDefault(); answerNumber(); });
  renderCoach();
}

function drawTally() {
  const t = $(".tally");
  if (t) t.textContent = `${page.tally.right} of ${page.tally.total} right on the first try`;
}
const tryAgain = () => `Try again${hintsShown < cur.hints.length ? ", or take a hint" : ""}.`;
const say = (cls, html) => { $("#fb").innerHTML = `<div class="feedback ${cls}">${html}</div>`; };
// a wrong try: the message, then the server's "look again" question about the likely mistake, if it sent one
const miss = (html) => { say("bad", html); if (look) $("#fb").insertAdjacentHTML("beforeend", `<div class="look"><b>Look again.</b> ${esc(look)}</div>`); };

// Sends one try. Resolves with the server's verdict, or null when there is nothing to show
// (not a real try, or the server could not be reached; the message is already on screen).
async function submit(answer) {
  if (solved || busy) return null;
  busy = true;
  try {
    const r = await api("/api/answer", { answer, hints: hintsShown });
    if (!r) return null;
    if (r.invalid) { say("bad", esc(r.invalid)); return null; }
    tries = r.tries; page = r.page;
    if (r.correct) { Sound.right(); solved = true; } else Sound.miss();
    if (r.tags.length) lastTags = r.tags;
    look = r.look || null;
    drawTally();
    return r;
  } catch (e) {
    say("bad", esc(e.status === 409 ? e.message : OFFLINE));
    return null;
  } finally { busy = false; }
}

async function answerMC(i, btn) {
  const r = await submit({ choice: i });
  if (!r) return;
  if (r.correct) {
    btn.classList.add("right");
    document.querySelectorAll(".opt").forEach(b => b.disabled = true);
    finish(r);
  } else {
    btn.classList.add("wrong"); btn.disabled = true;
    miss(`Not quite. ${tryAgain()}`);
    renderCoach();
  }
}

async function answerNumber() {
  const raw = $("#numans").value.trim();
  if (raw === "" || isNaN(+raw)) { say("bad", "Type a whole number, then press Check."); return; }
  const v = Math.round(+raw), r = await submit({ value: v });
  if (!r) return;
  if (r.correct) { $("#numans").disabled = true; finish(r); return; }
  miss(`${v} is not right. ${tryAgain()}`);
  renderCoach();
}

function finish(r) {
  $("#fb").innerHTML = `<div class="feedback good">${tries === 1 ? "Right on the first try." : "Got it."}</div>
    <div class="explain">${(r.explanation || []).map(l => `<p${l.startsWith("  ") ? ' class="mono"' : ""}>${esc(l).replace(/\{\{([A-Za-z]+)\}\}/g, (_, t) => tokensHTML(t))}</p>`).join("")}</div>`;
  $("#next").hidden = false; $("#hint").hidden = true;
  renderTabs(); renderCoach();
}

function drawHints() {
  let box = $("#hintbox");
  if (!box) { box = document.createElement("div"); box.className = "hintbox"; box.id = "hintbox"; $("#fb").before(box); }
  box.innerHTML = cur.hints.slice(0, hintsShown).map(h => `<div>${esc(h)}</div>`).join("");
  if (hintsShown >= cur.hints.length) $("#hint").disabled = true;
}
function showHint() {
  if (hintsShown >= cur.hints.length) return;
  hintsShown++;
  drawHints();
}

// ---- Lake Crossing: tap walkways, then check
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
  $("#clear").addEventListener("click", () => { if (solved) return; selected.clear(); groups.forEach(g => g.classList.remove("sel")); updateSum(); });
  $("#submit").addEventListener("click", async () => {
    const r = await submit({ edges: [...selected] });
    if (!r) return;
    if (r.correct) { finish(r); return; }
    const sum = [...document.querySelectorAll("#map g.walkway.sel")].reduce((s, x) => s + +x.dataset.w, 0);
    miss(`That crossing works, but it uses ${sum} planks. A cheaper one exists. ${tryAgain()}`);
    renderCoach();
  });
}

// ---- Lights On: tap buttons in the circuit, then check
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
  $("#submit").addEventListener("click", async () => {
    const n = selected.size, r = await submit({ buttons: [...selected] });
    if (!r) return;
    if (r.correct) { document.querySelector("#map .bulb").classList.add("lit"); finish(r); return; }
    miss(`${r.lit ? `The light is on, but it can be done with fewer than ${n} beavers.` : "The light stays off."} ${tryAgain()}`);
    renderCoach();
  });
  $("#clear").addEventListener("click", () => { if (solved) return; selected.clear(); btns.forEach(g => g.classList.remove("sel")); update(); });
}

// ---- Brick Pyramid: tap a brick to step it through red, yellow, blue
const BRICKS = { R: ["#d9534f", "#ffffff", "red"], Y: ["#f2c14e", "#1f2933", "yellow"], B: ["#3b6fd8", "#ffffff", "blue"] };
function setupBricks() {
  const bricks = document.querySelectorAll("#map g.brick.edit"), col = {};
  const paint = (g) => {
    const v = col[g.dataset.k], [fill, ink, name] = BRICKS[v] || ["#f4f1ea", "#5a6880", "empty"];
    g.querySelector("rect").setAttribute("fill", fill);
    const t = g.querySelector("text"); t.setAttribute("fill", ink); t.textContent = v || "?";
    g.setAttribute("aria-label", g.getAttribute("aria-label").replace(/, [a-z]+$/, ", " + name));
  };
  const update = () => { const n = Object.keys(col).length; $("#selsum").textContent = `${n} of ${bricks.length} coloured`; };
  bricks.forEach(g => {
    const step = () => { if (solved) return; col[g.dataset.k] = "RYB"[("RYB".indexOf(col[g.dataset.k] || "B") + 1) % 3]; paint(g); update(); };
    g.addEventListener("click", step);
    g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); step(); } });
  });
  update();
  $("#submit").addEventListener("click", async () => {
    if (Object.keys(col).length < bricks.length) { say("bad", cur.question_type === "fill" ? "Colour every empty brick first. Tap a brick to change its colour." : "Tap each hidden brick to choose its colour first."); return; }
    const r = await submit({ bricks: col });
    if (!r) return;
    if (r.correct) { bricks.forEach(g => g.classList.add("right")); finish(r); return; }
    miss(`${cur.question_type === "fill" ? "Some bricks break the rule." : "That does not match the bricks that are shown."} ${tryAgain()}`);
    renderCoach();
  });
  $("#clear").addEventListener("click", () => { if (solved) return; Object.keys(col).forEach(k => delete col[k]); bricks.forEach(paint); update(); });
}

// ---- Frog Hops: tap stones in order; each hop is drawn as an arc (forward above, back below) and the frog follows
function setupHops() {
  const sc = cur.scene, svg = document.querySelector("#map svg"), layer = svg.querySelector(".hoplayer"), frog = svg.querySelector("g.frog");
  const stones = document.querySelectorAll("#map g.spot.stone"), trip = [];
  const X = (n) => +svg.querySelector(`g.spot[data-n="${n}"] circle`).getAttribute("cx");
  const ROW = +stones[0].querySelector("circle").getAttribute("cy");
  const legal = (x, y) => y - x === sc.fwd || x - y === sc.back;
  const draw = () => {
    const path = [sc.start, ...trip];
    layer.innerHTML = trip.map((y, i) => {
      const x = path[i], x0 = X(x), x1 = X(y), up = y > x, h = 14 + 5 * Math.min(6, Math.abs(y - x));
      const yb = up ? ROW - 17 : ROW + 17, yc = up ? yb - 2 * h : yb + 2 * h, mx = (x0 + x1) / 2, my = (yb + yc) / 2;
      return `<path d="M${x0} ${yb} Q${mx} ${yc} ${x1} ${yb}" class="hop${legal(x, y) ? "" : " bad"}"/>`
        + `<g class="hopno"><circle cx="${mx}" cy="${my}" r="8"/><text x="${mx}" y="${my + 4}" text-anchor="middle">${i + 1}</text></g>`;
    }).join("");
    stones.forEach(g => g.classList.toggle("sel", path.includes(+g.dataset.n)));
    frog.setAttribute("transform", `translate(${X(path[path.length - 1]) - X(sc.start)} 0)`);
    $("#selsum").textContent = trip.length ? "Trip: " + path.join(" → ") : "";
  };
  stones.forEach(g => {
    g.setAttribute("tabindex", "0"); g.setAttribute("role", "button");
    const tap = () => { if (!solved && trip.length < 40) { trip.push(+g.dataset.n); draw(); } };
    g.addEventListener("click", tap);
    g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); tap(); } });
  });
  $("#undo").addEventListener("click", () => { if (!solved) { trip.pop(); draw(); } });
  $("#clear").addEventListener("click", () => { if (!solved) { trip.length = 0; draw(); } });
  $("#submit").addEventListener("click", async () => {
    const r = await submit({ hops: trip.slice() });
    if (!r) return;
    if (r.correct) { stones.forEach(g => g.classList.add("right")); finish(r); return; }
    const path = [sc.start, ...trip], i = trip.findIndex((y, k) => !legal(path[k], y)), twice = path.find((y, k) => path.indexOf(y) !== k);
    const at = path[path.length - 1], left = sc.stones.filter(y => !path.includes(y));
    const why = i >= 0 ? `The hop from ${path[i]} to ${trip[i]} is not ${sc.fwd} forward or ${sc.back} back.`
      : twice !== undefined ? `The frog lands on stone ${twice} twice.`
      : `The frog is stuck on stone ${at}, and stone${left.length > 1 ? "s" : ""} ${left.join(", ")} ${left.length > 1 ? "are" : "is"} left.`;
    miss(`${why} ${tryAgain()}`);
    renderCoach();
  });
  draw();
}

// ---- Code Lock: tap symbols onto the wheels, then try the code
function setupCode() {
  const n = cur.scene.slots, code = Array(n).fill(null);
  const wheels = document.querySelectorAll("#wheels .wheel"), syms = document.querySelectorAll(".palette .symbtn");
  const draw = () => {
    wheels.forEach((w, i) => { w.innerHTML = code[i] ? symSVG(code[i]) : ""; w.setAttribute("aria-label", `wheel ${i + 1}, ${code[i] ? SYM[code[i]][0] : "empty"}`); });
    syms.forEach(b => b.disabled = solved || code.includes(b.dataset.s));
  };
  syms.forEach(b => b.addEventListener("click", () => {
    const i = code.indexOf(null);
    if (solved || i < 0 || code.includes(b.dataset.s)) return;
    code[i] = b.dataset.s; draw();
  }));
  wheels.forEach((w, i) => w.addEventListener("click", () => { if (!solved) { code[i] = null; draw(); } }));
  $("#submit").addEventListener("click", async () => {
    if (code.includes(null)) { say("bad", "Put a symbol on every wheel first. Tap a wheel to take its symbol off."); return; }
    const r = await submit({ code: code.join("") });
    if (!r) return;
    if (r.correct) { wheels.forEach(w => w.classList.add("right")); draw(); finish(r); return; }
    miss(`That code does not open the lock. ${tryAgain()}`);
    renderCoach();
  });
  $("#clear").addEventListener("click", () => { if (solved) return; code.fill(null); draw(); });
  draw();
}

// ---- Pantry Map: tap shelves, then check
function setupCells() {
  const fill = cur.question_type === "fill", cells = document.querySelectorAll("#shelves .shelf");
  const editable = new Set(((cur.scene || {}).editable || []).map(x => x.join(",")));
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
  $("#submit").addEventListener("click", async () => {
    if (!fill && selected.size !== cur.pick) { say("bad", `Choose ${cur.pick} shel${cur.pick > 1 ? "ves" : "f"} first.`); return; }
    const r = await submit({ cells: [...selected] });
    if (!r) return;
    if (r.correct) { cells.forEach(b => { if (selected.has(b.dataset.k)) b.classList.add("right"); }); finish(r); return; }
    miss(`Not quite. ${tryAgain()}`);
    renderCoach();
  });
  $("#clear").addEventListener("click", () => { if (solved) return; selected.clear(); cells.forEach(b => b.classList.remove("sel")); update(); });
}

function renderCoach() {
  const C = COACH;
  let h = cur ? `<p style="margin:8px 0 0">Tests: ${cur.concepts.map(c => esc(C.concepts[c] || c)).join(", ")}. Puzzle: <span class="tag">${cur.fam}/L${cur.level}-${cur.seed}</span></p>` : "";
  if (lastTags.length) {
    h += `<p style="margin:8px 0 0"><b>Last wrong answer matched:</b></p><ul>` + lastTags.map(t => {
      const m = C.misconceptions[t];
      return m ? `<li><span class="tag">${t}</span> ${esc(m.description)} <i>Try:</i> ${esc(m.remediation)}</li>` : "";
    }).join("") + `</ul>`;
  }
  if (page && page.top.length) h += `<p style="margin:10px 0 0"><b>Most frequent so far:</b> ${page.top.map(([k, v]) => `<span class="tag">${k}</span> ×${v}`).join(", ")}</p>`;
  h += `<div class="row" style="margin-top:10px"><button class="btn ghost" id="reset">Reset levels</button><span id="resetMsg"></span></div>`;
  $("#coachBody").innerHTML = h;
  $("#reset").addEventListener("click", async () => {
    const m = $("#resetMsg");
    if (!m.dataset.armed) { m.dataset.armed = "1"; m.textContent = "Click again to start levels over. Your answers are kept."; return; }
    try { await api("/api/reset-levels"); next(); } catch (e) { m.textContent = problemMsg(e); }
  });
}

(async function start() {
  COACH = BEBRAS.coachData;
  if (!COACH) { $("#card").innerHTML = `<p class="loaderr">Could not load coach.js. Reload the page.</p>`; return; }
  const acct = await Account.init();   // shows the sign-in form until someone signs in
  if (!acct.user) { $("#card").innerHTML = `<p class="loaderr">${esc(acct.error || OFFLINE)}</p>`; return; }
  window.APP = { get coach() { return COACH; }, openProblem, next };
  $("#card").innerHTML = "<p>Loading a puzzle…</p>";
  // Practice (the tutor mixes puzzle types) is the default; "Pick a puzzle" opens the last type picked.
  document.querySelectorAll(".tab").forEach(t => t.addEventListener("click", () => next({ mode: t.dataset.fam })));
  document.querySelectorAll(".mode").forEach(m => m.addEventListener("click", () => {
    if (!page) return;
    const fams = [...document.querySelectorAll(".tab")].map(t => t.dataset.fam);
    const mode = m.dataset.mode === PRACTICE ? PRACTICE : page.lastFam || fams[0];
    if (mode !== page.mode) next({ mode });
  }));
  $("#auto").addEventListener("change", async (e) => {
    try { page = (await api("/api/settings", { auto: e.target.checked })).page; } catch (err) { e.target.checked = !e.target.checked; }
  });
  const soundBtn = $("#soundBtn"), showSound = () => soundBtn.setAttribute("aria-pressed", Sound.on);
  showSound();
  soundBtn.addEventListener("click", () => { Sound.set(!Sound.on); showSound(); if (Sound.on) Sound.right(); });
  $("#progressBtn").hidden = false;
  $("#progressBtn").addEventListener("click", () => Progress.open());
  await next({ resume: true });
  Progress.welcome();
})();

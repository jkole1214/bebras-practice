// Progress page: what the tutor knows about one student. Concepts shown or shaky,
// the misconceptions that keep coming up (with what to try), the puzzles they
// missed (open any of them again), and first-try results by puzzle type and level.
// A parent can switch between their kids.
//
// Family page (parents only): add a kid, rename them, change their username or password,
// download their answers, or remove them.

window.Progress = (() => {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const STATUS = { new: "Not started", started: "Just started", learning: "Learning", shaky: "Shaky", shown: "Shown" };
  let saved = null, filterTag = null, view = null;

  async function get(url) {
    const r = await fetch(url, { credentials: "same-origin" });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || `Request failed (${r.status})`);
    return d;
  }

  // Groups tries into one record per puzzle shown: a try 1 starts one, later tries join it.
  function instances(attempts) {
    const out = [];
    attempts.forEach(a => {
      if (a.try === 1) out.push({ fam: a.fam, level: a.level, seed: a.seed, t: a.t, tries: [a] });
      else {
        for (let i = out.length - 1; i >= Math.max(0, out.length - 5); i--) {
          const x = out[i];
          if (x.fam === a.fam && x.level === a.level && x.seed === a.seed) { x.tries.push(a); break; }
        }
      }
    });
    return out;
  }

  async function send(method, url, body) {
    const r = await fetch(url, { method, credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || `Request failed (${r.status})`);
    return d;
  }
  const isParent = () => Account.signedIn && Account.user.role === "parent";

  // Puts the puzzle on screen aside (close(true) brings it back) and hides the puzzle controls.
  function take(msg) {
    const card = $("#card");
    if (!saved) {
      saved = { nodes: document.createDocumentFragment(), ladder: $(".ladder").hidden };
      while (card.firstChild) saved.nodes.appendChild(card.firstChild);
    }
    $(".ladder").hidden = true; $("#coach").hidden = true; $("#progressBtn").hidden = true;
    card.innerHTML = `<p>${esc(msg)}</p>`;
  }
  function failed(e) {
    $("#card").innerHTML = `<p class="loaderr">${esc(e.message)}</p><div class="row"><button class="btn ghost" id="pBack">Back to puzzles</button></div>`;
    $("#pBack").addEventListener("click", () => close(true));
  }

  async function open(studentId) {
    const A = window.APP;
    if (!A) return;
    take("Loading progress…");
    let student, attempts, tutor, users = null;
    try {
      if (Account.signedIn) {
        if (isParent()) {
          const kids = (await get("/api/kids")).kids;
          users = kids.map(k => ({ id: k.id, name: k.name })).concat({ id: Account.user.id, name: `Me (${Account.user.name})` });
          if (!studentId && kids.length) studentId = kids[0].id;   // parents mostly want their kids
        }
        const h = await get("/api/history" + (studentId ? `?user=${encodeURIComponent(studentId)}` : ""));
        student = h.student; attempts = h.attempts;
        tutor = student.id === Account.user.id ? A.state.tutor : h.tutor;   // this tab's copy is the newest
      } else {
        student = { name: "this browser" };
        attempts = A.state.log.map(e => ({ fam: e.fam, level: e.level, seed: e.seed, try: 1, correct: e.correct, tags: e.tags || [], hints: e.hints || 0, t: e.t }));
        tutor = A.state.tutor;
      }
    } catch (e) { return failed(e); }
    view = { student, list: instances(attempts), tutor, users };
    filterTag = null;
    draw();
  }

  function draw() {
    const A = window.APP, C = A.DATA.coach, X = A.TX, { student, list, tutor, users } = view;
    const events = list.map(i => ({ fam: i.fam, level: i.level, correct: i.tries[0].correct, tags: i.tries[0].tags || [], hints: i.tries[0].hints || 0, t: i.t }));
    const M = Tutor.model(events, X);
    const right = events.filter(e => e.correct).length, week = events.filter(e => e.t > Date.now() - 7 * 864e5).length;
    const ms = list.reduce((s, i) => s + Math.min(15 * 60e3, Math.max(0, ...i.tries.map(t => t.ms || 0))), 0);

    let h = `<div class="ptop"><h2>Progress for ${esc(student.name)}</h2>`;
    if (users && users.length > 1) {
      h += `<label class="picker">Who <select id="pWho">${users.map(u =>
        `<option value="${u.id}"${u.id === student.id ? " selected" : ""}>${esc(u.name)}</option>`).join("")}</select></label>`;
    }
    h += `<button class="btn ghost" id="pBack">Back to puzzles</button></div>`;

    if (!list.length) {
      h += `<p>No puzzles answered yet. The tutor fills this in as puzzles are answered in the Practice tab or any puzzle tab.</p>`;
      return paint(h);
    }

    h += `<div class="tiles">
      ${tile(list.length, "puzzles tried")}
      ${tile(Math.round(100 * right / list.length) + "%", `right on the first try (${right} of ${list.length})`)}
      ${tile(week, "in the last 7 days")}
      ${ms ? tile(duration(ms), "practicing") : ""}
    </div>`;

    // what the tutor is doing now, and what it would work on
    const focus = Object.values(M.concepts).filter(c => c.status === "shaky" || c.status === "learning").sort((a, b) => a.score - b.score).slice(0, 3);
    h += `<section class="psec"><h3>Tutor focus</h3>`;
    if (tutor && tutor.remedy) {
      const r = tutor.remedy, m = C.misconceptions[r.tag] || {};
      h += `<p>Right now: a short step back to <b>${esc(C.titles[r.fam])} level ${r.level}</b>${r.prereq ? `, to practice ${esc((C.concepts[r.prereq] || r.prereq).toLowerCase())}` : ""},
        because this came up twice: ${esc(m.description || r.tag)}</p>`;
    }
    h += focus.length
      ? `<p>Next to work on: ${focus.map(c => `<b>${esc(C.concepts[c.id] || c.id)}</b>`).join(", ")}.</p>`
      : `<p>Nothing shaky right now. The Practice tab moves on to new levels and mixes in review.</p>`;
    h += `</section>`;

    // concepts by domain
    h += `<section class="psec"><h3>Concepts</h3><p class="nums">Based on first tries. Recent puzzles count more, as do right answers on hard levels and misses on easy ones. A first try after a hint counts as part right.</p>`;
    const byDom = {};
    [...X.covered].forEach(c => (byDom[(C.conceptDomain || {})[c] || "Other"] = byDom[(C.conceptDomain || {})[c] || "Other"] || []).push(M.concepts[c]));
    Object.keys(byDom).sort().forEach(d => {
      h += `<h4>${esc((C.domains || {})[d] || d)}</h4><ul class="concepts">` + byDom[d].sort((a, b) => b.n - a.n || a.id.localeCompare(b.id)).map(c =>
        `<li><span class="cname">${esc(C.concepts[c.id] || c.id)}</span>
          <span class="chip st-${c.status}">${STATUS[c.status]}</span>
          <span class="meter" role="img" aria-label="${c.n ? Math.round(c.score * 100) + "% estimated" : "no data"}">${c.n ? `<i style="width:${Math.round(c.score * 100)}%"></i>` : ""}</span>
          <span class="nums">${c.n ? `${c.right} of ${c.n} first tries` : ""}</span></li>`).join("") + `</ul>`;
    });
    h += `</section>`;

    // misconceptions
    const tags = Object.values(M.tags).sort((a, b) => b.weight - a.weight).slice(0, 6);
    if (tags.length) {
      h += `<section class="psec"><h3>Mistake patterns</h3><p class="nums">Wrong answers that match a known mix-up, with the most recent and frequent ones first.</p><ul class="mis">`;
      tags.forEach(t => {
        const m = C.misconceptions[t.id] || {};
        h += `<li><div class="row"><span class="tag">${esc(t.id)}</span><span class="nums">${t.count} time${t.count > 1 ? "s" : ""}, last ${day(t.last)}</span>
            <button class="linkbtn" data-tag="${esc(t.id)}">${filterTag === t.id ? "Show all misses" : "Show these misses"}</button></div>
          <p>${esc(m.description || "")}</p>${m.remediation ? `<p><i>Try:</i> ${esc(m.remediation)}</p>` : ""}</li>`;
      });
      h += `</ul></section>`;
    }

    // missed puzzles
    const missed = list.filter(i => !i.tries[0].correct && (!filterTag || (i.tries[0].tags || []).includes(filterTag))).reverse();
    h += `<section class="psec" id="pMissed"><h3>Missed on the first try${filterTag ? `: <span class="tag">${esc(filterTag)}</span>` : ""}</h3>`;
    if (!missed.length) h += `<p>None${filterTag ? " with this pattern" : ""}.</p>`;
    else {
      h += `<ul class="missed">` + missed.slice(0, 15).map(i => {
        const p = ((A.DATA.bank[i.fam] || {})[i.level] || []).find(x => x.seed === i.seed);
        const last = i.tries[i.tries.length - 1];
        const outcome = last.correct ? (i.tries.length === 1 ? "" : `Got it on try ${i.tries.length}.`) : "Did not get it.";
        return `<li><div class="row"><b>${esc(C.titles[i.fam] || i.fam)}, level ${i.level}</b><span class="nums">${day(i.t)}</span>
            ${p ? `<button class="btn ghost small" data-open="${esc(i.fam)}|${i.level}|${i.seed}">Open</button>` : `<span class="nums">(not in the current puzzle set)</span>`}</div>
          ${p ? `<p>First answer: <span class="ans">${esc(answerText(p, i.tries[0].answer))}</span>. Right answer: <span class="ans">${esc(rightText(p))}</span>. ${esc(outcome)}</p>` : ""}
          ${(i.tries[0].tags || []).length ? `<div>${i.tries[0].tags.map(t => `<span class="tag">${esc(t)}</span>`).join(" ")}</div>` : ""}</li>`;
      }).join("") + `</ul>`;
      if (missed.length > 15) h += `<p class="nums">Showing the latest 15 of ${missed.length}.</p>`;
    }
    h += `</section>`;

    // grid: family × level
    const maxL = Math.max(...Object.values(X.order).map(o => o[o.length - 1]));
    const cell = {};
    list.forEach(i => { const k = i.fam + "|" + i.level, c = cell[k] = cell[k] || { n: 0, r: 0, ms: 0, hints: 0 };
      c.n++; if (i.tries[0].correct) c.r++; c.ms += Math.min(15 * 60e3, i.tries[i.tries.length - 1].ms || 0); if (i.tries[0].hints) c.hints++; });
    h += `<section class="psec"><h3>By puzzle type and level</h3><p class="nums">Each box: right on the first try out of tried. Green is 75% or more, red under 50%.</p>
      <div class="gridwrap"><table class="lvgrid"><thead><tr><th></th>${Array.from({ length: maxL }, (_, k) => `<th>${k + 1}</th>`).join("")}</tr></thead><tbody>`;
    Object.keys(X.order).forEach(f => {
      h += `<tr><th scope="row">${esc(C.titles[f] || f)}</th>`;
      for (let l = 1; l <= maxL; l++) {
        if (!X.order[f].includes(l)) { h += `<td class="none"></td>`; continue; }
        const c = cell[f + "|" + l];
        if (!c) { h += `<td class="empty">·</td>`; continue; }
        const rate = c.r / c.n, cls = rate >= 0.75 ? "hi" : rate < 0.5 ? "lo" : "";
        h += `<td class="${cls}" title="${c.r} of ${c.n} right first try; ${c.hints} with hints; about ${Math.round(c.ms / c.n / 1000)} s each">${c.r}/${c.n}</td>`;
      }
      h += `</tr>`;
    });
    h += `</tbody></table></div></section>`;

    if (isParent()) {
      h += `<p class="nums">For the analysis notes: <a href="/api/export.json" download>download your family's answers</a> and run <span class="tag">python3 tools/observe.py kerbopple-export.json</span>.</p>`;
    }
    paint(h);
  }

  function paint(h) {
    const card = $("#card");
    card.innerHTML = `<div class="progress">${h}</div>`;
    $("#pBack").addEventListener("click", () => close(true));
    const who = $("#pWho");
    if (who) who.addEventListener("change", () => open(+who.value));
    card.querySelectorAll("[data-tag]").forEach(b => b.addEventListener("click", () => {
      filterTag = filterTag === b.dataset.tag ? null : b.dataset.tag; draw();
      const m = $("#pMissed"); if (m) m.scrollIntoView({ block: "start" });
    }));
    card.querySelectorAll("[data-open]").forEach(b => b.addEventListener("click", () => {
      const [fam, level, seed] = b.dataset.open.split("|");
      close(false);
      window.APP.openProblem(fam, +level, +seed);
      window.scrollTo(0, 0);
    }));
    window.scrollTo(0, 0);
  }

  // restore: put back the puzzle that was on screen (false when something new replaces it)
  function close(restore) {
    if (!saved) return;
    const card = $("#card");
    $("#coach").hidden = false; $("#progressBtn").hidden = false;
    if (restore) { card.replaceChildren(saved.nodes); $(".ladder").hidden = saved.ladder; }
    saved = null; view = null;
  }

  const tile = (big, small) => `<div class="tile"><b>${esc(big)}</b><span>${esc(small)}</span></div>`;
  const day = (t) => t ? new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" }) : "";
  function duration(ms) {
    const m = Math.round(ms / 60e3);
    return m < 1 ? "under 1 min" : m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${m % 60} min`;
  }
  const place = (x) => x === "N" ? "north shore" : x === "S" ? "south shore" : x;
  function optionText(o) {
    if (Array.isArray(o)) return o.every(v => typeof v === "number") ? o.join(", ") : o.map(place).join(" → ");
    return String(o);
  }
  function answerText(p, a) {
    if (a === null || a === undefined) return "not recorded";
    if (typeof a === "number") return String(a);
    if (a && a.option !== undefined) return p.family === "logic_gates" ? (a.option.length ? "buttons " + a.option.join(", ") : "nobody") : optionText(a.option);
    if (Array.isArray(a)) {
      if (p.question_type === "build") return "walkways " + a.map(k => k.split("|").map(place).join("–")).join(", ");
      if (p.entry === "press") return a.length ? "buttons " + a.join(", ") : "no buttons";
      if (p.entry === "cells") return a.map(cellName).join("; ") || "nothing";
    }
    return JSON.stringify(a);
  }
  function rightText(p) {
    if (p.question_type === "build") return routeOf(p.answer_path);
    if (p.entry === "press") return p.question_type === "fewest" ? `any ${p.answer_value} buttons that light the bulb` : "any buttons that light the bulb";
    if (p.entry === "cells") return (p.answer_value || []).map(x => cellName(x.join(","))).join("; ");
    if (p.entry === "number") return String(p.answer_value);
    const o = p.options[p.answer_index];
    return p.family === "logic_gates" ? (o.length ? "buttons " + o.join(", ") : "nobody") : optionText(o);
  }
  const routeOf = (path) => (path || []).map(place).join(" → ");
  const cellName = (k) => { const [r, c] = k.split(",").map(Number); return `row ${r + 1}, column ${c + 1}`; };

  // ---------- Family page (parents)
  let armed = null;   // id of the kid whose Remove button was clicked once
  async function family(note = "") {
    if (!isParent()) return;
    take("Loading your family…");
    let kids;
    try { kids = (await get("/api/kids")).kids; } catch (e) { return failed(e); }
    let h = `<div class="ptop"><h2>Your family</h2><button class="btn ghost" id="pBack">Back to puzzles</button></div>
      <p>Each kid signs in with <b>their username</b> and the password you choose for them. You sign in with your email. Kids who forget their password can ask you to set a new one here.</p>`;
    if (note) h += `<div class="feedback good">${esc(note)}</div>`;
    h += `<section class="psec"><h3>Kids</h3>`;
    if (!kids.length) h += `<p>No kids yet. Add one below.</p>`;
    else h += `<ul class="kids">` + kids.map(k => `<li data-id="${k.id}">
        <div class="row"><b>${esc(k.name)}</b><span class="nums">signs in as <b>${esc(k.username)}</b></span><span class="nums">${k.puzzles} puzzle${k.puzzles === 1 ? "" : "s"}${k.last_at ? `, last ${new Date(k.last_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}` : ""}</span></div>
        <div class="row">
          <button class="linkbtn" data-act="progress">Progress</button>
          <a href="/api/attempts.csv?user=${k.id}" download>Download answers</a>
          <button class="linkbtn" data-act="password">New password</button>
          <button class="linkbtn" data-act="rename">Rename</button>
          <button class="linkbtn" data-act="username">New username</button>
          <button class="linkbtn danger" data-act="remove">${armed === k.id ? `Click again to remove ${esc(k.name)} and all their answers` : "Remove"}</button>
        </div>
        <div class="kidform" hidden></div></li>`).join("") + `</ul>`;
    h += `</section><section class="psec"><h3>Add a kid</h3>
      <form class="auth kidadd" id="kidAdd" autocomplete="off">
        <label>Name<input name="name" type="text" maxlength="40" required autocomplete="off"></label>
        <label>Username<input name="username" type="text" maxlength="20" required autocomplete="off" autocapitalize="none" spellcheck="false"></label>
        <p class="nums" style="margin:0">What they type to sign in: 3 to 20 letters or digits, starting with a letter. It has to be one nobody else on the site has.</p>
        <label>Their password<input name="password" type="text" minlength="6" required autocomplete="off" spellcheck="false"></label>
        <p class="nums" style="margin:0">At least 6 characters. It is shown as you type so you can read it out to them.</p>
        <div id="kidMsg"></div>
        <div class="row"><button class="btn" type="submit">Add kid</button></div>
      </form></section>`;
    $("#card").innerHTML = `<div class="progress">${h}</div>`;
    $("#pBack").addEventListener("click", () => close(true));

    // suggest a username from the name until the parent types their own
    const nameIn = $("#kidAdd [name=name]"), userIn = $("#kidAdd [name=username]");
    let userEdited = false;
    userIn.addEventListener("input", () => { userEdited = !!userIn.value; });
    nameIn.addEventListener("input", () => {
      if (!userEdited) userIn.value = nameIn.value.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]/g, "").slice(0, 20);
    });
    $("#kidAdd").addEventListener("submit", async (e) => {
      e.preventDefault();
      const f = Object.fromEntries(new FormData(e.target));
      try { await send("POST", "/api/kids", f); armed = null; family(`Added ${f.name.trim()}. They sign in with the username ${f.username.trim().toLowerCase()} and the password you chose.`); }
      catch (err) { $("#kidMsg").innerHTML = `<div class="feedback bad">${esc(err.message)}</div>`; }
    });
    document.querySelectorAll("ul.kids li").forEach(li => {
      const id = +li.dataset.id, kid = kids.find(k => k.id === id), box = li.querySelector(".kidform");
      const ask = (label, name, type, value, done) => {
        box.hidden = false;
        box.innerHTML = `<form class="row"><input name="${name}" type="${type}" value="${esc(value)}" aria-label="${esc(label)}" placeholder="${esc(label)}" autocomplete="off" spellcheck="false" class="numin wide" required>
          <button class="btn" type="submit">Save</button><button class="btn ghost" type="button" data-cancel>Cancel</button></form><div class="msg"></div>`;
        box.querySelector("[data-cancel]").addEventListener("click", () => { box.hidden = true; });
        const input = box.querySelector("input"); input.focus();
        box.querySelector("form").addEventListener("submit", async (e) => {
          e.preventDefault();
          try { await send("POST", "/api/kids/update", { id, [name]: input.value }); armed = null; family(done(input.value)); }
          catch (err) { box.querySelector(".msg").innerHTML = `<div class="feedback bad">${esc(err.message)}</div>`; }
        });
      };
      li.querySelectorAll("[data-act]").forEach(b => b.addEventListener("click", async () => {
        const act = b.dataset.act;
        if (act === "progress") return open(id);
        if (act === "password") return ask(`New password for ${kid.name}`, "password", "text", "", () => `${kid.name}'s password is changed. They are signed out everywhere and sign in again with the new one.`);
        if (act === "rename") return ask("Name", "name", "text", kid.name, (v) => `Renamed to ${v.trim()}.`);
        if (act === "username") return ask("Username", "username", "text", kid.username, (v) => `${kid.name} now signs in as ${v.trim().toLowerCase()}.`);
        if (act === "remove") {
          if (armed !== id) { armed = id; return family(); }
          try { await send("POST", "/api/kids/delete", { id }); armed = null; family(`Removed ${kid.name}.`); }
          catch (err) { armed = null; family(); }
        }
      }));
    });
    window.scrollTo(0, 0);
  }

  // After a parent signs in: if there are no kids yet, go straight to the Family page.
  async function welcome() {
    if (!isParent()) return;
    try { if (!(await get("/api/kids")).kids.length) family(); } catch (e) {}
  }

  return { open, close, family, welcome };
})();

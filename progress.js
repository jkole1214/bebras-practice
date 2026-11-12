// Progress page: what the tutor knows about one student. Concepts shown or shaky,
// the misconceptions that keep coming up (with what to try), the puzzles they
// missed (open any of them again), and first-try results by puzzle type and level.
// The server works all of it out (GET /api/progress); this file draws it.
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
    if (!window.APP) return;
    take("Loading progress…");
    let users = null;
    try {
      if (isParent()) {
        const kids = (await get("/api/kids")).kids;
        users = kids.map(k => ({ id: k.id, name: k.name })).concat({ id: Account.user.id, name: `Me (${Account.user.name})` });
        if (!studentId && kids.length) studentId = kids[0].id;   // parents mostly want their kids
      }
      view = await get("/api/progress" + (studentId ? `?user=${encodeURIComponent(studentId)}` : ""));
      view.users = users;
    } catch (e) { return failed(e); }
    filterTag = null;
    draw();
  }

  function draw() {
    const C = window.APP.coach, v = view, student = v.student, users = v.users;

    let h = `<div class="ptop"><h2>Progress for ${esc(student.name)}</h2>`;
    if (users && users.length > 1) {
      h += `<label class="picker">Who <select id="pWho">${users.map(u =>
        `<option value="${u.id}"${u.id === student.id ? " selected" : ""}>${esc(u.name)}</option>`).join("")}</select></label>`;
    }
    h += `<button class="btn ghost" id="pBack">Back to puzzles</button></div>`;

    if (!v.puzzles) {
      h += `<p>No puzzles answered yet. The tutor fills this in as puzzles are answered in Practice or Pick a puzzle.</p>`;
      return paint(h);
    }

    h += `<div class="tiles">
      ${tile(v.puzzles, "puzzles tried")}
      ${tile(Math.round(100 * v.right / v.puzzles) + "%", `right on the first try (${v.right} of ${v.puzzles})`)}
      ${tile(v.week, "in the last 7 days")}
      ${v.ms ? tile(duration(v.ms), "practicing") : ""}
    </div>`;

    // what the tutor is doing now, and what it would work on
    h += `<section class="psec"><h3>Tutor focus</h3>`;
    if (v.remedy) {
      const r = v.remedy, m = C.misconceptions[r.tag] || {};
      h += `<p>Right now: a short step back to <b>${esc(C.titles[r.fam])} level ${r.level}</b>${r.prereq ? `, to practice ${esc((C.concepts[r.prereq] || r.prereq).toLowerCase())}` : ""},
        because this came up twice: ${esc(m.description || r.tag)}</p>`;
    }
    h += v.focus.length
      ? `<p>Next to work on: ${v.focus.map(c => `<b>${esc(C.concepts[c] || c)}</b>`).join(", ")}.</p>`
      : `<p>Nothing shaky right now. Practice moves on to new levels and mixes in review.</p>`;
    h += `</section>`;

    // concepts by domain
    h += `<section class="psec"><h3>Concepts</h3><p class="nums">Based on first tries. Recent puzzles count more, as do right answers on hard levels and misses on easy ones. A first try after a hint counts as part right.</p>`;
    const byDom = {};
    v.concepts.forEach(c => (byDom[(C.conceptDomain || {})[c.id] || "Other"] = byDom[(C.conceptDomain || {})[c.id] || "Other"] || []).push(c));
    Object.keys(byDom).sort().forEach(d => {
      h += `<h4>${esc((C.domains || {})[d] || d)}</h4><ul class="concepts">` + byDom[d].sort((a, b) => b.n - a.n || a.id.localeCompare(b.id)).map(c =>
        `<li><span class="cname">${esc(C.concepts[c.id] || c.id)}</span>
          <span class="chip st-${c.status}">${STATUS[c.status]}</span>
          <span class="meter" role="img" aria-label="${c.n ? Math.round(c.score * 100) + "% estimated" : "no data"}">${c.n ? `<i style="width:${Math.round(c.score * 100)}%"></i>` : ""}</span>
          <span class="nums">${c.n ? `${c.right} of ${c.n} first tries` : ""}</span></li>`).join("") + `</ul>`;
    });
    h += `</section>`;

    // misconceptions
    if (v.tags.length) {
      h += `<section class="psec"><h3>Mistake patterns</h3><p class="nums">Wrong answers that match a known mix-up, with the most recent and frequent ones first.</p><ul class="mis">`;
      v.tags.forEach(t => {
        const m = C.misconceptions[t.id] || {};
        h += `<li><div class="row"><span class="tag">${esc(t.id)}</span><span class="nums">${t.count} time${t.count > 1 ? "s" : ""}, last ${day(t.last)}</span>
            <button class="linkbtn" data-tag="${esc(t.id)}">${filterTag === t.id ? "Show all misses" : "Show these misses"}</button></div>
          <p>${esc(m.description || "")}</p>${m.remediation ? `<p><i>Try:</i> ${esc(m.remediation)}</p>` : ""}</li>`;
      });
      h += `</ul></section>`;
    }

    // missed puzzles (newest first)
    const missed = v.missed.filter(i => !filterTag || i.tags.includes(filterTag));
    h += `<section class="psec" id="pMissed"><h3>Missed on the first try${filterTag ? `: <span class="tag">${esc(filterTag)}</span>` : ""}</h3>`;
    if (!missed.length) h += `<p>None${filterTag ? " with this pattern" : ""}.</p>`;
    else {
      h += `<ul class="missed">` + missed.slice(0, 15).map(i => {
        const outcome = i.solved ? (i.tries === 1 ? "" : `Got it on try ${i.tries}.`) : "Not solved yet.";
        return `<li><div class="row"><b>${esc(C.titles[i.fam] || i.fam)}, level ${i.level}</b><span class="nums">${day(i.t)}</span>
            ${i.available ? `<button class="btn ghost small" data-open="${esc(i.fam)}|${i.level}|${i.seed}">Open</button>` : `<span class="nums">(not in the current puzzle set)</span>`}</div>
          ${i.available ? `<p>First answer: <span class="ans">${esc(i.first)}</span>.${i.right ? ` Right answer: <span class="ans">${esc(i.right)}</span>.` : ""} ${esc(outcome)}</p>` : ""}
          ${i.tags.length ? `<div>${i.tags.map(t => `<span class="tag">${esc(t)}</span>`).join(" ")}</div>` : ""}</li>`;
      }).join("") + `</ul>`;
      if (missed.length > 15) h += `<p class="nums">Showing the latest 15 of ${missed.length}.</p>`;
    }
    h += `</section>`;

    // grid: puzzle type × level
    const fams = Object.keys(v.levels), maxL = Math.max(...fams.map(f => v.levels[f][v.levels[f].length - 1]));
    h += `<section class="psec"><h3>By puzzle type and level</h3><p class="nums">Each box: right on the first try out of tried. Green is 75% or more, red under 50%.</p>
      <div class="gridwrap"><table class="lvgrid"><thead><tr><th></th>${Array.from({ length: maxL }, (_, k) => `<th>${k + 1}</th>`).join("")}</tr></thead><tbody>`;
    fams.forEach(f => {
      h += `<tr><th scope="row">${esc(C.titles[f] || f)}</th>`;
      for (let l = 1; l <= maxL; l++) {
        if (!v.levels[f].includes(l)) { h += `<td class="none"></td>`; continue; }
        const c = v.grid[f + "|" + l];
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

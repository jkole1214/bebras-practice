// Student accounts. When the page is served by server.js, students sign in and
// their progress and every answer attempt are saved on the server. When the page
// is opened straight from disk (file://) there is no server, and the page works
// as before with progress kept in this browser only.

window.Account = (() => {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let user = null, online = false, saveTimer = null, pendingState = null, flushing = false;

  const ls = {
    get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} }
  };
  const outboxKey = () => `bebras-outbox-${user.id}`;

  async function call(method, url, body) {
    const r = await fetch(url, {
      method, credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(data.error || `Request failed (${r.status})`), { status: r.status, unconfirmed: !!data.unconfirmed });
    return data;
  }

  // Resolves with { user, state } once someone is signed in, or { user: null } in disk mode.
  async function init() {
    if (location.protocol === "file:") return { user: null };
    // links from emails look like /#verify=TOKEN or /#reset=TOKEN. Opening one in a tab that
    // already has the page only changes the hash, so reload to handle it.
    window.addEventListener("hashchange", () => { if (/^#(verify|reset)=/.test(location.hash)) location.reload(); });
    const link = location.hash.match(/^#(verify|reset)=([A-Za-z0-9_-]+)$/);
    if (link) history.replaceState(null, "", location.pathname);
    let me;
    try { me = await call("GET", "/api/me"); } catch (e) { return { user: null }; }
    online = true;
    if (link && link[1] === "verify") {
      try { const r = await call("POST", "/api/confirm", { token: link[2] }); user = r.user; afterSignIn(); return r; }
      catch (e) { if (me.user) { user = me.user; afterSignIn(); return me; } return signInForm(me.registrationCode, "login", e.message); }
    }
    if (link && link[1] === "reset") return signInForm(me.registrationCode, "reset", "", link[2]);
    if (me.user) { user = me.user; afterSignIn(); return me; }
    return signInForm(me.registrationCode);
  }

  // One card with several screens: login, register, forgot, reset, sent (check your email).
  function signInForm(needsCode, startMode = "login", startMsg = "", resetToken = "") {
    return new Promise((resolve) => {
      let mode = startMode, lastEmail = "";
      const field = (label, name, type, auto, extra = "") =>
        `<label>${label}<input name="${name}" type="${type}" autocomplete="${auto}" required ${extra}${name === "email" && lastEmail ? ` value="${esc(lastEmail)}"` : ""}></label>`;
      const draw = (msg = "", ok = "", resend = false) => {
        const titles = { login: "Sign in", register: "Make an account", forgot: "Forgot your password?", reset: "Choose a new password", sent: "Check your email" };
        let fields = "", buttons = "";
        if (mode === "login") {
          fields = field("Email", "email", "email", "email") + field("Password", "password", "password", "current-password");
          buttons = `<button class="btn" type="submit">Sign in</button><button class="btn ghost" type="button" data-go="register">Make a new account</button>
            <button class="linkbtn" type="button" data-go="forgot">Forgot password?</button>`;
        } else if (mode === "register") {
          fields = field("Your name", "name", "text", "nickname", 'maxlength="60"') + field("Email", "email", "email", "email")
            + field("Password", "password", "password", "new-password", 'minlength="8"') + (needsCode ? field("Family code", "code", "text", "off") : "");
          buttons = `<button class="btn" type="submit">Make account</button><button class="btn ghost" type="button" data-go="login">I already have an account</button>`;
        } else if (mode === "forgot") {
          fields = `<p class="nums" style="margin:0">Type your email and we will send you a link to choose a new password.</p>` + field("Email", "email", "email", "email");
          buttons = `<button class="btn" type="submit">Send me a link</button><button class="btn ghost" type="button" data-go="login">Back to sign in</button>`;
        } else if (mode === "reset") {
          fields = field("New password", "password", "password", "new-password", 'minlength="8"');
          buttons = `<button class="btn" type="submit">Save password</button><button class="btn ghost" type="button" data-go="login">Back to sign in</button>`;
        } else if (mode === "sent") {
          buttons = `<button class="btn ghost" type="button" data-go="login">Back to sign in</button>`;
        }
        $("#card").innerHTML = `
          <form class="auth" id="authForm" novalidate>
            <h2>${titles[mode]}</h2>
            ${fields}
            ${ok ? `<div class="feedback good">${esc(ok)}</div>` : ""}
            ${msg ? `<div class="feedback bad">${esc(msg)}</div>` : ""}
            ${resend ? `<button class="linkbtn" type="button" id="resend">Send the confirmation email again</button>` : ""}
            <div class="row">${buttons}</div>
          </form>`;
        document.querySelectorAll("#authForm [data-go]").forEach(b => b.addEventListener("click", () => { mode = b.dataset.go; draw(); }));
        const rs = $("#resend");
        if (rs) rs.addEventListener("click", async () => {
          rs.disabled = true;
          try { await call("POST", "/api/resend-confirmation", { email: lastEmail }); mode = "sent"; draw("", `If ${lastEmail} has an account that is not confirmed yet, a new link is on its way. It can take a minute.`); }
          catch (err) { draw(err.message, "", true); }
        });
        $("#authForm").addEventListener("submit", async (e) => {
          e.preventDefault();
          const f = Object.fromEntries(new FormData(e.target));
          if (f.email) lastEmail = f.email.trim();
          const btn = e.target.querySelector("button[type=submit]");
          if (btn) btn.disabled = true;
          try {
            if (mode === "login") {
              const r = await call("POST", "/api/login", f); user = r.user; afterSignIn(); resolve(r);
            } else if (mode === "register") {
              const r = await call("POST", "/api/register", f);
              mode = "sent";
              if (r.emailFailed) draw(`Your account is made, but the email to ${r.email} could not be sent.`, "", true);
              else draw("", `We sent a link to ${r.email}. Open it to confirm your email, then you can start. Check spam if you do not see it.`, true);
            } else if (mode === "forgot") {
              await call("POST", "/api/forgot", f);
              mode = "sent"; draw("", `If ${lastEmail} has an account, a link to choose a new password is on its way. It works for 1 hour.`);
            } else if (mode === "reset") {
              const r = await call("POST", "/api/reset", { token: resetToken, password: f.password }); user = r.user; afterSignIn(); resolve(r);
            }
          } catch (err) { draw(err.message, "", !!err.unconfirmed); }
        });
        const first = $("#authForm input"); if (first) first.focus();
      };
      draw(startMsg);
    });
  }

  function afterSignIn() {
    renderBar();
    flush();
    window.addEventListener("online", flush);
    setInterval(flush, 60e3);
    // try to send anything unsent before the tab closes
    window.addEventListener("pagehide", () => {
      if (pendingState) fetch("/api/state", { method: "PUT", keepalive: true, credentials: "same-origin",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ state: pendingState }) }).catch(() => {});
    });
  }

  function renderBar() {
    const bar = $("#account");
    if (!bar) return;
    bar.hidden = false;
    bar.innerHTML = `<span>Signed in as <b>${esc(user.name)}</b></span>
      <a href="/api/attempts.csv" download>Download my answers</a>
      <button class="linkbtn" id="logout">Sign out</button>`;
    $("#logout").addEventListener("click", async () => {
      await flush();
      if (pendingState) await saveNow();
      try { await call("POST", "/api/logout"); } catch (e) {}
      location.reload();
    });
  }

  // Progress (levels, streaks, history): sent a moment after the last change.
  function saveState(state) {
    if (!user) return false;
    pendingState = state;
    clearTimeout(saveTimer);
    saveTimer = setTimeout(saveNow, 800);
    return true;
  }
  async function saveNow() {
    clearTimeout(saveTimer);
    const s = pendingState;
    if (!s) return;
    try { await call("PUT", "/api/state", { state: s }); if (pendingState === s) pendingState = null; }
    catch (e) { saveTimer = setTimeout(saveNow, 10e3); }
  }

  // Attempts go into a browser-side outbox first and are removed only once the server has them.
  function logAttempt(a) {
    if (!user) return;
    const rec = { id: (crypto.randomUUID ? crypto.randomUUID() : Date.now() + "-" + Math.random().toString(36).slice(2)), t: Date.now(), ...a };
    ls.set(outboxKey(), ls.get(outboxKey(), []).concat(rec));
    flush();
  }
  async function flush() {
    if (!user || flushing) return;
    const box = ls.get(outboxKey(), []);
    if (!box.length) return;
    flushing = true;
    let ok = false;
    try {
      await call("POST", "/api/attempts", { attempts: box.slice(0, 500) });
      const sent = new Set(box.slice(0, 500).map(a => a.id));
      ls.set(outboxKey(), ls.get(outboxKey(), []).filter(a => !sent.has(a.id)));
      ok = true;
    } catch (e) {
      if (e.status === 401) location.reload(); // session ended: sign in again; the outbox is kept
    } finally { flushing = false; }
    // more waiting (a big backlog, or one logged mid-send): send now; after a failure the 60s timer retries
    if (ok && ls.get(outboxKey(), []).length) flush();
  }

  return { init, saveState, logAttempt, get signedIn() { return !!user; }, get online() { return online; } };
})();

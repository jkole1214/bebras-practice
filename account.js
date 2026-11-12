// Family accounts. A parent signs up and adds their kids (on the Family page in
// progress.js), choosing each kid's username and password. Kids sign in with their
// username, parents with their email.
// Everything is kept on the server (server.js): the page needs to be served by it.

window.Account = (() => {
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let user = null;

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

  // Resolves with { user } once someone is signed in, or { error } when the server cannot be reached.
  async function init() {
    if (location.protocol === "file:") return { error: "Kerbopple runs on its server now. Start it with npm start and open http://localhost:3000." };
    // links from emails look like /#verify=TOKEN or /#reset=TOKEN. Opening one in a tab that
    // already has the page only changes the hash, so reload to handle it.
    window.addEventListener("hashchange", () => { if (/^#(verify|reset)=/.test(location.hash)) location.reload(); });
    const link = location.hash.match(/^#(verify|reset)=([A-Za-z0-9_-]+)$/);
    if (link) history.replaceState(null, "", location.pathname);
    let me;
    try { me = await call("GET", "/api/me"); } catch (e) { return { error: "Could not reach the server. Check your connection and reload the page." }; }
    if (link && link[1] === "verify") {
      try { const r = await call("POST", "/api/confirm", { token: link[2] }); user = r.user; afterSignIn(); return r; }
      catch (e) { if (me.user) { user = me.user; afterSignIn(); return me; } return signInForm("login", e.message); }
    }
    if (link && link[1] === "reset") return signInForm("reset", "", link[2]);
    if (me.user) { user = me.user; afterSignIn(); return me; }
    return signInForm();
  }

  // One card with several screens: login, register, forgot, reset, sent (check your email).
  function signInForm(startMode = "login", startMsg = "", resetToken = "") {
    return new Promise((resolve) => {
      let mode = startMode, lastEmail = "";
      const field = (label, name, type, auto, extra = "") =>
        `<label>${label}<input name="${name}" type="${type}" autocomplete="${auto}" required ${extra}${(name === "email" || name === "login") && lastEmail ? ` value="${esc(lastEmail)}"` : ""}></label>`;
      const draw = (msg = "", ok = "", resend = false) => {
        const titles = { login: "Sign in", register: "Make a family account", forgot: "Forgot your password?", reset: "Choose a new password", sent: "Check your email" };
        let fields = "", buttons = "";
        if (mode === "login") {
          fields = field("Username, or email for parents", "login", "text", "username", 'autocapitalize="none" spellcheck="false"')
            + field("Password", "password", "password", "current-password");
          buttons = `<button class="btn" type="submit">Sign in</button><button class="btn ghost" type="button" data-go="register">Parents: make a family account</button>
            <button class="linkbtn" type="button" data-go="forgot">Forgot password?</button>`;
        } else if (mode === "register") {
          fields = `<p class="nums" style="margin:0">For parents. After you confirm your email, you add an account for each kid and choose their username and password.</p>`
            + field("Your name", "name", "text", "nickname", 'maxlength="60"') + field("Your email", "email", "email", "email")
            + field("Password", "password", "password", "new-password", 'minlength="8"');
          buttons = `<button class="btn" type="submit">Make account</button><button class="btn ghost" type="button" data-go="login">I already have an account</button>`;
        } else if (mode === "forgot") {
          fields = `<p class="nums" style="margin:0">Parents: type your email and we will send you a link to choose a new password. Kids: ask a parent, who can change your password on the Family page.</p>` + field("Email", "email", "email", "email");
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
          if (f.login) lastEmail = f.login.trim().includes("@") ? f.login.trim() : "";
          const btn = e.target.querySelector("button[type=submit]");
          if (btn) btn.disabled = true;
          try {
            if (mode === "login") {
              const r = await call("POST", "/api/login", f); user = r.user; afterSignIn(); resolve(r);
            } else if (mode === "register") {
              const r = await call("POST", "/api/register", f);
              mode = "sent";
              if (r.emailFailed) draw(`Your account is made, but the email to ${r.email} could not be sent.`, "", true);
              else draw("", `We sent a link to ${r.email}. Open it to confirm your email, then add your kids. Check spam if you do not see it.`, true);
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

  function afterSignIn() { renderBar(); }

  function renderBar() {
    const bar = $("#account");
    if (!bar) return;
    bar.hidden = false;
    bar.innerHTML = `<span>Signed in as <b>${esc(user.name)}</b></span>
      ${user.role === "parent" ? `<button class="linkbtn" id="familyBtn">Family</button>` : `<a href="/api/attempts.csv" download>Download my answers</a>`}
      <button class="linkbtn" id="logout">Sign out</button>`;
    const fb = $("#familyBtn");
    if (fb) fb.addEventListener("click", () => Progress.family());
    $("#logout").addEventListener("click", async () => {
      try { await call("POST", "/api/logout"); } catch (e) {}
      location.reload();
    });
  }

  return { init, call, get signedIn() { return !!user; }, get user() { return user; } };
})();

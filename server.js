// Bebras Practice server: serves the page and a small JSON API for student
// accounts, saved progress, and a log of every answer attempt.
// No npm dependencies: uses Node's built-in http, crypto and sqlite (Node 22.13+).
//
//   node server.js                 # http://localhost:3000
//   PORT=8080 DB_PATH=/var/data/bebras.db REGISTRATION_CODE=beaver node server.js

"use strict";
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { DatabaseSync } = require("node:sqlite");

const ROOT = __dirname;
const PORT = +process.env.PORT || 3000;
const DB_PATH = process.env.DB_PATH || path.join(ROOT, "data", "bebras.db");
const REG_CODE = process.env.REGISTRATION_CODE || ""; // empty: anyone can sign up
const RESEND_KEY = process.env.RESEND_API_KEY || "";   // empty: email links are printed to the console instead
const EMAIL_FROM = process.env.EMAIL_FROM || "Bebras Practice <onboarding@resend.dev>";
// links in emails point here; Render sets RENDER_EXTERNAL_URL itself. Never taken from the request's Host header.
const APP_URL = (process.env.APP_URL || process.env.RENDER_EXTERNAL_URL || `http://localhost:${PORT}`).replace(/\/+$/, "");
const TOKEN_HOURS = { verify: 48, reset: 1 };
const SESSION_DAYS = 60;
const COOKIE = "bebras_sid";

// ---------- database
fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });
const db = new DatabaseSync(DB_PATH);
db.exec(`
  PRAGMA journal_mode = WAL;
  PRAGMA foreign_keys = ON;
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    pw_hash TEXT NOT NULL,
    created_at INTEGER NOT NULL
  );
  CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at INTEGER NOT NULL
  );
  CREATE TABLE IF NOT EXISTS progress (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    state TEXT NOT NULL,
    updated_at INTEGER NOT NULL
  );
  CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    client_id TEXT NOT NULL,
    family TEXT NOT NULL,
    level INTEGER NOT NULL,
    seed INTEGER NOT NULL,
    question_type TEXT,
    try_number INTEGER NOT NULL,
    correct INTEGER NOT NULL,
    answer TEXT,
    misconceptions TEXT,
    hints_shown INTEGER NOT NULL DEFAULT 0,
    ms_on_problem INTEGER,
    created_at INTEGER NOT NULL,
    UNIQUE (user_id, client_id)
  );
  CREATE INDEX IF NOT EXISTS attempts_user_time ON attempts (user_id, created_at);
  CREATE TABLE IF NOT EXISTS email_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose TEXT NOT NULL,          -- 'verify' or 'reset'
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
  );
`);
// accounts made before email confirmation existed count as confirmed
if (!db.prepare("PRAGMA table_info(users)").all().some(c => c.name === "email_verified_at")) {
  db.exec("ALTER TABLE users ADD COLUMN email_verified_at INTEGER; UPDATE users SET email_verified_at = created_at;");
}
const q = {
  userByEmail: db.prepare("SELECT * FROM users WHERE email = ?"),
  addUser: db.prepare("INSERT INTO users (email, name, pw_hash, created_at) VALUES (?, ?, ?, ?)"),
  userById: db.prepare("SELECT * FROM users WHERE id = ?"),
  markVerified: db.prepare("UPDATE users SET email_verified_at = ? WHERE id = ? AND email_verified_at IS NULL"),
  setPassword: db.prepare("UPDATE users SET pw_hash = ? WHERE id = ?"),
  dropUserSessions: db.prepare("DELETE FROM sessions WHERE user_id = ?"),
  addToken: db.prepare("INSERT INTO email_tokens (token_hash, user_id, purpose, created_at, expires_at) VALUES (?, ?, ?, ?, ?)"),
  recentToken: db.prepare("SELECT 1 FROM email_tokens WHERE user_id = ? AND purpose = ? AND created_at > ?"),
  findToken: db.prepare("SELECT * FROM email_tokens WHERE token_hash = ? AND purpose = ? AND expires_at > ?"),
  dropTokens: db.prepare("DELETE FROM email_tokens WHERE user_id = ? AND purpose = ?"),
  dropExpiredTokens: db.prepare("DELETE FROM email_tokens WHERE expires_at <= ?"),
  addSession: db.prepare("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)"),
  session: db.prepare("SELECT u.id, u.email, u.name FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ? AND s.expires_at > ?"),
  dropSession: db.prepare("DELETE FROM sessions WHERE token_hash = ?"),
  dropExpired: db.prepare("DELETE FROM sessions WHERE expires_at <= ?"),
  getState: db.prepare("SELECT state FROM progress WHERE user_id = ?"),
  putState: db.prepare(`INSERT INTO progress (user_id, state, updated_at) VALUES (?, ?, ?)
    ON CONFLICT (user_id) DO UPDATE SET state = excluded.state, updated_at = excluded.updated_at`),
  addAttempt: db.prepare(`INSERT OR IGNORE INTO attempts
    (user_id, client_id, family, level, seed, question_type, try_number, correct, answer, misconceptions, hints_shown, ms_on_problem, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`),
  attempts: db.prepare("SELECT * FROM attempts WHERE user_id = ? ORDER BY created_at, id"),
  summary: db.prepare(`SELECT family, COUNT(*) AS attempts,
      SUM(try_number = 1) AS first_tries, SUM(try_number = 1 AND correct) AS first_try_right
    FROM attempts WHERE user_id = ? GROUP BY family ORDER BY family`)
};

// ---------- passwords and sessions
function hashPassword(pw) {
  const salt = crypto.randomBytes(16);
  const key = crypto.scryptSync(pw, salt, 64);
  return `scrypt$${salt.toString("hex")}$${key.toString("hex")}`;
}
function checkPassword(pw, stored) {
  const [, saltHex, keyHex] = stored.split("$");
  const key = crypto.scryptSync(pw, Buffer.from(saltHex, "hex"), 64);
  return crypto.timingSafeEqual(key, Buffer.from(keyHex, "hex"));
}
// a password hash to compare against when the email is unknown, so timing does not reveal which emails exist
const DUMMY_HASH = hashPassword(crypto.randomBytes(16).toString("hex"));
const sha256 = (s) => crypto.createHash("sha256").update(s).digest("hex");

function startSession(res, req, userId) {
  const token = crypto.randomBytes(32).toString("base64url");
  q.addSession.run(sha256(token), userId, Date.now() + SESSION_DAYS * 864e5);
  setCookie(res, req, token, SESSION_DAYS * 86400);
}
function setCookie(res, req, value, maxAge) {
  const secure = req.headers["x-forwarded-proto"] === "https" || req.socket.encrypted;
  res.setHeader("Set-Cookie", `${COOKIE}=${value}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${maxAge}${secure ? "; Secure" : ""}`);
}
function tokenOf(req) {
  const m = (req.headers.cookie || "").match(new RegExp(`(?:^|;\\s*)${COOKIE}=([^;]+)`));
  return m ? m[1] : null;
}
function currentUser(req) {
  const t = tokenOf(req);
  return t ? q.session.get(sha256(t), Date.now()) || null : null;
}

// simple per-IP throttle for login/register: 20 tries per 15 minutes
const tries = new Map();
function throttled(req) {
  const ip = (req.headers["x-forwarded-for"] || req.socket.remoteAddress || "").split(",")[0].trim();
  const now = Date.now(), rec = tries.get(ip) || { n: 0, since: now };
  if (now - rec.since > 15 * 60e3) { rec.n = 0; rec.since = now; }
  rec.n++; tries.set(ip, rec);
  return rec.n > 20;
}
setInterval(() => { q.dropExpired.run(Date.now()); q.dropExpiredTokens.run(Date.now()); tries.clear(); }, 60 * 60e3).unref();

// ---------- email (Resend)
const escHTML = (s) => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function sendEmail(to, subject, text, html) {
  if (!RESEND_KEY) { console.log(`[email not sent: no RESEND_API_KEY] to ${to}: ${subject}\n${text}\n`); return; }
  const r = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { Authorization: `Bearer ${RESEND_KEY}`, "Content-Type": "application/json" },
    body: JSON.stringify({ from: EMAIL_FROM, to: [to], subject, text, html }),
    signal: AbortSignal.timeout(10e3)
  });
  if (!r.ok) throw new Error(`Resend ${r.status}: ${(await r.text()).slice(0, 300)}`);
}

// Makes a one-time link token and emails it. The token goes after '#', so it never reaches
// server logs, and the page has to POST it: mail scanners that open links cannot use it up.
// At most one email per user and purpose per minute. Returns false if the email failed.
async function emailLink(user, purpose) {
  const now = Date.now();
  if (q.recentToken.get(user.id, purpose, now - 60e3)) return true;
  const token = crypto.randomBytes(32).toString("base64url");
  q.addToken.run(sha256(token), user.id, purpose, now, now + TOKEN_HOURS[purpose] * 3600e3);
  const link = `${APP_URL}/#${purpose}=${token}`;
  const [subject, line, button] = purpose === "verify"
    ? ["Confirm your Bebras Practice account", "Click the button below to confirm your email and start practicing.", "Confirm my email"]
    : ["Reset your Bebras Practice password", "Someone asked to reset your password. If it was you, click the button below. It works for 1 hour.", "Choose a new password"];
  const text = `Hi ${user.name},\n\n${line}\n\n${link}\n\nIf you did not ask for this, you can ignore this email.`;
  const html = `<div style="font-family:system-ui,sans-serif;font-size:16px;line-height:1.5;color:#16233b;max-width:480px">
    <p>Hi ${escHTML(user.name)},</p><p>${line}</p>
    <p><a href="${escHTML(link)}" style="display:inline-block;background:#2f5dff;color:#fff;padding:10px 18px;border-radius:10px;text-decoration:none;font-weight:600">${button}</a></p>
    <p style="font-size:14px;color:#5a6880">Or paste this link into your browser:<br>${escHTML(link)}</p>
    <p style="font-size:14px;color:#5a6880">If you did not ask for this, you can ignore this email.</p></div>`;
  try { await sendEmail(user.email, subject, text, html); return true; }
  catch (e) { console.error(`Could not send ${purpose} email to user ${user.id}:`, e.message); q.dropTokens.run(user.id, purpose); return false; }
}
// Checks a link token and uses it up (all links of that purpose for the user stop working).
function useToken(token, purpose) {
  if (typeof token !== "string" || !token) return null;
  const row = q.findToken.get(sha256(token), purpose, Date.now());
  if (!row) return null;
  q.dropTokens.run(row.user_id, purpose);
  return q.userById.get(row.user_id);
}

// ---------- HTTP helpers
function send(res, code, body, headers = {}) {
  const isStr = typeof body === "string" || Buffer.isBuffer(body);
  res.writeHead(code, { "Content-Type": isStr ? "text/plain; charset=utf-8" : "application/json", "Cache-Control": "no-store", ...headers });
  res.end(isStr ? body : JSON.stringify(body));
}
function readJSON(req, limit = 256 * 1024) {
  return new Promise((resolve, reject) => {
    if (!/^application\/json/.test(req.headers["content-type"] || "")) return reject(Object.assign(new Error("Expected JSON"), { code: 415 }));
    let size = 0; const chunks = [];
    req.on("data", c => { size += c.length; if (size > limit) { reject(Object.assign(new Error("Too large"), { code: 413 })); req.destroy(); } else chunks.push(c); });
    req.on("end", () => { try { resolve(JSON.parse(Buffer.concat(chunks).toString() || "{}")); } catch (e) { reject(Object.assign(new Error("Bad JSON"), { code: 400 })); } });
    req.on("error", reject);
  });
}
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const str = (v, max) => (typeof v === "string" ? v.trim().slice(0, max) : "");
const int = (v) => (Number.isInteger(v) ? v : null);

// ---------- API
const api = {
  "GET /api/me"(req, res, user) {
    if (!user) return send(res, 200, { user: null, registrationCode: !!REG_CODE });
    const row = q.getState.get(user.id);
    send(res, 200, { user, state: row ? JSON.parse(row.state) : null });
  },
  async "POST /api/register"(req, res) {
    if (throttled(req)) return send(res, 429, { error: "Too many tries. Wait a few minutes." });
    const b = await readJSON(req);
    const email = str(b.email, 200).toLowerCase(), name = str(b.name, 60), pw = typeof b.password === "string" ? b.password : "";
    if (!EMAIL_RE.test(email)) return send(res, 400, { error: "Enter a valid email address." });
    if (!name) return send(res, 400, { error: "Enter your name." });
    if (pw.length < 8 || pw.length > 200) return send(res, 400, { error: "Passwords need at least 8 characters." });
    if (REG_CODE && str(b.code, 200) !== REG_CODE) return send(res, 403, { error: "That family code is not right." });
    if (q.userByEmail.get(email)) return send(res, 409, { error: "An account with that email already exists. Sign in instead." });
    const { lastInsertRowid } = q.addUser.run(email, name, hashPassword(pw), Date.now());
    const sent = await emailLink({ id: Number(lastInsertRowid), email, name }, "verify");
    send(res, 200, { checkEmail: true, email, emailFailed: !sent });
  },
  // Always answers the same way, so it cannot be used to find out which emails have accounts.
  async "POST /api/resend-confirmation"(req, res) {
    if (throttled(req)) return send(res, 429, { error: "Too many tries. Wait a few minutes." });
    const b = await readJSON(req);
    const u = q.userByEmail.get(str(b.email, 200).toLowerCase());
    if (u && !u.email_verified_at) await emailLink(u, "verify");
    send(res, 200, { ok: true });
  },
  async "POST /api/confirm"(req, res) {
    if (throttled(req)) return send(res, 429, { error: "Too many tries. Wait a few minutes." });
    const b = await readJSON(req);
    const u = useToken(b.token, "verify");
    if (!u) return send(res, 400, { error: "That confirmation link has expired or was already used. Try signing in, or ask for a new link." });
    q.markVerified.run(Date.now(), u.id);
    startSession(res, req, u.id);
    const row = q.getState.get(u.id);
    send(res, 200, { user: { id: u.id, email: u.email, name: u.name }, state: row ? JSON.parse(row.state) : null });
  },
  async "POST /api/forgot"(req, res) {
    if (throttled(req)) return send(res, 429, { error: "Too many tries. Wait a few minutes." });
    const b = await readJSON(req);
    const u = q.userByEmail.get(str(b.email, 200).toLowerCase());
    if (u) await emailLink(u, "reset");
    send(res, 200, { ok: true });
  },
  async "POST /api/reset"(req, res) {
    if (throttled(req)) return send(res, 429, { error: "Too many tries. Wait a few minutes." });
    const b = await readJSON(req);
    const pw = typeof b.password === "string" ? b.password : "";
    if (pw.length < 8 || pw.length > 200) return send(res, 400, { error: "Passwords need at least 8 characters." });
    const u = useToken(b.token, "reset");
    if (!u) return send(res, 400, { error: "That reset link has expired or was already used. Ask for a new one." });
    q.setPassword.run(hashPassword(pw), u.id);
    q.dropUserSessions.run(u.id);          // sign out everywhere else
    q.markVerified.run(Date.now(), u.id);  // the link proves they read this inbox
    startSession(res, req, u.id);
    const row = q.getState.get(u.id);
    send(res, 200, { user: { id: u.id, email: u.email, name: u.name }, state: row ? JSON.parse(row.state) : null });
  },
  async "POST /api/login"(req, res) {
    if (throttled(req)) return send(res, 429, { error: "Too many tries. Wait a few minutes." });
    const b = await readJSON(req);
    const email = str(b.email, 200).toLowerCase(), pw = typeof b.password === "string" ? b.password : "";
    const u = q.userByEmail.get(email);
    const ok = checkPassword(pw, u ? u.pw_hash : DUMMY_HASH) && !!u;
    if (!ok) return send(res, 401, { error: "That email and password do not match." });
    if (!u.email_verified_at) return send(res, 403, { error: "Confirm your email first. Look for our email, or send it again.", unconfirmed: true });
    startSession(res, req, u.id);
    const row = q.getState.get(u.id);
    send(res, 200, { user: { id: u.id, email: u.email, name: u.name }, state: row ? JSON.parse(row.state) : null });
  },
  "POST /api/logout"(req, res) {
    const t = tokenOf(req);
    if (t) q.dropSession.run(sha256(t));
    setCookie(res, req, "", 0);
    send(res, 200, { ok: true });
  },
  async "PUT /api/state"(req, res, user) {
    if (!user) return send(res, 401, { error: "Log in first." });
    const b = await readJSON(req);
    if (!b.state || typeof b.state !== "object") return send(res, 400, { error: "Missing state." });
    q.putState.run(user.id, JSON.stringify(b.state), Date.now());
    send(res, 200, { ok: true });
  },
  // Takes a list so the page can resend attempts it saved while offline. client_id makes resends harmless.
  async "POST /api/attempts"(req, res, user) {
    if (!user) return send(res, 401, { error: "Log in first." });
    const b = await readJSON(req);
    const list = Array.isArray(b.attempts) ? b.attempts.slice(0, 500) : [];
    let saved = 0;
    db.exec("BEGIN");
    try {
      for (const a of list) {
        const cid = str(a.id, 64), fam = str(a.family, 40);
        if (!cid || !fam || int(a.level) === null || int(a.seed) === null || int(a.try) === null) continue;
        const r = q.addAttempt.run(user.id, cid, fam, a.level, a.seed, str(a.questionType, 40) || null, a.try, a.correct ? 1 : 0,
          a.answer === undefined ? null : JSON.stringify(a.answer).slice(0, 4000),
          JSON.stringify(Array.isArray(a.tags) ? a.tags.slice(0, 20).map(t => String(t).slice(0, 60)) : []),
          int(a.hints) || 0, int(a.ms), Number.isFinite(a.t) && a.t > 0 && a.t <= Date.now() + 60e3 ? Math.round(a.t) : Date.now());
        saved += Number(r.changes);
      }
      db.exec("COMMIT");
    } catch (e) { db.exec("ROLLBACK"); throw e; }
    send(res, 200, { ok: true, received: list.length, saved });
  },
  "GET /api/summary"(req, res, user) {
    if (!user) return send(res, 401, { error: "Log in first." });
    send(res, 200, { families: q.summary.all(user.id) });
  },
  "GET /api/attempts.csv"(req, res, user) {
    if (!user) return send(res, 401, "Log in first.");
    const cols = ["created_at", "family", "level", "seed", "question_type", "try_number", "correct", "answer", "misconceptions", "hints_shown", "ms_on_problem"];
    const cell = (v) => { const s = v === null ? "" : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
    const lines = [cols.join(",")].concat(q.attempts.all(user.id).map(r =>
      cols.map(c => cell(c === "created_at" ? new Date(r[c]).toISOString() : r[c])).join(",")));
    send(res, 200, lines.join("\n") + "\n", { "Content-Type": "text/csv; charset=utf-8", "Content-Disposition": `attachment; filename="bebras-attempts.csv"` });
  }
};

// ---------- static files: only the page and the problem folders (never tools/, data/ or this file)
const FAMILY_DIRS = new Set([...fs.readFileSync(path.join(ROOT, "index.html"), "utf8").matchAll(/src="([a-z-]+)\/manifest\.js"/g)].map(m => m[1]));
const TOP_FILES = new Set(["index.html", "app.js", "account.js", "styles.css", "coach.js"]);
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8" };

function serveStatic(req, res) {
  let p;
  try { p = decodeURIComponent(new URL(req.url, "http://x").pathname); } catch (e) { return send(res, 400, "Bad path"); }
  if (p === "/") p = "/index.html";
  const parts = p.slice(1).split("/");
  const allowed = (parts.length === 1 && TOP_FILES.has(parts[0]))
    || (parts.length === 2 && FAMILY_DIRS.has(parts[0]) && /^[A-Za-z0-9_-]+\.js$/.test(parts[1]));
  if (!allowed) return send(res, 404, "Not found");
  const file = path.join(ROOT, ...parts);
  fs.readFile(file, (err, data) => {
    if (err) return send(res, 404, "Not found");
    res.writeHead(200, { "Content-Type": TYPES[path.extname(file)] || "application/octet-stream", "Cache-Control": "no-cache" });
    res.end(req.method === "HEAD" ? undefined : data);
  });
}

const server = http.createServer(async (req, res) => {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("Referrer-Policy", "same-origin");
  const route = `${req.method} ${req.url.split("?")[0]}`;
  try {
    if (api[route]) return await api[route](req, res, currentUser(req));
    if (req.url.startsWith("/api/")) return send(res, 404, { error: "No such endpoint." });
    if (req.method !== "GET" && req.method !== "HEAD") return send(res, 405, "Method not allowed");
    serveStatic(req, res);
  } catch (e) {
    const status = typeof e.code === "number" ? e.code : 500;
    if (!res.headersSent) send(res, status, { error: status === 500 ? "Server error." : e.message });
    if (status === 500) console.error(e);
  }
});
server.listen(PORT, () => console.log(`Bebras Practice on http://localhost:${PORT}  (db: ${DB_PATH}${REG_CODE ? ", family code required" : ""}; `
  + `${RESEND_KEY ? `email via Resend from ${EMAIL_FROM}` : "no RESEND_API_KEY: email links print here"}; links to ${APP_URL})`));

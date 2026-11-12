// The tutor: reads a student's first-try history against the concept map and
// decides what to practice next. Pure functions only, so the practice page and
// the progress page share one model (and node can test it).
//
// Index    built once from the loaded problems: which concepts each family level
//          tests and which misconceptions its problems can catch.
// model    per-concept mastery from first tries (weighted by level and recency),
//          and per-misconception counts.
// choose   the next family and level for mixed Practice mode.
// remedyFor when a misconception repeats: an easier level aimed at it, or a
//          prerequisite concept that is not shown yet.

(function (root) {
  "use strict";

  // Some answer modes are graded live in the page, so their tags are not in the problem file.
  const LIVE_TAGS = {
    press: ["XOR_AS_OR", "BOTH_AS_EITHER", "EXTRA_BUTTONS"],
    fill: ["PARITY_CORNER", "PARITY_ROWS_ONLY", "PARITY_COLS_ONLY"],
    hops: ["STOPS_AT_DEAD_END", "HOPS_WRONG_SIZE", "SWAPS_HOP_DIRECTIONS", "LANDS_TWICE"]
  };
  const RECENT = 10;          // a first try counts half as much after 10 newer ones on the same concept
  const SHOWN = 0.75, SHAKY = 0.5, MIN_EVIDENCE = 3;
  const DAY = 864e5;

  // Misconceptions a problem can catch: its tagged distractors plus live-graded tags.
  function problemTags(p) {
    const s = new Set();
    (p.distractors || []).forEach(d => (d.misconceptions || []).forEach(t => s.add(t)));
    Object.values(p.value_tags || {}).forEach(v => v.forEach(t => s.add(t)));
    Object.values(p.cell_tags || {}).forEach(v => v.forEach(t => s.add(t)));
    Object.keys(p.misconception_paths || {}).forEach(t => s.add(t));
    if (p.entry === "press") LIVE_TAGS.press.forEach(t => s.add(t));
    if (p.entry === "cells" && p.question_type === "fill") LIVE_TAGS.fill.forEach(t => s.add(t));
    if (p.entry === "hops") LIVE_TAGS.hops.forEach(t => s.add(t));
    return s;
  }

  // bank: { folder: { level: [problem, ...] } }, coach: the BEBRAS.coach data
  function index(bank, coach) {
    const X = { levels: {}, order: {}, famConcepts: {}, conceptAt: {}, covered: new Set(), coach };
    for (const fam of Object.keys(bank)) {
      X.levels[fam] = {}; X.famConcepts[fam] = new Set();
      X.order[fam] = Object.keys(bank[fam]).map(Number).sort((a, b) => a - b);
      for (const lv of X.order[fam]) {
        const list = bank[fam][lv], concepts = new Set(), tags = {};
        list.forEach(p => {
          p.concepts.forEach(c => concepts.add(c));
          problemTags(p).forEach(t => { tags[t] = (tags[t] || 0) + 1; });
        });
        Object.keys(tags).forEach(t => { tags[t] /= list.length; });   // share of this level's problems that can catch t
        X.levels[fam][lv] = { concepts: [...concepts], tags };
        concepts.forEach(c => {
          X.famConcepts[fam].add(c); X.covered.add(c);
          (X.conceptAt[c] = X.conceptAt[c] || []).push({ fam, level: lv });
        });
      }
    }
    return X;
  }

  // 0 at a family's first level, 1 at its last
  function rel(X, fam, level) {
    const o = X.order[fam] || [], i = o.indexOf(level);
    return o.length > 1 && i >= 0 ? i / (o.length - 1) : 0;
  }
  const prereqs = (X, c) => (X.coach.prereqs || {})[c] || [];

  function status(n, evidence, score) {
    if (!n) return "new";
    if (evidence < MIN_EVIDENCE) return "started";
    return score >= SHOWN ? "shown" : score < SHAKY ? "shaky" : "learning";
  }

  // events: first tries, oldest first: { fam, level, correct, tags, t, hints }
  function model(events, X) {
    const per = {}, M = { concepts: {}, tags: {}, famCount: {}, famLast: {}, events };
    events.forEach(e => {
      const L = X.levels[e.fam] && X.levels[e.fam][e.level];
      if (!L) return;
      L.concepts.forEach(c => (per[c] = per[c] || []).push(e));
      M.famCount[e.fam] = (M.famCount[e.fam] || 0) + 1;
      M.famLast[e.fam] = Math.max(M.famLast[e.fam] || 0, e.t || 0);
    });
    for (const c of X.covered) {
      const list = per[c] || [], n = list.length;
      // starts at 1 right out of 2, so one answer cannot decide anything
      let num = 1, den = 2, evidence = 0, right = 0;
      list.forEach((e, i) => {
        const r = rel(X, e.fam, e.level), recency = Math.pow(0.5, (n - 1 - i) / RECENT);
        // a right answer on a hard level, or a miss on an easy one, says more
        const w = recency * (e.correct ? 0.6 + 0.8 * r : 1.4 - 0.8 * r);
        const credit = e.correct ? (e.hints ? 0.6 : 1) : 0;
        num += w * credit; den += w; evidence += w;
        if (e.correct) right++;
      });
      const score = num / den;
      M.concepts[c] = { id: c, n, right, score, evidence, status: status(n, evidence, score), last: n ? list[n - 1].t : 0 };
    }
    events.forEach((e, i) => {
      (e.tags || []).forEach(t => {
        const m = M.tags[t] = M.tags[t] || { id: t, count: 0, weight: 0, last: 0, fams: {} };
        m.count++; m.weight += Math.pow(0.5, (events.length - 1 - i) / 15);
        m.last = Math.max(m.last, e.t || 0); m.fams[e.fam] = (m.fams[e.fam] || 0) + 1;
      });
    });
    return M;
  }

  // ctx: { levelOf(fam), recentFams: [...oldest→newest], now, random }
  function choose(M, X, ctx) {
    const now = ctx.now || Date.now(), rnd = ctx.random || Math.random, r = ctx.recentFams || [];
    const triedFams = Object.keys(M.famCount).length;
    // bring in new puzzle types one at a time: wait while two are still barely started
    const justStarted = Object.values(M.famCount).filter(n => n < 3).length;
    const cands = Object.keys(X.levels).map(fam => {
      const level = X.order[fam].includes(ctx.levelOf(fam)) ? ctx.levelOf(fam) : X.order[fam][0];
      const concepts = X.levels[fam][level].concepts, st = concepts.map(c => M.concepts[c]);
      let value, kind;
      if (!M.famCount[fam]) { kind = "new"; value = justStarted >= 2 ? 0.1 : triedFams < 3 ? 0.9 : 0.6; }
      else if (st.every(s => s.status === "shown")) {
        // spaced review: worth more the longer it has been
        kind = "review"; value = 0.15 + 0.5 * Math.min(1, (now - (M.famLast[fam] || 0)) / (5 * DAY));
      } else {
        kind = "practice"; value = 0.45 + st.reduce((a, s) => a + (1 - s.score), 0) / st.length;
      }
      // prerequisites taught by other puzzle types should be shown first
      let ready = 1, waitingOn = null;
      concepts.forEach(c => prereqs(X, c).forEach(([p, strength]) => {
        if (!X.covered.has(p) || X.famConcepts[fam].has(p) || M.concepts[p].status === "shown") return;
        ready *= strength === "firm" ? 0.25 : 0.7;
        waitingOn = waitingOn || p;
      }));
      // variety: never three in a row, and prefer types not seen lately
      let vary = 1;
      if (r.length >= 2 && r[r.length - 1] === fam && r[r.length - 2] === fam) vary = 0;
      else if (r[r.length - 1] === fam) vary = 0.5;
      // and fewer of the types that filled the last few puzzles
      vary *= Math.pow(0.7, r.slice(-6).filter(x => x === fam).length);
      const focus = st.slice().sort((a, b) => a.score - b.score)[0].id;   // the weakest concept at this level
      return { fam, level, kind, concepts, focus, waitingOn, w: value * ready * vary };
    }).filter(c => c.w > 0);
    const total = cands.reduce((a, c) => a + c.w * c.w, 0);
    let x = rnd() * total;
    for (const c of cands) { x -= c.w * c.w; if (x <= 0) return c; }
    return cands[cands.length - 1];
  }

  // After a first-try miss: if one misconception shows up twice in the last 8 first tries,
  // plan a short detour. ended: { tag: time a detour for it finished } so old misses are not recounted.
  function remedyFor(M, X, ctx) {
    const ev = M.events, last = ev[ev.length - 1];
    if (!last || last.correct || !(last.tags || []).length) return null;
    const ended = ctx.ended || {};
    const win = ev.slice(-8);
    const counts = last.tags.map(t => [t, win.filter(e => !e.correct && (e.tags || []).includes(t) && (e.t || 0) > (ended[t] || 0)).length])
      .filter(([, n]) => n >= 2).sort((a, b) => b[1] - a[1]);
    if (!counts.length) return null;
    const tag = counts[0][0], fam = last.fam, lv = last.level;
    const concept = (X.coach.misconceptions[tag] || {}).concept;
    const catches = (f, l) => ((X.levels[f][l] || {}).tags || {})[tag] >= 0.5;
    // 1. an easier level of the same puzzle type whose problems can catch this misconception
    //    (the easiest such level, but at most two levels down)
    const lower = X.order[fam].filter(l => l < lv && catches(fam, l));
    if (lower.length) {
      const near = lower.filter(l => l >= lv - 2);
      return { tag, concept, fam, level: near.length ? near[0] : lower[lower.length - 1], kind: "easier", from: { fam, level: lv } };
    }
    // 2. a prerequisite of the misconception's concept that is not shown yet, firm ones first
    const ps = prereqs(X, concept).slice().sort((a, b) => (a[1] === "firm" ? 0 : 1) - (b[1] === "firm" ? 0 : 1));
    for (const [p] of ps) {
      if (!X.covered.has(p) || M.concepts[p].status === "shown") continue;
      const at = X.conceptAt[p].filter(x => !X.levels[x.fam][x.level].concepts.includes(concept));
      if (!at.length) continue;
      const same = at.filter(x => x.fam === fam && x.level < lv);
      let pick;
      if (same.length) pick = same[same.length - 1];
      else {
        const other = at.filter(x => x.fam !== fam), working = other.filter(x => x.level <= ctx.levelOf(x.fam));
        pick = working.length ? working[working.length - 1] : other[0] || at[0];
      }
      return { tag, concept, prereq: p, fam: pick.fam, level: pick.level, kind: "prereq", from: { fam, level: lv } };
    }
    // 3. more of the same level, choosing problems that can catch it
    if (catches(fam, lv)) return { tag, concept, fam, level: lv, kind: "again", from: { fam, level: lv } };
    return null;
  }

  // A short line for the student about why this puzzle came up.
  function why(pick, coach) {
    const title = coach.titles[pick.fam] || pick.fam;
    const cname = (c) => { const n = coach.concepts[c] || c; return n[0].toLowerCase() + n.slice(1); };
    switch (pick.kind) {
      case "easier": return `A step back: an easier ${title} puzzle to practice one tricky idea.`;
      case "prereq": return `A step back to practice ${cname(pick.prereq)}. It helps with the last few puzzles.`;
      case "again": return `One more like the last one. Take your time, and take a hint if you want one.`;
      case "review": return `Quick review of something you already know.`;
      case "new": return `Something new: ${title}.`;
      default: return `Practice: ${cname(pick.focus || pick.concepts[0])}.`;
    }
  }

  const api = { index, model, choose, remedyFor, why, problemTags, SHOWN, SHAKY };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Tutor = api;
})(typeof window !== "undefined" ? window : globalThis);

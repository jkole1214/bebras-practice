// Answer sounds, made with Web Audio so there are no sound files to load.
//   Sound.right()  a bright, quick three-note chime going up
//   Sound.miss()   two soft, low notes stepping down: "not quite, try again", never a buzzer
// Sound can be turned off with the speaker button; the choice is kept per browser.
(function (root) {
  "use strict";
  const KEY = "kerbopple-sound";
  let ctx = null, on = true;
  try { on = localStorage.getItem(KEY) !== "off"; } catch (e) { /* storage blocked: keep sound on */ }

  function audio() {
    if (!ctx) {
      const AC = root.AudioContext || root.webkitAudioContext;
      if (!AC) return null;
      ctx = new AC();
    }
    if (ctx.state === "suspended") ctx.resume();
    return ctx;
  }

  // One note: a few sine partials with a quick rise and a smooth fade, through an optional low-pass.
  function note(a, out, freq, start, { len = 0.6, vol = 0.2, attack = 0.006, partials = [1], cutoff = 0 } = {}) {
    const env = a.createGain();
    env.gain.setValueAtTime(0.0001, start);
    env.gain.exponentialRampToValueAtTime(vol, start + attack);
    env.gain.exponentialRampToValueAtTime(0.0001, start + len);
    let dest = env;
    if (cutoff) {
      const f = a.createBiquadFilter();
      f.type = "lowpass"; f.frequency.value = cutoff; f.Q.value = 0.5;
      f.connect(env); dest = f;
    }
    env.connect(out);
    partials.forEach((amp, i) => {
      const o = a.createOscillator(), g = a.createGain();
      o.type = "sine"; o.frequency.value = freq * (i + 1); g.gain.value = amp;
      o.connect(g); g.connect(dest);
      o.start(start); o.stop(start + len + 0.05);
    });
  }

  function play(build) {
    if (!on) return;
    const a = audio();
    if (!a) return;
    const out = a.createGain();
    out.gain.value = 0.7;
    out.connect(a.destination);
    build(a, out, a.currentTime + 0.02);
  }

  const Sound = {
    // C6, E6, G6 played quickly, like a small glockenspiel
    right() {
      play((a, out, t) => {
        const bell = { len: 0.9, vol: 0.16, partials: [1, 0.25, 0.08] };
        note(a, out, 1046.5, t, bell);
        note(a, out, 1318.5, t + 0.08, bell);
        note(a, out, 1568.0, t + 0.16, { ...bell, len: 1.2 });
      });
    },
    // A4 then G4, soft and rounded like a wooden mallet: calm, a little "hmm", nothing harsh
    miss() {
      play((a, out, t) => {
        const soft = { len: 0.45, vol: 0.13, attack: 0.025, partials: [1, 0.15], cutoff: 1400 };
        note(a, out, 440.0, t, soft);
        note(a, out, 392.0, t + 0.17, { ...soft, len: 0.6 });
      });
    },
    get on() { return on; },
    set(v) {
      on = !!v;
      try { localStorage.setItem(KEY, on ? "on" : "off"); } catch (e) { /* not saved, still applies now */ }
    }
  };
  root.Sound = Sound;
})(window);

# Bebras practice (kerbopple.com)

A practice site, adaptive tutor and problem generator for Bebras-style computational-thinking puzzles, built for one family's kids (ages about 10-14). The problems follow the ideas of official Bebras tasks but never copy their text or pictures: USA Bebras owns those tasks, so describe them only in our own words and keep their wording and artwork out of the repo. The public name is "kerbopple" and leaves out "Bebras" because the name may be a trademark.

Calibrating difficulty against Bebras as a whole doesn't matter. What matters is the concept dependencies and adapting to each kid: when something is hard for a kid, the tutor should notice and back off to the prerequisite.

## Layout

- `index.html`, `app.js`, `styles.css`, `coach.js`: the practice page. Problem files are `.js` (`BEBRAS.add("folder", {...})`), and each family folder has a `manifest.js`. This lets the page still run from `file://`.
- `account.js`, `server.js`: accounts and storage (see below).
- Nine family folders: `rule-tracer`, `lake-crossing`, `signal-lamp`, `robot-routes`, `nuts-and-bolts`, `box-rows`, `lights-on`, `bead-rules`, `pantry-map`. A module's `family` value can differ from its folder name (for example `conveyor` → `nuts-and-bolts`).
- `tools/`: generators (`<module>.py`), independent checkers (`check_<module>.py`), `build_problems.py`, the knowledge map `bebras_knowledge_map.json` (69 tasks, 61 concepts, 77 misconceptions, 9 families, 16 generator candidates), analysis patches with `merge_patch.py`, and `notes.md`, which has a note on each official task. `tools/` is never served.

## Accounts and storage

- `server.js` uses plain Node 24 with built-in `node:sqlite` and has no npm dependencies. Start it with `npm start`. Its env vars are `PORT`, `DB_PATH`, `RESEND_API_KEY`, `EMAIL_FROM` and `APP_URL`. Without a Resend key, emails are printed to the console.
- Accounts use email and password and need email confirmation through Resend. Anyone can sign up; there is no family code.
- The `attempts` table holds one row per try, with: family, level, seed, question_type, try_number, correct, answer, misconceptions (tags), hints_shown, ms_on_problem and created_at. The `progress` table holds each user's page state as JSON.
- It does not store concepts. To get them, read the problem file at `<family>/L<level>-<seed>.js`.
- Attempts are queued in a localStorage outbox and deduped on the server by client id.
- Disk mode (`file://`) still works, with progress saved in localStorage under `bebras-practice-local`.
- Static serving uses an allowlist: the top-level page files and the family folders listed in `index.html`.
- Deployment: the Render Blueprint `render.yaml` defines the web service `kerbopple` (starter plan, disk at `/var/data`). Custom domains are added in the dashboard, never in the yaml. The old static service `bebras-practice` is still built by `tools/build_site.sh` until it is retired.

## Content rules (every family)

- **Single scene model.** One scene model drives both the picture and the solver. Pictures carry `data-*` attributes so checkers can read them.
- **Independent checkers.** A checker never imports its generator. Where possible it rebuilds the problem from the picture and solves it again with different code. Every checker gets a mutation test: corrupt the answer key and the checker must catch it.
- **Tagged distractors.** Every wrong option comes from a named misconception solver, such as `XOR_AS_OR` or `INDIRECTION_OUTSIDE_IN`. Typed answers use `value_tags`. Untagged distractors are not allowed.
- **Rejected problems.** Reject a problem when:
  - the answer is guessable (the smallest, largest or visually shortest option);
  - more than one answer is correct, unless the format grades by evaluating the answer (`press`, `build`);
  - a misconception happens to produce the right answer.
- **Problem record fields:** family, level, question_type, seed, scene, svg, prompt, question, options, answer_index, answer_value, entry, distractors, value_tags, concepts, explanation, hints, plus family extras (pick, cell_tags, codebook, signal, rule_text).
- **Entry modes:** `choice`, `number`, `build`, `press` and `cells`.
- **Explanations.** Lines that start with two spaces render monospace, and `{{rgb}}` renders beads in Bead Rules.
- **Auto-leveling.** Two first-try wins move up a level; two first-try misses move down.
- **Writing style.** Write prompts in plain words for ages 10-14. Hints go from a nudge to the method and never give the answer.

## Workflow

- After any generator change, run `python3 tools/build_problems.py`. The rejected count must stay at 0, or explain why it isn't. Current output: 12 per level, 600 problems.
- Record new analysis of official tasks as a patch merged with `tools/merge_patch.py map.json patch.json`, rather than hand-editing the map.
- Test pages in a browser at phone width, in light and dark mode, with no horizontal scroll.
- Don't commit or push unless asked.
- Write analysis and docs as analyst notes attributed to Claude, not in the user's voice.

## Roadmap (priority order)

1. **Adaptive tutor on the stored history.** Nothing reads the concept map yet; each tab levels on its own. Planned pieces:
   - per-user concept mastery and misconception counts;
   - a mixed "Practice" mode that picks the family and level, respects firm prerequisites, steps back when a misconception repeats, mixes in spaced review and keeps sessions varied;
   - a parent view per kid;
   - findings from the kids' own data (empirical difficulty, distractors nobody picks, levels in the wrong order), written back to the map as observations.
2. **More families** from `generator_candidates`: Virus, Maze, Treasure Box, Colorful Tower, Favorite Gem, the 2015 candidates and game trees. Concepts that have no family yet, and the SOC domain, are not covered.
3. **More analysis** (optional): other years' USA practice challenges, and Kits/Castors.
4. **Small items:** an "explain it back" step after a miss, worksheet export, and per-user accuracy on level select.

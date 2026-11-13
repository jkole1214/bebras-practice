# Bebras practice (kerbopple.com)

A practice site, adaptive tutor and problem generator for Bebras-style computational-thinking puzzles, built for one family's kids (ages about 10-14). The problems follow the ideas of official Bebras tasks but never copy their text or pictures: USA Bebras owns those tasks, so describe them only in our own words and keep their wording and artwork out of the repo. The public name is "kerbopple" and leaves out "Bebras" because the name may be a trademark.

Calibrating difficulty against Bebras as a whole doesn't matter. What matters is the concept dependencies and adapting to each kid: when something is hard for a kid, the tutor should notice and back off to the prerequisite.

## Layout

- `index.html`, `app.js`, `styles.css`, `coach.js`, `sound.js`: the practice page. It only draws puzzles and sends answers. A Practice / Pick a puzzle switch sits at the top; the `data-fam` buttons in `index.html` set the order of puzzle types.
- `engine.js` (server only, never served): loads the problem bank, picks puzzles, strips answers before sending, checks every try, moves levels, runs the tutor and computes the Progress page. Tested by `node tools/test_engine.js`.
- `tutor.js`: the adaptive tutor's pure functions, run by `engine.js` on the server. Tested by `node tools/test_tutor.js`.
- Problem files are `.js` (`BEBRAS.add("folder", {...})`) with a `manifest.js` per folder, read by `engine.js` at startup (restart the server after a rebuild). They are never served: answer keys stay on the server.
- `account.js`, `server.js`: accounts, the practice API and storage (see below).
- Fifteen family folders: `rule-tracer`, `lake-crossing`, `signal-lamp`, `robot-routes`, `nuts-and-bolts`, `box-rows`, `lights-on`, `bead-rules`, `pantry-map`, `paint-pipes`, `code-lock`, `brick-pyramid`, `pass-it-on`, `frog-hops`, `map-pieces`. A module's `family` value can differ from its folder name (for example `conveyor` → `nuts-and-bolts`, `parallel_spread` → `paint-pipes`, `code_clues` → `code-lock`, `brick_rule` → `brick-pyramid`, `friend_reach` → `pass-it-on`, `stone_hops` → `frog-hops`, `gossip_rounds` → `map-pieces`).
- `tools/`: generators (`<module>.py`), independent checkers (`check_<module>.py`), `build_problems.py`, the knowledge map `bebras_knowledge_map.json` (69 tasks, 61 concepts, 113 misconceptions, 15 families, 16 generator candidates), analysis patches with `merge_patch.py`, and `notes.md`, which has a note on each official task. `tools/` is never served.

## Accounts and storage

- `server.js` uses plain Node 24 with built-in `node:sqlite` and has no npm dependencies. Start it with `npm start`. Its env vars are `PORT`, `DB_PATH`, `RESEND_API_KEY`, `EMAIL_FROM` and `APP_URL`. Without a Resend key, emails are printed to the console.
- Family accounts. Only parents sign up (email and password, confirmed through Resend). Parents add kids on the Family page and choose each kid's username and password. Kids sign in with their username (unique across the site, stored lowercase in `users.username`); parents sign in with their email. The login field tells them apart by the `@`. Existing kids get a username made from their name when the server migrates. Reset emails reset only the parent's password; parents change kids' passwords. `users.parent_id` is set for kids, and kids have no email. Never use env vars to grant roles.
- Practice API: `POST /api/next` (`{}`, `{ resume }`, `{ mode }`, `{ level }`), `POST /api/answer` (`{ answer, hints }`), `POST /api/open` (reopen a puzzle from Progress), `POST /api/settings`, `POST /api/reset-levels`, `GET /api/progress?user=`. The server writes every attempt itself; the page cannot write attempts or state directly.
- The `attempts` table holds one row per try, with: family, level, seed, question_type, try_number, correct, answer, misconceptions (tags), hints_shown, ms_on_problem, created_at and served_as (`ladder`, `remedy` or `lookback`; look-backs are left out of levels, the tutor, Progress and `observe.py`).
- The `progress` table holds each student's practice state as JSON (`v: 2`): mode, levels, streaks, seen seeds, tutor plans and the puzzle on screen. Older page-owned states are migrated on read, keeping levels and tutor plans.
- It does not store concepts. The tutor maps family and level to concepts through `Tutor.index` over the bank.
- There is no disk (`file://`) mode and no static build: the page needs the server.
- Static serving uses an allowlist of the top-level page files only.
- Deployment: the Render Blueprint `render.yaml` defines the web service `kerbopple` (starter plan, disk at `/var/data`). Custom domains are added in the dashboard, never in the yaml.

## Content rules (every family)

- **Single scene model.** One scene model drives both the picture and the solver. Pictures carry `data-*` attributes so checkers can read them.
- **Independent checkers.** A checker never imports its generator. Where possible it rebuilds the problem from the picture and solves it again with different code. Every checker gets a mutation test: corrupt the answer key and the checker must catch it.
- **Tagged distractors.** Every wrong option comes from a named misconception solver, such as `XOR_AS_OR` or `INDIRECTION_OUTSIDE_IN`. Typed answers use `value_tags`. Untagged distractors are not allowed. Every tag needs a kid-facing `look_again` question (add it in `tools/make_look_again_patch.py`, merge the patch, rebuild `coach.js`); `tools/test_engine.js` fails on a tag without one. List the tag a level targets first, since the page asks about the first tag that has a question.
- **Rejected problems.** Reject a problem when:
  - the answer is guessable (the smallest, largest or visually shortest option);
  - more than one answer is correct, unless the format grades by evaluating the answer (`press`, `build`);
  - a misconception happens to produce the right answer.
- **Problem record fields:** family, level, question_type, seed, scene, svg, prompt, question, options, answer_index, answer_value, entry, distractors, value_tags, concepts, explanation, hints, plus family extras (pick, cell_tags, codebook, signal, rule_text).
- **Entry modes:** `choice`, `number`, `build`, `press`, `cells`, `code` (Code Lock: tap symbols onto wheels; wrong codes are tagged through `value_tags`) `bricks` (Brick Pyramid: tap bricks to cycle colours) and `hops` (Frog Hops: tap stones in order; graded by playing the trip back, with tags given by the server).
- **Explanations.** Lines that start with two spaces render monospace, and `{{rgb}}` renders beads in Bead Rules.
- **Auto-leveling.** Two first-try wins move up a level; two first-try misses move down.
- **Writing style.** Write prompts in plain words for ages 10-14. Hints go from a nudge to the method and never give the answer.

## Workflow

- After any generator change, run `python3 tools/build_problems.py`. The rejected count must stay at 0, or explain why it isn't. Current output: 12 per level, 960 problems. The build needs `networkx` and gives the same files on every run.
- Record new analysis of official tasks as a patch merged with `tools/merge_patch.py map.json patch.json`, rather than hand-editing the map.
- Test pages in a browser at phone width, in light and dark mode, with no horizontal scroll.
- Don't commit or push unless asked.
- Write analysis and docs as analyst notes attributed to Claude, not in the user's voice.

## Roadmap (priority order)

1. **Adaptive tutor (built, runs on the server).** Practice mode, the Progress page (parents switch between their kids) and `tools/observe.py`, which writes `data_observations` into the map. The details are in the README. Still open: tune the thresholds in `tutor.js` once there is real data.
2. **More families** from `generator_candidates`: Maze, Favorite Gem, Bowl Factory and game trees. Concepts that have no family yet, and the SOC domain, are not covered.
3. **More analysis** (optional): other years' USA practice challenges, and Kits/Castors.
4. **Small items:** worksheet export, and per-user accuracy on level select. (The "look again" step after a miss is built.)

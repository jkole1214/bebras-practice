# Bebras Practice

A practice page for nine puzzle families built from the Bebras example and practice tasks. The problems are original; they reuse the concepts, not the official tasks.

## The tutor

The **Practice** tab (the first tab, and the default for new students) is a tutor. It chooses the puzzle type and level for each puzzle from the student's first tries. The other tabs still work as before: one puzzle type, with its own level ladder.

- **Concept mastery.** Each problem tests concepts from the knowledge map. Every first try updates an estimate for those concepts.
  - Recent tries count more.
  - A right answer on a hard level, or a miss on an easy one, says more.
  - A right first try after a hint counts as part right.
  - Each concept is shown as Not started, Just started, Learning, Shaky or Shown.
- **What comes next.** The tutor favors concepts not yet shown, and holds back a puzzle type until its prerequisites from other types are shown. It brings in new types one at a time. Once a type's concepts are shown, it comes back as spaced review, more often the longer it has been. Sessions stay mixed: never the same type three times in a row.
- **Stepping back.** When the same misconception comes up twice within a student's last 8 first tries, the tutor takes a short detour. It goes to an easier level of the same type whose problems can catch that mistake: the easiest one, at most two levels down. For example, repeated `INDIRECTION_OUTSIDE_IN` on Box Rows level 5 goes back to level 3. If no easier level catches it, it goes to a prerequisite concept that isn't shown yet. The detour ends after two right first tries or four puzzles, and the student returns to their usual levels. Detour puzzles don't move the level ladder.
- **Why this puzzle.** A short line under the puzzle header tells the student why it came up.

**Progress** (next to the tabs) shows, for one student:

- concepts by domain;
- what the tutor is working on;
- the most frequent misconceptions, each with what to try;
- the puzzles missed on the first try, with the first answer and the right one. Each has an **Open** button, which shows that exact puzzle again without moving levels;
- a grid of first-try results by puzzle type and level.

A parent can switch between their kids. Without a server, the page shows this browser's history.

The tutor's logic is in `tutor.js`, and `node tools/test_tutor.js` tests it against the real problem bank.

### Findings from the kids' own answers

A parent can download the family's answers from the bottom of the progress page. Then:

```
python3 tools/observe.py kerbopple-export.json        # or the server's .db file
python3 tools/merge_patch.py tools/bebras_knowledge_map.json tools/observations_patch.json
```

The script prints and saves:

- first-try difficulty per level;
- levels that seem out of order;
- distractors offered many times but never picked;
- wrong answers that match no named misconception.

The merge stores these in the map as `data_observations`. Each merge replaces the previous one, and student names are never included. The export file holds names, so keep it out of the repository; `.gitignore` covers `kerbopple-export*.json`.

## Run it

**With student accounts** (Node 22.13 or newer, no `npm install` needed):

```
npm start                                  # http://localhost:3000
```

Accounts are per family:

- **Parents sign up.** Only parents make accounts: name, email and a password of at least 8 characters. They confirm the email from a link we send.
- **Parents add their kids.** On the **Family** page (in the bar at the top), a parent adds each kid with a name, a username and a password they choose (at least 6 characters). The same page lets them rename a kid, change their username, set a new password, download a kid's answers, or remove a kid. Removing a kid deletes all of that kid's answers.
- **Kids sign in with a username** the parent chooses on the Family page (3 to 20 letters, digits, dots, dashes or underscores, starting with a letter; unique across the site and not case-sensitive). Parents sign in with their email; anything with an `@` is treated as an email. A kid cannot sign in until the parent's email is confirmed. Kids who had accounts before usernames existed get one made from their name the first time the new server starts; the server log prints each one.
- **Password resets go to the parent.** **Forgot password?** on the sign-in card emails the parent a link that works for 1 hour; it resets the parent's password and signs the parent out everywhere else. Kids who forget their password ask a parent to set a new one; that signs the kid out everywhere.
- **Older accounts.** Accounts made before family accounts existed became parent accounts, with their history kept. Accounts made before email confirmation existed count as confirmed.

Levels and history follow each kid to any computer, and **every answer attempt** is saved: each try, not just the first, with the answer given, whether it was right, the misconceptions it matched, how many hints were showing and how long the problem had been on screen. Attempts are saved in the browser first and sent to the server, so a dropped connection loses nothing; they are resent later. Kids can download their own attempts as a CSV with **Download my answers**; parents download each kid's from the Family page. **Reset progress** resets levels but keeps saved attempts.

Everything is in one SQLite file, `data/bebras.db` by default (set `DB_PATH` to move it). To look at every student's attempts:

```
sqlite3 data/bebras.db "SELECT u.name, a.family, a.level, a.try_number, a.correct, datetime(a.created_at/1000,'unixepoch') FROM attempts a JOIN users u ON u.id = a.user_id ORDER BY a.created_at"
```

### Email (Resend)

Emails are sent with [Resend](https://resend.com). Set:

- `RESEND_API_KEY`: your Resend API key.
- `EMAIL_FROM`: the sender, on a domain you have verified in Resend, for example `Bebras Practice <practice@yourdomain.com>`. Without it the sender is Resend's test address `onboarding@resend.dev`, which can only send to the email on your own Resend account.
- `APP_URL`: the site address the links in emails point to. On Render this defaults to the service's own URL; set it for a custom domain. Locally it defaults to `http://localhost:3000`.

```
RESEND_API_KEY=re_... EMAIL_FROM="Bebras Practice <practice@yourdomain.com>" npm start
```

Without `RESEND_API_KEY`, nothing is sent and each email (with its link) is printed in the server's console instead. That is handy for trying things out locally.

Anyone who finds the address can make a family account; they still have to confirm a real email address first, and they only ever see their own family.

**Without a server:** double-click `index.html`. It opens in any modern browser straight from disk, with no sign-in and no internet connection needed. (Fonts load from Google Fonts when online; offline it falls back to system fonts.) Progress (level, history, misconception counts) is then saved in that browser only. Clear it with **Reset progress** under Coach notes.

## Folder layout

```
index.html            page shell
server.js             web server: family accounts, saved progress, attempt log (SQLite)
account.js            sign-in form and syncing progress/attempts to server.js
app.js                practice logic: loading, grading, hints, leveling, coach notes, Practice tab
tutor.js              the tutor: concept mastery, what to practice next, stepping back
progress.js           progress page (parents can switch between their kids) and the Family page
styles.css            styling (light and dark)
coach.js              misconception and concept text, prerequisites and domains (generated)
rule-tracer/          Rule Tracer problems, one file each, plus manifest.js
lake-crossing/        Lake Crossing problems, one file each, plus manifest.js
signal-lamp/          Signal Lamp problems, one file each, plus manifest.js
robot-routes/         Robot Routes problems, one file each, plus manifest.js
nuts-and-bolts/       Nuts and Bolts problems, one file each, plus manifest.js
box-rows/             Box Rows problems, one file each, plus manifest.js
lights-on/            Lights On problems, one file each, plus manifest.js
bead-rules/           Bead Rules problems, one file each, plus manifest.js
pantry-map/           Pantry Map problems, one file each, plus manifest.js
tools/                generators, independent checkers, build script, knowledge map
```

Problem files are named `L<level>-<seed>.js`. Each is one JSON object wrapped in a `BEBRAS.add(...)` call. They are `.js` rather than `.json` because browsers block reading `.json` files from a page opened from disk, but allow loading scripts. Each folder's `manifest.js` lists the files the page loads; a file not in the manifest is ignored.

## Make more problems

Requires Python 3.9+ and networkx (`pip install networkx`).

```
python3 tools/build_problems.py                    # 12 per level (default)
python3 tools/build_problems.py --per-level 30 --seed 5000
```

`python3 tools/build_problems.py --coach-only` rewrites only `coach.js`, for example after a change to the knowledge map, and does not need networkx.

A full build deletes the existing problem files in every family folder, generates new ones, runs every problem through its independent checker (failures are skipped and counted), and rewrites both manifests and `coach.js`. Different `--seed` values give different problems.

To check problems without rebuilding, the checkers take a JSON list of problems:

```
python3 tools/check_conditional_trace.py problems.json
python3 tools/check_shortest_path.py problems.json
python3 tools/check_signal_code.py problems.json
python3 tools/check_grid_routes.py problems.json
python3 tools/check_conveyor.py problems.json
python3 tools/check_pointer_lists.py problems.json
python3 tools/check_logic_gates.py problems.json
python3 tools/check_bead_grammar.py problems.json
python3 tools/check_parity_grid.py problems.json
```

## Levels

**Rule Tracer** (nested IF/ELSE on dice rolls)
1. Trace a roll through one IF/ELSE
2. Trace through a nested IF
3. Same, with two equal dice that a test compares
4. Inverse: which roll leads to a given place
5. Inverse through a nested IF
6. Inverse where the correct roll depends on a tie
7. Three levels of nesting, mixed strict and non-strict tests
8. Counting: how many of the 216 possible rolls reach a given place (type the number)

**Lake Crossing** (cheapest path across islands)
1. Compare three listed routes
2. Find the cheapest total, small map
3. Same, where taking the cheapest next walkway is a trap
4. Build the route by tapping walkways; runner-up is one plank more
5. Build the route; the best one steps back north at least once
6. Counting: how many different cheapest crossings are there (type the number)

**Signal Lamp** (codes that can be read more than one way)
1. Decode a signal from a code with only one possible reading
2. Count the readings of a short signal (multiple choice)
3. Count the readings of a longer signal (type the number)
4. Many codes start with other codes; keep running counts
5. Reverse: which of four signals has exactly a given number of meanings

**Robot Routes** (shortest routes on a street grid with closed intersections)
1. How long is the shortest route? Closures force a detour
2. Count the shortest routes on a small open grid
3. Count with some intersections closed
4. Closures force a detour; type the count
5. Large grid, many closures

**Nuts and Bolts** (matching with a running count, then a stack)
1. Which of four short belts works?
2. Same, with longer belts that go wrong near the end
3. Most nuts in the bucket at once (type the number)
4. Two sizes: a bolt must fit the nut on top of the pile
5. Fewest parts to add so the belt works (type the number)

**Box Rows** (a number used as the next box to look in)
1. One lookup: the number in a given box
2. A lookup inside a lookup, same row
3. Two rows, one inside the other
4. Three rows nested
5. Four lookups, longer rows, a row used twice (type the number)
6. Work backward: which starting box gives the target?

**Lights On** (signals through 'both', 'only one' and 'at least one' boxes)
1. Four buttons: which set of beavers lights the bulb?
2. Four buttons: tap buttons to light the bulb (any working set is right)
3. Eight buttons, like the Bebras task
4. Eight buttons, three kinds of box: light it with the fewest beavers
5. Count every set of buttons that lights the bulb (type the number)

**Bead Rules** (rules that grow a necklace or a line of magic objects)
1. Two necklace rules: which necklace can be made?
2. Three rules, longer necklaces
3. Which necklace can NOT be made? (like Sailor Necklace)
4. Wizard rules with objects that keep changing (like Mysteria)
5. How many different necklaces of a given length? (type the number)

**Pantry Map** (every row and column even; find what changed)
1. One dot rubbed out of a small map: tap where it was
2. The same on a bigger, busier map
3. Two dots rubbed out (like Pantry Map)
4. One shelf changed: rubbed out or smudged
5. Fill in the check row and column yourself

Box Rows never shows an item where a wrong habit (reading outside-in, counting from 0) happens to give the right answer, so a right answer always means the habit is not there.

With "Adjust level automatically" on, two first-try wins move up a level and two first-try misses move down.

## Knowledge map

`tools/bebras_knowledge_map.json` covers two sources, each in all four age groups (Benjamin, Cadet, Junior, Senior):

- the 2015 example sets (38 distinct tasks);
- the 2022-23 practice challenge (31 distinct tasks).

In total: 69 distinct tasks, 61 concepts with prerequisite edges, 77 tagged misconceptions, the nine built generator families, and 16 ranked candidates for new families (the five now built are marked). Each task lists every group, tier and site question id it appears under. `tools/notes.md` has the per-task working notes for both sources.

Both analyses after the original Benjamin/Cadet map were added as patches. To apply them to another copy of the map:

```
python3 tools/merge_patch.py path/to/bebras_knowledge_map.json tools/junior_senior_patch.json
python3 tools/merge_patch.py path/to/bebras_knowledge_map.json tools/practice_2022_patch.json
```

The merge is safe to run twice; it validates every concept, prerequisite and task reference and refuses to write if any are broken. `tools/make_2022_patch.py` is the source the 2022-23 patch JSON was built from.

## Deploy to Render

The folder is set up as a Render Node web service with a persistent disk (`render.yaml`). The disk holds the SQLite database, so accounts and attempts survive redeploys. Disks need a paid instance; the starter plan is enough.

1. Push this folder to a GitHub (or GitLab) repository.
2. In Render, choose **New > Blueprint**, connect the repository, and apply. When asked, set `RESEND_API_KEY` and `EMAIL_FROM`.
3. Every push redeploys. To change the problem set, run `tools/build_problems.py` locally, commit the new problem files, and push.

The server only serves the page and the problem folders. `tools/`, `data/` and the server code are never served. Back up the database from the service's **Shell** tab, for example `sqlite3 /var/data/bebras.db ".backup /var/data/backup.db"`, or with Render's disk snapshots.

`tools/build_site.sh` still builds a plain static copy in `dist/` (no accounts) for hosting without a server.

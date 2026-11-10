# Bebras Practice

A practice page for nine puzzle families built from the Bebras example and practice tasks. The problems are original; they reuse the concepts, not the official tasks.

## Run it

Double-click `index.html`. It opens in any modern browser straight from disk; no server or internet connection is needed. (Fonts load from Google Fonts when online; offline it falls back to system fonts.)

Progress (level, history, misconception counts) is saved in that browser only. Clear it with **Reset progress** under Coach notes.

## Folder layout

```
index.html            page shell
app.js                practice logic: loading, grading, hints, leveling, coach notes
styles.css            styling (light and dark)
coach.js              misconception and concept text for the coach panel (generated)
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

This deletes the existing problem files in every family folder, generates new ones, runs every problem through its independent checker (failures are skipped and counted), and rewrites both manifests and `coach.js`. Different `--seed` values give different problems.

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

The folder is set up as a Render static site (`render.yaml`). Render builds from a Git repository:

1. Put this folder in a GitHub (or GitLab) repository and push it.
2. In Render, choose **New > Blueprint**, connect the repository, and apply. Render reads `render.yaml`, runs `tools/build_site.sh` and serves `dist/` from its CDN. The free static-site plan is enough.
3. Every push redeploys. To change the problem set, run `tools/build_problems.py` locally, commit the new problem files, and push.

`tools/build_site.sh` copies only the page and the problem folders into `dist/`. The generators, checkers, knowledge map and notes in `tools/` are not published. Each browser (and each site address) keeps its own progress, so progress saved while using the page from disk does not carry over to the hosted copy.

"""
Builds practice_2022_patch.json: the 2022-23 USA Bebras practice challenge
(Benjamin, Cadet, Junior, Senior; 31 distinct tasks) in the same patch format
as junior_senior_patch.json. Descriptions are my own wording; no task text or
artwork is reproduced. Run once; the JSON is the artifact that merge_patch.py reads.
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://challenge.bebraschallenge.org/index.php?action=user_competition&grp_id="

def ap(*xs):
    return [{"age_group": g, "tier": t, "grq_id": q, "set": "2022-23 practice"} for g, t, q in xs]

def F(**k):
    return k

def p(*req):  # prerequisite list helper: ("ID", "firm"|"tentative", "reason")
    return [{"id": i, "strength": s, "reason": r} for i, s, r in req]

concepts = [
    F(id="PARITY_CHECK", name="Parity check bits", domain="DATA",
      prerequisites=p(("ELIMINATION", "tentative", "Locating the error is elimination over rows and columns.")),
      description="Extra marks are added so every row and column holds an even count; a change shows up as an odd row and an odd column, and their crossing locates it. The idea behind error-detecting and error-correcting codes.",
      observable_signs="Student counts each row and column and reasons from which ones are odd, rather than guessing cells.",
      tutor_moves=["Ask which rows are odd now, and which columns.", "Ask: if one mark disappeared, how many rows would change from even to odd?"]),
    F(id="GRAMMAR", name="Grammars and rewriting rules", domain="DATA",
      prerequisites=p(("RECURSION", "tentative", "Rules that refer to themselves build nested structure."),
                      ("SEQ_EXEC", "firm", "A derivation is a sequence of rule applications.")),
      description="A start symbol grows by applying rewriting rules; a string belongs to the language if some sequence of rules produces it. Deciding membership is easiest backward: undo a rule whose result is visible, repeat until reaching the start or getting stuck.",
      observable_signs="Student works backward from the string and can show the derivation, or explains why every backward step gets stuck.",
      tutor_moves=["Ask which rule could have made the last part of this string.", "Ask: if you undo that rule, what is left?"]),
    F(id="CYCLE_DETECTION", name="Cycles in a sequence of states", domain="ALG",
      prerequisites=p(("SIMULATION", "firm", "The cycle is found by stepping states forward."),
                      ("MODULAR_ARITHMETIC", "tentative", "Positions on a loop repeat with the loop length.")),
      description="A process that moves through finitely many states must eventually loop; a slow and a fast runner on the same path meet inside the loop (Floyd's tortoise and hare).",
      observable_signs="Student separates the lead-in from the loop and reasons about the gap between runners modulo the loop length.",
      tutor_moves=["Ask how far apart the runners are after each minute once both are on the loop."]),
    F(id="LOGIC_GATES", name="Logic gates and circuits", domain="LOGIC",
      prerequisites=p(("BOOLEAN_AND", "firm", "AND is the first gate; XOR and OR follow.")),
      description="Signals combine through AND (both), OR (at least one) and XOR (exactly one) gates in a tree. To make the output true, work backward from it: an AND needs both inputs, an XOR needs exactly one.",
      observable_signs="Student distinguishes 'only one' (XOR) from 'at least one' (OR) and works from the output back to the inputs.",
      tutor_moves=["Ask what this gate needs from its two inputs for the light to come on.", "Ask what happens to an 'only one' gate if both inputs are on."]),
    F(id="STACK_MATCHING", name="Matching with a counter or stack", domain="DATA",
      prerequisites=p(("STATE", "firm", "The bucket count is state carried along the sequence.")),
      description="Items that open and close (nuts and bolts, brackets) are valid when a running count never drops below zero and ends at zero.",
      observable_signs="Student checks the running count at every step, not only the totals.",
      tutor_moves=["Ask what is in the bucket after each item.", "Ask: is having equal numbers of nuts and bolts enough?"]),
    F(id="INDIRECTION", name="Indirection and indexing", domain="DATA",
      prerequisites=p(("SEQ_EXEC", "firm", "Nested lookups are done one at a time."),
                      ("FUNC_COMPOSITION", "tentative", "A nested lookup is a composition of functions.")),
      description="A value is used as a position for the next lookup (a[a[i]], pointers). Nested expressions are evaluated inside-out.",
      observable_signs="Student evaluates the innermost lookup first and keeps track of which list each step uses.",
      tutor_moves=["Ask which part of the expression can be worked out right now.", "Ask: is this number a position or a value?"]),
    F(id="TOURNAMENT_MAX", name="Finding the best with comparisons", domain="ALG",
      prerequisites=p(("ELIMINATION", "firm", "Each comparison eliminates the losers.")),
      description="Every comparison of k items eliminates at most k-1 of them, and the best is the only item never beaten; so q comparisons of k find the best among at most 1 + q(k-1) items. Knockout tournaments achieve the bound.",
      observable_signs="Student counts eliminations rather than items looked at, and carries the winner forward.",
      tutor_moves=["Ask how many gems each question rules out.", "Ask whether the winner of the first group has to be asked about again."]),
    F(id="LOWER_BOUND", name="Bounds that prove an answer is best", domain="LOGIC",
      prerequisites=p(("IMPOSSIBILITY_PROOF", "tentative", "A bound shows nothing better can exist.")),
      description="Before searching, compute what no solution can beat (total area, eliminations per step, presses per move); a solution that meets the bound is optimal.",
      observable_signs="Student states the bound first and then shows a solution that reaches it.",
      tutor_moves=["Ask: what is the best you could possibly hope for, and why?", "Ask whether your answer reaches that limit."]),
    F(id="WORST_CASE", name="Worst-case thinking", domain="ALG",
      prerequisites=p(("SHORTEST_PATH", "tentative", "Worst case is the reverse question to cheapest route.")),
      description="Find the input or order that makes a process as slow as possible; often the greedy 'go to the farthest remaining' choice builds it.",
      observable_signs="Student asks which choice would hurt most at each step and checks that the first choice is not fixed.",
      tutor_moves=["Ask which plane would take the longest to bring to the gate first."]),
    F(id="NEAREST_NEIGHBOR", name="Nearest-neighbour regions", domain="DATA",
      prerequisites=p(("DIRECTION_COORDS", "tentative", "Distance on a grid builds on coordinates.")),
      description="Each cell takes the label of the closest (or farthest) marked point, which splits a grid into regions; ties are a separate case.",
      observable_signs="Student predicts region shapes around points without computing every cell.",
      tutor_moves=["Ask which dot a cell in the corner is closest to.", "Ask what the picture would look like if the rule were 'farthest'."]),
    F(id="DOMINANCE", name="Dominance and Pareto optimality", domain="LOGIC",
      prerequisites=p(("CONDITIONALS", "tentative", "'No one rates another higher' is a for-all condition.")),
      description="An option is a favorite only if, for every person, nothing is rated higher. Changing one person's top rating changes which options count.",
      observable_signs="Student checks the condition person by person and considers lowering ratings as well as raising them.",
      tutor_moves=["Ask what this friend's highest rating is.", "Ask whether you could make this friend happy with every movie at once."]),
    F(id="EDGE_MATCHING", name="Edge-matching and tiling", domain="LOGIC",
      prerequisites=p(("CONSTRAINT_SAT", "firm", "Each shared side is a constraint between two tiles.")),
      description="Tiles with a symbol on each side must touch only at equal symbols; rotation is allowed. Counting how often each symbol appears prunes the search.",
      observable_signs="Student uses rare symbols to fix tiles to the outside and tries rotations systematically.",
      tutor_moves=["Ask which symbols appear on only one tile.", "Ask which two sides of a corner tile touch other tiles."]),
]

concept_updates = [
    {"id": "PARALLEL_SPREAD", "add_note": "2022-23 Virus: two infections spread at once; a node reached by both on the same day is destroyed and blocks further spread (multi-source BFS with ties as walls). The two sources are neighbours, so they destroy each other on day 1."},
    {"id": "GAME_TREE", "add_note": "2022-23 Seashells and Pebbles: a misère placement game on a graph; the unique winning move is an isolated leaf that wastes a turn and passes the shortage of safe holes to the opponent."},
    {"id": "SHORTEST_PATH", "add_note": "2022-23 Maze: two maze floors with a costly switch between them; state is (floor, cell) and a route with two switches beats staying on one floor."},
    {"id": "CONSTRAINT_SAT", "add_note": "2022-23 adds forced propagation tasks (Colorful Tower, Beehive, Flower Garden/minesweeper, Treasure Box/mastermind)."},
    {"id": "INVARIANT", "add_note": "2022-23 Tic-Tac-Toe: a final board is valid only if counts differ by at most one, the game is over, and the winner moved last."},
    {"id": "ENCODING_CIPHER", "add_note": "2022-23 Cipher 8: rotation relative to the current pointer (delta encoding), so repeated letters cost 0."},
    {"id": "DIRECTION_COORDS", "add_note": "2022-23 Listen and Walk: left/front/right relative to the walker's own heading, which turns; position and heading are both state."},
    {"id": "BACKTRACKING", "add_note": "2022-23 Listen and Walk and Four Tiles need trying a branch and backing out when a later clue fails."},
]

T = []
def task(key, title, appearances, fmt, scenario, tests, concepts, solution, answer, errors, drivers, hints, gen):
    T.append({"key": key, "title": title, "appearances": appearances, "format": fmt, "scenario": scenario,
              "what_it_tests": tests, "concepts": concepts, "solution": solution, "answer": answer,
              "common_errors": errors, "difficulty_drivers": drivers, "hint_ladder": hints,
              "generator_template": gen})

task("lilas_guessing_game", "Lila's Guessing Game", ap(("Benjamin", "A", 24139)), "drag_place",
     "Three bags each hold one item; three swaps of two bags are made in order. Place each item where it ends up.",
     "Tracing state through a sequence of swaps.", ["STATE", "SEQ_EXEC", "SWAP_TEMP"],
     ["Write the contents of the three bags.", "Apply the first swap to that state, then the second to the new state, then the third."],
     "The item from the third bag ends in the first, the middle item stays, the first bag's item ends in the third.",
     ["Applying the swaps in the wrong order.", "Applying each swap to the starting positions."],
     ["Number of swaps", "Repeated positions in the swaps"],
     ["What is in each bag after the first swap?", "Use that new picture for the next swap."],
     {"params": {"containers": "3-5", "swaps": "2-6"}, "validity": "Distractors from wrong order and from swapping original positions."})

task("tortoise_and_hare", "Tortoise and Hare", ap(("Benjamin", "A", 24140)), "click_select",
     "A path of 4 cells leads into a loop of 6. Two runners start together, one moving 1 cell a minute, the other 2. Click the first cell where they meet again.",
     "Simulating two moving positions until they coincide; a loop after a lead-in.", ["SIMULATION", "MODULAR_ARITHMETIC", "CYCLE_DETECTION"],
     ["Move both runners minute by minute.", "Stop the first time they share a cell."],
     "They meet after 6 minutes on the loop, 6 steps from the start.",
     ["Assuming they meet at the loop entrance.", "Checking positions only every other minute."],
     ["Lead-in length", "Loop length", "Speed ratio"],
     ["Where is each runner after 1 minute? After 2?", "Once both are on the loop, how does the gap change?"],
     {"params": {"lead_in": "0-6", "loop": "4-10", "speeds": "1 and 2 (or 1 and 3)"}, "validity": "Answer by simulation; distractors at loop entry and at start."})

task("colorful_tower", "Colorful Tower", ap(("Benjamin", "A", 24141)), "toggle",
     "A triangle of three-colour tiles; the bottom row is given. A tile and the two below it are all the same or all different. Colour the rest.",
     "Applying a local rule repeatedly; forced propagation.", ["CONSTRAINT_SAT", "SEQ_EXEC"],
     ["For each tile, look at the two below: same colour gives that colour, different gives the third.", "Fill row by row upward."],
     "Every tile is forced by the rule (verified on the site).",
     ["Using side neighbours instead of the two below.", "Choosing the same colour when the two below differ."],
     ["Width of the bottom row", "Asking only for the top tile"],
     ["Which two tiles hold this one up?", "If those two differ, which colour is left?"],
     {"params": {"bottom_row": "4-7 tiles", "colours": "3"}, "validity": "The rule is addition mod 3; ask for top tile or full fill."})

task("most_popular_book", "Most Popular Book", ap(("Benjamin", "A", 24138)), "mc_image",
     "A log of who borrowed which book. Which book was borrowed most?",
     "Tallying and ignoring an irrelevant column.", ["ELIMINATION"],
     ["Count each book's entries; ignore who borrowed it."], "The cat book (3 of 7 entries).",
     ["Counting readers instead of books."], ["Number of entries", "Ties"],
     ["Make a tally for each book."], {"params": {"entries": "6-15"}, "validity": "Unique maximum."})

task("beehive", "Beehive", ap(("Benjamin", "A", 24142)), "drag_place",
     "Seven bees each have a pattern of cells that must fit inside a seven-cell hive around the bee's cell. Place all bees.",
     "Matching under constraints; most-constrained-first.", ["CONSTRAINT_SAT", "ELIMINATION"],
     ["List where each bee's pattern fits.", "Place the bees that fit in only one cell, remove those cells, repeat."],
     "A unique placement (verified).", ["Placing flexible bees first and running out of cells.", "Reading a pattern's direction wrongly."],
     ["Number of bees with one option at the start"], ["Which bee has only one place it can go?"],
     {"params": {"cells": "5-9"}, "validity": "Unique solution reachable by forced steps."})

task("pantry_map", "Pantry Map", ap(("Benjamin", "B", 24147), ("Cadet", "A", 24156)), "click_select",
     "A grid of marks kept so every row and column is even; two marks were erased. Find them.",
     "2D parity check: locating changes from odd rows and columns.", ["PARITY_CHECK", "ELIMINATION"],
     ["Find the odd rows and the odd columns (two of each).", "The erased marks sit at crossings, one per odd row and column; rule out the pair that uses an already-marked cell."],
     "The one consistent pair of crossings (verified).",
     ["Picking any cell in an odd row.", "Choosing a crossing that already holds a mark."],
     ["Number of erased marks", "Grid size", "Decoy marks at crossings"],
     ["Count the marks in each row. Which are odd?", "Where do an odd row and an odd column cross?"],
     {"params": {"grid": "5x5 to 8x8", "erased": "1-2"}, "validity": "Exactly one consistent answer; distractors at the other crossings."})

task("hamburger_recipe", "Hamburger Recipe", ap(("Benjamin", "B", 24145), ("Cadet", "A", 24154)), "mc_image",
     "Rules about layer order: one item directly above another, a group below a group, an item never next to the bun. Which stack follows every rule?",
     "Checking several constraints on an order.", ["BOOLEAN_AND", "ORDERING", "ELIMINATION"],
     ["Check every rule against every stack; drop a stack at its first broken rule."], "The fourth stack (verified).",
     ["Reading 'directly above' as 'somewhere above'.", "Checking only one rule."],
     ["Number of rules", "Distractors breaking exactly one rule"], ["Which rule does this stack break?"],
     {"params": {"layers": "5-8", "rules": "3-5"}, "validity": "Each distractor breaks exactly one rule."})

task("embroidery_machine", "Embroidery Machine", ap(("Benjamin", "B", 24143), ("Cadet", "A", 24153)), "mc_text",
     "A looping program of stitch and advance commands; two stitches in one space combine. Which program makes a given repeating pattern?",
     "Simulating a loop and matching its period.", ["LOOPS", "SEQ_EXEC", "PERIODIC"],
     ["Run each program for one or two loops.", "Compare with the start of the pattern; the period equals the number of advances."],
     "The third program (verified).", ["Forgetting the program repeats.", "Combining a stitch with the wrong space."],
     ["Program length", "Combined symbols"], ["What does the machine make in the first space?"],
     {"params": {"commands": "3-6"}, "validity": "Exactly one program matches."})

task("heart_graphics", "Heart Graphics", ap(("Benjamin", "B", 24144)), "mc_text",
     "A heart drawn from a rotated square and two circles. Which sequence of rotate, move, duplicate operations makes it?",
     "Decomposing a picture into shapes and transformations.", ["PROGRAM_WRITE", "SEQ_EXEC"],
     ["Identify the shapes and how each differs from the starting shapes."], "Duplicate the circle, rotate the square, move the circles.",
     ["Rotating or duplicating the wrong shape."], ["Number of operations"], ["Which shape appears twice?"],
     {"params": {"shapes": "2-3", "ops": "3-5"}, "validity": "Distractors swap the shape an operation acts on."})

task("sailor_necklace", "Sailor Necklace", ap(("Benjamin", "B", 24146), ("Cadet", "A", 24155)), "mc_image",
     "A necklace starts as two beads and grows by appending a pair on the right or wrapping both ends with another bead. Which necklace cannot be made?",
     "Membership in a grammar by working backward.", ["GRAMMAR", "RECURSION"],
     ["Undo a rule: remove an appended pair from the right, or the wrap beads from both ends.", "Repeat until reaching the start or getting stuck."],
     "The fourth necklace (verified).", ["Working only forward.", "Removing a pair from the wrong end."],
     ["Necklace length", "Two rules both applicable"], ["What could the last rule have been?"],
     {"params": {"rules": "2-3", "length": "6-10"}, "validity": "BFS over buildable strings; exactly one option missing."})

task("cipher_8", "Cipher 8", ap(("Benjamin", "C", 24151), ("Cadet", "B", 24161), ("Junior", "A", 24171)), "mc_text",
     "A pointer on an octagon of letter groups; each letter is coded as steps to rotate from the current position plus its place in the group. Encode a word.",
     "Relative (delta) encoding with modular rotation.", ["ENCODING_CIPHER", "MODULAR_ARITHMETIC", "STATE"],
     ["For each letter, count clockwise steps from where the pointer is now.", "Then its place within the group."],
     "The fourth code (verified).", ["Counting from the start every time.", "Wrong in-group position."],
     ["Repeated letters", "Wrap-around past the start"], ["Where is the pointer after the first letter?"],
     {"params": {"groups": "6-8", "word": "4-6 letters"}, "validity": "Distractors use absolute positions."})

task("marys_neighbors", "Mary's Neighbors", ap(("Benjamin", "C", 24148), ("Cadet", "B", 24158), ("Junior", "A", 24168)), "click_select",
     "Islands joined by walkways; clues give how many walkways each person's island has and who neighbours whom. Click Mary's house.",
     "Degree reasoning in a graph; start from the most specific clue.", ["GRAPH_MODEL", "CONSTRAINT_SAT"],
     ["Find the unique island with two walkways whose neighbours both have four.", "That fixes two people; the remaining four-walkway island is the answer."],
     "The house on the middle island (verified).", ["Counting walkways that only pass by.", "Starting from a vague clue."],
     ["Islands", "Number of islands with equal degree"], ["Which clue fits only one island?"],
     {"params": {"nodes": "6-10"}, "validity": "Unique consistent assignment."})

task("rug_weaving", "Rug Weaving", ap(("Benjamin", "C", 24152), ("Cadet", "B", 24162)), "mc_image",
     "A 6x6 rug; each cell's symbol comes from a decision chart on its row and column (border, diagonal, below or above the diagonal). Which rug is right?",
     "Evaluating a decision tree per cell; test order matters.", ["NESTED_CONDITIONALS", "DIRECTION_COORDS"],
     ["Apply the tests in the chart's order for a few telling cells (corners, diagonal, one above and one below)."],
     "The second rug (verified).", ["Swapping 'row > column' and 'column > row'.", "Testing the diagonal before the border."],
     ["Number of tests", "Tests like row + column even"], ["What does the chart say for row 1, column 1?"],
     {"params": {"grid": "5x5 to 8x8", "tests": "2-4"}, "validity": "Each distractor results from one misordered or reversed test."})

task("lights_on", "Lights On", ap(("Benjamin", "C", 24149), ("Cadet", "B", 24159), ("Junior", "A", 24169)), "toggle",
     "Eight buttons feed a tree of 'both' and 'only one' gates into a bulb. Choose buttons to light it.",
     "AND/XOR circuits; backward reasoning from the output; many valid answers.", ["LOGIC_GATES", "BOOLEAN_AND"],
     ["The bulb's gate needs both inputs: so both halves must be on.", "For each 'only one' gate pick one side; for each 'both' gate turn on both sides."],
     "E.g. buttons 1, 2, 3, 5, 6 (any satisfying input is accepted).",
     ["Reading 'only one' as 'at least one'.", "Turning on every button."],
     ["Tree depth", "Mix of gate types", "Asking for the fewest buttons"], ["What does the last gate need?"],
     {"params": {"inputs": "4-16", "gates": "AND, XOR, OR"}, "validity": "Grade by evaluating the circuit; variants ask for a count of solutions."})

task("nuts_and_bolts", "Nuts and Bolts", ap(("Benjamin", "C", 24150), ("Cadet", "B", 24160), ("Junior", "A", 24170)), "mc_image",
     "Nuts go into a bucket; each bolt takes one out. Fail if a bolt finds the bucket empty or nuts are left at the end. Which sequence works?",
     "Balanced matching with a running counter.", ["STACK_MATCHING", "STATE"],
     ["Keep a running count: +1 nut, -1 bolt.", "Reject a sequence the moment the count goes below zero, and any that ends above zero."],
     "The third sequence: N N N B N N B B B B (verified).",
     ["Checking only that the totals are equal.", "Checking only the start."],
     ["Sequence length", "Late failures"], ["How many nuts are in the bucket after each item?"],
     {"params": {"length": "8-14"}, "validity": "Distractors fail early, fail late, or end with leftovers."})

task("flower_garden", "Flower Garden", ap(("Cadet", "A", 24157), ("Junior", "A", 24172)), "click_select",
     "Minesweeper: numbers count hidden flowers among the 8 neighbours. One flower is known; which of four squares holds another?",
     "Local constraint propagation.", ["CONSTRAINT_SAT", "ELIMINATION"],
     ["A 1 already touching the known flower clears its other neighbours.", "A 2 with only one uncleared neighbour besides the known flower forces it."],
     "B (verified).", ["Counting only 4 neighbours.", "Forgetting the known flower already satisfies a 1."],
     ["Number of deduction steps"], ["Which numbers already touch the known flower?"],
     {"params": {"board": "4x6 to 6x8"}, "validity": "Brute-force all placements consistent with the numbers; unique answer among options."})

task("hangar_carousel", "Hangar Carousel", ap(("Cadet", "C", 24164), ("Junior", "B", 24175), ("Senior", "A", 24185)), "drag_place",
     "Six planes on a turntable; position 1 starts at the gate; each press turns one position either way. Give an order of taking all planes out that needs the most presses.",
     "Worst-case ordering with circular distance.", ["WORST_CASE", "MODULAR_ARITHMETIC"],
     ["The first plane need not be the one at the gate.", "Always go to the farthest remaining position (3 presses where possible)."],
     "4 1 3 6 2 5 or 4 1 5 2 6 3 (16 presses).",
     ["Taking plane 1 first (gives at most 13).", "Counting one-way distance instead of the shorter way round."],
     ["Number of positions", "Best case vs worst case"], ["Which plane is farthest from the gate right now?"],
     {"params": {"positions": "5-8"}, "validity": "Brute force over all orders; accept any optimal order."})

task("listen_and_walk", "Listen and Walk", ap(("Cadet", "C", 24165), ("Junior", "B", 24174), ("Senior", "A", 24184)), "click_select",
     "A walker hears what is on her left, ahead and right at each new road square. From eight readings, find where she ends.",
     "Tracking position and heading; matching relative observations; backtracking.", ["STATE", "DIRECTION_COORDS", "BACKTRACKING"],
     ["Track position and facing.", "At junctions try each turn and keep the one whose next reading matches.", "Look one reading ahead when two branches fit."],
     "B (verified).", ["Using compass directions instead of her left/right after turning.", "Assuming she goes straight."],
     ["Number of junctions", "Readings that fit two branches"], ["After she turns, which way is her left?"],
     {"params": {"map": "8x8 to 10x10", "readings": "6-10"}, "validity": "Search all walks; exactly one end square fits."})

task("tic_tac_toe", "Tic-Tac-Toe", ap(("Cadet", "C", 24167), ("Junior", "B", 24177), ("Senior", "A", 24187)), "mc_image",
     "Which of four finished boards could come from a real game?",
     "Validity of a final state by invariants.", ["INVARIANT", "BOOLEAN_AND", "ELIMINATION"],
     ["Counts must differ by at most one.", "The game must be over (a line or a full board).", "The winner moved last; nobody moved after a win."],
     "The third board (verified).", ["Checking only for a line.", "Assuming X always starts."],
     ["Boards that pass some checks"], ["How many X and how many O?"],
     {"params": {}, "validity": "Each distractor breaks one invariant; checker enumerates reachable states."})

task("lists", "Lists", ap(("Cadet", "C", 24163), ("Junior", "B", 24173), ("Senior", "A", 24183)), "mc_text",
     "Three lists of five numbers; (X i) means the number at position i. Evaluate a nested lookup like (A (B (C 3))).",
     "Indirection and inside-out evaluation.", ["INDIRECTION", "FUNC_COMPOSITION"],
     ["Evaluate the innermost lookup first.", "Use each result as the position in the next list out."],
     "4 (verified).", ["Evaluating left to right.", "Counting positions from 0."],
     ["Nesting depth", "Distractor values from wrong orders"], ["Which part can you work out first?"],
     {"params": {"lists": "2-4", "depth": "2-4"}, "validity": "Reject instances where a wrong order gives the right answer (this instance has that flaw)."})

task("favorite_movie", "Favorite Movie", ap(("Cadet", "C", 24166), ("Junior", "B", 24176), ("Senior", "A", 24186)), "toggle",
     "Friends rate seven movies high, medium or low; a favorite is a movie no friend rates anything above. Make the fewest changes so a favorite exists.",
     "Dominance; minimum edits; lowering a maximum.", ["DOMINANCE", "LOWER_BOUND"],
     ["For each movie, count friends who rate it below their own top.", "Also consider lowering a friend's single top rating.", "Two changes suffice: lower Niklaus's only medium, raise Rozsa on movie 6."],
     "2 changes (verified).", ["Only raising ratings (gives 3).", "Treating 'favorite' as most top ratings."],
     ["Friends with a single top rating"], ["What is this friend's highest rating?"],
     {"params": {"friends": "4-7", "movies": "5-8"}, "validity": "Search all edit sets up to size 3."})

task("packing", "Packing", ap(("Junior", "C", 24400), ("Senior", "B", 24401)), "drag_place",
     "Four chocolate bars (15, 12, 6 and 5 pieces) go flat into a rectangular box; make as few empty cells as possible.",
     "Area lower bound plus 2D packing.", ["LOWER_BOUND", "CONSTRAINT_SAT"],
     ["Total area 38; 38 only factors as 1x38 or 2x19, too thin for the 3-wide bars, so at least 2 gaps.", "A 5x8 box reaches 2 gaps."],
     "2 gaps, e.g. a 5x8 box (verified).", ["Packing without computing the bound.", "Forgetting rotations."],
     ["Total area prime or near-prime", "Bar widths"], ["What is the total number of pieces?"],
     {"params": {"bars": "3-5"}, "validity": "Exhaustive tiling search for the minimum."})

task("favorite_gem", "Favorite Gem", ap(("Junior", "C", 24179), ("Senior", "B", 24189)), "mc_text",
     "Three questions of the form 'which of these four is your favorite?'. What is the largest collection in which the overall favorite can always be found?",
     "Counting eliminations per comparison.", ["TOURNAMENT_MAX", "LOWER_BOUND"],
     ["Each question rules out at most 3 gems.", "n - 1 <= 9, so n <= 10; a knockout reaches 10."],
     "10 (verified).", ["3 x 4 = 12, forgetting the carried-forward winner.", "Requiring disjoint groups."],
     ["Group size", "Number of questions"], ["How many gems does one answer rule out?"],
     {"params": {"k": "2-5", "q": "2-5"}, "validity": "Answer 1 + q(k-1)."})

task("mysteria", "Mysteria", ap(("Junior", "C", 24178), ("Senior", "B", 24188)), "mc_image",
     "A wizard rewrites a diamond into a coin or a diamond and coin, and a coin into potion-dragon or potion-diamond-dragon. Which line cannot come from one diamond?",
     "A two-symbol grammar; backward reduction.", ["GRAMMAR", "RECURSION"],
     ["Fold potion...dragon pairs (with nothing or a diamond inside) into coins; fold diamond+coin and lone coins into diamonds.", "The line with a coin between a potion and dragon never folds."],
     "The second line (verified).", ["Allowing any symbol between potion and dragon."],
     ["Nesting depth", "Unexpanded symbols left in lines"], ["What could this potion and dragon have come from?"],
     {"params": {"nonterminals": "2", "length": "5-9"}, "validity": "BFS over sentential forms."})

task("maze", "Maze", ap(("Junior", "C", 24181), ("Senior", "C", 24193)), "mc_text",
     "Two 6x6 maze floors; a step costs 1, switching floors at the same cell costs 5. Shortest time from A to B.",
     "Shortest path in a layered graph.", ["SHORTEST_PATH", "STATE"],
     ["State is floor plus cell.", "Compare staying on floor 1 (20) with routes that switch twice: 6 + 5 + 2 + 5 = 18."],
     "18 (verified).", ["Counting only one switch.", "Staying on one floor."],
     ["Switch cost", "Wall density"], ["Is there a shortcut on the other floor worth 10 seconds?"],
     {"params": {"floors": "2", "switch_cost": "3-6"}, "validity": "Dijkstra; distractors from one switch counted and from one floor."})

task("treasure_box", "Treasure Box", ap(("Junior", "C", 24180), ("Senior", "B", 24190)), "mc_image",
     "Crack a 3-shape code from five guesses with right-place / wrong-place feedback.",
     "Consistency with feedback (Mastermind).", ["CONSTRAINT_SAT", "ELIMINATION"],
     ["Use the 'nothing is correct' guess first to remove three shapes.", "Test each option against every clue."],
     "Star, circle, moon (verified).", ["Ignoring position feedback."], ["Clues needed together"],
     ["Which shapes can you cross out completely?"],
     {"params": {"slots": "3-4", "guesses": "4-6"}, "validity": "Exactly one option consistent."})

task("floor_pattern", "Floor Pattern", ap(("Senior", "B", 24191)), "drag_place",
     "A robot snakes through a 10x10 grid with a few black and white dots and paints by one of four rules (nearest dot, farthest dot, last dot passed, local majority). Match each rule to its picture.",
     "Recognising a program by its output.", ["NEAREST_NEIGHBOR", "STATE", "SIMULATION"],
     ["'Last dot passed' gives long runs along the snake path.", "'Local majority' leaves most cells blank.", "'Nearest' puts colours around their own dots; 'farthest' does the opposite."],
     "Nearest-1, farthest-3, last-passed-4, majority-2 (verified).", ["Confusing nearest and farthest.", "Ignoring the snake order."],
     ["Number of dots", "Rules with similar outputs"], ["Which picture has long straight runs?"],
     {"params": {"grid": "8x8 to 10x10", "dots": "3-6"}, "validity": "Render each rule; all four pictures distinct."})

task("four_tiles", "Four Tiles", ap(("Senior", "C", 24194)), "mc_image",
     "Five square tiles with symbols on their sides; four must form a 2x2 square where touching sides match. Which tile is left out?",
     "Edge matching with rotation.", ["EDGE_MATCHING", "BACKTRACKING"],
     ["Each tile in a 2x2 uses two adjacent sides inside.", "Symbols that appear on only one tile must face out; that rules out the third tile."],
     "The third tile (verified).", ["Forgetting rotation.", "Matching opposite sides."],
     ["Rare symbols", "Decoy tiles that almost fit"], ["Which symbols appear on only one tile?"],
     {"params": {"tiles": "5", "symbols": "6-9"}, "validity": "Exactly one 4-subset tiles."})

task("seashells_and_pebbles", "Seashells and Pebbles", ap(("Senior", "C", 24195)), "click_select",
     "Players place their own pieces on a graph of holes; whoever first puts two of their own pieces on neighbouring holes loses. Find the move that forces a win.",
     "Minimax in a misère placement game.", ["GAME_TREE", "GRAPH_MODEL"],
     ["Rule out holes next to your own pieces.", "Of the rest, look ahead: the isolated leaf hole 7 is the only winning move."],
     "Hole 7 (verified by full minimax).", ["Choosing the hole with most safe neighbours.", "Not considering the reply."],
     ["Empty holes", "Leaves and isolated holes"], ["After your move, how many safe holes does the opponent have?"],
     {"params": {"holes": "8-12", "empty": "5-8"}, "validity": "Unique winning move by minimax."})

task("beaver_games", "Beaver Games", ap(("Senior", "C", 24196)), "drag_place",
     "Eight players' scores in three rounds (teams of four, then pairs, then head-to-head). Ada won everything; find her round-1 teammates.",
     "Backward reasoning through an elimination tournament.", ["ELIMINATION", "CONSTRAINT_SAT"],
     ["Round 3: only G scored below Ada, so G was her partner.", "Round 2: only D and F together are below Ada + G, so they were the other pair.", "Check round 1: 72 beats 71."],
     "D, F and G (site explanation; brute force agrees).", ["Working forward from round 1.", "Assuming teammates are high scorers."],
     ["Number of stages", "Near-ties"], ["Start at the last round: who could Ada have beaten?"],
     {"params": {"players": "8", "rounds": "3"}, "validity": "Enumerate all splits; unique teammates."})

task("virus", "Virus", ap(("Senior", "C", 24197)), "mc_text",
     "Two viruses spread daily through a network; a computer reached by both is destroyed and stops spreading. How many computers end with only the second virus?",
     "Simultaneous multi-source BFS with ties destroyed.", ["PARALLEL_SPREAD", "SIMULATION"],
     ["The two start computers are neighbours, so both are destroyed on day 1.", "Spread both fronts one day at a time; equal-day arrivals are destroyed."],
     "6 (verified).", ["Keeping the start computers alive (gives 7).", "Spreading one virus fully first."],
     ["Adjacent sources", "Number of tie points"], ["What happens to the two starting computers on day 1?"],
     {"params": {"nodes": "12-20", "sources": "2-3"}, "validity": "Simulate; distractors from protected sources and sequential spread."})

misconceptions = [
    {"id": "SWAPS_ON_ORIGINAL", "concept": "STATE", "description": "Applies each swap or step to the starting picture instead of the current one.", "remediation": "Have the student redraw the state after every step.", "families": []},
    {"id": "PARITY_ANY_ODD_CELL", "concept": "PARITY_CHECK", "description": "Picks a cell in an odd row without checking that its column is odd too.", "remediation": "Ask which rows AND which columns are odd, and look only where they cross.", "families": []},
    {"id": "GRAMMAR_FORWARD_GUESS", "concept": "GRAMMAR", "description": "Tries random forward derivations instead of undoing rules from the string.", "remediation": "Ask which rule could have produced the right-hand end, and undo it.", "families": []},
    {"id": "XOR_AS_OR", "concept": "LOGIC_GATES", "description": "Reads an 'only one' gate as 'at least one' and turns on both inputs.", "remediation": "Ask what the gate does when both inputs are on.", "families": []},
    {"id": "TOTALS_ONLY_MATCHING", "concept": "STACK_MATCHING", "description": "Accepts a sequence because the numbers of openers and closers are equal, missing a point where the count goes negative.", "remediation": "Have the student write the running count under each item.", "families": []},
    {"id": "INDIRECTION_OUTSIDE_IN", "concept": "INDIRECTION", "description": "Evaluates a nested lookup from the outside in (left to right).", "remediation": "Ask which part of the expression can be worked out with what you already know.", "families": []},
    {"id": "FIXED_FIRST_ITEM", "concept": "WORST_CASE", "description": "Assumes the first item in an order must be the one at the start position.", "remediation": "Ask whether the rules say which plane has to leave first.", "families": []},
    {"id": "WINNER_NOT_CARRIED", "concept": "TOURNAMENT_MAX", "description": "Multiplies questions by group size, not seeing that the winner must be carried into the next comparison.", "remediation": "Ask how many items one question rules out.", "families": []},
    {"id": "NO_AREA_BOUND", "concept": "LOWER_BOUND", "description": "Searches for a packing without first computing what the best could be, so cannot tell when to stop.", "remediation": "Ask for the total area and which box sizes it allows.", "families": []},
    {"id": "RAISE_ONLY", "concept": "DOMINANCE", "description": "Only considers raising ratings, missing that lowering a single top rating satisfies a person for every option.", "remediation": "Ask whether there is a way to make this friend content with any movie.", "families": []},
    {"id": "ABSOLUTE_FOR_RELATIVE", "concept": "DIRECTION_COORDS", "description": "Uses map directions after the walker has turned, or absolute positions in a relative code.", "remediation": "Ask the student to turn the map so the walker faces up.", "families": []},
    {"id": "PROTECTED_SOURCES", "concept": "PARALLEL_SPREAD", "description": "Treats the starting computers as safe even when both viruses reach them.", "remediation": "Ask what spreads into each starting computer on day 1.", "families": []},
    {"id": "SEQUENTIAL_SPREAD", "concept": "PARALLEL_SPREAD", "description": "Spreads one virus completely before the other instead of day by day together.", "remediation": "Have the student colour both fronts for day 1, then day 2.", "families": []},
    {"id": "ONE_SWITCH_COST", "concept": "SHORTEST_PATH", "description": "Counts the cost of switching floors once for a route that switches there and back.", "remediation": "Ask which floor B is on and how the route gets back there.", "families": []},
    {"id": "FORWARD_TOURNAMENT", "concept": "CONSTRAINT_SAT", "description": "Works forward from the first round, where many outcomes are possible, instead of backward from the final.", "remediation": "Ask who Ada could have beaten in the last round.", "families": []},
]

progression = {
    "mode": "append",
    "set": "2022-23 practice challenge",
    "reuse": "The 2022-23 practice sets reuse heavily and in the same pattern as 2015: each group's tier C becomes the next group's tier B, and its tier B becomes the next group's tier A. Cadet tier B is exactly Benjamin tier C; Senior tier A is exactly Cadet tier C. Seven tasks appear in three groups. Of 60 slots across the four groups, 31 tasks are distinct.",
    "what_changes_with_age": [
        "Benjamin: tracing state (swaps, runners), applying a local rule everywhere (tower, rug), checking constraints, and the first error-detection idea (parity map).",
        "Cadet adds relative reasoning (walker's left/right, pointer rotation), indirection (nested list lookups), worst-case ordering, validity by invariants, and minimum-edit questions.",
        "Junior hard tier needs a bound or a count before searching: area bound for packing, eliminations per question, a two-floor shortest path, a two-symbol grammar.",
        "Senior hard tier: game minimax with a unique winning move, simultaneous two-source spread, edge-matching with rotation, backward reasoning through a tournament, recognising programs by output.",
        "Compared with 2015: more grammar and parsing (Sailor Necklace, Mysteria), the first error-detection task (Pantry Map), logic gates (Lights On), bracket matching (Nuts and Bolts), and pointer/indexing (Lists). No 'computers and society' tasks in 2022-23.",
    ],
    "implications_for_the_tutor": [
        "New gaps now covered: parity/error detection, grammars, logic gates, stack matching, indirection; add them to the concept graph before building families.",
        "Several Benjamin and Cadet items have many valid answers (Lights On, Hangar Carousel, Favorite Movie). A generator must grade by evaluating the rule, not by comparing with one key.",
        "Lists shows why distractors must be audited: there the left-to-right misreading lands on the right answer, so the item cannot detect that misconception.",
        "Backward reasoning recurs at every level (Sailor Necklace, Lights On, Mysteria, Beaver Games); a tutor move 'start from the end' is worth a dedicated hint step.",
    ],
}

generator_candidates = [
    {"source_task": "nuts_and_bolts", "why": "Bracket strings with a running counter; trivially checkable; distractors fail early, fail late, or leave items over. Easy at Benjamin, extend with two bracket types at Cadet."},
    {"source_task": "lists", "why": "Random permutations and nesting depth; answer by direct evaluation; distractors from outside-in order, 0-based indexing and stopping a level early (reject coincidences)."},
    {"source_task": "lights_on", "why": "Random gate trees; grade by evaluating; variants ask for any solution, the fewest buttons, or the number of solutions (a counting task for Junior)."},
    {"source_task": "sailor_necklace", "why": "Pairs with mysteria as one 'grammar' family: random small rule sets, BFS membership checker, one unreachable option."},
    {"source_task": "pantry_map", "why": "Random grids with parity marks and 1-2 erasures; unique answer by crossing odd rows and columns; fills the error-detection gap."},
    {"source_task": "favorite_gem", "why": "Closed form 1 + q(k-1) with natural distractors qk, qk+1; a quick bound-reasoning item for all levels."},
    {"source_task": "virus", "why": "Random graphs with two sources; synchronous simulation checker; distractors from protected sources and sequential spread."},
    {"source_task": "maze", "why": "Extends lake-crossing / robot-routes to a layered graph; Dijkstra checker; switch cost tunes difficulty."},
    {"source_task": "colorful_tower", "why": "Rule is addition mod 3; random bottom rows; ask for the top tile or a missing tile in the middle (inverse)."},
    {"source_task": "treasure_box", "why": "Mastermind clues generated from a hidden code; checker enumerates all codes for uniqueness."},
]

patch = {
    "patch_id": "practice-2022-23",
    "built": "2026-11-10",
    "analyst": "Claude",
    "map_title": "Bebras knowledge map: 2015 example sets and 2022-23 practice challenge (Benjamin, Cadet, Junior, Senior)",
    "method": ("Every task in the 2022-23 USA Bebras practice challenge for Benjamin, Cadet, Junior and Senior (31 distinct tasks, 60 slots) "
               "was opened, solved and submitted to the site's checker. 29 were marked correct on submission. Two (Hangar Carousel, Beaver Games) "
               "were confirmed against the site's published explanation after a first submission was not registered or was wrong; both answers are "
               "also re-derived by exhaustive search. Search-based answers (Hangar Carousel, Mysteria, Maze, Four Tiles, Seashells and Pebbles, "
               "Beaver Games, Virus, Treasure Box) were computed by brute force. Descriptions are my own; no task wording or artwork is reproduced. "
               "Kits and Castors were not analyzed."),
    "source_sets": [
        {"age_group": g, "ages": a, "url": URL + str(n), "set": "2022-23 practice"}
        for g, a, n in [("Benjamin", "10-12", 1851), ("Cadet", "12-14", 1852), ("Junior", "14-16", 1853), ("Senior", "16-18", 1854)]
    ],
    "formats": {"click_select": "Click one element of a picture (a cell, a house, a hole) and save."},
    "domains": [],
    "concepts": concepts,
    "concept_updates": concept_updates,
    "tasks": T,
    "appearances_for_existing_tasks": [],
    "misconceptions": misconceptions,
    "progression": progression,
    "generator_candidates_mode": "append",
    "generator_candidates": generator_candidates,
}

if __name__ == "__main__":
    out = os.path.join(HERE, "practice_2022_patch.json")
    with open(out, "w") as fh:
        json.dump(patch, fh, indent=1, ensure_ascii=False)
    slots = sum(len(t["appearances"]) for t in T)
    print(f"{len(T)} tasks, {slots} appearances, {len(concepts)} concepts, {len(misconceptions)} misconceptions -> {out}")

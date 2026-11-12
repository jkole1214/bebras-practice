"""
Write look_again_patch.json: a short question for the student, one per misconception tag.

After a wrong try that carries a tag, the practice page shows that tag's question under
"Not quite." It points at the likely mistake without giving the answer away. The
remediation text in the map is for parents; these are for the student (ages 10-14).

    python3 tools/make_look_again_patch.py
    python3 tools/merge_patch.py tools/bebras_knowledge_map.json tools/look_again_patch.json
    python3 tools/build_problems.py --coach-only
"""

import json
import os

LOOK_AGAIN = {
    # Rule Tracer (dice rules)
    "REVERSED_COMPARISON": "Read each test out loud with the real numbers in it. Which die has to be bigger?",
    "INDEX_CONFUSION": "Number the dice 1, 2, 3 from the left before you check any test. Did you use the right die each time?",
    "TIES_FLIPPED": "Two of the dice are equal. Is 'greater than' true when the numbers are the same?",
    "SKIPS_OUTER_TEST": "To reach that line, an earlier test had to be false. Did you check it?",
    "FORGETS_FREE_DIE": "Is there a die the rules never look at? How many faces could it show?",

    # Lake Crossing (walkways and planks)
    "GREEDY_FROM_START": "The cheapest first walkway is not always part of the cheapest crossing. Where did it lead you?",
    "GREEDY_FROM_END": "Picking the cheapest walkway each time doesn't work from the south shore either. Add up the whole route.",
    "FEWEST_WALKWAYS": "A route with fewer walkways can still need more planks. Did you add up the numbers?",
    "NO_BACKTRACKING": "Does any rule say you must always head south? Try a route that steps back north.",
    "DROPS_SHORE_WALKWAY": "Point to every walkway on your route as you add. Did you count the ones touching the shores?",
    "SHORES_ONLY": "Trace your route with a finger from shore to shore. Does it really connect?",
    "ONE_CHEAPEST_ONLY": "Is there a different route with exactly the same total?",
    "COUNTS_ALL_CROSSINGS": "The question counts only crossings with the fewest planks. Did some of yours cost more?",
    "COUNTS_NEAR_CHEAPEST": "Add each route up exactly. Does every one you counted match the cheapest total?",
    "LENGTH_FOR_COUNT": "Read the question again. Does it ask how long the best route is, or how many best routes there are?",

    # Signal Lamp (flashes and code words)
    "MISREAD_SYMBOL": "Write the signal as S and L letters first. Did you read every flash right?",
    "MISSES_SHORT_WORD": "At each spot in the signal, did you try every code word, even the shortest one?",
    "FIRST_PARSE_ONLY": "Could the signal start with a different first word?",
    "COUNTS_DEAD_ENDS": "Does each reading you counted use up the whole signal, right to the last flash?",
    "COUNTS_WORD_SETS": "Are 'east, fog' and 'fog, east' the same message? Count each order on its own.",
    "DROPS_WORD": "Turn your answer back into flashes. Is it as long as the signal?",
    "ORDER_SWAP": "Mark where each word starts in the signal, left to right. Are your words in that order?",

    # Robot Routes (city grid)
    "COUNTS_INTERSECTIONS": "Count the blocks the robot drives along, not the corners it passes.",
    "COUNTS_BOX_INTERSECTIONS": "Two routes can pass the same corners in a different order. Are you counting routes or corners?",
    "FEW_TURNS_ONLY": "Could a zigzag route be just as short?",
    "GREEDY_ROUTE": "Write how far each corner is from the start, nearest first. Is heading straight for the goal really shortest?",
    "IGNORES_CLOSED": "Cross out every closed corner first. Can a route go through one?",
    "IGNORES_CLOSED_LENGTH": "Trace your route with a finger. Does it go through a closed corner?",

    # Nuts and Bolts (belt and bucket)
    "CHECKS_START_ONLY": "Did you keep your count going all the way to the end of the belt?",
    "TOTALS_ONLY_MATCHING": "Write the number of nuts in the bucket under each part. Does a bolt ever find it empty?",
    "IGNORES_LEFTOVERS": "When the belt is empty, how many nuts are still in the bucket?",
    "LEFTOVER_ONLY": "Run the count from the start. Does a bolt ever arrive with no nut waiting?",
    "SHORTFALL_ONLY": "After fixing the early bolts, are any nuts still left in the bucket at the end?",
    "DIFFERENCE_FOR_REPAIR": "Equal totals are not enough. Do any bolts arrive before there is a nut for them?",
    "TOTAL_NUTS_FOR_DEPTH": "Bolts take nuts out as the belt moves. Follow the bucket after each part.",
    "LONGEST_RUN_FOR_DEPTH": "When a run of nuts starts, are some nuts already in the bucket?",
    "SIZES_SEPARATELY": "Only the nut on top of the pile can be taken. Does each bolt fit the nut on top?",

    # Box Rows (lookups)
    "INDIRECTION_OUTSIDE_IN": "Which part can you work out right now? Start with the innermost brackets.",
    "ZERO_BASED_INDEX": "Read the small number above each box. Which box is box 1?",
    "COUNTS_FROM_RIGHT": "The box numbers are printed above the row. Which end does box 1 sit at?",
    "STOPS_ONE_EARLY": "Count the pairs of brackets. Each pair is one lookup. Did you do them all?",
    "SAME_ROW_EVERY_STEP": "Before each step, which row's name is in front of the bracket?",
    "POSITION_AS_ANSWER": "Is your answer the box's number, or what is written inside the box?",
    "FORWARD_NOT_INVERSE": "Work backward: which box in the outer row holds the target?",
    "INVERSE_ONE_STEP": "You found a box in the outer row. Where does that box number come from in the inner row?",

    # Lights On (buttons, boxes and the bulb)
    "XOR_AS_OR": "What does an 'only one' box do when both of its wires are on?",
    "BOTH_AS_EITHER": "Does that box need one wire on, or both wires on?",
    "EXTRA_BUTTONS": "The bulb lights. Could it light with fewer buttons pressed?",
    "ONE_ANSWER_ONLY": "Is there another set of buttons that also works? Try listing them in order.",

    # Bead Rules (necklaces and wizard lines)
    "GRAMMAR_WRONG_END": "Read the rule again. Which end do the new beads go on?",
    "WRAP_ONE_END": "Does the rule add both beads to one end, or one bead at each end?",
    "GRAMMAR_FORWARD_GUESS": "Work backward: which rule could have made the end of this necklace? Undo it and keep going.",
    "COUNTS_SHORTER_TOO": "Does every necklace you counted have exactly the number of beads asked for?",
    "GRAMMAR_ORDER_IGNORED": "A rule's new objects always come out in the order shown. Did you keep that order?",
    "GRAMMAR_ANY_OBJECT": "Each rule changes only the kind of object on its left side. Was it that kind?",

    # Pantry Map (every row and column even)
    "PARITY_ANY_ODD_CELL": "Which rows are odd, and which columns are odd? Look where they cross.",
    "PARITY_MARKED_CROSSING": "A rubbed-out dot leaves an empty shelf. Can it be a shelf that still shows a dot?",
    "PARITY_ROWS_ONLY": "Every row is even now. Count each column too, including the check row at the bottom.",
    "PARITY_COLS_ONLY": "Every column is even now. Count each row too, including the check column on the right.",
    "PARITY_CORNER": "The corner shelf belongs to both the last row and the last column. Does it work for both?",

    # Paint Pipes (two colours spreading)
    "MINUTE_OFF_BY_ONE": "Write 'minute 1', 'minute 2' and so on, with what changes under each. How many minutes does the question ask about?",
    "FLOWS_ALL_THE_WAY": "Paint moves through one pipe each minute. How far can it get in the first minute?",
    "FORGETS_START": "What colour is the tank the paint was poured into?",
    "SEQUENTIAL_SPREAD": "Both colours move in the same minute. Colour both of them for minute 1, then minute 2.",
    "FIRST_COLOR_STAYS": "Find an orange tank and a blue tank joined by a pipe. What does each push into the other next minute?",
    "PROTECTED_SOURCES": "The starting tanks follow the same rules as every other tank. What flows into each of them, and when?",
    "MUD_STILL_FLOWS": "Read the rule about mud again. Can a mud tank push paint anywhere?",
    "COUNTS_MUD": "Name each tank you counted and say its colour at the end. Is any of them mud?",

    # Code Lock (symbol wheels and clues)
    "SKIPS_EMPTY_CLUE": "One guess has nothing right. Did you cross out every symbol in it?",
    "CLUE_POSITION_IGNORED": "Pick a symbol your code shares with a guess. Is it on the same wheel in both, or a different one?",
    "CLUE_FEEDBACK_SWAPPED": "Say one clue in full words: how many symbols are in exactly the right spot, and how many are in a wrong spot?",
    "SKIPS_A_CLUE": "Test your code against every clue, ticking each one off. Does it really agree with all of them?",
}

HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    patch = {
        "patch_id": "look-again",
        "built": "2026-11-12",
        "analyst": "Claude",
        "method": ("Claude wrote one short question for the student per misconception tag that the generators or the "
                   "answer checker can produce (72 tags). The practice page shows it after a wrong try with that tag. "
                   "Each question points at the likely mistake without giving the answer away."),
        "misconception_updates": [{"id": k, "look_again": v} for k, v in sorted(LOOK_AGAIN.items())],
    }
    with open(os.path.join(HERE, "look_again_patch.json"), "w") as fh:
        json.dump(patch, fh, indent=2, ensure_ascii=False)
    print(f"{len(LOOK_AGAIN)} questions written")

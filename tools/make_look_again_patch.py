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

    # Brick Pyramid (three colours, all the same or all different)
    "COPIES_A_SUPPORT": "Find a brick that rests on two different colours. Can it match either of them, or must it be the third colour?",
    "MATCH_MEANS_CHANGE": "Find a brick that rests on two bricks of the same colour. Does the rule let all three be the same?",
    "FORGETS_BOTTOM_ROW": "Point to every brick of that colour, starting with the bottom row. Did you count them all?",

    # Pass It On (news travels two steps through friends)
    "ONE_STEP_ONLY": "The friends hear it first. What does each of them do with the news next?",
    "ONLY_SECOND_STEP": "Did you count the friends who heard it first, as well as the people they told?",
    "COUNTS_SENDER": "Read the question again. Does the person with the news count as hearing it?",
    "PASSES_IT_ON_TOO_FAR": "Mark the friends, then their friends. Does anyone tell the news a third time?",
    "COUNTS_REPEATS": "Some people hear the news from two friends. Did you tick each person only once?",
    "MOST_FRIENDS_WINS": "Count two steps out from the person with the most friends. Does that really reach the most people?",
    "JOINS_A_MISSED_PERSON": "A new friend also tells all of their own friends. Whose friends cover everyone who is missed?",

    # Frog Hops (a fixed hop forward or back, every stone once)
    "STOPS_AT_DEAD_END": "The frog got stuck with stones left. Where was the last stone it had two hops to choose from? Try the other one.",
    "FAR_END_IS_LAST": "Does the frog have to finish at the far end? Follow its hops one at a time and see where it really stops.",
    "HOPS_WRONG_SIZE": "Count the spots on each hop, water spots too. Is every hop exactly the right size?",
    "SWAPS_HOP_DIRECTIONS": "Which hop goes forward, and which goes back? Check each hop against the rule again.",
    "LANDS_TWICE": "Does the frog land on any stone more than once?",

    # Map Pieces (friends meet in pairs each round and copy each other's pieces)
    "PARTNERS_OWN_PIECE_ONLY": "When two friends meet, do they swap only their own letters, or every letter they have collected so far?",
    "LEAVES_OUT_OWN_PIECE": "Did you count the friend's own letter too?",
    "IGNORES_ROUND_ORDER": "Go round by round. Could a letter pass through a meeting that happened before anyone in it had that letter?",
    "COUNTS_SHARED_PIECES_TWICE": "Write the letters, not just how many. If both friends had the same letter, does it count twice?",
    "NEW_FACES_FIRST": "Meeting someone new does not always help. For each friend, which letters are missing, and who has them all?",
    "WASTED_MEETING": "Compare the letters of the two friends in each meeting. Do any two already have exactly the same letters?",
    "IGNORES_LINKS": "Only friends joined by a line can meet. Can you really write that fast plan using only the lines?",
    "ODD_ONE_OUT_FREE": "With an odd number of friends, someone sits out the last round. How many pieces must they have before it?",
    "FARTHEST_PAIR_ONLY": "Each friend meets only one other per round. Can you write a plan that short, or does someone have to wait?",
    "ONE_PIECE_PER_ROUND": "When a friend with two letters meets another friend with two different letters, how many does each end with?",
    "FIRST_PLAN_IS_BEST": "Your plan works. Is there a round where someone learned little? Try to finish with one round fewer.",

    # Acorn Game (you against a raccoon that always plays its best)
    "BIGGEST_BASKET": "Could you really reach that big basket? At the grey fork before it, which way would the raccoon send you?",
    "RACCOON_PICKS_RANDOMLY": "You only get one basket, and the raccoon picks it. On each path, which basket would it leave you?",
    "ONE_STEP_AHEAD": "You headed for the biggest basket. Work back from the bottom: what does the raccoon let you have on that side?",
    "RACCOON_PICKS_ALL": "Look at the colours. At a yellow fork, who chooses: you or the raccoon?",
    "FLIPS_TURNS": "At your yellow forks, do you take the bigger or the smaller basket? And what does the raccoon want at the grey ones?",
    "GRABS_MOST": "After you take that many, what pile does the raccoon face? Can it win from there?",
    "OFF_BY_ONE_PATTERN": "Try the small case: if the pile equals the biggest move, can the player whose turn it is win right away?",
    "MISERE_MIXUP": "Read the sign again. Does taking the last acorn win or lose? Try a pile of 1 by hand.",
    "PLAIN_PATTERN": "Some move sizes are missing from the sign. Does the usual pattern still hold? Build the list from pile 1 up.",
    "EVEN_PILES_LOSE": "Try a pile of 2. Can the player whose turn it is take both acorns?",
    "ONLY_FIRST_TRAP": "You found the first lose-pile. Keep going up: is there another pile where every move leaves a win-pile?",

    # Bowl Belt (one worker walks the row, swapping neighbours that are out of order)
    "CARRY_STOPS": "After a swap, the bowl that moved is in the next pair. Did you check it again, or leave it behind?",
    "ONE_PASS_SORTS": "Walk the row once, pair by pair, and look at the end. Is every bowl in order yet?",
    "PASS_WRONG_WAY": "Look at the arrow. Which end does the worker start from?",
    "ONLY_CARRIED_MOVES": "Every swap moves two bowls. What happened to the bowls the worker passed?",
    "COUNTS_COMPARISONS": "Did the worker swap at every pair, or only where the left bowl was bigger?",
    "SWAPS_FOR_PASSES": "The question asks for workers, not swaps. One worker can make many swaps on one walk.",
    "FARTHEST_BOWL": "That bowl is far from home, but which way does it travel? Can it ride many places on one walk?",
    "COUNTS_CHECK_PASS": "Stop as soon as the row is in order. Did your last worker change anything?",
}

HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    patch = {
        "patch_id": "look-again",
        "built": "2026-11-12",
        "analyst": "Claude",
        "method": ("Claude wrote one short question for the student per misconception tag that the generators or the "
                   "answer checker can produce (117 tags). The practice page shows it after a wrong try with that tag. "
                   "Each question points at the likely mistake without giving the answer away."),
        "misconception_updates": [{"id": k, "look_again": v} for k, v in sorted(LOOK_AGAIN.items())],
    }
    with open(os.path.join(HERE, "look_again_patch.json"), "w") as fh:
        json.dump(patch, fh, indent=2, ensure_ascii=False)
    print(f"{len(LOOK_AGAIN)} questions written")

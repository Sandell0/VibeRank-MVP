from __future__ import annotations

from .domain import Question


FIXED_DEBUG_QUESTIONS: tuple[Question, ...] = (
    Question(
        id="debug-1-card-rule",
        title="Which cards must be checked?",
        domain="deductive logic",
        prompt=(
            "Four cards lie on a table showing A, D, 4, and 7. Every card has a letter on one "
            "side and a number on the other. Test this rule: 'If a card has a vowel on one side, "
            "then it has an even number on the other side.' Which card or cards must be turned "
            "over to determine whether the rule is violated? Explain briefly."
        ),
        reference_answer=(
            "Turn over A and 7. A must have an even number on its reverse; otherwise the rule is "
            "violated. The 7 must not have a vowel on its reverse; otherwise it is a vowel with "
            "an odd number. D is irrelevant because the rule says nothing about consonants, and "
            "4 is irrelevant because an even number is not required to have a vowel."
        ),
        rubric=(
            "Selects both A and 7",
            "Explains that A tests whether a vowel has an even number",
            "Explains that 7 tests the contrapositive case and does not require turning 4 or D",
        ),
        grade_anchors=(
            "Turn over A and 4, because those are the vowel and the even number.",
            "Turn over A only, to check whether its other side is even.",
            "Turn over A and 7: A checks the stated rule and 7 checks the odd-number case.",
            (
                "Turn over A and 7. A could violate the rule if its reverse is odd; 7 could "
                "violate it if its reverse is a vowel. D and 4 cannot falsify the one-way rule."
            ),
        ),
        difficulty_elo=1300.0,
    ),
    Question(
        id="debug-2-defective-source",
        title="Source of a defective item",
        domain="probability",
        prompt=(
            "A factory uses two production lines. Line A makes 30% of all items and 2% of its "
            "items are defective. Line B makes 70% of all items and 5% of its items are "
            "defective. An item is selected uniformly at random and is found to be defective. "
            "What is the probability that it came from Line B? Show the calculation."
        ),
        reference_answer=(
            "P(B | defective) = P(defective | B)P(B) / P(defective). The defective mass from "
            "B is 0.05 × 0.70 = 0.035. Total defective mass is 0.02 × 0.30 + 0.05 × 0.70 "
            "= 0.006 + 0.035 = 0.041. Therefore P(B | defective) = 0.035 / 0.041 = 35/41, "
            "approximately 0.8537 or 85.4%."
        ),
        rubric=(
            "Weights each defect rate by its production-line base rate",
            "Uses 0.035 as the numerator and 0.041 as total defective probability",
            "Concludes 35/41, approximately 85.4%",
        ),
        grade_anchors=(
            "The probability is 70%, because Line B makes 70% of the items.",
            "The probability is 5 / (2 + 5), or about 71.4%.",
            "The probability is about 85.4%, after accounting for the two production rates.",
            (
                "P(B|D) = (0.70×0.05) / (0.30×0.02 + 0.70×0.05) "
                "= 0.035/0.041 = 35/41 ≈ 85.4%."
            ),
        ),
        difficulty_elo=1700.0,
    ),
    Question(
        id="debug-3-loop-invariant",
        title="Trace and interpret the loop",
        domain="algorithmic reasoning",
        prompt=(
            "Consider this Python function:\n\n"
            "def mystery(values):\n"
            "    best = 0\n"
            "    current = 0\n"
            "    for x in values:\n"
            "        current = max(0, current + x)\n"
            "        best = max(best, current)\n"
            "    return best\n\n"
            "What does mystery([-4, 2, -1, 3, -5, 4, 4, -10]) return? Explain what "
            "`current` and `best` represent after each iteration, and identify the function's "
            "behavior on a non-empty list containing only negative numbers."
        ),
        reference_answer=(
            "It returns 8. The current values are 0, 2, 1, 4, 0, 4, 8, 0 and the best values "
            "are 0, 2, 2, 4, 4, 4, 8, 8. After each iteration, current is the maximum sum of "
            "a contiguous suffix ending at the current position, with the empty suffix of sum "
            "0 allowed. best is the maximum such sum seen anywhere so far. Thus this is Kadane's "
            "algorithm allowing an empty subarray; on an all-negative non-empty list it returns "
            "0 rather than the largest (least negative) element."
        ),
        rubric=(
            "Computes the returned value as 8",
            "Correctly describes current as the best nonnegative suffix sum and best as the maximum seen",
            "Notes that allowing the empty subarray makes every all-negative input return 0",
        ),
        grade_anchors=(
            "It returns 4; `current` is the current item and `best` is the largest item.",
            "It returns 8, but `current` and `best` both just store the largest sum.",
            (
                "It returns 8. `current` is the best contiguous sum ending at the current "
                "position and `best` is the largest seen, but the all-negative case is not discussed."
            ),
            (
                "It returns 8. `current` is the best suffix sum ending here, floored at zero; "
                "`best` is the maximum encountered. Because zero represents an empty subarray, "
                "an all-negative non-empty list returns 0."
            ),
        ),
        difficulty_elo=2100.0,
    ),
    Question(
        id="debug-4-operation-order",
        title="Enumerate the operation orders",
        domain="state transformation",
        prompt=(
            "A display starts at 0. Pressing button A adds 4 to the displayed number; pressing "
            "button B multiplies it by 2. You must press A exactly twice and B exactly twice, in "
            "any order. What are all possible final displayed values? Show enough intermediate "
            "work to justify that none are missing."
        ),
        reference_answer=(
            "There are six distinct orders of two A presses and two B presses. AABB gives 32, "
            "ABAB gives 24, ABBA gives 20, BAAB gives 16, BABA gives 12, and BBAA gives 8. "
            "Therefore all possible final values are {8, 12, 16, 20, 24, 32}. Listing all "
            "6 = 4!/(2!2!) orders proves none are missing."
        ),
        rubric=(
            "Lists exactly the six values 8, 12, 16, 20, 24, and 32",
            "Correctly evaluates representative or all A/B orderings",
            "Justifies completeness by accounting for all six distinct orderings",
        ),
        grade_anchors=(
            "The only result is 16 because adding and multiplying can be done in any order.",
            "The possible results are 8, 16, and 32.",
            "The possible values are 8, 12, 16, 20, 24, and 32, but no completeness argument is given.",
            (
                "The six orders are AABB→32, ABAB→24, ABBA→20, BAAB→16, BABA→12, "
                "and BBAA→8. Hence the values are {8, 12, 16, 20, 24, 32}; these six "
                "orders exhaust 4!/(2!2!) possibilities."
            ),
        ),
        difficulty_elo=1500.0,
    ),
    Question(
        id="debug-5-critical-path",
        title="Find the project completion time",
        domain="dependency planning",
        prompt=(
            "A project has six tasks. Durations are A=3, B=2, C=4, D=5, E=2, and F=3 "
            "hours. C can start only after A. D can start only after both A and B. E can start "
            "only after C. F can start only after both D and E. With unlimited workers and all "
            "tasks starting as early as possible, when does the project finish, and which chain "
            "of tasks determines that time? Show the earliest start or finish reasoning."
        ),
        reference_answer=(
            "A finishes at 3 and B at 2. C then runs from 3 to 7. D waits for A and B, so it "
            "runs from 3 to 8. E runs after C from 7 to 9. F waits for D and E, so it starts at "
            "9 and finishes at 12. The determining critical chain is A→C→E→F, whose duration "
            "is 3+4+2+3=12 hours."
        ),
        rubric=(
            "Computes the project completion time as 12 hours",
            "Identifies A→C→E→F as the critical chain",
            "Correctly reasons that F starts at hour 9 after D finishes at 8 and E at 9",
        ),
        grade_anchors=(
            "The project takes 19 hours because all six task durations must be added.",
            "The project finishes after 11 hours on the chain A→D→F.",
            "The project finishes after 12 hours on A→C→E→F, without showing the merge timing before F.",
            (
                "A and B finish at 3 and 2; C finishes at 7, D at 8, and E at 9. F therefore "
                "runs from 9 to 12. The critical chain is A→C→E→F, totaling 12 hours."
            ),
        ),
        difficulty_elo=1900.0,
    ),
)

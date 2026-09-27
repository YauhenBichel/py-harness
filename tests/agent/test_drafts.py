"""Asking again is cheaper than arguing, when a draft will not parse.

A reply the loop cannot read costs a whole step: it is answered with
"Could not parse" and the budget is one shorter. Five separate draft
shapes had to be repaired in the parser before a hosted model could be
measured at all — bold labels, list markers, a reason after the verb, a
whole-reply fence — which is the same finding the literature reports for
small models: what breaks them is format compliance, not reasoning.

So when a draft does not parse, ask again rather than feed the model its
own mistake. Blind resampling measures better than self-repair below 7B,
and costs fewer tokens.

The check stops at "does this parse". Anything further would need the
action carried out, and a carried-out action cannot be taken back.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from harness.agent.loop import _first_that_parses  # noqa: E402
from harness.agent.options import AgentOptions  # noqa: E402

GOOD = "Action: read\nPath: src/orders.py\n"
ALSO_GOOD = "Action: grep\nQuery: total\n"
JUNK = "Sure! Let me help you with that. Here is what I would do next."


def _replies(*texts: str):
    """A generate() that returns each text in turn, then repeats the last."""
    calls = {"n": 0}

    def generate(_prompt: str) -> str:
        i = min(calls["n"], len(texts) - 1)
        calls["n"] += 1
        return texts[i]

    generate.calls = calls  # type: ignore[attr-defined]
    return generate


class AskingAgainTest(unittest.TestCase):
    def test_one_draft_is_the_old_behaviour(self) -> None:
        generate = _replies(JUNK, GOOD)
        draft, turn, tried = _first_that_parses(
            generate, "p", 1, question=False, ship=False
        )
        self.assertEqual(tried, 1, "it asked again when it was told not to")
        self.assertIsNone(turn)
        self.assertEqual(draft, JUNK)
        self.assertEqual(generate.calls["n"], 1)

    def test_a_second_draft_is_taken_when_the_first_will_not_parse(self) -> None:
        generate = _replies(JUNK, GOOD)
        draft, turn, tried = _first_that_parses(
            generate, "p", 3, question=False, ship=False
        )
        self.assertEqual(tried, 2)
        self.assertIsNotNone(turn)
        self.assertEqual(turn.action, "read")
        self.assertEqual(draft, GOOD)

    def test_it_stops_at_the_first_that_parses(self) -> None:
        """The budget is a cap, not a quota. A good first draft costs one."""
        generate = _replies(GOOD, ALSO_GOOD)
        _draft, turn, tried = _first_that_parses(
            generate, "p", 5, question=False, ship=False
        )
        self.assertEqual(tried, 1)
        self.assertEqual(turn.action, "read")
        self.assertEqual(generate.calls["n"], 1)

    def test_it_gives_up_after_the_budget_and_keeps_the_last(self) -> None:
        generate = _replies(JUNK)
        draft, turn, tried = _first_that_parses(
            generate, "p", 3, question=False, ship=False
        )
        self.assertEqual(tried, 3)
        self.assertIsNone(turn, "an unparsed draft must still be reported as one")
        self.assertEqual(draft, JUNK)

    def test_a_budget_below_one_still_asks_once(self) -> None:
        generate = _replies(GOOD)
        _draft, _turn, tried = _first_that_parses(
            generate, "p", 0, question=False, ship=False
        )
        self.assertEqual(tried, 1)


class TheOptionTest(unittest.TestCase):
    def test_the_default_is_one_so_nothing_changes(self) -> None:
        """Every run that has ever been measured here used one draft."""
        self.assertEqual(AgentOptions(project=Path(".")).drafts, 1)

    def test_it_can_be_asked_for(self) -> None:
        self.assertEqual(AgentOptions(project=Path("."), drafts=4).drafts, 4)


if __name__ == "__main__":
    unittest.main()

"""A bug fix closes on a green suite, and the named-file nudge stands down.

Traced on 2026-09-27 with a local 30B, tiers 5 and 7: the fix landed on
the first step in every run, and eleven of fifteen runs then hit the
step limit. Two things kept them open.

After the patch, the policy demanded a new test and rendered the
write-tests skill, whose example calls `multiply` and `weekday`. The
model copied it verbatim, the gate refused it because `multiply` did not
exist, and the model added a `multiply` to the named file to make its
own copy pass.

And once the named file had been patched, every non-write turn was still
answered with "Next Action must be patch Path: <named file> with a
Find:", so the model re-sent a Find: that no longer matched, four turns
in a row, until the budget ran out.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from harness.agent.policy import (  # noqa: E402
    RUN_SUITE,
    LoopState,
    next_prompt,
    should_run_suite_after_write,
    write_needs_a_test,
)
from harness.task import set_decided_intent  # noqa: E402

SAID = "the totals from compute_total in src/orders.py come out one too low"
KEYWORD = "fix last_price in src/orders.py, it raises IndexError on a full list"


def _project(root: Path) -> None:
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src" / "orders.py").write_text(
        "def compute_total(prices):\n    return sum(prices)\n\n"
        "def last_price(prices):\n    return prices[-1]\n",
        encoding="utf-8",
    )
    # A suite that exists but never calls the symbol the task names.
    (root / "tests" / "test_orders.py").write_text(
        "import unittest\n\n\nclass T(unittest.TestCase):\n"
        "    def test_nothing(self) -> None:\n        self.assertTrue(True)\n",
        encoding="utf-8",
    )


class BugfixClosesOnAGreenSuiteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        _project(self.root)
        # The symptom phrasing carries no keyword; route it as the fitted
        # model does, so both ways into the bugfix path are covered.
        set_decided_intent(SAID, "bugfix")

    def tearDown(self) -> None:
        set_decided_intent(SAID, None)
        self.tmp.cleanup()

    def _patched_impl(self, task: str) -> LoopState:
        return LoopState(
            task=task, project=self.root, wrote_something=True,
            last_path="src/orders.py", wrote_paths={"src/orders.py"},
        )

    def test_a_bugfix_never_needs_a_hand_written_test(self) -> None:
        for task in (SAID, KEYWORD):
            state = self._patched_impl(task)
            self.assertFalse(
                write_needs_a_test(state, "patched src/orders.py", "src/orders.py"),
                task,
            )

    def test_the_suite_runs_right_after_the_fix(self) -> None:
        for task in (SAID, KEYWORD):
            state = self._patched_impl(task)
            self.assertTrue(
                should_run_suite_after_write(state, "patched src/orders.py", "src/orders.py"),
                task,
            )

    def test_the_write_tests_skill_is_not_handed_over_after_a_fix(self) -> None:
        for task in (SAID, KEYWORD):
            state = self._patched_impl(task)
            got = next_prompt(
                state, SimpleNamespace(action="patch", path="src/orders.py"),
                "patched src/orders.py",
            )
            self.assertEqual(got, RUN_SUITE, task)
            self.assertNotIn("write-tests", got)
            self.assertNotIn("multiply", got)

    def test_a_refused_turn_after_the_fix_points_at_the_suite(self) -> None:
        """Turn 6 of the traced run: Find: no longer matches, fix is in."""
        state = self._patched_impl(SAID)
        got = next_prompt(
            state, SimpleNamespace(action="patch", path="src/orders.py"),
            "Find: string not in file.",
        )
        self.assertEqual(got, RUN_SUITE)
        self.assertNotIn("must be patch", got)

    def test_after_the_suite_passed_the_next_step_is_done(self) -> None:
        state = self._patched_impl(SAID)
        state.ran_tests = True
        got = next_prompt(
            state, SimpleNamespace(action="patch", path="src/orders.py"),
            "Find: string not in file.",
        )
        self.assertIn("Action: done", got)
        self.assertNotIn("must be patch", got)

    def test_before_any_fix_the_named_file_is_still_demanded(self) -> None:
        state = LoopState(task=SAID, project=self.root)
        got = next_prompt(
            state, SimpleNamespace(action="read", path="src/orders.py"), "ok"
        )
        self.assertIn("must be patch Path: src/orders.py", got)

    def test_the_path_is_matched_however_the_model_spelt_it(self) -> None:
        state = self._patched_impl(SAID)
        state.wrote_paths = {"./src/orders.py"}
        got = next_prompt(
            state, SimpleNamespace(action="read", path="src/orders.py"), "ok"
        )
        self.assertEqual(got, RUN_SUITE)


class TheLoopRecordsWhatItWroteTest(unittest.TestCase):
    """The nudge above reads `wrote_paths`; the loop has to fill it in."""

    def test_a_patch_lands_in_wrote_paths(self) -> None:
        from unittest import mock

        from harness import Agent, AgentOptions

        def scripted(*drafts: str):
            remaining = list(drafts)

            def generate(_prompt: str) -> str:
                return remaining.pop(0) if remaining else "Action: done\nSummary: out of drafts"

            return lambda *a, **k: ("scripted", generate)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root)
            states: list[LoopState] = []
            real = LoopState.__init__

            def spy(self, *a, **k):
                real(self, *a, **k)
                states.append(self)

            with mock.patch.object(LoopState, "__init__", spy):
                with mock.patch(
                    "harness.agent.loop.make_generate",
                    scripted(
                        "Action: read\nPath: src/orders.py",
                        "Action: patch\nPath: src/orders.py\n"
                        "Find:     return prices[-1]\nReplace:     return prices[-1]  # same",
                        "Action: done\nSummary: fixed last_price",
                    ),
                ):
                    Agent(AgentOptions(project=root, task=KEYWORD)).run()
        self.assertTrue(states, "the loop never built a LoopState")
        self.assertIn("src/orders.py", states[-1].wrote_paths, states[-1].wrote_paths)


class SayingDonePlainlyTest(unittest.TestCase):
    """Told to finish, the 30B answered in a sentence, or pasted its whole
    plan again with the stale patch above the done block. Either way the
    fix was in and the suite green, and the run ran out of steps."""

    def _run(self, *drafts: str):
        from unittest import mock

        from harness import Agent, AgentOptions

        remaining = list(drafts)

        def generate(_prompt: str) -> str:
            return remaining.pop(0) if remaining else "Action: done\nSummary: out of drafts"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root)
            (root / "src" / "orders.py").write_text(
                "def compute_total(prices):\n    return sum(prices)\n\n"
                "def last_price(prices):\n    return prices[len(prices)]\n",
                encoding="utf-8",
            )
            with mock.patch(
                "harness.agent.loop.make_generate", lambda *a, **k: ("scripted", generate)
            ):
                return Agent(AgentOptions(project=root, task=KEYWORD, steps=4)).run()

    PATCH = (
        "Action: patch\nPath: src/orders.py\n"
        "Find:     return prices[len(prices)]\nReplace:     return prices[-1]\n"
    )

    def test_a_bare_sentence_after_done_was_asked_is_the_summary(self) -> None:
        got = self._run(
            self.PATCH,
            "I changed last_price to return the last element.",
        )
        self.assertEqual(got.stopped, "done", [s.result or s.refused for s in got.steps])
        self.assertTrue(got.ok)
        self.assertIn("last_price", got.summary)
        self.assertEqual(len(got.steps), 2)

    def test_a_pasted_plan_after_done_was_asked_takes_its_done_block(self) -> None:
        got = self._run(
            self.PATCH,
            "Action: read\nPath: src/orders.py\n\n" + self.PATCH
            + "\nAction: run\nArgv: -m unittest discover -s tests -q\n\n"
            "Action: done\nSummary: fixed last_price\n",
        )
        self.assertEqual(got.stopped, "done", [s.result or s.refused for s in got.steps])
        self.assertEqual(got.summary, "fixed last_price")
        self.assertEqual(len(got.steps), 2)

    def test_a_sentence_before_done_was_asked_still_does_not_parse(self) -> None:
        from harness.agent.loop import _first_that_parses

        _draft, turn, _tried = _first_that_parses(
            lambda _p: "Sure, let me look at that.", "p", 1, question=False, ship=False
        )
        self.assertIsNone(turn)

    def test_only_the_finishing_nudge_counts_as_asking_for_done(self) -> None:
        from harness.agent.loop import _asked_for_done

        self.assertTrue(_asked_for_done(
            "Tool result:\npatched src/orders.py\nexit 0\nOK\n\n"
            "Tests passed. Action: done Summary: say what you changed.\n"))
        self.assertTrue(_asked_for_done(
            "Tool result:\nFind: string not in file.\n\n"
            "The fix is in and the suite passed. Action: done Summary: say what you changed.\n"))
        # The opening prompt for a question lists done as one option.
        self.assertFalse(_asked_for_done(
            "Questions: if you see # auto-read, Action: done. Else read one file, then done.\n"
            "Files:\n  src/orders.py\n\nTask: what does compute_total return?\n"))
        self.assertFalse(_asked_for_done(
            "Nothing was changed. Action: patch Path: src/orders.py with a Find: line "
            "copied whole from the file and a Replace:. If the file is already correct, "
            "Action: done Summary: copy the line that makes it correct.\n"))


if __name__ == "__main__":
    unittest.main()

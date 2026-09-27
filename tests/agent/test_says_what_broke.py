"""A run that turned a green suite red stops, and every ending says what it wrote.

Issue #339: asked to add one function to a 259-file project, a run got
`exit 1` from the suite and kept appending for thirteen more steps. It
ended "stopped after 20 steps" over a project whose 996 tests no longer
imported. The backups were there and nothing pointed at them.

Two rules, tested separately. The suite's colour is read before the
model starts; a run that turns green into red gets the one repair the
loop already allows, and is stopped on the second red. And every ending
names the files written, their backups, and whether the suite is worse
than when the run began.
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from harness import Agent, AgentOptions  # noqa: E402
from harness.agent.loop import (  # noqa: E402
    _closing_note,
    _failing_line,
    _measure_suite_at_start,
)
from harness.agent.policy import LoopState  # noqa: E402

FIX = "fix total in src/orders.py, it returns the wrong sum"
ADD = "add a function double(amount) to src/orders.py"

READ = "Action: read\nPath: src/orders.py\n"


def _patch(find: str, replace: str) -> str:
    return f"Action: patch\nPath: src/orders.py\nFind: {find}\nReplace: {replace}\n"


def _project(root: Path, expected: int = 3) -> None:
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src" / "__init__.py").write_text("", encoding="utf-8")
    (root / "src" / "orders.py").write_text(
        "def total(prices):\n    return sum(prices)\n", encoding="utf-8"
    )
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")
    (root / "tests" / "test_orders.py").write_text(
        "import unittest\n\nfrom src.orders import total\n\n\n"
        "class T(unittest.TestCase):\n"
        f"    def test_total(self) -> None:\n        self.assertEqual(total([1, 2]), {expected})\n",
        encoding="utf-8",
    )


def _scripted(*drafts: str):
    remaining = list(drafts)

    def generate(_prompt: str) -> str:
        return remaining.pop(0) if remaining else "???"

    return lambda *a, **k: ("scripted", generate)


def _run(root: Path, task: str, *drafts: str, steps: int = 8):
    with mock.patch("harness.agent.loop.make_generate", _scripted(*drafts)):
        return Agent(AgentOptions(project=root, task=task, steps=steps)).run()


class StopWhenTheRunBrokeTheSuiteTest(unittest.TestCase):
    def test_green_to_red_twice_stops_the_run_and_names_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root)
            got = _run(
                root, FIX,
                _patch("    return sum(prices)", "    return sum(prices) - 1"),
                _patch("    return sum(prices) - 1", "    return sum(prices) - 2"),
                _patch("    return sum(prices) - 2", "    return sum(prices) - 3"),
            )
        self.assertEqual(got.stopped, "broke", [s.refused or s.result for s in got.steps])
        self.assertFalse(got.ok)
        self.assertIn("turned the suite red", got.summary)
        self.assertIn("Wrote: src/orders.py", got.summary)
        self.assertIn("src/orders.py.bak", got.summary)
        self.assertIn("green before this run and is red now", got.summary)
        self.assertRegex(got.summary, r"FAIL: test_total|AssertionError")
        # Two writes, not three: the third patch was never asked for.
        self.assertEqual(len(got.writes), 2, got.writes)

    def test_one_red_is_the_repair_the_loop_already_allows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root)
            got = _run(
                root, FIX,
                _patch("    return sum(prices)", "    return sum(prices) - 1"),
                _patch("    return sum(prices) - 1", "    return sum(prices)"),
            )
        self.assertNotEqual(got.stopped, "broke", got.summary)
        self.assertNotIn("red now", got.summary)

    def test_a_suite_already_red_is_not_this_runs_fault(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root, expected=4)
            got = _run(
                root, FIX,
                _patch("    return sum(prices)", "    return sum(prices) - 1"),
                _patch("    return sum(prices) - 1", "    return sum(prices) - 2"),
                _patch("    return sum(prices) - 2", "    return sum(prices) - 3"),
                steps=6,
            )
        self.assertNotEqual(got.stopped, "broke", got.summary)
        self.assertIn("already red before this run", got.summary)

    def test_a_read_only_run_does_not_measure_the_suite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root)
            state = LoopState(task=FIX, project=root, allow_writes=False)
            with mock.patch("harness.agent.loop._verify_mechanical") as verify:
                _measure_suite_at_start(root, state)
            verify.assert_not_called()
        self.assertEqual(state.suite_at_start, "")


class EveryEndingSaysWhatWasWrittenTest(unittest.TestCase):
    def test_running_out_of_steps_lists_the_writes_and_the_backups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root)
            # After the write the suite is green and the loop asks for done;
            # a model that keeps exploring instead runs out of steps.
            got = _run(
                root, ADD,
                "Action: patch\nPath: src/orders.py\nAppend:\ndef double(amount):\n    return amount * 2\n",
                "Action: grep\nQuery: total\n",
                "Action: grep\nQuery: double\n",
                "Action: grep\nQuery: prices\n",
                steps=4,
            )
        self.assertEqual(got.stopped, "steps", got.summary)
        self.assertIn("stopped after 4 steps", got.summary)
        self.assertIn("Wrote: src/orders.py", got.summary)
        self.assertIn("src/orders.py.bak", got.summary)

    def test_nothing_written_adds_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _project(root)
            state = LoopState(task=FIX, project=root, suite_at_start="green")
            self.assertEqual(_closing_note(root, state, ()), "")

    def test_the_failing_line_is_the_error_or_the_test(self) -> None:
        self.assertEqual(
            _failing_line("exit 1\nTraceback\n  File x\nImportError: cannot import name 'total'\n"),
            "ImportError: cannot import name 'total'",
        )
        self.assertEqual(
            _failing_line("exit 1\nF\n======\nFAIL: test_total (tests.test_orders.T)\n------\n"),
            "FAIL: test_total (tests.test_orders.T)",
        )
        self.assertEqual(_failing_line("exit 1\n-----\nRan 0 tests\n"), "Ran 0 tests")
        self.assertEqual(_failing_line(""), "exit code was not 0")


if __name__ == "__main__":
    unittest.main()

"""A suite that ran nothing did not pass.

`unittest discover` exits 0 when it collected no tests, so the harness
read "Ran 0 tests" as a green suite. A run then wrote this:

    def test_apply_discount(self) -> None:
        got = apply_discount(100.0, 25.0)
        self.assertEqual(got, 75.0)

a test method with no class around it. It compiles, so nothing errors.
Discovery imports the file, finds no `TestCase` subclass, collects
nothing, and exits 0 — and the run reported done. Issue #173.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from types import SimpleNamespace  # noqa: E402

from harness.agent.policy import (  # noqa: E402
    NO_TESTS_RAN,
    LoopState,
    next_prompt,
    ran_no_tests,
)

DISCOUNT = "def apply_discount(total, percent):\n    return round(total * (1 - percent / 100), 2)\n"

ORPHAN_METHOD = '''

def test_apply_discount(self) -> None:
        from pricing import apply_discount
        got = apply_discount(100.0, 25.0)
        self.assertEqual(got, 75.0)
'''

REAL_TEST = '''import unittest

from pricing import apply_discount


class TestPricing(unittest.TestCase):
    def test_apply_discount(self) -> None:
        self.assertEqual(apply_discount(100.0, 25.0), 75.0)
'''


class ReadingTheSuiteOutputTest(unittest.TestCase):
    def test_zero_tests_is_not_a_pass(self) -> None:
        self.assertTrue(ran_no_tests("exit 0\nRan 0 tests in 0.000s\n\nOK\n"))

    def test_one_test_is(self) -> None:
        self.assertFalse(ran_no_tests("exit 0\nRan 1 test in 0.001s\n\nOK\n"))

    def test_ten_tests_are_not_mistaken_for_zero(self) -> None:
        """`Ran 0 tests` must not match inside `Ran 10 tests`."""
        self.assertFalse(ran_no_tests("exit 0\nRan 10 tests in 0.010s\n\nOK\n"))

    def test_the_other_wording_is_caught(self) -> None:
        self.assertTrue(ran_no_tests("exit 0\nNO TESTS RAN\n"))

    def test_the_refusal_says_what_to_do(self) -> None:
        self.assertIn("TestCase", NO_TESTS_RAN)
        self.assertIn("not done", NO_TESTS_RAN)


class AgainstRealDiscoveryTest(unittest.TestCase):
    """The shapes above, run through unittest for real."""

    def _discover(self, body: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "pricing.py").write_text(DISCOUNT, encoding="utf-8")
            (root / "tests" / "test_pricing.py").write_text(body, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                cwd=root, capture_output=True, text=True, timeout=60, check=False,
            )
            return f"exit {proc.returncode}\n{proc.stdout}{proc.stderr}"

    def test_the_orphan_method_really_runs_nothing(self) -> None:
        """The exit code is not the signal, which is the point.

        Python 3.12 made `unittest` exit 5 when it collected nothing;
        3.11 exits 0 and reads as a pass. This project tests on both, so
        the check is on what the output says rather than on the code.
        """
        self.assertTrue(ran_no_tests(self._discover(ORPHAN_METHOD)))

    def test_a_real_test_case_is_not_refused(self) -> None:
        result = self._discover(REAL_TEST)
        self.assertTrue(result.startswith("exit 0"))
        self.assertFalse(ran_no_tests(result))


class ZeroTestsDoesNotMarkTheSuiteAsRunTest(unittest.TestCase):
    """The other half of #173. The nudge said "not done", but the loop had
    already set `ran_tests` on the exit code alone, so the next `done`
    passed the write gate over a suite that proved nothing. Python 3.11
    exits 0 on an empty collection; 3.12 exits 5."""

    ZERO = "exit 0\n\n----------------------------------------------------------------------\nRan 0 tests in 0.000s\n\nNO TESTS RAN\n"
    ONE = "exit 0\n.\n----------------------------------------------------------------------\nRan 1 test in 0.000s\n\nOK\n"

    def test_suite_passed_needs_a_test_to_have_run(self) -> None:
        from harness.agent.loop import _suite_passed

        self.assertFalse(_suite_passed(self.ZERO))
        self.assertTrue(_suite_passed(self.ONE))
        self.assertFalse(_suite_passed("exit 1\nFAIL: test_x\n"))

    def test_the_automatic_suite_run_does_not_count_zero_tests(self) -> None:
        from unittest import mock

        from harness.agent import loop as L

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            state = LoopState(task="add multiply to src/m.py", project=root, wrote_something=True)
            turn = SimpleNamespace(action="patch", path="src/m.py")
            with mock.patch.object(L, "should_run_suite_after_write", return_value=True), \
                 mock.patch.object(L, "run_python", return_value=self.ZERO):
                _result, nudge = L._nudge_after_action(root, state, turn, "patched src/m.py", None)
        self.assertFalse(state.ran_tests, "zero tests were recorded as a passing suite")
        self.assertEqual(nudge, NO_TESTS_RAN)

    def test_the_automatic_suite_run_counts_a_real_pass(self) -> None:
        from unittest import mock

        from harness.agent import loop as L

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            state = LoopState(task="add multiply to src/m.py", project=root, wrote_something=True)
            turn = SimpleNamespace(action="patch", path="src/m.py")
            with mock.patch.object(L, "should_run_suite_after_write", return_value=True), \
                 mock.patch.object(L, "run_python", return_value=self.ONE):
                L._nudge_after_action(root, state, turn, "patched src/m.py", None)
        self.assertTrue(state.ran_tests)


if __name__ == "__main__":
    unittest.main()


class TheLoopIsToldTest(unittest.TestCase):
    """The helper being right is not the same as the loop using it."""

    def _after_suite(self, output: str, *, wrote: bool = True) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            state = LoopState(
                task="write tests for apply_discount",
                project=root,
                wrote_something=wrote,
            )
            turn = SimpleNamespace(action="run", path="")
            return next_prompt(state, turn, output)

    def test_a_suite_that_ran_nothing_is_sent_back(self) -> None:
        got = self._after_suite("exit 0\nRan 0 tests in 0.000s\n\nOK\n")
        self.assertEqual(got, NO_TESTS_RAN)

    def test_the_same_when_the_exit_code_is_five(self) -> None:
        """Python 3.12 and later exit 5 rather than 0."""
        got = self._after_suite("exit 5\nRan 0 tests in 0.000s\n\nNO TESTS RAN\n")
        self.assertEqual(got, NO_TESTS_RAN)

    def test_a_suite_that_ran_something_is_not(self) -> None:
        got = self._after_suite("exit 0\nRan 4 tests in 0.003s\n\nOK\n")
        self.assertNotEqual(got, NO_TESTS_RAN)

    def test_a_run_before_any_writing_is_left_alone(self) -> None:
        """Looking at the starting state is not a failure to report."""
        got = self._after_suite("exit 0\nRan 0 tests in 0.000s\n", wrote=False)
        self.assertNotEqual(got, NO_TESTS_RAN)

    def test_ten_tests_are_not_read_as_zero(self) -> None:
        got = self._after_suite("exit 0\nRan 10 tests in 0.010s\n\nOK\n")
        self.assertNotEqual(got, NO_TESTS_RAN)

    def test_the_words_in_a_failure_message_are_not_a_suite_result(self) -> None:
        """`Ran 0 tests` has to start its line, or a traceback quoting
        the phrase would end the run."""
        got = self._after_suite(
            "exit 1\nAssertionError: expected 'Ran 0 tests' in output\n"
        )
        self.assertNotEqual(got, NO_TESTS_RAN)

"""The experiment pipeline has to refuse the mistakes already made here.

Three of them, all from this project's own record:

A gap inside the noise floor was read as a result, four times in one
evening. A total of "nothing" hid one case going 6/10 to 10/10 and
another going 3/10 to 0/10. And the tell for that hidden pair was a flat
line across passes plus zero-step runs going from none to ten — a
mechanical path answering wrongly with no model at all.

`compare` has to say all three out loud, so reading the number correctly
is not a matter of remembering.
"""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def _experiment():
    spec = importlib.util.spec_from_file_location(
        "py_harness_experiment", ROOT / "scripts" / "measure" / "experiment.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _rows(verdicts: dict[str, str], steps: int = 4) -> list[dict]:
    """verdicts: case -> one letter per pass, Y for worked."""
    rows = []
    for case, marks in verdicts.items():
        for number, mark in enumerate(marks, 1):
            rows.append(
                {
                    "case": case,
                    "tier": 3,
                    "worked": "yes" if mark == "Y" else "no",
                    "why": "" if mark == "Y" else "did not work",
                    "pass": number,
                    "steps": steps,
                    "asked": 0,
                }
            )
    return rows


def _result(mod, name: str, verdicts: dict[str, str], **kw):
    passes = len(next(iter(verdicts.values())))
    return mod.Result(
        name=name,
        rows=_rows(verdicts, steps=kw.pop("steps", 4)),
        passes=passes,
        model=kw.pop("model", "llama3.1:8b"),
        engine=kw.pop("engine", "ollama"),
        tiers=kw.pop("tiers", [3]),
        commit=kw.pop("commit", "abc1234"),
        dirty=kw.pop("dirty", False),
        when="2026-09-24",
        machine="Darwin arm64",
    )


class ReadingTheNumberTest(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = _experiment()

    def test_a_gap_inside_the_floor_is_called_noise(self) -> None:
        """Both arms move by 1 on their own, so a gap of 1 says nothing."""
        before = _result(self.mod, "before", {"a": "YYNYY", "b": "NYNYN"})
        after = _result(self.mod, "after", {"a": "YYYYY", "b": "NYNYN"})
        said = self.mod.compare(before, after)
        self.assertIn("NOISE", said)
        self.assertNotIn("REAL", said)

    def test_a_gap_outside_the_floor_is_called_real(self) -> None:
        before = _result(self.mod, "before", {"a": "NNNNN", "b": "NNNNN"})
        after = _result(self.mod, "after", {"a": "YYYYY", "b": "YYYYY"})
        said = self.mod.compare(before, after)
        self.assertIn("REAL", said)
        self.assertNotIn("NOISE", said)

    def test_the_floor_is_the_wider_of_the_two_arms(self) -> None:
        """A steady arm must not make a jumpy one look resolvable."""
        steady = _result(self.mod, "steady", {"a": "YYYYY", "b": "NNNNN"})
        jumpy = _result(self.mod, "jumpy", {"a": "YNYNY", "b": "YNYNN"})
        call, _gap, floor = self.mod.verdict(steady, jumpy)
        self.assertGreaterEqual(floor, 1)
        self.assertEqual(call, "noise")


class WhatATotalHidesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = _experiment()

    def test_every_case_is_printed_even_when_the_total_did_not_move(self) -> None:
        """The 9-of-20 against 10-of-20 case: two large effects cancelling."""
        before = _result(self.mod, "before", {"slugify": "YNYNYN", "wordcount": "YNNYNN"})
        after = _result(self.mod, "after", {"slugify": "YYYYYY", "wordcount": "NNNNNN"})
        said = self.mod.compare(before, after)
        self.assertIn("slugify", said)
        self.assertIn("wordcount", said)
        self.assertIn("6/6", said, "the case that went to perfect is not shown")
        self.assertIn("0/6", said, "the case that went to zero is not shown")

    def test_it_warns_that_a_total_can_hide_the_parts(self) -> None:
        before = _result(self.mod, "before", {"slugify": "YNYNYN", "wordcount": "YNNYNN"})
        after = _result(self.mod, "after", {"slugify": "YYYYYY", "wordcount": "NNNNNN"})
        self.assertIn("cancelling", self.mod.compare(before, after))


class TheTellsTest(unittest.TestCase):
    """Variance and zero-step runs, the two signals that caught it."""

    def setUp(self) -> None:
        self.mod = _experiment()

    def test_a_flat_line_across_passes_is_called_out(self) -> None:
        before = _result(self.mod, "before", {"a": "YNYNY", "b": "NYNYN"})
        after = _result(self.mod, "after", {"a": "YYYYY", "b": "NNNNN"})
        said = self.mod.compare(before, after)
        self.assertIn("same on every pass", said)

    def test_a_normal_spread_is_not_called_out(self) -> None:
        """Both arms must really vary. Two cases that alternate against
        each other total the same every pass, which is flat on purpose
        and would be flagged — correctly."""
        before = _result(self.mod, "before", {"a": "YYNYN", "b": "YNNYY"})
        after = _result(self.mod, "after", {"a": "YNNYY", "b": "YYNYN"})
        self.assertEqual(before.totals, [2, 1, 0, 2, 1], "fixture is not varying")
        self.assertNotIn("same on every pass", self.mod.compare(before, after))

    def test_a_perfect_score_is_not_called_stuck(self) -> None:
        """Every case passing every pass is flat by arithmetic, not
        because something stopped being decided by the model. A real
        20/20 arm was warned about before this."""
        before = _result(self.mod, "before", {"a": "YYNYN", "b": "YNNYY"})
        after = _result(self.mod, "after", {"a": "YYYYY", "b": "YYYYY"})
        self.assertEqual(after.totals, [2, 2, 2, 2, 2], "fixture is not at the ceiling")
        self.assertNotIn("same on every pass", self.mod.compare(before, after))

    def test_a_flat_zero_is_not_called_stuck_either(self) -> None:
        before = _result(self.mod, "before", {"a": "YYNYN", "b": "YNNYY"})
        after = _result(self.mod, "after", {"a": "NNNNN", "b": "NNNNN"})
        self.assertEqual(after.totals, [0, 0, 0, 0, 0], "fixture is not at the floor")
        self.assertNotIn("same on every pass", self.mod.compare(before, after))

    def test_zero_step_runs_appearing_is_called_out(self) -> None:
        before = _result(self.mod, "before", {"a": "YNYNY"}, steps=6)
        after = _result(self.mod, "after", {"a": "YYYYY"}, steps=0)
        said = self.mod.compare(before, after)
        self.assertIn("Zero-step runs moved", said)
        self.assertIn("0 -> 5", said)

    def test_zero_step_runs_holding_steady_is_not_called_out(self) -> None:
        before = _result(self.mod, "before", {"a": "YNYNY"}, steps=3)
        after = _result(self.mod, "after", {"a": "YYNYN"}, steps=3)
        self.assertNotIn("Zero-step runs moved", self.mod.compare(before, after))


class ComparingLikeWithLikeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = _experiment()

    def test_two_different_models_are_flagged(self) -> None:
        a = _result(self.mod, "a", {"x": "YNYNY"}, model="llama3.1:8b")
        b = _result(self.mod, "b", {"x": "YYYYY"}, model="qwen2.5-coder:7b")
        self.assertIn("different models", self.mod.compare(a, b))

    def test_two_different_tiers_are_flagged(self) -> None:
        a = _result(self.mod, "a", {"x": "YNYNY"}, tiers=[3])
        b = _result(self.mod, "b", {"x": "YYYYY"}, tiers=[6])
        self.assertIn("not the same cases", self.mod.compare(a, b))

    def test_a_dirty_tree_is_flagged_as_unreplayable(self) -> None:
        a = _result(self.mod, "a", {"x": "YNYNY"})
        b = _result(self.mod, "b", {"x": "YYYYY"}, dirty=True)
        self.assertIn("dirty tree", self.mod.compare(a, b))

    def test_the_same_setup_is_not_flagged(self) -> None:
        a = _result(self.mod, "a", {"x": "YNYNY"})
        b = _result(self.mod, "b", {"x": "YYNYN"})
        said = self.mod.compare(a, b)
        for warning in ("different models", "not the same cases", "dirty tree"):
            self.assertNotIn(warning, said)


class ARunThatNeverRanTest(unittest.TestCase):
    """A missing model scores zero. That is not a score."""

    def setUp(self) -> None:
        self.mod = _experiment()

    def _errored(self, name: str, n: int):
        rows = [
            {"case": "a", "tier": 1, "worked": "error",
             "why": "RuntimeError: remote model HTTP 404", "pass": i + 1}
            for i in range(n)
        ]
        return self.mod.Result(name=name, rows=rows, passes=n, model="absent:8b",
                               engine="ollama", tiers=[1], commit="abc1234",
                               when="2026-09-24", machine="Darwin arm64")

    def test_errored_runs_are_counted_apart_from_failures(self) -> None:
        self.assertEqual(self._errored("x", 4).errored, 4)
        good = _result(self.mod, "y", {"a": "YNYNY"})
        self.assertEqual(good.errored, 0)

    def test_a_comparison_says_the_setup_was_broken(self) -> None:
        said = self.mod.compare(_result(self.mod, "a", {"x": "YNYNY"}),
                                self._errored("b", 5))
        self.assertIn("never ran", said)
        self.assertIn("broken setup", said)

    def test_the_record_keeps_the_errored_count(self) -> None:
        self.assertIn("errored_runs", self._errored("x", 2).as_dict())


class TheRecordTest(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = _experiment()

    def test_a_result_round_trips(self) -> None:
        original = _result(self.mod, "x", {"a": "YNYNY", "b": "YYNNY"})
        again = self.mod.Result.from_dict(json.loads(json.dumps(original.as_dict())))
        self.assertEqual(again.worked, original.worked)
        self.assertEqual(again.totals, original.totals)
        self.assertEqual(again.by_case, original.by_case)

    def test_the_record_keeps_what_a_replay_needs(self) -> None:
        stored = _result(self.mod, "x", {"a": "YNYNY"}).as_dict()
        for key in ("commit", "model", "engine", "tiers", "passes", "when", "dirty"):
            self.assertIn(key, stored, f"{key} is not recorded, so this cannot be replayed")

    def test_the_raw_rows_are_kept_not_just_the_summary(self) -> None:
        """A summary cannot be re-read later for something nobody thought
        to count at the time. The rows can."""
        stored = _result(self.mod, "x", {"a": "YNYNY"}).as_dict()
        self.assertEqual(len(stored["rows"]), 5)
        self.assertIn("why", stored["rows"][0])


if __name__ == "__main__":
    unittest.main()

"""The benchmark's repeat mode, which is the point of the benchmark.

One pass of these cases is a sample, not a score: ten of the fifteen
changed verdict between identical runs on unchanged code. The runner has
to make repeating easy and has to say so when it has not been done.
"""

import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _bench():
    spec = importlib.util.spec_from_file_location(
        "python_vibe_bench", ROOT / "scripts" / "measure" / "bench.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _rows(verdicts: dict[str, str]) -> list[dict]:
    """verdicts: case -> a string like 'YnY', one letter per pass."""
    rows = []
    for case, marks in verdicts.items():
        for number, mark in enumerate(marks, 1):
            rows.append(
                {
                    "case": case,
                    "tier": 1,
                    "worked": "yes" if mark == "Y" else "no",
                    "pass": number,
                }
            )
    return rows


class RepeatReportTest(unittest.TestCase):
    def _report(self, rows, passes) -> str:
        buffer = io.StringIO()
        with redirect_stderr(buffer):
            _bench().report(rows, passes)
        return buffer.getvalue()

    def test_a_single_pass_says_it_cannot_settle_a_comparison(self) -> None:
        text = self._report(_rows({"a": "Y", "b": "n"}), 1)
        self.assertIn("Only one pass", text)
        self.assertIn("--repeat", text)

    def test_repeats_show_a_rate_for_every_case(self) -> None:
        text = self._report(_rows({"steady": "YYY", "flaky": "YnY"}), 3)
        self.assertIn("steady", text)
        self.assertIn("3/3", text)
        self.assertIn("2/3", text)
        self.assertNotIn("Only one pass", text)

    def test_it_counts_what_held_still_and_what_moved(self) -> None:
        text = self._report(_rows({"a": "YYY", "b": "YnY", "c": "nnn"}), 3)
        self.assertIn("passed every pass: 1", text)
        self.assertIn("changed verdict: 1", text)

    def test_it_names_the_spread_when_anything_moved(self) -> None:
        text = self._report(_rows({"a": "YYY", "b": "Ynn"}), 3)
        self.assertIn("totals per pass: [2, 1, 1]", text)
        self.assertIn("noise", text)

    def test_a_steady_set_is_not_called_noisy(self) -> None:
        text = self._report(_rows({"a": "YY", "b": "YY"}), 2)
        self.assertIn("changed verdict: 0", text)
        self.assertNotIn("noise", text)


class RepeatFlagTest(unittest.TestCase):
    def test_the_flag_exists_and_defaults_to_one(self) -> None:
        source = (ROOT / "scripts" / "measure" / "bench.py").read_text(encoding="utf-8")
        self.assertIn('"--repeat"', source)
        self.assertIn('row["pass"] = number', source)

    def test_zero_repeats_is_refused(self) -> None:
        module = _bench()
        old = sys.argv
        try:
            sys.argv = ["bench.py", "--repeat", "0"]
            with redirect_stderr(io.StringIO()):
                self.assertEqual(module.main(), 2)
        finally:
            sys.argv = old


if __name__ == "__main__":
    unittest.main()


class KeepingTheTracesTest(unittest.TestCase):
    """The benchmark runs in a temporary directory that is then deleted.

    Recording is on by default, and it writes into whatever project the
    run ran in — so every turn the benchmark produced went into that
    directory and was deleted with it. Ninety runs left nothing. These
    tests check the turns now land somewhere that outlives the run.
    """

    def setUp(self) -> None:
        self.bench = _bench()

    def test_the_default_is_outside_the_temporary_project(self) -> None:
        """It is the checkout's file, which is what the builder reads."""
        from harness.observe.trace_record import default_trace_path

        self.assertEqual(self.bench.DEFAULT_TRACES, default_trace_path(self.bench.ROOT))

    def test_run_takes_somewhere_to_record(self) -> None:
        import inspect

        self.assertIn("traces", inspect.signature(self.bench.run).parameters)

    def test_run_hands_that_path_to_the_agent(self) -> None:
        """`record=traces`, not a temporary path the run then deletes."""
        import ast

        source = (ROOT / "scripts" / "measure" / "bench.py").read_text(encoding="utf-8")
        run = next(
            node
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.FunctionDef) and node.name == "run"
        )
        options = [
            node
            for node in ast.walk(run)
            if isinstance(node, ast.Call)
            and getattr(node.func, "id", "") == "AgentOptions"
        ]
        self.assertEqual(len(options), 1)
        passed = {kw.arg: kw.value for kw in options[0].keywords}
        self.assertIn("record", passed)
        self.assertEqual(getattr(passed["record"], "id", ""), "traces")

    def test_the_flag_is_offered_and_can_be_turned_off(self) -> None:
        text = " ".join(_help(self.bench).split())  # argparse wraps mid-phrase
        self.assertIn("--traces", text)
        self.assertIn("empty string to record nothing", text)

    def test_an_empty_traces_argument_records_nothing(self) -> None:
        self.assertIsNone(self.bench._trace_path(""))

    def test_a_named_path_is_used_and_expanded(self) -> None:
        self.assertEqual(self.bench._trace_path("~/t.jsonl"), Path.home() / "t.jsonl")

    def test_counting_turns_in_a_file(self) -> None:
        import tempfile

        self.assertEqual(self.bench._turns_in(None), 0)
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "nothing.jsonl"
            self.assertEqual(self.bench._turns_in(missing), 0)
            missing.write_text('{"a": 1}\n\n{"b": 2}\n', encoding="utf-8")
            self.assertEqual(self.bench._turns_in(missing), 2)


def _help(bench) -> str:
    """The runner's --help text, without exiting the test process."""
    import contextlib

    out = io.StringIO()
    argv, sys.argv = sys.argv, ["bench.py", "--help"]
    try:
        with contextlib.redirect_stdout(out), contextlib.suppress(SystemExit):
            bench.main()
    finally:
        sys.argv = argv
    return out.getvalue()


class SayingWhatTheSampleResolvesTest(unittest.TestCase):
    """"A gap smaller than the spread above is noise" was not enough.

    In one night four readings were made or nearly made off gaps inside
    that spread — a partial 3 of 9 read as a regression caused by a
    change that finished 10 of 20 against a control of 10 of 20, and an
    11-against-8 read as one model beating another. The runner knows the
    number. It should say it.
    """

    def setUp(self) -> None:
        self.bench = _bench()

    def test_the_floor_is_the_spread_of_identical_runs(self) -> None:
        self.assertEqual(self.bench.noise_floor([10, 7, 9, 8, 10]), 3)

    def test_a_steady_sample_resolves_a_single_case(self) -> None:
        self.assertEqual(self.bench.noise_floor([4, 4, 4]), 0)

    def test_no_passes_is_not_a_crash(self) -> None:
        self.assertEqual(self.bench.noise_floor([]), 0)

    def test_the_report_states_the_number(self) -> None:
        rows = _rows({"a": "YnY", "b": "nnY"})
        out = io.StringIO()
        with redirect_stderr(out):
            self.bench.report(rows, 3)
        text = " ".join(out.getvalue().split())
        self.assertIn("resolves a gap of", text)
        self.assertIn("must not be reported as a result", text)

    def test_it_does_not_claim_more_than_the_spread(self) -> None:
        """Totals of 2, 0, 2 move by two, so two is noise and three is not."""
        rows = _rows({"a": "YnY", "b": "YnY"})
        out = io.StringIO()
        with redirect_stderr(out):
            self.bench.report(rows, 3)
        self.assertIn("gap of 3 case(s) or more", " ".join(out.getvalue().split()))


class TierSevenSaysItLikeAPersonTest(unittest.TestCase):
    """Tier 7 exists so a decider that reads meaning can be told apart
    from one that reads keywords. That only holds if its tasks carry no
    keyword, and if the fixture really is broken the way the task says."""

    def setUp(self) -> None:
        self.bench = _bench()
        self.seven = [c for c in self.bench.CASES if c.tier == 7]
        self.assertTrue(self.seven, "tier 7 has no cases")

    def test_no_tier_seven_task_uses_a_word_the_regex_keys_on(self) -> None:
        sys.path.insert(0, str(ROOT / "src"))
        from harness import task as T

        for case in self.seven:
            T.set_decided_intent(case.task, None)
            self.assertFalse(
                T.looks_like_bugfix(case.task),
                f"{case.key}: the regex already sees a fix in {case.task!r}, "
                "so this case cannot separate the two deciders",
            )

    def test_every_tier_seven_fixture_fails_its_own_check_before_any_fix(self) -> None:
        import subprocess
        import tempfile

        for case in self.seven:
            with tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp)
                for rel, body in {**self.bench.BASE, **case.files}.items():
                    (project / rel).parent.mkdir(parents=True, exist_ok=True)
                    (project / rel).write_text(body, encoding="utf-8")
                proc = subprocess.run(
                    [sys.executable, "-c", self.bench.LOADER + case.check],
                    cwd=project, capture_output=True, text=True, timeout=60, check=False,
                )
                self.assertNotEqual(
                    proc.returncode, 0,
                    f"{case.key}: the check passes on the unfixed fixture, so the "
                    "case measures nothing",
                )

    def test_tier_seven_is_the_same_bugs_as_tier_five(self) -> None:
        """A symptom-phrased case must be answerable by the same fix as a
        keyword-phrased one, or a gap between tiers is a gap in difficulty."""
        five = {c.key: c for c in self.bench.CASES if c.tier == 5}
        pairs = {"said-nameerror": "fix-nameerror", "said-offbyone": "fix-offbyone"}
        for seven_key, five_key in pairs.items():
            seven = next(c for c in self.seven if c.key == seven_key)
            self.assertEqual(seven.files, five[five_key].files, f"{seven_key} fixture drifted")
            self.assertEqual(seven.check, five[five_key].check, f"{seven_key} check drifted")

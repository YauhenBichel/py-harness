from pathlib import Path
import unittest
import tempfile
from types import SimpleNamespace

from harness.act.parse import AgentTurn
from harness.agent.loop import Agent
from harness.agent.options import AgentOptions
from harness.agent.policy import LoopState, refuse_before
from harness.guard.loop_guard import LoopGuard


class LoopGuardTest(unittest.TestCase):
    def test_first_explore_passes(self) -> None:
        self.assertEqual(LoopGuard().check(AgentTurn(action="grep", query="total")), "")

    def test_same_grep_twice_is_refused(self) -> None:
        guard = LoopGuard()
        turn = AgentTurn(action="grep", query="total")
        self.assertEqual(guard.check(turn), "")
        blocked = guard.check(turn)
        self.assertIn("already ran that exact grep", blocked)
        self.assertIn("Action: read", blocked)

    def test_different_query_passes(self) -> None:
        guard = LoopGuard()
        guard.check(AgentTurn(action="grep", query="total"))
        self.assertEqual(guard.check(AgentTurn(action="grep", query="other")), "")

    def test_rerunning_tests_after_a_patch_is_progress(self) -> None:
        guard = LoopGuard()
        turn = AgentTurn(action="run", argv=("-m", "unittest"))
        self.assertEqual(guard.check(turn), "")
        self.assertEqual(guard.check(turn), "")

    def test_same_patch_body_is_allowed_across_paths(self) -> None:
        guard = LoopGuard()
        first = AgentTurn(action="patch", path="a.py", append="value = 1")
        repeated = AgentTurn(action="patch", path="b.py", append="value = 1")
        self.assertEqual(guard.check(first), "")
        self.assertEqual(guard.check(repeated), "")

    def test_repeated_patch_names_the_actual_result(self) -> None:
        guard = LoopGuard()
        turn = AgentTurn(action="patch", path="a.py", append="value = 1")
        self.assertEqual(guard.check(turn), "")
        guard.remember_patch_result(turn, "applied")
        self.assertIn("It was applied", guard.check(turn))

    def test_a_different_patch_body_passes(self) -> None:
        guard = LoopGuard()
        guard.check(AgentTurn(action="patch", path="a.py", append="value = 1"))
        self.assertEqual(
            guard.check(AgentTurn(action="patch", path="a.py", append="value = 2")),
            "",
        )

    def test_a_policy_refused_patch_is_still_remembered(self) -> None:
        state = LoopState(task="change app.py", project=Path("."), allow_writes=False)
        patch = AgentTurn(action="patch", path="app.py", append="value = 1")
        self.assertIn("read-only", refuse_before(state, patch).lower())
        self.assertIn("It was refused", refuse_before(state, patch))

    def test_read_prerequisite_allows_the_requested_patch_retry(self) -> None:
        state = LoopState(task="fix the bug in total in src/orders.py", project=Path("."))
        patch = AgentTurn(
            action="patch",
            path="src/orders.py",
            find="    return 0",
            replace="    return sum(prices)",
        )
        self.assertIn("Action: read", refuse_before(state, patch))
        state.files_seen.add("src/orders.py")
        self.assertEqual(refuse_before(state, patch), "")

    def test_same_body_without_a_path_is_two_files(self) -> None:
        # A patch with no Path lands on the last file read. The same import line
        # added to two files in turn is ordinary work, not a repeat.
        guard = LoopGuard()
        turn = AgentTurn(action="patch", append="from __future__ import annotations")
        self.assertEqual(guard.check(turn, path="src/a.py"), "")
        self.assertEqual(guard.check(turn, path="src/b.py"), "")

    def test_same_body_on_the_same_resolved_path_is_refused(self) -> None:
        guard = LoopGuard()
        turn = AgentTurn(action="patch", append="from __future__ import annotations")
        self.assertEqual(guard.check(turn, path="src/a.py"), "")
        self.assertIn("already proposed that exact patch", guard.check(turn, path="src/a.py"))

    def test_pathless_patch_follows_the_file_last_read(self) -> None:
        state = LoopState(task="fix the bug in total in src/orders.py", project=Path("."))
        state.files_seen.update({"src/a.py", "src/b.py"})
        patch = AgentTurn(action="patch", find="    return 0", replace="    return 1")

        state.last_path = "src/a.py"
        self.assertEqual(refuse_before(state, patch), "")
        state.last_path = "src/b.py"
        self.assertEqual(refuse_before(state, patch), "")
        state.last_path = "src/a.py"
        self.assertIn("already proposed that exact patch", refuse_before(state, patch))

    def test_mechanical_fix_refusal_records_the_actual_result(self) -> None:
        state = LoopState(task="change app.py", project=Path("."), autofixed=True)
        patch = AgentTurn(action="patch", path="app.py", append="value = 1")
        self.assertIn("mechanical fix", refuse_before(state, patch))
        self.assertIn("It was refused", refuse_before(state, patch))

    def test_raised_patch_error_records_a_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("value = 1\n", encoding="utf-8")
            options = AgentOptions(project=root, task="change app.py")
            agent = Agent(options)
            state = LoopState(task=options.task, project=root, last_path="app.py")
            run = SimpleNamespace(options=options, preamble=SimpleNamespace(target=None), writes=[])
            patch = AgentTurn(action="patch", append="oops(\n")
            self.assertEqual(refuse_before(state, patch), "")
            self.assertTrue(agent._carry_out(patch, state, run))
            self.assertEqual((root / "app.py").read_text(), "value = 1\n")
            self.assertIn("It was refused", refuse_before(state, patch))

    def test_pathless_patches_record_applied_results_on_each_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("a.py", "b.py"):
                (root / name).write_text("def value():\n    return 1\n\ndef other():\n    return 2\n", encoding="utf-8")
            options = AgentOptions(project=root, task="update modules")
            agent = Agent(options)
            state = LoopState(task=options.task, project=root)
            run = SimpleNamespace(options=options, preamble=SimpleNamespace(target=None), writes=[])
            patch = AgentTurn(action="patch", append="extra = 2\n")
            for name in ("a.py", "b.py"):
                read = AgentTurn(action="read", path=name)
                self.assertEqual(refuse_before(state, read), "")
                agent._carry_out(read, state, run)
                self.assertEqual(refuse_before(state, patch), "")
                result = agent._carry_out(patch, state, run)
                self.assertTrue(result.startswith(("patched", "wrote")), result)
                self.assertEqual((root / name).read_text().count("extra = 2"), 1)
                self.assertIn("It was applied", refuse_before(state, patch))
            state.last_path = "a.py"
            self.assertIn("It was applied", refuse_before(state, patch))

    def test_none_turn(self) -> None:
        self.assertEqual(LoopGuard().check(None), "")


class ARepeatHearsTheRefusalAgainTest(unittest.TestCase):
    """Every refusal in the loop names the one right next step. The guard
    used to replace it on the retry with "take a different action", which
    is the moment that step is needed most. Three cases, checked on the
    merged tree on 2026-09-27."""

    def test_read_only_retry_still_says_done(self) -> None:
        state = LoopState(task="change app.py", project=Path("."), allow_writes=False)
        patch = AgentTurn(action="patch", path="app.py", append="value = 1")
        first = refuse_before(state, patch)
        second = refuse_before(state, patch)
        self.assertIn("read-only", first)
        self.assertIn("already proposed that exact patch", second)
        self.assertIn("It was refused: This run is read-only", second)
        self.assertIn("Action: done", second)

    def test_wrong_file_retry_still_names_the_right_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / "src" / "orders.py").write_text("def total(p):\n    return 0\n")
            (root / "src" / "other.py").write_text("x = 1\n")
            state = LoopState(
                task="fix total in src/orders.py so it sums", project=root,
                located_path="src/orders.py",
            )
            state.files_seen.update({"src/orders.py", "src/other.py"})
            patch = AgentTurn(action="patch", path="src/other.py", find="x = 1", replace="x = 2")
            first = refuse_before(state, patch)
            second = refuse_before(state, patch)
        self.assertIn("Action: patch Path: src/orders.py", first)
        self.assertIn("already proposed that exact patch", second)
        self.assertIn("Action: patch Path: src/orders.py", second)

    def test_find_miss_retry_still_shows_the_closest_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / "src" / "orders.py").write_text("TAX = 0.2\n")
            options = AgentOptions(project=root, task="fix TAX in src/orders.py")
            agent = Agent(options)
            state = LoopState(
                task=options.task, project=root, located_path="src/orders.py",
                files_seen={"src/orders.py"},
            )
            run = SimpleNamespace(options=options, preamble=SimpleNamespace(target=None), writes=[])
            patch = AgentTurn(action="patch", path="src/orders.py", find="TAX = 0.02", replace="TAX = 0.2")
            self.assertEqual(refuse_before(state, patch), "")
            result = agent._carry_out(patch, state, run)
            second = refuse_before(state, patch)
        self.assertIn("string not in file", result)
        self.assertIn("already proposed that exact patch", second)
        self.assertIn("TAX = 0.2", second)
        self.assertIn("copy one whole line", second)

    def test_an_applied_patch_keeps_the_short_wording(self) -> None:
        guard = LoopGuard()
        turn = AgentTurn(action="patch", path="a.py", append="value = 1")
        guard.check(turn)
        guard.remember_patch_result(turn, "applied")
        self.assertIn("It was applied; repeating it will not help", guard.check(turn))


if __name__ == "__main__":
    unittest.main()

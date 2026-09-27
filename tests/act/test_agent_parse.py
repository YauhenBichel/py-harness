import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from harness.act.parse import parse_turn, parse_turn_smart


class AgentParseTest(unittest.TestCase):
    def test_grep(self) -> None:
        turn = parse_turn("Action: grep\nQuery: def main")
        self.assertIsNotNone(turn)
        self.assertEqual(turn.action, "grep")
        self.assertEqual(turn.query, "def main")

    def test_edit_with_fence(self) -> None:
        turn = parse_turn(
            "Action: edit\nPath: src/foo.py\n```python\nprint(1)\n```\n"
        )
        self.assertEqual(turn.action, "edit")
        self.assertEqual(turn.path, "src/foo.py")
        self.assertEqual(turn.source, "print(1)")

    def test_patch_append(self) -> None:
        turn = parse_turn(
            "Action: patch\nPath: pkg/mathy.py\nAppend:\n"
            "def multiply(a: int, b: int) -> int:\n    return a * b\n"
        )
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.action, "patch")
        self.assertIn("def multiply", turn.append)
        self.assertIn("return a * b", turn.append)

    def test_patch(self) -> None:
        turn = parse_turn(
            "Action: patch\nPath: pkg/util_stats.py\nFind: return tota\n"
            "Replace: return sum(cleaned)\n"
        )
        self.assertEqual(turn.action, "patch")
        self.assertEqual(turn.find, "return tota")
        self.assertEqual(turn.replace, "return sum(cleaned)")

    def test_done(self) -> None:
        turn = parse_turn("Action: done\nSummary: nothing to fix")
        self.assertEqual(turn.action, "done")
        self.assertIn("nothing", turn.summary)

    def test_map_and_plan(self) -> None:
        mapped = parse_turn("Action: map\nScope: src/harness")
        self.assertIsNotNone(mapped)
        assert mapped is not None
        self.assertEqual(mapped.action, "map")
        self.assertEqual(mapped.scope, "src/harness")
        plan = parse_turn("Action: plan\nSummary: read then patch")
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertEqual(plan.action, "plan")
        self.assertEqual(plan.summary, "read then patch")

    def test_smart_prefers_patch_in_a_menu_dump(self) -> None:
        draft = (
            "Action: skill\nName: add-feature\n\n"
            "Action: patch\nPath: pkg/mathy.py\nAppend:\n"
            "def multiply(a: int, b: int) -> int:\n    return a * b\n"
        )
        turn = parse_turn_smart(draft)
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.action, "patch")
        self.assertIn("def multiply", turn.append)
        q = parse_turn_smart(
            "Action: patch\nPath: x.py\nAppend:\nz\n\nAction: done\nSummary: empty draft\n",
            question=True,
        )
        assert q is not None
        self.assertEqual(q.action, "done")

    def test_edit_append_is_source(self) -> None:
        turn = parse_turn(
            "Action: edit\nPath: pkg/__init__.py\n"
            'Append:\n"""Public exports only."""\n'
        )
        assert turn is not None
        self.assertEqual(turn.action, "edit")
        self.assertIn("Public exports", turn.source or "")

    def test_file_alias_is_path(self) -> None:
        turn = parse_turn("Action: read\nFile: src/harness/http.py")
        self.assertIsNotNone(turn)
        assert turn is not None
        self.assertEqual(turn.action, "read")
        self.assertEqual(turn.path, "src/harness/http.py")

    def test_issue_and_pr_fields(self) -> None:
        issue = parse_turn("Action: issue\nNumber: 50")
        assert issue is not None
        self.assertEqual(issue.action, "issue")
        self.assertEqual(issue.number, "50")
        pr = parse_turn(
            "Action: pr\nTitle: After locate, questions must Action: done\n"
            "Body: Closes #50\n"
        )
        assert pr is not None
        self.assertEqual(pr.action, "pr")
        self.assertIn("locate", pr.title)
        self.assertIn("Closes", pr.body)

    def test_unparsed(self) -> None:
        self.assertIsNone(parse_turn("no issues"))


class FieldNameAsActionTest(unittest.TestCase):
    """A field name on the Action line means the action it belongs to.

    Watched a run spend five of ten turns on this: `Action: patch` with no
    body, then `Action: append` carrying the body, then the same again,
    then `Action: find`. Each of the field-name turns was answered with
    "unknown Action" and thrown away.
    """

    def test_append_carries_its_body_into_a_patch(self) -> None:
        turn = parse_turn(
            "Action: append\nPath: src/orders.py\n"
            "def initials(name):\n    return name\n"
        )
        self.assertEqual(turn.action, "patch")
        self.assertEqual(turn.path, "src/orders.py")
        self.assertIn("def initials", turn.append)

    def test_find_becomes_a_patch(self) -> None:
        turn = parse_turn(
            "Action: find\nPath: src/o.py\nFind: return sum(x)\nReplace: return 0\n"
        )
        self.assertEqual(turn.action, "patch")
        self.assertEqual(turn.find, "return sum(x)")
        self.assertEqual(turn.replace, "return 0")

    def test_summary_becomes_done(self) -> None:
        turn = parse_turn("Action: summary\nSummary: it returns int\n")
        self.assertEqual(turn.action, "done")
        self.assertEqual(turn.summary, "it returns int")

    def test_a_real_patch_is_untouched(self) -> None:
        turn = parse_turn("Action: patch\nPath: src/o.py\nAppend:\ndef f():\n    pass\n")
        self.assertEqual(turn.action, "patch")
        self.assertEqual(turn.append, "def f():\n    pass")

    def test_a_known_action_is_never_remapped(self) -> None:
        for verb in ("read", "grep", "run", "done", "edit"):
            turn = parse_turn(f"Action: {verb}\nPath: src/o.py\n")
            self.assertEqual(turn.action, verb)


class DoneWinsOnceAskedForTest(unittest.TestCase):
    PASTED = (
        "Action: patch\nPath: src/orders.py\nFind: TAX = 0.02\nReplace: TAX = 0.2\n\n"
        "Action: run\nArgv: -m unittest discover -s tests -q\n\n"
        "Action: done\nSummary: fixed the tax rate\n"
    )

    def test_the_patch_wins_by_default(self) -> None:
        self.assertEqual(parse_turn_smart(self.PASTED).action, "patch")

    def test_done_wins_once_the_harness_asked_for_it(self) -> None:
        turn = parse_turn_smart(self.PASTED, asked_done=True)
        self.assertEqual(turn.action, "done")
        self.assertEqual(turn.summary, "fixed the tax rate")

    def test_asking_for_done_does_not_invent_one(self) -> None:
        single = "Action: read\nPath: src/orders.py\n"
        self.assertEqual(parse_turn_smart(single, asked_done=True).action, "read")


class ADiffIsAPatchTest(unittest.TestCase):
    """A 7B answered "Action: patch" with a fenced unified diff, correct
    and complete, and heard "patch needs Find: or Append:" ten times."""

    DIFF = (
        "Action: patch\n```diff\n"
        "diff --git a/src/orders.py b/src/orders.py\n"
        "--- a/src/orders.py\n+++ b/src/orders.py\n"
        "@@ -5,7 +5,7 @@ def last_price(prices: list[int]) -> int:\n"
        "-    return prices[len(prices)]\n"
        "+    return prices[-1]\n"
        "```\n"
    )

    def test_removed_and_added_lines_are_find_and_replace(self) -> None:
        turn = parse_turn_smart(self.DIFF)
        self.assertEqual(turn.action, "patch")
        self.assertEqual(turn.find, "    return prices[len(prices)]")
        self.assertEqual(turn.replace, "    return prices[-1]")

    def test_the_path_comes_from_the_header_when_none_is_given(self) -> None:
        self.assertEqual(parse_turn_smart(self.DIFF).path, "src/orders.py")

    def test_a_given_path_wins_over_the_header(self) -> None:
        turn = parse_turn_smart(self.DIFF.replace("Action: patch\n", "Action: patch\nPath: pkg/o.py\n"))
        self.assertEqual(turn.path, "pkg/o.py")

    def test_context_lines_are_trimmed_so_the_find_is_the_changed_lines(self) -> None:
        diff = (
            "Action: patch\n```diff\n--- a/x.py\n+++ b/x.py\n@@ -1,3 +1,3 @@\n"
            " def f():\n-    return 1\n+    return 2\n \n```\n"
        )
        turn = parse_turn_smart(diff)
        self.assertEqual(turn.find, "    return 1")
        self.assertEqual(turn.replace, "    return 2")

    def test_an_addition_only_hunk_is_an_append(self) -> None:
        diff = "Action: patch\n```diff\n--- a/x.py\n+++ b/x.py\n@@ -3,0 +4,2 @@\n+def g():\n+    return 3\n```\n"
        turn = parse_turn_smart(diff)
        self.assertEqual(turn.find, "")
        self.assertEqual(turn.append, "def g():\n    return 3")

    def test_explicit_fields_are_left_alone(self) -> None:
        turn = parse_turn_smart("Action: patch\nPath: a.py\nFind: x = 1\nReplace: x = 2\n")
        self.assertEqual((turn.find, turn.replace), ("x = 1", "x = 2"))


class AJsonObjectIsATurnTest(unittest.TestCase):
    """The same 7B, on another run, answered every turn as ```json``` with
    an "action" key, once with single-quoted values, and parsed to nothing
    ten times."""

    def test_valid_json_patch(self) -> None:
        turn = parse_turn_smart(
            '```json\n{"action": "patch", "path": "src/orders.py", "find": "TAX = 0.02", "replace": "TAX = 0.2"}\n```'
        )
        self.assertEqual(turn.action, "patch")
        self.assertEqual(turn.path, "src/orders.py")
        self.assertEqual((turn.find, turn.replace), ("TAX = 0.02", "TAX = 0.2"))

    def test_single_quoted_values_still_read(self) -> None:
        turn = parse_turn_smart(
            "```json\n{\n  \"action\": \"patch\",\n  \"path\": \"src/orders.py\",\n"
            "  \"find\": 'return subtotal + (subtotal * TAX)',\n  \"replace\": 'return subtotal * 1.2'\n}\n```"
        )
        self.assertEqual(turn.action, "patch")
        self.assertEqual(turn.find, "return subtotal + (subtotal * TAX)")

    def test_read_and_run(self) -> None:
        self.assertEqual(parse_turn_smart('{"action": "read", "path": "src/orders.py"}').path, "src/orders.py")
        run = parse_turn_smart('{"action": "run", "argv": ["-m", "unittest", "discover", "-s", "tests", "-q"]}')
        self.assertEqual(run.argv, ("-m", "unittest", "discover", "-s", "tests", "-q"))

    def test_an_edit_carries_its_source(self) -> None:
        turn = parse_turn_smart('{"action": "edit", "path": "a.py", "content": "x = 1\\n"}')
        self.assertEqual(turn.source, "x = 1\n")

    def test_braces_in_prose_are_not_a_turn(self) -> None:
        self.assertIsNone(parse_turn_smart("I would use a dict like {'a': 1} here."))
        self.assertIsNone(parse_turn_smart('{"action": "start_line", "path": "x"}'))

    def test_an_action_line_still_wins(self) -> None:
        turn = parse_turn_smart('Action: read\nPath: a.py\n{"action": "done"}')
        self.assertEqual(turn.action, "read")


class ABareDiffIsAPatchTest(unittest.TestCase):
    """The next run sent the diff with no Action line at all, ten times."""

    BARE = (
        "```diff\ndiff --git a/src/orders.py b/src/orders.py\n"
        "--- a/src/orders.py\n+++ b/src/orders.py\n"
        "@@ -2,5 +2,5 @@ Order arithmetic.\"\"\"\n \n"
        " def compute_total(prices: list[int]) -> int:\n"
        "-    return sum(prices) - 1\n+    return sum(prices)\n```\n"
    )

    def test_a_diff_alone_is_a_patch_to_its_file(self) -> None:
        turn = parse_turn_smart(self.BARE)
        self.assertIsNotNone(turn)
        self.assertEqual(turn.action, "patch")
        self.assertEqual(turn.path, "src/orders.py")
        self.assertEqual(turn.find, "    return sum(prices) - 1")
        self.assertEqual(turn.replace, "    return sum(prices)")

    def test_a_diff_with_no_hunk_is_not_a_turn(self) -> None:
        self.assertIsNone(parse_turn_smart("--- a/x.py\n+++ b/x.py\n"))

    def test_a_diff_with_no_path_is_not_a_turn(self) -> None:
        self.assertIsNone(parse_turn_smart("@@ -1 +1 @@\n-a\n+b\n"))


if __name__ == "__main__":
    unittest.main()

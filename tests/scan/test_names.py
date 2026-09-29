"""Compiler-style undefined-name oracle. No model."""

import tempfile
import unittest
from pathlib import Path

from harness.act.tools import edit_py, patch_py
from harness.scan.names import new_undefined, undefined_names
from harness.skillkit.refuse_change import (
    refuse_rename_incomplete,
    refuse_test_in_impl,
    refuse_undefined_draft,
)
from harness.skillkit.refuse_finish import refuse_done_oracle



ORDERS = '''TAX_RATE = 0.2

def compute_total(prices: list[int]) -> int:
    return sum(prices)

def total_with_tax(prices: list[int]) -> float:
    subtotal = compute_total(prices)
    return subtotl + (subtotl * TAX_RATE)
'''

FIXED = ORDERS.replace("subtotl", "subtotal")


class UndefinedNamesTest(unittest.TestCase):
    def test_planted_typo_is_found(self) -> None:
        self.assertIn("subtotl", undefined_names(ORDERS))

    def test_fixed_file_is_clean(self) -> None:
        self.assertEqual(undefined_names(FIXED), [])

    def test_adding_a_function_does_not_count_the_old_typo(self) -> None:
        draft = FIXED.replace(
            "return subtotal + (subtotal * TAX_RATE)\n",
            "return subtotal + (subtotal * TAX_RATE)\n\n"
            "def total_lines(prices: list[int]) -> int:\n    return len(prices)\n",
        )
        # original still has the typo; draft is clean — not "new" undefined
        self.assertEqual(new_undefined(ORDERS, draft), [])

    def test_a_new_typo_is_new_undefined(self) -> None:
        draft = FIXED + (
            "\ndef total_lines(prices: list[int]) -> int:\n    return lenght\n"
        )
        self.assertIn("lenght", new_undefined(FIXED, draft))


class StyleOracleTest(unittest.TestCase):
    def test_test_in_impl_is_refused(self) -> None:
        draft = ORDERS + "\ndef test_apply_discount_reduces_the_total(self) -> None:\n    pass\n"
        self.assertIn("tests/", refuse_test_in_impl("src/orders.py", draft))
        self.assertEqual(
            refuse_test_in_impl("tests/test_orders.py", draft),
            "",
        )

    def test_bugfix_cannot_leave_the_typo(self) -> None:
        self.assertIn(
            "subtotl",
            refuse_undefined_draft(
                "find a real NameError in src/orders.py and fix it",
                "src/orders.py",
                ORDERS,
                ORDERS + "\n# note\n",
            ),
        )
        self.assertEqual(
            refuse_undefined_draft(
                "find a real NameError in src/orders.py and fix it",
                "src/orders.py",
                ORDERS,
                FIXED,
            ),
            "",
        )

    def test_rename_must_change_the_def(self) -> None:
        body = "def calc(left: int, right: int) -> int:\n    return left * right\n"
        self.assertIn(
            "still defines calc",
            refuse_rename_incomplete("rename calc to multiply", "src/util.py", body),
        )
        self.assertEqual(
            refuse_rename_incomplete(
                "rename calc to multiply",
                "src/util.py",
                body.replace("calc", "multiply"),
            ),
            "",
        )

    def test_done_oracle_sees_the_named_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (src / "orders.py").write_text(ORDERS, encoding="utf-8")
            self.assertIn(
                "subtotl",
                refuse_done_oracle(
                    "find a real NameError in src/orders.py and fix it",
                    root,
                    "src/orders.py",
                ),
            )
            (src / "orders.py").write_text(FIXED, encoding="utf-8")
            self.assertEqual(
                refuse_done_oracle(
                    "find a real NameError in src/orders.py and fix it",
                    root,
                    "src/orders.py",
                ),
                "",
            )

    def test_write_tests_done_requires_the_named_function(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "tests").mkdir()
            (root / "src" / "orders.py").write_text(FIXED, encoding="utf-8")
            (root / "tests" / "test_orders.py").write_text(
                "import unittest\n\n\n"
                "class TestOrders(unittest.TestCase):\n"
                "    def test_compute_total_sums_the_prices(self) -> None:\n"
                "        pass\n",
                encoding="utf-8",
            )
            task = "write tests for apply_discount in src/orders.py"
            self.assertIn(
                "apply_discount",
                refuse_done_oracle(task, root, "src/orders.py"),
            )
            (root / "tests" / "test_orders.py").write_text(
                "import unittest\n\n\n"
                "class TestOrders(unittest.TestCase):\n"
                "    def test_apply_discount_reduces_the_total(self) -> None:\n"
                "        got = apply_discount(10, 0.2)\n",
                encoding="utf-8",
            )
            self.assertEqual(refuse_done_oracle(task, root, "src/orders.py"), "")

    def test_patch_refuses_a_test_in_the_impl_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "src" / "orders.py"
            path.parent.mkdir()
            path.write_text(FIXED, encoding="utf-8")
            blocked = patch_py(
                root,
                "src/orders.py",
                "",
                "",
                append="    def test_apply_discount_reduces_the_total(self) -> None:\n        pass\n",
                task="write tests for apply_discount in src/orders.py",
            )
        self.assertIn("tests/", blocked)


class MethodsAreScannedTest(unittest.TestCase):
    """Every unittest test is a method, and methods were never scanned.

    Seen in an editor session: the model wrote the function into one file
    and a test calling it into another, without the import. The scan saw
    nothing, the write was allowed, and the suite went red.
    """

    TEST_FILE = (
        "import unittest\n\n"
        "from src.orders import compute_total\n\n\n"
        "class TestOrders(unittest.TestCase):\n"
        "    def test_compute_total_sums(self) -> None:\n"
        "        self.assertEqual(compute_total([1, 2]), 3)\n\n"
        "    def test_total_lines_counts(self) -> None:\n"
        "        got = total_lines([1, 2, 3])\n"
        "        self.assertEqual(got, 3)\n"
    )

    def test_a_method_calling_an_unimported_name_is_found(self) -> None:
        self.assertIn("total_lines", undefined_names(self.TEST_FILE))

    def test_an_imported_name_is_not_flagged(self) -> None:
        self.assertNotIn("compute_total", undefined_names(self.TEST_FILE))

    def test_self_is_not_flagged(self) -> None:
        self.assertNotIn("self", undefined_names(self.TEST_FILE))

    def test_a_class_attribute_is_bound_for_its_methods(self) -> None:
        source = (
            "class Thing:\n"
            "    LIMIT = 3\n\n"
            "    def check(self) -> bool:\n"
            "        return LIMIT > 1\n"
        )
        self.assertEqual(undefined_names(source), [])


class NoFalsePositivesTest(unittest.TestCase):
    """A guard that blocks good code is worse than the bug it catches.

    Scanning methods found sixteen names in this project's own source that
    are perfectly well bound: comprehension variables, parameters of nested
    functions and lambdas, and module dunders.
    """

    ROOT = Path(__file__).resolve().parents[2]

    def test_this_project_has_no_undefined_names(self) -> None:
        flagged = []
        for path in sorted((self.ROOT / "src").rglob("*.py")):
            names = undefined_names(path.read_text(encoding="utf-8"))
            if names:
                flagged.append(f"{path.relative_to(self.ROOT)}: {names[:3]}")
        self.assertEqual(flagged, [])

    def test_a_nested_function_parameter_is_bound(self) -> None:
        source = (
            "def outer():\n"
            "    def inner(text: str) -> str:\n"
            "        return text.upper()\n"
            "    return inner\n"
        )
        self.assertEqual(undefined_names(source), [])

    def test_a_lambda_parameter_is_bound(self) -> None:
        source = "def outer():\n    return sorted([], key=lambda item: item.name)\n"
        self.assertEqual(undefined_names(source), [])

    def test_a_module_dunder_is_bound(self) -> None:
        source = "from pathlib import Path\n\n\ndef here():\n    return Path(__file__).parent\n"
        self.assertEqual(undefined_names(source), [])


class MissingImportTargetTest(unittest.TestCase):
    """A test importing a function nobody has written yet reads as valid.

    The import binds the name, so the undefined-name scan sees nothing, and
    the failure only appears when the suite runs. Asked to create a module
    and a test for it, the model wrote the test alone four times out of
    four.
    """

    def _project(self, tmp: str) -> Path:
        root = Path(tmp)
        (root / "src").mkdir()
        (root / "src" / "__init__.py").write_text("", encoding="utf-8")
        (root / "src" / "orders.py").write_text(
            "def compute_total(prices):\n    return sum(prices)\n", encoding="utf-8"
        )
        return root

    def test_a_name_the_module_does_not_define_is_found(self) -> None:
        from harness.scan.names import missing_import_targets

        with tempfile.TemporaryDirectory() as tmp:
            got = missing_import_targets(
                self._project(tmp), "from src.orders import slugify\n"
            )
        self.assertEqual(got, [("src.orders", "slugify")])

    def test_a_name_it_does_define_is_fine(self) -> None:
        from harness.scan.names import missing_import_targets

        with tempfile.TemporaryDirectory() as tmp:
            got = missing_import_targets(
                self._project(tmp), "from src.orders import compute_total\n"
            )
        self.assertEqual(got, [])

    def test_an_import_from_outside_the_project_is_left_alone(self) -> None:
        from harness.scan.names import missing_import_targets

        with tempfile.TemporaryDirectory() as tmp:
            got = missing_import_targets(
                self._project(tmp), "from pathlib import Path\nimport unittest\n"
            )
        self.assertEqual(got, [])

    def test_the_write_is_refused_and_the_file_is_not_created(self) -> None:
        from harness.act.tools import edit_py

        with tempfile.TemporaryDirectory() as tmp:
            project = self._project(tmp)
            (project / "tests").mkdir()
            out = edit_py(
                project,
                "tests/test_it.py",
                "import unittest\n\nfrom src.orders import slugify\n\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_slugify_lowercases(self) -> None:\n"
                "        got = slugify('A B')\n"
                "        self.assertEqual(got, 'a-b')\n",
                task="create a module with slugify and a unit test",
            )
            created = (project / "tests" / "test_it.py").exists()
        self.assertIn("does not define slugify", out)
        self.assertFalse(created)


class CoveredSymbolTest(unittest.TestCase):
    """A pronoun is not a function name."""

    def test_a_pronoun_is_not_a_symbol_to_cover(self) -> None:
        from harness.task import covered_symbol

        self.assertEqual(
            covered_symbol(
                "create a function slugify(text) and a unit test for it"
            ),
            "",
        )

    def test_a_real_name_still_is(self) -> None:
        from harness.task import covered_symbol

        self.assertEqual(
            covered_symbol("write tests for apply_discount in src/orders.py"),
            "apply_discount",
        )

    def test_creating_a_function_asks_for_the_feature_skill_first(self) -> None:
        from harness.skillkit.catalog import list_skills, pick_skills

        names = sorted(
            skill.name
            for skill in pick_skills(
                "create a new module with a function slugify(text) and a unit test for it",
                list_skills(),
            )
        )
        self.assertIn("add-feature", names)


if __name__ == "__main__":
    unittest.main()

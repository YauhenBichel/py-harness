"""Whether a run may say it is finished.

A different question from whether a change is acceptable. These look
at the project after the work, not at the draft before it: is the
symbol actually there, did a test run, does a test call what it was
asked to cover.
"""

from __future__ import annotations

# The oracle reuses one draft rule: a half-finished rename is a
# reason to refuse a finish as well as a draft.
from harness.skillkit.refuse_change import refuse_rename_incomplete

"""SoC / readable-name guards. Deterministic. No model."""
import ast
import re
from pathlib import Path
from harness.task import (
    looks_like_add_feature,
    looks_like_bugfix,
    looks_like_design_loop,
    covered_symbol,
    looks_like_everyday_code,
    looks_like_fix_smell,
    looks_like_write_tests,
    looks_like_app_loop,
    looks_like_app_overflow,
    looks_like_new_package,
    looks_like_refactor,
    question_symbol,
    rename_pair,
)


def _class_bases(node: ast.ClassDef) -> list[str]:
    """The names a class inherits from, as they are written."""
    names: list[str] = []
    for base in node.bases:
        if isinstance(base, ast.Name):
            names.append(base.id)
        elif isinstance(base, ast.Attribute):
            names.append(base.attr)
    return names


def _is_test_case(
    node: ast.ClassDef,
    classes: dict[str, ast.ClassDef],
    seen: frozenset[str] = frozenset(),
) -> bool:
    """True when `unittest discover` would collect this class.

    A class counts when it inherits from `unittest.TestCase`, however
    that is spelled, or from another class in the same file that does.
    A `test_` method anywhere else is never run, so it is not coverage.
    """
    for base in _class_bases(node):
        if base.endswith("TestCase"):
            return True
        parent = classes.get(base)
        if (
            parent is not None
            and base not in seen
            and _is_test_case(parent, classes, seen | {base})
        ):
            return True
    return False


def _test_cases(tree: ast.AST) -> list[ast.ClassDef]:
    """The `TestCase` subclasses a parsed file declares."""
    classes = {
        node.name: node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
    }
    return [node for node in classes.values() if _is_test_case(node, classes)]


def _mentions(node: ast.AST, symbol: str) -> bool:
    """True when `node` names `symbol` at all."""
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and child.id == symbol:
            return True
        if isinstance(child, ast.Attribute) and child.attr == symbol:
            return True
    return False


def _a_test_uses(body: str, symbol: str) -> bool:
    """True when a test method calls `symbol`.

    The method has to be one `unittest discover` would run: a method of
    a `TestCase` subclass. An 8B run, asked to cover `apply_discount`,
    wrote

        def test_apply_discount(self) -> None:
            from pricing import apply_discount
            got = apply_discount(100.0, 25.0)

    a test method with no class around it. It compiles, so nothing
    errors; discovery imports the file, finds no `TestCase` subclass,
    collects nothing and exits 0, and the run reported `done` over a
    suite that ran nothing. Asking only whether the name appears
    anywhere in the test files accepted a file holding one import line
    the same way. An import is not coverage, and neither is a method
    no runner will call.
    """
    if not body.strip() or not symbol:
        return False
    try:
        tree = ast.parse(body)
    except (SyntaxError, ValueError):
        # A file discovery cannot import is a file whose tests never
        # run, so nothing in it counts.
        return False
    for cls in _test_cases(tree):
        for node in cls.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test"):
                continue
            if _mentions(node, symbol):
                return True
    return False


def test_files(project: Path) -> list[Path]:
    """The files under tests/ that `unittest discover` would collect."""
    tests = Path(project) / "tests"
    if not tests.is_dir():
        return []
    return [path for path in sorted(tests.glob("test_*.py")) if path.is_file()]


def tests_call(project: Path, symbol: str) -> bool:
    """True when some test in tests/ actually calls symbol."""
    if not symbol:
        return False
    for path in test_files(project):
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if _a_test_uses(body, symbol):
            return True
    return False


def refuse_done_oracle(task: str, project: Path, last_path: str) -> str:
    """Refuse done when the named file or last write still has an unbound name."""
    from harness.scan.names import undefined_in_file
    from harness.task import named_project_file, rename_pair

    if looks_like_app_overflow(task):
        return ""

    paths: list[str] = []
    named = named_project_file(task, project)
    if named:
        paths.append(named)
    if last_path and last_path not in paths:
        paths.append(last_path)
    if looks_like_bugfix(task):
        for rel in paths:
            leftover = undefined_in_file(Path(project) / rel)
            if leftover:
                return (
                    f"undefined name {leftover[0]} in {rel}. "
                    f"Action: patch Path: {rel} Find: {leftover[0]} "
                    "Replace: the name you assigned."
                )
    if looks_like_add_feature(task):
        symbol = question_symbol(task)
        if symbol:
            found = False
            root = Path(project)
            from harness.scan.project_brief import iter_text_files

            for path, _size in iter_text_files(root):
                if path.suffix != ".py":
                    continue
                try:
                    body = path.read_text(encoding="utf-8")
                except OSError:
                    continue
                if re.search(rf"^def {re.escape(symbol)}\b", body, re.MULTILINE):
                    found = True
                    break
            if not found:
                from harness.skillkit.target import pick_module

                dest = pick_module(root, last_path, task)
                return (
                    f"def {symbol} is not in the project. "
                    f"Action: patch Path: {dest} Append: def {symbol}(...)."
                )
    if looks_like_write_tests(task):
        symbol = covered_symbol(task)
        if symbol and not tests_call(project, symbol):
            test_rel = "tests/test_module.py"
            if named:
                test_rel = f"tests/test_{Path(named).stem}.py"
            return (
                f"no test calls {symbol}. "
                f"Action: patch Path: {test_rel} "
                f"Append: one AAA test that calls {symbol}."
            )
    if looks_like_fix_smell(task) and named:
        old, new = rename_pair(task)
        try:
            body = (Path(project) / named).read_text(encoding="utf-8")
        except OSError:
            body = ""
        if old and new and body:
            missed = refuse_rename_incomplete(task, named, body)
            if missed:
                return missed
    return ""


def refuse_write_done(task: str, ran_tests: bool, *, wrote: bool = True) -> str:
    """Write tasks are not finished until a passing unittest has run.

    A task that has not written yet is handled by the empty-done refuse.
    New-package still needs a run even if the model claims it is done.
    """
    if ran_tests:
        return ""
    if looks_like_new_package(task):
        return "not done. Action: run Argv: -m unittest discover -s tests -q"
    if not wrote:
        return ""
    needs_run = (
        looks_like_add_feature(task)
        or looks_like_everyday_code(task)
        or looks_like_fix_smell(task)
        or looks_like_bugfix(task)
        or looks_like_refactor(task)
        or looks_like_design_loop(task)
    )
    if not needs_run:
        return ""
    return "not done. Action: run Argv: -m unittest discover -s tests -q"


def refuse_package_done(task: str, ran_tests: bool, wrote: bool = True) -> str:
    return refuse_write_done(task, ran_tests, wrote=wrote)


def refuse_app_done(task: str, project: Path) -> str:
    """Refuse done while list/show/http/mocked tests are still missing."""
    from harness.scan.app_spec import (
        next_app_action,
        next_overflow_action,
        render_app_review,
        required_gaps,
    )

    if looks_like_app_overflow(task):
        leftover = next_overflow_action(project, task)
        return ("not done. " + leftover.strip()) if leftover else ""
    if not looks_like_app_loop(task):
        return ""
    if required_gaps(project, task):
        return (
            "not done. "
            + next_app_action(project, task).strip()
            + "\n"
            + render_app_review(project, task)
        )
    return ""


# Names a framework calls, so nobody in this project has to.
_CALLED_BY_SOMETHING_ELSE = ("test", "_", "main")


def _added_functions(path: Path) -> list[str]:
    """Top-level functions this run put in the file that were not there.

    The original is on disk: every write leaves a `.bak` beside the file
    it changed. Without it there is no way to tell a function the run
    added from one that was already there, and refusing on the second
    would be refusing somebody else's code.
    """
    backup = path.with_suffix(path.suffix + ".bak")
    try:
        now = ast.parse(path.read_text(encoding="utf-8"))
        before = ast.parse(backup.read_text(encoding="utf-8"))
    except (SyntaxError, ValueError, OSError):
        return []
    was = {
        n.name for n in before.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    return [
        n.name for n in now.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name not in was
        and not n.name.startswith(_CALLED_BY_SOMETHING_ELSE)
    ]


def _anything_calls(project: Path, name: str, skip: Path) -> bool:
    """Does any other file in the project call this by name?"""
    called = re.compile(rf"\b{re.escape(name)}\s*\(")
    for path in project.rglob("*.py"):
        if path == skip or path.name.endswith(".bak") or ".git" in path.parts:
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if called.search(body) or _a_test_uses(body, name):
            return True
    return False


def refuse_unwired_addition(
    project: Path, last_path: str, task: str = ""
) -> str:
    """A function added, and nobody left to call it.

    Asked to add a check that refuses to send when a prompt carries a
    token, a run wrote `reject_github_tokens_in_prompt` and left nothing
    nothing. The file parsed and the suite stayed green, because a
    function nobody calls cannot fail. It also cannot work.

    Whether the body is any good needs a reader. Whether anything will
    ever run it does not, so that much is checked here.

    Overflow comment/pagination/config is a later typed run. The 8B
    writes ``def comment_on`` and the unused-function guard then
    burns the step budget. That cell is not this rule.
    """
    if looks_like_app_overflow(task):
        return ""
    if not last_path:
        return ""
    path = Path(project) / last_path
    for name in _added_functions(path):
        try:
            here = path.read_text(encoding="utf-8")
        except OSError:
            return ""
        if re.search(rf"\b{re.escape(name)}\s*\(", here.replace(f"def {name}(", "")):
            continue
        if _anything_calls(Path(project), name, path):
            continue
        return (
            f"`{name}` was added to {last_path} and nothing calls it. A "
            "function nobody calls cannot fail, and cannot work either. "
            "Action: patch the place that should use it, or write a test "
            "that calls it."
        )
    return ""

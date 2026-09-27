"""May this draft be written? One question, asked before any file changes.

The tools carry a change out. This decides whether it may happen: a
module that already exists under another name, an import with nothing
behind it, a style rule the project keeps, a definition already in the
file. Keeping it apart from `tools` means the answer to "where are the
tools" is one file, and so is the answer to "what stops a bad write".
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import ast
import re
from pathlib import Path

from harness.paths import rel_posix
from harness.skillkit.refuse_change import (
    refuse_add_opens_file,
    refuse_layout,
    refuse_opaque_module,
    refuse_opaque_names,
    refuse_ops_draft,
    refuse_platform_draft,
    refuse_dropped_definition,
    refuse_rename_incomplete,
    refuse_shell_fetch,
    refuse_stdlib_shadow,
    refuse_stub_body,
    refuse_self_at_module_level,
    refuse_test_in_impl,
    refuse_undefined_draft,
    refuse_weak_test,
)



_TEST_METH = re.compile(r"def\s+(test_\w+)\s*\(")
_ASSERT_CALL = re.compile(r"assertEqual\s*\(\s*([A-Za-z_]\w+)\s*\(")
_IMPORT_LINE = re.compile(r"^(from\s+\S+\s+import\s+)(.+)$")


def _add_import_symbol(text: str, name: str) -> str:
    if not name or name in {"self", "True", "False", "None"}:
        return text
    for line in text.splitlines():
        match = _IMPORT_LINE.match(line)
        if not match:
            continue
        imported = {part.strip() for part in match.group(2).split(",")}
        if name in imported:
            return text
        if any(skip in line for skip in ("unittest", "pathlib", "typing")):
            continue
        return text.replace(line, f"{match.group(1)}{match.group(2).rstrip()}, {name}", 1)
    return text


def _called_name(original: str, append: str) -> str:
    """The function the new test needs imported.

    It used to be read out of `assertEqual(multiply(...))`. The change rules
    ask for the opposite shape — `got = multiply(...)`, then assert `got` —
    so following them meant the import was never added and the suite broke.
    Reading the names the new test leaves unbound covers both shapes.
    """
    from harness.scan.names import new_undefined

    for name in new_undefined(original, original.rstrip() + "\n\n" + append):
        return name
    match = _ASSERT_CALL.search(append)
    return match.group(1) if match else ""


def _class_name_for(rel: str) -> str:
    """A TestCase name from the file it is going into.

    `tests/test_pricing.py` gives `TestPricing`, which is what this
    project's own test files are called. Naming it after the test method
    instead gave `TestApplyDiscountReturnsTotalMinusPercent`.
    """
    stem = Path(rel).stem.removeprefix("test_") if rel else ""
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", stem) if part]
    if not parts:
        return "Tests"
    return "Test" + "".join(part[:1].upper() + part[1:] for part in parts)


def _new_test_file(append: str, rel: str) -> str | None:
    """A whole test module around a bare test method. None if unsure.

    Asked to write tests for a function, an 8B answers with the method
    and not the class it belongs to — indented, because it knows it goes
    inside something, and it never writes the something. Appended to a
    file that does not exist yet, that is `unexpected indent` and no
    file at all. Four runs of four spent every step resending it.

    Supplying `class Test...(unittest.TestCase):` invents no behaviour:
    the assertions are the model's, and this is the scaffolding unittest
    requires in order to collect them.
    """
    lines = [line for line in append.strip("\n").splitlines() if line.strip()]
    if not lines:
        return None
    base = len(lines[0]) - len(lines[0].lstrip())
    body = "\n".join(
        line[base:] if len(line) >= base else line.lstrip()
        for line in append.strip("\n").splitlines()
    )
    try:
        ast.parse(body)
    except SyntaxError:
        return None
    if re.search(r"^class\s", body, re.MULTILINE):
        return None
    method = "    " + body.rstrip().replace("\n", "\n    ")
    name = _class_name_for(rel)
    return (
        "import unittest\n\n\n"
        f"class {name}(unittest.TestCase):\n{method}\n\n\n"
        'if __name__ == "__main__":\n    unittest.main()\n'
    )


def repair_unittest_append(original: str, append: str, rel: str = "") -> str | None:
    """8B Append: often lands after if __name__ and skips the import."""
    if "def test_" not in append:
        return None
    if not original.strip():
        # A test file that does not exist yet. There is no class to put
        # the method into, so the repair is to write the whole module.
        return _new_test_file(append, rel)
    if "TestCase" not in original and "unittest" not in original:
        return None
    meth = _TEST_METH.search(append)
    if not meth or re.search(rf"def\s+{re.escape(meth.group(1))}\s*\(", original):
        return None
    lines = append.strip("\n").splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return None
    base = len(lines[0]) - len(lines[0].lstrip())
    dedented = "\n".join(
        line[base:] if len(line) >= base else line.lstrip() for line in lines
    )
    method = "    " + dedented.replace("\n", "\n    ")
    text = _add_import_symbol(original, _called_name(original, append))
    marker = "\nif __name__"
    if marker in text:
        return text.replace(marker, "\n" + method + "\n" + marker, 1)
    return text.rstrip() + "\n\n" + method + "\n"


def refuse_duplicate_module(project: Path, rel: str, original: str) -> str:
    """Refuse a new file that repeats a module this project already has.

    Watched a run write the same function to `pkg/orders.py` and then
    `src/orders.py`. Two modules with one name is worse than either: an
    import finds whichever comes first on the path, and the other rots.
    """
    if original.strip():
        return ""
    from harness.paths import as_project_rel, rel_posix

    wanted = Path(as_project_rel(rel))
    if wanted.name.startswith("test_") or "tests" in wanted.parts:
        return ""
    root = Path(project).resolve()
    for existing in sorted(root.rglob(f"{wanted.stem}.py")):
        if any(part in {".git", ".venv", "__pycache__"} for part in existing.parts):
            continue
        found = rel_posix(existing, root)
        if found != wanted.as_posix():
            return (
                f"{found} is already this project's {wanted.stem} module. "
                f"Action: patch Path: {found} Append: the new function"
            )
    return ""


def refuse_missing_import_target(project: Path, rel: str, draft: str) -> str:
    """Refuse a file importing a name this project has not defined yet.

    Asked to create a module and a test for it, the model wrote only the
    test, importing a function nobody had written. That reads as valid
    Python — the import binds the name — and fails when the suite runs. The
    function has to exist first.
    """
    from harness.scan.names import missing_import_targets

    missing = missing_import_targets(project, draft)
    if not missing:
        return ""
    module, name = missing[0]
    return (
        f"{module} does not define {name} yet. Write the function first: "
        f"Action: patch Path: {module.replace('.', '/')}.py Append: def {name}(...)"
    )


@dataclass(frozen=True)
class ProposedChange:
    """One change the model has proposed, and what it is judged on.

    Fields:
        task: what the user asked for, in their own words.
        rel: the file the change targets, project-relative.
        original: the file as it stands, or "" when it is new.
        draft: the file as this change would leave it.
        fragment: only the part being added, when the change appends.
            Judging a whole file as one test turns a single inline
            assertion anywhere into a refusal for everything in it.
    """

    task: str
    rel: str
    original: str
    draft: str
    fragment: str = ""


# Every rule a proposed change is put through, in the order they run.
# This was thirty lines of `blocked = rule(...); if blocked: return
# blocked`, eleven times over, which hid both the order and the fact that
# a new rule has to be added to it. A rule written and not listed here
# does nothing, and a test below checks for exactly that.
CHANGE_RULES: tuple[tuple[str, Callable[[ProposedChange], str]], ...] = (
    ("stdlib shadow", lambda c: refuse_stdlib_shadow(c.rel, c.original)),
    ("layout", lambda c: refuse_layout(c.rel, c.original, c.draft)),
    ("opens a file", lambda c: refuse_add_opens_file(c.task, c.rel, c.draft)),
    ("shell fetch", lambda c: refuse_shell_fetch(c.rel, c.draft)),
    ("platform draft", lambda c: refuse_platform_draft(c.rel, c.draft)),
    ("operations draft", lambda c: refuse_ops_draft(c.rel, c.draft)),
    ("test in implementation", lambda c: refuse_test_in_impl(c.rel, c.draft)),
    (
        "self outside a class",
        lambda c: refuse_self_at_module_level(c.rel, c.fragment or c.draft),
    ),
    ("stub body", lambda c: refuse_stub_body(c.task, c.rel, c.draft)),
    (
        "undefined name",
        lambda c: refuse_undefined_draft(c.task, c.rel, c.original, c.draft),
    ),
    (
        "dropped the subject",
        lambda c: refuse_dropped_definition(c.task, c.rel, c.original, c.draft),
    ),
    (
        "half a rename",
        lambda c: refuse_rename_incomplete(c.task, c.rel, c.draft),
    ),
    ("weak test", lambda c: refuse_weak_test(c.rel, c.fragment or c.draft)),
    ("opaque names", lambda c: refuse_opaque_names(c.draft, c.task)),
    ("opaque module", lambda c: refuse_opaque_module(c.rel, c.original)),
)


def first_refusal(
    task: str, rel: str, original: str, draft: str, fragment: str = ""
) -> str:
    """The first refusal a proposed change earns, or "" if it earns none."""
    change = ProposedChange(task, rel, original, draft, fragment)
    for _name, rule in CHANGE_RULES:
        refusal = rule(change)
        if refusal:
            return refusal
    return ""


def already_defined(original: str, append: str, rel: str) -> str:
    """Refuse appending a definition the file already has, or "".

    Only test methods were checked, so an ordinary function could be
    added twice: a live run appended `def slugify` to the same file on
    two separate turns and left both in place.
    """
    meth = _TEST_METH.search(append)
    if meth and re.search(rf"def\s+{re.escape(meth.group(1))}\s*\(", original):
        return (
            f"{meth.group(1)} already exists. Action: done Summary: "
            "that function is already covered."
        )
    for name in re.findall(r"(?m)^def\s+(\w+)\s*\(", append):
        if re.search(rf"(?m)^def\s+{re.escape(name)}\s*\(", original):
            return (
                f"{name} is already defined in {rel}. Action: done "
                "Summary: say what it does, or patch the existing one."
            )
    return ""



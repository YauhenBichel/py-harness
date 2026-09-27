"""Whether one proposed change may be written.

Each rule reads a draft and answers with a refusal or nothing. They
are run in order by `CHANGE_RULES` in `act/gate.py`, and each was
written from a run that went wrong: a module shadowing the standard
library, a function whose body was `...`, a test asserting nothing.
"""

from __future__ import annotations

"""SoC / readable-name guards. Deterministic. No model."""
import ast
import re
import sys
from pathlib import Path
from harness.scan.names import new_undefined, undefined_names
from harness.task import (
    looks_like_add_feature,
    looks_like_bugfix,
    looks_like_design_loop,
    looks_like_everyday_code,
    looks_like_fix_smell,
    question_symbol,
    rename_pair,
    smell_symbol,
)


_DEF = re.compile(r"^def\s+([A-Za-z_]\w*)\s*\(", re.MULTILINE)


_CLASS = re.compile(r"^class\s+([A-Za-z_]\w*)", re.MULTILINE)


_OK_PARAM = frozenset({"self", "cls", "i", "j", "k"})


_OPAQUE = frozenset(
    {
        "btn",
        "calc",
        "data",
        "do",
        "fn",
        "foo",
        "bar",
        "baz",
        "func",
        "helper",
        "mgr",
        "misc",
        "obj",
        "proc",
        "stuff",
        "temp",
        "thing",
        "tmp",
        "util",
        "val",
        "var",
    }
)


def _opaque_param(draft: str, asked: frozenset[str] = frozenset()) -> str:
    for match in re.finditer(r"^def\s+\w+\s*\((.*?)\)", draft, re.MULTILINE | re.DOTALL):
        for part in match.group(1).split(","):
            token = part.strip()
            if not token or token.startswith("*"):
                continue
            name = token.split(":")[0].split("=")[0].strip()
            if name in _OK_PARAM or name in asked:
                continue
            if len(name) == 1 or name in _OPAQUE:
                return (
                    f"opaque parameter {name}. Use a readable noun "
                    f"(quantity, unit_price), not x or tmp."
                )
    return ""


_SHELL_FETCH = re.compile(
    r"(?m)^\s*(os\.system|subprocess\.|Popen)|"
    r"\b(curl|wget)\s+\S"
)


_TASK_SIGNATURE = re.compile(r"\b\w+\s*\(\s*([^)]*?)\s*\)")


_ABOUT_FILES = re.compile(
    r"\b(file|files|path|paths|read|reads|load|loads|parse|parses|"
    r"open|opens|contents|lines of|\.env|config|json|csv|yaml|toml)\b",
    re.I,
)


def task_names_arguments(task: str) -> str:
    """The argument list the task itself gives, or ""."""
    symbol = question_symbol(task)
    if not symbol:
        return ""
    found = re.search(rf"\b{re.escape(symbol)}\s*\(\s*([^)]*?)\s*\)", task)
    return found.group(1).strip() if found else ""


def refuse_add_opens_file(task: str, rel: str, draft: str) -> str:
    """Counting the prices of an order does not mean opening a file.

    A live 8B read `add a function total_lines` in an orders module as a
    file-line counter and appended `open(file_path)`.

    The first version of this refused `open(` in any added function and
    told the model to write `return len(prices)` instead. That is only
    right for the one task it was written for. `read_env_file(path)` has
    to open a file — refusing it left a function returning an int where
    the caller wanted a dict, and the run spent its whole budget being
    told to write something else. So this now declines to judge whenever
    the task itself mentions files, or names its own arguments.
    """
    if not looks_like_add_feature(task):
        return ""
    if "test" in (rel or "").replace("\\", "/").lower():
        return ""
    if not draft or not re.search(r"\bopen\s*\(", draft):
        return ""
    if _ABOUT_FILES.search(task):
        return ""
    if task_names_arguments(task):
        return ""
    symbol = question_symbol(task) or "the_new_function"
    return (
        f"Reading a file is not what {symbol} was asked for. "
        f"Action: patch Path: {rel} Append: def {symbol}(...) using the "
        "values the module already has."
    )


def refuse_stub_body(task: str, rel: str, draft: str) -> str:
    """Refuse a requested function whose body is `...` or `pass`.

    Asked to create `slugify`, a live 8B wrote

        def slugify(text: str) -> str: ...

    twice. It parses, it passes a name check, and it does nothing. A
    stub is a reasonable thing to write when someone asked for an
    interface; it is not what "create a function that lowercases and
    joins words" asked for.

    Every function in the draft is judged, not only the one the task
    names. The task wording does not reliably yield that name — for
    "create a function slugify(text)" it comes back as "create" — and on
    an add-feature task an empty body is wrong whatever it is called.
    """
    if "test" in (rel or "").replace("\\", "/").lower():
        return ""
    if not (looks_like_add_feature(task) or looks_like_everyday_code(task)):
        return ""
    try:
        tree = ast.parse(draft or "")
    except (SyntaxError, ValueError):
        return ""
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = [
            item
            for item in node.body
            if not (
                isinstance(item, ast.Expr)
                and isinstance(item.value, ast.Constant)
                and isinstance(item.value.value, str)
            )
        ]
        empty = all(
            isinstance(item, ast.Pass)
            or (
                isinstance(item, ast.Expr)
                and isinstance(item.value, ast.Constant)
                and item.value.value is Ellipsis
            )
            for item in body
        )
        if body and empty:
            return (
                f"def {node.name} has no body. Write what it does, not a "
                f"placeholder. Action: patch Path: {rel} Append: def "
                f"{node.name}(...) with a return statement."
            )
    return ""


def refuse_shell_fetch(rel: str, draft: str) -> str:
    """HTTP helpers use urllib. curl|sh is already PV003; this catches curl alone.

    Test files may quote the blocked pattern, so they are not judged.
    """
    if "test" in rel.replace("\\", "/").lower():
        return ""
    if not draft or not _SHELL_FETCH.search(draft):
        return ""
    return "urllib.request only. Do not emit curl, wget, or os.system."


_PIPE_SH = re.compile(r"curl\s+\S+.*\|\s*(sh|bash)|wget\s+\S+.*\|\s*(sh|bash)", re.I)


_BIND_ALL = re.compile(r"0\.0\.0\.0")


_INLINE_SECRET = re.compile(
    r"""(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*['"][^'"]{8,}['"]"""
)


def refuse_ops_draft(rel: str, draft: str) -> str:
    """Workflow YAML stays a test runner. No installer pipe, no public bind."""
    suffix = Path(rel or "").suffix.lower()
    if suffix not in {".yml", ".yaml"} and "workflow" not in (rel or "").lower():
        return ""
    if not draft:
        return ""
    if _PIPE_SH.search(draft):
        return "no curl|sh in a workflow. Run unittest only."
    if _BIND_ALL.search(draft):
        return "do not bind 0.0.0.0. Keep the sidecar on 127.0.0.1."
    if _INLINE_SECRET.search(draft):
        return "no inline secrets. Use the runner's secret store, or omit."
    return ""


_OS_PATH = re.compile(
    r"\bos\.path\.(join|exists|isfile|isdir|dirname|abspath|basename|"
    r"expanduser|normpath)\b"
)


_HARD_HOME = re.compile(
    r"""['"](?:/Users/|/home/|[A-Za-z]:\\Users\\|[A-Za-z]:\\\\Users\\\\)"""
)


_HARD_TMP = re.compile(r"""['"]/tmp/""")


_POSIX_ONLY_VENV = re.compile(r"""['"]bin/python['"]""")


_OPEN_CALL = re.compile(r"\bopen\(([^)]*)\)")


def refuse_platform_draft(rel: str, draft: str) -> str:
    """Path helpers stay pathlib and work on Windows, macOS, and Linux.

    Test files may quote a blocked pattern, so they are not judged.
    """
    if "test" in (rel or "").replace("\\", "/").lower():
        return ""
    if not draft:
        return ""
    if _OS_PATH.search(draft):
        return (
            "use pathlib. Path / 'src' / 'app.py', not os.path.join. "
            "exists is Path.exists()."
        )
    if _HARD_HOME.search(draft):
        return "no hardcoded home. Use Path.home()."
    if _HARD_TMP.search(draft):
        return "no hardcoded /tmp. Use tempfile.TemporaryDirectory."
    if _POSIX_ONLY_VENV.search(draft) and "Scripts" not in draft:
        return (
            "venv interpreter is Scripts/python.exe on Windows, "
            "bin/python on POSIX. Branch on os.name."
        )
    for match in _OPEN_CALL.finditer(draft):
        args = match.group(1)
        if "encoding" in args:
            continue
        if re.search(r"['\"][^'\"]*b", args):
            continue
        return 'open(..., encoding="utf-8"). Text files need an encoding.'
    if ".chmod(" in draft and "nt" not in draft:
        return 'chmod is POSIX-only. Guard with os.name != "nt".'
    return ""


# A task that spells a signature has chosen the names in it. `add a
# function double(n) that returns n times two` asks for `n`, and a rule
# that refuses `n` there is arguing with the person who typed it.
_SIGNATURE = re.compile(r"\b([a-zA-Z_]\w*)\s*\(([^)]*)\)")


def names_the_task_asked_for(task: str) -> frozenset[str]:
    """Every function and parameter name the task spells out itself."""
    asked: set[str] = set()
    for match in _SIGNATURE.finditer(task or ""):
        asked.add(match.group(1))
        for part in match.group(2).split(","):
            name = part.strip().split(":")[0].split("=")[0].strip()
            if name and name.isidentifier():
                asked.add(name)
    return frozenset(asked)


def refuse_opaque_names(draft: str, task: str = "") -> str:
    """Refuse a name nobody can read, unless the task asked for it.

    This rule was written and tested, and nothing ever called it. It sat
    from the test that checks every draft rule is in the table, behind a
    comment saying it was "called from the draft rules themselves",
    which was not true.

    Wiring it as it stood would have refused the benchmark's own tier-1
    case: the task is `add a function double(n) that returns n times
    two`, and `n` is the parameter the task names. Refusing a draft for
    doing what it was told is worse than not checking at all, and is
    the likeliest reason this was left dead rather than fixed.
    """
    if not draft.strip():
        return ""
    asked = names_the_task_asked_for(task)
    for match in _DEF.finditer(draft):
        name = match.group(1)
        if name.startswith("test_") or (name.startswith("__") and name.endswith("__")):
            continue
        if name in asked:
            continue
        if len(name) == 1 or name in _OPAQUE:
            return (
                f"opaque name {name}. Use a readable snake_case verb_noun "
                f"(total_price, not calc or tmp)."
            )
        if name != name.lower() or any(ch.isupper() for ch in name):
            return f"functions are snake_case: {name}"
    param = _opaque_param(draft, asked)
    if param:
        return param
    for match in _CLASS.finditer(draft):
        name = match.group(1)
        if name[0].islower() or "_" in name:
            return f"classes are PascalCase: {name}"
    return ""


def refuse_smell_wrong_file(
    task: str,
    action: str,
    path: str,
    located_path: str,
    located_body: str = "",
) -> str:
    if not looks_like_fix_smell(task) or action != "patch" or not located_path:
        return ""
    rel = path.replace("\\", "/").lower()
    located = located_path.replace("\\", "/").lower()
    if "test" not in rel or "test" in located:
        return ""
    old = smell_symbol(task)
    if old and located_body and not re.search(rf"\bdef\s+{re.escape(old)}\b", located_body):
        return ""
    return (
        f"rename the implementation first. "
        f"Action: patch Path: {located_path} Find: the old def line."
    )


_TEST_DEF = re.compile(r"^[ \t]*def\s+(test_\w+)\s*\(", re.MULTILINE)


_TEST_CLASS = re.compile(r"^[ \t]*class\s+(\w+)\s*\(", re.MULTILINE)


_ONE_SHOT_ASSERT = re.compile(
    r"self\.assert\w+\s*\(\s*[A-Za-z_]\w+\s*\(",
)


_OPAQUE_TEST_PART = frozenset(
    {"bar", "foo", "fn", "func", "it", "ok", "tmp", "works"}
)


_ACT_NAMES = ("got", "actual", "result", "outcome")


def refuse_weak_test(rel: str, draft: str) -> str:
    """Refuse a newly written test that is unclear about what it checks.

    Calibrated against this project's own tests: none of them is refused.
    A rule that rejects the code it is shipped with is not a style rule, it
    is an obstacle, so `tests/test_refusals.py` checks that directly.

    Only a draft holding a single test is judged on arrangement. A whole
    file holds many tests written over time, and judging it as one unit
    turns one inline assertion anywhere into a refusal for everything.
    """
    posix = rel.replace("\\", "/").lower()
    if "test" not in posix and "def test_" not in (draft or ""):
        return ""
    if "def test_" not in (draft or ""):
        return ""
    one_test = len(_TEST_DEF.findall(draft)) == 1
    for match in _TEST_CLASS.finditer(draft):
        name = match.group(1)
        if name.startswith("test_") or name in {"Test", "Tests"} or "_" in name:
            return (
                f"class name {name}. Use Test<Unit> PascalCase "
                "(TestMultiply), not Tests or test_mathy."
            )
    for match in _TEST_DEF.finditer(draft):
        name = match.group(1)
        parts = name.split("_")
        # A short name is only a problem when it says nothing: test_total
        # and test_health name their subject, test_ok and test_works do not.
        # An opaque word only makes a name opaque when it carries the
        # meaning. test_it_works says nothing;
        # test_the_suite_passes_before_the_agent_touches_it says plenty and
        # happens to end in "it".
        if len(parts) <= 3 and any(part in _OPAQUE_TEST_PART for part in parts[1:]):
            return (
                f"opaque test name {name}. "
                "Name the behavior, not it/fn/ok/works."
            )
    # Anchored to the start of a line so the phrase inside a string literal,
    # which is how several of this project's own tests carry sample code,
    # is not mistaken for the statement.
    if re.search(r"^[ \t]*assert\s+True\b", draft, re.MULTILINE):
        return "do not assert True. Assert the value you computed."
    named_act = any(re.search(rf"\b{name}\s*=", draft) for name in _ACT_NAMES)
    if one_test and _ONE_SHOT_ASSERT.search(draft) and not named_act:
        return (
            "use AAA. Arrange inputs, Act: got = multiply(left, right), "
            "Assert: self.assertEqual(got, expected)."
        )
    return ""


def refuse_test_in_impl(rel: str, draft: str) -> str:
    """Tests belong in tests/. Live 8B wrote def test_ into src/orders.py."""
    posix = (rel or "").replace("\\", "/").lower()
    if "test" in posix or posix.endswith("conftest.py"):
        return ""
    if re.search(r"^[ \t]*def test_", draft or "", re.MULTILINE):
        return (
            "tests go in tests/test_<unit>.py. "
            "Do not write def test_ in the implementation file."
        )
    return ""


_SELF_AT_TOP = re.compile(r"^def\s+(\w+)\s*\(\s*(self|cls)\b", re.MULTILINE)


def refuse_self_at_module_level(rel: str, draft: str) -> str:
    """Refuse a def at column 0 whose first parameter is self or cls.

    A class method emitted with no class around it. Live 8B wrote
    `def total_lines(self) -> int` at module level, which nothing can
    call, and `def test_apply_discount(self)` with no TestCase, which
    discovery never collects. Issues #173 and #174 are the same shape
    twice; this is the one check both asked for.
    """
    match = _SELF_AT_TOP.search(draft or "")
    if not match:
        return ""
    name, first = match.group(1), match.group(2)
    posix = (rel or "").replace("\\", "/").lower()
    if name.startswith("test_") or "test" in posix:
        return (
            f"def {name}({first}, ...) is at module level with no class around it, "
            "so unittest never collects it. Put it, indented, inside "
            "`class Test...(unittest.TestCase):`."
        )
    return (
        f"def {name}({first}, ...) is at module level with no class around it, "
        f"so nothing can call it. Write def {name}(...) without `{first}`, "
        "taking what it needs as arguments."
    )


def _undefined_message(rel: str, name: str) -> str:
    """Say how to bind the name, not just that it is unbound.

    `Path` used without `from pathlib import Path` was answered with
    "Find: Path Replace: the name you assigned", which asks for a rename
    when the fix is an import line.
    """
    from harness.scan.names import import_for

    line = import_for(name)
    if line:
        return (
            f"{name} is used but never imported. "
            f"Action: patch Path: {rel} Find: {line.split()[-1]} "
            f"Replace: {line.split()[-1]}  # then add at the top: {line}"
        )
    return (
        f"undefined name {name}. "
        f"Action: patch Path: {rel} Find: {name} "
        "Replace: the name you assigned."
    )


def refuse_undefined_draft(task: str, rel: str, original: str, draft: str) -> str:
    """Refuse a write that adds an unbound name, or a bugfix that leaves one."""
    if not draft or not (rel or "").endswith(".py"):
        return ""
    if looks_like_bugfix(task):
        leftover = undefined_names(draft)
        if leftover:
            return _undefined_message(rel, leftover[0])
        return ""
    added = new_undefined(original, draft)
    if added:
        return _undefined_message(rel, added[0]) or (
            f"undefined name {added[0]}. "
            f"Action: patch Path: {rel} Find: {added[0]} "
            "Replace: the name you assigned."
        )
    return ""


def refuse_dropped_definition(task: str, rel: str, original: str, draft: str) -> str:
    """Refuse a write that removes the function the task named.

    Asked to fix the bug in `last_price`, a run rewrote `src/orders.py`
    without it. The file still imported, the suite still passed — there
    was nothing left to fail — and the benchmark reported the function
    missing. One run in five ended that way.

    Deleting the subject is never the fix for "fix the bug in X", so this
    is narrow on purpose: only the one name the task is about, and not
    when the task asks for a rename or a move, where the old name is
    supposed to go.

    It covers what `question_symbol` can name, which is lower case. A
    class called `Ledger` is answered as `ledger` and so is not matched.
    Comparing case-insensitively instead would refuse honest edits to a
    differently-cased name, which is the worse trade.
    """
    symbol = question_symbol(task)
    if not symbol or not rel.endswith(".py"):
        return ""
    # A rename, a move or a removal is entitled to take the name away.
    if any(word in task.lower() for word in ("move ", "rename", "delete", "remove")):
        return ""
    here = rf"(?m)^(?:def|class)\s+{re.escape(symbol)}\b"
    if not re.search(here, original) or re.search(here, draft):
        return ""
    return (
        f"that draft drops {symbol} from {rel}, and the task is about "
        f"{symbol}. Action: patch Path: {rel} Find: a unique line inside "
        f"{symbol} Replace: the corrected line."
    )


def refuse_rename_incomplete(task: str, rel: str, draft: str) -> str:
    """A rename is not done if the old def is still there."""
    if not looks_like_fix_smell(task) or "test" in (rel or "").replace("\\", "/").lower():
        return ""
    old, new = rename_pair(task)
    if not old or not new:
        return ""
    if re.search(rf"^def {re.escape(old)}\b", draft or "", re.MULTILINE):
        return (
            f"still defines {old}. "
            f"Action: patch Find: def {old} Replace: def {new}"
        )
    if not re.search(rf"^def {re.escape(new)}\b", draft or "", re.MULTILINE):
        return (
            f"missing def {new}. "
            f"Action: patch Find: def {old} Replace: def {new}"
        )
    return ""


def refuse_god_target(task: str, project: Path, action: str, path: str) -> str:
    """Design-loop writes go to a new one-function file, not the god module."""
    if not looks_like_design_loop(task) or action not in {"edit", "patch"}:
        return ""
    rel = (path or "").replace("\\", "/").lstrip("./")
    if not rel:
        return ""
    target = Path(project) / rel
    if not target.is_file():
        return ""
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return ""
    count = len(re.findall(r"^def ", text, re.MULTILINE))
    if count < 4:
        return ""
    return (
        f"SoC: {rel} already has {count} functions. "
        "Action: edit Path: pkg/<new_concern>.py with only the new function."
    )


_STDLIB = frozenset(sys.stdlib_module_names)


_SHADOW_ALLOWED = frozenset({"types", "typing", "test", "tests", "config"})


# Names that say where a thing was put, not what it is. A reader
# grepping for the concern finds nothing, because the file name never
# had one.
DRAWER_STEMS = frozenset(
    {"common", "helper", "helpers", "misc", "shared", "tmp", "util", "utils"}
)


def refuse_opaque_module(rel: str, original: str) -> str:
    """Reject a *new* file whose name names nothing.

    `refuse_opaque_names` reads defs, classes and parameters and never
    looked at the file name, so `pkg/helpers.py` was always allowed —
    and an 8B reaches for it constantly.

    Only a new file. An existing `util.py` in somebody's tree is theirs,
    and refusing to touch it would make the rule about their history
    rather than about this change. Test files are left alone too: a
    `tests/test_util.py` beside a `util.py` is named after the thing it
    tests, which is correct.
    """
    if original.strip():
        return ""
    path = Path(rel)
    if path.name.startswith("test_") or "tests" in path.parts:
        return ""
    stem = path.stem.lower()
    if stem not in DRAWER_STEMS:
        return ""
    return (
        f"opaque module {path.name}. Name the concern it holds "
        "(pricing.py, not helpers.py), so the next reader can find it."
    )


def refuse_stdlib_shadow(rel: str, original: str) -> str:
    """Refuse a new module whose name hides one from the standard library.

    Asked for a clamp helper, the model created `pkg/math.py`. Every later
    `import math` in that project then finds the new file, and the failure
    appears far from the change that caused it. Only new files are checked:
    a project that already has such a module is its own business.
    """
    if original.strip():
        return ""
    stem = Path(rel).stem
    if stem not in _STDLIB or stem in _SHADOW_ALLOWED:
        return ""
    return (
        f"{rel} would hide the standard library module {stem}. "
        f"Choose another name, such as {stem}_helpers.py."
    )


def refuse_layout(rel: str, original: str, draft: str) -> str:
    posix = rel.replace("\\", "/").lstrip("./")
    has_impl = bool(re.search(r"^(async\s+)?(def |class )", draft, re.MULTILINE))
    if posix.endswith("__init__.py") and has_impl:
        return (
            "SoC: __init__.py is exports only. "
            "Action: edit Path: pkg/<noun>.py with the function."
        )
    if (posix.startswith("scripts/") or "/scripts/" in posix) and has_impl:
        if "def main" not in draft:
            return "SoC: library code is not in scripts/. Use pkg/<noun>.py"
    if has_impl and original:
        count = len(re.findall(r"^def ", original, re.MULTILINE))
        if count >= 4:
            return (
                f"SoC: {posix} already has {count} functions. "
                "Action: edit Path: pkg/<new_concern>.py with only the new function."
            )
    return ""


def wrap_bare_unittest(source: str, symbol: str) -> str:
    """8B writes def test_*(self) with no TestCase. Wrap it."""
    if "TestCase" in source:
        return source
    if not re.search(r"^def\s+test_\w+\s*\(\s*self", source, re.MULTILINE):
        return source
    class_name = "Test" + "".join(
        part[:1].upper() + part[1:] for part in symbol.split("_") if part
    )
    if class_name == "Test":
        class_name = "TestModule"
    import_line = f"from pkg.{symbol} import {symbol}\n\n" if symbol else ""
    body = "\n".join(
        ("    " + line if line.strip() else "") for line in source.strip().splitlines()
    )
    return (
        "import unittest\n\n"
        f"{import_line}"
        f"class {class_name}(unittest.TestCase):\n"
        f"{body}\n\n"
        'if __name__ == "__main__":\n'
        "    unittest.main()\n"
    )

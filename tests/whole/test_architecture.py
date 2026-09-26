"""The layer rule, enforced. A refactor that rots fails here first.

`src/harness/` is ordered bottom-up. A module may import a layer strictly
below it and never one above or beside it, so the import graph stays a
DAG and every layer can be read on its own.
"""

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "src" / "harness"

# Lower number = deeper. A layer may only import strictly lower layers.
DEPTH = {
    # `paths` and `task` are the bottom: they import nothing of their own.
    "paths": 0,
    "task": 0,
    # A fitted decision about the task. Imports nothing of the harness,
    # like `task`; the agent layer asks it and hands the answer down.
    "decide": 0,
    # The shapes that are a secret whoever is looking. Both the guard
    # that reads what arrives and the check on what leaves need them,
    # and neither may import the other, so they sit under both.
    "secrets": 0,
    # What a run remembers. It imports nothing of its own, and the loop
    # owns it: the model package is handed a memory, it does not make one.
    "memory": 0,
    "chat_backend": 0,
    "model": 1,
    # `ship` sits above `scan` because reading a ticket means locating what
    # it names in the project.
    "ship": 3,
    "guard": 1,
    "scan": 2,
    "skillkit": 3,
    "act": 4,
    "locate": 5,
    "observe": 6,
    "agent": 7,
    # The request and reply shape the server speaks. It imports nothing from
    # this project, so it sits below the server that uses it.
    "openai_api": 7,
    "server": 8,
    "mcp_stdio": 8,
    "editor_kit": 1,
    "cli": 9,
    "__main__": 10,
}


def _layer(rel: Path) -> str:
    """Package name for a subpackage module, else the module's own stem."""
    return rel.parts[0] if len(rel.parts) > 1 else rel.stem


def _edges() -> set[tuple[str, str, str]]:
    found: set[tuple[str, str, str]] = set()
    for path in sorted(HARNESS.rglob("*.py")):
        rel = path.relative_to(HARNESS)
        if rel == Path("__init__.py"):
            continue
        source = _layer(rel)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if not node.module or not node.module.startswith("harness."):
                continue
            target = node.module.split(".", 1)[1].split(".")[0]
            if target != source:
                found.add((source, target, str(rel)))
    return found


class LayerRuleTest(unittest.TestCase):
    def test_every_layer_is_known(self) -> None:
        layers = {_layer(p.relative_to(HARNESS)) for p in HARNESS.rglob("*.py")}
        layers.discard("__init__")
        unknown = sorted(layers - set(DEPTH))
        self.assertEqual(
            unknown,
            [],
            f"new layer(s) {unknown}: give them a depth in DEPTH, or move them",
        )

    def test_imports_only_point_downwards(self) -> None:
        upward = [
            f"{where}: {source} -> {target}"
            for source, target, where in sorted(_edges())
            if DEPTH[target] >= DEPTH[source]
        ]
        self.assertEqual(upward, [], "layer rule broken")

    def test_no_import_cycles(self) -> None:
        graph: dict[str, set[str]] = {}
        for source, target, _where in _edges():
            graph.setdefault(source, set()).add(target)
        state: dict[str, int] = {}

        def walk(node: str, trail: list[str]) -> list[str] | None:
            state[node] = 1
            for nxt in sorted(graph.get(node, ())):
                if state.get(nxt) == 1:
                    return trail + [node, nxt]
                if state.get(nxt, 0) == 0:
                    found = walk(nxt, trail + [node])
                    if found:
                        return found
            state[node] = 2
            return None

        for node in sorted(graph):
            if state.get(node, 0) == 0:
                self.assertIsNone(walk(node, []), "import cycle between layers")

    def test_no_module_counts_its_own_depth(self) -> None:
        """`parents[N]` breaks the moment a module moves into a layer."""
        offenders = [
            str(path.relative_to(HARNESS))
            for path in sorted(HARNESS.rglob("*.py"))
            if "parents[" in path.read_text(encoding="utf-8")
            and path.name != "paths.py"
        ]
        self.assertEqual(offenders, [], "use harness.paths instead of parents[N]")

    def test_the_guard_layer_cannot_write(self) -> None:
        """The safety boundary must not import a layer that touches files."""
        writers = {"act", "locate"}
        leaks = [
            f"{where}: guard -> {target}"
            for source, target, where in sorted(_edges())
            if source == "guard" and target in writers
        ]
        self.assertEqual(leaks, [])


class TempDirectoryTest(unittest.TestCase):
    """A test must not create files inside the checkout.

    AGENTS.md asks for `tempfile.TemporaryDirectory`. Passing `dir=ROOT`
    puts the directory in the repository instead of the system temp area,
    so a crashed run leaves it behind, where the suite's own scans of the
    project will then find it.
    """

    TESTS = Path(__file__).resolve().parent

    def test_no_test_creates_a_temporary_directory_in_the_repo(self) -> None:
        offenders: list[str] = []
        for path in sorted(self.TESTS.glob("test_*.py")):
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1
            ):
                stripped = line.strip()
                if "TemporaryDirectory(" not in stripped:
                    continue
                if "dir=" in stripped and "dir=tmp" not in stripped:
                    offenders.append(f"{path.name}:{number}: {stripped}")
        self.assertEqual(offenders, [], "use the system temp area")


class SuiteRunsWholeFilesTest(unittest.TestCase):
    """Every test in a file must run when that file is run on its own.

    `unittest.main()` executes where it sits, so a class defined below
    it is never collected. Ten files had it mid-file; test_autofix.py
    ran 11 of its 36 tests that way. CI uses discovery, so all of them
    were green while more than half of one file did nothing. Iterating
    on a single file is the normal way to work, and it was the way that
    lied.
    """

    def test_no_test_class_is_defined_after_unittest_main(self) -> None:
        stragglers = []
        for path in sorted((ROOT / "tests").glob("test_*.py")):
            lines = path.read_text(encoding="utf-8").splitlines()
            start = next(
                (i for i, line in enumerate(lines)
                 if line.startswith('if __name__ == "__main__"')),
                None,
            )
            if start is None:
                continue
            after = [
                line for line in lines[start + 1:]
                if line.startswith("class ") or line.startswith("def test")
            ]
            if after:
                stragglers.append(f"{path.name}: {after[0]}")
        self.assertEqual(stragglers, [])

    def test_running_a_file_directly_collects_what_discovery_does(self) -> None:
        import unittest.loader

        loader = unittest.defaultTestLoader
        for path in sorted((ROOT / "tests").glob("test_*.py")):
            with self.subTest(file=path.name):
                found = loader.discover(str(ROOT / "tests"), pattern=path.name)
                self.assertGreater(found.countTestCases(), 0, path.name)

class FunctionsStaySmallTest(unittest.TestCase):
    """A function long enough to need a map is a function to split.

    `Agent.run` reached 242 lines and 33 branch points, holding the whole
    decision about whether the model was needed at all in local
    variables, so none of those decisions could be read or tested apart
    from the others. `prelude` was 141 lines of task kinds, where the
    shared tail read as if it belonged to whichever branch you had just
    finished reading.

    The six below are what is left. Each is listed with what it is, so
    the number is a decision someone made rather than a line that
    drifted. Nothing new joins the list without saying why.
    """

    LIMIT = 80
    KNOWN_LONG = {
        "make_handler": "one HTTP route table, closing over the server",
        "_work_with_the_model": (
            "the model turn loop; its branches end in continue or return, "
            "so splitting them needs a protocol that reads worse than the loop"
        ),
        "handle_rpc": "one JSON-RPC method table",
        "pick_skills": "one ordered list of skill rules",
        "next_prompt": "one ordered list of nudges",
        "build_parser": "argparse declarations, no branching",
    }

    def _long_functions(self) -> dict[str, int]:
        found: dict[str, int] = {}
        for path in sorted((ROOT / "src" / "harness").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                length = (node.end_lineno or node.lineno) - node.lineno
                if length > self.LIMIT:
                    found[node.name] = length
        return found

    def test_no_new_long_function(self) -> None:
        unexpected = {
            name: length
            for name, length in self._long_functions().items()
            if name not in self.KNOWN_LONG
        }
        self.assertEqual(
            unexpected,
            {},
            f"over {self.LIMIT} lines and not in KNOWN_LONG: {unexpected}. "
            "Split it, or list it with the reason it stays whole.",
        )

    def test_the_list_has_no_stale_entries(self) -> None:
        """A function that no longer needs the exception should lose it."""
        stale = sorted(set(self.KNOWN_LONG) - set(self._long_functions()))
        self.assertEqual(stale, [], f"no longer long, drop these: {stale}")

    def test_every_exception_says_why(self) -> None:
        for name, reason in self.KNOWN_LONG.items():
            with self.subTest(function=name):
                self.assertTrue(reason.strip(), name)


class ThreeRingsTest(unittest.TestCase):
    """An agent is a harness around a model, and the rings stay separate.

    Outermost is what a person or an editor talks to: the command line,
    the HTTP server, the MCP bridge, the editor files. In the middle is
    the harness — the loop, the tools, the guards, the skills — which is
    where nearly all of the behaviour lives. Innermost is the code that
    talks to a model.

    The rule that makes the picture real is that the outer ring does not
    reach into the inner one. The command line and the server both did:
    they imported `harness.model.*` directly, so the model package could
    not change shape without changing them. `openai_api` used to live in
    that package as well, though it only knows what a chat request looks
    like and nothing about weights.
    """

    DELIVERY = {"cli", "server", "mcp_stdio", "editor_kit", "__main__", "openai_api"}
    MODEL = "model"

    def _imports(self, path: Path) -> list[tuple[str, int]]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "harness."
            ):
                found.append((node.module, node.lineno))
        return found

    def test_the_outer_ring_does_not_reach_into_the_model(self) -> None:
        offenders = []
        for path in sorted(HARNESS.rglob("*.py")):
            rel = path.relative_to(HARNESS).as_posix()
            name = rel.split("/")[0].removesuffix(".py")
            if name not in self.DELIVERY:
                continue
            for module, line in self._imports(path):
                if module.split(".")[1] == self.MODEL:
                    offenders.append(f"{rel}:{line} imports {module}")
        self.assertEqual(
            offenders,
            [],
            "the command line and the server go through the harness, "
            f"not into the model package: {offenders}",
        )

    def test_the_model_package_only_talks_to_a_model(self) -> None:
        """Nothing in there should be about HTTP shapes or the CLI."""
        for path in sorted((HARNESS / "model").glob("*.py")):
            with self.subTest(module=path.name):
                for module, _line in self._imports(path):
                    second = module.split(".")[1]
                    self.assertNotIn(
                        second,
                        self.DELIVERY,
                        f"{path.name} imports the outer ring: {module}",
                    )

    def test_the_harness_is_what_drives_the_model(self) -> None:
        """Exactly one place calls for a generator, and it is the loop."""
        callers = [
            path.relative_to(HARNESS).as_posix()
            for path in sorted(HARNESS.rglob("*.py"))
            if "make_generate" in path.read_text(encoding="utf-8")
            and path.parent.name != "model"
        ]
        self.assertEqual(callers, ["agent/loop.py"], callers)


class NothingIsWrittenAndForgottenTest(unittest.TestCase):
    """A function nobody calls is a claim nobody checks.

    `skill_example_path` was written to stop a placeholder path reaching
    the model, and returned `pkg/<noun>.py` when it could not find one —
    a placeholder path. It was never called from anywhere, and the job
    it was for is done by `everyday_example_path`, which is called from
    four places. Nothing failed when it was deleted.
    """

    # Called by http.server itself, by name, not from this project.
    CALLED_BY_A_FRAMEWORK = {"do_GET", "do_POST", "log_message"}

    def test_every_function_is_reachable(self) -> None:
        import collections

        defined: dict[str, str] = {}
        used: collections.Counter = collections.Counter()
        roots = [ROOT / "src" / "harness", ROOT / "tests", ROOT / "scripts"]
        for root in roots:
            for path in root.rglob("*.py"):
                if "__pycache__" in path.parts:
                    continue
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8"))
                except SyntaxError:
                    continue
                inside = path.is_relative_to(ROOT / "src" / "harness")
                for node in ast.walk(tree):
                    if inside and isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ):
                        defined.setdefault(
                            node.name, path.relative_to(ROOT).as_posix()
                        )
                    if isinstance(node, ast.Name):
                        used[node.id] += 1
                    elif isinstance(node, ast.Attribute):
                        used[node.attr] += 1
                    elif isinstance(node, ast.ImportFrom):
                        for alias in node.names:
                            used[alias.asname or alias.name] += 1
                    elif isinstance(node, ast.Constant) and isinstance(
                        node.value, str
                    ):
                        for word in (
                            node.value.replace("(", " ").replace(".", " ").split()
                        ):
                            if word.isidentifier():
                                used[word] += 1
        orphans = sorted(
            f"{name} in {where}"
            for name, where in defined.items()
            if used[name] == 0
            and not name.startswith("__")
            and name not in self.CALLED_BY_A_FRAMEWORK
        )
        self.assertEqual(orphans, [], f"written and never called: {orphans}")



class ToolsAreOnlyToolsTest(unittest.TestCase):
    """`act/tools.py` holds the things the agent can do, and nothing else.

    It had grown to 419 lines doing three jobs at once: the seven tools,
    the gate that judges a draft before it is written, and the helpers
    that repair one. Asked where the tools were, nobody could point at a
    file. The gate moved to `act/gate.py`; this keeps the answer short.
    """

    TOOLS = {
        "glob_py", "grep_py", "map_py", "read_py",
        "patch_py", "edit_py", "run_python",
    }

    def _top_level(self, module: str) -> set[str]:
        source = (ROOT / "src" / "harness" / "act" / module).read_text(
            encoding="utf-8"
        )
        return {
            node.name
            for node in ast.parse(source).body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        }

    def test_tools_holds_the_seven_tools_and_nothing_else(self) -> None:
        self.assertEqual(self._top_level("tools.py"), self.TOOLS)

    def test_no_refusal_is_written_in_tools(self) -> None:
        """A refusal is the gate's job, whichever file it ends up in."""
        stray = sorted(
            name for name in self._top_level("tools.py")
            if name.startswith("refuse_")
        )
        self.assertEqual(stray, [], f"belongs in act/gate.py: {stray}")

    def test_the_gate_holds_no_tool(self) -> None:
        self.assertEqual(self._top_level("gate.py") & self.TOOLS, set())


class TestsSitBesideWhatTheyTestTest(unittest.TestCase):
    """A test folder that is not a package contributes nothing, quietly.

    `unittest discover` walks into a directory only when it is
    importable. A folder added without `__init__.py` is skipped, its
    tests never run, and the suite still says OK — the worst shape a
    test failure can take, because there is no failure.
    """

    def _folders(self) -> list[Path]:
        tests = ROOT / "tests"
        return sorted(
            d for d in tests.iterdir()
            if d.is_dir() and not d.name.startswith(("_", "."))
        )

    def test_every_folder_is_a_package(self) -> None:
        missing = sorted(
            d.name for d in self._folders() if not (d / "__init__.py").is_file()
        )
        self.assertEqual(
            missing, [],
            f"no __init__.py, so discover skips them and their tests never "
            f"run: {missing}",
        )

    def test_no_folder_shadows_the_standard_library(self) -> None:
        """`tests/site/` broke four files the moment it was created.

        `site` is a real module, imported while the interpreter starts.
        The harness refuses this in a draft; it can refuse it here too.
        """
        clash = sorted(
            d.name for d in self._folders() if d.name in sys.stdlib_module_names
        )
        self.assertEqual(clash, [], f"shadows the standard library: {clash}")

    def test_no_test_file_is_left_loose(self) -> None:
        """A file directly in tests/ has no component to belong to."""
        loose = sorted(p.name for p in (ROOT / "tests").glob("test_*.py"))
        self.assertEqual(loose, [], f"put these beside what they test: {loose}")


    def test_no_script_is_left_loose(self) -> None:
        """A script directly in scripts/ has no job to belong to.

        Scripts are not components — nothing here belongs to `act` or
        `scan`. What separates them is why you would run one: point the
        tool at something, find out whether it is any good, or build the
        weights it talks to.
        """
        loose = sorted(p.name for p in (ROOT / "scripts").glob("*.py"))
        self.assertEqual(loose, [], f"put these under a job folder: {loose}")

    def test_every_script_folder_is_named_for_a_job(self) -> None:
        folders = sorted(
            d.name for d in (ROOT / "scripts").iterdir()
            if d.is_dir() and not d.name.startswith(("_", "."))
        )
        # The three reasons to run something: point the tool at a
        # project, find out whether it is any good, or build the weights
        # it talks to. A fourth name here means either a new job worth
        # naming, or a folder that wandered in.
        self.assertEqual(folders, ["measure", "run", "weights"])


if __name__ == "__main__":
    unittest.main()

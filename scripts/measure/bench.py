#!/usr/bin/env python3
"""Measure py-harness on tasks of increasing size, and check the result.

Tiers exist so improvement can be seen where it happens. A change that
helps one-file work and not two-file work should show exactly that.

The three jobs this is for: write a test, add a small component, fix a bug.

  tier 1  one small component in an existing file
  tier 2  a component and a test for it, two files
  tier 3  a new module with a component and a test
  tier 4  write a test for something already there
  tier 5  fix a bug that is already in the code
  tier 6  platform and operations work: paths, environment, config, retries

Each case runs the code afterwards. "Worked" means the function does the
job, not that a file was written.

  python scripts/measure/bench.py                 # every tier, needs Ollama
  python scripts/measure/bench.py --tier 1

Every turn is appended to the checkout's own `.python-vibe/traces.jsonl`,
which is outside the temporary project so it survives the run, and is
the file `scripts/weights/build_agent_data.py` already reads. Point it
somewhere else with `--traces`, or pass an empty one to keep nothing.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from harness import Agent, AgentOptions  # noqa: E402
from harness.observe.trace_record import default_trace_path  # noqa: E402

# A module that raises on import is skipped, which is right — a project
# may hold a script that cannot run here. But skipping it silently meant
# a file that *defines* the wanted function and fails to import reported
# "not found in any module", and that sentence sends the reader looking
# for a missing function rather than a broken import. It did exactly
# that to me: I read three such failures as the run deleting the
# function it was asked to fix, and went to check. It had not.
LOADER = '''
import importlib.util, pathlib
def load(name):
    broken = []
    for path in sorted(pathlib.Path(".").rglob("*.py")):
        if "__init__" in path.name or path.name.startswith("test"):
            continue
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if not spec or not spec.loader:
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            try:
                defines = ("def " + name) in path.read_text(encoding="utf-8")
            except OSError:
                defines = False
            if defines:
                broken.append(
                    path.as_posix() + " defines " + name
                    + " but does not import: "
                    + type(exc).__name__ + ": " + str(exc)
                )
            continue
        if callable(getattr(module, name, None)):
            return getattr(module, name)
    if broken:
        raise AssertionError("; ".join(broken))
    raise AssertionError(name + " not found in any module")
'''

APP = (
    '"""Order arithmetic."""\n\n\n'
    "def compute_total(prices: list[int]) -> int:\n"
    "    return sum(prices)\n"
)
TEST = (
    "import unittest\n\n"
    "from src.orders import compute_total\n\n\n"
    "class TestOrders(unittest.TestCase):\n"
    "    def test_compute_total_sums_the_prices(self) -> None:\n"
    "        prices = [1, 2]\n"
    "        got = compute_total(prices)\n"
    "        self.assertEqual(got, 3)\n"
)
BASE = {
    "src/__init__.py": "",
    "src/orders.py": APP,
    "tests/__init__.py": "",
    "tests/test_orders.py": TEST,
}


@dataclass
class Case:
    key: str
    tier: int
    task: str
    check: str
    suite_must_pass: bool = False
    files: dict = field(default_factory=dict)


CASES = [
    Case("double", 1, "add a function double(n) that returns n times two",
         "assert load('double')(4) == 8\n"),
    Case("largest", 1, "add a function largest(values) that returns the biggest value",
         "assert load('largest')([3, 9, 2]) == 9\n"),
    Case("initials", 1,
         "add a function initials(name) that returns the first letter of each word, upper case",
         "got = load('initials')('ada lovelace')\nassert got.upper() == 'AL', got\n"),
    Case("average", 2,
         "add a function average(values) that returns the mean, and a unit test",
         "assert load('average')([2, 4]) == 3\n", suite_must_pass=True),
    Case("clamp", 2,
         "add a function clamp(value, low, high) that keeps a value inside a range, and a unit test",
         "f = load('clamp')\nassert f(5, 1, 3) == 3 and f(0, 1, 3) == 1\n",
         suite_must_pass=True),
    Case("slugify", 3,
         "create a new module with a function slugify(text) that lowercases and joins words with a dash, and a unit test for it",
         "assert load('slugify')('Hello There') == 'hello-there'\n",
         suite_must_pass=True),
    Case("wordcount", 3,
         "create a new module with a function word_count(text) that counts words, and a unit test for it",
         "assert load('word_count')('a b c') == 3\n", suite_must_pass=True),

    # Tier 4: cover something that is already written.
    Case("cover-discount", 4,
         "write a unit test for apply_discount in src/orders.py",
         "import pathlib\n"
         "body = pathlib.Path('tests/test_orders.py').read_text()\n"
         "assert 'apply_discount' in body, 'no test names apply_discount'\n",
         suite_must_pass=True,
         files={"src/orders.py": APP + "\n\ndef apply_discount(total: int, percent: int) -> int:\n"
                                        "    return total - (total * percent) // 100\n"}),
    Case("cover-shout", 4,
         "write a unit test for shout in src/orders.py",
         "import pathlib\n"
         "body = pathlib.Path('tests/test_orders.py').read_text()\n"
         "assert 'shout' in body, 'no test names shout'\n",
         suite_must_pass=True,
         files={"src/orders.py": APP + "\n\ndef shout(text: str) -> str:\n    return text.upper() + '!'\n"}),

    # Tier 5: a bug that is already there, with a test that catches it.
    Case("fix-nameerror", 5,
         "fix the NameError in src/orders.py",
         "assert load('total_with_tax')([10]) == 12.0\n",
         files={"src/orders.py": APP + "\n\nTAX = 0.2\n\n\n"
                                        "def total_with_tax(prices: list[int]) -> float:\n"
                                        "    subtotal = compute_total(prices)\n"
                                        "    return subtotl + (subtotl * TAX)\n"}),
    # Tier 6: the work a platform or operations person brings.
    Case("env-flag", 6,
         "add a function env_flag(name, default) that reads a boolean environment "
         "variable, accepting 1, true and yes in any case",
         "import os\n"
         "f = load('env_flag')\n"
         "os.environ['X'] = 'TRUE'\nassert f('X', False) is True, 'TRUE'\n"
         "os.environ['X'] = 'yes'\nassert f('X', False) is True, 'yes'\n"
         "os.environ['X'] = '0'\nassert f('X', True) is False, '0'\n"
         "os.environ.pop('X')\nassert f('X', True) is True, 'default'\n"),
    Case("venv-python", 6,
         "add a function venv_python(venv, windows) that returns the interpreter "
         "path inside a virtual environment, Scripts on Windows and bin elsewhere",
         "from pathlib import Path\n"
         "f = load('venv_python')\n"
         "def call(on_windows):\n"
         "    # The natural signature makes `windows` keyword-only. Accept\n"
         "    # either shape: what matters is the path it returns.\n"
         "    try:\n"
         "        return str(f(Path('/p/.venv'), on_windows))\n"
         "    except TypeError:\n"
         "        return str(f(Path('/p/.venv'), windows=on_windows))\n"
         "win, nix = call(True), call(False)\n"
         "assert 'Scripts' in win and 'python' in win.lower(), win\n"
         "assert 'bin' in nix, nix\n"),
    Case("read-env-file", 6,
         "add a function read_env_file(path) that reads KEY=VALUE lines into a dict, "
         "skipping blank lines and comments",
         "open('.env.sample','w').write('# note\\nA=1\\n\\nB=two\\n')\n"
         "got = load('read_env_file')('.env.sample')\n"
         "assert got.get('A') == '1' and got.get('B') == 'two', got\n"
         "assert '#' not in ''.join(got), got\n"),
    Case("retry", 6,
         "add a function retry(action, times) that calls action and tries again "
         "on an exception, up to times, returning the result",
         "calls = []\n"
         "def flaky():\n"
         "    calls.append(1)\n"
         "    if len(calls) < 3:\n"
         "        raise ValueError('not yet')\n"
         "    return 'ok'\n"
         "assert load('retry')(flaky, 5) == 'ok', calls\n"),

    Case("fix-offbyone", 5,
         "fix the bug in last_price in src/orders.py: it raises IndexError on a full list",
         "assert load('last_price')([1, 2, 3]) == 3\n",
         files={"src/orders.py": APP + "\n\ndef last_price(prices: list[int]) -> int:\n"
                                        "    return prices[len(prices)]\n"}),
]


# What a person says when a run stops to ask. Deliberately empty of
# information: answering the question properly would hand over the thing
# the case is checking, and every model would score the same.
#
# Without any answer at all, a question ends the run and counts as a
# failure. Models differ enormously in how often they ask — on tier 3,
# `llama3.1:8b` asked in one run of twenty and `qwen2.5-coder:7b` in
# eleven — so a benchmark with nobody there measures willingness to act
# without asking, and calls it capability.
NO_HELP = (
    "Use the most likely reading, say which you chose, and continue."
)


# Outside the temporary project on purpose. A run records its turns into
# whatever project it ran in, and this benchmark's project is deleted
# when the run ends, so the default took every trace down with it.
#
# This is the checkout's own trace file, which is the one the training
# data builder already reads. Anywhere else and the rows would have to
# be found and pointed at by hand, which is how they got lost.
DEFAULT_TRACES = default_trace_path(ROOT)


# The last line carries the reason. 60 characters cut the exception off
# the end of it, leaving "src/orders.py defines last_price but does not
# import: Module" — the half that says what went wrong, gone.
WHY_LIMIT = 160


def why_from(output: str) -> str:
    """The one line of a failed check that says why, kept readable."""
    tail = output.strip().splitlines()
    return tail[-1][:WHY_LIMIT] if tail else "check failed"


def run(case: Case, model: str, steps: int, engine: str = "ollama",
        traces: Path | None = None, decide: str = "regex") -> dict:
    """Measure one case, and keep the turns it produced.

    The project is a temporary directory, so a run that records into it
    — which is the default since #192 — has its trace deleted along with
    the directory. Twenty runs leave nothing behind. `traces` points the
    recorder at a file that outlives the run instead.

    That data is the reason to bother: the fine-tune question is waiting
    on volume, each run is about twenty turns of a real task, and the
    trace ends with a row saying whether the run worked, so the builder
    can tell a run that did the job from a run that spent the budget.
    """
    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        for rel, body in {**BASE, **case.files}.items():
            dest = project / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body, encoding="utf-8")
        started = time.time()
        try:
            result = Agent(
                AgentOptions(
                    project=project,
                    task=case.task,
                    model=model,
                    steps=steps,
                    engine=engine,
                    record=traces,
                    decide=decide,
                    on_question=lambda _question: NO_HELP,
                )
            ).run()
        except Exception as exc:  # noqa: BLE001
            return {"case": case.key, "tier": case.tier, "worked": "error",
                    "why": f"{type(exc).__name__}: {exc}"}
        proc = subprocess.run([sys.executable, "-c", LOADER + case.check], cwd=project,
                              capture_output=True, text=True, timeout=60, check=False)
        worked = proc.returncode == 0
        why = ""
        if not worked:
            why = why_from(proc.stderr or proc.stdout)
        suite = ""
        if case.suite_must_pass:
            run_tests = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                cwd=project, capture_output=True, text=True, timeout=90, check=False,
            )
            suite = "green" if run_tests.returncode == 0 else "red"
            if worked and suite == "red":
                worked, why = False, "suite red"
        return {"case": case.key, "tier": case.tier,
                "worked": "yes" if worked else "no", "why": why, "suite": suite,
                "stopped": result.stopped,
                "asked": sum(1 for step in result.steps if step.action == "ask"),
                "steps": len(result.steps), "writes": list(result.writes),
                "seconds": round(time.time() - started, 1)}


ONE_RUN_WARNING = (
    "Only one pass. Ten of these fifteen cases changed verdict between "
    "identical runs on unchanged code, so a single number cannot show a "
    "gain or a regression. Use --repeat 5 before believing a comparison."
)


def report(rows: list[dict], passes: int) -> None:
    """Per-case pass rate and per-pass totals, written to stderr."""
    cases = list(dict.fromkeys(row["case"] for row in rows))
    by_case = {
        case: [r for r in rows if r["case"] == case] for case in cases
    }
    if passes > 1:
        print(f"\n{'case':<18}{'tier':<6}passed", file=sys.stderr)
        for case in cases:
            runs = by_case[case]
            marks = "".join("Y" if r["worked"] == "yes" else "." for r in runs)
            good = marks.count("Y")
            print(
                f"{case:<18}{runs[0]['tier']:<6}{marks}  {good}/{len(runs)}",
                file=sys.stderr,
            )
    for tier in sorted({row["tier"] for row in rows}):
        same = [r for r in rows if r["tier"] == tier]
        ok = sum(1 for r in same if r["worked"] == "yes")
        count = len({r["case"] for r in same})
        if passes > 1:
            per = [
                sum(
                    1
                    for r in same
                    if r["pass"] == n and r["worked"] == "yes"
                )
                for n in range(1, passes + 1)
            ]
            print(
                f"tier {tier}: {ok}/{len(same)} over {passes} passes "
                f"({'-'.join(str(x) for x in (min(per), max(per)))} of {count})",
                file=sys.stderr,
            )
        else:
            print(f"tier {tier}: {ok}/{len(same)}", file=sys.stderr)
    if passes > 1:
        totals = [
            sum(1 for r in rows if r["pass"] == n and r["worked"] == "yes")
            for n in range(1, passes + 1)
        ]
        steady = sum(
            1
            for case in cases
            if all(r["worked"] == "yes" for r in by_case[case])
        )
        moved = sum(
            1
            for case in cases
            if len({r["worked"] for r in by_case[case]}) > 1
        )
        print(
            f"\ntotals per pass: {totals}  of {len(cases)}", file=sys.stderr
        )
        print(
            f"passed every pass: {steady}   changed verdict: {moved}",
            file=sys.stderr,
        )
        floor = noise_floor(totals)
        if moved:
            print(
                f"This sample resolves a gap of {floor + 1} case(s) or more. "
                f"Identical code scored {min(totals)}-{max(totals)} across "
                f"{passes} passes, so a difference of {floor} or fewer is "
                "noise and must not be reported as a result.",
                file=sys.stderr,
            )
    else:
        print(f"\n{ONE_RUN_WARNING}", file=sys.stderr)


def noise_floor(totals: list[int]) -> int:
    """The largest gap this sample cannot tell from run-to-run variation.

    One configuration, measured repeatedly, moves on its own. Whatever it
    moves by is the smallest difference between *two* configurations that
    this sample could not have produced by chance, so a comparison closer
    than that says nothing.

    It is stated as a number because "smaller than the spread above" was
    not enough. In one night four readings were published or nearly
    published off gaps inside this floor: a 3-of-9 partial read as a
    regression from a change that scored 10 of 20 against a control of
    10 of 20, and an 11-versus-8 read as one model beating another.
    """
    return max(totals) - min(totals) if totals else 0


def _trace_path(argument: str) -> Path | None:
    """Where to record, or None when the run should keep nothing.

    An empty `--traces` is the off switch. It has to be something a
    person can type, because a benchmark measuring the recorder itself
    must be able to leave the file alone.
    """
    return Path(argument).expanduser() if argument else None


def _turns_in(path: Path | None) -> int:
    """How many turns the trace file holds. Zero when there is none."""
    if not path or not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure the agent on tasks of increasing size."
    )
    parser.add_argument("--tier", type=int, action="append", default=[])
    parser.add_argument("--model", default=AgentOptions(project=Path(".")).model)
    parser.add_argument(
        "--engine",
        default="ollama",
        help="ollama (local), or openai to measure a model too big to run here",
    )
    parser.add_argument("--steps", type=int, default=10)
    parser.add_argument(
        "--decide", default="regex", choices=("regex", "model"),
        help="how the kind of task is decided: the regex (default) or the fitted model",
    )
    parser.add_argument(
        "--traces",
        default=str(DEFAULT_TRACES),
        metavar="PATH",
        help="append every turn here, so the runs survive the benchmark "
        f"(default: {DEFAULT_TRACES}; empty string to record nothing)",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        metavar="N",
        help="run every case N times and report a pass rate (recommended: 5)",
    )
    args = parser.parse_args()
    if args.repeat < 1:
        print("--repeat must be at least 1", file=sys.stderr)
        return 2
    cases = [c for c in CASES if not args.tier or c.tier in args.tier]
    traces = _trace_path(args.traces)
    if traces:
        traces.parent.mkdir(parents=True, exist_ok=True)
    before = _turns_in(traces)
    rows: list[dict] = []
    for number in range(1, args.repeat + 1):
        for case in cases:
            row = run(case, args.model, args.steps, args.engine, traces, args.decide)
            row["pass"] = number
            rows.append(row)
            print(json.dumps(row), flush=True)
    report(rows, args.repeat)
    if traces:
        kept = _turns_in(traces) - before
        print(f"\nkept {kept} turn(s) in {traces}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

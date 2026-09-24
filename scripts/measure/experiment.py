#!/usr/bin/env python3
"""Run an experiment, check the result honestly, and keep the record.

Three commands, in the order the work actually goes:

  run      measure one arm and file the result under a name
  compare  put two filed results side by side and say whether the
           difference is real
  list     what has been filed

The point is not to save typing. It is to stop the three mistakes this
project has already made with its own numbers.

**A gap inside the noise floor is not a result.** `bench.py` prints the
floor; nothing made anyone apply it. In one evening four readings were
published or nearly published off gaps the sample could not resolve.
`compare` refuses to call such a difference anything but noise.

**A total hides its parts.** A change once scored 9 of 20 against 10 of
20 and looked like nothing. Underneath, one case went from 6/10 to 10/10
and another from 3/10 to 0/10. `compare` always prints per case.

**Variance and zero-step runs are the tell.** That same change scored
exactly 1 on all ten passes — a flat line on a benchmark that changes
verdict two thirds of the time — because a mechanical path had started
answering, wrongly, with no model at all. Both numbers are recorded and
both are shown.

Usage:

  python scripts/measure/experiment.py run baseline --tier 3 --repeat 10
  python scripts/measure/experiment.py run grammar-decoding --tier 3 --repeat 10
  python scripts/measure/experiment.py compare baseline grammar-decoding
  python scripts/measure/experiment.py list
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import platform
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs" / "experiments"


def _bench():
    """The benchmark, imported rather than reimplemented."""
    spec = importlib.util.spec_from_file_location(
        "py_harness_bench", Path(__file__).resolve().parent / "bench.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def commit() -> str:
    """The commit the arm was measured at, so a result can be replayed."""
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except OSError:
        return "unknown"
    return out.stdout.strip() or "unknown"


def dirty() -> bool:
    """True when the tree has uncommitted changes.

    An arm measured on a dirty tree cannot be replayed from its commit,
    so the record says so rather than implying otherwise.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain"],
            capture_output=True, text=True, timeout=30, check=False,
        )
    except OSError:
        return False
    return bool(out.stdout.strip())


@dataclass
class Result:
    """One measured arm."""

    name: str
    rows: list[dict]
    passes: int
    model: str
    engine: str
    tiers: list[int] = field(default_factory=list)
    commit: str = ""
    dirty: bool = False
    when: str = ""
    machine: str = ""
    seconds: float = 0.0

    @property
    def worked(self) -> int:
        return sum(1 for r in self.rows if r.get("worked") == "yes")

    @property
    def totals(self) -> list[int]:
        """Cases that worked, per pass. The spread of this is the floor."""
        return [
            sum(
                1
                for r in self.rows
                if r.get("pass") == n and r.get("worked") == "yes"
            )
            for n in range(1, self.passes + 1)
        ]

    @property
    def by_case(self) -> dict[str, tuple[int, int]]:
        good: dict[str, int] = collections.Counter()
        seen: dict[str, int] = collections.Counter()
        for row in self.rows:
            seen[row["case"]] += 1
            if row.get("worked") == "yes":
                good[row["case"]] += 1
        return {case: (good[case], seen[case]) for case in sorted(seen)}

    @property
    def errored(self) -> int:
        """Runs that never really ran: a missing model, a dead endpoint.

        These are not failures of the agent and must not be counted as
        one. A first run here scored 0 of 6 because the model named in
        the default was not installed, and without this the record would
        have read like a score of zero.
        """
        return sum(1 for r in self.rows if r.get("worked") == "error")

    @property
    def zero_step(self) -> int:
        """Runs that finished without asking the model anything.

        Either a repair the harness is sure of, or a bug that looks
        exactly like one. The count going up is the thing to look at.
        """
        return sum(1 for r in self.rows if r.get("steps") == 0)

    @property
    def asked(self) -> int:
        return sum(1 for r in self.rows if r.get("asked", 0) > 0)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "when": self.when,
            "commit": self.commit,
            "dirty": self.dirty,
            "machine": self.machine,
            "model": self.model,
            "engine": self.engine,
            "tiers": self.tiers,
            "passes": self.passes,
            "seconds": round(self.seconds, 1),
            "worked": self.worked,
            "runs": len(self.rows),
            "totals_per_pass": self.totals,
            "errored_runs": self.errored,
            "zero_step_runs": self.zero_step,
            "runs_that_asked": self.asked,
            "rows": self.rows,
        }

    @staticmethod
    def from_dict(data: dict) -> "Result":
        return Result(
            name=data["name"],
            rows=data["rows"],
            passes=data["passes"],
            model=data.get("model", "?"),
            engine=data.get("engine", "?"),
            tiers=data.get("tiers", []),
            commit=data.get("commit", ""),
            dirty=data.get("dirty", False),
            when=data.get("when", ""),
            machine=data.get("machine", ""),
            seconds=data.get("seconds", 0.0),
        )


def path_for(name: str) -> Path:
    return LEDGER / f"{name}.json"


def save(result: Result) -> Path:
    LEDGER.mkdir(parents=True, exist_ok=True)
    target = path_for(result.name)
    target.write_text(
        json.dumps(result.as_dict(), indent=2) + "\n", encoding="utf-8"
    )
    return target


def load(name: str) -> Result:
    target = path_for(name)
    if not target.is_file():
        raise SystemExit(
            f"no experiment called {name!r}. Filed so far: "
            f"{', '.join(filed()) or 'none'}"
        )
    return Result.from_dict(json.loads(target.read_text(encoding="utf-8")))


def filed() -> list[str]:
    if not LEDGER.is_dir():
        return []
    return sorted(p.stem for p in LEDGER.glob("*.json"))


def measure(name: str, tiers: list[int], model: str, engine: str,
            passes: int, steps: int) -> Result:
    bench = _bench()
    cases = [c for c in bench.CASES if not tiers or c.tier in tiers]
    if not cases:
        raise SystemExit(f"no cases in tier(s) {tiers}")
    started = time.time()
    rows: list[dict] = []
    for number in range(1, passes + 1):
        for case in cases:
            row = bench.run(case, model, steps, engine)
            row["pass"] = number
            rows.append(row)
            print(json.dumps(row), flush=True)
    return Result(
        name=name,
        rows=rows,
        passes=passes,
        model=model,
        engine=engine,
        tiers=sorted({c.tier for c in cases}),
        commit=commit(),
        dirty=dirty(),
        when=date.today().isoformat(),
        machine=f"{platform.system()} {platform.machine()}",
        seconds=time.time() - started,
    )


def verdict(a: Result, b: Result) -> tuple[str, int, int]:
    """Is the gap between two arms bigger than either could move alone?

    The floor is the wider of the two arms' own spreads. Measuring one
    configuration repeatedly moves it by that much, so two arms closer
    than that are not distinguishable by this sample.
    """
    bench = _bench()
    floor = max(bench.noise_floor(a.totals), bench.noise_floor(b.totals))
    gap = b.worked - a.worked
    if abs(gap) <= floor:
        return "noise", gap, floor
    return "real", gap, floor


def describe(result: Result) -> str:
    lines = [
        f"{result.name}: {result.worked}/{len(result.rows)}"
        f"   {result.model} via {result.engine}"
        f"   tiers {result.tiers or 'all'}   {result.passes} passes",
        f"  commit {result.commit}{' (DIRTY TREE)' if result.dirty else ''}"
        f"   {result.when}   {result.seconds / 60:.1f} min",
        f"  per pass {result.totals}",
        f"  zero-step runs {result.zero_step}   runs that asked {result.asked}"
        + (f"   ERRORED {result.errored}" if result.errored else ""),
    ]
    for case, (good, total) in result.by_case.items():
        lines.append(f"    {case:<16} {good}/{total}")
    return "\n".join(lines)


def compare(a: Result, b: Result) -> str:
    call, gap, floor = verdict(a, b)
    out = [describe(a), "", describe(b), ""]

    if a.model != b.model or a.engine != b.engine:
        out.append(
            f"  !! different models: {a.model}/{a.engine} against "
            f"{b.model}/{b.engine}. This compares two models, not two changes."
        )
    if a.tiers != b.tiers:
        out.append(
            f"  !! different tiers: {a.tiers} against {b.tiers}. "
            "These are not the same cases."
        )
    if a.errored or b.errored:
        out.append(
            f"  !! runs that never ran: {a.name} {a.errored}, {b.name} "
            f"{b.errored}. Those are a broken setup, not a failing agent, "
            "and they drag the total down on whichever arm has them."
        )
    if a.dirty or b.dirty:
        out.append("  !! one arm was measured on a dirty tree; it cannot be replayed.")

    out.append(f"{'case':<18}{a.name:>14}{b.name:>14}   moved")
    for case in sorted(set(a.by_case) | set(b.by_case)):
        ag, at = a.by_case.get(case, (0, 0))
        bg, bt = b.by_case.get(case, (0, 0))
        moved = ""
        if at and bt:
            delta = bg / bt - ag / at
            if abs(delta) >= 0.2:
                moved = f"  {'+' if delta > 0 else ''}{delta * 100:.0f}%"
        out.append(f"{case:<18}{f'{ag}/{at}':>14}{f'{bg}/{bt}':>14}{moved}")

    out.append("")
    if call == "noise":
        out.append(
            f"NOISE. {b.name} is {gap:+d} against {a.name}, and this sample "
            f"cannot resolve a gap of {floor} or fewer. Do not report it as a "
            "result. Look at the per-case rows above: a total of nothing can "
            "still hide two large effects cancelling out."
        )
    else:
        out.append(
            f"REAL. {b.name} is {gap:+d} against {a.name}, outside a floor "
            f"of {floor}."
        )
    if b.zero_step != a.zero_step:
        out.append(
            f"Zero-step runs moved {a.zero_step} -> {b.zero_step}. A run that "
            "writes without asking the model is either a repair the harness is "
            "sure of or a bug that looks just like one. Check which."
        )
    # A flat line matters because it means something stopped being
    # decided by the model. At a ceiling or a floor it means no such
    # thing: every case passing on every pass is flat by arithmetic.
    # Found by running this tool on a 20/20 arm and being warned about it.
    def _stuck(r) -> bool:
        if r.passes < 5 or len(set(r.totals)) != 1:
            return False
        cases = len(r.by_case)
        return r.totals[0] not in (0, cases)

    flat = [r for r in (a, b) if _stuck(r)]
    for result in flat:
        out.append(
            f"{result.name} scored the same on every pass ({result.totals[0]}). "
            "On a benchmark this noisy that usually means something stopped "
            "being decided by the model."
        )
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="measure one arm and file it")
    run.add_argument("name")
    run.add_argument("--tier", type=int, action="append", default=[])
    run.add_argument("--model", default="llama3.1:8b")
    run.add_argument("--engine", default="ollama")
    run.add_argument("--repeat", type=int, default=5, metavar="N")
    run.add_argument("--steps", type=int, default=10)

    cmp_ = sub.add_parser("compare", help="two filed arms, side by side")
    cmp_.add_argument("baseline")
    cmp_.add_argument("arm")

    sub.add_parser("list", help="what has been filed")

    args = parser.parse_args()

    if args.command == "run":
        if args.repeat < 2:
            print(
                "--repeat must be at least 2: one pass cannot show its own "
                "spread, and without that there is no floor to judge against.",
                file=sys.stderr,
            )
            return 2
        result = measure(
            args.name, args.tier, args.model, args.engine, args.repeat, args.steps
        )
        if result.errored == len(result.rows):
            why = next((r.get("why", "") for r in result.rows if r.get("why")), "")
            print(
                f"\nevery run errored, so there is nothing to file. {why}\n"
                f"Check the model exists: ollama list | grep {args.model}",
                file=sys.stderr,
            )
            return 2
        target = save(result)
        print("\n" + describe(result), file=sys.stderr)
        print(f"\nfiled as {target.relative_to(ROOT)}", file=sys.stderr)
        return 0

    if args.command == "compare":
        print(compare(load(args.baseline), load(args.arm)))
        return 0

    if args.command == "list":
        names = filed()
        if not names:
            print("nothing filed yet")
            return 0
        for name in names:
            result = load(name)
            print(
                f"  {name:<24} {result.worked}/{len(result.rows)}"
                f"   {result.model}   {result.when}   {result.commit}"
                f"{'  DIRTY' if result.dirty else ''}"
            )
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

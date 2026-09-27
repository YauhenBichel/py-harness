#!/usr/bin/env python3
"""Which benchmark cases would the two deciders route differently?

An A/B of `--decide regex` against `--decide model` can only move on a
case where the two disagree about what kind of task it is. Run this
before the A/B and it says which cases those are; run it after and it
says whether a moved case was one of them. Every case where they agree
is a control: the run is the same in both arms and any gap on it is the
noise floor showing.

The regex column is the harness's own `looks_like_bugfix` with nothing
decided; the model column is `harness.decide.intent.intent_of`, which
needs the embedding model behind Ollama and says so when it cannot.

Usage:
  python scripts/measure/intent_routes.py            # prints, and files decide-routes.json
  python scripts/measure/intent_routes.py --tier 5 --tier 7
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import bench  # noqa: E402

from harness import task as T  # noqa: E402
from harness.decide.intent import intent_of  # noqa: E402

LEDGER = ROOT / "docs" / "experiments"


def routes(cases: list) -> list[dict]:
    rows: list[dict] = []
    for case in cases:
        T.set_decided_intent(case.task, None)
        regex = T.looks_like_bugfix(case.task)
        decision = intent_of(case.task)
        rows.append({
            "case": case.key,
            "tier": case.tier,
            "task": case.task,
            "regex_bugfix": regex,
            "model_intent": decision.intent if decision else None,
            "model_bugfix": (decision.intent == "bugfix") if decision else None,
            "margin": round(decision.margin, 3) if decision else None,
            "runner_up": decision.runner_up if decision else None,
            "differ": (decision.intent == "bugfix") != regex if decision else None,
        })
    return rows


def describe(rows: list[dict]) -> str:
    lines = [f"{'case':<16}{'tier':>4}  {'regex':<6}{'model':<16}{'margin':>7}  "]
    for r in rows:
        model = r["model_intent"] or "unavailable"
        margin = f"{r['margin']:.2f}" if r["margin"] is not None else "—"
        mark = "  <-- routes differently" if r["differ"] else ""
        lines.append(f"{r['case']:<16}{r['tier']:>4}  {str(r['regex_bugfix']):<6}"
                     f"{model:<16}{margin:>7}{mark}")
    differ = [r["case"] for r in rows if r["differ"]]
    lines.append("")
    if any(r["model_intent"] is None for r in rows):
        lines.append("the embedding model did not answer; nothing here compares the two")
    elif differ:
        lines.append(f"{len(differ)} of {len(rows)} route differently: {', '.join(differ)}. "
                     "Only these can move in a regex-against-model A/B; the rest are controls.")
    else:
        lines.append(f"0 of {len(rows)} route differently. An A/B on these cases "
                     "compares the same run with itself.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tier", type=int, action="append", default=[])
    args = parser.parse_args()
    cases = [c for c in bench.CASES if not args.tier or c.tier in args.tier]
    rows = routes(cases)
    print(describe(rows))
    if all(r["model_intent"] is None for r in rows):
        print("not filed: the model never answered", file=sys.stderr)
        return 2
    LEDGER.mkdir(parents=True, exist_ok=True)
    target = LEDGER / "decide-routes.json"
    target.write_text(json.dumps({
        "when": date.today().isoformat(),
        "tiers": sorted({c.tier for c in cases}),
        "differ": [r["case"] for r in rows if r["differ"]],
        "rows": rows,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"filed as {target.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

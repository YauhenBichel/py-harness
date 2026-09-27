#!/usr/bin/env python3
"""How easy must a question be before a small model answers it reliably?

The design under test: take one hard task, reduce it to a pipeline of
very small questions, and let a small local model decide each one. The
harness composes the answers; the model never writes anything.

The literature half-supports it. Restricting a model to a classification
improves it (one benchmark went 41.6 to 60.3) while asking it to reason
freely collapses it (76.0 to 49.3). Models also answer sub-questions they
cannot compose — the gap is about 40% and flat from 1B to 175B — which
is exactly the split this design wants, because the pipeline composes,
not the model.

The arithmetic is the catch. A chain of `n` questions each right with
probability `p` is right end to end about `p**n` times, unless something
checks each step. At 58% five questions is 6%. At 95% it is 77%.

The rungs, easiest first. Each says whether a parser could answer it
instead, and that claim is checked against `ast` rather than asserted,
because it is the real question: a question easy enough for a 0.8B is
often easy enough for a parser, and then no model is needed at all.

  syntax      is this valid Python                     parser: yes
  defines     does it define a function called X        parser: yes
  signature   does that function take an argument X     parser: yes
  intent      what is this task asking for              parser: no
  naming      is this a descriptive function name       parser: no
  correct     does this do what the task asks           parser: no

Usage:
  python scripts/measure/judge_ladder.py --model factory-qwen3.5-0.8b:q4_K_M
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "docs" / "experiments"

GOOD_WORDCOUNT = "def word_count(text: str) -> int:\n    return len(text.split())"
BAD_WORDCOUNT = "def word_count(prices: list[int]) -> int:\n    return len(prices)"
GOOD_CLAMP = (
    "def clamp(value: int, low: int, high: int) -> int:\n"
    "    return max(low, min(value, high))"
)
BROKEN_SYNTAX = "def word_count(text:\n    return len(text.split())"
ORPHAN_TEST = (
    "def test_apply_discount(self) -> None:\n"
    "    self.assertEqual(apply_discount(100, 20), 80.0)"
)


@dataclass(frozen=True)
class Q:
    rung: str
    key: str
    question: str
    answer: bool
    computable: bool


QUESTIONS: tuple[Q, ...] = (
    Q("syntax", "good", f"Is this valid Python?\n\n{GOOD_WORDCOUNT}", True, True),
    Q("syntax", "broken", f"Is this valid Python?\n\n{BROKEN_SYNTAX}", False, True),
    Q("syntax", "clamp", f"Is this valid Python?\n\n{GOOD_CLAMP}", True, True),
    Q("syntax", "orphan", f"Is this valid Python?\n\n{ORPHAN_TEST}", True, True),
    Q("defines", "yes",
      f"Does this code define a function called word_count?\n\n{GOOD_WORDCOUNT}", True, True),
    Q("defines", "no",
      f"Does this code define a function called slugify?\n\n{GOOD_WORDCOUNT}", False, True),
    Q("defines", "clamp-yes",
      f"Does this code define a function called clamp?\n\n{GOOD_CLAMP}", True, True),
    Q("defines", "clamp-no",
      f"Does this code define a function called average?\n\n{GOOD_CLAMP}", False, True),
    Q("signature", "text",
      f"Does the function take an argument called text?\n\n{GOOD_WORDCOUNT}", True, True),
    Q("signature", "prices",
      f"Does the function take an argument called text?\n\n{BAD_WORDCOUNT}", False, True),
    Q("signature", "three",
      f"Does the function take an argument called high?\n\n{GOOD_CLAMP}", True, True),
    Q("signature", "missing",
      f"Does the function take an argument called default?\n\n{GOOD_CLAMP}", False, True),
    Q("intent", "new-module",
      'Task: "create a new module with a function slugify(text)".\n'
      "Does this task ask for a new file to be created?", True, False),
    Q("intent", "fix-bug",
      'Task: "fix the bug in last_price in src/orders.py: it raises IndexError".\n'
      "Does this task ask for a new file to be created?", False, False),
    Q("intent", "add-test",
      'Task: "write a unit test for apply_discount in src/orders.py".\n'
      "Does this task ask for a test to be written?", True, False),
    Q("intent", "add-function",
      'Task: "add a function average(values) that returns the mean".\n'
      "Does this task ask for a test to be written?", False, False),
    Q("intent", "rename",
      'Task: "rename calc to compute_total across the project".\n'
      "Does this task ask for an existing name to be changed?", True, False),
    Q("intent", "env",
      'Task: "add a function env_flag(name, default) reading an environment '
      'variable".\nDoes this task involve reading the environment?', True, False),
    Q("naming", "good",
      "Is `calculate_total` a descriptive name for a function that adds up "
      "prices?", True, False),
    Q("naming", "bad",
      "Is `do_it` a descriptive name for a function that adds up prices?", False, False),
    Q("naming", "opaque",
      "Is `x1` a descriptive name for a function that formats a date?", False, False),
    Q("naming", "fine",
      "Is `read_env_file` a descriptive name for a function that reads "
      "KEY=VALUE lines from a file?", True, False),
    Q("correct", "wordcount-good",
      'Task: "count the words in a string".\n\n' + GOOD_WORDCOUNT +
      "\n\nDoes this code correctly do what the task asks?", True, False),
    Q("correct", "wordcount-bad",
      'Task: "count the words in a string".\n\n' + BAD_WORDCOUNT +
      "\n\nDoes this code correctly do what the task asks?", False, False),
    Q("correct", "clamp-good",
      'Task: "keep a value inside a range".\n\n' + GOOD_CLAMP +
      "\n\nDoes this code correctly do what the task asks?", True, False),
    Q("correct", "orphan-test",
      'Task: "write a unit test for apply_discount".\n\n' + ORPHAN_TEST +
      "\n\nWill unittest discover and run this test?", False, False),
)

ASK = "{question}\n\nAnswer with one word: yes or no. Nothing else."
ORDER = ("syntax", "defines", "signature", "intent", "naming", "correct")


def check_computable() -> list[str]:
    """Prove the 'a parser could answer this' claim rather than assert it."""
    wrong = []
    try:
        ast.parse(GOOD_WORDCOUNT)
    except SyntaxError:
        wrong.append("GOOD_WORDCOUNT should parse")
    try:
        ast.parse(BROKEN_SYNTAX)
        wrong.append("BROKEN_SYNTAX should not parse")
    except SyntaxError:
        pass
    tree = ast.parse(GOOD_WORDCOUNT)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    if names != {"word_count"}:
        wrong.append(f"defines: expected word_count, found {names}")
    args = {a.arg for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
            for a in n.args.args}
    if args != {"text"}:
        wrong.append(f"signature: expected text, found {args}")
    return wrong


_YES = re.compile(r"\byes\b", re.IGNORECASE)
_NO = re.compile(r"\bno\b", re.IGNORECASE)


def read_answer(text: str) -> bool | None:
    stripped = re.sub(r"<think>.*?</think>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    yes, no = bool(_YES.search(stripped)), bool(_NO.search(stripped))
    if yes == no:
        return None
    return yes


def ask(model: str, prompt: str, host: str, timeout: int) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0},
        "keep_alive": "10m",
    }).encode()
    request = urllib.request.Request(
        f"{host}/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return str((json.loads(response.read().decode()).get("message") or {})
                   .get("content", ""))


def run(model: str, host: str, repeat: int, timeout: int) -> dict:
    rungs: dict[str, dict] = {}
    started = time.time()
    for _ in range(repeat):
        for q in QUESTIONS:
            slot = rungs.setdefault(
                q.rung, {"right": 0, "wrong": 0, "unusable": 0, "computable": q.computable}
            )
            try:
                reply = ask(model, ASK.format(question=q.question), host, timeout)
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                print(f"  {q.rung}/{q.key}: {exc}", file=sys.stderr)
                slot["unusable"] += 1
                continue
            said = read_answer(reply)
            if said is None:
                slot["unusable"] += 1
            elif said == q.answer:
                slot["right"] += 1
            else:
                slot["wrong"] += 1
    for slot in rungs.values():
        answered = slot["right"] + slot["wrong"]
        slot["answered"] = answered
        slot["accuracy"] = round(slot["right"] / answered, 3) if answered else None
    return {"model": model, "repeat": repeat,
            "seconds": round(time.time() - started, 1), "rungs": rungs}


def describe(result: dict) -> str:
    lines = [
        f"{result['model']}   {result['repeat']} passes   {result['seconds'] / 60:.1f} min",
        "",
        f"{'rung':<12}{'correct':>10}{'accuracy':>11}{'unusable':>10}"
        "   a parser could answer it",
    ]
    for rung in ORDER:
        slot = result["rungs"].get(rung)
        if not slot:
            continue
        score = f"{slot['right']}/{slot['answered']}"
        acc = "—" if slot["accuracy"] is None else f"{slot['accuracy']:.0%}"
        note = "yes — so no model is needed" if slot["computable"] else "no"
        lines.append(f"{rung:<12}{score:>10}{acc:>11}{slot['unusable']:>10}   {note}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", required=True)
    parser.add_argument("--host",
                        default=os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--name", default="")
    args = parser.parse_args()

    broken = check_computable()
    if broken:
        print("fixtures do not match their claims: " + "; ".join(broken), file=sys.stderr)
        return 2
    result = run(args.model, args.host, args.repeat, args.timeout)
    print(describe(result), file=sys.stderr)
    if not any(s["answered"] for s in result["rungs"].values()):
        print(f"\nnothing answered; check the model and host {args.host}", file=sys.stderr)
        return 2
    LEDGER.mkdir(parents=True, exist_ok=True)
    name = args.name or f"ladder-{args.model.replace(':', '_').replace('/', '_')}"
    target = LEDGER / f"{name}.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"\nfiled as {target.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

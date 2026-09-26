#!/usr/bin/env python3
"""Build a large labelled set of task phrasings, one label per intent.

The decisions the harness makes with regular expressions — is this a
bug fix, a test to write, a rename, a question — have never been
measured on more than a handful of hand-written cases. This makes the
sample large enough to trust.

Every phrasing is generated in two passes and kept only if both agree:

  1. *Write* — a large local model is asked for realistic requests that
     a Python developer would type, for one named intent, in a named
     style. Style is varied on purpose: terse, chatty, with file paths,
     with symptoms and no keywords, as a ticket, as a chat message.
  2. *Label blind* — the same model is shown each phrasing alone, with
     no hint of how it was made, and asked which intent it is. A
     phrasing whose blind label disagrees with the intent it was written
     for is dropped. That is the quality gate: the label is not "what we
     asked for", it is "what a reader sees".

Hand-labelled phrasings from the probes are kept apart as `gold` and are
never used for training, so the model is also scored on text no
generator produced.

Output, under data/intent/:
  train.jsonl   generated, agreed, 80%
  test.jsonl    generated, agreed, 20%, stratified
  gold.jsonl    hand-labelled, never trained on
  rejected.jsonl  what the blind pass threw out, so the gate can be audited

Usage:
  python scripts/measure/intent_dataset.py --model qwen3-coder:30b --per-style 20
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "intent"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ollama_client  # noqa: E402

# The intents, each with what it means and two honest examples. These
# mirror the decisions in src/harness/task.py; the mapping to its
# functions lives in intent_model.py.
INTENTS: dict[str, dict] = {
    "bugfix": {
        "means": "something already written is broken and should be corrected",
        "examples": ["the totals come out one too low",
                     "fix the IndexError in last_price"],
    },
    "add_feature": {
        "means": "add a new function, method or small component that does not exist yet",
        "examples": ["add a function average(values) that returns the mean",
                     "we need a helper that slugifies a title"],
    },
    "write_tests": {
        "means": "write or extend tests for code that already exists",
        "examples": ["write a unit test for apply_discount",
                     "cover read_env_file with tests"],
    },
    "rename_or_move": {
        "means": "rename a symbol or file, or move code between files, without changing behaviour",
        "examples": ["rename calc to compute_total everywhere",
                     "move the helpers into their own module"],
    },
    "new_package": {
        "means": "create a new package, project or module from scratch",
        "examples": ["scaffold a package for the billing code",
                     "create a new module for date helpers"],
    },
    "question": {
        "means": "ask how something works or what it does; nothing should change",
        "examples": ["what does apply_source refuse?",
                     "how does the loader pick a module"],
    },
    "refactor": {
        "means": "restructure working code for clarity or design, keeping behaviour",
        "examples": ["split this long function into smaller ones",
                     "the orders module does too much, break it up"],
    },
    "docs": {
        "means": "write or improve documentation, docstrings, comments or a README",
        "examples": ["add a docstring to read_env_file",
                     "write a README section for the CLI"],
    },
    "review": {
        "means": "review code or a change and report on it, changing nothing",
        "examples": ["review the open pull request",
                     "look over orders.py and tell me what is wrong with it"],
    },
    "ship": {
        "means": "commit, push, open a pull request, merge, tag or release",
        "examples": ["commit this and open a PR",
                     "merge the branch once checks pass"],
    },
    "platform_ops": {
        "means": "environment variables, paths, config files, retries, virtualenvs, OS differences",
        "examples": ["read a boolean flag from an environment variable",
                     "find the python inside the venv on windows and mac"],
    },
    "script_cli": {
        "means": "a runnable script or command-line tool with arguments",
        "examples": ["write a script that reports open issues",
                     "add a --verbose flag to the command"],
    },
}

STYLES: tuple[tuple[str, str], ...] = (
    ("terse", "very short, like a commit subject or a two-second chat message"),
    ("descriptive", "a full sentence or two, as a careful colleague would write in a ticket"),
    ("symptom", "describes what is observed or wanted WITHOUT naming the category and "
                "WITHOUT using obvious keywords for it"),
    ("with_paths", "mentions specific file paths, function names or modules"),
    ("casual", "informal, possibly with a typo or lowercase, as typed in a hurry"),
)

WRITE = """You are helping build a dataset of realistic requests that a Python developer types to a coding assistant.

Write {n} DISTINCT requests that are clearly of this kind:

  kind: {intent}
  meaning: {means}
  examples of the kind: {examples}

Style for this batch: {style}.

Rules:
- Each request must be something a real developer would plausibly type.
- Vary vocabulary, length and sentence shape. Do not reuse a template.
- Use different function names, file names and domains across items (orders, invoices, users, parsing, dates, config, http, files, reports).
- Do NOT copy the examples.
- Output ONLY a JSON array of {n} strings. No commentary, no numbering, no markdown fence."""

LABEL = """A Python developer typed this request to a coding assistant:

"{task}"

Which ONE of these kinds is it? Answer with the kind's name only.

{menu}

Answer with exactly one name from the list, nothing else."""


def chat(model: str, prompt: str, host: str, timeout: int, temperature: float) -> str:
    text = ollama_client.chat(host, model, prompt, timeout, temperature, label="gen")
    return re.sub(r"<think>.*?</think>", " ", text, flags=re.DOTALL | re.IGNORECASE)


def parse_array(text: str) -> list[str]:
    """The model was told 'JSON array only'. Be tolerant of a fence anyway."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end < 0:
        return []
    try:
        items = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    return [s.strip() for s in items if isinstance(s, str) and s.strip()]


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def generate(model: str, host: str, timeout: int, per_style: int) -> list[dict]:
    rows: list[dict] = []
    for intent, spec in INTENTS.items():
        for style_name, style in STYLES:
            prompt = WRITE.format(
                n=per_style, intent=intent, means=spec["means"],
                examples=json.dumps(spec["examples"]), style=style,
            )
            try:
                items = parse_array(chat(model, prompt, host, timeout, temperature=0.9))
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                print(f"  {intent}/{style_name}: {exc}", file=sys.stderr)
                items = []
            print(f"  wrote {len(items):>3}  {intent}/{style_name}", file=sys.stderr)
            for task in items:
                rows.append({"task": task, "intent": intent, "style": style_name})
    return rows


def label_blind(model: str, host: str, timeout: int, rows: list[dict]) -> None:
    menu = "\n".join(f"  {name}: {spec['means']}" for name, spec in INTENTS.items())
    names = set(INTENTS)
    for i, row in enumerate(rows, 1):
        try:
            said = chat(model, LABEL.format(task=row["task"], menu=menu),
                        host, timeout, temperature=0).strip().lower()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            row["blind"] = f"error: {exc}"
            continue
        found = [n for n in names if re.search(rf"\b{re.escape(n)}\b", said)]
        row["blind"] = found[0] if len(found) == 1 else (found[0] if found else said[:40])
        if i % 50 == 0:
            print(f"  labelled {i}/{len(rows)}", file=sys.stderr)


def load_gold() -> list[dict]:
    """The hand-labelled phrasings from the probes, mapped to intents."""
    gold: list[dict] = []
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import intent_probe  # type: ignore
    except Exception:  # noqa: BLE001
        return gold
    for case in list(intent_probe.CASES) + list(intent_probe.TRAINING):
        gold.append({
            "task": case.task,
            # The probe only labels bugfix-or-not; everything else is "other".
            "intent": "bugfix" if case.is_bugfix else "other",
            "source": "hand",
        })
    return gold


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", required=True)
    parser.add_argument("--host",
                        default=os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434")
    parser.add_argument("--per-style", type=int, default=20)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--skip-blind", action="store_true",
                        help="keep everything generated; no agreement gate")
    args = parser.parse_args()

    started = time.time()
    print(f"generating {len(INTENTS)} intents x {len(STYLES)} styles x "
          f"{args.per_style} with {args.model}", file=sys.stderr)
    rows = generate(args.model, args.host, args.timeout, args.per_style)

    # Dedupe, and keep nothing that is also in the gold set.
    gold = load_gold()
    gold_norm = {norm(g["task"]) for g in gold}
    seen: set[str] = set()
    unique: list[dict] = []
    for row in rows:
        key = norm(row["task"])
        if key in seen or key in gold_norm or len(key) < 8:
            continue
        seen.add(key)
        unique.append(row)
    print(f"  {len(rows)} written, {len(unique)} unique and not in gold", file=sys.stderr)

    if not args.skip_blind:
        print("blind labelling", file=sys.stderr)
        label_blind(args.model, args.host, args.timeout, unique)
    kept = [r for r in unique if args.skip_blind or r.get("blind") == r["intent"]]
    rejected = [r for r in unique if not args.skip_blind and r.get("blind") != r["intent"]]
    print(f"  {len(kept)} agreed, {len(rejected)} rejected by the blind pass",
          file=sys.stderr)

    # Stratified split, deterministic.
    rng = random.Random(args.seed)
    train: list[dict] = []
    test: list[dict] = []
    for intent in INTENTS:
        bucket = [r for r in kept if r["intent"] == intent]
        rng.shuffle(bucket)
        cut = max(1, int(len(bucket) * 0.2)) if bucket else 0
        test.extend(bucket[:cut])
        train.extend(bucket[cut:])
    for row in train + test:
        row["source"] = "generated"
        row["id"] = hashlib.sha1(norm(row["task"]).encode()).hexdigest()[:10]

    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in (("train", train), ("test", test), ("gold", gold),
                       ("rejected", rejected)):
        (OUT / f"{name}.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in data),
            encoding="utf-8",
        )
    summary = {
        "model": args.model, "per_style": args.per_style,
        "written": len(rows), "unique": len(unique), "kept": len(kept),
        "rejected": len(rejected), "train": len(train), "test": len(test),
        "gold": len(gold), "minutes": round((time.time() - started) / 60, 1),
        "per_intent": {i: sum(1 for r in kept if r["intent"] == i) for i in INTENTS},
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

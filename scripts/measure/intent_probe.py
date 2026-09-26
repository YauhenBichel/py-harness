#!/usr/bin/env python3
"""At a decision the harness already makes with a regex, what does better?

py-harness reduces a task to small decisions before any model runs.
`task.py` holds thirty-one regular expressions and about twenty
`looks_like_*` functions; each answers a narrow yes/no question about
the task — is this a bug fix, a rename, a question, a new package.

So the architecture "split the hard task into very small decisions" is
already here. What was never measured is how often those decisions are
wrong. `looks_like_bugfix` fires on the words fix, bug, nameerror, crash
and defect, and a person who writes "the totals come out one too low"
has described a bug without using any of them.

Three deciders answer the same question on the same held-out cases:

  regex   the one in task.py today                     no model
  prompt  a small chat model asked yes/no             a model, unpinned
  trained a decision model: sentence embeddings and   a model, but a
          a logistic regression fit on other           tiny fitted one
          phrasings, never on the test cases

The third is the one the literature backs for small models — a
classifier over features, not a chat model asked to reason. Logistic
regression on small-model embeddings beat zero-shot prompting of the
same model 80% to 69% in one comparison. This measures whether that
holds at the decision this harness actually makes.

The training phrasings and the test cases are kept disjoint on purpose,
and that is checked, because a classifier that has seen the test cases
measures memory.

Usage:
  python scripts/measure/intent_probe.py --model factory-qwen3.5-0.8b:q4_K_M
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ollama_client  # noqa: E402
LEDGER = ROOT / "docs" / "experiments"

from harness.task import looks_like_bugfix  # noqa: E402


@dataclass(frozen=True)
class Case:
    task: str
    is_bugfix: bool
    note: str = ""


# ---------------------------------------------------------------------
# Held-out test cases. Labelled by hand, each with the reason.
# ---------------------------------------------------------------------
CASES: tuple[Case, ...] = (
    # plainly a bug fix, using the words the regex knows
    Case("fix the bug in last_price in src/orders.py", True, "keyword: fix, bug"),
    Case("fix the NameError in src/orders.py", True, "keyword: fix, nameerror"),
    Case("there is a crash in the report writer, sort it out", True, "keyword: crash"),
    # plainly a bug fix, described the way people describe them
    Case("the totals come out one too low", True, "off-by-one, no keyword"),
    Case("last_price raises IndexError on a full list", True, "names the exception"),
    Case("average() divides by zero when the list is empty", True, "states the fault"),
    Case("the config loader returns True for FLAG=false", True, "wrong behaviour"),
    Case("slugify leaves spaces in the output when it should use hyphens", True,
         "wrong output"),
    Case("retry gives up after the first failure instead of trying again", True,
         "wrong behaviour"),
    # not a bug fix, however it is phrased
    Case("add a function average(values) that returns the mean", False, "new feature"),
    Case("write a unit test for apply_discount", False, "test writing"),
    Case("create a new module with a function slugify(text)", False, "new module"),
    Case("rename calc to compute_total across the project", False, "a rename"),
    Case("what does apply_source refuse?", False, "a question"),
    Case("add a docstring to read_env_file", False, "documentation"),
    # contains a keyword but is not a bug fix
    Case("add a function fix_encoding(text) that repairs mojibake", False,
         'contains "fix", asks for a new function'),
    Case("write a test that reproduces the crash in last_price", False,
         'contains "crash", asks for a test'),
    Case("document how we fix flaky tests in CONTRIBUTING", False,
         'contains "fix", asks for documentation'),
    Case("rename the bug_report module to issue_report", False,
         'contains "bug", is a rename'),
)

# ---------------------------------------------------------------------
# Training phrasings for the decision model. None of these is a test
# case, and that is asserted before anything is fitted.
# ---------------------------------------------------------------------
TRAINING: tuple[Case, ...] = (
    Case("fix the off-by-one in paginate", True),
    Case("the parser crashes on an empty file", True),
    Case("compute_total returns 0 for a non-empty list", True),
    Case("format_date raises ValueError on valid input", True),
    Case("the login form accepts an empty password", True),
    Case("sort_items puts None before every other value and it should not", True),
    Case("the cache is never invalidated after a write", True),
    Case("read_env_file drops the last line of the file", True),
    Case("the CLI exits 0 even when a step failed", True),
    Case("the discount is applied twice on a repeated order", True),
    Case("the wrong file gets deleted when the path has a space in it", True),
    Case("timestamps are printed in the wrong time zone", True),
    Case("this KeyError should not happen when the key is present", True),
    Case("the retry counter never decrements", True),
    Case("the totals page shows yesterday's figures", True),
    Case("negative quantities are accepted by the order form", True),
    Case("the tests pass locally and fail in CI because of the temp dir", True),
    Case("clamp returns the low bound when the value is above the high bound", True),
    Case("add a function median(values)", False),
    Case("write tests for the report writer", False),
    Case("create a package for the billing code", False),
    Case("rename total to grand_total everywhere", False),
    Case("how does the loader pick a module?", False),
    Case("move the helpers into their own file", False),
    Case("add type hints to the orders module", False),
    Case("write a README section for the CLI", False),
    Case("add a --verbose flag to the command", False),
    Case("what is the difference between edit and patch?", False),
    Case("split orders.py into orders and pricing", False),
    Case("add a function that fixes up whitespace in a string", False),
    Case("write a regression test for the crash we saw last week", False),
    Case("explain why the bug tracker uses that schema", False),
    Case("refactor the crash handler into smaller functions", False),
    Case("review the fix in the open pull request", False),
    Case("add a script that reports open bugs from the tracker", False),
    Case("document the known defects in the release notes", False),
)

ASK = (
    'A developer wrote this task for a coding assistant:\n\n"{task}"\n\n'
    "Is the developer reporting something that is broken and asking for it "
    "to be corrected?\n(Adding a new feature, writing a test, renaming, or "
    "asking a question is not.)\n\n"
    "Answer with one word: yes or no. Nothing else."
)

_YES = re.compile(r"\byes\b", re.IGNORECASE)
_NO = re.compile(r"\bno\b", re.IGNORECASE)


def read_answer(text: str) -> bool | None:
    stripped = re.sub(r"<think>.*?</think>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    yes, no = bool(_YES.search(stripped)), bool(_NO.search(stripped))
    if yes == no:
        return None
    return yes


def ask(model: str, prompt: str, host: str, timeout: int) -> str:
    return ollama_client.chat(host, model, prompt, timeout, label="ask")


def embed(model: str, texts: list[str], host: str, timeout: int) -> np.ndarray:
    vectors = np.asarray(ollama_client.embed(host, model, texts, timeout), dtype=np.float64)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


def fit_logistic(x: np.ndarray, y: np.ndarray, steps: int = 3000,
                 rate: float = 0.5, l2: float = 1e-3) -> tuple[np.ndarray, float]:
    """Plain logistic regression by gradient descent. No library needed.

    Thirty-odd examples in a thousand dimensions overfit trivially, so a
    little L2 keeps the weights honest. The point is not the best
    classifier; it is whether a tiny fitted one beats a regex at all.
    """
    weights = np.zeros(x.shape[1])
    bias = 0.0
    for _ in range(steps):
        logits = x @ weights + bias
        p = 1 / (1 + np.exp(-logits))
        error = p - y
        weights -= rate * (x.T @ error / len(y) + l2 * weights)
        bias -= rate * error.mean()
    return weights, bias


def predict_logistic(x: np.ndarray, weights: np.ndarray, bias: float) -> np.ndarray:
    return (x @ weights + bias) > 0


def check_disjoint() -> list[str]:
    test = {c.task.strip().lower() for c in CASES}
    return [c.task for c in TRAINING if c.task.strip().lower() in test]


def run(model: str, embed_model: str, host: str, repeat: int, timeout: int) -> dict:
    started = time.time()
    truth = np.array([c.is_bugfix for c in CASES])

    # --- arm 1: the regex ---------------------------------------------
    regex = np.array([looks_like_bugfix(c.task) for c in CASES])

    # --- arm 2: the trained decision model ----------------------------
    trained = None
    trained_error = ""
    try:
        train_x = embed(embed_model, [c.task for c in TRAINING], host, timeout)
        train_y = np.array([c.is_bugfix for c in TRAINING], dtype=np.float64)
        test_x = embed(embed_model, [c.task for c in CASES], host, timeout)
        weights, bias = fit_logistic(train_x, train_y)
        trained = predict_logistic(test_x, weights, bias)
    except (urllib.error.URLError, TimeoutError, OSError, KeyError) as exc:
        trained_error = str(exc)

    # --- arm 3: the small chat model, prompted -------------------------
    prompted: list[bool | None] = []
    unsteady = 0
    for case in CASES:
        said: list[bool | None] = []
        for _ in range(repeat):
            try:
                said.append(read_answer(ask(model, ASK.format(task=case.task), host, timeout)))
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                print(f"  {case.task[:40]}: {exc}", file=sys.stderr)
                said.append(None)
        usable = [s for s in said if s is not None]
        prompted.append(sum(usable) * 2 > len(usable) if usable else None)
        if len(set(usable)) > 1:
            unsteady += 1

    rows = []
    for i, case in enumerate(CASES):
        rows.append(
            {
                "task": case.task,
                "truth": case.is_bugfix,
                "note": case.note,
                "regex": bool(regex[i]),
                "trained": None if trained is None else bool(trained[i]),
                "prompted": prompted[i],
            }
        )

    def score(column):
        answered = [(r[column], r["truth"]) for r in rows if r[column] is not None]
        right = sum(1 for got, want in answered if got == want)
        fp = sum(1 for got, want in answered if got and not want)
        fn = sum(1 for got, want in answered if not got and want)
        return {
            "right": right,
            "answered": len(answered),
            "accuracy": round(right / len(answered), 3) if answered else None,
            "false_positives": fp,
            "false_negatives": fn,
        }

    return {
        "model": model,
        "embed_model": embed_model,
        "repeat": repeat,
        "cases": len(CASES),
        "training_examples": len(TRAINING),
        "arms": {
            "regex": score("regex"),
            "trained": score("trained"),
            "prompted": score("prompted"),
        },
        "prompted_unsteady": unsteady,
        "trained_error": trained_error,
        "seconds": round(time.time() - started, 1),
        "rows": rows,
    }


def describe(result: dict) -> str:
    n = result["cases"]
    lines = [
        f"{n} held-out cases   trained on {result['training_examples']} other phrasings"
        f"   {result['seconds'] / 60:.1f} min",
        "",
        f"{'decider':<40}{'right':>8}{'accuracy':>10}{'FP':>5}{'FN':>5}",
    ]
    names = {
        "regex": "regex in task.py today",
        "trained": f"decision model ({result['embed_model']} + logistic)",
        "prompted": f"prompted yes/no ({result['model']})",
    }
    for arm, label in names.items():
        s = result["arms"][arm]
        acc = "—" if s["accuracy"] is None else f"{s['accuracy']:.0%}"
        score = f"{s['right']}/{s['answered']}"
        lines.append(
            f"{label:<40}{score:>8}{acc:>10}{s['false_positives']:>5}"
            f"{s['false_negatives']:>5}"
        )
    if result["trained_error"]:
        lines.append(f"  (decision model did not run: {result['trained_error']})")
    if result["prompted_unsteady"]:
        lines.append(f"  (prompted model changed its answer on {result['prompted_unsteady']} cases across passes)")
    lines.append("")
    lines.append(f"{'task':<50}{'truth':>6}{'regex':>7}{'train':>7}{'prompt':>7}")
    mark = lambda v: "—" if v is None else ("yes" if v else "no")  # noqa: E731
    for r in result["rows"]:
        lines.append(
            f"{r['task'][:48]:<50}{mark(r['truth']):>6}{mark(r['regex']):>7}"
            f"{mark(r['trained']):>7}{mark(r['prompted']):>7}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--model", required=True, help="the small chat model to prompt")
    parser.add_argument("--embed-model", default="bge-m3:latest")
    parser.add_argument(
        "--host", default=os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434"
    )
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--name", default="")
    args = parser.parse_args()

    leaked = check_disjoint()
    if leaked:
        print(f"training phrasings overlap the test cases: {leaked}", file=sys.stderr)
        return 2

    result = run(args.model, args.embed_model, args.host, args.repeat, args.timeout)
    print(describe(result), file=sys.stderr)
    if not result["arms"]["prompted"]["answered"] and result["trained_error"]:
        print(f"\nneither model arm ran; check the host {args.host}", file=sys.stderr)
        return 2
    LEDGER.mkdir(parents=True, exist_ok=True)
    name = args.name or f"intent-{args.model.replace(':', '_').replace('/', '_')}"
    target = LEDGER / f"{name}.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"\nfiled as {target.relative_to(ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

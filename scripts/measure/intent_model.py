#!/usr/bin/env python3
"""Train a decision model on task intent, and score it against the regex.

One decision model, many decisions: an embedding of the task text and a
one-vs-rest logistic regression per intent, fitted on the generated
training split and scored on the held-out test split and on the
hand-labelled gold set it never saw.

For every intent that the harness already decides with a regular
expression, the same held-out phrasings are also put through that
regex, so the two are compared on identical text. That is the number
that decides whether building a decision model for this project is
worth it: not whether the model is good in the abstract, but whether it
beats what routes behaviour today.

Usage:
  python scripts/measure/intent_model.py            # after intent_dataset.py
  python scripts/measure/intent_model.py --embed-model bge-m3:latest
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
DATA = ROOT / "data" / "intent"
LEDGER = ROOT / "docs" / "experiments"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ollama_client  # noqa: E402

from harness import task as T  # noqa: E402

# Which regex in task.py answers each intent. Absent means the harness
# has no single deterministic decision for it.
REGEX_FOR = {
    "bugfix": T.looks_like_bugfix,
    "add_feature": T.looks_like_add_feature,
    "write_tests": T.looks_like_write_tests,
    "rename_or_move": T.looks_like_file_operation,
    "new_package": T.looks_like_new_package,
    "question": T.looks_like_question,
    "refactor": T.looks_like_refactor,
    "review": T.looks_like_review,
    "ship": T.looks_like_ship,
    "platform_ops": lambda t: T.looks_like_platform(t) or T.looks_like_ops(t),
    "script_cli": T.looks_like_script,
}


def read(name: str) -> list[dict]:
    path = DATA / f"{name}.jsonl"
    if not path.is_file():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def embed(model: str, texts: list[str], host: str, timeout: int, batch: int = 64) -> np.ndarray:
    out: list[np.ndarray] = []
    for i in range(0, len(texts), batch):
        out.append(np.asarray(ollama_client.embed(host, model, texts[i:i + batch], timeout),
                              dtype=np.float64))
    vectors = np.vstack(out)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.where(norms == 0, 1, norms)


def fit(x: np.ndarray, y: np.ndarray, steps: int = 2000, rate: float = 0.5,
        l2: float = 1e-3) -> tuple[np.ndarray, float]:
    w = np.zeros(x.shape[1])
    b = 0.0
    for _ in range(steps):
        p = 1 / (1 + np.exp(-(x @ w + b)))
        err = p - y
        w -= rate * (x.T @ err / len(y) + l2 * w)
        b -= rate * err.mean()
    return w, b


def scores(x: np.ndarray, models: dict[str, tuple[np.ndarray, float]]) -> dict[str, np.ndarray]:
    return {intent: x @ w + b for intent, (w, b) in models.items()}


def prf(pred: np.ndarray, truth: np.ndarray) -> dict:
    tp = int(((pred == 1) & (truth == 1)).sum())
    fp = int(((pred == 1) & (truth == 0)).sum())
    fn = int(((pred == 0) & (truth == 1)).sum())
    tn = int(((pred == 0) & (truth == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "accuracy": round((tp + tn) / max(1, len(truth)), 3),
            "precision": round(precision, 3), "recall": round(recall, 3),
            "f1": round(f1, 3)}


def evaluate(split_name: str, rows: list[dict], x: np.ndarray,
             models: dict[str, tuple[np.ndarray, float]], intents: list[str]) -> dict:
    """Per intent: the decision model vs the regex, on identical text."""
    truth_intent = np.array([r["intent"] for r in rows])
    logit = scores(x, models)
    stacked = np.vstack([logit[i] for i in intents])          # intents x rows
    argmax = np.array(intents)[stacked.argmax(axis=0)]
    result: dict = {"n": len(rows), "per_intent": {}}
    known = truth_intent != "other"
    if known.any():
        result["multiclass_accuracy"] = round(float((argmax[known] == truth_intent[known]).mean()), 3)
    for intent in intents:
        truth = (truth_intent == intent).astype(int)
        if truth.sum() == 0 and split_name != "gold":
            continue
        # The router's real decision is the argmax over intents, not a
        # separate threshold per intent. With one positive in twelve the
        # per-intent fit leans negative and "accuracy" is mostly the
        # negatives — the first run showed F1 of 0.00 beside 91%
        # accuracy for exactly that reason. Compare the decision a router
        # would actually make.
        model_pred = (argmax == intent).astype(int)
        entry = {"support": int(truth.sum()), "model": prf(model_pred, truth)}
        regex = REGEX_FOR.get(intent)
        if regex is not None:
            regex_pred = np.array([int(bool(regex(r["task"]))) for r in rows])
            entry["regex"] = prf(regex_pred, truth)
        result["per_intent"][intent] = entry
    return result


def describe(name: str, ev: dict) -> str:
    lines = [f"{name}: {ev['n']} phrasings"
             + (f"   multi-class accuracy {ev['multiclass_accuracy']:.0%}"
                if "multiclass_accuracy" in ev else "")]
    lines.append(f"{'intent':<16}{'n':>5}{'model acc':>11}{'F1':>7}{'regex acc':>11}{'F1':>7}"
                 f"{'model FP':>10}{'regex FP':>10}")
    for intent, e in ev["per_intent"].items():
        m = e["model"]
        r = e.get("regex")
        lines.append(
            f"{intent:<16}{e['support']:>5}{m['accuracy']:>11.0%}{m['f1']:>7.2f}"
            + (f"{r['accuracy']:>11.0%}{r['f1']:>7.2f}" if r else f"{'—':>11}{'—':>7}")
            + f"{m['fp']:>10}" + (f"{r['fp']:>10}" if r else f"{'—':>10}")
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--embed-model", default="bge-m3:latest")
    parser.add_argument("--host",
                        default=os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument(
        "--export", default="",
        help="also write the fitted weights here as JSON, for the harness to "
             "score with in pure Python (default: not written)",
    )
    args = parser.parse_args()

    train, test, gold = read("train"), read("test"), read("gold")
    if not train or not test:
        print("no data/intent/train.jsonl and test.jsonl; run intent_dataset.py first",
              file=sys.stderr)
        return 2
    intents = sorted({r["intent"] for r in train})
    started = time.time()

    x_train = embed(args.embed_model, [r["task"] for r in train], args.host, args.timeout)
    models = {}
    for intent in intents:
        y = np.array([r["intent"] == intent for r in train], dtype=np.float64)
        models[intent] = fit(x_train, y)

    if args.export:
        # Five decimals is plenty for a decision and keeps the file small.
        export = {
            "embed_model": args.embed_model,
            "dims": int(x_train.shape[1]),
            "trained_on": len(train),
            "intents": {
                intent: {"weights": [round(float(v), 5) for v in w], "bias": round(float(b), 5)}
                for intent, (w, b) in models.items()
            },
        }
        target = Path(args.export)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(export, separators=(",", ":")) + "\n", encoding="utf-8")
        print(f"weights exported to {target} ({target.stat().st_size // 1024} KB)", file=sys.stderr)

    out = {"embed_model": args.embed_model, "intents": intents,
           "train": len(train), "splits": {}}
    for name, rows in (("test", test), ("gold", gold)):
        if not rows:
            continue
        x = embed(args.embed_model, [r["task"] for r in rows], args.host, args.timeout)
        ev = evaluate(name, rows, x, models, intents)
        out["splits"][name] = ev
        print(describe(name, ev), file=sys.stderr)
        print("", file=sys.stderr)
    out["minutes"] = round((time.time() - started) / 60, 1)

    LEDGER.mkdir(parents=True, exist_ok=True)
    target = LEDGER / "intent-decision-model.json"
    target.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"filed as {target.relative_to(ROOT)}   {out['minutes']} min", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""What kind of task is this? Decided by a fitted model, not a regex.

The harness has always answered this with regular expressions —
`looks_like_bugfix` fires on *fix, bug, nameerror, crash, defect* — and
measured against phrasings people actually write, that regex was right
53% of the time. A person who types "the totals come out one too low"
has reported a bug without using any of its words.

This is the other decider: a sentence embedding of the task and one
logistic regression per intent, fitted on 841 phrasings and scored on
text it never saw at 86% against the regex's 53%. The weights are a JSON
file beside this module; scoring is a dot product per intent and needs
no numpy.

It is deliberately allowed to fail. Embedding needs an embedding model
behind Ollama, and a laptop may not have one. `intent_of` answers None
in that case and the caller keeps the regex. A decision model that
raised would make the harness worse on every machine it is not set up
on, which is most of them.
"""

from __future__ import annotations

import json
import math
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Callable

WEIGHTS = Path(__file__).with_name("intent_weights.json")

Embedder = Callable[[str], "list[float] | None"]


@dataclass(frozen=True)
class Decision:
    """The intent chosen, and how clearly it won.

    `margin` is the gap between the best and second-best score. Two
    intents that genuinely overlap — a new package against a new
    function — sit close together, and a caller that needs to be sure
    can ask for a margin before trusting the call.
    """

    intent: str
    margin: float
    runner_up: str


@lru_cache(maxsize=1)
def _weights() -> dict:
    return json.loads(WEIGHTS.read_text(encoding="utf-8"))


def intents() -> tuple[str, ...]:
    return tuple(_weights()["intents"])


def _normalise(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    return [v / norm for v in vector] if norm else vector


def score(vector: list[float]) -> dict[str, float]:
    """One logit per intent, from an embedding of the task."""
    spec = _weights()
    if len(vector) != spec["dims"]:
        raise ValueError(f"expected {spec['dims']} dimensions, got {len(vector)}")
    unit = _normalise(vector)
    out: dict[str, float] = {}
    for intent, head in spec["intents"].items():
        out[intent] = sum(w * x for w, x in zip(head["weights"], unit)) + head["bias"]
    return out


def decide(vector: list[float]) -> Decision:
    ranked = sorted(score(vector).items(), key=lambda kv: kv[1], reverse=True)
    (best, top), (second, next_) = ranked[0], ranked[1]
    return Decision(intent=best, margin=top - next_, runner_up=second)


def ollama_embed(task: str, *, host: str | None = None, timeout: float = 20.0) -> list[float] | None:
    """Embed with the model the weights were fitted on. None if it cannot."""
    base = (host or os.environ.get("OLLAMA_HOST") or "http://127.0.0.1:11434").rstrip("/")
    body = json.dumps(
        {"model": _weights()["embed_model"], "input": [task], "keep_alive": "10m"}
    ).encode()
    request = urllib.request.Request(
        f"{base}/api/embed", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return None
    vectors = payload.get("embeddings") or []
    return list(vectors[0]) if vectors else None


def intent_of(task: str, *, embed: Embedder = ollama_embed) -> Decision | None:
    """The decided intent of a task, or None when it cannot be decided.

    None means "keep whatever you were doing": the embedding model is
    absent, unreachable, or answered nonsense. It never means "no
    intent"; every task has one.
    """
    if not task or not task.strip():
        return None
    vector = embed(task.strip())
    if not vector:
        return None
    try:
        return decide(vector)
    except ValueError:
        return None

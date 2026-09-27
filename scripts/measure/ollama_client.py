"""One ollama client for the measurement scripts, with the two things
they all needed and none of them had.

Every request is timed and written to stderr as it completes, so a run
that is blocked shows *where* it is blocked instead of showing nothing
until it ends. Three probes in a row sat for half an hour each with 0.3
seconds of CPU, and every one of them was piped through `tail`, which
hid the fact that they had never finished a single call.

And a request that hangs is retried once after evicting its model.
Three separate hangs on this host were all cleared by exactly that —
`keep_alive: 0` for the stuck model — and never by waiting. The cause
was not found; the recovery was, so the recovery is automatic.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request


def _raw(host: str, path: str, body: dict, timeout: int) -> dict:
    request = urllib.request.Request(
        f"{host}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())


def evict(host: str, model: str) -> None:
    """Unload one model. Harmless if it is not loaded."""
    try:
        _raw(host, "/api/generate", {"model": model, "keep_alive": 0}, 30)
    except (urllib.error.URLError, TimeoutError, OSError):
        pass


def post(host: str, path: str, body: dict, timeout: int = 90,
         label: str = "") -> dict:
    """POST, log the latency, and on a hang evict the model and try once more."""
    model = str(body.get("model", "?"))
    for attempt in (1, 2):
        started = time.time()
        try:
            payload = _raw(host, path, body, timeout)
            print(f"    {label or path} {model} {time.time() - started:.1f}s",
                  file=sys.stderr, flush=True)
            return payload
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"    {label or path} {model} FAILED after "
                  f"{time.time() - started:.0f}s ({type(exc).__name__}); "
                  f"{'evicting and retrying' if attempt == 1 else 'giving up'}",
                  file=sys.stderr, flush=True)
            if attempt == 2:
                raise
            evict(host, model)
            time.sleep(2)
    raise RuntimeError("unreachable")


def chat(host: str, model: str, prompt: str, timeout: int = 90,
         temperature: float = 0.0, label: str = "chat") -> str:
    payload = post(host, "/api/chat", {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": temperature},
        "keep_alive": "10m",
    }, timeout, label)
    return str((payload.get("message") or {}).get("content", ""))


def embed(host: str, model: str, texts: list[str], timeout: int = 120,
          label: str = "embed") -> list[list[float]]:
    payload = post(host, "/api/embed",
                   {"model": model, "input": texts, "keep_alive": "10m"},
                   timeout, f"{label}[{len(texts)}]")
    return payload["embeddings"]

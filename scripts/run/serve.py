#!/usr/bin/env python3
"""Tiny HTTP sidecar: Ollama generates, PythonVibeGuard decides.

Binds 127.0.0.1 by default. Set HARNESS_HOST=0.0.0.0 only if you accept LAN
clients. POST bodies larger than MAX_BODY (32 KiB) are rejected.

  PYTHONPATH=src python scripts/run/serve.py
  curl -s localhost:8080/health
  curl -s localhost:8080/v1/python-vibe -d '{"prompt":"jsonl reader"}' -H 'content-type: application/json'
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from finetune.models import SPECS  # noqa: E402
from harness.guard.fallbacks import PYTHON_VIBE_FALLBACK  # noqa: E402
from harness.model.ollama_generate import OllamaGenerate  # noqa: E402
from harness.guard.python_vibe import PythonVibeGuard  # noqa: E402
from harness.guard.run import complete  # noqa: E402


def _route():
    py = SPECS["python-vibe"]
    return OllamaGenerate(py.ollama_base, py.system), PythonVibeGuard(), PYTHON_VIBE_FALLBACK


GENERATE, GUARD, FALLBACK = _route()
MAX_BODY = 32 * 1024
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _json(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        # Say the exchange is over. A client left waiting blocks until its
        # own timeout, which is how this failed on Windows.
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(raw)
        self.wfile.flush()
        self.close_connection = True

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/health":
            self._json(404, {"error": "not found"})
            return
        spec = SPECS["python-vibe"]
        self._json(
            200,
            {
                "ok": True,
                "ollama": {"python-vibe": GENERATE.healthy()},
                "models": {
                    "python-vibe": {
                        "ollama": spec.ollama_base,
                        "hf": f"https://huggingface.co/{spec.hf_repo}",
                        "ram_mb": spec.ram_mb,
                    }
                },
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/v1/python-vibe":
            self._json(404, {"error": "not found"})
            return
        # A negative length would make read() wait for the client to close,
        # which is no cap at all; a non-number would crash the handler.
        raw_length = (self.headers.get("Content-Length") or "0").strip()
        if not raw_length.isdigit():
            self._json(400, {"error": "invalid content-length"})
            return
        length = int(raw_length)
        if length > MAX_BODY:
            self._json(413, {"error": "body too large"})
            return
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid json"})
            return
        prompt = (body.get("prompt") or "").strip()
        if not prompt:
            self._json(400, {"error": "prompt required"})
            return
        try:
            outcome = complete(GENERATE, GUARD, FALLBACK, prompt)
        except RuntimeError as exc:
            self._json(502, {"error": str(exc)})
            return
        self._json(
            200,
            {
                "text": outcome.output,
                "verdict": outcome.verdict,
                "fallback": outcome.fallback,
                "findings": [
                    {"rule_id": f.rule_id, "severity": f.severity, "excerpt": f.excerpt}
                    for f in outcome.findings
                ],
                "ruleset": outcome.ruleset_version,
            },
        )


def listen_host() -> str:
    return os.environ.get("HARNESS_HOST") or DEFAULT_HOST


def listen_port(argv: list[str]) -> int:
    if len(argv) > 1:
        return int(argv[1])
    return int(os.environ.get("HARNESS_PORT") or DEFAULT_PORT)


def main() -> None:
    host = listen_host()
    port = listen_port(sys.argv)
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"harness listening on http://{host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()

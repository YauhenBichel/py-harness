---
title: Commands
description: Every py-harness command and flag. The Python API and the local HTTP server on 127.0.0.1.
date: 2026-09-06
---

# Commands

The usual way is the `py-harness` command. You can also call the
Python library, or an HTTP server on `127.0.0.1`.

## Command line

```bash
py-harness                  # prints the command list
py-harness brief            # no model
py-harness ask  "what does compute_total return?"
py-harness run  "write tests for apply_discount"
py-harness run  "write tests for apply_discount" --dry-run --scope src
py-harness serve --project .
py-harness editors cursor --allow-writes
```

`python -m harness …` is the same command if `py-harness` is not on PATH.

`brief`, `layout`, and `route` never call a model. `ask` never changes
files. `run` writes unless you pass `--dry-run`. Add `--json` for
machine-readable output, `-v` for tool results.

### What `run` may do to your project

`run` changes files inside the folder you give it, keeps a `.bak` copy of
anything it edits, and **runs that project's test suite** to check its own
work. If you would rather it did nothing, use `ask`, or pass
`--dry-run`, which refuses every change and never runs anything.

Some fixes need no model at all. A misspelled name that Python cannot
resolve, or a rename you asked for by name, are corrected directly; the
tests are then run once, and if they pass the task ends there.

## Library

```python
from pathlib import Path
from harness import Agent, AgentOptions

agent = Agent(AgentOptions(project=Path("~/app"), scope="src"))
result = agent.run("add multiply(a, b) and a unit test")

result.ok        # True when the agent finished the task
result.summary   # its closing sentence
result.writes    # files it changed
result.steps     # every turn, in order
result.refusals  # what the harness stopped, and why
```

### Settings

| Field | Default | What it does |
| --- | --- | --- |
| `project` | required | Directory the agent may read and write inside |
| `task` | `""` | What you are asking for |
| `model` | `llama3.1:8b` | Ollama model name |
| `engine` | `ollama` | `ollama`, `mlx`, or `openai` (remote OpenAI-compatible HTTP) |
| `scope` | `""` | Stay inside this subdirectory |
| `skills` | `()` | Skill names to load. Empty means choose from the task. Catalog: [Skills]({{ '/skills/' | relative_url }}) |
| `steps` | `20` | Maximum model turns before the run stops |
| `max_tokens` | `700` | Maximum length of one model reply |
| `allow_writes` | `True` | When `False`, patch, edit and run are refused |
| `record` | `None` | File to append redacted turns to. `None` writes `.python-vibe/traces.jsonl` in the project |
| `keep_no_record` | `False` | Write no trace (`--no-record`) |
| `on_event` | `None` | Called with progress messages |
| `on_question` | `None` | Called when the agent needs you to choose |

### Read-only runs

```python
options = AgentOptions(project=Path("~/app"), allow_writes=False)
Agent(options).run("what would you change in src/app.py?")
```

Nothing is written. `patch`, `edit` and `run` are refused before any tool
sees them, and the prompt says the run is read-only.

### When the agent needs to know something

A task such as `"clean this up"` names no file and no function. Rather than
guessing, the harness asks before it calls the model:

```python
def choose(question):
    print(question.render())
    return input("> ")

Agent(AgentOptions(project=..., on_question=choose)).run("clean this up")
```

Without `on_question` the run stops immediately and returns the question:

```python
result.stopped   # "question"
result.summary   # the question and the options
result.writes    # ()
```

### When the run breaks the suite

Before the model starts, a run that may write reads the suite once. If
the suite was green then and is red after a write, the model gets the
one repair the loop always allows. A second red result stops the run:

```python
result.stopped   # "broke"
result.ok        # False
result.summary   # "stopped after 4 steps: this run turned the suite red and one repair did not fix it.
                 #  Wrote: src/orders.py (backups: src/orders.py.bak).
                 #  The suite was green before this run and is red now: FAIL: test_total (tests.test_orders.T)
                 #  Restore from the backups if the change is not wanted."
```

Every other ending that wrote something carries the same two lines:
which files were written, with their backups, and whether the suite is
worse than when the run started. A `done` over a suite this run turned
red is `ok=False`.

## Install

The harness uses only the standard library, so there is nothing to build and
the same three commands work on macOS, Linux and Windows.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install py-harness-cli
```

The command is `py-harness`. The PyPI name is `py-harness-cli` because
`py-harness` collides with another package. Do not `pip install
py-harness` or `pip install pyharness`. Activate the virtualenv in
every new terminal, or the shell says `command not found`.

From a clone (sample project and extras):

```bash
git clone https://github.com/YauhenBichel/py-harness.git
cd py-harness
python3 scripts/run/install.py
source .venv/bin/activate
```

That creates `.venv` when needed and runs `pip install -e .`. Already
in a virtualenv: `pip install -e .` is the same install. The sample
project is `cd demo/orders` then `py-harness brief`.

That gives you a `py-harness` command. No `PYTHONPATH`, no version-pinned
interpreter, no script paths:

| | Before | After |
| --- | --- | --- |
| macOS / Linux | `PYTHONPATH=src python3.13 scripts/run/agent.py --project ~/app "..."` | `py-harness run "…"` in that folder |
| Windows | did not work: `PYTHONPATH=src` is not valid in cmd or PowerShell | `py-harness run "…"` in that folder |

Training on Apple Silicon needs extras: `pip install -e ".[train]"`.
Publishing to the Hub needs `pip install -e ".[hub]"`.

### Remote weights

`--engine openai` sends generate calls to an OpenAI-compatible host
(Hugging Face Inference, vLLM, or a box you rent). The write limit stays on
this machine. Set `PYTHON_VIBE_BASE_URL` and a token
(`HF_TOKEN` or `PYTHON_VIBE_API_KEY`). A remote Ollama is the same
`--engine ollama` with `OLLAMA_HOST` pointed at that box.

What goes to that host is read before it leaves. A prompt carrying an
AWS access key, an Anthropic key, a GitHub token or a private key is
refused rather than sent, and the refusal names the kind without
repeating the value. A prompt over 200,000 characters is refused as
well, on the grounds that a whole tree is a mistake rather than a task;
raise `PYTHON_VIBE_MAX_SEND` if it was the intent. The first send of a
run prints how many characters went where, so nobody has to guess.

None of this runs for a local host. Sending to `127.0.0.1` is not
sending.

See [cloud weights]({{ '/investigations/cloud-weights/' | relative_url }}).

### Hub GGUFs that Ollama does not ship

OpenCoder 8B and SWE-agent-LM 7B are on Hugging Face, not in the Ollama
library. From a clone of this repo:

```bash
python3 scripts/weights/import_hf_ollama.py --name opencoder
python3 scripts/weights/import_hf_ollama.py --name swe-agent-lm
py-harness --model opencoder:8b run "add a function clamp and a unit test"
```

That downloads the Q4_K_M GGUF (~4.7 GB each) and runs `ollama create`.
Default stays `llama3.1:8b`. See
[Hub models]({{ '/investigations/hub-models/' | relative_url }}).

Paths are always written with forward slashes, on every platform, because
the model is shown them and copies them back.

## HTTP server

```bash
py-harness serve --project ~/app --port 8090
```

Binds `127.0.0.1` only. **File changes are off by default**, because an
HTTP request that reaches the agent can change files on the machine the
server runs on.

| Route | Method | Needs `--allow-writes` |
| --- | --- | --- |
| `/health` | GET | no |
| `/v1/brief` | POST | no |
| `/v1/layout` | POST | no |
| `/v1/ask` | POST | no |
| `/v1/models` | GET | no |
| `/v1/chat/completions` | POST | writes only with `--allow-writes` |
| `/v1/run` | POST | yes |

```bash
curl -s localhost:8090/health
curl -s localhost:8090/v1/layout -d '{}'
curl -s localhost:8090/v1/ask -d '{"task":"what does compute_total return?"}'
curl -s localhost:8090/v1/models
```

`POST /v1/chat/completions` takes the last user message as the task and
returns an OpenAI-shaped reply. `stream` is refused. A write task on a
read-only server is `403`. Point VS Code and other OpenAI-compatible
editors at `http://127.0.0.1:8090/v1`, or copy drop-in files with
`py-harness editors cursor --allow-writes`. Details:
[Cursor]({{ '/cursor/' | relative_url }}) ·
[local editor]({{ '/local-editor/' | relative_url }}).


Without `--allow-writes`, `/v1/run` answers `403` and says how to enable it.
The path restriction, the draft guard and the `.bak` backup apply in every
mode; the flag is an additional control, not a replacement for them.

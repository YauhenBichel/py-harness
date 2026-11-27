---
title: FAQ
description: When to use py-harness, when not, and short answers. Includes the plain-text output of brief and run on demo/orders.
permalink: /faq/
date: 2026-11-27
---

# FAQ

## What it prints

Two commands that need no model, run on the sample project `demo/orders` (installed from a clone at version 0.4.0; the PyPI release 0.3.1 prints the same):

```console
$ py-harness brief
10 Python and Markdown files, 3.3 KB in total.
Small enough that py-harness can read all of it, so you can ask about any part.

Files:
  README.md  1.0 KB
  src/__init__.py  68 B
  src/orders.py  467 B
  src/orders_controller.py  568 B
  src/orders_service.py  285 B
  src/render.py  193 B
  src/report.py  155 B
  src/util.py  67 B
  tests/__init__.py  0 B
  tests/test_orders.py  511 B

py-harness has 24 skills it can apply. It picks them from the wording of your task; you do not choose them.
$ py-harness run "find the NameError and fix it"
bound unique NameError typo (subtotl → subtotal) in src/orders.py. Tests passed.
```

The fix changes one line in `src/orders.py`: `return subtotl + (subtotl * TAX_RATE)` becomes `return subtotal + (subtotal * TAX_RATE)`. `ask` and most other `run` jobs need Ollama; their recorded sessions are on the [Live demo]({{ '/live/' | relative_url }}) page.

## When to use it, and when not

Use it to try a local 8B model on a small Python project you do not want to send to a cloud service, with a harness that checks each change by running your tests. Do not use it as an everyday coding assistant (the [results]({{ '/investigations/' | relative_url }}) say it is not ready), on a large repository (a real 4,580-file repository wrote 1 / 12), or for languages other than Python.

## FAQ

### How do I run a local LLM on my Python project?

Install `py-harness-cli`, run `ollama pull llama3.1:8b`, then `py-harness ask "what does add return?"` in the project folder. See [Start]({{ '/start/' | relative_url }}).

### Does it send my code to the cloud?

Not by default. The default backend is a local Ollama server (or the one named in `OLLAMA_HOST`). Other backends can be chosen with `--engine`, so check which one you set. It reads and writes only the folder you point at.

### What can it change?

Only `.py`, `.pyi`, `.md`, `.toml`, `.yml`, `.yaml`, `.cfg`, `.ini` and `.json` files under the project folder, and it refuses secret file names. `ask` never writes.

### Why is the package called py-harness-cli?

The name `py-harness` on PyPI belongs to another project. The command is still `py-harness`.

### Do I need a GPU?

No. The sample commands above need no model at all. Daily work uses `llama3.1:8b` through Ollama on a laptop.

### How is it different from a general coding assistant?

A general assistant covers many models and languages. py-harness is narrower: four jobs, Python only, a deterministic harness that decides what is written, and published measurements of where it fails.


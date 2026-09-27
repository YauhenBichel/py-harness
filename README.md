# py-harness

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](./LICENSE)
[![PyPI](https://img.shields.io/pypi/v/py-harness-cli.svg)](https://pypi.org/project/py-harness-cli/)
[![CI](https://github.com/YauhenBichel/py-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/YauhenBichel/py-harness/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-2F6FED)](https://yauhenbichel.github.io/py-harness/)
[![Pages](https://github.com/YauhenBichel/py-harness/actions/workflows/pages.yml/badge.svg)](https://yauhenbichel.github.io/py-harness/)
[![Contributors](https://img.shields.io/github/contributors/YauhenBichel/py-harness)](https://github.com/YauhenBichel/py-harness#contributors)

Four jobs on your laptop: **ask**, **write a test**, **fix a bug**, **add
one small function**. Only touches the folder you point at. Daily work
is `py-harness` plus Ollama `llama3.1:8b`. Not everyday-ready.
Site: [yauhenbichel.github.io/py-harness](https://yauhenbichel.github.io/py-harness/).

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install py-harness-cli
```

The command is `py-harness`. The PyPI name is `py-harness-cli` because
`py-harness` collides with another package. Do not `pip install
py-harness` or `pip install pyharness`.

Sample project — clone, then `cd demo/orders`. Do not `brief` this
repository.

```bash
git clone https://github.com/YauhenBichel/py-harness.git
cd py-harness/demo/orders
py-harness brief
py-harness ask  "what does compute_total return?"
py-harness run  "find the NameError and fix it"
```

Activate `.venv` in **every new terminal**. If the shell says
`command not found: py-harness`, it is not active. Daily work needs
`ollama pull llama3.1:8b`. From a clone,
`python3 scripts/run/install.py` is the editable install.

`ask` never writes. `run` writes, then runs the tests. The NameError
sample is built into the tool (no model). Another folder:
`py-harness ask ~/app "what does add return?"`.

[Start](https://yauhenbichel.github.io/py-harness/start/) ·
[Commands](https://yauhenbichel.github.io/py-harness/api/) ·
[Contributing](./CONTRIBUTING.md) ·
[Security](./SECURITY.md)

## What it looks like

![pip install py-harness-cli, then brief and a NameError fix](docs/media/pip-demo.gif)

Replay: `asciinema play docs/media/pip-demo.cast`.
A longer session (8B ask): `docs/media/live-demo.gif`.
Full log: [Live demo](https://yauhenbichel.github.io/py-harness/live/).

**VS Code** — `py-harness editors vscode`, then Tasks: Run Task.

![py-harness VS Code tasks on demo/orders](docs/media/vscode-demo.gif)

Replay: `asciinema play docs/media/vscode-demo.cast`.
[VS Code](https://yauhenbichel.github.io/py-harness/vscode/).

**Cursor** — `py-harness editors cursor --allow-writes`, then chat or Tasks.

![py-harness Cursor MCP on demo/orders](docs/media/cursor-demo.gif)

Replay: `asciinema play docs/media/cursor-demo.cast`.
[Cursor](https://yauhenbichel.github.io/py-harness/cursor/).

## Scores

One laptop. 29 Aug–5 Sep 2026. **Not everyday-ready.**

| What I tried | Result |
| --- | --- |
| 0.5B as daily work | **0 / 4** vibe, **0 / 2** parse |
| Four Start commands on `demo/orders` | **0 / 4**, then **4 / 4** after the harness |
| Same bench, code must run | 8B **6–9 / 9**; 7B coder 7 / 9; 30B timeout |
| Same-night daily (write tests, clamp, sum × 3) | 8B **9 / 9**, 7B coder **7 / 9**. Keep the 8B |
| Extra 7B–8B on disk | 8192-warmed SWE daily clamp: first generate 180s. Not a score |
| A real repository (4,580 files) | reading works; writing **1 / 12** |

The long table: [Experiments](https://yauhenbichel.github.io/py-harness/investigations/experiments/).
Every score: [Results](https://yauhenbichel.github.io/py-harness/investigations/).
Which tags timed out: [Hub models](https://yauhenbichel.github.io/py-harness/investigations/hub-models/).

## More

| If you want | Go here |
| --- | --- |
| What each folder is | [Folders](https://yauhenbichel.github.io/py-harness/tree/) |
| Tests | `PYTHONPATH=src python -m unittest discover -s tests -q` |
| 0.5B style prior | [YauhenBichel/python-vibe-0.5b](https://huggingface.co/YauhenBichel/python-vibe-0.5b) |
| Train / serve / API | [Commands](https://yauhenbichel.github.io/py-harness/api/) |
| A first issue | [good first issue](https://github.com/YauhenBichel/py-harness/labels/good%20first%20issue) |

Vulnerabilities: a **public** GitHub issue. Do not paste live keys.

---

## Contributors

Thank you to everyone who has helped py-harness.

<!-- readme: contributors,bots/- -start -->
<p align="center">
  <a href="https://github.com/YauhenBichel" title="Yauhen Bichel" aria-label="Yauhen Bichel"><img src=".github/faces/YauhenBichel.svg" width="87" height="99" alt="Yauhen Bichel" /></a>
  <a href="https://github.com/xianjianlf2" title="Mark Xian" aria-label="Mark Xian"><img src=".github/faces/xianjianlf2.svg" width="66" height="75" alt="Mark Xian" /></a>
  <a href="https://github.com/ItzSaurav" title="Itzsaurav" aria-label="Itzsaurav"><img src=".github/faces/ItzSaurav.svg" width="72" height="82" alt="Itzsaurav" /></a>
  <a href="https://github.com/svkzn" title="svkzn" aria-label="svkzn"><img src=".github/faces/svkzn.svg" width="80" height="91" alt="svkzn" /></a>
  <a href="https://github.com/Aditya-233" title="Aditya" aria-label="Aditya"><img src=".github/faces/Aditya-233.svg" width="63" height="72" alt="Aditya" /></a>
  <a href="https://github.com/kkkhs" title="Huangshuo Kuang" aria-label="Huangshuo Kuang"><img src=".github/faces/kkkhs.svg" width="76" height="87" alt="Huangshuo Kuang" /></a>
</p>
<!-- readme: contributors,bots/- -end -->

Filled from GitHub commits (bots omitted). [Contributor graph](https://github.com/YauhenBichel/py-harness/graphs/contributors) · [good first issue](https://github.com/YauhenBichel/py-harness/labels/good%20first%20issue) · [Action](https://github.com/YauhenBichel/readme-contributors)

# Contributing to py-harness

Thanks for being here. This repo is small: one 0.5B LoRA, a deterministic
harness, and stdlib HTTP. It is a good first open-source project if you keep
the rules below.

## Rules that are not negotiable

- The harness stays **deterministic**. Do not add a keyword router on the user
  prompt that skips `PythonVibeGuard`.
- Do not commit `.safetensors`, `.env`, tokens, or real hostnames.
- Do not teach the model to comment on moles or lesions (PV004 already blocks
  that — this is a coding model).
- Do not add `curl … | sh` examples the harness would block (PV003).

## Getting set up

The folders are listed in [docs/tree.md](./docs/tree.md).
Daily work is `demo/orders`, not the repository root.

```bash
git clone https://github.com/YauhenBichel/py-harness.git
cd py-harness
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python -m unittest discover -s tests -q
```

You do **not** need a Hugging Face token, Ollama, or a GPU to run the harness
tests. Training the tiny LoRA uses MLX on Apple Silicon (Homebrew Python 3.13).
Everyday agent work uses Ollama 8B+ — see [AGENTS.md](./AGENTS.md) and
[docs/local-editor.md](./docs/local-editor.md). The project site is
[yauhenbichel.github.io/py-harness](https://yauhenbichel.github.io/py-harness/).
New public notes go in `docs/` (Jekyll). Do not name other editors or chat
products there.

Uploads go to **your** Hub namespace (`HF_USER=yourname` or `HF_REPO=…`), never
to the official weights repo unless you are a maintainer. Anyone can download
the public adapters without an account.

## What you may add

- More **short** Python training pairs (stdlib first, type hints, no secrets)
- A harness rule with **two fixtures**: one string that must `block`, one
  near-miss that must `pass`
- An 8B-shaped skill (`skills/<name>/SKILL.md`, one `Action:` block) after
  `scripts/measure/skill_probe.py` shows the intended first Action
- Docs, CI, eval prompts, and drop-in files under `editors/`

### Naming conventions

Choose names that describe the work or behavior.

| Kind | Do | Do not |
| --- | --- | --- |
| Function | `total_price(quantity, unit_price)` | `calc`, `tmp`, `x`, `TotalPrice` |
| Class | `PriceLine`, `TestMultiply` | `pricing`, `Test`, `test_mathy` |
| Module | `pkg/pricing.py` | `util.py`, `helpers.py`, `misc.py` |
| Test | `test_total_price_returns_product` + `got =` | `test_it_works`, `assertEqual(fn(), n)` on one line |

For renaming an unclear function, see [fix-smell](./skills/fix-smell/SKILL.md).
For tests, arrange inputs, store the result in `got`, then assert it.
See [write-tests](./skills/write-tests/SKILL.md) for examples.

## Before you open a pull request

- [ ] `PYTHONPATH=src python -m unittest discover -s tests -q` passes
- [ ] New pairs do not include live keys or `curl|sh`
- [ ] No secrets, real hostnames, or personal data
- [ ] One concern per PR

## Pick an issue by level

Start at [Welcome — how to pick an issue](https://github.com/YauhenBichel/py-harness/discussions/10).
Design questions go in [Discussions](https://github.com/YauhenBichel/py-harness/discussions), not a drive-by PR.

| Level | Label | Open examples |
| --- | --- | --- |
| Very junior | [`good first issue`](https://github.com/YauhenBichel/py-harness/labels/good%20first%20issue) | [#96](https://github.com/YauhenBichel/py-harness/issues/96) naming table · [#97](https://github.com/YauhenBichel/py-harness/issues/97) refuse util.py |
| Intermediate | [`intermediate`](https://github.com/YauhenBichel/py-harness/labels/intermediate) | [#99](https://github.com/YauhenBichel/py-harness/issues/99) two god-module rules · [#100](https://github.com/YauhenBichel/py-harness/issues/100) demo orders |

What has been measured, and how many runs each number stands on: [Experiments](https://yauhenbichel.github.io/py-harness/investigations/experiments/).

Open threads: [fused weights](https://github.com/YauhenBichel/py-harness/discussions/11) · [stdlib vs FastAPI](https://github.com/YauhenBichel/py-harness/discussions/12) · [eval protocol](https://github.com/YauhenBichel/py-harness/discussions/13) · [train without MLX](https://github.com/YauhenBichel/py-harness/discussions/14) · [experiment results](https://github.com/YauhenBichel/py-harness/discussions/128).

## GitHub account `py-harness`

The harness never authors a commit as this project. **You** stay the
author. When `Action: commit` runs, it adds:

```
Co-authored-by: python-vibe <322567521+python-vibe@users.noreply.github.com>
```

The user is [py-harness](https://github.com/python-vibe). GitHub links
that numbered noreply address to the profile. Do not grant the account
write access to other repos — attribution only.

## Project site

The project site is published at https://yauhenbichel.github.io/py-harness/.

To enable GitHub Pages in a repository or fork:
1. Go to **Settings** → **Pages**.
2. Under **Build and deployment** → **Source**, select **GitHub Actions**.
3. Ensure the default branch is added to the `github-pages` environment deployment allow-list.

New public notes belong in `docs/` and must not name other editors or chat products.

## Reporting security issues

Do **not** open a public issue. See [SECURITY.md](./SECURITY.md).

## Licence

By contributing you agree that your contributions are licensed under the
[Apache-2.0 licence](./LICENSE) that covers this project.
 

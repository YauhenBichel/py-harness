---
title: Harness comparison
description: What transfers from other agent harnesses to an 8B on a laptop. Edit recovery and context assembly transfer. A free shell tool does not.
date: 2026-08-29
type: article
---

# Investigation: what other agent harnesses do, and what this one was missing

**Question.** `scripts/run/agent.py` is a harness around a model too small to
be trusted with a free-form tool loop. Published harnesses solve the same
problem for larger models. Which of their design choices transfer to an 8B
on a laptop, and which are weight-class luxuries?

**Answer.** Three transfer and were missing here: a signature outline
instead of a file list, a recoverable edit tool, and skills whose paths
point at *this* project. One does not transfer: a general-purpose `bash`
tool. Related: [everyday-laptop](./everyday-laptop.md) ·
[everyday-skills](./everyday-skills.md).

## The five layers

Read across the harnesses below and the same layers appear, in this order
of leverage for a small model:

1. **Context assembly** — what the model sees before its first action.
2. **Tool contract** — how an intent becomes a file change.
3. **Verification** — what proves the change was right.
4. **Permission boundary** — what the loop refuses to do.
5. **Observability** — what a failed run leaves behind.

## Comparison

| | py-harness (before) | pi | mini-swe-agent | aider |
| --- | --- | --- | --- | --- |
| Tools | 11 typed actions | `read` `write` `edit` `bash` | `bash` only | edit formats, no loop tools |
| Action format | `Action:` text protocol | provider tool-calling | plain shell in prose | fenced diff blocks |
| Context assembly | file list + sizes | `AGENTS.md`, session tree | linear message history | ranked repo map of signatures |
| Edit primitive | unique-substring `Find:` | exact match, must hit once | `sed`/heredoc via bash | search-replace blocks |
| Verification | model must ask for `run` | model runs tests via bash | bash | auto-lint, auto-test |
| Permission | path check, `.bak`, no shell | project trust gate | sandbox/container | git commit per change |
| Skills | `SKILL.md` kit | Agent Skills standard | none | none |

The text protocol is the right call here and stays: an 8B through Ollama
cannot be relied on to emit well-formed tool-call JSON, and mini-swe-agent
makes the same argument from the other end — dropping the tool-calling API
is what lets one prompt run on *any* model.

Dropping to a single `bash` tool does **not** transfer. That design moves
the whole burden of not destroying the repo onto the model's judgement.
mini-swe-agent can afford it because it runs frontier models inside a
container. This harness runs an 8B against a laptop working tree, so the
limit (`resolve_project_file`, no shell, no `curl | sh`) is the product.

## What the literature says is the biggest lever

The edit tool, not the model. One published sweep across 16 models changed
**only** the edit format and moved the average pass rate ~15 points, with
the worst-affected model going from 6.7% to 68.3%. The stated diagnosis
matches what this repo already recorded on 29 Aug 2026 (`Find: def add(left`
→ syntax break): *the model understands the task and fails to express the
edit*.

That does not argue for a new edit format here. Exact-substring replace
fails loudly instead of editing the wrong line, which is what a `.bak` and
a 2/3-length guard are protecting. It argues that a near-miss must come
back **recoverable** rather than as `Find: string not in file`.

## Audit of this harness

Reproduced on a two-file scratch project, no model in the loop:

| Finding | Evidence | Severity |
| --- | --- | --- |
| Kit skills ship fixture paths | `add-feature` says `Path: pkg/mathy.py`; copying it verbatim created `pkg/mathy.py` in an unrelated project | writes junk into someone's repo |
| `Find:` misses are dead ends | `Find: string not in file` with no next move; a lost indent or a doubled space is unrecoverable | wasted steps |
| `map` reports sizes | `src/app.py 64 B` does not say what is in it, so the first grep is a guess | wasted steps |
| No repeat detection | the same read or patch body can be re-served until `--steps` runs out | wasted steps |
| Target project's own rules ignored | its `AGENTS.md` was never read | wrong-by-convention edits |

`write-tests` shipped a third failure of the first kind in its body:
`Find: from pkg.mathy import add`, which cannot match in any project except
the eval fixture.

## What shipped

- `src/harness/skill_target.py` — before the model sees a skill, any
  `Path:`/`Scope:` in it that is not real *here* is repointed at this
  project's module or test file. Placeholders {% raw %}`{{module}} {{test}}
  {{scope}} {{symbol}}`{% endraw %} are filled the same way. A path that does exist
  (the eval fixtures) is left alone, and `__init__.py` is never repointed
  because scaffolding legitimately names a file that does not exist yet.
- `src/harness/patch_fix.py` — an exact `Find:` still wins. A miss retries
  on whitespace-normalised lines, refuses a normalised match that is
  ambiguous, re-indents the `Replace:` to the line it actually matched, and
  otherwise answers with the closest real lines in the file.
- `src/harness/repo_map.py` — `Action: map` now carries a signature
  outline (`def apply_source(path, source, *, original: str) -> None`)
  under the file list, budgeted to 120 lines. This is aider's argument:
  signatures are what let the model pick a file.
- `src/harness/loop_guard.py` — an identical read-only action is refused
  once with the next action spelled out. An exact patch body is remembered
  before policy checks and refused if proposed again, even for another path;
  re-running tests after a fix remains progress.
- `src/harness/project_docs.py` — the target project's `AGENTS.md` (then
  `CLAUDE.md`, `CONTRIBUTING.md`) is prepended, capped at 1200 chars, and
  ranked above the kit skill.
- `skills/write-tests/SKILL.md` is `Append:`-only. `repair_unittest_append`
  already inserts the method inside the class and adds the name to the
  import, so the `Find:` line was pure liability.

## What did not ship, and why

- **Auto-run tests after every write.** Verification-on-write is right for
  a harness that owns a container. Here it would run a stranger's test
  suite unasked. The loop already refuses `unittest` with no `tests/`.
- **A new edit format** (hash-tagged lines, fuzzy patch). It would replace
  a primitive that fails loudly with one that fails quietly.
- **Fuzzier `Find:` matching.** A normalised match that hits twice is
  refused, not guessed.
- **Sub-agents, MCP, session branching.** Weight-class luxuries. An 8B
  cannot spend a budget it does not have.

## Do not

- Do not add a kit skill with a literal path unless that path is an eval
  fixture. Use {% raw %}`{{module}}` / `{{test}}`{% endraw %}.
- Do not let a skill instruct a `Find:` where an `Append:` already works.
- Do not name third-party products in skill text. This page is a
  comparison; skills are copy-paste blocks.

## Sources

- [pi coding agent](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent) —
  four-tool core, edit must match exactly once, project trust gate, skills
  and extensions.
- [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) — bash-only,
  no tool-calling API, linear history, >74% on SWE-bench verified.
- [aider repository map](https://aider.chat/docs/repomap.html) — signatures
  over file lists, ranked, token-budgeted.
- [The harness problem](https://stencil.so/blog/the-harness-problem) — edit
  format alone, 16 models, ~+15 points average and 6.7% → 68.3% worst case.
- Public agent-skill authoring notes — description says what *and when*,
  concise bodies, one default not a menu, evaluations before documentation.

---
title: Where py-harness stands
description: A status board for 6 September 2026 — the seventeen fixes that took the benchmark from 51 of 75 to 64 of 75, the two findings left open, and what to do next, ranked by harm.
permalink: /status/
date: 2026-09-06
type: article
---

# Where py-harness stands

**6 September 2026.** A day spent fixing the tool rather than asking
anything of a model. The benchmark moved from **51 of 75 to 64 of 75**
on the same fifteen cases — and the two faults that started it had made
two days of model comparison say nothing about any model.

<div class="stats">
  <div class="stat"><b>64 / 75</b><span>benchmark, all tiers, five passes — was 51 / 75</span></div>
  <div class="stat"><b>17</b><span>changes merged: 7 harness, 6 instrument, 4 write-ups</span></div>
  <div class="stat"><b>2</b><span>findings filed and deliberately left alone</span></div>
  <div class="stat"><b>9 → 19</b><span>tier 3, twenty runs, after one guard</span></div>
</div>

## What was done

Grouped by what each change touches rather than by order. Almost none of
it was the model.

### Harness behaviour — what the agent does with a draft

| | | |
| --- | --- | --- |
| #283 | Take the code fence off before it reaches the file | a hosted 32B scored 1 of 10; with four backticks stripped, **9 of 10** |
| #303 | Read the draft a chat model writes | bold labels, list markers, a reason after the verb, a whole-reply fence — five shapes that parsed to nothing |
| #308 | Take the name from the brackets, and stop guessing a signature it gave | tier 3 from **9 of 20 to 19 of 20** |
| #320 | A suite that ran nothing is not a suite that passed | `unittest discover` exits 0 on zero tests, and 5 from Python 3.12 — so the check reads the output, not the code |
| #326 | Write the class the test method needs | suites that actually ran a test: **2 of 8 → 8 of 8** |
| #336 | Keep the function you were sent to fix | deleted the subject in 4 of 12 runs, now 0 of 12 — the score did not move |
| #338 | Make `--scope` fence the writes, not only the reads | it fenced every read and no write; found by running the tool on a real repository |

### The instrument — what the tool reports about itself

| | | |
| --- | --- | --- |
| #295 | Keep the turns the benchmark produces | every run recorded into a temporary directory and deleted it |
| #306 | Say how big a gap this sample can resolve | the runner knew the number and did not print it |
| #307 | Stop the contributors workflow cancelling itself | a red check on every branch that meant nothing |
| #328 | Blame the file the action was actually about | on an exception the step kept the previous file — and the repair prompt reads the same field |
| #333 | Say the module did not import, instead of calling the function missing | a broken import was reported as an absent function |
| #335 | Print the loader's path with forward slashes | `str(path)` passed locally and broke all three Windows jobs |

### Written up

[The fence was the whole story]({{ '/investigations/the-fence/' | relative_url }}) ·
[The wall two local models share]({{ '/investigations/the-wall/' | relative_url }}) ·
[What the totals were hiding]({{ '/investigations/totals-hide-things/' | relative_url }}) ·
[A day of repairs]({{ '/investigations/a-day-of-repairs/' | relative_url }})

## Where it stands

All fifteen cases, five passes, `llama3.1:8b`. What is left is
concentrated in three cases.

| Tier | Score | Weakest case |
| --- | --- | --- |
| 1 · one small component | 15 / 15 | — |
| 2 · a component and a test | 10 / 10 | — |
| 3 · a new module | 8 / 10 | `wordcount` 3/5 |
| 4 · a test for existing code | 10 / 10 | — |
| 5 · fix a bug already there | 7 / 10 | `fix-offbyone` 2/5 |
| 6 · platform and operations | 14 / 20 | `env-flag` 2/5 |

The benchmark now states its own resolution, so a difference inside the
noise cannot be written up as a result. Twice in one day it would have
stopped a wrong conclusion:

```
This sample resolves a gap of 2 case(s) or more. Identical code scored
1-2 across 10 passes, so a difference of 1 or fewer is noise and must
not be reported as a result.
```

Tier six is the tier two local models were said to stop at together.
Measured on the repaired instrument, the two local models are level with
each other by this project's own noise rule, and the larger model is
clear of both — which reversed the standing advice to keep that work
local.

| Tier six, twenty runs each | worked | `env-flag` |
| --- | --- | --- |
| `Qwen2.5-Coder-32B` (hosted) | **18 / 20** | 4/5 |
| `qwen2.5-coder:7b` (local) | 11 / 20 | 3/5 |
| `llama3.1:8b` (local, the default) | 8 / 20 | **0/5** |

## Open

Both found by running the harness on a real 259-file repository rather
than the two-file fixture.

- **#339 — a run that has broken the suite keeps going, and never says
  so.** It ran the suite, saw `exit 1`, and appended for thirteen more
  steps. It ended with 996 tests passing before and an `ImportError`
  after, reporting only "stopped after 20 steps".
- **#340 — the same patch is accepted over and over.** An identical
  `atexit` block written four times to three files. The harness refuses
  a repeated read; there is no equivalent for a write.

The wider backlog holds 53 open issues, most predating this work and
unaudited.

## What should be done

Ranked by expected harm, not by size. The first two protect a working
repository.

1. **Stop a run that has broken the suite** (#339). Higher real harm
   than anything else open: the benchmark scores it as one failure among
   many, and a person loses a working test suite without being told. The
   harness already runs the suite and already knows the exit code.
2. **Refuse a patch identical to one already applied** (#340). Cheap to
   detect — the loop already holds every step and its draft — and it
   turns a wasted twenty-step budget into an early, honest stop.
3. **Take on `env-flag`, the weakest case left** (2 of 5). Failure
   messages are trustworthy now, so start by reading them rather than
   inferring. The default 8B never passes it; the 7B coder passes it
   three times in five.
4. **Narrow the fine-tune target.** Not "be a better agent" but what a
   32B knows about flags, paths and environment files that neither local
   model does — small enough for an adapter to carry.
5. **Get variety into the training data, not volume.** Traces are kept
   now, but the builder de-duplicates and fifteen fixed cases repeat
   themselves: seventeen turns yielded four unique pairs. Dogfooding on
   real repositories is worth more per run.

## What the day actually taught

Every fault had one shape: **the tool reported something other than what
happened**, and each was invisible until something outside its
assumptions was plugged in. The harness had quietly specialised to the
single model it runs itself — local weights rarely ask a question, and
they do not fence their code, so neither fault could appear until a
hosted model was measured.

Two habits came out of it, both cheap, and both from numbers the tool
was already printing:

- **Read the variance, not only the mean.** A flat line across passes of
  a benchmark that changes verdict two thirds of the time means
  something stopped being decided by the model.
- **Count the runs that used no model steps.** They went from none to
  ten when a mechanical path started answering wrongly. On the current
  suite fifteen of seventy-five runs use no model, and all fifteen are
  correct.

And the counterweight: a fix that moves no score is the normal case
here. Two were kept for that reason. Guarding against a draft that
deletes the function it was sent to fix took that outcome from four runs
in twelve to none, while the pass rate stayed inside the noise. It
converts *deleted the function* into *did not fix the bug* — the same
score, and a file left intact rather than damaged.

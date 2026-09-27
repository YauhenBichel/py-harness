---
title: Experiments, every run
description: Every measured run since 24 September 2026, generated from the ledger records in this folder, with the decision-model measurements beside them.
permalink: /experiments/
date: 2026-09-27
type: article
---

# Experiments, every run

Every run since 24 September goes through `scripts/measure/experiment.py`,
which files a record under `docs/experiments/` with its commit, model and
every raw row, and refuses to call a gap inside the noise floor a result.
"Worked" is read off the project afterwards by running the code; "hit the
step limit" is a run that landed something and never managed to say done.

| date | experiment | model | tiers | passes | worked | hit the step limit | mean steps | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-09-24 | `baseline-t1-qwen3coder30b` | qwen3-coder:30b | 1 | 3 | **9 / 9** | 0 | 4.0 | smoke: tier 1 on the 30B |
| 2026-09-24 | `tier6-qwen3coder30b` | qwen3-coder:30b | 6 | 5 | **20 / 20** | 2 | 5.0 | the tier that was a wall for the 8B, on the 30B |
| 2026-09-24 | `tier6-qwen35-9b` | factory-qwen3.5-9b:q4_K_M | 6 | 5 | **16 / 20** | 0 | 3.6 | same tier, a 9B; 2 runs errored (host) |
| 2026-09-24 | `all-tiers-qwen3coder30b` | qwen3-coder:30b | 1,2,3,4,5,6 | 5 | **72 / 75** | 12 | 4.2 | tiers 1–6 on the 30B; 3 runs errored (host) |
| 2026-09-27 | `decide-regex` | qwen3-coder:30b | 5,7 | 5 | **30 / 30** | 9 | 4.4 | regex decider, 30B, tiers 5+7 |
| 2026-09-27 | `decide-model` | qwen3-coder:30b | 5,7 | 5 | **30 / 30** | 16 | 6.0 | decision model, 30B: same score, 16 runs never said done |
| 2026-09-27 | `bugfix-closes-regex` | qwen3-coder:30b | 5,7 | 5 | **30 / 30** | 3 | 3.2 | after fix 1 (bug fix closes on a green suite) |
| 2026-09-27 | `bugfix-closes-model` | qwen3-coder:30b | 5,7 | 5 | **30 / 30** | 3 | 2.2 | after fix 1, decision model |
| 2026-09-27 | `bugfix-done-regex` | qwen3-coder:30b | 5,7 | 5 | **30 / 30** | 0 | 1.9 | after fix 2 (done taken when asked, even in prose) |
| 2026-09-27 | `bugfix-done-model` | qwen3-coder:30b | 5,7 | 5 | **30 / 30** | 0 | 1.4 | after fix 2, decision model |
| 2026-09-27 | `decide-regex-7b` | qwen2.5-coder:7b | 5,7 | 5 | **6 / 30** | 24 | 8.3 | regex decider on a 7B |
| 2026-09-27 | `decide-model-7b` | qwen2.5-coder:7b | 5,7 | 5 | **11 / 30** | 18 | 6.5 | decision model on a 7B: REAL +5, all from one repair |
| 2026-09-27 | `diff-json-7b` | qwen2.5-coder:7b | 5,7 | 5 | **15 / 30** | 15 | 5.6 | 7B, parser reads diffs and JSON turns: REAL +4 |
| 2026-09-27 | `bare-diff-7b` | qwen2.5-coder:7b | 5,7 | 5 | **15 / 30** | 14 | 5.2 | 7B, parser reads a bare diff too: NOISE, floor 3 |

**The decision model against the regexes.** `bge-m3` embeddings and one
logistic regression per intent, fitted on 841 generated phrasings
([the dataset](https://huggingface.co/datasets/YauhenBichel/py-harness-intents)).

| is it a bug fix? | decision model | regex | prompted 1.5B |
| --- | --- | --- | --- |
| 203 held-out generated phrasings, 12 intents | **90%** multi-class; bugfix F1 **0.91** | bugfix F1 0.10 | — |
| 55 hand-written phrasings | **86%**, 0 false positives | 53%, 3 | 63%, 5 |
| 19 hand-labelled probe cases, 3 repeats | **17 / 19** | 11 / 19 | 12 / 19 |
| benchmark cases the two deciders route apart | tiers 1–6: **0 of 15**; tier 7: **4 of 4** | | |

**What the runs say.** On the 30B the decider cannot move a pass count
that is already 30 / 30; it exposed three harness faults on the bug-fix
path instead (runs that never said done: 16 → 3 → 0). On the 7B it is
REAL, +5 of 30, all of it one case the harness then repairs without the
model. Reading the 7B's replies as it writes them — diffs and JSON — is
another REAL +4. After that the 7B's own pass-to-pass spread is three
cases, so five passes cannot see a smaller gain.

**Not measured.** `llama3.1:8b` on the GPU host (Ollama 0.34.0, ROCm) is
coherent under about 500 prompt tokens and word salad above, so no number
from it means anything until that is understood; the 7B stands in.

The records: this folder and the same files on
[Hugging Face](https://huggingface.co/datasets/YauhenBichel/py-harness-intents/tree/main/experiments).
The write-ups: [What would make it useful](https://yauhenbichel.github.io/py-harness/investigations/what-would-make-it-useful/)
and the [Experiments](https://yauhenbichel.github.io/py-harness/investigations/experiments/) appendix.

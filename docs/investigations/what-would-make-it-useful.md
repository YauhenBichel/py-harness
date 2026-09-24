---
title: What would actually make this useful
description: Two literature reviews and this project's own numbers agree on the order of work. The model ceiling turned out to be the cheapest thing to fix, and training is not viable yet with thirty rows of data.
permalink: /investigations/what-would-make-it-useful/
date: 2026-09-24
type: article
---

The benchmark says **64 of 75**. Pointed at a real 259-file repository,
the same harness spent twenty steps, never wrote the function it was
asked for, and left the test suite broken. Both statements are true, and
the gap between them is the whole problem.

This note is a review of what could close it: every method the
literature offers, weighed against what has already been measured here.

## What this project has already proved to itself

| | |
| --- | --- |
| Harness repairs, no model change | **51 → 64 of 75** |
| Four sampled drafts plus an execution check, 0.5B | **0 / 54 greedy → 9 / 18** |
| 0.5B LoRA, greedy | **0 / 54** |
| Training rows on hand | **30** |
| Drafts the agent loop samples per step | **one, greedy** |

Two of those rows matter more than the rest. Sampling several drafts and
keeping the one that runs is the largest effect this project has ever
measured from a change that is not a harness repair — and **the agent
loop does not do it.** It takes one greedy draft per step. The result
came from a separate script evaluation and was never brought into the
loop.

## The model ceiling was the cheapest thing to fix

Tier six is platform work: environment flags, virtualenv paths,
`KEY=VALUE` files, retries. It is where two 7–8B models stopped at the
same place, and the tier a hosted 32B was rented to clear.

| tier six, twenty runs each | worked |
| --- | --- |
| `qwen3-coder:30b`, local | **20 / 20** |
| `Qwen2.5-Coder-32B`, hosted, billed | 18 / 20 |
| `llama3.1:8b`, the old default | 8 / 20 |

A second local model on the same four cases, same day, same machine:
`factory-qwen3.5-9b` scored 16 of 20, losing `env-flag` 2 of 5 — the
same case the old 8B never passed. Two of its runs never started, which
the record marks separately so they are not counted as failures.

Across all fifteen cases, five passes:

| all tiers, 75 runs | worked |
| --- | --- |
| `qwen3-coder:30b`, local | **72 / 75** |
| `llama3.1:8b`, recorded 6 September | 64 / 75 |


Measured today, in four minutes, on a machine that already had the model
pulled. The old ceiling of 7–8B came from an 18 GB laptop. It is not the
ceiling here, and every plan that routed around it — escalate to a
hosted model, distil the 32B's platform knowledge into an 8B — was
solving a problem this machine does not have.

## What the literature offers, ranked by effect over cost

Two reviews, one on inference-time methods and one on training, over
roughly 2024–2026 work.

| Method | Best measured effect | Cost | Fit here |
| --- | --- | --- | --- |
| Fixed pipeline instead of a free agent | 19.2% vs 11.2% SWE-bench Verified, 8B — **+8.0pp** | *Negative*: fewer turns | Strong |
| Grammar-constrained action format | Qwen3-0.6B **16.7% → 59.2%**; mean **+12.7pp** over 13 models 0.5–4B | ~zero, measured *faster* | Strong |
| Best-of-n with an execution verifier | 15.9% → 56% at 250 samples; **+7.9pp** at K=16 for small models | Linear in n | Strong |
| Blind resampling instead of self-repair | **+6.1pp** over self-repair at 1.5B, 2.5–5.5× fewer tokens | Lowest of any retry | Strong |
| Localisation: repo map, AST index | 69.7% file-level (Agentless); BM25 top-30 87.7% recall at **3.4% precision** | Index build | Needed at scale |
| Context compaction | Required at 8B; "context rot" costs 13.9–85% accuracy as context grows | Summarisation calls | Needed at scale |
| Self-repair on a traceback | +9.8pp at 8B; **negative below 3B**, null at 7B | 2× tokens | Conditional |
| MCTS over edits | +23% relative, SWE-bench Lite | Up to 100 iterations | Poor per token |
| Narrow-skill distillation | 350M tool-caller **77.6%** on ToolBench | 1k–20k examples, hours | Later |
| Fine-tuning on trajectories | 7B: **+1.0pp**. 14B: +8.0pp. 32B: +8.5pp — same data | 500+ trajectories, multi-GPU | Not yet |
| RL with execution rewards | Llama-3-70B → 41.0% Verified | 1k–10k tasks, sandbox | Not yet |
| Process reward models | 32.0% Verified with a trained verifier | A second model | Skip: run the tests |

## Why the 0.5B adapter scored zero, and why that was predictable

It is the expected result, not a bad run.

Reinforcement and rejection-sampling methods are bounded by what the
base model can already produce: if it never samples a correct answer, a
pass/fail reward gives no gradient and there is nothing to train on.
Next-token loss on trajectories rewards surface form — formatting, call
syntax, comment style are frequent and low-entropy, while correctness is
a sparse global constraint. So a small adapter learns the shape of an
answer and not its substance. That is exactly what was observed: the
style changed and 0 of 54 ran.

The measured floor for agent work is between 7B and 14B. On identical
data, the same fine-tune moved a 7B by 1.0 point and a 32B by 8.5.

**With thirty rows on hand and five hundred the usual minimum, training
is not a live option.** It is also no longer the pressing question: the
capability it was meant to buy is available locally at 20/20.

## The order of work

1. **Change the default model.** Free, measured, done in four minutes.
   Nothing else on this list is close.
2. **Constrain the action format with a grammar, not a prompt.** The
   parser here needed five separate repairs for drafts that failed to
   parse — bold labels, list markers, a reason after the verb, a
   whole-reply fence. That is the format-compliance failure the
   literature says dominates small models, and grammar-constrained
   decoding is free and largest at the smallest sizes.
3. **Sample several drafts per step and keep one that survives the
   checks.** This project's own biggest non-harness result, still not in
   the loop.
4. **Resample blind on a refused step rather than arguing with the
   model.** Cheaper and better below 7B.
5. **Build a real-repository tier for the benchmark.** The fixture is
   four or five files. The failure is at 259. Until this exists, every
   change above is judged by an instrument that cannot see the problem.
6. **Try a fixed localise → repair → validate pipeline** against the
   free-running loop, as a measured arm rather than a rewrite.

Training sits below all of these, and should stay there until a base
model passes often enough to generate its own training data.

## How each of these gets measured

Through `scripts/measure/experiment.py`, which files an arm with its
commit, model and raw rows, and refuses to call a difference inside the
noise floor a result. Every row in the plan above is one `run` and one
`compare`.

```bash
python scripts/measure/experiment.py run baseline --tier 6 --repeat 5
python scripts/measure/experiment.py run grammar --tier 6 --repeat 5
python scripts/measure/experiment.py compare baseline grammar
```

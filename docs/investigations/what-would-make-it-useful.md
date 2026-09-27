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

## A decision model, measured

The harness already reduces every task to small decisions before a
model runs: `task.py` holds thirty-one regular expressions and about
twenty `looks_like_*` functions, each answering a narrow yes/no about
the task. Nobody had measured how often they are wrong.

So three deciders were put on the same held-out phrasings:

- the **regex** in `task.py` today;
- a **decision model** — `bge-m3` sentence embeddings and one logistic
  regression per intent, fitted in numpy on phrasings it was never
  tested on;
- a **prompted small model** (`qwen2.5:1.5b-instruct`) asked the same
  question as yes/no.

The phrasings: 1,201 generated by a local 30B across twelve intents and
five styles, then every one labelled *blind* by the same model with no
hint of how it was made, and kept only where the two passes agreed —
**1,044 survived**, 841 to train and 203 held out. Plus 55 hand-written
phrasings the model never saw.

| on 203 held-out phrasings | model | regex |
| --- | --- | --- |
| multi-class accuracy | **90%** | — |
| `bugfix` F1 | **0.91** | 0.10 |
| `add_feature` false positives | 3 | **23** |
| `question` false positives | 1 | **19** |
| `platform_ops` F1 | **1.00** | 0.00 |
| `new_package` F1 | **0.85** | 0.26 |

| on 55 hand-written phrasings, is-it-a-bug-fix | right | false positives |
| --- | --- | --- |
| decision model | **86%** | 0 |
| prompted 1.5B | 63% | 5 |
| regex | 53% | 3 |

The regex is not bad on the easy cases. It is bad on the way people
actually write: "the totals come out one too low" has no keyword in it.
The decision model reads that as a bug fix; the regex does not.

The prompted small model is the form of this idea the literature
warned about, and it measured that way: barely above the regex, and
five false positives — it says yes to things that are not bug fixes.
The same intuition, as a fitted classifier over embeddings, is the form
that works. Each decision costs about fifty milliseconds and no GPU.

Two honest limits. The held-out 203 were generated by the same model
that generated the training set, so 90% is the optimistic number; the
55 hand-written ones are the trustworthy one, and 86% against 53% is
still not close. And the agreement gate threw out 156 phrasings, mostly
where two intents genuinely overlap — a new package against a new
function, a review against a question. A router should treat those as
neighbours, not as exclusive.

**So: yes, a decision model for this project is worth building.** It is
already built, at the size of a script. What remains is wiring it in
where the regexes are, one decision at a time, and measuring each swap
through `experiment.py`.

### Where it lives

The sample, the rejects, and every measurement are published as
[YauhenBichel/py-harness-intents](https://huggingface.co/datasets/YauhenBichel/py-harness-intents)
on the Hub, with a card that says how the sample was made and what it
cannot show.

The model is in the harness as `harness.decide.intent`: the fitted
weights as a 101 KB JSON file, and scoring as one dot product per intent
in plain Python. It is behind a switch — `AgentOptions.decide`, `--decide
model` on the benchmark and the experiment pipeline — that defaults to
the regex, so nothing already measured moves. With the switch on, the
intent is decided once at the start of a run and registered against the
task text, so the twelve places that ask `looks_like_bugfix` see it
without being changed, and it is forgotten when the run ends so a later
arm measured with the regex cannot inherit it. If no embedding model is
reachable, nothing is registered and the regex answers as before.

Whether the swap helps the *benchmark* — not just the decision — is a
separate measurement. It was made on 27 September, and what it found
was not about the decider.

### What the decider exposed

First, which cases could an A/B even move? `intent_routes.py` asks
both deciders about every benchmark task before anything runs. On
tiers 1 to 6, **none of the fifteen route differently**: every fix
there says "fix" or names the exception, which is exactly what the
regex keys on. An A/B on those tiers compares a run with itself, and
the tool now says so. So a seventh tier was added — the tier-5 bugs
said the way people report them, with no keyword in them:

> the totals from compute_total in src/orders.py come out one too low

Four cases, and all four route differently: the regex sees a feature,
the decision model sees a fix.

Then the A/B, on tiers 5 and 7, five passes, a local 30B. Both arms
scored **30 of 30**. The verdict on the pass count is NOISE, as it has
to be at a ceiling. But the ledger also counts something the pass count
cannot see: runs that landed the fix and then **never managed to say
done**, burning the rest of their budget until the step limit stopped
them.

| tiers 5 and 7, 30 runs an arm | worked | hit the step limit | mean steps | minutes |
| --- | --- | --- | --- | --- |
| regex | 30/30 | 9 | 4.4 | 6.2 |
| decision model | 30/30 | **16** | 6.0 | **16.9** |

Routing a symptom-phrased task as a fix — correctly — made the run
worse. Tracing one showed why, and it was two harness faults on the
bug-fix path, both already there on tier 5 with only one case to show
them:

1. After the patch landed, the policy demanded a new test and rendered
   the write-tests skill, whose example calls `multiply` and `weekday`.
   The 30B copied the example verbatim, the gate refused it because
   `multiply` did not exist, and the model added a `multiply` to the
   named file to make its own copy pass.
2. Once that was over, every non-write turn was still answered with
   "Next Action must be patch Path: src/orders.py with a Find:", so the
   model re-sent a Find: that no longer matched, four turns in a row.

Fixed: a bug fix closes when the suite is green, and the named-file
nudge stands down once that file has been patched. Re-measured, with
the same cases and the same model:

| after the first fix | worked | hit the step limit | mean steps | minutes |
| --- | --- | --- | --- | --- |
| regex | 30/30 | 3 | 3.2 | 3.7 |
| decision model | 30/30 | 3 | 2.2 | 5.0 |

The three that remained were a third fault. Told "Tests passed. Action:
done Summary: say what you changed", the model answered with the
summary as a sentence and no Action line, was told it could not be
parsed, and then pasted its whole plan again with the stale patch above
the done block, which the parser took. Fixed too: once the finishing
nudge has been sent, a reply with no Action line is the summary, and a
reply with several blocks is read at its done block.

| after both fixes | worked | hit the step limit | mean steps | minutes |
| --- | --- | --- | --- | --- |
| regex | 30/30 | **0** | 1.9 | 1.5 |
| decision model | 30/30 | **0** | 1.4 | 4.0 |

So, the honest answer on the decider. On a 30B at the ceiling it does
not change whether a run works. It changes how a run closes: the
symptom-phrased NameError goes from three model steps to none, because
routing it as a fix lets the harness's own typo repair handle it, which
is where the zero-step count moving from 5 to 10 comes from. Mean
steps 1.9 against 1.4 is the whole measurable difference, and the
model arm's extra minutes are the embedding call, which loads `bge-m3`
beside the 30B on the same host. Where the routing should matter is on
a model that cannot recover from a wrong path — the 8B — and on a real
repository, and neither has been measured yet.

What the day actually produced is the pattern this whole note keeps
finding: the instrument was wrong before the model was. Two arms at
30 of 30 hid one arm taking nearly three times as long as the other.
`compare` now reports runs that hit the step limit and mean steps
beside the pass count, and refuses to let a first arm's own ledger
record mark the second arm as unreplayable.

### On a 7B, the decider moves the score

The same A/B on a model that cannot recover from a wrong path:
`qwen2.5-coder:7b`, tiers 5 and 7, five passes, same GPU, after the
three fixes above.

| tiers 5 and 7, 30 runs an arm | worked | hit the step limit | mean steps |
| --- | --- | --- | --- |
| regex | 6/30 | 24 | 8.3 |
| decision model | **11/30** | 18 | 6.5 |

**REAL: +5, outside a floor of 1.** The first time the decider has moved
a pass count. And the whole of it is one case: the symptom-phrased
NameError goes from 0 of 5 to 5 of 5. The regex reads "stops with: name
'subtotl' is not defined" as a feature request and hands it to a model
that cannot fix it in ten steps; the decision model reads it as a fix,
and the harness's own typo repair then lands it in zero steps, before
the model is asked anything. The keyword version of the same bug was
already 5 of 5 on both arms for the same reason.

The other four bugs the 7B cannot fix on either route, 1 of 5 at best.
So the honest reading is narrower than "the decider helps": on a small
model the decider is worth exactly what the harness can do
deterministically once it knows what kind of task it has. Today that
is the typo repair. Every further deterministic repair on the bug-fix
path widens that gain; nothing on the model's side does.

### Reading the small model's replies

The 7B's failures were traced next, and none of the first three was
reasoning. Asked to fix a one-line bug, it wrote the fix as a fenced
unified diff under `Action: patch` — correct and complete — and heard
"patch needs Find: or Append:" ten times. On another run it answered
every turn as a JSON object with an `action` key, once with
single-quoted values, and parsed to nothing ten times. On a third it
sent the diff with no Action line at all. This is the format-compliance
failure the literature review above said dominates small models,
arriving in three shapes.

The parser now reads all three: a hunk's removed lines are the Find and
its added lines the Replace, a JSON object with a known action is a
turn, and a reply that is only a diff is a patch to the file in its
header. Measured on the same arm as above, one reading at a time:

| 7B, tiers 5 and 7, decision model | worked | hit the step limit | mean steps |
| --- | --- | --- | --- |
| before | 11/30 | 18 | 6.5 |
| diff under Action, and JSON | **15/30** | 15 | 5.6 |
| bare diff too | 15/30 | 14 | 5.2 |

The first step is **REAL, +4 outside a floor of 1**: the "one too low"
bug goes from 1 of 5 to 4 of 5, and the keyword off-by-one from 0 to 1.
The second step is NOISE: the same 15, with the cases reshuffled inside
a floor of 3. That floor is the other finding. At 15 of 30 the 7B's
own pass-to-pass spread is three cases, so with five passes nothing
smaller than a four-case gain can be seen at all, and the bare-diff
reading, which can only turn an unparsed reply into a patch, is below
it. The two bugs still at 1 of 5 are model errors now — a wrong line
patched and `done` said over it — not the harness refusing a right
answer.

So on this model the ordering from the top of the note held: after the
decider's one repair, the next four cases came from reading what the
model wrote, not from asking it to write differently.

### A note on the 8B

The plan was to measure on `llama3.1:8b`, the everyday model. On the
GPU host it could not be measured: coherent under about five hundred
prompt tokens and word salad above that, at every context size and
batch size tried, until the length limit — the harness's real first
prompt, 1,269 tokens, got 6,923 tokens of nothing. The 30B and the 7B
on the same prompt are fine, so it is that model on that Ollama build
(0.34.0, ROCm), not the prompt. A first probe returned garbage on a
2,846-token prompt and was read as "the model answered"; the
instrument, again. Until it is understood, no number from that host
for that model means anything, and the 7B stands in for the small
model.

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

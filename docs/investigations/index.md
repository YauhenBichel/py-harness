---
title: Results
description: A map of the measurements. Start here, then open one note. Dates are the day of the run.
date: 2026-09-05
---

# Results

Every score on this site comes from one laptop. Open one note. Each
note is one question, what I typed, and what happened.

**Not ready for daily work.** That bar means beating a plain 8B both at
picking the next step and at fixing a real bug the helper cannot do
itself. It does not, yet.

Public pages do not name other editors or chat products.

<div class="stats">
  <div class="stat"><b>9 / 9</b><span>8B daily jobs, evening of 5 Sep</span></div>
  <div class="stat"><b>7 / 9</b><span>7B coder, same jobs</span></div>
  <div class="stat"><b>8 / 15</b><span>8B first-step reading</span></div>
  <div class="stat"><b>0 / 54</b><span>tiny 0.5B LoRA, greedy</span></div>
</div>

## Read these first

<div class="tracks">
  <div class="track">
    <h2>The scores</h2>
    <p><a href="{{ '/investigations/experiments/' | relative_url }}">Experiments</a> — paper form: abstract, methods, every measured run. 0.5B is 500 million weights.</p>
    <p><a href="{{ '/investigations/which-model/' | relative_url }}">Which model</a> — keep <code>llama3.1:8b</code>. A 7B coder is close, not better.</p>
    <p><a href="{{ '/investigations/hub-models/' | relative_url }}">Hub models</a> — which Hugging Face weights fit 18 GB, and how to import two that Ollama does not ship.</p>
  </div>
  <div class="track">
    <h2>How to use the tool</h2>
    <p><a href="{{ '/scenarios/' | relative_url }}">What you type</a> — the four jobs on <code>demo/orders</code>.</p>
    <p><a href="{{ '/investigations/first-run-four/' | relative_url }}">First-run four</a> — those jobs failed, then the helper finished them.</p>
    <p><a href="{{ '/cite/' | relative_url }}">Cite</a> — APA and BibTeX for this software.</p>
    <p><a href="{{ '/references/' | relative_url }}">References</a> — papers the design sits on.</p>
  </div>
</div>

## Which model

| Note | In one sentence |
| --- | --- |
| [Which model]({{ '/investigations/which-model/' | relative_url }}) | Evening daily: 8B 9/9, 7B coder 7/9. 8192-warmed SWE daily clamp: first generate 180s. Keep the 8B. |
| [The instrument was broken]({{ '/investigations/measuring/' | relative_url }}) | A day comparing models found two faults in the benchmark instead. Every model number before this is unsafe. |
| [The fence was the whole story]({{ '/investigations/the-fence/' | relative_url }}) | The hosted 32B was never the problem. 1 of 10 became 9 of 10 once four backticks stopped reaching the Python parser. |
| [The wall two local models share]({{ '/investigations/the-wall/' | relative_url }}) | Tier six: 18 of 20 hosted 32B, 8 and 11 for the two local models. They are level; the gap to the larger one is not. |
| [What the totals were hiding]({{ '/investigations/totals-hide-things/' | relative_url }}) | 9 of 20 against 10 of 20 looked like noise. It was two opposite effects, one of them a wrong function written with no model. Now 19 of 20. |
| [A day of repairs]({{ '/investigations/a-day-of-repairs/' | relative_url }}) | Nine fixes, 51 of 75 to 64 of 75. Almost none of it was the model. Two moved nothing and are kept anyway. |
| [Where py-harness stands]({{ '/status/' | relative_url }}) | The status board: what is fixed, what is open, and what to do next, ranked by harm. |
| [Two models, one wall]({{ '/investigations/two-models/' | relative_url }}) | The same 75 jobs. 51 vs 50. They fail in opposite ways. |
| [Model lanes]({{ '/investigations/model-lanes/' | relative_url }}) | Which local weight for a question, a write, or a ship. Default stays 8B. |
| [Hub models]({{ '/investigations/hub-models/' | relative_url }}) | 8192-warmed SWE daily clamp: first generate 180s. Do not switch. |
| [Cloud weights]({{ '/investigations/cloud-weights/' | relative_url }}) | A larger model on a rented GPU. The helper stays on this machine. |
| [Everyday laptop]({{ '/investigations/everyday-laptop/' | relative_url }}) | Why the 0.5B adapter is a demo, not daily work. |
| [Bench record]({{ '/investigations/bench-record/' | relative_url }}) | The machine, what fits in 18 GB, and the runs behind the numbers. |

## What we measured

| Note | In one sentence |
| --- | --- |
| [Experiments]({{ '/investigations/experiments/' | relative_url }}) | Paper form. 0.5B means 500 million weights, not the daily 8B. |
| [0.5B exact stdout]({{ '/investigations/held-out-exec-eval/' | relative_url }}) | 18 scripts, three times each. 7 / 54, then 12 / 54 after one repair. |
| [0.5B sample-and-run]({{ '/investigations/sample-and-run/' | relative_url }}) | Four drafts found 9 / 18. A later loop 12 / 18. The adapter at greedy temperature: 0 / 54. |
| [0.5B vibe review]({{ '/research-vibe-review/' | relative_url }}) | Held-out short scripts, and a 100-file walk that was not a review. |
| [First-run four]({{ '/investigations/first-run-four/' | relative_url }}) | 0 / 4 by hand, then 4 / 4 once the helper did the compiler jobs. |
| [Same jobs, same evening]({{ '/investigations/same-jobs/' | relative_url }}) | Eleven demo tasks. Laptop 8B vs a hosted IDE agent. |
| [Local loop vs hosted agents]({{ '/investigations/local-vs-cloud/' | relative_url }}) | Every shipped path against a hosted IDE agent. |

## Where it fails

| Note | In one sentence |
| --- | --- |
| [Where the failures are]({{ '/investigations/failures/' | relative_url }}) | A third of runs fail. Most of those wrote the wrong code. |
| [When a run says done and means nothing]({{ '/investigations/false-finish/' | relative_url }}) | Five in ten claimed success having written nothing. After two fixes, none did. |
| [What the helper cannot fix]({{ '/investigations/limits/' | relative_url }}) | Cases where the helper knew the answer and the model still missed. |
| [Asking a bigger model]({{ '/investigations/asking-a-bigger-model/' | relative_url }}) | A run that stops to ask has already failed, three times in three. |
| [Small steps, measured]({{ '/investigations/small-steps/' | relative_url }}) | Splitting one hard job into easy ones bought nothing. |
| [What to improve]({{ '/investigations/what-to-improve/' | relative_url }}) | Gaps a helper can close, and gaps it cannot. |

## How it is built

| Note | In one sentence |
| --- | --- |
| [Fine-tune or harness]({{ '/investigations/fine-tune-or-harness/' | relative_url }}) | Do not train on 35 pairs or 30 seed traces. Later, about 2k clean turns. |
| [Small models, classic development]({{ '/investigations/small-llm-harness/' | relative_url }}) | How an 8B finishes careful work: checks, not hope. |
| [Harness comparison]({{ '/investigations/harness-comparison/' | relative_url }}) | What transfers from other published helpers. No free shell. |
| [Everyday skills]({{ '/investigations/everyday-skills/' | relative_url }}) | Each skill is one copy-paste step, written for an 8B. |
| [Skills]({{ '/skills/' | relative_url }}) | The twenty-four kit skills and when each one loads. |
| [Platform engineering]({{ '/investigations/platform-engineering/' | relative_url }}) | Small files that must work on every OS. |
| [What would make it useful]({{ '/investigations/what-would-make-it-useful/' | relative_url }}) | Every method, ranked against this project's own numbers. A local 30B scores 20/20 where the old default scored 8/20. |
| [Architecture]({{ '/architecture/' | relative_url }}) | Layers from the bottom up. A cycle fails the merge gate. |

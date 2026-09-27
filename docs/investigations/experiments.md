---
title: Experiments
description: A laptop paper. Numbered citations, methods, headline scores, then the full tables. 0.5B is 500 million weights.
permalink: /investigations/experiments/
date: 2026-09-06
type: article
---

# Experiments

<p class="paper-meta">Yauhen Bichel · 6 September 2026 ·
<a href="https://github.com/YauhenBichel/py-harness">github.com/YauhenBichel/py-harness</a></p>

<nav class="toc" aria-label="On this page">
<p>On this page</p>
<ol>
  <li><a href="#abstract">Abstract</a></li>
  <li><a href="#introduction">Introduction</a></li>
  <li><a href="#related-work">Related work</a></li>
  <li><a href="#methods">Methods</a></li>
  <li><a href="#results">Results</a></li>
  <li><a href="#discussion">Discussion</a></li>
  <li><a href="#limitations">Limitations</a></li>
  <li><a href="#conclusion">Conclusion</a></li>
  <li><a href="#references">References</a></li>
  <li><a href="#appendix-full-tables">Appendix</a></li>
</ol>
</nav>

<div class="abstract" markdown="1">

## Abstract

A local helper plus a small open model was asked to do four daily
Python jobs on one laptop: answer a question, write a test, fix a
bug, add one function. Dates: 29–30 August and 5 September 2026.

**0.5B** means a model with about **500 million weights** —
Qwen2.5-Coder-0.5B, plus an optional public LoRA. It is the tiny
Hub demo, not daily work. **8B** means about **8 billion weights**
— Ollama `llama3.1:8b`, the default. **7B** is
`qwen2.5-coder:7b`.

The 0.5B adapter is a style prior, not an agent (held-out vibe
**0 / 4**; greedy LoRA **0 / 54**). One traceback repair lifts
exact-stdout from **7 / 54** to **12 / 54**. Daily jobs on the 8B
reached **9 / 9** the same evening the 7B coder scored **7 / 9**.
The helper moved the four Start commands from **0 / 4** to
**4 / 4** by doing compiler jobs itself. The everyday-ready bar —
beat a plain 8B at the next step **and** at a real bug the helper
cannot write — is not met. This paper does **not** report a
SWE-bench score. A hosted **32B** was measured once the
benchmark itself was repaired: it scores **9 / 10** on tier 3, where
before the repair it scored **1 / 10**. A day of repairs to the harness
and the benchmark then took the whole suite from **51 / 75** to
**64 / 75** without asking more of the model.

</div>

<div class="stats">
  <div class="stat"><b>12 / 18</b><span>tiny 0.5B (500 million weights), four drafts then a later loop</span></div>
  <div class="stat"><b>0 / 54</b><span>same 0.5B + LoRA, one greedy try each</span></div>
  <div class="stat"><b>8 / 15</b><span>daily 8B (8 billion weights) picked the right first step</span></div>
  <div class="stat"><b>9 / 9</b><span>daily 8B jobs, evening of 5 Sep</span></div>
</div>

## Introduction

The question is whether a laptop helper and a small open model can
do everyday Python without a hosted agent. Two sizes are easy to
mix up: the **public 0.5B** (500 million weights, a style prior)
and the **daily 8B** (8 billion weights, what `ask` / `run` call).

“Everyday-ready” means: beat a plain 8B at reading the next step,
**and** at fixing a real bug the helper cannot write. The first
“real bug” cell was a whole-line `return 0.0` on a named sum — the
helper can write that, so it is no longer a model job.

This note is the paper. The long run log is the
[appendix](#appendix-full-tables). Cite the software or a score
with [Cite]({{ '/cite/' | relative_url }}). The machine:
[Bench record]({{ '/investigations/bench-record/' | relative_url }}).

## Related work

The loop is one `Action:` block, then tools — a tight read-act
loop, not a free shell <a class="cite" href="#ref-1">[1]</a>.
SWE-agent showed that the interface around the same model moves
the score <a class="cite" href="#ref-2">[2]</a>: previous best
retrieval-only 3.8%, agent 12.5%; same model 1.3% → 12.5%. The
first-run four jobs here were **0 / 4** then **4 / 4** after the
helper. Same shape, smaller tree.

CodeAct lets the model emit Python as the action
<a class="cite" href="#ref-3">[3]</a>. This project uses named
actions and a write limit. A green suite that never called the bug
is not done <a class="cite" href="#ref-4">[4]</a>. `run` may send
**one** traceback back <a class="cite" href="#ref-5">[5]</a>
<a class="cite" href="#ref-6">[6]</a>. Small models can be workers
at 7–8B <a class="cite" href="#ref-7">[7]</a>; that is not a claim
that a 0.5B style adapter is an agent. SWE-bench is the field’s
ruler <a class="cite" href="#ref-8">[8]</a> and the wrong ruler
for a one-folder laptop helper. This paper does **not** report a
SWE-bench score.

The longer list of papers: [References]({{ '/references/' | relative_url }}).

## Methods

**Machine.** One Apple M3 Pro laptop, 18 GB unified memory. Ollama
for most cells; MLX for the 0.5B sample-and-run cell
<a class="cite" href="#ref-9">[9]</a>.

**Models.** Size names are weight counts, not versions.

| Name | Weights | What it is | Role |
| --- | --- | --- | --- |
| **0.5B** | 500 million | Qwen2.5-Coder-0.5B <a class="cite" href="#ref-10">[10]</a>. Ollama `qwen2.5-coder:0.5b` or MLX 4-bit. Optional LoRA <a class="cite" href="#ref-11">[11]</a> [YauhenBichel/python-vibe-0.5b](https://huggingface.co/YauhenBichel/python-vibe-0.5b), step 100 | Style prior. Not daily `ask` / `run` |
| **7B** | 7 billion | `qwen2.5-coder:7b` unless a table names another tag | Same-night comparison |
| **8B** | 8 billion | Ollama `llama3.1:8b` <a class="cite" href="#ref-12">[12]</a> | Daily default |
| **32B** | 32 billion | Hosted `Qwen2.5-Coder-32B-Instruct` | One GPU comparison, after the fence fix |

A “clean” 8B is the same 8 billion weights with no agent system
prompt and no loop. The 0.5B file on disk is about 400 MB; the 8B
is about 4.9 GB.

**Tasks.** Four daily jobs on `demo/orders` unless a table names
another fixture. A case counts only if the function runs and does
the job — not if a file appeared, and not if the run said `done`.
Writes stay inside the named folder. There is no general shell.

**Scoring.** One run unless the table says otherwise. A gap of one
or two cases is noise. Compiler-bound cells (NameError `subtotl`,
whole-line `return 0` on a named sum) finish with no model. They
are not model scores. Replay scripts live in `scripts/measure/`.
The full cells are in the [appendix](#appendix-full-tables).

## Results

### 0.5B — 500 million weights

Held-out vibe (weekday, count-md, jsonl, docstring): **0 / 4**.
Parsed `Action:` that day: **0 / 2**. Exact stdout, 18 scripts × 3,
Ollama `qwen2.5-coder:0.5b` <a class="cite" href="#ref-13">[13]</a>:
base **7 / 54**, one traceback repair **12 / 54**. Greedy LoRA:
**0 / 54**. Four drafts then a later loop: **12 / 18**
<a class="cite" href="#ref-14">[14]</a>. Sampling found a different
set, not a superset.

### Daily 8B and 7B

Same evening, 5 September 2026. `llama3.1:8b`: **9 / 9**.
`qwen2.5-coder:7b`: **7 / 9**. First-run four on `demo/orders`:
**0 / 4**, then **4 / 4** after the helper did the compiler jobs.
Live first-Action parse: **8 / 15**.

### Everyday-ready bar

Beat a plain 8B at the next step **and** at a ≥1 KB logic fix the
helper cannot write (`clip`). Last recorded night: harness parse
**8 / 15**, clean 8B **0 / 15**; harness fix **0 / 3**, clean 8B
**3 / 3**. Not everyday-ready.

### A real tree

4,580 first-party files. Reads worked. Write a test or add a
function: **1 / 12**.

### The instrument, then a hosted 32B

A run that stops to ask needs someone to answer. Local 8B almost
never asks; a 7B coder asks in eleven of twenty tier-3 runs. The
same week, a hosted 32B wrapped drafts in markdown fences and the
fence reached the file. Before the harness stripped it:
**1 / 10**. After: **9 / 10**. Local 8B does not fence, so the
same fix leaves it at **10 / 20**. The tables are in the
[appendix](#the-fence-was-the-whole-story)
<a class="cite" href="#ref-16">[16]</a>.

## Discussion

The helper is load-bearing for jobs it can finish without a model
<a class="cite" href="#ref-2">[2]</a>. First-run four went
**0 / 4** to **4 / 4** once the compiler wrote the NameError, the
test, and `total_lines`. The model still has to do the rest. Daily
`llama3.1:8b` is **9 / 9** on small fixtures and **8 / 15** on
first-step parse. The everyday-ready bar asks for a ≥1 KB logic
fix the helper cannot write (`clip`). Harness **0 / 3**, clean 8B
**3 / 3**. The loop helps the 8B pick an Action and does not get a
patch on `clip`.

The 0.5B is a style prior. A traceback fixes `NameError` and
`SyntaxError`, not logic <a class="cite" href="#ref-6">[6]</a>. A
7B coder is close (**7 / 9**) and not better. Writing on a
4,580-file tree is **1 / 12**. Two models of different lineage hit
the same wall (51 vs 50 of 75). That pair was measured before the
instrument was repaired, so the number to trust is the shape, not
the score. Raising the count that works is the target.

The most transferable result is about the instrument, not any
model. Both faults had one shape: the harness had specialised to
the single model it runs itself. Local weights rarely ask, so
nobody noticed there was no one to answer; they do not fence, so
nobody noticed the fence reached the file. A hosted 32B looked
incapable at **1 / 10** and scores **9 / 10** with four backticks
removed <a class="cite" href="#ref-16">[16]</a>. Measure a second
model early. It is the cheapest way to find the assumptions the
first one hides.

## Limitations

One laptop, 18 GB unified memory. One run unless a table says
otherwise; gaps of one or two cases are noise. Several cells are
compiler binds, not model writes. The instrument was wrong for
part of the month: unanswered `ask` stops, and markdown fences
reaching the file. Both are fixed, and every model number from
before 6 September is unsafe. Tier 3 has two cases, so its
run-to-run spread is wide: the same 8B on the same code scored
14 / 20 and 10 / 20 on different nights.

This paper does **not** report a SWE-bench score
<a class="cite" href="#ref-8">[8]</a>. The public numbers are four
jobs on `demo/orders` and a 4,580-file write rate of **1 / 12**.
No hosted chat product is named. No claim that the 0.5B LoRA
audited a real repository.

## Conclusion

Keep `llama3.1:8b`. Do not train more 0.5B steps. Do not switch
the default to a 7B coder or a Hub GGUF that misses the 180s
generate cap. The helper should keep finishing compiler jobs. The
everyday-ready bar stays: beat a plain 8B at the next step
**and** at a real bug the helper cannot write. It does not, yet.

## References

<ol class="refs">
<li id="ref-1">Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K., &amp; Cao, Y. (2023). ReAct: Synergizing reasoning and acting in language models. <i>International Conference on Learning Representations</i>. <a href="https://arxiv.org/abs/2210.03629">arXiv:2210.03629</a></li>
<li id="ref-2">Yang, J., Jimenez, C. E., Wettig, A., Lieret, K., Yao, S., Narasimhan, K., &amp; Press, O. (2024). SWE-agent: Agent-computer interfaces enable automated software engineering. <i>Advances in Neural Information Processing Systems</i>. <a href="https://arxiv.org/abs/2405.15793">arXiv:2405.15793</a></li>
<li id="ref-3">Wang, X., Chen, Y., Yuan, L., Zhang, Y., Li, Y., Peng, H., &amp; Ji, H. (2024). Executable code actions elicit better LLM agents. <i>International Conference on Machine Learning</i>. <a href="https://arxiv.org/abs/2402.01030">arXiv:2402.01030</a></li>
<li id="ref-4">Liu, J., Xia, C. S., Wang, Y., &amp; Zhang, L. (2023). Is your code generated really correct? Rigorous evaluation of large language models for code generation. <i>Advances in Neural Information Processing Systems</i>. <a href="https://arxiv.org/abs/2305.01210">arXiv:2305.01210</a></li>
<li id="ref-5">Shinn, N., Cassano, F., Labash, B., Gopinath, A., Narasimhan, K., &amp; Yao, S. (2023). Reflexion: Language agents with verbal reinforcement learning. <i>Advances in Neural Information Processing Systems</i>. <a href="https://arxiv.org/abs/2303.11366">arXiv:2303.11366</a></li>
<li id="ref-6">McAndrews, C. J. (2026). Feedback over form: Why execution feedback matters more than pipeline topology in 1–3B code generation. <a href="https://arxiv.org/abs/2604.21950">arXiv:2604.21950</a></li>
<li id="ref-7">Belcak, P., Heinrich, G., Diao, S., Fu, Y., Dong, X., Muralidharan, S., Lin, Y. C., &amp; Molchanov, P. (2025). Small language models are the future of agentic AI. <a href="https://arxiv.org/abs/2506.02153">arXiv:2506.02153</a></li>
<li id="ref-8">Jimenez, C. E., Yang, J., Wettig, A., Yao, S., Pei, K., Press, O., &amp; Narasimhan, K. (2024). SWE-bench: Can language models resolve real-world GitHub issues? <i>International Conference on Learning Representations</i> (oral). <a href="https://arxiv.org/abs/2310.06770">arXiv:2310.06770</a></li>
<li id="ref-9">Bichel, Y. (2026). Bench record. In <i>py-harness</i>. <a href="https://yauhenbichel.github.io/py-harness/investigations/bench-record/">yauhenbichel.github.io/py-harness/investigations/bench-record/</a></li>
<li id="ref-10">Hui, B., Yang, J., Cui, Z., Yang, J., et al. (2024). <i>Qwen2.5-Coder technical report</i>. <a href="https://arxiv.org/abs/2409.12186">arXiv:2409.12186</a></li>
<li id="ref-11">Hu, E. J., Shen, Y., Wallis, P., Allen-Zhu, Z., Li, Y., Wang, S., Wang, L., &amp; Chen, W. (2022). LoRA: Low-rank adaptation of large language models. <i>International Conference on Learning Representations</i>. <a href="https://arxiv.org/abs/2106.09685">arXiv:2106.09685</a></li>
<li id="ref-12">Grattafiori, A., et al. (2024). <i>The Llama 3 herd of models</i>. <a href="https://arxiv.org/abs/2407.21783">arXiv:2407.21783</a></li>
<li id="ref-13">Bichel, Y. (2026, September 5). 0.5B exact-stdout eval. In <i>py-harness</i> experiments. <a href="https://yauhenbichel.github.io/py-harness/investigations/held-out-exec-eval/">yauhenbichel.github.io/py-harness/investigations/held-out-exec-eval/</a></li>
<li id="ref-14">Bichel, Y. (2026, September 5). 0.5B sample-and-run. In <i>py-harness</i> experiments. <a href="https://yauhenbichel.github.io/py-harness/investigations/sample-and-run/">yauhenbichel.github.io/py-harness/investigations/sample-and-run/</a></li>
<li id="ref-15">Bichel, Y. (2026). <i>py-harness</i> [Computer software]. <a href="https://github.com/YauhenBichel/py-harness">github.com/YauhenBichel/py-harness</a></li>
<li id="ref-16">Bichel, Y. (2026, September 6). The fence was the whole story. In <i>py-harness</i> experiments. <a href="https://yauhenbichel.github.io/py-harness/investigations/the-fence/">yauhenbichel.github.io/py-harness/investigations/the-fence/</a></li>
</ol>

APA and BibTeX for this software: [Cite]({{ '/cite/' | relative_url }}).

## Appendix: full tables

Each cell below is one question, what I typed, and what happened.
The paper above is the result.

### The 0.5B as daily work

The tiny model: **500 million weights**, not the daily 8B.

**Example.** Public adapter
[YauhenBichel/python-vibe-0.5b](https://huggingface.co/YauhenBichel/python-vibe-0.5b)
on Qwen2.5-Coder-0.5B. Ask it for a weekday-name helper, a markdown
file counter, a jsonl line, a docstring. Ask it to emit `Action:`.

**Result**

| What I asked | What I got |
| --- | --- |
| Held-out vibe (weekday, count-md, jsonl, docstring) | **0 / 4** |
| Parsed `Action:` that day | **0 / 2** |
| Walk a hundred stub files | A hundred “no issues”. Not a review |
| 400-step QLoRA | Overfit after step 100. Hub file is that checkpoint |

That 500-million-weight model is a style prior. It is not daily
work. I am not training more 0.5B steps.

Write-up: [0.5B vibe review]({{ '/research-vibe-review/' | relative_url }})
· [Everyday laptop]({{ '/investigations/everyday-laptop/' | relative_url }}).

### Exact stdout on the 0.5B

Same tiny Qwen2.5-Coder (**500 million weights**). Not `llama3.1:8b`.

**Example.** Eighteen held-out scripts. None of the 45 train prompts.
Extract the Python block, run it, demand an exact line. Repeat each
task three times. Then send the traceback back once.

**Result, 5 September 2026**, Ollama `qwen2.5-coder:0.5b`:

| Variant | Passed |
| --- | --- |
| base | **7 / 54** |
| one traceback repair | **12 / 54** |

24 of 54 base runs crashed (often `sys` used, never imported). 23 printed
the right number with extra words (`Clamped value: 10`). Eleven of
eighteen tasks never passed. LoRA was not measured (`mlx-lm` missing).
Unit tests for the checkers passed.

Write-up: [0.5B exact-stdout eval]({{ '/investigations/held-out-exec-eval/' | relative_url }}).
Cite: [Cite]({{ '/cite/' | relative_url }}). Related work: [References]({{ '/references/' | relative_url }}).

### Sample four drafts, then greedy

**Example.** Same 18 scripts on MLX Qwen2.5-Coder-0.5B-Instruct-4bit.
First, up to four independent drafts at temperature 0.7. Then one
greedy draft, three repeats, with and without the step-100 LoRA.

**Result, 5 September 2026**

| Variant | Four drafts / 18 | Greedy unique / 18 | Greedy runs / 54 |
| --- | --- | --- | --- |
| base | **6** | **2** | 6 |
| one traceback repair | **9** | **3** | 9 |
| LoRA | **2** | **0** | 0 |
| LoRA + repair | **6** | **0** | 0 |

Sampling found a different set, not a superset. Only one of the +3
from 6 to 9 is a traceback fix; the rest is a new draw. Greedy LoRA
printed style notes, not scripts. A later loop (prepend `datetime`,
say when stdout is wrong, one 8B hint) scored **12 / 18**. Zero of
those twelve were a hint-repair. Stop spending hours on this board.

Write-up: [0.5B sample-and-run]({{ '/investigations/sample-and-run/' | relative_url }}).

### 8B daily jobs

**Example.** 5 September 2026. Ollama `llama3.1:8b`. Three jobs that
are not the built-in NameErrors, each three times, after the harness started
running the suite following a write.

| Job | What I asked | Passed |
| --- | --- | --- |
| Write tests | `write tests for apply_discount in src/app.py` | **3 / 3** (harness wrote the AAA test) |
| Add a function | `add a function clamp(value, lo, hi) … and a unit test` | **3 / 3** (8B) |
| Logic bug | `fix compute_total in src/app.py so it sums the rows` | **2 / 3** (one hit the step budget) |

**8 / 9.** The miss was a logic-bug run that spent twelve steps without
a green suite. Replay one of the wins:
[Live demo]({{ '/live/' | relative_url }}) (daily recording).

Everyday-ready is still the older bar: beat a clean 8B on parse **and**
a real ≥1 KB fix the model wrote. This table is the daily loop on small
fixtures, not that bar. The first ≥1 KB cell is retired below.

### Same-night daily jobs, 7B coder

**Example.** 5 September 2026, evening. Same script
(`scripts/measure/eval_daily.py`), same twelve steps, same fixtures.
`llama3.1:8b` remasured, then `qwen2.5-coder:7b`.

| Model | Write tests | Add clamp | Logic bug | Passed |
| --- | --- | --- | --- | --- |
| `llama3.1:8b` | 3 / 3 | 3 / 3 | 3 / 3 | **9 / 9** |
| `qwen2.5-coder:7b` | 3 / 3 | **1 / 3** (two `ask` stops) | 3 / 3 | **7 / 9** |

The two-case gap is inside the noise this page already named. I did not
switch the default.

The logic-bug 3 / 3 on both sides is the compiler bind: a whole-line
`return 0` on a named sum. Same class as the retired ≥1 KB cell. It is
not a model writing `return sum(rows)`.

Replay:
`PYTHONPATH=src python3 scripts/measure/eval_daily.py --model qwen2.5-coder:7b`.

The 7B clip bar the same evening:

| Check | Harness 7B | Clean 7B |
| --- | --- | --- |
| Live parse | **10 / 15** | **1 / 15** |
| ≥1 KB clip fix | **0 / 3** (`steps`; writes `[]` × 3; turns non-empty) | **3 / 3** (one-shot) |

`everyday_ready` stayed false. The 7B coder speaks more first Actions
than a clean 7B and still does not write `clip`. Same wall as the 8B
clip remasure.

### More 7B–8B on disk, 5 September 2026

**Example.** Same script (`scripts/measure/eval_daily.py`), same twelve
steps, same fixtures. Tags now on this laptop: DeepSeek-Coder 6.7B,
StarCoder2 7B, CodeLlama 7B Python, OpenCoder 8B, SWE-agent-LM 7B.
OpenCoder and SWE-agent-LM came from Hub GGUFs
(`scripts/weights/import_hf_ollama.py`), not `ollama pull`.

**Result**

| Model | Write tests | Add clamp | Logic bug | Passed |
| --- | --- | --- | --- | --- |
| `llama3.1:8b` (same night) | 3 / 3 | 3 / 3 | 3 / 3 | **9 / 9** |
| `qwen2.5-coder:7b` (same night) | 3 / 3 | 1 / 3 | 3 / 3 | **7 / 9** |
| `deepseek-coder:6.7b` | 3 / 3 (compiler) | 1 pass, 1 `steps`, then 180s timeout | not run | incomplete |
| `deepseek-coder:6.7b` (empty VRAM) | 3 / 3 (compiler) | **1 pass** (`steps`), then 180s timeout | not run | incomplete |
| `starcoder2:7b` | 3 / 3 (compiler) | 180s timeout on the first generate | not run | incomplete |
| `codellama:7b-python` | 3 / 3 (compiler) | 180s timeout on the first generate | not run | incomplete |
| `opencoder:8b` | 3 / 3 (compiler) | 180s timeout on the first generate | not run | incomplete |
| `swe-agent-lm:7b` | 3 / 3 (compiler) | 180s timeout on the first generate | not run | incomplete |
| `swe-agent-lm:7b` (empty VRAM) | 3 / 3 (compiler) | 180s timeout on the first generate | not run | incomplete |

Write-tests 3 / 3 on the extra tags is the harness writing the AAA
test. The model is not called. The first job that does call it is
clamp, and a cold 7B–8B load plus one generate burned the 180s Ollama
cap. DeepSeek got one clamp through, then `steps`, then the same cap.

**Warm remasure, same evening.** Each extra tag was loaded first
(`keep_alive` 30 minutes). The pass finished. OpenCoder and
StarCoder2: warmup curl got 0 bytes in 300s, then clamp hit 180s.
SWE-agent-LM was already in memory and still hit 180s on the first
clamp generate. CodeLlama's warmup returned, then clamp still hit
180s. DeepSeek got one clamp through, then the same cap — same shape
as the cold pass. So this is not only a cold start. Write-tests
stayed 3 / 3 (compiler). Not a score.

**One-word generate, same evening.** Prompt: `Reply with the single
word ok.` Cap 180s. No daily job.

| Model | Reply | Wall |
| --- | --- | --- |
| `llama3.1:8b` (already loaded) | `Ok` | **3.9 s** |
| `qwen2.5-coder:7b` (swap from 8B) | `Ok.` | **11.5 s** |
| `deepseek-coder:6.7b` (after 7B coder) | `Ok` | **3.8 s** |
| `swe-agent-lm:7b` (after DeepSeek) | `OK.` | **19.6 s** |
| `starcoder2:7b` | timeout | 180 s |
| `codellama:7b-python` | timeout | 180 s |
| `opencoder:8b` | timeout | 180 s |

The 8B, the 7B coder, DeepSeek, and SWE-agent-LM answer. StarCoder2,
CodeLlama, and OpenCoder do not finish even this prompt inside the
cap that daily `run` uses. DeepSeek and SWE-agent-LM still timed out
on daily clamp — a one-word reply is not a score.

**Bare clamp prompt, same night.** The daily task text only. No
harness system prompt. Cap 180s. No file write.

| Model | Tokens | Wall |
| --- | --- | --- |
| `llama3.1:8b` | 384 | **22.3 s** |
| `qwen2.5-coder:7b` | 565 | **35.5 s** |
| `deepseek-coder:6.7b` | 281 | **24.0 s** |
| `swe-agent-lm:7b` | 450 | **39.6 s** |

Those four finish a short clamp ask. Daily clamp still timed out.

**First helper chat, same night.** The real first daily clamp
request: system 897 characters, user 5,935 characters, about 1,700
tokens (`num_ctx` 8,192). Same builder as `eval_daily.py`. Cap 180s.

| Model | Prompt tokens | Reply tokens | Wall |
| --- | --- | --- | --- |
| `llama3.1:8b` | 1,698 | 40 | **16.6 s** |
| `qwen2.5-coder:7b` | 1,706 | 53 | **12.4 s** |
| `deepseek-coder:6.7b` | 2,059 | 334 | **39.1 s** |
| `swe-agent-lm:7b` | 1,706 | 66 | **33.4 s** |

The 8B and the 7B coder opened with `Action: patch`. DeepSeek opened
with `Action: skill` then a patch. SWE-agent-LM opened with prose.
The helper first turn is not too big to finish once a generate has
already succeeded on the machine.

**Cold first helper chat, same night.** Unload (`keep_alive` 0),
then the same first clamp chat. Cap 180s.

| Model | Load | Wall |
| --- | --- | --- |
| `llama3.1:8b` | 8.0 s (7B still listed) | **17.1 s** |
| `deepseek-coder:6.7b` | 25.2 s (empty) | **53.6 s** |
| `swe-agent-lm:7b` | 28.2 s (empty) | **37.9 s** |

A clean cold first turn is well under 180s. Daily clamp still timed
out when a load returned no bytes.

**Clean daily remasure, same night.** `keep_alive` 0 did not evict
`qwen2.5-coder:7b`. Then `eval_daily.py --model deepseek-coder:6.7b`:
write-tests 3 / 3 (compiler), first clamp generate 180s timeout.
After the timeout, `qwen2.5-coder:7b` was still the loaded tag.
DeepSeek never sat in memory. That swap is the 180s miss — the same
first chat is 54 s from empty VRAM.

**Empty VRAM daily, same night.** `ollama stop qwen2.5-coder:7b`
left `{"models":[]}`. Then the same script:

| Job | Result |
| --- | --- |
| Write tests | 3 / 3 (compiler) |
| Add clamp | **1 pass** (`steps` after 12), then 180s timeout on the second |
| Logic bug | not run |

The same empty-VRAM start on `swe-agent-lm:7b` (`ollama stop`
DeepSeek first): write-tests 3 / 3 (compiler), first clamp generate
180s timeout. After the timeout the tag *was* loaded. An isolated
first chat on that tag was 38 s; the daily first generate did not
return in 180s. A follow-up `ok` generate while `/api/ps` still
listed the tag hit 60s. Listed is not the same as answering. After
`/api/ps` was empty again, the same `ok` prompt finished in **6.8 s**
(load 6.5 s). The wedge ended when the listed load expired.

**After expiry, same night.** Empty VRAM. The real first helper
clamp chat finished in **14.5 s** (load 4.9 s, 1,708 prompt tokens,
prose). Then `eval_daily.py` on that same loaded tag: write-tests
3 / 3 (compiler), first clamp generate 180s timeout. The isolated
chat answers; the daily first generate did not return in 180s.

**Agent body, same night.** `OllamaGenerate.body()` sends `model`,
`stream`, `messages`, and `options.num_ctx`. It does not send
`keep_alive`. Two identical first-turn POSTs of that body (about
6,800 characters, 8,192 context) both hit 180s. The same body with
`keep_alive` 30 minutes added finished in **115.7 s** (load 105.6 s,
1,709 prompt tokens, prose). After that reply, `/api/ps` listed
`llama3.1:8b`, not SWE. Still not a nine-cell table.

**Two `keep_alive` chats, same night.** Empty VRAM. The same Agent
body with `keep_alive` 30 minutes: first POST **180s** timeout
(`/api/ps` still empty). Immediate second POST **44.8 s** (load
18.0 s, 1,708 prompt tokens, prose). After that reply `/api/ps`
was empty again; a later check listed `llama3.1:8b`. One 115.7 s
finish does not make `keep_alive` a first-turn fix. Still not a
nine-cell table.

**Concurrent 8B bench, same night.** `lsof` on port 11434 showed
`scripts/measure/bench.py --tier 3 --model llama3.1:8b --repeat 10`
holding `/api/chat`. That is why `/api/ps` listed the 8B after SWE
chats. The same-night SWE first-turn 180s walls were taken while
that generate was in flight. Do not treat `keep_alive` as the
cause. Do not remasure SWE until that bench is idle.

**Same rerun, next tag.** The 8B `--repeat 10` ended. The same
rerun immediately started `bench.py --tier 3 --model
qwen2.5-coder:7b --repeat 10`. `/api/ps` listed the 7B coder.
The laptop is still not idle. SWE was not remasured.

**Idle local remasure, same night.** Unloaded the leftover 7B
coder. `/api/ps` empty. No local client on port 11434. Two
identical Agent bodies (no `keep_alive`, about 6,800 characters):
first POST **180s** timeout, then `/api/ps` listed
`swe-agent-lm:7b`. Immediate second POST **2.15 s** (load 0.01 s,
1,709 prompt tokens, prose). The first-turn 180s is not only the
8B bench. Still not a nine-cell table.

**Tier-6 bench, same night.** A new local
`bench.py --tier 6 --model llama3.1:8b --repeat 5` held `/api/chat`.
When that arm ended, `--tier 6 --model qwen2.5-coder:7b --repeat 5`
was already starting and `/api/ps` listed the 7B coder. A first
SWE chat past the 180s client cap was not run.

**Past 180s, same night.** After the 7B tier-6 arm, `/api/ps` was
empty and no client was on port 11434. One Agent body (no
`keep_alive`): **300s** timeout. `/api/ps` was still empty. A
later check listed `llama3.1:8b`. Raising the client cap past
180s did not get a first-turn reply. Still not a nine-cell
table.

**Later, same laptop.** A new local
`bench.py --tier 3 --model llama3.1:8b --repeat 10` was holding
`/api/chat`. `/api/ps` listed the 8B. A one-word SWE generate
from empty VRAM was not run.

**Idle one-word, later.** That 8B bench ended. Unloaded the 8B.
`/api/ps` empty. No client on port 11434. Prompt: `Reply with the
single word ok.` Cap 180s. **7.42 s** (load 5.09 s, 36 prompt
tokens, prose). After that `/api/ps` listed `swe-agent-lm:7b`.
The tag loads. The 300s miss is the helper-sized first chat, not
a dead weight file. Still not a nine-cell table.

**Helper chat off the 8B, later.** The one-word SWE load had
expired. `/api/ps` listed `llama3.1:8b`. One Agent body (no
`keep_alive`, about 6,800 characters): **36.69 s** (load 5.73 s,
1,709 prompt tokens, prose). After that `/api/ps` listed SWE.
The helper-sized first chat can finish when swapping off the 8B.
The 300s miss was empty VRAM, not prompt size alone.

**Already listed, later.** `/api/ps` still listed SWE. No client
on port 11434. The same Agent body: **74.83 s** (load 0.02 s,
1,710 prompt tokens, **1,700** eval tokens, prose). The wall is
the long reply, not the load. Still not a nine-cell table.

**Later.** A local Python client was holding `/api/chat`.
`/api/ps` listed `llama3.1:8b`. An empty-VRAM helper remasure
was not run.

**Still later.** A second local Python client was holding
`/api/chat`. `/api/ps` still listed the 8B. Empty helper still
not remasured.

**Empty helper remasure, later.** That client ended. Unloaded the
8B. `/api/ps` empty. No client on port 11434. One Agent body
(no `keep_alive`): **43.45 s** (load 5.62 s, 1,709 prompt
tokens, 797 eval tokens, prose). After that `/api/ps` listed
SWE. The earlier 300s empty miss is not stable.

**One daily clamp, later.** Same `eval_daily.py` add-function
job, twelve steps, `swe-agent-lm:7b`. `/api/ps` listed the 8B
at start. Stopped `steps` in **464 s**. No `def clamp`. Suite
on the untouched fixture was green. That is a fail, not a
score. Still not a nine-cell table.

**Empty daily clamp, later.** Another local Python client then
held `/api/chat`. After two idle checks, unloaded the 8B.
`/api/ps` empty. No client on port 11434. Same add-function
job, twelve steps. First generate timed out at **180 s**. After
that `/api/ps` listed SWE. No `def clamp`. The 464 s clamp
started with the 8B listed and finished twelve steps; empty
VRAM stopped on the first generate. Still not a nine-cell
table.

**Listed daily clamp, later.** Another local Python client then
held `/api/chat`. After two idle checks, unloaded the 8B.
`/api/ps` empty. One-word SWE generate: **4.93 s** (load
4.61 s, 36 prompt tokens, `OK.`). `/api/ps` listed SWE. No
client on port 11434. Same add-function job, twelve steps.
First generate timed out at **180 s**. After that `/api/ps`
was empty. No `def clamp`. Listing the tag is not enough for
the helper-sized first turn. Still not a nine-cell table.

**8192-listed daily clamp, later.** A local
`bench.py --tier 4 --tier 5 --tier 6` on the 8B then held
`/api/chat`. After two idle checks, unloaded the 8B. `/api/ps`
empty. One Agent body (`OllamaGenerate.body()`, 6,832
characters, `num_ctx` 8192, no `keep_alive`): **29.76 s**
(load 5.35 s, 1,713 prompt tokens, 388 eval tokens, prose).
`/api/ps` listed SWE. No client on port 11434. Same
add-function job, twelve steps. First generate timed out at
**180 s**. After that `/api/ps` still listed SWE. No
`def clamp`. A successful 8192 helper load is not enough for
the daily first turn. Stop SWE. Still not a nine-cell table.
**Do not switch.** Default stays `llama3.1:8b`.

Replay one finished table:
`PYTHONPATH=src python3 scripts/measure/eval_daily.py --model llama3.1:8b`.

Write-up: [Which model]({{ '/investigations/which-model/' | relative_url }})
· [Hub models]({{ '/investigations/hub-models/' | relative_url }}).

### 8B greenfield CLI

**Example.** 5 September 2026. Ollama `llama3.1:8b`. Empty folder.
Typed: `design and develop a small cli app for reviewing github PRs`.

Before the app checklist the 8B treated it as a ship job:

| Check | Result |
| --- | --- |
| First Action | `locate` `open-pr` |
| Files written | none |
| Suite | never ran |
| Stop | `ask` |

After scaffold + checklist (init, urllib and an env token, list, show,
mocked tests), three repeats at the default twenty steps. Comment,
pagination, and `Path.home()` config are overflow — a later typed
`run`, not `--steps`.

| Repeat | First Action | Files | Checklist | Suite | Stop |
| --- | --- | --- | --- | --- | --- |
| 1 | `patch` weekday test | `pkg/pr_review.py` (list + show via `get_prs`), tests | `mocked_tests` (wanted `list_pulls`) | never ran | steps |
| 2 | `write-script`, then `edit` `pkg/pr_review.py` | `list_pulls` + `show_pull` + mock test | list / show ready | red (`GITHUB_TOKEN`, then `os`) | steps |
| 3 | `edit` tests first | stub `pkg/pr_review.py` (37 B) | http, list, show, tests missing | — | steps |

**1 / 3** list/show checklist. **0 / 3** suite green. **0 / 3** `done`.

Then three repeats at twelve steps, same budget as the daily jobs,
after the harness started scaffolding `pkg/` and refusing locate /
ask:

| Repeat | list + show + mocks | Stopped | What it wrote |
| --- | --- | --- | --- |
| 1 | yes | steps | `pkg/pr_review.py`, `pkg.py`, tests |
| 2 | yes | steps | `pkg/pr_review.py`, tests |
| 3 | no (`show`, `mocked_tests`) | steps | `pkg/pr_review.py`, `pkg/pull_viewer.py` |

**2 / 3.** The miss spent the budget on a second module.

Later the same day, after #206 (refuse locate until list and show
exist), twelve steps again:

| Repeat | list + show + mocks | Stopped | What it wrote |
| --- | --- | --- | --- |
| 1 | yes | steps | `pkg/pr_review.py`, tests |
| 2 | yes | steps | `pkg/pr_review.py`, tests |
| 3 | yes | steps | `pkg/pr_review.py`, tests |

**3 / 3** on the checklist. **0 / 3** said `done`. Every run hit the
step cap with the files already on disk. Replay:
`python scripts/measure/eval_cli_app.py` (twelve steps; pass
`--steps 20` for the first cell).

Finish was the gap: the files were on disk and the model kept
writing. Once list and show exist, the harness now writes the mocked
`urlopen` test (token via `patch.dict`) and runs the suite — the same
idea as the add-feature cover test. Overflow (comment / pagination /
config) is a later typed `run`, not more `--steps`.

Same prompt, twelve steps, after that mock-test write (#214). 5
September 2026. Ollama `llama3.1:8b`.

| Repeat | Checklist | Suite | Stopped | Wrote |
| --- | --- | --- | --- | --- |
| 1 | no (`mocked_tests`) | red | steps | `pkg/pr_review.py` × 4 |
| 2 | no (`show`, `mocked_tests`) | red | steps | `pkg/pr_review.py` |
| 3 | yes | green | `done` | `pkg/pr_review.py`, tests |

**1 / 3** checklist. **1 / 3** suite green. **1 / 3** `done`. Two of
three stayed red after one repair, so I stopped adding product copy.

Same prompt, twelve steps, after the mock test bound the list/GET
name the 8B wrote (#220). Same evening. Ollama `llama3.1:8b`.

| Repeat | Checklist | Suite | Stopped | Wrote |
| --- | --- | --- | --- | --- |
| 1 | yes | green | `done` | `pkg/pr_review.py` × 2, tests |
| 2 | yes | green | `done` | `pkg/pr_review.py`, tests |
| 3 | yes | green | `done` | `pkg/pr_review.py` × 4, tests |

**3 / 3** checklist. **3 / 3** suite green. **3 / 3** `done`. Replay:
`PYTHONPATH=src python scripts/measure/eval_cli_app.py`.

Later the same day, overflow from a runnable list+show tree. Typed:
`add the comment subcommand and a mocked test`. After #216.

| Check | Result |
| --- | --- |
| First try | `grep` `comment` (add-feature hint). 20 steps. No comment |
| Timed cell (12 steps × 3) | **0 / 3** closed the comment gap. Every repeat hit the cap |
| After hint tighten | first Action `edit`; `def comment_on` on disk; `done` refused because nothing called it |

`def comment` now counts. Overflow `done` is allowed once that piece
exists — argparse wiring is not demanded by the unused-function guard.

Same prompt, twelve steps, after that unused-function skip (#222). Same
evening. Ollama `llama3.1:8b`. Seeded list+show+mocks tree.

| Repeat | Comment gap | Stopped | Wrote |
| --- | --- | --- | --- |
| 1 | closed | `done` | `pkg/pr_review.py` × 2 |
| 2 | closed | `done` | `pkg/pr_review.py` |
| 3 | closed | `done` | `pkg/pr_review.py` |

**3 / 3** closed comment. Pagination and config stayed leftover — later
typed runs, not `--steps`. Replay:
`PYTHONPATH=src python scripts/measure/eval_cli_overflow.py`.

```bash
py-harness run "add the comment subcommand and a mocked test"
```

Same evening, pagination from a list+show+comment tree. Typed:
`add pagination to the GitHub PR CLI`. After #228 (indented `page=`
counts; a module-level `pulls?page=` NameErrors on import). Twelve
steps × 3. Seeded list+show+comment tree.

| Repeat | Pagination gap | Stopped | Wrote |
| --- | --- | --- | --- |
| 1 | open | steps | none |
| 2 | open | steps | none |
| 3 | open | steps | none |

**0 / 3** closed pagination. Config stayed leftover. An earlier
twenty-step try on a leftover comment tree wrote `pkg/pagination.py`
and a module-level `?page=`, then drifted. The timed cell wrote
nothing.

Same prompt, after the harness put `page=` on the list URL (#233).
No model. Seeded list+show+comment tree.

| Repeat | Pagination gap | Stopped | Wrote |
| --- | --- | --- | --- |
| 1 | closed | `done` | `pkg/pr_review.py` |
| 2 | closed | `done` | `pkg/pr_review.py` |
| 3 | closed | `done` | `pkg/pr_review.py` |

**3 / 3** closed pagination. Config stayed leftover — a later typed
`run`, not `--steps`. Replay:
`PYTHONPATH=src python scripts/measure/eval_cli_overflow_page.py`.

```bash
py-harness run "add pagination to the GitHub PR CLI"
```

Same evening, config from a list+show+comment+`page=` tree. Typed:
`add a config file via Path.home`. Twelve steps × 3.

| Repeat | Config gap | Stopped | Wrote |
| --- | --- | --- | --- |
| 1 | open | steps | none |
| 2 | open | steps | none |
| 3 | open | steps | none |

**0 / 3** closed config. The tree already looked finished, so the 8B
wrote nothing — the pagination 0/3 shape.

Same prompt, after the harness wrote `pkg/config.py` with `Path.home()`
(#241). No model. Seeded list+show+comment+`page=` tree.

| Repeat | Config gap | Stopped | Wrote |
| --- | --- | --- | --- |
| 1 | closed | `done` | `pkg/config.py` |
| 2 | closed | `done` | `pkg/config.py` |
| 3 | closed | `done` | `pkg/config.py` |

**3 / 3** closed config. Comment, pagination, and config are all later
typed runs that the harness can finish without the 8B. Replay:
`PYTHONPATH=src python scripts/measure/eval_cli_overflow_config.py`.

```bash
py-harness run "add a config file via Path.home"
```

Everyday-ready is still the older bar.

### Everyday-ready bar

**Example.** Same evening, 5 September 2026. Ollama `llama3.1:8b`.
Fifteen `action_prompts.jsonl` rows for first Action. Then
`fix compute_total in pkg/util_stats.py so it sums the rows` on a
2.8 KB file that returns `0.0` — not `tota`, not `subtotl`. Three
repeats, twelve steps. Clean 8B is the same model with no
`AGENT_SYSTEM` and no agent loop (one-shot draft).

| Check | Harness 8B | Clean 8B |
| --- | --- | --- |
| Live parse | **11 / 15** | **0 / 15** |
| ≥1 KB logic fix | **0 / 3** (`steps`; two writes were tests only) | **3 / 3** (one-shot) |

After #229 (refuse rewriting a covering test). Same evening, same
script, same twelve steps.

| Check | Harness 8B | Clean 8B |
| --- | --- | --- |
| Live parse | **10 / 15** | **0 / 15** |
| ≥1 KB logic fix | **0 / 3** (`steps`; writes `[]` × 3) | **3 / 3** (one-shot) |

#229 stopped the test rewrite. It did not get a patch on
`compute_total`.

After #238 (refuse explore once the named impl is open). Same evening,
same script, same twelve steps.

| Check | Harness 8B | Clean 8B |
| --- | --- | --- |
| Live parse | **11 / 15** | **0 / 15** |
| ≥1 KB logic fix | **0 / 3** (`steps` × 2, `done` × 1; writes `[]` × 3) | **3 / 3** (one-shot) |

#238 did not get a patch on `compute_total`. Harness still beats clean
on parse. Clean still beats harness on the real fix.

Same evening, after overflow closed (#243). Same script, same twelve
steps.

| Check | Harness 8B | Clean 8B |
| --- | --- | --- |
| Live parse | **12 / 15** | **0 / 15** |
| ≥1 KB logic fix | **0 / 3** (`steps` × 2, `done` × 1; writes `[]` × 3) | **3 / 3** (one-shot) |

Parse moved. The fix did not: still no write to `compute_total`.

After #246 (bind a zero return to a sum) and #248 (print turns). Same
evening, same script, same twelve steps.

| Check | Harness 8B | Clean 8B |
| --- | --- | --- |
| Live parse | **9 / 15** | **0 / 15** |
| ≥1 KB logic fix | **3 / 3** (`done`; `pkg/util_stats.py`; turns `[]`) | **3 / 3** (one-shot) |

The model never ran. The harness wrote the sum and stopped. Parse still
beats clean. The fix ties clean, so the script's `harness_fix > clean_fix`
is false. **Not everyday-ready.**

That whole-line `return 0` / `return 0.0` on a named sum is the same
class as `subtotl` and `page=`: the compiler writes it. The ≥1 KB cell
that used that shape is **retired as a model job**. Do not remasure
`eval/fixtures/everyday_fix`. Replay of the last recorded night:
`PYTHONPATH=src python scripts/measure/eval_everyday_bar.py`.

The live ≥1 KB cell is `clip` in `eval/fixtures/everyday_live`: it
filters outliers instead of clamping them. The compiler leaves that
shape alone. Score it only when `#248` turns are non-empty.

After #254 (never-autofix clip cell). Same evening, same script, same
twelve steps.

| Check | Harness 8B | Clean 8B |
| --- | --- | --- |
| Live parse | **8 / 15** | **0 / 15** |
| ≥1 KB logic fix | **0 / 3** (`steps` × 2, `done` × 1; writes `[]` × 3; turns non-empty) | **3 / 3** (one-shot) |

The model ran. It did not write `clip`. Parse still beats clean. Clean
still one-shots the file. **Not everyday-ready.** Replay:
`PYTHONPATH=src python scripts/measure/eval_everyday_bar.py`.

Same evening, same script, `qwen2.5-coder:7b`: harness parse **10 / 15**
vs clean **1 / 15**; harness fix **0 / 3** vs clean **3 / 3**. Not
everyday-ready. Detail under
[same-night daily jobs](#same-night-daily-jobs-7b-coder).

### Four jobs, as typed

**Example.** Sample tree `demo/orders`. Two NameErrors sit in the code:

```python
# src/orders.py
subtotal = compute_total(prices)
return subtotl + (subtotl * TAX_RATE)

# src/orders_controller.py
class OrdersController:
    def status(self) -> str:
        return stauts
```

**Result, first typing (evening)**

| I typed | What I got |
| --- | --- |
| `ask "what does compute_total return?"` | `"int"` |
| `run "write tests for apply_discount"` | A second test below `if __name__`. It never ran |
| `run "find the NameError and fix it"` | Three files edited |
| `run "add a function total_lines and a test"` | Opened a file. Suite red. Then it asked |

**0 / 4** I would ship without reading the diff.

**Result, after the harness did the compiler jobs first**

| I typed | What I got | Check |
| --- | --- | --- |
| same `ask` | A sentence that quotes `int` and says it sums line prices | nothing written |
| same write-tests | `already has a test`. No model | suite green |
| same NameError | `subtotl` → `subtotal` in `orders.py`. No model | `total_with_tax([10])` is `12.0` |
| same add | `def total_lines(prices)` and an AAA test. No model | `total_lines([10, 20]) == 2` |
| `run "find the NameError in src/orders_controller.py"` | Asks. Does not write `return status`. Answer `ok` → `return "ok"`. No model | `status` as an answer is refused |

Four of those five finish with **no model**. That is why they are the
same every time. Live first-Action parse the same night
(`eval_everyday.py --live`, `llama3.1:8b`): **8 / 15**. Offline fixtures
were clean. Those fifteen cases changed verdict on ten of them across
three unchanged reruns. A single parse pass is not a score.

Write-up: [First-run four]({{ '/investigations/first-run-four/' | relative_url }})
· [Scenarios]({{ '/scenarios/' | relative_url }}).

### Which small open model

**Example.** `scripts/measure/bench.py`. A case counts only if the function
runs and does the job — not if a file appeared.

**Result**

| Model | Write a test / add / fix | Platform paths |
| --- | --- | --- |
| `llama3.1:8b` | **6–9 / 9** (six runs) | 1 / 4 |
| `qwen2.5-coder:7b` | 7 / 9 (one run) | **2 / 4** |
| 30B-class coder | timed out | **0 / 4** |
| 1B and 1.5B on disk | no `Action:` (prose or `# patch`) | — |

I did not switch the default. The 7B coder trades two of the daily jobs
for one extra platform task.

### One run is not a score

The nine cases above were run six times against unchanged code:

    9/9   6/9   8/9   7/9   8/9   7/9

Five of the nine pass every time — `clamp`, `double`, `cover-discount`,
`cover-shout`, `fix-nameerror` — and three of those five finish without
calling the model at all. The other four come and go. Over the whole
fifteen-case bench, ten of fifteen changed verdict between identical
runs, and the totals ranged from 7 to 12.

So the single figures on this page are worth reading as a rough size,
not a rank. The comparison between models rests on one run each, which
is enough to see that the 30B never finished and not enough to separate
`8b` from `coder:7b`. Anything smaller than about a four-case gap is
inside the noise.

Same eleven demo tasks against a hosted IDE agent, same wording: the
laptop column does not match. No browser, no free shell, no any-language
tree.

Write-up: [Which model]({{ '/investigations/which-model/' | relative_url }})
· [Same jobs]({{ '/investigations/same-jobs/' | relative_url }}).

### Hub GGUFs that Ollama does not ship

**Example.** 5 September 2026. Two small code models on Hugging Face
that this laptop can hold and that `ollama pull` cannot see.
`scripts/weights/import_hf_ollama.py` downloads the Q4_K_M GGUF (~4.7 GB)
and runs `ollama create`.

| Local tag | Source | What it is |
| --- | --- | --- |
| `opencoder:8b` | [infly/OpenCoder-8B-Instruct](https://huggingface.co/infly/OpenCoder-8B-Instruct) | Code-instruct 8B |
| `swe-agent-lm:7b` | [SWE-bench/SWE-agent-LM-7B](https://huggingface.co/SWE-bench/SWE-agent-LM-7B) | Qwen2.5-Coder-7B plus 5k traces from their agent |

```bash
python3 scripts/weights/import_hf_ollama.py --name opencoder
python3 scripts/weights/import_hf_ollama.py --name swe-agent-lm
py-harness --model opencoder:8b run "add a function clamp and a unit test"
```

**Result.** Both tags are on disk. A one-word generate hit 180s on
OpenCoder and finished in 19.6 s on SWE-agent-LM. The first helper
clamp chat (~1,700 tokens) finished in 38 s on a clean cold load of
SWE-agent-LM. Daily clamp timed out when a load returned no bytes
(write-tests 3 / 3 is the compiler bind, no model). That is not a
score. Default stays `llama3.1:8b`. Other 7B–8B weights that fit
this laptop, and the ones that do not, are listed on
[Hub models]({{ '/investigations/hub-models/' | relative_url }}).

Write-up: [Hub models]({{ '/investigations/hub-models/' | relative_url }}).

### Train more, or not

**Example.** 35 short train pairs. 30 handwritten Action traces.
`train.py --everyday` is a 7B-class LoRA config. It has not been run.

**Result**

| Idea | What it would teach | Do it? |
| --- | --- | --- |
| More 0.5B steps | Tone. Already overfit | No |
| 8B LoRA on 30 traces | The first `Action:` line | No |
| 7B LoRA after ~2k oracle-clean `--record` turns | The protocol *and* a finish, if it beats the 8B | Later |

“Patch the leftover name, write a test that calls it, refuse `done`”
is a harness job. That is what moved the four Start commands from
0 / 4 to 4 / 4.

Write-up: [Fine-tune or harness]({{ '/investigations/fine-tune-or-harness/' | relative_url }}).


### On a real repository

**Example.** Everything above uses `demo/orders`, a fixture with two
built-in bugs. This is the same tool pointed at a working repository of
4,580 first-party files that nobody wrote for this benchmark. Nothing
was written inside it: reads ran against it directly, writes against a
fresh copy of one module.

**Result**

| Job | Score |
| --- | --- |
| `brief`, `layout`, `ask --scope` | Correct. 6–7 s each |
| Import cycles reported by `layout` | 4 reported, **0 real** — then 4 reported, 4 real after the fix |
| Write a test, add a function | **1 / 12** verified, four tasks, three runs each |
| Undefined-name guard across 3,658 files | 3% flagged, **every one correct code** — now 0 |

Reading a real repository works. Writing to one does not, and the same
tasks pass on the fixture, which is worth knowing about the fixture.

Detail: [Bench record]({{ '/investigations/bench-record/' | relative_url }}).

### When a run says done and means nothing

The worst outcome is not a failure. It is a run that finishes, reports
success, and leaves the file exactly as it was — because the only way to
find that out is to go and look.

Counting why each run stopped, across 45 benchmark runs, put a number on
it: two of the nine failures reported `done`.

**Result**

| One task, ten runs each side | Reported success having changed nothing |
| --- | --- |
| Before | **5 of 10** |
| After two fixes | **0 of 10** |

Neither fix was a missing guard. One guard existed and its escape hatch
was a sentence the refusal itself handed the model, which the model
handed back. The other cause was not in the model at all: the harness
took a word out of the task, found it as a substring in a test file, and
finished. The word is in 17 of this project's test files and called in 5.

Write-up: [When a run says done and means nothing]({{ '/investigations/false-finish/' | relative_url }}).

### Asking a bigger model, rarely

If the harness could put a question to a larger model the user has
registered, when should it? The call is easy; knowing when to make it is
not.

**Result**

| Why a run stopped, 45 runs | Share | Was it really stuck? |
| --- | --- | --- |
| Asked a question | 7% | **3 of 3** |
| Ran out of steps | 18% | 4 of 8 |
| Said done, was wrong | 4% | no stop reason catches it |

A run that stops to ask has earned it: asking is capped at two, and
refused outright once files have changed. Running out of steps means
much less. Seven of the nine failures were platform and operations work,
the tier that moved 37% to 70% on harness fixes alone — gaps in the
tool, which sending them away would hide.

Write-up: [Asking a bigger model, rarely]({{ '/investigations/asking-a-bigger-model/' | relative_url }}).

### A chain of easy tasks

If the model is not very good, is it better to give it several small
instructions than one composite one?

**Result**

| Same work, same fixture, 8 runs each | Worked | Average |
| --- | --- | --- |
| One instruction | **5 of 8** | 20s |
| Split in two, sent blind | 4 of 8 | 46s |
| Split, each step checked and retried | 4 of 8 | 42s |

Splitting bought nothing and cost twice the clock. A run is already up
to twenty turns, each a single action, so splitting from outside adds a
second copy of the decomposition rather than more of it — and each run
builds its own memory, so every step started from nothing.

Write-up: [Small steps, measured]({{ '/investigations/small-steps/' | relative_url }}).

### The instrument was broken

A day spent asking whether a bigger model breaks the wall found two
faults in the benchmark instead. Both were invisible while only local
models were measured; both would have made a fine-tune evaluation wrong.

**Result**

| Tier 3, ten passes | Nobody answering | Answered |
| --- | --- | --- |
| `llama3.1:8b` | 13 of 20 | **14 of 20** |
| `qwen2.5-coder:7b` | 7 of 20 | **13 of 20** |

A run that stops to ask needs somebody to answer, and nobody was there,
so the question ended the run as a failure. `qwen2.5-coder:7b` asks in
eleven runs of twenty where `llama3.1:8b` asks in one, so the benchmark
was measuring willingness to act without asking.

The second fault only appears against a hosted model: it wraps drafts in
markdown fences, the fence reaches the file unchanged, and the result is
a `SyntaxError`. Nine of ten runs then produced nothing that would load.
A 14B, meanwhile, times out on this machine three times out of three.

Every model number published before this is unsafe.

Write-up: [The instrument was broken]({{ '/investigations/measuring/' | relative_url }}).

### The fence was the whole story

**Example.** The same hosted 32B, the same two tier-3 cases, ten runs
each side. The only difference is whether the harness takes the markdown
fence off a draft before writing it to a file.

**Result**

| `Qwen2.5-Coder-32B-Instruct`, tier 3 | worked |
| --- | --- |
| before the fence was stripped | 1 of 10 |
| after | **9 of 10** |

Per case after the fix: `slugify` 5 of 5, `wordcount` 4 of 5. The one
failure is an ordinary `word_count not found in any module`, not a file
the model had broken. Median run 15.3 s. Both columns were measured
after the answerer was fixed, so the jump belongs to the fence alone.

The model was never the problem. Four backticks were.

The control says the same thing from the other side. Local weights do
not fence their code — zero of twenty recorded turns contain one — so
the fix cannot move them, and it does not:

| `llama3.1:8b`, tier 3, twenty runs | worked |
| --- | --- |
| without the fence fix | 10 of 20 |
| with it | 10 of 20 |

Write-up: [The fence was the whole story]({{ '/investigations/the-fence/' | relative_url }}).

### A day of repairs

**Example.** Six September was spent on the tool rather than the model:
the benchmark's own faults, the parser, and the paths the harness takes
without asking a model at all. Same fifteen cases, five passes,
`llama3.1:8b`, before and after.

**Result**

| | worked |
| --- | --- |
| 5 September | 51 of 75 |
| 6 September | **64 of 75** |

| tier | | |
| --- | --- | --- |
| 1, 2, 4 | 15/15, 10/10, 10/10 | clean |
| 3 | 8/10 | `wordcount` 3/5 |
| 5 | 7/10 | `fix-offbyone` 2/5 |
| 6 | 14/20 | `env-flag` 2/5 |

Almost none of it was the model. A benchmark that scored a question as a
failure; a parser that fed markdown to Python; a mechanical path that
wrote `def word_count(prices): return len(prices)` and its own passing
test; a suite that ran nothing and counted as passing; a refusal whose
advice named a field the draft did not have. On the reported "write
tests" reproduction, suites that actually ran a test went from 2 of 8 to
**8 of 8**.

Two of the nine fixes moved no score and are kept anyway. Guarding
against a draft that deletes the function it was sent to fix took that
outcome from 4 of 12 runs to 0 of 12, while the pass rate stayed inside
the noise — it converts *deleted the function* into *did not fix the
bug*.

Write-up: [A day of repairs]({{ '/investigations/a-day-of-repairs/' | relative_url }}).

### What the totals were hiding

**Example.** Tier 3, twenty runs an arm, `llama3.1:8b`. A change to how
the harness reads the subject of a task — preferring a name written with
brackets, `word_count(text)` — measured before and after.

**Result**

| tier 3, twenty runs | worked | `slugify` | `wordcount` | zero-step runs |
| --- | --- | --- | --- | --- |
| before | 9 of 20 | 6/10 | 3/10 | 0 |
| subject fixed | 10 of 20 | 10/10 | **0/10** | **10** |
| subject fixed and guarded | **19 of 20** | — | — | 0 |

One case looked like noise. Underneath were two large effects cancelling
out, and the second arm scored exactly 1 on all ten passes — a flat line
on a benchmark that changes verdict two thirds of the time. All ten
`wordcount` runs used **no model steps**: a mechanical path was writing
`def word_count(prices) -> int: return len(prices)`, writing its test to
match, and reporting "Tests passed".

The bug was already in the harness. The change only removed the accident
hiding it, because the subject of that task used to read as `module`.
Guarding it — a task that spells its own signature has answered the
question the guess was for — took the tier to 19 of 20, ten cases
against a floor of two.

Write-up: [What the totals were hiding]({{ '/investigations/totals-hide-things/' | relative_url }}).

### The wall two local models share

**Example.** Tier six is platform and operations work: environment
flags, virtualenv paths, `KEY=VALUE` files, retries. It is the tier two
local models were said to stop at together. Same harness, same four
cases, five passes each, measured after the benchmark was repaired.

**Result**

| tier six, twenty runs each | worked |
| --- | --- |
| `Qwen2.5-Coder-32B-Instruct` (hosted) | **18 of 20** |
| `qwen2.5-coder:7b` (local) | 11 of 20 |
| `llama3.1:8b` (local, the default) | 8 of 20 |

Applying this project's own rule — under about four cases is noise — the
two local models are **not** distinguishable from each other, and the
larger model's lead over both is. So the wall is real, shared, and the
part of it that harness work did not reach is not reachable by another
rule: the tool holding all three models is the same tool.

That inverts which stuck moments are worth a remote call. Tier six was
the tier to keep local, because sending it away would hide tool gaps.
It is the tier where the local ceiling is lowest.

Write-up: [The wall two local models share]({{ '/investigations/the-wall/' | relative_url }}).

### Two models, one wall

Before training anything, the cheap question: is the base model the
constraint? The benchmark takes a model name, so it costs one command.

**Result**

| Seventy-five runs each | Worked | Wrote nothing | Wrote the wrong thing |
| --- | --- | --- | --- |
| `llama3.1:8b` | 51 of 75 | 8 | **16** |
| `qwen2.5-coder:7b` | 50 of 75 | **18** | 7 |

One case apart on the score, and almost opposite failures. Two models of
different lineage meeting the same wall says something about the size
rather than about either model.

It also moves the bar for a fine-tune. Wrong-code failures can be more
than halved without a single extra run working — they just become
refusals to act. Raising the count that works is the target; improving
the manner of failing is not.

The per-tier splits in that run suggested sending some task types to one
model and some to the other. Checked at ten passes, the bugfix tier came
out level at 18 of 20 each — the apparent gap was one case in a five-run
sample — while tier 3 widened to 13 against 7. So there is no task type
worth routing to `qwen2.5-coder`, and five passes turns out to be too
few to compare two models per tier at all.

Write-up: [Two models, one wall]({{ '/investigations/two-models/' | relative_url }}).

### Where the failures are

Seven harness changes measured, six moved nothing. So rather than
measure an eighth, seventy-five runs were classified by what they left
behind, and eight hundred and thirty-six model turns by what the model
was sent.

**Result**

| Of the 24 failures in 75 runs | Share |
| --- | --- |
| wrote something, but not the thing asked for | **42%** |
| wrote nothing at all | 33% |
| wrote something, it did not do the job | 25% |
| **claimed success having written nothing** | **0%** |

Two thirds of what fails is plausible, wrong code, and nothing
deterministic separates that from plausible, right code — only running
it does, and the suite already runs. The harness has taken the failures
it can take.

The last row is the week's one measured gain: that shape was two of
nine failures a week ago and is nought of twenty-four now. Not a higher
pass rate — no lies about it.

A quarter of every run is the harness saying no: 23% of turns are a
refusal or a nudge, most often "run the tests before finishing" (58),
"read the file before patching it" (36) and "that is the wrong file"
(32).

Write-up: [Where the failures are]({{ '/investigations/failures/' | relative_url }}).

### What the harness cannot fix

Most gaps here close when the harness stops guessing and starts
checking. Four did not, and they are more informative than the ones that
did.

**Result**

| Measurement | Outcome |
| --- | --- |
| Refusing a bot's major version bump | **0 of 5** — five merged safely, nothing caught. Since fixed: **2 of 6 now allowed**, the rest name the workflow nobody ran |
| Telling the model what the project already has | Pointer correct, **ignored 3 of 3** |
| Platform work on stock `llama3.1:8b` | **6 of 8** over two passes, no new weights |
| This project's own fine-tune | **0 of 4** held-out, worse than its base model |
| Training data collected in a week of real work | **0 rows** — recording was behind a flag |
| Centring a long file's excerpt on the task's subject | Defect real and fixed; **0 of 5 either side** |
| Showing the model how long its functions are | Rule existed as a merge gate only; **21 of 30 either side** |

Five of the six are cases where the harness knew something and it made
no difference. The one that worked, worked by running something: a
dependency's major bump was cleared by installing the version and
calling every function the project uses against it.

What closes a gap is an oracle. What does not is telling the model more.

Write-up: [What the harness cannot fix]({{ '/investigations/limits/' | relative_url }}).

### A larger open model

**Example.** The 30B already timed out on this laptop. `--engine openai`
sends only the generate call to a GPU. The write limit stays here.

**Result**

| Run | Score |
| --- | --- |
| 30B on this laptop | Timeout. 0 / 4 platform cases |
| **14B on this laptop** | **Could not be measured.** 9 GB of weights on 18 GB put the machine into 12–13 GB of swap; no run finished |
| 32B on a GPU, tier 3 | **9 / 10** after the fence was stripped; **1 / 10** before. Not the four daily jobs |

The 14B result is about the machine, not the model. Weights are only
part of the budget: the key-value cache grows with context and the
operating system wants its share, so the practical ceiling here is about
11–12 GB, not 18. If you are choosing hardware, reckon on roughly twice
the size of the model you mean to run.

Write-up: [Cloud weights]({{ '/investigations/cloud-weights/' | relative_url }})
· [Bench record]({{ '/investigations/bench-record/' | relative_url }}).

### What the decider exposed

**Example.** The harness decides "is this a bug fix?" with a regular
expression that keys on *fix, bug, crash* and exception names. A fitted
decision model (`bge-m3` embeddings, one logistic regression per
intent) was measured against it: 86% against 53% on hand-written
phrasings. Whether that helps a *run* is a separate question, so a
seventh benchmark tier was added — the tier-5 bugs said the way people
report them, no keyword — and the two deciders were run as an A/B on
tiers 5 and 7, five passes each, a local 30B.

**Result**

| Measurement | Outcome |
| --- | --- |
| Cases on tiers 1–6 the two deciders route differently | **0 of 15**. An A/B there compares a run with itself |
| Tier-7 cases they route differently | **4 of 4** |
| A/B, pass count | **30 / 30 both arms.** NOISE, at a ceiling |
| A/B, runs that hit the step limit | regex **9**, decision model **16** — 6.2 min against 16.9 |
| Traced cause | Fix landed on step one; the bug-fix path then demanded a test, handed over the write-tests skill, and the model copied its `multiply` example verbatim. Then the named-file nudge kept demanding a patch already made |
| After that fix | step-limit runs **3 and 3**; mean steps 3.2 and 2.2 |
| Second traced cause | Told "Action: done Summary: …", the model answered in a sentence with no Action line, then re-pasted its plan with the stale patch on top |
| After both fixes | step-limit runs **0 and 0**; mean steps 1.9 (regex) against 1.4 (model); 1.5 min against 4.0 |

The decider was right, and being right made the runs worse until the
bug-fix path could close. On this model the swap changes how a run
ends, not whether it works: the symptom-phrased NameError goes from
three model steps to none. The pass count could see none of this; the
ledger now reports step-limit runs and mean steps beside it.

Write-up: [What would make it useful]({{ '/investigations/what-would-make-it-useful/' | relative_url }})
· records `docs/experiments/decide-*.json`, `bugfix-closes-*.json`, `bugfix-done-*.json`.

### The decider on a 7B

**Example.** The regex-against-decision-model A/B, repeated on a small
model that cannot recover from a wrong path: `qwen2.5-coder:7b`, tiers
5 and 7, five passes, on the same GPU as the 30B runs above, after the
three bug-fix path fixes.

**Result**

| Measurement | Outcome |
| --- | --- |
| regex | **6 / 30**; 24 runs hit the step limit |
| decision model | **11 / 30**; 18 hit the step limit |
| verdict | **REAL**, +5 outside a floor of 1 |
| where the gain is | the symptom-phrased NameError, 0/5 → 5/5, in zero model steps: routed as a fix, the harness's typo repair lands it before the model is asked |
| the other four bugs | 1/5 at best on either route |
| `llama3.1:8b` on the same host | **not measurable**: word salad above ~500 prompt tokens on this Ollama build (0.34.0, ROCm); the 30B and 7B on the same prompt are fine |

On a small model the decider is worth what the harness can do
deterministically once it knows the kind of task. Today that is one
repair; each further one on the bug-fix path widens the gain.

Write-up: [What would make it useful]({{ '/investigations/what-would-make-it-useful/' | relative_url }})
· records `docs/experiments/decide-regex-7b.json`, `decide-model-7b.json`.

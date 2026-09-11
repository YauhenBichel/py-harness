"""Run one task from start to finish.

    from harness import Agent, AgentOptions

    result = Agent(AgentOptions(project=Path("~/app"))).run("fix the NameError")

This class is responsible for the order of steps and nothing else. It asks
`harness.agent.prompt` what to send to the model, `harness.agent.policy`
whether a proposed action is allowed, and `harness.agent.dispatch` to carry
an allowed action out.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

from harness.act.autofix import (
    apply_cli_mock_test,
    apply_cover_test,
    apply_person_bind,
    unbound_typo,
)
from harness.act.parse import parse_turn_smart
from harness.act.tools import run_python
from harness.scan.names import undefined_in_file
from harness.agent.dispatch import ACTIONS, run_action
from harness.agent.options import AgentOptions, AgentResult, Step
from harness.agent.policy import (
    LoopState,
    done_without_proof,
    next_prompt,
    refuse_before,
    refuse_done,
    should_run_suite_after_write,
)
from harness.agent.prompt import Preamble, build_preamble
from harness.locate import named_file_review_summary
from harness.memory import Conversation
from harness.model.engine import make_generate
from harness.model.ollama_generate import CONTEXT_TOKENS
from harness.observe.trace_record import append_turn, default_trace_path
from harness.scan.design import render_design_review
from harness.task import (
    looks_like_add_feature,
    looks_like_app_loop,
    looks_like_bugfix,
    looks_like_design_loop,
    looks_like_question,
    looks_like_ship,
    looks_unclear,
    named_project_file,
)


@dataclass(frozen=True)
class Question:
    """A question the agent needs answered before it can continue.

    Fields:
        text: the question.
        options: answers the agent considers likely. May be empty.
    """

    text: str
    options: tuple[str, ...] = ()

    def render(self) -> str:
        if not self.options:
            return self.text
        listed = "\n".join(f"  {i}. {opt}" for i, opt in enumerate(self.options, 1))
        return f"{self.text}\n{listed}"


def trace_path(options: AgentOptions) -> Path | None:
    """Where this run writes its turns, or None when it writes none.

    Recording is on unless asked not to. A run that records nothing
    leaves no way to measure it afterwards, and there is no getting the
    trace back: this project reached sixty-five rows of training data
    while doing a week of real work, because the flag was opt-in.
    """
    if options.keep_no_record:
        return None
    if options.record is not None:
        return options.record.expanduser()
    return default_trace_path(options.resolved_project())


def new_trace_id() -> str:
    """A short name for one run, so its turns can be found together.

    A recorded turn carried no sign of which run it came from, so a turn
    from a run that finished the job looked exactly like a turn from one
    that spent twenty steps and wrote nothing. About a third of runs
    fail, and training on both without being able to tell them apart
    teaches the failure alongside the work.
    """
    return uuid.uuid4().hex[:12]


def _trace_result(
    options: AgentOptions, result: AgentResult, trace_id: str
) -> None:
    """Keep a row saying how the run ended, and under which id.

    `trace_id` has no default on purpose. It had one, and a caller that
    forgot it wrote a closing row signed with an empty string — which
    reads as a run whose turns cannot be found, so its outcome could not
    be used to filter anything. Three of the first thirty-five turns
    collected after the change were exactly that.
    """
    dest = trace_path(options)
    if dest is None:
        return
    append_turn(
        dest,
        {
            "run": trace_id,
            "user": options.task,
            "assistant": result.summary,
            "action": result.stopped,
            "stopped": result.stopped,
            "ok": result.ok,
        },
    )


def _question_from(turn) -> Question:
    text = (turn.query or turn.summary or "").strip() or "What should I do?"
    raw = turn.append or turn.replace or ""
    options = tuple(
        line.strip(" -*\t")
        for line in raw.splitlines()
        if line.strip(" -*\t")
    )
    return Question(text, options[:4])


@dataclass
class RunState:
    """What one run carries while it decides whether to call the model.

    `run()` used to hold all of this in local variables across two
    hundred lines, which is why the steps could not be read or tested
    apart from each other.

    Fields:
        options: the request, replaced when the user answers a question.
        preamble: what the harness found before any model turn.
        trace_id: a short name for this run, stamped on every turn it
            records, so the turns of a run that worked can be told from
            the turns of one that did not.
        writes: project-relative paths this run has changed.
        test_note: what the suite said after a mechanical fix, when that
            fix was not the end of the job. It is put to the model so it
            starts from the real failure instead of looking for one.
    """

    options: AgentOptions
    preamble: object
    trace_id: str = field(default_factory=new_trace_id)
    writes: list[str] = field(default_factory=list)
    test_note: str = ""

    def answer_was(self, answer: str, *, rebuild: bool = False) -> None:
        """Fold the user's answer into the task and say so in the trace."""
        self.options = _with_task(self.options, f"{self.options.task} ({answer})")
        if rebuild:
            self.preamble = build_preamble(self.options)
        self.options.emit("preamble", f"user answered: {answer}")

    def mechanical_note(self, fallback: str) -> str:
        """The first line of what the mechanical pass reported."""
        return next(
            (
                line[2:]
                for line in (getattr(self.preamble, "autofix", "") or "").splitlines()
                if line.startswith("- ")
            ),
            fallback,
        )

    def first_prompt(self) -> str:
        """The prompt the model opens on."""
        prompt = self.preamble.prompt
        if not self.test_note:
            return prompt
        return (
            f"{prompt}\n\nHarness ran tests after the mechanical fix:\n"
            f"{self.test_note}\n"
            "Action: patch the remaining failure, or Action: done if "
            "the task is already met."
        )


class Agent:
    """Runs one task against one project."""

    def __init__(self, options: AgentOptions) -> None:
        self.options = options
        self.project = options.resolved_project()

    def preamble(self, task: str | None = None) -> Preamble:
        options = self.options if task is None else _with_task(self.options, task)
        return build_preamble(options)

    def run(self, task: str | None = None) -> AgentResult:
        """Answer the task, and say honestly how the run ended.

        Read as four questions asked in order, before the model is
        loaded at all: is the task clear enough to start from, is
        reading the file the whole job, can the harness make the change
        on its own, and is there a typo only a person can settle. Each
        one either finishes the run or hands on to the next. Whatever
        survives all four is what the model is actually needed for.
        """
        options = self.options if task is None else _with_task(self.options, task)
        if not options.task.strip():
            raise ValueError("task required")
        run = RunState(options=options, preamble=build_preamble(options))
        run.options.emit("preamble", run.preamble.pre_text or "")

        for decide in (
            self._settle_an_unclear_task,
            self._read_the_file_if_that_is_the_whole_job,
            self._make_the_change_without_a_model,
            self._settle_a_typo_only_a_person_can,
        ):
            finished = decide(run)
            if finished is not None:
                _trace_result(run.options, finished, run.trace_id)
                return finished

        # Every run ends with a row saying how it ended. Without one,
        # the turns of a run that spent its whole budget look exactly
        # like the turns of a run that did the job.
        result = self._work_with_the_model(run)
        _trace_result(run.options, result, run.trace_id)
        return result

    # -- the four questions asked before the model is loaded ------------

    def _settle_an_unclear_task(self, run: RunState) -> AgentResult | None:
        """A task naming no file and no symbol cannot be started from.

        The harness asks rather than relying on the model to notice: a
        small model reaches for `patch` long before it reaches for `ask`.
        """
        question = opening_question(run.options.task, run.preamble)
        if question is None:
            return None
        answer = self._ask(question, run.options)
        if answer is None:
            return AgentResult(ok=False, summary=question.render(), stopped="question")
        run.answer_was(answer, rebuild=True)
        return None

    def _read_the_file_if_that_is_the_whole_job(
        self, run: RunState
    ) -> AgentResult | None:
        """A review of a named file is reading, not editing."""
        review = named_file_review_summary(self.project, run.options.task)
        if not review:
            return None
        run.options.emit("result", review)
        return AgentResult(ok=True, summary=review, stopped="done")

    def _make_the_change_without_a_model(self, run: RunState) -> AgentResult | None:
        """Apply the mechanical repairs, and stop if they were enough.

        These are the cases that cannot be got wrong: a misspelling with
        exactly one candidate in scope, a missing import for a module
        everyone knows, a test appended where one already exists. They
        take a tenth of a second and give the same answer every time.
        """
        if not run.preamble.autofix:
            return None
        run.writes.extend(_autofix_paths(run.preamble.autofix))
        if not run.options.allow_writes:
            return AgentResult(
                ok=True,
                summary=f"Read-only: would {run.mechanical_note('mechanical fix')}. "
                "Nothing written.",
                stopped="done",
                writes=(),
            )
        still_undefined = self._names_left_undefined(run)
        verdict, test_output = _verify_mechanical(self.project)
        run.options.emit("result", test_output)
        if still_undefined:
            run.test_note = (
                f"undefined name {still_undefined[0]} after the "
                "mechanical fix. The suite is not enough."
            )
            run.options.emit("result", run.test_note)
            return None
        if verdict not in {"passed", "no suite"}:
            run.test_note = test_output
            return None
        tail = (
            "Tests passed."
            if verdict == "passed"
            else "This project has no tests to check it against."
        )
        note = run.mechanical_note("mechanical fix applied")
        return AgentResult(
            ok=True,
            summary=f"{note}. {tail}",
            stopped="done",
            writes=tuple(run.writes),
        )

    def _names_left_undefined(self, run: RunState) -> list[str]:
        """Names still unbound in what the mechanical pass just wrote."""
        if not looks_like_bugfix(run.options.task):
            return []
        found: list[str] = []
        for rel in run.writes:
            found.extend(undefined_in_file(self.project / rel))
        return found

    def _settle_a_typo_only_a_person_can(self, run: RunState) -> AgentResult | None:
        """A misspelling with no safe candidate is a question, not a guess."""
        question = leftover_bind_question(run.options.task, self.project)
        if question is None:
            return None
        answer = self._ask(question, run.options)
        if answer is None:
            return AgentResult(
                ok=False,
                summary=question.render(),
                stopped="question",
                writes=tuple(run.writes),
            )
        # Asking is not writing, so a read-only run may still ask. What it
        # may not do is act on the answer: `ask` and `--dry-run` both
        # promise the folder is left alone.
        note = apply_person_bind(
            self.project,
            run.options.task,
            answer,
            write=run.options.allow_writes,
        )
        if not note:
            return AgentResult(
                ok=False,
                summary=(
                    f"{question.render()} "
                    "That answer is still not something this method can return."
                ),
                stopped="question",
                writes=tuple(run.writes),
            )
        if not run.options.allow_writes:
            return AgentResult(
                ok=True,
                summary=f"Read-only: would {note}. Nothing written.",
                stopped="done",
                writes=(),
            )
        named = named_project_file(run.options.task, self.project)
        if named and named not in run.writes:
            run.writes.append(named)
        verdict, test_output = _verify_mechanical(self.project)
        run.options.emit("result", test_output)
        if verdict not in {"passed", "no suite"}:
            # The name is bound, but the project is red. A red suite is
            # never a finished run: the mechanical pass hands the real
            # failure to the model, and so does this.
            run.test_note = test_output
            return None
        tail = (
            "Tests passed."
            if verdict == "passed"
            else "This project has no tests to check it against."
        )
        return AgentResult(
            ok=True,
            summary=f"{note}. {tail}",
            stopped="done",
            writes=tuple(run.writes),
        )

    # -- what is left is what the model is for --------------------------

    def _work_with_the_model(self, run: RunState) -> AgentResult:
        options = run.options
        pre = run.preamble
        # The run's memory belongs here, not in the model package: what
        # is kept and what is let go is a harness decision.
        memory = Conversation(
            budget_tokens=CONTEXT_TOKENS, system=pre.system or options.system or ""
        )
        label, generate = make_generate(
            options.engine,
            options.max_tokens,
            model=options.model,
            system=pre.system or options.system,
            memory=memory,
        )
        options.emit("engine", f"{label}  project {self.project}  mode {pre.brief.kind}")
        state = self._starting_state(run)
        prompt = run.first_prompt()
        steps: list[Step] = []

        for number in range(1, options.steps + 1):
            draft = generate(prompt)
            _remember(generate, prompt, draft)
            options.emit("draft", f"--- step {number} ---\n{draft}")
            turn = parse_turn_smart(
                draft,
                question=looks_like_question(options.task),
                ship=looks_like_ship(options.task),
            )
            trace = trace_path(options)
            if trace is not None:
                append_turn(
                    trace,
                    {
                        "run": run.trace_id,
                        "user": prompt,
                        "assistant": draft,
                        "action": turn.action if turn else "",
                    },
                )
            if turn is None:
                steps.append(Step(number, "", refused="unparsed", draft=draft))
                prompt = f"Could not parse. One Action: {ACTIONS}"
                continue

            if turn.action == "done":
                blocked = refuse_done(state, turn)
                if blocked:
                    steps.append(Step(number, "done", refused=blocked, draft=draft))
                    options.emit("refused", blocked)
                    prompt = blocked
                    continue
                steps.append(Step(number, "done", result=turn.summary, draft=draft))
                # The model has run out of refusals but still has nothing
                # to show. Let the run end; do not let it end as a win.
                unproven = done_without_proof(state, turn)
                return AgentResult(
                    ok=not unproven,
                    summary=unproven or turn.summary or "done",
                    stopped="done",
                    steps=tuple(steps),
                    writes=tuple(run.writes),
                )

            # Policy first, ask included: the cap on repeated questions
            # lives there, so it has to run before the question is put.
            blocked = refuse_before(state, turn)
            if blocked:
                steps.append(
                    Step(number, turn.action, turn.path, refused=blocked, draft=draft)
                )
                options.emit("refused", blocked)
                prompt = blocked
                continue

            if turn.action == "ask":
                question = _question_from(turn)
                state.questions_asked += 1
                answer = self._ask(question, options)
                if answer is None:
                    steps.append(
                        Step(number, "ask", result=question.render(), draft=draft)
                    )
                    return AgentResult(
                        ok=False,
                        summary=question.render(),
                        stopped="question",
                        steps=tuple(steps),
                        writes=tuple(run.writes),
                    )
                steps.append(Step(number, "ask", result=answer, draft=draft))
                prompt = f"The user answered: {answer}\n\nNext Action:"
                continue

            result = self._carry_out(turn, state, run)
            result, nudge = _nudge_after_action(
                self.project, state, turn, result, pre.target
            )
            options.emit("result", result)
            steps.append(
                Step(number, turn.action, state.last_path, result=result, draft=draft)
            )
            prompt = (
                f"Tool result:\n{result}\n\n{nudge}"
                if nudge
                else f"Tool result:\n{result}\n\nNext Action:"
            )

        return AgentResult(
            ok=False,
            summary=f"stopped after {options.steps} steps",
            stopped="steps",
            steps=tuple(steps),
            writes=tuple(run.writes),
        )

    def _starting_state(self, run: RunState) -> LoopState:
        pre, options = run.preamble, run.options
        return LoopState(
            task=options.task,
            project=self.project,
            located_path=pre.located_path,
            located_signature=pre.located_signature,
            prelude_ran=bool(pre.pre_text),
            allow_writes=options.allow_writes,
            last_path=pre.located_path,
            instructions=_instruction_lines(pre),
            scope=options.scope,
            autofixed=bool(pre.autofix),
            # Anything already written counts, not only the mechanical
            # pass: a person's answer to an unbindable typo is written
            # before the model starts, and leaving that out let the model
            # say `done` over a suite nobody had run.
            wrote_something=bool(pre.autofix or run.writes),
            existing_paths=pre.existing_paths,
            design_report=(
                render_design_review(self.project, options.scope)
                if looks_like_design_loop(options.task)
                else ""
            ),
        )

    def _carry_out(self, turn, state: LoopState, run: RunState) -> str:
        """Run one action and record what it changed."""
        try:
            result, state.last_path = run_action(
                self.project,
                turn,
                state.last_path,
                run.options.scope,
                run.preamble.target,
                task=run.options.task,
            )
        except (ValueError, OSError) as exc:
            # The action raised, so `run_action` never returned a path and
            # `last_path` still holds the previous step's file. Everything
            # downstream then talks about the wrong one: the step log
            # blames a file the model did not touch, and the repair names
            # it too. A failed patch is still about the file it named.
            state.last_path = turn.path or state.last_path
            return str(exc)
        if turn.action == "read" and state.last_path:
            state.files_seen.add(state.last_path)
        if turn.action == "run" and result.startswith("exit 0"):
            state.ran_tests = True
        if result.startswith(("patched", "wrote")):
            if turn.action == "patch":
                state.guard.remember_patch_result(turn, "applied")
            run.writes.append(turn.path or state.last_path)
            state.wrote_something = True
            cover = _cover_after_add(
                self.project, run.options.task, turn.path or state.last_path
            )
            if cover:
                for rel in _autofix_paths(f"- {cover}"):
                    if rel not in run.writes:
                        run.writes.append(rel)
                result = f"{result}\n{cover}"
        elif turn.action == "patch":
            state.guard.remember_patch_result(turn, "refused")
        return result

    def _ask(self, question: Question, options: AgentOptions) -> str | None:
        """None means nobody is there to answer — the caller decides."""
        handler = getattr(options, "on_question", None)
        if handler is None:
            return None
        return handler(question)


def _nudge_after_action(project, state: LoopState, turn, result: str, target):
    """After a write, run the suite when tests already cover the work."""
    if not should_run_suite_after_write(state, result, state.last_path):
        return result, next_prompt(state, turn, result, target)
    suite = run_python(
        project, ("-m", "unittest", "discover", "-s", "tests", "-q")
    )
    if suite.startswith("exit 0"):
        state.ran_tests = True
    run_turn = SimpleNamespace(action="run", path=getattr(turn, "path", "") or "")
    return (
        f"{result}\n{suite}",
        next_prompt(state, run_turn, suite, target),
    )


def _cover_after_add(project, task: str, path: str) -> str:
    """Add the AAA test once the new function exists. Empty if not this job."""
    if looks_like_app_loop(task):
        return apply_cli_mock_test(project, task, write=True)
    if not looks_like_add_feature(task):
        return ""
    if "test" in (path or "").replace("\\", "/").lower():
        return ""
    return apply_cover_test(project, task, write=True)


def _autofix_paths(note: str) -> list[str]:
    """Paths named in mechanical-fix notes, in the order they were written."""
    found: list[str] = []
    for line in note.splitlines():
        if not line.startswith("- ") or " in " not in line:
            continue
        tail = line.rsplit(" in ", 1)[-1].strip()
        if tail.endswith(".py") and tail not in found:
            found.append(tail)
    return found


def _verify_mechanical(project) -> tuple[str, str]:
    """Run the project suite after a mechanical fix. No model.

    Returns "passed", "failed", or "no suite". A project with no tests has
    not failed anything, and saying so keeps the loop from asking the model
    to repair a failure that does not exist.
    """
    result = run_python(project, ("-m", "unittest", "discover", "-s", "tests", "-q"))
    if result.startswith("exit 0"):
        return "passed", result
    if "no tests/ directory" in result:
        return "no suite", result
    return "failed", result


def leftover_bind_question(task: str, project) -> Question | None:
    """Ask when a named file holds a typo the harness must not guess at.

    `stauts` inside `def status` reads as a misspelling of `status`, and
    `status` is the method's own name, which is not in scope in its body.
    Binding it writes `return status`, still a NameError, in a tenth of a
    second and reports success. Sending it to the model instead spent
    twenty steps and left `return stauts` untouched. A person has to say
    what was meant. Their answer is written as a Constant or an in-scope
    name. The method name is still refused.

    Only a name that looks like a typo counts. Any other undefined name
    is work the model can do: a missing import, or something the task is
    asking to be written. Asking about those would stop a run that had
    every chance of finishing.
    """
    found = unbound_typo(task, project)
    if found is None:
        return None
    shown = ", ".join(f"`{name}`" for name in found.near[:3])
    return Question(
        f"`{found.bad}` in {found.rel} looks like {shown}, but none of those "
        "is in scope where it is used. What did you mean?",
    )


def opening_question(task: str, pre) -> Question | None:
    """Return a question to put before the run starts, or None to proceed.

    Only returned when the task names nothing the agent can search for and
    the harness did not find a file on its own.
    """
    if pre.located_path or not looks_unclear(task):
        return None
    options = tuple(
        item for item in (pre.target.module, pre.target.test) if item
    )
    return Question(
        f'"{task.strip()}" does not name a file or a function. '
        "Which file should I work on?",
        options,
    )


def _instruction_lines(pre) -> tuple[str, ...]:
    """Every line the model was handed, so an echo of any of them is caught.

    The skills were checked but the system prompt was not, and its examples
    are handed over on every single turn. Asked what a function returns, an
    8B answered with the system prompt's own example line: "one short
    question, when the task could mean two different things".
    """
    lines: list[str] = []
    sources = [skill.body for skill in pre.skills]
    if getattr(pre, "system", ""):
        sources.append(pre.system)
    for body in sources:
        lines.extend(
            line.strip()
            for line in body.splitlines()
            if len(line.strip()) >= 12 and not line.strip().startswith("Action:")
        )
    return tuple(lines)


def _with_task(options: AgentOptions, task: str) -> AgentOptions:
    from dataclasses import replace

    return replace(options, task=task)


def _remember(generate, prompt: str, draft: str) -> None:
    """Hand the exchange to the run's memory, if it keeps one."""
    memory = getattr(generate, "memory", None)
    if memory is None:
        return
    memory.remember(prompt, draft)

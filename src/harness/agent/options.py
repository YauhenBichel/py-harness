"""The inputs and outputs of a run.

`AgentOptions` is everything the caller chooses. `AgentResult` is
everything the run reports back. These two classes are the public interface
of the harness; the other modules in this package are how the run is
carried out.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

# The everyday model name and system prompt are product defaults that the
# training side also needs, so they are defined there and imported here.
# This is the only place `harness` reaches into `finetune`.
from finetune.agent_system import AGENT_SYSTEM
from finetune.everyday import DEFAULT_EVERYDAY_OLLAMA

DEFAULT_STEPS = 20
DEFAULT_MAX_TOKENS = 700


@dataclass(frozen=True)
class AgentOptions:
    """Settings for one run.

    Fields:
        project: directory the agent may read and write inside.
        task: what the user asked for, in their own words.
        model: name of the Ollama model to use.
        engine: "ollama", "mlx", or "openai" (remote OpenAI-compatible HTTP).
        scope: subdirectory to stay within. Empty means the whole project.
        skills: skill names to load. Empty means choose them from the task.
        steps: maximum number of model turns before the run stops.
        max_tokens: maximum length of one model reply.
        drafts: how many replies to ask for at each step, keeping the
            first that parses into an action the loop can carry out.
            One means the behaviour this harness has always had. A reply
            that does not parse costs a whole step, and on small models
            format compliance — not reasoning — is the common failure:
            five separate draft shapes had to be repaired in the parser
            before a hosted model could be measured at all.
        allow_writes: when False, patch, edit and run are refused and the
            project is not modified. Used for the HTTP server and --dry-run.
        record: file to append redacted turns to, for training data.
            None means the project's own `.python-vibe/traces.jsonl`,
            which is the default: a run that records nothing leaves no
            way to measure it later, and every trace thrown away is a
            trace nobody gets back. `keep_no_record` turns it off.
        keep_no_record: write no trace at all.
        system: system prompt template. Placeholders are filled per run.
        on_event: called with progress messages. None means print nothing.
        on_question: called when the agent asks the user something. None
            means nobody is available to answer, and the run stops instead.
    """

    project: Path
    task: str = ""
    model: str = DEFAULT_EVERYDAY_OLLAMA
    engine: str = "ollama"
    scope: str = ""
    skills: tuple[str, ...] = ()
    steps: int = DEFAULT_STEPS
    max_tokens: int = DEFAULT_MAX_TOKENS
    drafts: int = 1
    allow_writes: bool = True
    record: Path | None = None
    keep_no_record: bool = False
    system: str = AGENT_SYSTEM
    on_event: Callable[[str, str], None] | None = None
    # Answering a question is optional. No handler means the loop stops
    # and hands the question back rather than guessing silently.
    on_question: Callable[..., str] | None = None

    def resolved_project(self) -> Path:
        project = self.project.expanduser().resolve()
        if not project.is_dir():
            raise ValueError(f"not a directory: {project}")
        return project

    def emit(self, kind: str, text: str) -> None:
        if self.on_event is not None:
            self.on_event(kind, text)


@dataclass(frozen=True)
class Step:
    """One turn of the loop.

    Fields:
        number: position in the run, starting at 1.
        action: the action the model asked for, or "" if it could not be read.
        path: file the action applied to.
        result: text returned to the model.
        refused: reason the action was not carried out, or "" if it ran.
        draft: the model's full reply for this turn.
    """

    number: int
    action: str
    path: str = ""
    result: str = ""
    refused: str = ""
    draft: str = ""

    @property
    def ran(self) -> bool:
        return not self.refused


@dataclass(frozen=True)
class AgentResult:
    """What happened during a run.

    Fields:
        ok: True when the agent finished the task.
        summary: the agent's closing sentence, or the reason it stopped.
        stopped: "done", "steps" when the step budget ran out, or
            "question" when the agent needs an answer to continue.
        steps: every turn, in order.
        writes: files that were changed.
    """

    ok: bool
    summary: str
    stopped: str
    steps: tuple[Step, ...] = ()
    writes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def refusals(self) -> tuple[str, ...]:
        return tuple(step.refused for step in self.steps if step.refused)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "summary": self.summary,
            "stopped": self.stopped,
            "steps": [
                {
                    "number": step.number,
                    "action": step.action,
                    "path": step.path,
                    "refused": step.refused,
                    "result": step.result[:2000],
                }
                for step in self.steps
            ],
            "writes": list(self.writes),
        }

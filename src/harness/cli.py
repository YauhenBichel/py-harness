"""Command line interface for the harness.

One command with subcommands, so a user does not have to know which file in
`scripts/` to run:

    python -m harness brief  ~/app
    python -m harness layout ~/app
    python -m harness ask    ~/app "what does compute_total return?"
    python -m harness run    ~/app "add multiply(a, b) and a test"
    python -m harness serve    --project ~/app
    python -m harness mcp      --project ~/app
    python -m harness editors  cursor --allow-writes
    python -m harness commit   ~/app "why the change landed"
    python -m harness route    "what does compute_total return?"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from harness.agent import Agent, AgentOptions
from harness.agent.options import DEFAULT_MAX_TOKENS, DEFAULT_STEPS
from harness.scan.layout import render_layout
from harness.scan.project_brief import classify_project, render_brief_for_person
from harness.skillkit.catalog import list_skills

# The everyday jobs. Extra commands exist; this is what people should
# type first. {prog} is filled in from how the tool was started: the
# installed command is not always on PATH, and printing it when it is
# not sends a first-time user to a command that does not exist.
HOW_TO = """\
{prog} — four jobs, on this machine.

  {prog} brief
  {prog} ask  "what does compute_total return?"
  {prog} run  "write tests for apply_discount"
  {prog} run  "find the NameError and fix it"
  {prog} run  "add a function total_lines and a test"

Run those inside your project folder. To point at another folder:

  {prog} brief /path/to/project
  {prog} ask /path/to/project "what does compute_total return?"

ask never writes. Daily run writes, then runs the suite; a failing
traceback goes back to the model once. Unique-typo NameError and a
template add are harness demos on demo/orders — they finish with no model.
Sample (clone first): {prog} brief demo/orders
More commands: {prog} --help
"""


def how_to() -> str:
    """The short list, naming the command this machine can actually run."""
    return HOW_TO.format(prog=_program_name())


def resolve_project_task(first: str, second: str | None) -> tuple[Path, str]:
    """`ask DIR TASK` or `ask TASK` (DIR is the current folder)."""
    if second:
        return Path(first).expanduser().resolve(), second
    path = Path(first).expanduser()
    if path.exists() and path.is_dir() and " " not in first.strip():
        return path.resolve(), ""
    return Path(".").resolve(), first


def _printer(verbose: bool):
    def emit(kind: str, text: str) -> None:
        if not text:
            return
        if kind == "draft":
            print(f"\n{text}\n", flush=True)
        elif verbose or kind in {"refused", "engine"}:
            print(text[:2000], file=sys.stderr)

    return emit


def _prompt_user(question) -> str:
    """The agent asked. Put it to the person actually sitting here."""
    print(f"\n{question.render()}", file=sys.stderr)
    try:
        answer = input("> ").strip()
    except EOFError:
        return ""
    if question.options and answer.isdigit():
        index = int(answer) - 1
        if 0 <= index < len(question.options):
            return question.options[index]
    return answer


def _options(args, *, interactive: bool) -> AgentOptions:
    return AgentOptions(
        project=args.project,
        task=getattr(args, "task", "") or "",
        model=args.model,
        engine=args.engine,
        scope=args.scope,
        skills=tuple(args.skill or ()),
        steps=args.steps,
        max_tokens=args.max_tokens,
        drafts=getattr(args, "drafts", 1),
        allow_writes=getattr(args, "allow_writes", True),
        record=getattr(args, "record", None),
        keep_no_record=getattr(args, "no_record", False),
        on_event=_printer(args.verbose),
        on_question=_prompt_user if interactive else None,
    )


def _add_agent_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scope", default="", help="work only inside this folder")
    parser.add_argument("--skill", action="append", default=[], metavar="NAME")
    parser.add_argument("--model", default=AgentOptions(project=Path(".")).model)
    parser.add_argument(
        "--engine",
        default="ollama",
        help="ollama (local or OLLAMA_HOST), mlx, or openai (remote weights)",
    )
    parser.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument(
        "--drafts",
        type=int,
        default=1,
        metavar="N",
        help="ask up to N times at each step, keeping the first reply that "
        "parses into an action (default 1, the long-standing behaviour)",
    )
    parser.add_argument(
        "--record",
        type=Path,
        help="write turns here instead of .python-vibe/traces.jsonl",
    )
    parser.add_argument(
        "--no-record",
        action="store_true",
        help="write no trace of this run",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--json", action="store_true", help="print the result as JSON")


def _program_name() -> str:
    """What to print in usage: the installed command, or the module form."""
    name = Path(sys.argv[0]).name
    if name.startswith("py-harness"):
        return "py-harness"
    if name.startswith("python-vibe"):
        return "python-vibe"
    return "python -m harness"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=_program_name(),
        description="Four everyday Python jobs, on this machine.",
        epilog="Run py-harness with no arguments for the short how-to.",
    )
    subs = parser.add_subparsers(dest="command", required=False)

    brief = subs.add_parser("brief", help="summarise this folder. Needs no AI model.")
    brief.add_argument("project", nargs="?", default=".", type=Path)
    brief.add_argument("--scope", default="")

    layout = subs.add_parser("layout", help="report what makes a project hard to read. Needs no AI model.")
    layout.add_argument("project", nargs="?", default=".", type=Path)

    route = subs.add_parser(
        "route", help="which local model suits a task. Needs no AI model."
    )
    route.add_argument("task")

    ask = subs.add_parser("ask", help="answer a question. Changes nothing.")
    ask.add_argument("first", help="the question, or a folder then the question")
    ask.add_argument("second", nargs="?", default="", help="the question, when the first argument is a folder")
    _add_agent_flags(ask)

    run = subs.add_parser("run", help="write tests, fix a bug, or add one small function")
    run.add_argument("first", help="what to do, or a folder then what to do")
    run.add_argument("second", nargs="?", default="", help="the task, when the first argument is a folder")
    run.add_argument(
        "--dry-run",
        dest="allow_writes",
        action="store_false",
        help="say what it would change, without changing anything",
    )
    _add_agent_flags(run)

    serve = subs.add_parser("serve", help="serve on this machine only. Changes nothing unless --allow-writes.")
    serve.add_argument("--project", type=Path, required=True)
    serve.add_argument("--port", type=int, default=8090)
    serve.add_argument(
        "--allow-writes",
        action="store_true",
        help="allow callers to change files inside --project",
    )
    serve.add_argument("--model", default=AgentOptions(project=Path(".")).model)

    mcp = subs.add_parser(
        "mcp",
        help="let an editor call py-harness. Changes nothing unless --allow-writes.",
    )
    mcp.add_argument("--project", type=Path, required=True)
    mcp.add_argument("--allow-writes", action="store_true")
    mcp.add_argument("--model", default=AgentOptions(project=Path(".")).model)

    last = subs.add_parser(
        "last", help="show the latest recorded turns. Needs no AI model."
    )
    last.add_argument("project", nargs="?", default=".", type=Path)

    commit = subs.add_parser(
        "commit",
        help="record current changes. You stay the author; python-vibe is co-author.",
    )
    commit.add_argument("project", type=Path)
    commit.add_argument("summary", help="why, not what (at least 8 characters)")

    editors = subs.add_parser(
        "editors",
        help="write ready-made editor settings into a project",
    )
    editors.add_argument("kind", choices=("vscode", "continue", "cursor", "zed"))
    editors.add_argument(
        "--project",
        type=Path,
        default=Path("."),
        help="folder it may change (default: current directory)",
    )
    editors.add_argument(
        "--allow-writes",
        action="store_true",
        help="let the editor's run tool change files (cursor MCP only)",
    )
    editors.add_argument(
        "--global",
        dest="user_wide",
        action="store_true",
        help="merge into ~/.cursor/mcp.json so every workspace can call it",
    )
    return parser


def _require_dir(raw: Path) -> Path | str:
    """A real folder, or a one-line refusal. Missing paths used to look empty."""
    path = raw.expanduser().resolve()
    if path.is_dir():
        return path
    return f"not a directory: {raw}"


def _run_brief(args) -> int:
    project = _require_dir(args.project)
    if isinstance(project, str):
        print(project, file=sys.stderr)
        return 2
    print(
        render_brief_for_person(
            classify_project(project, args.scope), scope=args.scope
        )
    )
    # The full catalogue is written for the model, in the model's own
    # syntax. Printing it here buries the answer the person asked for.
    count = len(list_skills(project))
    print()
    print(
        f"py-harness has {count} skills it can apply. It picks them from "
        "the wording of your task; you do not choose them."
    )
    return 0


def _run_layout(args) -> int:
    print(render_layout(args.project.expanduser().resolve()))
    return 0


def _run_route(args) -> int:
    from harness import route_advice

    print(route_advice(args.task))
    return 0


def _run_serve(args) -> int:
    from harness.server import serve

    return serve(
        args.project.expanduser().resolve(),
        port=args.port,
        allow_writes=args.allow_writes,
        model=args.model,
    )


def _run_mcp(args) -> int:
    from harness.mcp_stdio import serve_stdio

    return serve_stdio(
        args.project.expanduser().resolve(),
        allow_writes=args.allow_writes,
        model=args.model,
    )


def _run_last(args) -> int:
    from harness.observe.trace_record import render_last

    print(render_last(args.project.expanduser().resolve()))
    return 0


def _run_commit(args) -> int:
    from harness.ship.git_ship import commit_changes

    print(commit_changes(args.project.expanduser().resolve(), args.summary))
    return 0


def _run_editors(args) -> int:
    from harness.editor_kit import install_editors, next_steps

    try:
        written = install_editors(
            args.project,
            args.kind,
            allow_writes=getattr(args, "allow_writes", False),
            user_wide=getattr(args, "user_wide", False),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    for path in written:
        print(path)
    print()
    print(
        next_steps(
            args.kind,
            allow_writes=getattr(args, "allow_writes", False),
            user_wide=getattr(args, "user_wide", False),
        )
    )
    return 0


def _run_agent(args) -> int:
    """ask and run: the two commands that call the model."""
    interactive = sys.stdin.isatty()
    if args.command == "ask":
        args.allow_writes = False
    try:
        result = Agent(_options(args, interactive=interactive)).run()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result.as_dict(), indent=2))
    else:
        print(result.summary)
        if args.command == "run" and not getattr(args, "no_record", False):
            from harness.observe.trace_record import default_trace_path

            dest = getattr(args, "record", None) or default_trace_path(args.project)
            print(f"recorded {len(result.steps)} turns in {dest}", file=sys.stderr)
    return 0 if result.ok else 1


# One entry per subcommand. A chain of nine `if args.command ==` tests
# said the same thing at three times the length, and adding a command
# meant finding the right place in the middle of it.
COMMANDS = {
    "brief": _run_brief,
    "layout": _run_layout,
    "route": _run_route,
    "serve": _run_serve,
    "mcp": _run_mcp,
    "last": _run_last,
    "commit": _run_commit,
    "editors": _run_editors,
    "ask": _run_agent,
    "run": _run_agent,
}


def _missing_task_message(command: str) -> str:
    """What to print when ask or run was given no words to work on."""
    wanted = "a question" if command == "ask" else "what to change"
    return (
        f"{command} needs {wanted}, for example:\n"
        f'  {_program_name()} {command} "what does add return?"'
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.command:
        print(how_to(), end="")
        return 0

    if args.command in {"ask", "run"}:
        project, task = resolve_project_task(args.first, args.second or None)
        if not task.strip():
            print(_missing_task_message(args.command), file=sys.stderr)
            return 2
        args.project = project
        args.task = task

    return COMMANDS[args.command](args)

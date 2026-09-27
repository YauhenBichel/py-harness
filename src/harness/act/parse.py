"""Parse one agent turn. Deterministic. No model."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass

from harness.act.code import extract_python

# A chat model decorates the line the harness is trying to read. It
# emboldens the label (`**Action:** patch`), numbers its steps
# (`1. Action: patch`), or explains the verb in the same breath
# (`Action: patch to add slugify`). Local weights write the bare line,
# so an anchored pattern was enough until the harness was pointed at a
# model it does not run itself — and then the turn parsed to nothing.
#
# Only `*`, `#`, `>` and list numbering are allowed as decoration, and
# never `_`, because a value may legitimately start with one and
# `Name: _helpers` must keep its underscore.
_DECOR = r"[ \t>*#-]{0,6}(?:\d{1,2}[.)][ \t]*)?[ \t>*]{0,4}"
_AFTER_KEY = r"[* \t]*"

# Hyphens are allowed so a skill name works as an action: every kit
# skill is hyphenated, and `\w+` could not match one. There is no `$`:
# anything after the verb is the model thinking aloud, and an unknown
# verb is still rejected by KNOWN_ACTIONS below.
_ACTION = re.compile(
    rf"^{_DECOR}Action:{_AFTER_KEY}([\w-]+)", re.MULTILINE | re.IGNORECASE
)
# Every verb the loop can carry out. A model that writes `Action: find`
# has put a field name on the Action line; that block is skipped so the
# turn is not spent on an unknown verb.
KNOWN_ACTIONS = frozenset(
    {
        "glob", "grep", "read", "edit", "patch", "run", "map", "plan",
        "skill", "locate", "layout", "ask", "done",
        "issue", "branch", "commit", "push", "pr", "merge",
    }
)
_FIELD = re.compile(
    rf"^{_DECOR}(Path|File|Query|Pattern|Argv|Summary|Scope|Name|Number|Title):"
    rf"{_AFTER_KEY}(.+?)[ \t*]*$",
    re.MULTILINE,
)
_STOP = re.compile(
    rf"^{_DECOR}(Action|Path|File|Query|Pattern|Argv|Summary|Scope|Name|Number"
    rf"|Title|Body|Find|Replace|Append|Add):{_AFTER_KEY}",
    re.IGNORECASE,
)


# A model that answers in chat wraps code in a fence. Local weights
# happen not to; every hosted one does, so this only bites the moment
# the harness is pointed at a model it does not run itself.
# A fence marker alone on the last line, with or without a language:
# a whole-reply fence closing, or a second block the model opened
# and never filled. Either way it is not Python.
_CLOSING = re.compile(r"^[ \t]*```[\w+-]*[ \t]*$")
_FENCED = re.compile(
    r"^[^\S\n]*```[\w+-]*[^\S\n]*\n(.*?)\n[^\S\n]*```",
    re.DOTALL,
)


def unfenced(body: str) -> str:
    """The code inside a markdown fence, or the text unchanged.

    An `Append:` body arriving as ```python … ``` used to reach the file
    with the backticks still on it. What landed was a SyntaxError, and
    by its third turn a hosted 32B was reporting an unterminated string
    literal in a file it had broken itself. Nine of ten runs then spent
    the whole budget writing nothing that would load.

    Anything after the closing fence goes too. A model that signs off
    with "That should do it." puts that sentence inside the fence's
    file otherwise, which fails exactly the same way the backticks do.
    """
    found = _FENCED.match(body)
    if found:
        return found.group(1)
    # The model fenced its whole reply rather than the code, so the
    # block never opened with a fence and the closing one is left
    # trailing on the end of it. That reaches the file and is the same
    # SyntaxError, arriving by a different route.
    lines = body.splitlines()
    if lines and _CLOSING.match(lines[-1]):
        return "\n".join(lines[:-1]).rstrip()
    return body


def _block(text: str, key: str) -> str:
    match = re.search(
        rf"^{_DECOR}{key}:{_AFTER_KEY}(.*?)[ \t*]*$",
        text,
        re.MULTILINE | re.IGNORECASE,
    )
    if not match:
        return ""
    lines: list[str] = []
    first = match.group(1).rstrip()
    if first:
        lines.append(first)
    for line in text[match.end() :].lstrip("\n").splitlines():
        if _STOP.match(line):
            break
        lines.append(line.rstrip())
    return "\n".join(lines).rstrip()


@dataclass(frozen=True)
class AgentTurn:
    action: str
    path: str = ""
    query: str = ""
    pattern: str = ""
    argv: tuple[str, ...] = ()
    summary: str = ""
    source: str | None = None
    find: str = ""
    replace: str = ""
    scope: str = ""
    name: str = ""
    append: str = ""
    number: str = ""
    title: str = ""
    body: str = ""


_PREFERRED_WRITE = ("patch", "edit", "run", "locate", "done")
_PREFERRED_QUESTION = ("done", "locate", "grep", "read")
_PREFERRED_SHIP = (
    "issue",
    "branch",
    "commit",
    "push",
    "pr",
    "merge",
    "patch",
    "done",
)


# A field name written on the Action line. The model means the action that
# field belongs to, and every such turn was spent on "unknown Action".
_FIELD_AS_ACTION = {
    "append": "patch",
    "add": "patch",
    "find": "patch",
    "replace": "patch",
    "summary": "done",
}


def _body_after_action(text: str) -> str:
    """The code below the Action line, with the field lines left out.

    `Action: append` is followed by `Path:` and then the function. Stopping
    at the first field line returned nothing, so the turn was spent for no
    reason.
    """
    match = _ACTION.search(text)
    if not match:
        return ""
    lines = [
        line.rstrip()
        for line in text[match.end():].splitlines()
        if not _STOP.match(line)
    ]
    while lines and not lines[0].strip():
        lines.pop(0)
    return "\n".join(lines).strip("\n")


_DIFF_HEADER = re.compile(r"^\+\+\+\s+(?:b/)?(\S+)", re.MULTILINE)
_HUNK = re.compile(r"^@@.*@@", re.MULTILINE)


def _from_diff(text: str) -> dict[str, str]:
    """Find, Replace and Path read off a unified diff, or {}.

    A 7B answers "Action: patch" with a fenced ```diff``` block: the
    file headers, a hunk, `-` for the old line and `+` for the new. That
    is a complete, correct patch, and the harness answered "patch needs
    Find: or Append:" ten times in a row while the model re-sent it. The
    first hunk's removed lines are the Find and its added lines the
    Replace, with context lines kept on both sides so the Find still
    matches whole lines. A hunk that only adds is an Append.
    """
    hunk = _HUNK.search(text)
    if not hunk:
        return {}
    old: list[str] = []
    new: list[str] = []
    for line in text[hunk.end():].splitlines()[1:]:
        if line.startswith("@@") or line.startswith("```"):
            break
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            old.append(line[1:])
        elif line.startswith("+"):
            new.append(line[1:])
        elif line.startswith(" ") or not line:
            old.append(line[1:])
            new.append(line[1:])
        else:
            break
    while old and new and old[0] == new[0]:
        old.pop(0)
        new.pop(0)
    while old and new and old[-1] == new[-1]:
        old.pop()
        new.pop()
    found: dict[str, str] = {}
    header = _DIFF_HEADER.search(text)
    if header and header.group(1) not in {"/dev/null"}:
        found["path"] = header.group(1)
    if old:
        found["find"] = "\n".join(old).rstrip()
        found["replace"] = "\n".join(new).rstrip()
    elif new:
        found["append"] = "\n".join(new).rstrip()
    return found


_JSON_KEYS = {
    "path": "path", "file": "path", "query": "query", "pattern": "pattern",
    "summary": "summary", "find": "find", "replace": "replace",
    "append": "append", "add": "append", "scope": "scope", "name": "name",
    "number": "number", "title": "title", "body": "body",
}


def _from_json(text: str) -> AgentTurn | None:
    """A turn written as a JSON object, or None.

    Small chat models answer in ```json``` with {"action": "patch",
    "path": ..., "find": ..., "replace": ...}, and not always in valid
    JSON: a 7B quoted the values with single quotes. Both are read.
    Only an object with a known action counts, so braces in prose or in
    a code sample are never mistaken for a turn.
    """
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    raw = text[start:end + 1]
    data = None
    for load in (json.loads, ast.literal_eval):
        try:
            data = load(raw)
            break
        except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
            continue
    if not isinstance(data, dict):
        return None
    action = str(data.get("action") or "").strip().lower()
    if action not in KNOWN_ACTIONS:
        return None
    fields: dict[str, object] = {}
    for key, value in data.items():
        target = _JSON_KEYS.get(str(key).lower())
        if target and value is not None:
            fields[target] = str(value)
    argv = data.get("argv") or data.get("args") or ()
    if isinstance(argv, str):
        argv = argv.split()
    source = None
    if action == "edit":
        for key in ("source", "content", "new_content", "code"):
            if data.get(key):
                source = str(data[key])
                break
    return AgentTurn(
        action=action,
        argv=tuple(str(part) for part in argv if str(part)),
        source=source,
        **fields,  # type: ignore[arg-type]
    )


def parse_turn(text: str) -> AgentTurn | None:
    match = _ACTION.search(text)
    if not match:
        return None
    action = match.group(1).lower()
    body_as_append = ""
    if action in _FIELD_AS_ACTION and action not in KNOWN_ACTIONS:
        if action in {"append", "add"}:
            body_as_append = _body_after_action(text)
        action = _FIELD_AS_ACTION[action]
    fields = {m.group(1).lower(): m.group(2).strip() for m in _FIELD.finditer(text)}
    argv = tuple(part for part in fields.get("argv", "").split() if part)
    source = extract_python(text) if action == "edit" else None
    if action == "edit" and not source:
        extra = _block(text, "Append") or _block(text, "Add")
        if extra:
            source = extra
    find = unfenced(_block(text, "Find"))
    replace = unfenced(_block(text, "Replace"))
    append = unfenced(_block(text, "Append") or _block(text, "Add") or body_as_append)
    path = fields.get("path") or fields.get("file", "")
    if action == "patch" and not (find or replace or append):
        diff = _from_diff(text)
        find = diff.get("find", "")
        replace = diff.get("replace", "")
        append = diff.get("append", "")
        path = path or diff.get("path", "")
    return AgentTurn(
        action=action,
        path=path,
        query=fields.get("query", ""),
        pattern=fields.get("pattern", ""),
        argv=argv,
        summary=fields.get("summary", ""),
        source=source,
        find=find,
        replace=replace,
        scope=fields.get("scope", ""),
        name=fields.get("name", ""),
        append=append,
        number=fields.get("number", ""),
        title=fields.get("title", ""),
        body=_block(text, "Body"),
    )


def _is_skill_name(verb: str) -> bool:
    """`Action: write-tests` names a skill, which the loop loads."""
    return "-" in verb or "_" in verb


def parse_turn_smart(
    text: str, *, question: bool = False, ship: bool = False,
    asked_done: bool = False,
) -> AgentTurn | None:
    """Small models paste the Action menu. Pick one block by task kind.

    `asked_done` is set when the harness's last message told the model to
    finish. A reply that pastes its whole plan again then carries a stale
    patch above its done block, and taking the patch sent a 30B round the
    same refused Find: until the budget ran out, with the fix already in
    and the suite green. Once done has been asked for, done wins.
    """
    matches = [
        match
        for match in _ACTION.finditer(text)
        if match.group(1).lower() in KNOWN_ACTIONS or _is_skill_name(match.group(1))
    ]
    if not matches:
        return parse_turn(text) or _from_json(text)
    if len(matches) == 1:
        return parse_turn(text[matches[0].start() :])
    if asked_done:
        prefer = ("done",)
    elif question:
        prefer = _PREFERRED_QUESTION
    elif ship:
        prefer = _PREFERRED_SHIP
    else:
        prefer = _PREFERRED_WRITE
    chosen = matches[0]
    for match in matches:
        if match.group(1).lower() in prefer:
            chosen = match
            break
    start = chosen.start()
    end = len(text)
    for match in matches:
        if match.start() > start:
            end = match.start()
            break
    return parse_turn(text[start:end])

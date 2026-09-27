"""Read the user's task and report what kind of work it asks for.

Every layer needs to know whether the task is a question, a request to add
code, a rename, or a request to create a package. These functions are the
single place that decision is made, so the layers above agree with each
other. This module imports nothing from the rest of the harness.

Rule shared by all of the writer functions below: a question is never a
write, so each one returns False when the task is a question.
"""

from __future__ import annotations

import re

QUESTION_PREFIXES = (
    "what ",
    "why ",
    "how ",
    "where ",
    "which ",
    "explain ",
    "list ",
    "who ",
)
_SYMBOL = re.compile(r"\b([a-z_][a-z0-9_]{4,})\b")
_DOES_SYMBOL = re.compile(r"\bdoes\s+([a-z_][a-z0-9_]*)\b")
# A name written with brackets was typed on purpose. Eleven of the
# fifteen benchmark tasks spell the subject that way — `word_count(text)`
# — and taking it is right every time, where reading left to right takes
# `module` out of "create a new module with a function word_count(text)".
# A run then wrote a function literally called `module` and said so.
_CALLED = re.compile(r"\b([a-z_][a-z0-9_]*)\s*\(")
_SYMBOL_SKIP = frozenset(
    {
        # The word a task opens with is what to do, not what to do it to.
        # Asked to "create a new module and move the helpers into it", the
        # harness took `create` for a function name, found the word in a
        # test file and answered "already has a test for create".
        "build",
        "create",
        "delete",
        "make",
        "move",
        "remove",
        "rename",
        "split",
        "write",
        "about",
        "after",
        "and",
        "apply",
        "are",
        "before",
        "but",
        "can",
        "did",
        "does",
        "explain",
        "feature",
        "for",
        "from",
        "function",
        "had",
        "has",
        "how",
        "not",
        "refuse",
        "return",
        "source",
        "that",
        "the",
        "this",
        "was",
        "what",
        "where",
        "which",
        "who",
        "why",
        "with",
        "you",
    }
)
_ADD_START = re.compile(r"^(please\s+)?(add|implement|introduce|create)\b|new feature")
_SMELL = re.compile(
    r"\b(code smell|smell|rename|readable name|human[- ]readable|clean up|cleanup)\b"
)
_PACKAGE = re.compile(
    r"\b(scaffold|new package|new project|"
    r"create a package|create a project|create a pkg|"
    r"design and develop|"
    r"(?:design|develop|build|create) an? (?:small )?"
    r"(?:cli(?:\s+app|\s+tool|\s+application)?|"
    r"command[ -]line(?:\s+app|\s+tool)?|"
    r"app(?:lication)?|tool))\b",
    re.I,
)
_GITHUB_PR_APP = re.compile(
    r"\b(github|gh)\b.*\b(pr|prs|pull requests?)\b|"
    r"\b(pr|prs|pull requests?)\b.*\b(github|gh)\b",
    re.I,
)
_SNAKE_NAME = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
_PACKAGE_NOUN_SKIP = _SYMBOL_SKIP | frozenset(
    {
        "app",
        "application",
        "cli",
        "command",
        "design",
        "develop",
        "github",
        "line",
        "package",
        "project",
        "pull",
        "request",
        "requests",
        "reviewing",
        "scaffold",
        "script",
        "small",
        "tool",
    }
)
_REVIEW = re.compile(
    r"\b(review|system design|architecture|project structure|design review)\b"
)
_REFACTOR = re.compile(
    r"\b(refactor|extract (a )?function|split (the )?module|move function)\b"
)
_RENAME = re.compile(
    r"\brename\s+([A-Za-z_][A-Za-z0-9_]*)\s+to\s+([A-Za-z_][A-Za-z0-9_]*)",
    re.I,
)


def looks_like_question(task: str) -> bool:
    text = task.strip().lower()
    return text.endswith("?") or text.startswith(QUESTION_PREFIXES)


_FILE_OPERATION = re.compile(
    r"\b(move|rename|split|delete|remove|extract)\b.{0,60}"
    r"(\.py\b|\bmodule\b|\bfile\b|\bpackage\b|\bfolder\b)",
    re.I,
)


def looks_like_file_operation(task: str) -> bool:
    """Moving, renaming, splitting or deleting a file, not editing one.

    These have no symbol to work on, and guessing one is worse than
    having none: asked to "create a new module and move the helpers into
    it", the harness took a word out of the task, looked for a test
    naming it, found one, and answered "already has a test for create".
    """
    lowered = task.lower()
    if _FILE_OPERATION.search(lowered):
        return True
    return bool(
        re.search(r"\b(create|add)\b.{0,40}\b(new )?(module|file|package)\b", lowered)
        and re.search(r"\b(move|into it|and put)\b", lowered)
    )


def question_symbol(task: str) -> str:
    """The first word in the task that could be a symbol name."""
    called = [
        name
        for name in _CALLED.findall(task.lower())
        if name not in _SYMBOL_SKIP
    ]
    if called:
        return called[0]
    does = _DOES_SYMBOL.search(task.lower())
    if does:
        name = does.group(1)
        if name not in _SYMBOL_SKIP:
            return name
    hits = [word for word in _SYMBOL.findall(task.lower()) if word not in _SYMBOL_SKIP]
    return hits[0] if hits else ""


def looks_like_new_package(task: str) -> bool:
    if looks_like_question(task):
        return False
    return bool(_PACKAGE.search(task.strip().lower()))


def looks_like_app_loop(task: str) -> bool:
    """A greenfield CLI that talks to GitHub: list / show / comment, not a weekday copy."""
    return looks_like_new_package(task) and mentions_cli(task) and mentions_http(task)


def looks_like_app_overflow(task: str) -> bool:
    """A later typed run for comment / pagination / config. Not a new package."""
    if looks_like_question(task) or looks_like_new_package(task):
        return False
    text = task.strip().lower()
    if re.search(r"\bcomment\b", text) and re.search(
        r"\b(subcommand|argparse|mocked)\b", text
    ):
        return True
    return bool(re.search(r"\b(pagination|config file|path\.home)\b", text))


def mentions_cli(task: str) -> bool:
    """True when the task names a CLI, even if it is also a new package."""
    return bool(_SCRIPT.search(_without_paths(task)))


def mentions_http(task: str) -> bool:
    """True when the work talks to an HTTP API, including GitHub PRs."""
    if _HTTP.search(task):
        return True
    lowered = task.lower()
    if "url" in lowered and "json" in lowered:
        return True
    return bool(_GITHUB_PR_APP.search(task))


def package_noun(task: str) -> str:
    """The module name for a new-package task: pkg/<noun>.py.

    `question_symbol` takes the first five-letter word, so
    "design and develop a CLI" would become `pkg/design.py`. A snake_case
    name in the task wins; a GitHub-PR app is `pr_review`; otherwise the
    last content word after "for", then a leftover symbol, then `service`.
    """
    text = task.strip().lower()
    for name in _SNAKE_NAME.findall(text):
        if name not in _PACKAGE_NOUN_SKIP:
            return name
    if _GITHUB_PR_APP.search(text) or looks_like_app_overflow(task):
        return "pr_review"
    purpose = re.search(r"\bfor\s+(.+)$", text)
    if purpose:
        words = [
            word
            for word in re.findall(r"[a-z][a-z0-9]{2,}", purpose.group(1))
            if word not in _PACKAGE_NOUN_SKIP
        ]
        if len(words) == 1:
            return words[0]
        if len(words) >= 2:
            return f"{words[0]}_{words[1]}"
    symbol = question_symbol(task)
    if symbol and symbol not in _PACKAGE_NOUN_SKIP:
        return symbol
    return "service"


def looks_like_fix_smell(task: str) -> bool:
    if looks_like_question(task):
        return False
    text = task.strip().lower()
    # "find code smells" is a report. "fix the code smell" / rename is a write.
    if re.search(r"\b(find|report|list|show)\b", text) and "smell" in text:
        return False
    return bool(_SMELL.search(text))


_SHIP = re.compile(
    r"(\bopen a pr\b|\bcreate a pr\b|\bopen a pull request\b|"
    r"\bcommit\b|\bpush\b|\bmerge\b)",
    re.I,
)
_ISSUE_NUM = re.compile(r"(?:#|issue\s+#?|pr\s+#?)(\d+)", re.I)
_TICKET_WORK = re.compile(
    r"\b(fix|do|implement|write|add|address|handle|cover)\b", re.I
)
_PR_REF = re.compile(r"\b(pr|pull request)\s+#?\d+", re.I)


def looks_like_ship(task: str) -> bool:
    """Commit, push, open a PR, or merge — not merely “fix #50”."""
    if looks_like_question(task) or looks_like_new_package(task):
        return False
    return bool(_SHIP.search(task))


def looks_like_merge(task: str) -> bool:
    return looks_like_ship(task) and bool(re.search(r"\bmerge\b", task, re.I))


def issue_number(task: str) -> str:
    match = _ISSUE_NUM.search(task)
    return match.group(1) if match else ""


def looks_like_ticket(task: str) -> bool:
    return bool(issue_number(task))


def looks_like_pr_ref(task: str) -> bool:
    return bool(_PR_REF.search(task))


def looks_like_ticket_work(task: str) -> bool:
    """Do the work the ticket names, not only open or merge a PR."""
    if not looks_like_ticket(task) or looks_like_question(task):
        return False
    if looks_like_merge(task) and not _TICKET_WORK.search(task):
        return False
    return bool(_TICKET_WORK.search(task))


def looks_like_refactor(task: str) -> bool:
    if looks_like_question(task) or looks_like_new_package(task) or looks_like_ship(task):
        return False
    return bool(_REFACTOR.search(task.lower()))


def looks_like_design_loop(task: str) -> bool:
    """Review, then one-split, then review again until the scan is clean.

    "review src/orders.py for bugs" is a report on one file. That is not
    this loop. Live 8B on main spent eight turns fighting review-design
    after a named-file review.
    """
    if (
        task_paths(task)
        and looks_like_review_code(task)
        and not looks_like_refactor(task)
    ):
        return False
    return looks_like_review(task) or looks_like_refactor(task)


def looks_like_review(task: str) -> bool:
    if looks_like_new_package(task) or looks_like_ship(task):
        return False
    if looks_like_refactor(task) and not re.search(r"\breview\b", task, re.I):
        return False
    return bool(_REVIEW.search(task.lower()))


_BUG = re.compile(r"\b(fix|bug|nameerror|crash|defect)\b", re.I)


# An intent decided for this exact task by the fitted model, when the
# agent layer chose to ask it. Empty in every test and in every run that
# did not opt in, so the regular expressions below answer as they always
# have. Keyed by the task text because the twelve places that ask
# `looks_like_bugfix` hold the text, not the run.
_DECIDED: dict[str, str] = {}


def set_decided_intent(task: str, intent: str | None) -> None:
    """Record, or with None forget, the decided intent of a task."""
    key = task.strip()
    if intent is None:
        _DECIDED.pop(key, None)
    else:
        _DECIDED[key] = intent


def decided_intent(task: str) -> str | None:
    return _DECIDED.get(task.strip())


def looks_like_bugfix(task: str) -> bool:
    """A concrete fix that is not a rename, package, review, or ship.

    If the fitted model has decided this task, its answer wins: measured
    on phrasings people actually write it was right 86% of the time
    against this regex's 53%. Otherwise the regex, unchanged.
    """
    decided = decided_intent(task)
    if decided is not None:
        return decided == "bugfix"
    if looks_like_question(task):
        return False
    if (
        looks_like_new_package(task)
        or looks_like_fix_smell(task)
        or looks_like_ship(task)
        or looks_like_review(task)
        or looks_like_refactor(task)
    ):
        return False
    return bool(_BUG.search(task))


_SCRIPT = re.compile(
    r"\b(script|cli|argparse|argv|command[ -]line|__main__)\b", re.I
)
_HTTP = re.compile(
    r"\b(http api|rest api|fetch json|urllib|call the api|"
    r"get json|post json|\bcurl\b|http get|http post|"
    # A job that names a url and json is an HTTP call however it is worded.
    r"gets? an? url|download the json|read json from|from a url)\b",
    re.I,
)
_ANALYTICS = re.compile(
    r"\b(analytics|group by|groupby|tally|histogram|counter|csv)\b", re.I
)
_ALGO = re.compile(
    r"\b(algorithm|binary search|linked list|hash map|two pointers?|"
    r"breadth.first|depth.first|\bbfs\b|\bdfs\b|quicksort|mergesort|"
    r"implement (a |an )?(stack|queue|heap))\b",
    re.I,
)
_PLATFORM = re.compile(
    r"\b("
    r"pathlib|file.?system|cross.?platform|platform engineer|"
    r"path helper|os\.path|USERPROFILE|ntpath|"
    r"venv|virtual.?env|python\.exe|bin/python|"
    r"Path\.home|tempfile|line.?ending"
    r")\b",
    re.I,
)
_OPS = re.compile(
    r"\b("
    r"devops|dev.?ops|\bci\b|continuous integration|"
    r"workflow|pipeline|ci workflow"
    r")\b",
    re.I,
)


def _without_paths(task: str) -> str:
    """Drop file paths so `tests/cli/foo.py` is not a CLI-script job."""
    text = re.sub(r"\b[\w.-]+(?:/[\w.-]+)+\b", " ", task)
    return re.sub(r"\S+\.py\b", " ", text)


def looks_like_script(task: str) -> bool:
    if looks_like_question(task) or looks_like_new_package(task) or looks_like_ship(task):
        return False
    return bool(_SCRIPT.search(_without_paths(task)))


def looks_like_http_client(task: str) -> bool:
    if looks_like_question(task) or looks_like_new_package(task) or looks_like_ship(task):
        return False
    return mentions_http(task)


def looks_like_analytics(task: str) -> bool:
    if looks_like_question(task) or looks_like_new_package(task) or looks_like_ship(task):
        return False
    return bool(_ANALYTICS.search(task))


def looks_like_algorithm(task: str) -> bool:
    if looks_like_question(task) or looks_like_new_package(task) or looks_like_ship(task):
        return False
    return bool(_ALGO.search(task))


def looks_like_platform(task: str) -> bool:
    """Path / venv / OS-layout work. Small files, many platforms."""
    if looks_like_question(task) or looks_like_new_package(task) or looks_like_ship(task):
        return False
    if looks_like_ops(task):
        return False
    return bool(_PLATFORM.search(task))


def looks_like_ops(task: str) -> bool:
    """CI / workflow YAML. Not a function add, not a path helper."""
    if looks_like_question(task) or looks_like_new_package(task) or looks_like_ship(task):
        return False
    if looks_like_write_tests(task):
        return False
    return bool(_OPS.search(task))


def looks_like_everyday_code(task: str) -> bool:
    """Simple script, HTTP client, tally, algorithm, path helper, or CI YAML."""
    return (
        looks_like_script(task)
        or looks_like_http_client(task)
        or looks_like_analytics(task)
        or looks_like_algorithm(task)
        or looks_like_platform(task)
        or looks_like_ops(task)
    )


def everyday_skill_name(task: str) -> str:
    """The kit skill for a script / HTTP / tally / algorithm / path / CI task."""
    if looks_like_ops(task):
        return "write-workflow"
    if looks_like_platform(task):
        return "write-paths"
    if looks_like_http_client(task):
        return "call-http"
    if looks_like_analytics(task):
        return "analyze-data"
    if looks_like_algorithm(task):
        return "write-algorithm"
    if looks_like_script(task):
        return "write-script"
    return ""


_EVERYDAY_PATH = {
    "write-script": "pkg/weekday_name.py",
    "call-http": "pkg/fetch_json.py",
    "analyze-data": "pkg/tally.py",
    "write-algorithm": "pkg/index_of.py",
    "write-paths": "pkg/paths.py",
    "write-workflow": ".github/workflows/tests.yml",
}


def everyday_example_path(task: str) -> str:
    """The Path: the skill wants the 8B to copy. Keep in sync with SKILL.md."""
    return _EVERYDAY_PATH.get(everyday_skill_name(task), "pkg/<noun>.py")


_WRITE_TESTS = re.compile(r"\bwrite tests?\b|\badd tests?\b|\bunit tests?\b", re.I)
_COVERED = re.compile(
    r"\b(?:for|cover)\s+(?:the\s+)?"
    r"([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\b"
)
_COVERED_SKIP = frozenset(
    {
        # Pronouns are not function names. "…and a unit test for it" read as
        # "cover the function `it`", so a task asking to create a function
        # was handled as a request to test one that already exists.
        "everything",
        "file",
        "it",
        "module",
        "some",
        "that",
        "them",
        "these",
        "this",
        "those",
        "test",
        "tests",
        "unit",
    }
)


def looks_like_write_tests(task: str) -> bool:
    """Cover an existing function. Not “add X and a test” (that is add-feature)."""
    if looks_like_question(task) or looks_like_new_package(task) or looks_like_ship(task):
        return False
    if not _WRITE_TESTS.search(task):
        return False
    # "add multiply and a unit test" starts with add. "write tests for X" covers X.
    if _ADD_START.search(task.strip().lower()) and not covered_symbol(task):
        return False
    return True


def covered_symbol(task: str) -> str:
    """`write tests for apply_discount` → apply_discount.

    Also `OrderService`, `OrdersController.handle`.
    """
    match = _COVERED.search(task)
    if not match:
        return ""
    name = match.group(1)
    return "" if name.lower() in _COVERED_SKIP else name


def looks_like_add_feature(task: str) -> bool:
    text = task.strip().lower()
    if looks_like_question(text):
        return False
    if looks_like_write_tests(task):
        return False
    if looks_like_ops(task) or looks_like_platform(task):
        return False
    if (
        looks_like_new_package(text)
        or looks_like_fix_smell(text)
        or looks_like_ship(text)
        or looks_like_review(text)
        or looks_like_refactor(text)
    ):
        return False
    return bool(_ADD_START.search(text)) or looks_like_everyday_code(task)


def rename_pair(task: str) -> tuple[str, str]:
    """`rename calc to total_price` -> ("calc", "total_price")."""
    match = _RENAME.search(task)
    return (match.group(1), match.group(2)) if match else ("", "")


_SMELL_SKIP = frozenset(
    {
        "and",
        "clean",
        "cleanup",
        "code",
        "for",
        "human",
        "into",
        "name",
        "names",
        "readable",
        "rename",
        "smell",
        "that",
        "the",
        "this",
        "with",
    }
)


def smell_symbol(task: str) -> str:
    """The name a rename task is about: `rename calc to x` -> "calc"."""
    old, _new = rename_pair(task)
    if old:
        return old
    names = re.findall(r"\b([a-z_][a-z0-9_]{2,})\b", task.lower())
    hits = [name for name in names if name not in _SMELL_SKIP]
    return hits[-1] if hits else ""


def rename_target(task: str) -> str:
    """The name a rename task wants: `rename calc to x` -> "x"."""
    return rename_pair(task)[1]


_REVIEW_CODE = re.compile(
    r"\b(review|check|find bugs?|find errors?|defects?|audit|"
    r"code smells?)\b"
)


def looks_like_review_code(task: str) -> bool:
    """True when the task asks for problems to be reported, not fixed."""
    text = task.strip().lower()
    if looks_like_new_package(text) or looks_like_ship(text):
        return False
    if looks_like_add_feature(text) or looks_like_fix_smell(text):
        return False
    if looks_like_write_tests(text):
        return False
    return bool(_REVIEW_CODE.search(text))


_IDENTIFIER = re.compile(r"[A-Za-z_]\w*_\w+|\w+\s*\(|\S+\.py\b|\b[A-Za-z]\w*/\S+")


def names_something_concrete(task: str) -> bool:
    """True when the task names a file, a call, or a snake_case identifier.

    `question_symbol` will return any five-letter word, including ordinary
    English like "clean", so it cannot be used on its own to decide whether
    the agent has been told what to work on.
    """
    return bool(_IDENTIFIER.search(task))


def looks_unclear(task: str) -> bool:
    """True when the task is short and names nothing the agent can search for.

    A task like "clean this up" gives the agent no file and no symbol, so
    asking one question is better than guessing which file to change.
    """
    text = task.strip()
    if looks_like_question(text) or looks_like_ship(text):
        return False
    if names_something_concrete(text):
        return False
    # If the kind of work is recognised, the agent has a skill and a first
    # action for it, so a short task is still workable.
    known = (
        looks_like_add_feature,
        looks_like_everyday_code,
        looks_like_fix_smell,
        looks_like_new_package,
        looks_like_review_code,
        looks_like_design_loop,
        looks_like_bugfix,
    )
    if any(check(text) for check in known):
        return False
    return len(text.split()) <= 6


_TASK_PATH = re.compile(r"[\w./\\-]+\.(?:py|pyi|md)\b")


def task_paths(task: str) -> tuple[str, ...]:
    """File paths named in the task, with forward slashes, in order.

    A task that says "in src/harness/model/engine.py ..." has already told
    the agent which file to open. Searching for a word out of that path
    instead finds every file in the project.
    """
    seen: list[str] = []
    for hit in _TASK_PATH.findall(task):
        cleaned = hit.replace("\\", "/").strip("./,;:()[]'\"")
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return tuple(seen)


def named_project_file(task: str, project) -> str:
    """The one file the task names that exists in the project, or "".

    Empty when the task names none, or names more than one, because then
    there is nothing unambiguous to act on.
    """
    from pathlib import Path as _Path

    root = _Path(project).resolve()
    found = [rel for rel in task_paths(task) if (root / rel).is_file()]
    return found[0] if len(found) == 1 else ""


_WALK_FILES = re.compile(
    r"\b(under|inside|recursively|every file|all files|folder|directory|"
    r"file size|newest|oldest)\b"
)
_ARCHIVE = re.compile(r"\b(zip|unzip|tar|archive|compress|extract)\b")
_COMPARE = re.compile(
    r"\b(compare|diff|differ|different|changed|missing from|not in)\b"
)


def looks_like_walk_files(task: str) -> bool:
    """True when the job is to reach files under a folder, not one known path."""
    text = task.strip().lower()
    if looks_like_question(text) or looks_like_ship(text):
        return False
    return bool(_WALK_FILES.search(text))


def looks_like_archive(task: str) -> bool:
    text = task.strip().lower()
    if looks_like_question(text) or looks_like_ship(text):
        return False
    return bool(_ARCHIVE.search(text))


def looks_like_compare(task: str) -> bool:
    text = task.strip().lower()
    if looks_like_question(text) or looks_like_ship(text):
        return False
    return bool(_COMPARE.search(text))

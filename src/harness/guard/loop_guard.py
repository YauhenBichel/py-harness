"""Reject an action that has already been run with the same arguments.

A model that is unsure what to do next will often repeat its last search.
The tool returns the same output, the model is no better informed, and the
step budget is spent.

Read-only actions are keyed by their arguments. Patches are keyed by their
destination and exact Find, Replace, and Append body so the same boilerplate
can legitimately be applied to more than one file. Running the tests again
after a change remains progress and is never rejected here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

EXPLORE = frozenset({"glob", "grep", "read", "map", "locate", "plan", "skill"})
_NEXT = {
    "grep": "Action: read Path: one file from those hits.",
    "glob": "Action: read Path: one file from that list.",
    "map": "Action: grep Query: a symbol from the task.",
    "locate": "Action: read Path: the file it named, or Action: done.",
    "read": "Action: done with the answer, or Action: patch with a fix.",
    "plan": "Take the first explore action now.",
    "skill": "Copy the Action: block from the skill.",
}


def turn_key(turn) -> tuple[str, ...]:
    return (
        turn.action,
        turn.path.strip(),
        turn.query.strip(),
        turn.pattern.strip(),
        turn.scope.strip(),
        turn.name.strip(),
    )


def patch_key(turn) -> tuple[str, ...] | None:
    """The destination and exact mutation a patch proposes."""
    if turn.action != "patch":
        return None
    body = tuple(
        getattr(turn, field, "") for field in ("find", "replace", "append")
    )
    if not any(body):
        return None
    return ("patch", turn.path.strip(), *body)


@dataclass
class LoopGuard:
    """Remembers explore actions and patch bodies already seen in this run."""

    seen: dict[tuple[str, ...], str] = field(default_factory=dict)

    def remember_patch_result(self, turn, result: str) -> None:
        """Record whether a previously accepted patch was applied or refused."""
        patch = patch_key(turn)
        if patch is not None and patch in self.seen:
            self.seen[patch] = result

    def check(self, turn) -> str:
        if turn is None:
            return ""
        patch = patch_key(turn)
        if patch is not None:
            if result := self.seen.get(patch):
                return (
                    f"already proposed that exact patch for this path. It was {result}; "
                    "repeating it will not help. Read the "
                    "earlier result and take a different action."
                )
            self.seen[patch] = "proposed"
            return ""
        if turn.action not in EXPLORE:
            return ""
        key = turn_key(turn)
        if key in self.seen:
            hint = _NEXT.get(turn.action, "Take a different action.")
            detail = turn.path or turn.query or turn.pattern or turn.name
            return (
                f"already ran that exact {turn.action}"
                + (f" ({detail})" if detail else "")
                + f". The result has not changed. {hint}"
            )
        self.seen[key] = "ran"
        return ""

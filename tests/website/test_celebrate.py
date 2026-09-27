"""The merge comment runs on `pull_request_target`. That is the risk.

The celebration itself moved into `YauhenBichel/merge-cheer`, which
bundles its own images. What stays this repository's problem is the
trigger it hands that action: `pull_request_target` runs with this
repository's token, on a pull request opened by anyone.

These checks used to describe the inline implementation — a tag picked
from the title, a file in `.github/celebrate/`, a pinned
`actions/github-script`. That implementation is gone. The properties it
had to hold have not changed, so they are asserted against the workflow
that exists now.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "celebrate-merge.yml"


class CelebrateWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.body = WORKFLOW.read_text(encoding="utf-8")

    def test_every_action_is_pinned_to_a_commit(self) -> None:
        """`pull-requests: write` plus a mutable tag is a silent
        privilege change: a tag can be moved, a commit cannot."""
        used = re.findall(r"uses:\s*(\S+)", self.body)
        self.assertTrue(used, "the workflow runs no action at all")
        unpinned = [ref for ref in used if not re.search(r"@[0-9a-f]{40}$", ref)]
        self.assertEqual(unpinned, [], f"not pinned to a commit: {unpinned}")

    def test_the_pull_request_code_is_never_checked_out(self) -> None:
        """pull_request_target carries this repository's secrets, so the
        fork's code must never run beside them."""
        self.assertNotIn("actions/checkout", self.body)

    def test_no_untrusted_field_reaches_a_shell(self) -> None:
        """A title, branch name or body is attacker-controlled on a fork
        pull request. Interpolating one into `run:` is a shell injection;
        the safe shape is an `env:` binding the script reads."""
        for step in self.body.split("- ")[1:]:
            if "run:" not in step:
                continue
            shell = step.split("run:", 1)[1]
            for field in ("title", "body", "head_ref", "login"):
                self.assertNotIn(
                    "${{ github.event.pull_request." + field,
                    shell,
                    f"pull_request.{field} is interpolated into a shell",
                )

    def test_it_only_fires_on_a_merged_human_pull_request(self) -> None:
        self.assertIn("github.event.pull_request.merged", self.body)
        self.assertIn("!= 'Bot'", self.body)

    def test_the_workflow_does_not_name_a_branch(self) -> None:
        """Nothing here should stop working if the default branch is
        renamed."""
        self.assertNotRegex(self.body, r"(?<![\w-])(main|master)(?![\w-])")

    def test_it_asks_for_no_more_permission_than_it_needs(self) -> None:
        """A comment needs `pull-requests: write` and nothing else."""
        block = self.body.split("permissions:", 1)[1].split("jobs:", 1)[0]
        granted = dict(re.findall(r"(\w[\w-]*):\s*(\w+)", block))
        self.assertEqual(granted, {"pull-requests": "write"}, granted)

    def test_the_images_are_not_carried_here_any_more(self) -> None:
        """They moved into the action, which bundles its own. Six GIFs
        left behind and referenced by nothing is dead weight in a clone."""
        self.assertFalse(
            (ROOT / ".github" / "celebrate").exists(),
            "the action ships its own images; these are unreferenced",
        )


if __name__ == "__main__":
    unittest.main()

"""README contributor list is a workflow marker, not a hardcoded table."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "README.md"
WORKFLOW = ROOT / ".github" / "workflows" / "contributors.yml"
CELEBRATE = ROOT / ".github" / "workflows" / "celebrate-merge.yml"

_START = "<!-- readme: contributors,bots/- -start -->"
_END = "<!-- readme: contributors,bots/- -end -->"


class ReadmeContributorsTest(unittest.TestCase):
    def test_readme_shows_the_pip_install(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("pip install py-harness-cli", text)
        self.assertIn("docs/media/pip-demo.gif", text)
        self.assertIn("asciinema play docs/media/pip-demo.cast", text)
        self.assertIn("pypi.org/project/py-harness-cli", text)
        self.assertNotIn("pip install py-harness\n", text)

    def test_readme_shows_the_vscode_recording(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("docs/media/vscode-demo.gif", text)
        self.assertIn("asciinema play docs/media/vscode-demo.cast", text)
        self.assertIn("py-harness editors vscode", text)

    def test_readme_shows_the_cursor_recording(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("docs/media/cursor-demo.gif", text)
        self.assertIn("asciinema play docs/media/cursor-demo.cast", text)
        self.assertIn("py-harness editors cursor --allow-writes", text)

    def test_readme_stays_short(self) -> None:
        """The GitHub front page was a second site. Keep the how-to first."""
        text = README.read_text(encoding="utf-8")
        body = text.split(_START, 1)[0]
        self.assertLess(len(body.splitlines()), 120, len(body.splitlines()))
        self.assertIn("source .venv/bin/activate", body)
        self.assertIn("cd demo/orders", body)
        self.assertIn("py-harness/tree/", body)

    def test_markers_not_hardcoded_table(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn(_START, text)
        self.assertIn(_END, text)
        self.assertEqual(text.count(_START), 1)
        self.assertLess(text.index(_START), text.index(_END))
        self.assertNotIn("contrib.rocks", text)
        self.assertNotIn("| Contributor | Commits |", text)

    def test_workflow_reads_github_api(self) -> None:
        """The list is generated, and no contributor is named in the file.

        This used to require `fill_contributors.py` by name, which said
        which generator rather than that there is one, and went red when
        the step became a reusable action.

        The no-hardcoded-names half is the part worth keeping, and it
        needs care now: the generator is `YauhenBichel/readme-contributors`,
        so the owner's login appears legitimately. Every other name is
        still banned, and his is allowed only as part of that reference.
        """
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("github-actions[bot]", text)
        self.assertNotIn("akhilmhdh/contributors-readme-action", text)
        for login in ("ItzSaurav", "svkzn", "Aditya-233", "xianjianlf2", "kkkhs"):
            self.assertNotIn(login, text, f"{login} is hardcoded in the workflow")
        self.assertNotIn(
            "YauhenBichel",
            text.replace("YauhenBichel/readme-contributors", ""),
            "the owner is named outside the action reference",
        )

    def test_the_generator_is_pinned_to_a_commit(self) -> None:
        """A step with `contents: write` must not follow a moving tag."""
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertRegex(text, r"uses: YauhenBichel/readme-contributors@[0-9a-f]{40}")
        self.assertIn("format: html", text)

    def test_checkout_is_pinned_to_a_commit(self) -> None:
        """contents: write plus persist-credentials must not follow a moving tag."""
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertRegex(text, r"uses: actions/checkout@[0-9a-f]{40}")

    @staticmethod
    def _commands(text: str) -> str:
        """The workflow minus its comments, which tell the history in the
        very words the negative checks forbid."""
        return "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))

    def test_nothing_runs_on_a_pull_request(self) -> None:
        """A wall drawn on a pull request branch is stale by the time it merges.

        A fork's pull request cannot run the job at all: its branch lives on
        the fork, so the checkout died on `git fetch origin
        +refs/heads/patch-2*` and showed a failing check that had nothing to
        do with the change. A same-repository branch runs it, then lands a
        wall computed before whatever merged ahead of it. MoleCare/molecare-mcp
        lost a contributor exactly that way, in 44 seconds.
        """
        on_block = WORKFLOW.read_text(encoding="utf-8").split("\npermissions:")[0]
        self.assertNotRegex(self._commands(on_block), r"(?m)^\s*pull_request(_target)?:")
        self.assertRegex(on_block, r"(?m)^  push:\n    branches:\n      - main")

    def test_a_stale_list_on_main_is_pushed_to_main(self) -> None:
        """No separate pull request: the refresh lands on main itself.

        main is protected. The job used to force-push to docs/contributors
        and stop, and nothing merged that branch, then it opened a pull
        request for it. It now pushes to main through a write deploy key,
        the one bypass actor on the ruleset besides the owner.
        """
        text = WORKFLOW.read_text(encoding="utf-8")
        commands = self._commands(text)
        self.assertIn("ref: main", commands)
        self.assertIn("ssh-key: ${{ secrets.CONTRIBUTORS_DEPLOY_KEY }}", commands)
        self.assertIn("git push origin HEAD:main", commands)
        self.assertNotIn("gh pr create", commands)
        self.assertNotIn("docs/contributors", commands)
        self.assertNotIn("pull-requests: write", commands)
        # A deploy-key push starts workflows; a README-only refresh must not.
        self.assertIn("[skip ci]", commands)

    def test_a_fork_merge_reaches_the_wall(self) -> None:
        """The job runs on main after every merge, forks included.

        After a fork merge the generated list used to be discarded, because
        both the PR-head push and the default-branch push were skipped.
        """
        commands = self._commands(WORKFLOW.read_text(encoding="utf-8"))
        self.assertNotIn("head.repo.full_name", commands)
        self.assertNotIn("github.event.repository.default_branch", commands)
        self.assertIn("workflow_dispatch", commands)
        self.assertIn("schedule", commands)

    def test_a_removal_waits_for_a_person(self) -> None:
        """A name should never leave the wall; if one would, the API
        most likely answered short.

        That is why a person used to read the refresh. With no pull request
        left, an automatic run that would remove a name pushes nothing and
        says so, and only a run started by hand pushes the removal.
        """
        commands = self._commands(WORKFLOW.read_text(encoding="utf-8"))
        self.assertIn("REMOVED=$(git diff --cached -U0 -- README.md", commands)
        self.assertIn("STARTED_BY_HAND: ${{ github.event_name == 'workflow_dispatch' }}", commands)
        guard = commands.index('if [ "$REMOVED" -gt 0 ] && [ "$STARTED_BY_HAND" != "true" ]; then')
        self.assertIn("::warning::", commands[guard:guard + 400])
        self.assertLess(guard, commands.index("git commit"), "the guard must come before the commit")

    def test_celebrate_merge_hardcodes_no_gif(self) -> None:
        """The celebration moved into `YauhenBichel/merge-cheer`, which
        chooses the image and bundles its own fallbacks.

        This checked the inline implementation — a Giphy call, a rating,
        a folder of owned GIFs. What still has to hold here is that no
        specific image is nailed into the workflow, so a broken or
        moved URL cannot reach a public comment.
        """
        text = CELEBRATE.read_text(encoding="utf-8")
        self.assertIn("pull_request_target", text)
        self.assertNotIn("media.giphy.com/media/", text)
        self.assertNotRegex(text, r"https?://\S+\.gif")
        self.assertNotIn(".github/celebrate/", text)
        # The images, and the NOTICE recording where they came from, moved
        # with them: `YauhenBichel/merge-cheer` carries its own.
        self.assertFalse((ROOT / ".github" / "celebrate").exists())

    def test_contributor_markers_are_not_an_empty_pair(self) -> None:
        """Each person is a separate icon that links to their profile.

        A single `<img src="contributors.svg">` is one picture: GitHub
        cannot attach a URL to each face. The wall must be one `<a>`
        per person, wrapping that person's avatar.
        """
        text = README.read_text(encoding="utf-8")
        start = text.index(_START) + len(_START)
        end = text.index(_END)
        body = text[start:end]
        self.assertNotIn("contributors.svg", body)
        self.assertNotIn("<table>", body)
        icons = re.findall(
            r'<a href="https://github.com/([A-Za-z0-9-]+)"[^>]*>\s*<img ',
            body,
        )
        self.assertGreaterEqual(len(icons), 2, body)
        self.assertEqual(len(icons), len(set(icons)), body)
        for login in icons:
            # Where the icon is hosted is the generator's business — it
            # has been the avatar CDN and is now a generated SVG under
            # `.github/faces/`. What must hold is that the icon beside a
            # profile link belongs to that person.
            self.assertRegex(
                body,
                rf'<a href="https://github\.com/{re.escape(login)}"[^>]*>\s*'
                rf'<img src="[^"]*{re.escape(login)}[^"]*"',
                f"{login}'s icon does not carry their name",
            )

    def test_fill_script_renders_a_table_without_bots(self) -> None:
        import importlib.util

        path = ROOT / ".github" / "scripts" / "fill_contributors.py"
        spec = importlib.util.spec_from_file_location("fill_contributors", path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        html = module.render_table(
            [{"login": "alice", "name": "Alice Example"}]
        )
        self.assertIn("github.com/alice", html)
        self.assertIn("Alice Example", html)
        self.assertIn("<table>", html)

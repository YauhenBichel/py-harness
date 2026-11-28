import unittest
from pathlib import Path

from harness.skillkit.catalog import list_skills, pick_skills
from harness.skillkit.refuse_change import refuse_shell_fetch

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "eval" / "fixtures" / "script_pkg"


class ScriptFixtureTest(unittest.TestCase):
    def test_fixture_leaves_the_script_to_be_created(self) -> None:
        for rel in ("pkg/__init__.py", "tests/__init__.py"):
            with self.subTest(path=rel):
                self.assertTrue((FIXTURE / rel).is_file())
        self.assertFalse((FIXTURE / "pkg" / "weekday_name.py").exists())

    def test_weekday_task_selects_script_and_tests(self) -> None:
        picked = pick_skills("write a weekday script from argv", list_skills(ROOT))
        self.assertEqual(
            [skill.name for skill in picked], ["write-script", "write-tests"]
        )

    def test_shell_fetch_drafts_are_refused(self) -> None:
        for draft in (
            'import subprocess\nsubprocess.run(["curl", source], check=True)\n',
            'import os\nos.system("curl " + source)\n',
        ):
            with self.subTest(draft=draft):
                self.assertIn("urllib", refuse_shell_fetch("pkg/weekday_name.py", draft))


if __name__ == "__main__":
    unittest.main()

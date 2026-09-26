"""The fitted decision is used only when asked for, and never leaks.

`AgentOptions.decide` defaults to "regex", which is what every number
this project has published was measured with. With "model", the intent
is decided once at the start of the run and registered against the task
text, so the twelve places that ask `looks_like_bugfix` see it without
being changed. When the run ends the registration is forgotten, because
a benchmark arm measured with the regex must not inherit the previous
arm's decision.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from harness import task as T  # noqa: E402
from harness.agent.options import AgentOptions  # noqa: E402


class TheRegistryTest(unittest.TestCase):
    def tearDown(self) -> None:
        T.set_decided_intent("the totals come out one too low", None)

    def test_the_regex_answers_when_nothing_was_decided(self) -> None:
        self.assertFalse(T.looks_like_bugfix("the totals come out one too low"))

    def test_a_decision_overrides_the_regex(self) -> None:
        T.set_decided_intent("the totals come out one too low", "bugfix")
        self.assertTrue(T.looks_like_bugfix("the totals come out one too low"))

    def test_a_decision_can_say_no_where_the_regex_said_yes(self) -> None:
        task = "document how we fix flaky tests in CONTRIBUTING"
        self.assertTrue(T.looks_like_bugfix(task), "the regex fires on 'fix'")
        T.set_decided_intent(task, "docs")
        try:
            self.assertFalse(T.looks_like_bugfix(task))
        finally:
            T.set_decided_intent(task, None)

    def test_forgetting_restores_the_regex(self) -> None:
        T.set_decided_intent("the totals come out one too low", "bugfix")
        T.set_decided_intent("the totals come out one too low", None)
        self.assertFalse(T.looks_like_bugfix("the totals come out one too low"))

    def test_whitespace_does_not_split_the_key(self) -> None:
        T.set_decided_intent("  the totals come out one too low ", "bugfix")
        self.assertEqual(T.decided_intent("the totals come out one too low"), "bugfix")


class TheSwitchTest(unittest.TestCase):
    def test_the_default_is_the_regex(self) -> None:
        self.assertEqual(AgentOptions(project=Path(".")).decide, "regex")

    def test_the_regex_arm_never_calls_the_model(self) -> None:
        """Asserted on the call, not on the outcome. The first version
        checked only that nothing was registered — which is also what
        happens when the model is *called* and no embedder answers, so
        it passed with the guard removed whenever the host was busy."""
        from unittest import mock

        from harness.agent.loop import Agent
        from harness.decide.intent import Decision

        options = AgentOptions(project=Path("."), task="the totals come out one too low")
        with mock.patch(
            "harness.decide.intent.intent_of",
            return_value=Decision("bugfix", 1.5, "platform_ops"),
        ) as asked:
            Agent(options)._decide_intent(options)
        self.assertEqual(asked.call_count, 0, "the regex arm asked the model")
        self.assertIsNone(T.decided_intent("the totals come out one too low"))

    def test_the_model_arm_registers_a_decision_and_run_forgets_it(self) -> None:
        from unittest import mock

        from harness.agent.loop import Agent
        from harness.decide.intent import Decision

        task = "the totals come out one too low"
        options = AgentOptions(project=Path("."), task=task, decide="model")
        agent = Agent(options)
        with mock.patch(
            "harness.decide.intent.intent_of",
            return_value=Decision("bugfix", 1.5, "platform_ops"),
        ):
            agent._decide_intent(options)
            self.assertEqual(T.decided_intent(task), "bugfix")
        T.set_decided_intent(task, None)

    def test_run_forgets_the_decision_however_it_ends(self) -> None:
        """The forgetting lives in run()'s finally, so it has to be
        reached through run(), not through _decide_intent."""
        from unittest import mock

        from harness.agent.loop import Agent
        from harness.agent.options import AgentResult
        from harness.decide.intent import Decision

        task = "the totals come out one too low"
        options = AgentOptions(project=Path("."), task=task, decide="model")
        ended = AgentResult(ok=True, summary="done", stopped="done")
        with mock.patch(
            "harness.decide.intent.intent_of",
            return_value=Decision("bugfix", 1.5, "platform_ops"),
        ), mock.patch.object(Agent, "_after_deciding", return_value=ended) as body:
            Agent(options).run()
        self.assertEqual(body.call_count, 1)
        self.assertIsNone(T.decided_intent(task), "the decision leaked past the run")

    def test_run_forgets_the_decision_even_when_the_body_raises(self) -> None:
        from unittest import mock

        from harness.agent.loop import Agent
        from harness.decide.intent import Decision

        task = "the totals come out one too low"
        options = AgentOptions(project=Path("."), task=task, decide="model")
        with mock.patch(
            "harness.decide.intent.intent_of",
            return_value=Decision("bugfix", 1.5, "platform_ops"),
        ), mock.patch.object(Agent, "_after_deciding", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                Agent(options).run()
        self.assertIsNone(T.decided_intent(task))

    def test_no_embedding_model_means_the_regex_stays(self) -> None:
        from unittest import mock

        from harness.agent.loop import Agent

        task = "the totals come out one too low"
        options = AgentOptions(project=Path("."), task=task, decide="model")
        with mock.patch("harness.decide.intent.intent_of", return_value=None):
            Agent(options)._decide_intent(options)
        self.assertIsNone(T.decided_intent(task))
        self.assertFalse(T.looks_like_bugfix(task))


if __name__ == "__main__":
    unittest.main()

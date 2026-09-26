"""The intent decision model, without a network.

Every test here hands `intent_of` its own embedder, so nothing depends
on an embedding model being installed. The one thing that must hold on
every machine is the fallback: when embedding is impossible, the answer
is None and the caller keeps the regex.
"""

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from harness.decide import intent as I  # noqa: E402


def _unit_weights(name: str) -> list[float]:
    """The normalised weight vector of one intent's head.

    Scoring that vector should rank its own intent first: it is the
    direction the head was fitted to point at.
    """
    head = I._weights()["intents"][name]
    return I._normalise(head["weights"])


class TheWeightsTest(unittest.TestCase):
    def test_twelve_intents_are_shipped(self) -> None:
        self.assertEqual(len(I.intents()), 12)
        self.assertIn("bugfix", I.intents())

    def test_the_dimension_matches_the_embedding_model(self) -> None:
        spec = I._weights()
        self.assertEqual(spec["dims"], 1024)
        for head in spec["intents"].values():
            self.assertEqual(len(head["weights"]), 1024)

    def test_a_wrong_dimension_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            I.score([0.1] * 10)


class DecidingTest(unittest.TestCase):
    def test_each_head_ranks_its_own_direction_first(self) -> None:
        for name in I.intents():
            with self.subTest(name):
                self.assertEqual(I.decide(_unit_weights(name)).intent, name)

    def test_the_margin_is_the_gap_to_the_runner_up(self) -> None:
        decision = I.decide(_unit_weights("bugfix"))
        ranked = sorted(I.score(_unit_weights("bugfix")).values(), reverse=True)
        self.assertAlmostEqual(decision.margin, ranked[0] - ranked[1], places=6)
        self.assertNotEqual(decision.runner_up, decision.intent)

    def test_scoring_normalises_so_scale_does_not_matter(self) -> None:
        small = I.decide(_unit_weights("ship"))
        big = I.decide([v * 1000 for v in _unit_weights("ship")])
        self.assertEqual(small.intent, big.intent)
        self.assertAlmostEqual(small.margin, big.margin, places=6)


class KeepingTheRegexWhenItCannotDecideTest(unittest.TestCase):
    def test_no_embedder_answer_means_none(self) -> None:
        self.assertIsNone(I.intent_of("fix the bug", embed=lambda _t: None))

    def test_an_empty_task_is_not_sent_anywhere(self) -> None:
        called = []
        self.assertIsNone(I.intent_of("   ", embed=lambda t: called.append(t) or [0.0] * 1024))
        self.assertEqual(called, [])

    def test_nonsense_dimensions_mean_none_not_a_crash(self) -> None:
        self.assertIsNone(I.intent_of("fix the bug", embed=lambda _t: [0.5, 0.5]))

    def test_an_unreachable_host_means_none(self) -> None:
        self.assertIsNone(I.ollama_embed("fix the bug", host="http://127.0.0.1:9", timeout=1))

    def test_a_real_vector_yields_a_decision(self) -> None:
        got = I.intent_of("fix the bug", embed=lambda _t: _unit_weights("bugfix"))
        self.assertIsNotNone(got)
        self.assertEqual(got.intent, "bugfix")


if __name__ == "__main__":
    unittest.main()

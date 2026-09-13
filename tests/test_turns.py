"""Behavior tests for the HassMic per-turn lifecycle."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "custom_components/hassmic/turns.py"
SPEC = importlib.util.spec_from_file_location("hassmic_turns", MODULE_PATH)
assert SPEC and SPEC.loader
turns = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = turns
SPEC.loader.exec_module(turns)


class TurnLifecycleTest(unittest.TestCase):
    def test_stale_playback_acknowledgement_is_rejected(self) -> None:
        lifecycle = turns.TurnLifecycle()
        lifecycle.begin("turn-current")

        self.assertFalse(lifecycle.accepts("turn-old"))
        self.assertTrue(lifecycle.accepts("turn-current"))

    def test_playback_can_complete_once_for_the_active_turn(self) -> None:
        lifecycle = turns.TurnLifecycle()
        lifecycle.begin("turn-42")
        lifecycle.await_playback("turn-42")

        self.assertTrue(lifecycle.complete_playback("turn-42"))
        self.assertFalse(lifecycle.complete_playback("turn-42"))


if __name__ == "__main__":
    unittest.main()

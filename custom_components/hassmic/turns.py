"""Per-turn lifecycle guards for the HassMic Assist satellite."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TurnLifecycle:
    """Accept only events belonging to the currently active satellite turn."""

    active_turn_id: str | None = None
    awaiting_playback_turn_id: str | None = None

    def begin(self, turn_id: str) -> None:
        """Start a new turn and invalidate any prior playback acknowledgement."""
        if not turn_id:
            raise ValueError("turn_id is required")
        self.active_turn_id = turn_id
        self.awaiting_playback_turn_id = None

    def accepts(self, turn_id: str) -> bool:
        """Return whether an incoming event belongs to the active turn."""
        return bool(turn_id) and turn_id == self.active_turn_id

    def await_playback(self, turn_id: str) -> None:
        """Mark the active turn as waiting for its playback acknowledgement."""
        if not self.accepts(turn_id):
            raise ValueError("cannot await playback for an inactive turn")
        self.awaiting_playback_turn_id = turn_id

    def complete_playback(self, turn_id: str) -> bool:
        """Consume one valid playback acknowledgement for the active turn."""
        if turn_id != self.awaiting_playback_turn_id:
            return False
        self.awaiting_playback_turn_id = None
        return True

    def clear(self) -> None:
        """Discard state after disconnect, cancellation, or expiry."""
        self.active_turn_id = None
        self.awaiting_playback_turn_id = None

"""
State file management utilities for tests.

Provides helpers for managing langsmith_state.json during testing.
"""

import json
from pathlib import Path
from typing import Any, Optional


class StateManager:
    """Manage langsmith_state.json for tests"""

    def __init__(self, state_file: Path):
        self.state_file = Path(state_file)

    def load(self) -> dict:
        """
        Load state from file.

        Returns:
            State dictionary (empty dict if file doesn't exist)
        """
        if not self.state_file.exists():
            return {}

        try:
            return json.loads(self.state_file.read_text())
        except (json.JSONDecodeError, IOError):
            return {}

    def save(self, state: dict):
        """
        Save state to file.

        Args:
            state: State dictionary to save
        """
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2))

    def get_session_state(self, session_id: str) -> dict:
        """
        Get state for a specific session.

        Args:
            session_id: Session ID to look up

        Returns:
            Session state dictionary (empty dict if not found)
        """
        state = self.load()
        return state.get(session_id, {})

    def update_session(self, session_id: str, **kwargs):
        """
        Update session state with new values.

        Args:
            session_id: Session ID to update
            **kwargs: Key-value pairs to update in the session state
        """
        state = self.load()

        if session_id not in state:
            state[session_id] = {}

        state[session_id].update(kwargs)
        self.save(state)

    def set_session_state(self, session_id: str, session_state: dict):
        """
        Set complete session state (replaces existing).

        Args:
            session_id: Session ID
            session_state: New session state dictionary
        """
        state = self.load()
        state[session_id] = session_state
        self.save(state)

    def delete_session(self, session_id: str):
        """
        Delete a session from state.

        Args:
            session_id: Session ID to delete
        """
        state = self.load()
        if session_id in state:
            del state[session_id]
            self.save(state)

    def clear(self):
        """Clear all state (delete the file)."""
        if self.state_file.exists():
            self.state_file.unlink()

    def exists(self) -> bool:
        """
        Check if state file exists.

        Returns:
            True if file exists
        """
        return self.state_file.exists()

    def get_last_line(self, session_id: str) -> int:
        """
        Get the last processed line number for a session.

        Args:
            session_id: Session ID

        Returns:
            Last line number (0 if not found)
        """
        session_state = self.get_session_state(session_id)
        return session_state.get("last_line", 0)

    def get_turn_count(self, session_id: str) -> int:
        """
        Get the turn count for a session.

        Args:
            session_id: Session ID

        Returns:
            Turn count (0 if not found)
        """
        session_state = self.get_session_state(session_id)
        return session_state.get("turn_count", 0)

    def set_last_line(self, session_id: str, last_line: int):
        """
        Set the last processed line number for a session.

        Args:
            session_id: Session ID
            last_line: Line number
        """
        self.update_session(session_id, last_line=last_line)

    def set_turn_count(self, session_id: str, turn_count: int):
        """
        Set the turn count for a session.

        Args:
            session_id: Session ID
            turn_count: Number of turns
        """
        self.update_session(session_id, turn_count=turn_count)

    def list_sessions(self) -> list[str]:
        """
        Get list of all session IDs in state.

        Returns:
            List of session ID strings
        """
        state = self.load()
        return list(state.keys())

    def __repr__(self) -> str:
        return f"StateManager({self.state_file})"

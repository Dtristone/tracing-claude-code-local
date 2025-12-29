"""
Unit tests for state management functions from stop_hook.sh.

Tests:
- load_state() - Read langsmith_state.json
- save_state() - Write state file
"""

import json
import pytest


@pytest.mark.unit
class TestStateManagement:
    """Tests for load_state() and save_state() functions"""

    def test_load_state_returns_empty_for_missing_file(self, bash_executor, temp_state_file):
        """Test loading state when file doesn't exist"""
        # temp_state_file doesn't exist yet
        result = bash_executor.call_function("load_state")
        loaded = json.loads(result)
        assert loaded == {}

    def test_save_and_load_state(self, bash_executor, temp_state_file, state_manager):
        """Test round-trip state persistence"""
        state = {
            "session_123": {
                "last_line": 42,
                "turn_count": 5,
                "updated": "2025-01-01T00:00:00Z"
            }
        }

        # Save state using state_manager (creates the file)
        state_manager.save(state)

        # Load using bash function
        result = bash_executor.call_function("load_state")
        loaded = json.loads(result)

        assert loaded == state
        assert loaded["session_123"]["last_line"] == 42
        assert loaded["session_123"]["turn_count"] == 5

    def test_state_tracks_multiple_sessions(self, bash_executor, state_manager):
        """Test state management for multiple sessions"""
        state = {
            "session_1": {"last_line": 10, "turn_count": 1},
            "session_2": {"last_line": 20, "turn_count": 2}
        }

        state_manager.save(state)

        result = bash_executor.call_function("load_state")
        loaded = json.loads(result)

        assert "session_1" in loaded
        assert "session_2" in loaded
        assert loaded["session_1"]["last_line"] == 10
        assert loaded["session_2"]["last_line"] == 20

    def test_save_state_creates_directory(self, bash_executor, tmp_path):
        """Test that save_state creates parent directory if needed"""
        # Use a nested path that doesn't exist
        nested_state_file = tmp_path / "nested" / "dir" / "state.json"

        state = {"test": {"value": 123}}

        # Manually set STATE_FILE env var for this test
        import os
        old_state_file = os.environ.get("STATE_FILE")
        os.environ["STATE_FILE"] = str(nested_state_file)

        try:
            bash_executor.call_function("save_state", json.dumps(state))

            # Verify file was created
            assert nested_state_file.exists()

            # Verify content
            loaded_content = json.loads(nested_state_file.read_text())
            assert loaded_content == state
        finally:
            if old_state_file:
                os.environ["STATE_FILE"] = old_state_file

    def test_save_state_with_complex_data(self, bash_executor, state_manager):
        """Test saving complex state data"""
        state = {
            "session_abc": {
                "last_line": 100,
                "turn_count": 25,
                "updated": "2025-01-01T12:34:56Z",
                "metadata": {
                    "model": "claude-sonnet-4-5-20250929",
                    "total_tokens": 5000
                }
            }
        }

        state_manager.save(state)

        result = bash_executor.call_function("load_state")
        loaded = json.loads(result)

        assert loaded == state
        assert loaded["session_abc"]["metadata"]["model"] == "claude-sonnet-4-5-20250929"

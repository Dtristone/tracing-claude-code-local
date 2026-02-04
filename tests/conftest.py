"""
Pytest configuration and shared fixtures for stop_hook.sh tests.
"""

import uuid

import pytest

from tests.helpers.bash_runner import BashRunner
from tests.helpers.state_manager import StateManager


# =============================================================================
# Test Environment Fixtures
# =============================================================================

@pytest.fixture
def temp_state_file(tmp_path):
    """
    Provide an isolated state file for each test.

    Returns:
        Path to temporary state file
    """
    state_file = tmp_path / "langsmith_state.json"
    yield state_file
    # Cleanup happens automatically via tmp_path


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, temp_state_file, tmp_path):
    """
    Ensure each test has isolated environment variables.

    This fixture automatically applies to all tests.
    """
    # Override state file location
    monkeypatch.setenv("STATE_FILE", str(temp_state_file))

    # Override log file location
    log_file = tmp_path / "hook.log"
    monkeypatch.setenv("LOG_FILE", str(log_file))

    # Disable tracing during most tests (can be re-enabled per test)
    monkeypatch.setenv("TRACE_TO_LANGSMITH", "false")

    # Disable debug logging
    monkeypatch.setenv("CC_LANGSMITH_DEBUG", "false")

    # Set test project
    monkeypatch.setenv("CC_LANGSMITH_PROJECT", "cc-test")


# =============================================================================
# Helper Class Fixtures
# =============================================================================

@pytest.fixture
def bash_executor():
    """
    Provide BashRunner for executing bash functions in isolation.

    Returns:
        BashRunner instance
    """
    return BashRunner()  # Uses auto-detection


@pytest.fixture
def state_manager(temp_state_file):
    """
    Provide StateManager for managing test state files.

    Returns:
        StateManager instance with isolated state file
    """
    return StateManager(temp_state_file)


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_assistant_message():
    """
    Provide a sample assistant message with tool use.

    Returns:
        Dictionary with assistant message structure
    """
    return {
        "type": "assistant",
        "message": {
            "id": "msg_test123",
            "role": "assistant",
            "model": "claude-sonnet-4-5-20250929",
            "content": [
                {"type": "thinking", "thinking": "Let me analyze this..."},
                {"type": "text", "text": "Here's my response"},
                {
                    "type": "tool_use",
                    "id": "tool_test_abc",
                    "name": "Read",
                    "input": {"file_path": "/test/file.txt"}
                }
            ],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_read_input_tokens": 1000
            }
        },
        "timestamp": "2025-01-01T00:00:01Z"
    }


@pytest.fixture
def sample_tool_result():
    """
    Provide a sample tool result message.

    Returns:
        Dictionary with tool result structure
    """
    return {
        "type": "user",
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "tool_test_abc",
                "content": "File contents: hello world"
            }
        ],
        "timestamp": "2025-01-01T00:00:02Z"
    }


@pytest.fixture
def sample_streaming_parts():
    """
    Provide sample streaming assistant message parts (SSE simulation).

    Returns:
        List of message dictionaries with same ID
    """
    msg_id = "msg_stream_123"
    return [
        {
            "type": "assistant",
            "message": {
                "id": msg_id,
                "role": "assistant",
                "model": "claude-sonnet-4-5-20250929",
                "content": [{"type": "text", "text": "Hello "}],
                "usage": {"input_tokens": 10, "output_tokens": 2}
            },
            "timestamp": "2025-01-01T00:00:00.000Z"
        },
        {
            "type": "assistant",
            "message": {
                "id": msg_id,
                "role": "assistant",
                "model": "claude-sonnet-4-5-20250929",
                "content": [{"type": "text", "text": "world"}],
                "usage": {"input_tokens": 10, "output_tokens": 4}  # Cumulative
            },
            "timestamp": "2025-01-01T00:00:00.100Z"
        },
        {
            "type": "assistant",
            "message": {
                "id": msg_id,
                "role": "assistant",
                "model": "claude-sonnet-4-5-20250929",
                "content": [{"type": "text", "text": "!"}],
                "usage": {"input_tokens": 10, "output_tokens": 5}  # Cumulative
            },
            "timestamp": "2025-01-01T00:00:00.200Z"
        }
    ]


# =============================================================================
# Session ID Fixture
# =============================================================================

@pytest.fixture
def session_id():
    """
    Generate a unique session ID for each test.

    Returns:
        UUID string
    """
    return str(uuid.uuid4())


# =============================================================================
# Parametrize Helpers
# =============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test (no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test (requires API access)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow (takes >5 seconds)"
    )

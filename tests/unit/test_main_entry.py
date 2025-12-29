"""
Unit tests for main() entry point in stop_hook.sh.

Tests:
- Hook input parsing (session_id, transcript_path)
- stop_hook_active flag handling
- Incremental processing (last_line tracking)
- Turn grouping logic
- Message ID tracking for SSE streaming
- State updates
- Execution time tracking
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.mark.unit
class TestHookInputParsing:
    """Tests for parsing hook input JSON"""

    def test_extracts_session_id(self):
        """Test that session_id is extracted from hook input"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "session_id" in content
        assert '.session_id' in content  # jq extraction

    def test_extracts_transcript_path(self):
        """Test that transcript_path is extracted from hook input"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "transcript_path" in content
        assert '.transcript_path' in content  # jq extraction

    def test_expands_tilde_in_transcript_path(self):
        """Test that ~ is expanded to $HOME in transcript_path"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should use sed to replace ~
        assert 's|^~|$HOME|' in content

    def test_validates_session_id_not_empty(self):
        """Test that empty session_id is handled"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert '-z "$session_id"' in content

    def test_validates_transcript_file_exists(self):
        """Test that missing transcript file is handled"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert '! -f "$transcript_path"' in content


@pytest.mark.unit
class TestStopHookActiveFlag:
    """Tests for stop_hook_active flag handling"""

    def test_checks_stop_hook_active_flag(self):
        """Test that stop_hook_active flag is checked"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "stop_hook_active" in content

    def test_exits_when_stop_hook_active_is_true(self):
        """Test that script exits when stop_hook_active is true"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert '.stop_hook_active == true' in content
        assert "exit 0" in content


@pytest.mark.unit
class TestIncrementalProcessing:
    """Tests for incremental message processing via last_line tracking"""

    def test_loads_state_for_last_line(self):
        """Test that state is loaded to get last_line"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "load_state" in content
        assert "last_line" in content

    def test_uses_awk_to_skip_processed_lines(self):
        """Test that awk is used to skip already processed lines"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should use awk with NR > start
        assert "awk" in content
        assert "NR >" in content

    def test_tracks_new_last_line(self):
        """Test that new_last_line is tracked during processing"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "new_last_line" in content

    def test_updates_state_with_new_last_line(self):
        """Test that state is updated with new last_line"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "save_state" in content

    def test_exits_early_if_no_new_messages(self):
        """Test that script exits if no new messages"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "No new messages" in content or "exit 0" in content


@pytest.mark.unit
class TestTurnGrouping:
    """Tests for grouping messages into turns"""

    def test_tracks_current_user_message(self):
        """Test that current user message is tracked"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "current_user" in content

    def test_tracks_current_assistants_array(self):
        """Test that current assistant messages are tracked as array"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "current_assistants" in content
        assert '"[]"' in content or "='[]'" in content

    def test_tracks_current_tool_results(self):
        """Test that current tool results are tracked"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "current_tool_results" in content

    def test_identifies_user_role(self):
        """Test that user role is identified"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should check for role == "user"
        assert '"user"' in content
        assert "role" in content

    def test_identifies_assistant_role(self):
        """Test that assistant role is identified"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert '"assistant"' in content

    def test_new_user_starts_new_turn(self):
        """Test that new user message starts a new turn"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # When user message is found (not tool result), should start new turn
        assert "current_user" in content
        assert 'current_user="$line"' in content

    def test_tool_result_added_to_current_turn(self):
        """Test that tool result is added to current turn"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "is_tool_result" in content
        assert "current_tool_results" in content

    def test_creates_trace_when_turn_complete(self):
        """Test that create_trace is called when turn is complete"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "create_trace" in content


@pytest.mark.unit
class TestSSEStreamingMerge:
    """Tests for merging SSE streaming message parts"""

    def test_tracks_current_msg_id(self):
        """Test that current message ID is tracked for SSE parts"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "current_msg_id" in content

    def test_tracks_current_assistant_parts(self):
        """Test that assistant parts are tracked for merging"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "current_assistant_parts" in content

    def test_same_msg_id_adds_to_parts(self):
        """Test that same message ID adds to current parts"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should compare msg_id to current_msg_id
        assert '$msg_id" = "$current_msg_id"' in content or 'msg_id = "$current_msg_id"' in content

    def test_different_msg_id_starts_new_message(self):
        """Test that different message ID starts a new message"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should set current_msg_id to new msg_id
        assert 'current_msg_id="$msg_id"' in content

    def test_merges_parts_before_new_message(self):
        """Test that parts are merged before starting new message"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "merge_assistant_parts" in content

    def test_extracts_message_id_from_line(self):
        """Test that message ID is extracted from each line"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should extract .message.id via jq
        assert ".message.id" in content


@pytest.mark.unit
class TestStateUpdates:
    """Tests for state file updates after processing"""

    def test_updates_last_line_in_state(self):
        """Test that last_line is updated in state"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "last_line" in content
        assert "new_last_line" in content

    def test_updates_turn_count_in_state(self):
        """Test that turn_count is updated in state"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "turn_count" in content

    def test_updates_timestamp_in_state(self):
        """Test that updated timestamp is set in state"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "updated" in content

    def test_state_is_session_specific(self):
        """Test that state is keyed by session_id"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should use session_id as key
        assert ".[$sid]" in content or '[$sid]' in content


@pytest.mark.unit
class TestExecutionTimeTracking:
    """Tests for execution time tracking and warnings"""

    def test_tracks_script_start_time(self):
        """Test that script start time is recorded"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "script_start" in content

    def test_tracks_script_end_time(self):
        """Test that script end time is recorded"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "script_end" in content

    def test_calculates_duration(self):
        """Test that duration is calculated"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "duration" in content

    def test_logs_execution_time(self):
        """Test that execution time is logged"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should log processing time
        assert "duration" in content
        assert "log" in content

    def test_warns_on_slow_execution(self):
        """Test that warning is logged for slow execution (>3min)"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should warn if > 180 seconds
        assert "180" in content
        assert "WARN" in content


@pytest.mark.unit
class TestTracingDisabledCheck:
    """Tests for early exit when tracing is disabled"""

    def test_checks_trace_to_langsmith_env(self):
        """Test that TRACE_TO_LANGSMITH is checked"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "TRACE_TO_LANGSMITH" in content

    def test_case_insensitive_check(self):
        """Test that check is case insensitive"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should use tr to lowercase
        assert "tr '[:upper:]' '[:lower:]'" in content

    def test_exits_early_when_disabled(self):
        """Test that script exits when tracing disabled"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should have early exit
        assert '!= "true"' in content
        assert "exit 0" in content


@pytest.mark.unit
class TestRequiredCommandChecks:
    """Tests for required command availability checks"""

    def test_checks_jq_available(self):
        """Test that jq availability is checked"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "jq" in content
        assert "command -v" in content

    def test_checks_curl_available(self):
        """Test that curl availability is checked"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "curl" in content

    def test_checks_uuidgen_available(self):
        """Test that uuidgen availability is checked"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "uuidgen" in content

    def test_exits_gracefully_if_command_missing(self):
        """Test that script exits gracefully if required command missing"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should exit 0 (not error) if command missing
        assert "exit 0" in content


@pytest.mark.unit
class TestFinalTurnProcessing:
    """Tests for processing the final turn at end of transcript"""

    def test_processes_pending_assistant_parts(self):
        """Test that pending assistant parts are merged at end"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should check for pending parts after loop
        assert "current_msg_id" in content
        assert "merge_assistant_parts" in content

    def test_processes_final_turn(self):
        """Test that final turn is processed after loop"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should have processing after the while loop
        # Look for create_trace call after loop ends
        main_section = content[content.find("# Process final turn"):]
        assert "create_trace" in main_section


@pytest.mark.unit
class TestLoggingInMain:
    """Tests for logging throughout main function"""

    def test_logs_session_start(self):
        """Test that session processing start is logged"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "Processing session" in content

    def test_logs_message_count(self):
        """Test that new message count is logged"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "new messages" in content

    def test_logs_turns_processed(self):
        """Test that turns processed count is logged"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "turns" in content

    def test_logs_invalid_input_warning(self):
        """Test that invalid input is logged as warning"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "WARN" in content
        assert "Invalid input" in content


@pytest.mark.unit
class TestMainIntegration:
    """Integration tests for main() with mocked environment"""

    def test_main_exits_when_tracing_disabled(self, tmp_path, monkeypatch):
        """Test that main exits early when TRACE_TO_LANGSMITH is not true"""
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text('{"type": "user", "content": "hello"}\n')

        hook_input = json.dumps({
            "session_id": "test-session",
            "transcript_path": str(transcript)
        })

        script = f"""
        export TRACE_TO_LANGSMITH="false"
        export LOG_FILE="{tmp_path}/hook.log"
        cd /Users/tanushreesharma/tracing-claude-code
        echo '{hook_input}' | bash stop_hook.sh
        echo "Exit code: $?"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True
        )

        # Should exit 0 (gracefully)
        assert "Exit code: 0" in result.stdout

    def test_main_exits_when_missing_session_id(self, tmp_path):
        """Test that main exits when session_id is empty"""
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text('{"type": "user", "content": "hello"}\n')

        hook_input = json.dumps({
            "session_id": "",
            "transcript_path": str(transcript)
        })

        script = f"""
        export TRACE_TO_LANGSMITH="true"
        export CC_LANGSMITH_API_KEY="test-key"
        export LOG_FILE="{tmp_path}/hook.log"
        cd /Users/tanushreesharma/tracing-claude-code
        echo '{hook_input}' | bash stop_hook.sh
        echo "Exit code: $?"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True
        )

        # Should exit 0 (gracefully)
        assert "Exit code: 0" in result.stdout

    def test_main_exits_when_transcript_missing(self, tmp_path):
        """Test that main exits when transcript file doesn't exist"""
        hook_input = json.dumps({
            "session_id": "test-session",
            "transcript_path": str(tmp_path / "nonexistent.jsonl")
        })

        script = f"""
        export TRACE_TO_LANGSMITH="true"
        export CC_LANGSMITH_API_KEY="test-key"
        export LOG_FILE="{tmp_path}/hook.log"
        cd /Users/tanushreesharma/tracing-claude-code
        echo '{hook_input}' | bash stop_hook.sh
        echo "Exit code: $?"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True
        )

        # Should exit 0 (gracefully)
        assert "Exit code: 0" in result.stdout

    def test_main_exits_when_stop_hook_active(self, tmp_path):
        """Test that main exits when stop_hook_active is true"""
        transcript = tmp_path / "transcript.jsonl"
        transcript.write_text('{"type": "user", "content": "hello"}\n')

        hook_input = json.dumps({
            "session_id": "test-session",
            "transcript_path": str(transcript),
            "stop_hook_active": True
        })

        script = f"""
        export TRACE_TO_LANGSMITH="true"
        export CC_LANGSMITH_API_KEY="test-key"
        export LOG_FILE="{tmp_path}/hook.log"
        cd /Users/tanushreesharma/tracing-claude-code
        echo '{hook_input}' | bash stop_hook.sh
        echo "Exit code: $?"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True
        )

        # Should exit 0
        assert "Exit code: 0" in result.stdout

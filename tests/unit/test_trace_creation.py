"""
Unit tests for trace creation in stop_hook.sh.

Tests:
- create_trace() - Main trace creation logic
- Turn run structure
- LLM (assistant) run structure
- Tool run structure
- Parent-child relationships
- Usage metadata
- Dotted order hierarchy
"""

import json
import subprocess
import uuid
from datetime import datetime

import pytest


@pytest.mark.unit
class TestCreateTraceFunction:
    """Tests for create_trace() function existence and structure"""

    def test_function_exists(self, bash_executor):
        """Test that create_trace function exists"""
        source = bash_executor.get_function_source("create_trace")
        assert "create_trace" in source

    def test_accepts_session_id_parameter(self, bash_executor):
        """Test that function accepts session_id parameter"""
        source = bash_executor.get_function_source("create_trace")
        assert "session_id" in source

    def test_accepts_turn_num_parameter(self, bash_executor):
        """Test that function accepts turn_num parameter"""
        source = bash_executor.get_function_source("create_trace")
        assert "turn_num" in source

    def test_accepts_user_msg_parameter(self, bash_executor):
        """Test that function accepts user_msg parameter"""
        source = bash_executor.get_function_source("create_trace")
        assert "user_msg" in source

    def test_accepts_assistant_messages_parameter(self, bash_executor):
        """Test that function accepts assistant_messages parameter"""
        source = bash_executor.get_function_source("create_trace")
        assert "assistant_messages" in source

    def test_accepts_tool_results_parameter(self, bash_executor):
        """Test that function accepts tool_results parameter"""
        source = bash_executor.get_function_source("create_trace")
        assert "tool_results" in source


@pytest.mark.unit
class TestTurnRunCreation:
    """Tests for turn (top-level chain) run creation"""

    def test_creates_turn_run_with_chain_type(self, bash_executor):
        """Test that turn run has run_type: chain"""
        source = bash_executor.get_function_source("create_trace")
        assert '"chain"' in source
        assert "run_type" in source

    def test_turn_run_has_unique_id(self, bash_executor):
        """Test that turn run gets a unique UUID"""
        source = bash_executor.get_function_source("create_trace")
        assert "uuidgen" in source
        assert "turn_id" in source

    def test_turn_run_name_is_claude_code(self, bash_executor):
        """Test that turn run is named 'Claude Code'"""
        source = bash_executor.get_function_source("create_trace")
        assert '"Claude Code"' in source

    def test_turn_run_has_dotted_order(self, bash_executor):
        """Test that turn run has dotted_order field"""
        source = bash_executor.get_function_source("create_trace")
        assert "dotted_order" in source
        assert "turn_dotted_order" in source

    def test_turn_run_trace_id_equals_run_id(self, bash_executor):
        """Test that for top-level run, trace_id = run_id"""
        source = bash_executor.get_function_source("create_trace")
        # trace_id: $turn_id (same as run id)
        assert "trace_id" in source

    def test_turn_run_has_session_name(self, bash_executor):
        """Test that turn run has session_name (project)"""
        source = bash_executor.get_function_source("create_trace")
        assert "session_name" in source
        assert "project" in source.lower() or "PROJECT" in source

    def test_turn_run_has_thread_id_metadata(self, bash_executor):
        """Test that turn run has thread_id in metadata"""
        source = bash_executor.get_function_source("create_trace")
        assert "thread_id" in source
        assert "session" in source

    def test_turn_run_has_tags(self, bash_executor):
        """Test that turn run has appropriate tags"""
        source = bash_executor.get_function_source("create_trace")
        assert '"claude-code"' in source
        assert "turn-" in source  # turn-N tag


@pytest.mark.unit
class TestAssistantRunCreation:
    """Tests for assistant (LLM) run creation"""

    def test_creates_llm_run_type(self, bash_executor):
        """Test that assistant run has run_type: llm"""
        source = bash_executor.get_function_source("create_trace")
        assert '"llm"' in source

    def test_assistant_run_has_unique_id(self, bash_executor):
        """Test that assistant run gets a unique UUID"""
        source = bash_executor.get_function_source("create_trace")
        assert "assistant_id" in source
        assert "uuidgen" in source

    def test_assistant_run_name_is_claude(self, bash_executor):
        """Test that assistant run is named 'Claude'"""
        source = bash_executor.get_function_source("create_trace")
        assert '"Claude"' in source

    def test_assistant_run_has_parent_run_id(self, bash_executor):
        """Test that assistant run references turn as parent"""
        source = bash_executor.get_function_source("create_trace")
        assert "parent_run_id" in source

    def test_assistant_run_has_trace_id(self, bash_executor):
        """Test that assistant run has trace_id from parent"""
        source = bash_executor.get_function_source("create_trace")
        assert "trace_id" in source

    def test_assistant_run_has_model_in_metadata(self, bash_executor):
        """Test that assistant run has model in metadata"""
        source = bash_executor.get_function_source("create_trace")
        assert "ls_model_name" in source
        assert "ls_provider" in source
        assert "anthropic" in source

    def test_assistant_run_has_model_in_tags(self, bash_executor):
        """Test that model name is in tags"""
        source = bash_executor.get_function_source("create_trace")
        assert "tags" in source
        assert "model" in source

    def test_assistant_run_has_dotted_order(self, bash_executor):
        """Test that assistant run has dotted_order as child of turn"""
        source = bash_executor.get_function_source("create_trace")
        assert "assistant_dotted_order" in source


@pytest.mark.unit
class TestToolRunCreation:
    """Tests for tool run creation"""

    def test_creates_tool_run_type(self, bash_executor):
        """Test that tool run has run_type: tool"""
        source = bash_executor.get_function_source("create_trace")
        assert '"tool"' in source

    def test_tool_run_has_unique_id(self, bash_executor):
        """Test that tool run gets a unique UUID"""
        source = bash_executor.get_function_source("create_trace")
        assert "tool_id" in source

    def test_tool_run_has_tool_name(self, bash_executor):
        """Test that tool run uses the tool's name"""
        source = bash_executor.get_function_source("create_trace")
        assert "tool_name" in source

    def test_tool_run_has_parent_as_turn(self, bash_executor):
        """Test that tool run has turn as parent (sibling of assistant)"""
        source = bash_executor.get_function_source("create_trace")
        # Tools are children of turn, not assistant
        assert "parent_run_id" in source
        assert "turn_id" in source

    def test_tool_run_has_input(self, bash_executor):
        """Test that tool run includes tool input"""
        source = bash_executor.get_function_source("create_trace")
        assert "tool_input" in source
        assert "input" in source

    def test_tool_run_has_dotted_order(self, bash_executor):
        """Test that tool run has dotted_order"""
        source = bash_executor.get_function_source("create_trace")
        assert "tool_dotted_order" in source

    def test_tool_run_has_tool_tag(self, bash_executor):
        """Test that tool run has 'tool' tag"""
        source = bash_executor.get_function_source("create_trace")
        assert '"tool"' in source


@pytest.mark.unit
class TestFindToolResultWithTimestamp:
    """Tests for find_tool_result_with_timestamp() function"""

    def test_function_exists(self, bash_executor):
        """Test that find_tool_result_with_timestamp function exists"""
        source = bash_executor.get_function_source("find_tool_result_with_timestamp")
        assert "find_tool_result_with_timestamp" in source

    def test_accepts_tool_id_parameter(self, bash_executor):
        """Test that function accepts tool_id parameter"""
        source = bash_executor.get_function_source("find_tool_result_with_timestamp")
        assert "tool_id" in source

    def test_accepts_tool_results_parameter(self, bash_executor):
        """Test that function accepts tool_results parameter"""
        source = bash_executor.get_function_source("find_tool_result_with_timestamp")
        assert "tool_results" in source

    def test_returns_result_and_timestamp(self, bash_executor):
        """Test that function returns both result and timestamp"""
        source = bash_executor.get_function_source("find_tool_result_with_timestamp")
        assert "result" in source
        assert "timestamp" in source

    def test_finds_tool_result_by_id(self):
        """Test finding tool result by tool_use_id"""
        tool_results = [
            {
                "type": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool_abc",
                        "content": "Found result"
                    }
                ],
                "timestamp": "2025-01-01T00:00:00Z"
            }
        ]

        script = f"""
        set -e
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)

        tool_results='{json.dumps(tool_results)}'
        find_tool_result_with_timestamp "tool_abc" "$tool_results"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        output = json.loads(result.stdout.strip())
        assert output["result"] == "Found result"
        assert output["timestamp"] == "2025-01-01T00:00:00Z"

    def test_returns_no_result_for_missing_tool(self):
        """Test that missing tool returns 'No result'"""
        tool_results = [
            {
                "type": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool_abc",
                        "content": "Some result"
                    }
                ],
                "timestamp": "2025-01-01T00:00:00Z"
            }
        ]

        script = f"""
        set -e
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)

        tool_results='{json.dumps(tool_results)}'
        find_tool_result_with_timestamp "tool_xyz" "$tool_results"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        output = json.loads(result.stdout.strip())
        assert output["result"] == "No result"

    def test_handles_array_content_in_tool_result(self):
        """Test handling of array content in tool result"""
        tool_results = [
            {
                "type": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool_array",
                        "content": [
                            {"type": "text", "text": "Part 1"},
                            {"type": "text", "text": "Part 2"}
                        ]
                    }
                ],
                "timestamp": "2025-01-01T00:00:00Z"
            }
        ]

        script = f"""
        set -e
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)

        tool_results='{json.dumps(tool_results)}'
        find_tool_result_with_timestamp "tool_array" "$tool_results"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        output = json.loads(result.stdout.strip())
        # Should concatenate text parts
        assert "Part 1" in output["result"]
        assert "Part 2" in output["result"]


@pytest.mark.unit
class TestUsageMetadata:
    """Tests for usage metadata in LLM runs"""

    def test_usage_metadata_included_in_assistant_run(self, bash_executor):
        """Test that usage_metadata is included in assistant run outputs"""
        source = bash_executor.get_function_source("create_trace")
        assert "usage_metadata" in source

    def test_usage_metadata_has_input_tokens(self, bash_executor):
        """Test that usage_metadata includes input_tokens"""
        source = bash_executor.get_function_source("create_trace")
        assert "input_tokens" in source

    def test_usage_metadata_has_output_tokens(self, bash_executor):
        """Test that usage_metadata includes output_tokens"""
        source = bash_executor.get_function_source("create_trace")
        assert "output_tokens" in source

    def test_usage_metadata_has_token_details(self, bash_executor):
        """Test that usage_metadata includes input_token_details"""
        source = bash_executor.get_function_source("create_trace")
        assert "input_token_details" in source
        assert "cache_read" in source
        assert "cache_creation" in source

    def test_usage_includes_cache_tokens_in_total(self, bash_executor):
        """Test that total input_tokens includes cache tokens"""
        source = bash_executor.get_function_source("create_trace")
        # Should add cache tokens to input_tokens
        assert "cache_creation_input_tokens" in source
        assert "cache_read_input_tokens" in source


@pytest.mark.unit
class TestDottedOrderHierarchy:
    """Tests for dotted_order parent-child hierarchy"""

    def test_turn_dotted_order_is_root(self, bash_executor):
        """Test that turn dotted_order is root (no dots)"""
        source = bash_executor.get_function_source("create_trace")
        # Turn dotted order: timestamp + turn_id
        assert "turn_dotted_order" in source
        assert "${dotted_timestamp}${turn_id}" in source

    def test_assistant_dotted_order_includes_turn(self, bash_executor):
        """Test that assistant dotted_order includes turn's dotted_order"""
        source = bash_executor.get_function_source("create_trace")
        # Assistant: turn_dotted_order.assistant_timestamp+id
        assert "assistant_dotted_order" in source
        assert "${turn_dotted_order}." in source

    def test_tool_dotted_order_includes_turn(self, bash_executor):
        """Test that tool dotted_order includes turn's dotted_order"""
        source = bash_executor.get_function_source("create_trace")
        # Tool: turn_dotted_order.tool_timestamp+id
        assert "tool_dotted_order" in source
        assert "${turn_dotted_order}." in source


@pytest.mark.unit
class TestOutputsAccumulation:
    """Tests for outputs accumulation across LLM calls"""

    def test_all_outputs_initialized_with_user_message(self, bash_executor):
        """Test that all_outputs starts with user message"""
        source = bash_executor.get_function_source("create_trace")
        assert "all_outputs" in source
        assert "user" in source

    def test_llm_outputs_added_to_all_outputs(self, bash_executor):
        """Test that LLM outputs are added to all_outputs"""
        source = bash_executor.get_function_source("create_trace")
        assert "llm_outputs" in source

    def test_tool_results_added_to_all_outputs(self, bash_executor):
        """Test that tool results are added to all_outputs"""
        source = bash_executor.get_function_source("create_trace")
        # Tool results should be added with role: tool
        assert '"tool"' in source
        assert "tool_call_id" in source

    def test_turn_outputs_filters_user_messages(self, bash_executor):
        """Test that turn outputs filter out user messages"""
        source = bash_executor.get_function_source("create_trace")
        # Final outputs should exclude user messages
        assert 'select(.role != "user")' in source


@pytest.mark.unit
class TestBatchProcessing:
    """Tests for batch processing of runs"""

    def test_posts_batch_initialized(self, bash_executor):
        """Test that posts_batch is initialized"""
        source = bash_executor.get_function_source("create_trace")
        assert "posts_batch" in source

    def test_patches_batch_initialized(self, bash_executor):
        """Test that patches_batch is initialized"""
        source = bash_executor.get_function_source("create_trace")
        assert "patches_batch" in source

    def test_turn_added_to_posts_batch(self, bash_executor):
        """Test that turn run is added to posts batch"""
        source = bash_executor.get_function_source("create_trace")
        # Should add turn_data to posts_batch
        assert "turn_data" in source
        assert "posts_batch" in source

    def test_assistant_added_to_posts_batch(self, bash_executor):
        """Test that assistant run is added to posts batch"""
        source = bash_executor.get_function_source("create_trace")
        assert "assistant_data" in source

    def test_tool_added_to_posts_batch(self, bash_executor):
        """Test that tool run is added to posts batch"""
        source = bash_executor.get_function_source("create_trace")
        assert "tool_data" in source

    def test_assistant_update_added_to_patches_batch(self, bash_executor):
        """Test that assistant update is added to patches batch"""
        source = bash_executor.get_function_source("create_trace")
        assert "assistant_update" in source
        assert "patches_batch" in source

    def test_tool_update_added_to_patches_batch(self, bash_executor):
        """Test that tool update is added to patches batch"""
        source = bash_executor.get_function_source("create_trace")
        assert "tool_update" in source

    def test_turn_update_added_to_patches_batch(self, bash_executor):
        """Test that turn update is added to patches batch"""
        source = bash_executor.get_function_source("create_trace")
        assert "turn_update" in source

    def test_send_multipart_batch_called_for_posts(self, bash_executor):
        """Test that send_multipart_batch is called for posts"""
        source = bash_executor.get_function_source("create_trace")
        assert 'send_multipart_batch "post"' in source

    def test_send_multipart_batch_called_for_patches(self, bash_executor):
        """Test that send_multipart_batch is called for patches"""
        source = bash_executor.get_function_source("create_trace")
        assert 'send_multipart_batch "patch"' in source


@pytest.mark.unit
class TestCurrentTurnTracking:
    """Tests for CURRENT_TURN_ID tracking for cleanup"""

    def test_current_turn_id_set_after_turn_creation(self, bash_executor):
        """Test that CURRENT_TURN_ID is set after creating turn run"""
        source = bash_executor.get_function_source("create_trace")
        assert "CURRENT_TURN_ID" in source
        assert 'CURRENT_TURN_ID="$turn_id"' in source

    def test_current_turn_id_cleared_after_completion(self, bash_executor):
        """Test that CURRENT_TURN_ID is cleared after trace completion"""
        source = bash_executor.get_function_source("create_trace")
        assert 'CURRENT_TURN_ID=""' in source


@pytest.mark.unit
class TestMultipleLLMCalls:
    """Tests for handling multiple LLM calls in one turn"""

    def test_iterates_over_assistant_messages(self, bash_executor):
        """Test that function iterates over all assistant messages"""
        source = bash_executor.get_function_source("create_trace")
        # Should loop through assistant_messages
        assert "while" in source or "for" in source
        assert "assistant_msg" in source

    def test_llm_num_counter(self, bash_executor):
        """Test that LLM call number is tracked"""
        source = bash_executor.get_function_source("create_trace")
        assert "llm_num" in source

    def test_last_llm_end_tracked(self, bash_executor):
        """Test that last LLM end time is tracked for next LLM start"""
        source = bash_executor.get_function_source("create_trace")
        assert "last_llm_end" in source

    def test_llm_inputs_include_accumulated_context(self, bash_executor):
        """Test that LLM inputs include all previous context"""
        source = bash_executor.get_function_source("create_trace")
        assert "llm_inputs" in source
        assert "all_outputs" in source


@pytest.mark.unit
class TestLogging:
    """Tests for logging in create_trace"""

    def test_logs_turn_creation(self, bash_executor):
        """Test that turn creation is logged"""
        source = bash_executor.get_function_source("create_trace")
        assert "log" in source
        assert "INFO" in source
        assert "turn" in source.lower()

    def test_logs_llm_call_count(self, bash_executor):
        """Test that LLM call count is logged"""
        source = bash_executor.get_function_source("create_trace")
        assert "llm_num" in source
        assert "LLM call" in source

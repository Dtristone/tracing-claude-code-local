"""
Unit tests for message parsing functions from stop_hook.sh.

Tests:
- get_content() - Extract content from messages
- is_tool_result() - Identify tool result messages
- get_tool_uses() - Extract tool_use blocks
"""

import json
import pytest


@pytest.mark.unit
class TestGetContent:
    """Tests for get_content() function"""

    def test_get_content_from_message_wrapper(self, bash_executor):
        """Test extracting content from {message: {content: ...}} format"""
        msg = json.dumps({"message": {"content": "hello"}})
        result = bash_executor.call_function("get_content", msg)
        assert result == '"hello"'

    def test_get_content_from_direct_format(self, bash_executor):
        """Test extracting content from {content: ...} format"""
        msg = json.dumps({"content": "world"})
        result = bash_executor.call_function("get_content", msg)
        assert result == '"world"'

    def test_get_content_with_array(self, bash_executor):
        """Test extracting array content"""
        msg = json.dumps({
            "content": [
                {"type": "text", "text": "hi"}
            ]
        })
        result = bash_executor.call_function("get_content", msg)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert parsed[0]["type"] == "text"
        assert parsed[0]["text"] == "hi"

    def test_get_content_returns_null_for_invalid(self, bash_executor):
        """Test null return for invalid input"""
        msg = json.dumps({})
        result = bash_executor.call_function("get_content", msg)
        assert result == "null"

    def test_get_content_with_nested_message(self, bash_executor, sample_assistant_message):
        """Test extracting content from complex assistant message"""
        msg = json.dumps(sample_assistant_message)
        result = bash_executor.call_function("get_content", msg)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 3  # thinking + text + tool_use
        assert parsed[0]["type"] == "thinking"
        assert parsed[1]["type"] == "text"
        assert parsed[2]["type"] == "tool_use"


@pytest.mark.unit
class TestIsToolResult:
    """Tests for is_tool_result() function"""

    def test_identifies_tool_result_message(self, bash_executor):
        """Test identifying messages containing tool_result"""
        msg = json.dumps({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "abc",
                    "content": "result"
                }
            ]
        })
        result = bash_executor.call_function("is_tool_result", msg)
        assert result == "true"

    def test_identifies_tool_result_from_sample(self, bash_executor, sample_tool_result):
        """Test identifying tool result using sample fixture"""
        msg = json.dumps(sample_tool_result)
        result = bash_executor.call_function("is_tool_result", msg)
        assert result == "true"

    def test_rejects_non_tool_result(self, bash_executor):
        """Test rejecting normal user messages"""
        msg = json.dumps({"role": "user", "content": "hello"})
        result = bash_executor.call_function("is_tool_result", msg)
        assert result == "false"

    def test_rejects_assistant_message(self, bash_executor, sample_assistant_message):
        """Test rejecting assistant messages (even with tool_use)"""
        msg = json.dumps(sample_assistant_message)
        result = bash_executor.call_function("is_tool_result", msg)
        assert result == "false"

    def test_handles_string_content(self, bash_executor):
        """Test handling string content (not array)"""
        msg = json.dumps({"role": "user", "content": "not an array"})
        result = bash_executor.call_function("is_tool_result", msg)
        assert result == "false"

    def test_handles_empty_content_array(self, bash_executor):
        """Test handling empty content array"""
        msg = json.dumps({"role": "user", "content": []})
        result = bash_executor.call_function("is_tool_result", msg)
        assert result == "false"


@pytest.mark.unit
class TestGetToolUses:
    """Tests for get_tool_uses() function"""

    def test_extracts_tool_uses_from_content(self, bash_executor, sample_assistant_message):
        """Test extracting tool_use blocks from assistant message"""
        msg = json.dumps(sample_assistant_message)
        result = bash_executor.call_function("get_tool_uses", msg)
        tools = json.loads(result)

        assert isinstance(tools, list)
        assert len(tools) == 1
        assert tools[0]["type"] == "tool_use"
        assert tools[0]["name"] == "Read"
        assert tools[0]["id"] == "tool_test_abc"
        assert "input" in tools[0]

    def test_extracts_multiple_tool_uses(self, bash_executor):
        """Test extracting multiple tool_use blocks"""
        msg = json.dumps({
            "message": {
                "content": [
                    {"type": "text", "text": "I'll use two tools"},
                    {
                        "type": "tool_use",
                        "id": "tool_1",
                        "name": "Read",
                        "input": {"file": "a.txt"}
                    },
                    {
                        "type": "tool_use",
                        "id": "tool_2",
                        "name": "Write",
                        "input": {"file": "b.txt"}
                    }
                ]
            }
        })
        result = bash_executor.call_function("get_tool_uses", msg)
        tools = json.loads(result)

        assert len(tools) == 2
        assert tools[0]["name"] == "Read"
        assert tools[1]["name"] == "Write"

    def test_returns_empty_for_no_tools(self, bash_executor):
        """Test empty array when no tool uses"""
        msg = json.dumps({
            "message": {
                "content": [{"type": "text", "text": "no tools"}]
            }
        })
        result = bash_executor.call_function("get_tool_uses", msg)
        tools = json.loads(result)
        assert tools == []

    def test_handles_string_content(self, bash_executor):
        """Test handling non-array content"""
        msg = json.dumps({"content": "string content"})
        result = bash_executor.call_function("get_tool_uses", msg)
        tools = json.loads(result)
        assert tools == []

    def test_handles_missing_content(self, bash_executor):
        """Test handling messages without content field"""
        msg = json.dumps({"message": {"id": "123"}})
        result = bash_executor.call_function("get_tool_uses", msg)
        tools = json.loads(result)
        assert tools == []

    def test_handles_mixed_content_types(self, bash_executor):
        """Test extracting tool_use from mixed content"""
        msg = json.dumps({
            "content": [
                {"type": "thinking", "thinking": "analyzing"},
                {"type": "text", "text": "result"},
                {"type": "tool_use", "id": "t1", "name": "Bash", "input": {}},
                {"type": "text", "text": "more text"}
            ]
        })
        result = bash_executor.call_function("get_tool_uses", msg)
        tools = json.loads(result)

        assert len(tools) == 1
        assert tools[0]["name"] == "Bash"

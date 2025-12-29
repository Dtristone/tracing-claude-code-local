"""
Unit tests for content formatting functions from stop_hook.sh.

Tests:
- format_content() - Convert content to LangSmith format
- merge_assistant_parts() - Merge SSE streaming parts
- get_usage_from_parts() - Extract token usage from parts
"""

import json
import pytest


@pytest.mark.unit
class TestFormatContent:
    """Tests for format_content() function"""

    def test_formats_string_content(self, bash_executor):
        """Test converting string to LangSmith format"""
        msg = json.dumps({"content": "hello world"})
        result = bash_executor.call_function("format_content", msg)
        formatted = json.loads(result)

        assert isinstance(formatted, list)
        assert len(formatted) == 1
        assert formatted[0]["type"] == "text"
        assert formatted[0]["text"] == "hello world"

    def test_formats_array_content(self, bash_executor):
        """Test formatting array with multiple content types"""
        msg = json.dumps({
            "content": [
                {"type": "thinking", "thinking": "analyzing..."},
                {"type": "text", "text": "result"},
                {"type": "tool_use", "id": "t1", "name": "Read", "input": {}}
            ]
        })
        result = bash_executor.call_function("format_content", msg)
        formatted = json.loads(result)

        assert len(formatted) == 3
        assert formatted[0]["type"] == "thinking"
        assert formatted[1]["type"] == "text"
        # tool_use should be converted to tool_call
        assert formatted[2]["type"] == "tool_call"
        assert formatted[2]["name"] == "Read"

    def test_converts_tool_use_to_tool_call(self, bash_executor):
        """Test that tool_use blocks are converted to tool_call"""
        msg = json.dumps({
            "content": [
                {
                    "type": "tool_use",
                    "id": "tool_123",
                    "name": "Bash",
                    "input": {"command": "ls"}
                }
            ]
        })
        result = bash_executor.call_function("format_content", msg)
        formatted = json.loads(result)

        assert len(formatted) == 1
        assert formatted[0]["type"] == "tool_call"
        assert formatted[0]["id"] == "tool_123"
        assert formatted[0]["name"] == "Bash"
        assert formatted[0]["args"] == {"command": "ls"}

    def test_handles_empty_content(self, bash_executor):
        """Test default for empty/null content"""
        msg = json.dumps({"content": []})
        result = bash_executor.call_function("format_content", msg)
        formatted = json.loads(result)

        # Should return default text block
        assert len(formatted) == 1
        assert formatted[0]["type"] == "text"
        assert formatted[0]["text"] == ""

    def test_handles_null_content(self, bash_executor):
        """Test handling null content"""
        msg = json.dumps({"content": None})
        result = bash_executor.call_function("format_content", msg)
        formatted = json.loads(result)

        assert len(formatted) == 1
        assert formatted[0]["type"] == "text"
        assert formatted[0]["text"] == ""

    def test_handles_missing_content(self, bash_executor):
        """Test handling messages without content field"""
        msg = json.dumps({"message": {"id": "123"}})
        result = bash_executor.call_function("format_content", msg)
        formatted = json.loads(result)

        assert len(formatted) == 1
        assert formatted[0]["type"] == "text"
        assert formatted[0]["text"] == ""


@pytest.mark.unit
class TestMergeAssistantParts:
    """Tests for merge_assistant_parts() function"""

    def test_merges_multiple_parts_with_same_id(self, bash_executor, sample_streaming_parts):
        """Test merging SSE streaming parts"""
        parts_json = json.dumps(sample_streaming_parts)
        result = bash_executor.call_function("merge_assistant_parts", parts_json)
        merged = json.loads(result)

        # Check structure
        assert "message" in merged
        assert "content" in merged["message"]

        # Check content was merged
        content = merged["message"]["content"]
        assert len(content) == 1
        assert content[0]["type"] == "text"
        assert content[0]["text"] == "Hello world!"

        # Check usage is from last part (cumulative)
        assert "_usage" in merged["message"]
        assert merged["message"]["_usage"]["output_tokens"] == 5

    def test_merges_text_blocks_only(self, bash_executor):
        """Test that only adjacent text blocks are merged"""
        parts = [
            {
                "message": {
                    "id": "msg_1",
                    "content": [{"type": "text", "text": "Part 1 "}],
                    "usage": {"input_tokens": 10, "output_tokens": 2}
                }
            },
            {
                "message": {
                    "id": "msg_1",
                    "content": [{"type": "text", "text": "Part 2"}],
                    "usage": {"input_tokens": 10, "output_tokens": 4}
                }
            }
        ]

        result = bash_executor.call_function("merge_assistant_parts", json.dumps(parts))
        merged = json.loads(result)

        content = merged["message"]["content"]
        assert len(content) == 1
        assert content[0]["text"] == "Part 1 Part 2"

    def test_preserves_non_text_content(self, bash_executor):
        """Test that tool_use blocks are not merged"""
        parts = [
            {
                "message": {
                    "id": "msg_1",
                    "content": [
                        {"type": "text", "text": "Calling tool"},
                        {"type": "tool_use", "id": "t1", "name": "Read", "input": {}}
                    ],
                    "usage": {"input_tokens": 10, "output_tokens": 5}
                }
            }
        ]

        result = bash_executor.call_function("merge_assistant_parts", json.dumps(parts))
        merged = json.loads(result)

        content = merged["message"]["content"]
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "tool_use"

    def test_handles_single_part(self, bash_executor):
        """Test that single part is returned as-is"""
        parts = [
            {
                "message": {
                    "id": "msg_1",
                    "content": [{"type": "text", "text": "Single part"}],
                    "usage": {"input_tokens": 10, "output_tokens": 5}
                }
            }
        ]

        result = bash_executor.call_function("merge_assistant_parts", json.dumps(parts))
        merged = json.loads(result)

        content = merged["message"]["content"]
        assert len(content) == 1
        assert content[0]["text"] == "Single part"


@pytest.mark.unit
class TestGetUsageFromParts:
    """Tests for get_usage_from_parts() function"""

    def test_extracts_usage_from_last_part(self, bash_executor, sample_streaming_parts):
        """Test extracting usage from last part (cumulative tokens)"""
        parts_json = json.dumps(sample_streaming_parts)
        result = bash_executor.call_function("get_usage_from_parts", parts_json)
        usage = json.loads(result)

        # Should get usage from last part (cumulative)
        assert usage["input_tokens"] == 10
        assert usage["output_tokens"] == 5

    def test_extracts_usage_with_cache_tokens(self, bash_executor):
        """Test extracting usage with cache read tokens"""
        parts = [
            {
                "message": {
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "cache_read_input_tokens": 1000,
                        "cache_creation_input_tokens": 200
                    }
                }
            }
        ]

        result = bash_executor.call_function("get_usage_from_parts", json.dumps(parts))
        usage = json.loads(result)

        assert usage["input_tokens"] == 100
        assert usage["output_tokens"] == 50
        assert usage["cache_read_input_tokens"] == 1000
        assert usage["cache_creation_input_tokens"] == 200

    def test_handles_missing_usage(self, bash_executor):
        """Test handling parts without usage field"""
        parts = [{"message": {"content": [{"type": "text", "text": "hi"}]}}]

        result = bash_executor.call_function("get_usage_from_parts", json.dumps(parts))

        # Should return null or empty object
        assert result in ["null", "{}"]

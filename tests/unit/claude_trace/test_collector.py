"""Tests for claude_trace.collector module."""

import json
import os
import pytest
import tempfile
from pathlib import Path

from claude_trace.collector import TraceCollector
from claude_trace.models import ContentType, MessageRole


@pytest.fixture
def temp_transcript(tmp_path):
    """Create a temporary transcript file."""
    transcript_file = tmp_path / "test_transcript.jsonl"
    return transcript_file


@pytest.fixture
def minimal_transcript_data():
    """Minimal transcript data."""
    return [
        {"type": "user", "role": "user", "content": "Hello", "timestamp": "2025-02-04T10:30:00.000Z"},
        {"type": "assistant", "message": {"id": "msg_1", "role": "assistant", "model": "claude-sonnet-4-5", "content": [{"type": "text", "text": "Hi there!"}], "usage": {"input_tokens": 10, "output_tokens": 5}}, "timestamp": "2025-02-04T10:30:01.000Z"}
    ]


@pytest.fixture
def transcript_with_tools():
    """Transcript data with tool usage."""
    return [
        {"type": "user", "role": "user", "content": "Read file test.txt", "timestamp": "2025-02-04T10:30:00.000Z"},
        {"type": "assistant", "message": {"id": "msg_1", "role": "assistant", "model": "claude-sonnet-4-5", "content": [{"type": "text", "text": "I'll read that file."}, {"type": "tool_use", "id": "tool_1", "name": "Read", "input": {"file_path": "/test/test.txt"}}], "usage": {"input_tokens": 10, "output_tokens": 15}}, "timestamp": "2025-02-04T10:30:01.000Z"},
        {"type": "user", "role": "user", "content": [{"type": "tool_result", "tool_use_id": "tool_1", "content": "File content: hello world"}], "timestamp": "2025-02-04T10:30:02.000Z"},
        {"type": "assistant", "message": {"id": "msg_2", "role": "assistant", "model": "claude-sonnet-4-5", "content": [{"type": "text", "text": "The file says: hello world"}], "usage": {"input_tokens": 20, "output_tokens": 10}}, "timestamp": "2025-02-04T10:30:03.000Z"}
    ]


def write_transcript(file_path: Path, data: list):
    """Write transcript data to a JSONL file."""
    with open(file_path, 'w') as f:
        for item in data:
            f.write(json.dumps(item) + '\n')


@pytest.mark.unit
class TestTraceCollector:
    """Tests for TraceCollector class."""
    
    def test_collect_minimal_transcript(self, temp_transcript, minimal_transcript_data):
        """Test collecting from a minimal transcript."""
        write_transcript(temp_transcript, minimal_transcript_data)
        
        collector = TraceCollector()
        session = collector.collect_from_file(str(temp_transcript))
        
        assert session.session_id == "test_transcript"
        assert len(session.turns) == 1
        assert session.turns[0].user_message is not None
        assert session.turns[0].user_message.text_content == "Hello"
        assert len(session.turns[0].assistant_messages) == 1
        assert session.turns[0].assistant_messages[0].text_content == "Hi there!"
    
    def test_collect_with_tools(self, temp_transcript, transcript_with_tools):
        """Test collecting transcript with tool usage."""
        write_transcript(temp_transcript, transcript_with_tools)
        
        collector = TraceCollector()
        session = collector.collect_from_file(str(temp_transcript))
        
        assert len(session.turns) == 1
        turn = session.turns[0]
        
        # Check tool uses
        assert len(turn.tool_uses) == 1
        tool = turn.tool_uses[0]
        assert tool.tool_name == "Read"
        assert tool.input_data == {"file_path": "/test/test.txt"}
        assert tool.output_data == "File content: hello world"
    
    def test_collect_custom_session_id(self, temp_transcript, minimal_transcript_data):
        """Test collecting with custom session ID."""
        write_transcript(temp_transcript, minimal_transcript_data)
        
        collector = TraceCollector()
        session = collector.collect_from_file(
            str(temp_transcript), 
            session_id="custom-session-123"
        )
        
        assert session.session_id == "custom-session-123"
    
    def test_collect_empty_file(self, temp_transcript):
        """Test collecting from empty file."""
        temp_transcript.touch()
        
        collector = TraceCollector()
        session = collector.collect_from_file(str(temp_transcript))
        
        assert len(session.turns) == 0
    
    def test_collect_file_not_found(self, tmp_path):
        """Test error when file not found."""
        collector = TraceCollector()
        
        with pytest.raises(FileNotFoundError):
            collector.collect_from_file(str(tmp_path / "nonexistent.jsonl"))
    
    def test_collect_multi_turn(self, temp_transcript):
        """Test collecting multi-turn conversation."""
        data = [
            {"type": "user", "role": "user", "content": "First question", "timestamp": "2025-02-04T10:30:00.000Z"},
            {"type": "assistant", "message": {"id": "msg_1", "role": "assistant", "model": "claude-sonnet-4-5", "content": [{"type": "text", "text": "First answer"}], "usage": {"input_tokens": 10, "output_tokens": 5}}, "timestamp": "2025-02-04T10:30:01.000Z"},
            {"type": "user", "role": "user", "content": "Second question", "timestamp": "2025-02-04T10:30:10.000Z"},
            {"type": "assistant", "message": {"id": "msg_2", "role": "assistant", "model": "claude-sonnet-4-5", "content": [{"type": "text", "text": "Second answer"}], "usage": {"input_tokens": 20, "output_tokens": 10}}, "timestamp": "2025-02-04T10:30:11.000Z"},
        ]
        write_transcript(temp_transcript, data)
        
        collector = TraceCollector()
        session = collector.collect_from_file(str(temp_transcript))
        
        assert len(session.turns) == 2
        assert session.turns[0].turn_number == 1
        assert session.turns[1].turn_number == 2
        assert session.turns[0].user_message.text_content == "First question"
        assert session.turns[1].user_message.text_content == "Second question"
    
    def test_collect_with_thinking(self, temp_transcript):
        """Test collecting messages with thinking blocks."""
        data = [
            {"type": "user", "role": "user", "content": "Complex question", "timestamp": "2025-02-04T10:30:00.000Z"},
            {"type": "assistant", "message": {"id": "msg_1", "role": "assistant", "model": "claude-sonnet-4-5", "content": [{"type": "thinking", "thinking": "Let me analyze this..."}, {"type": "text", "text": "Here's my analysis"}], "usage": {"input_tokens": 50, "output_tokens": 100}}, "timestamp": "2025-02-04T10:30:05.000Z"},
        ]
        write_transcript(temp_transcript, data)
        
        collector = TraceCollector()
        session = collector.collect_from_file(str(temp_transcript))
        
        msg = session.turns[0].assistant_messages[0]
        assert len(msg.content) == 2
        assert msg.content[0].type == ContentType.THINKING
        assert msg.content[0].thinking == "Let me analyze this..."
        assert msg.content[1].type == ContentType.TEXT
    
    def test_collect_token_usage(self, temp_transcript, minimal_transcript_data):
        """Test that token usage is captured."""
        write_transcript(temp_transcript, minimal_transcript_data)
        
        collector = TraceCollector()
        session = collector.collect_from_file(str(temp_transcript))
        
        msg = session.turns[0].assistant_messages[0]
        assert msg.usage is not None
        assert msg.usage.input_tokens == 10
        assert msg.usage.output_tokens == 5
    
    def test_collect_model_name(self, temp_transcript, minimal_transcript_data):
        """Test that model name is captured."""
        write_transcript(temp_transcript, minimal_transcript_data)
        
        collector = TraceCollector()
        session = collector.collect_from_file(str(temp_transcript))
        
        msg = session.turns[0].assistant_messages[0]
        assert msg.model == "claude-sonnet-4-5"
    
    def test_session_timing(self, temp_transcript, minimal_transcript_data):
        """Test that session timing is set correctly."""
        write_transcript(temp_transcript, minimal_transcript_data)
        
        collector = TraceCollector()
        session = collector.collect_from_file(str(temp_transcript))
        
        assert session.start_time is not None
        assert session.end_time is not None
        assert session.start_time <= session.end_time


@pytest.mark.unit
class TestIncrementalCollection:
    """Tests for incremental trace collection."""
    
    def test_incremental_new_data(self, temp_transcript, minimal_transcript_data):
        """Test incremental collection with new data."""
        write_transcript(temp_transcript, minimal_transcript_data)
        
        collector = TraceCollector()
        
        # First collection
        session, last_line = collector.collect_incremental(
            str(temp_transcript),
            "test_session",
            0
        )
        
        assert len(session.turns) == 1
        assert last_line == 2
    
    def test_incremental_no_new_data(self, temp_transcript, minimal_transcript_data):
        """Test incremental collection with no new data."""
        write_transcript(temp_transcript, minimal_transcript_data)
        
        collector = TraceCollector()
        
        # Collect all
        session1, last_line1 = collector.collect_incremental(
            str(temp_transcript),
            "test_session",
            0
        )
        
        # Try to collect again - should return same session
        session2, last_line2 = collector.collect_incremental(
            str(temp_transcript),
            "test_session",
            last_line1
        )
        
        assert last_line2 == last_line1

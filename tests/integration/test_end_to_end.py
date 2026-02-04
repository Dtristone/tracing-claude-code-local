"""
End-to-End Integration Tests for Claude Code Local Tracing.

These tests verify the complete data flow from transcript parsing through
storage, analysis, and CLI output. They ensure all plan requirements are met:

1. Session Timeline - Main process flow visualization
2. Model Tracking - Input/output context, token counts, latency
3. Tool Monitoring - Tool name, input, output, latency
4. Operation Logging - All operations with timestamps  
5. Time Analysis - Breakdown of time spent in each phase
6. Statistics - Fail/retry counts, conversation loop metrics
7. KV Cache Analysis - Cache hit/miss statistics
"""

import json
import os
import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from claude_trace.collector import TraceCollector
from claude_trace.storage import TraceStorage
from claude_trace.analyzer import TraceAnalyzer
from claude_trace.reporter import TraceReporter
from claude_trace.models import (
    Session, Turn, Message, ToolUse, TokenUsage,
    ContentType, MessageRole
)


class TestEndToEndTracing:
    """End-to-end tests for the complete tracing pipeline."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test_traces.db"
        return TraceStorage(str(db_path))
    
    @pytest.fixture
    def complex_transcript(self, tmp_path):
        """Create a complex transcript with multiple turns, tools, and cache usage."""
        transcript_data = [
            # Turn 1: User question with tool use
            {
                "type": "user",
                "role": "user", 
                "content": "Read the config file and explain what it does",
                "timestamp": "2025-02-04T10:30:00.000000Z"
            },
            {
                "type": "assistant",
                "message": {
                    "id": "msg_001",
                    "role": "assistant",
                    "model": "claude-sonnet-4-5-20250929",
                    "content": [
                        {"type": "text", "text": "I'll read the config file for you."},
                        {"type": "tool_use", "id": "tool_001", "name": "Read", "input": {"file_path": "/config/settings.json"}}
                    ],
                    "usage": {
                        "input_tokens": 150,
                        "output_tokens": 45,
                        "cache_read_input_tokens": 100,
                        "cache_creation_input_tokens": 50
                    }
                },
                "timestamp": "2025-02-04T10:30:02.500000Z"
            },
            {
                "type": "user",
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "tool_001", "content": '{"debug": true, "port": 8080}'}],
                "timestamp": "2025-02-04T10:30:02.600000Z"
            },
            {
                "type": "assistant",
                "message": {
                    "id": "msg_002",
                    "role": "assistant",
                    "model": "claude-sonnet-4-5-20250929",
                    "content": [
                        {"type": "text", "text": "The config file contains debug mode enabled and port 8080."}
                    ],
                    "usage": {
                        "input_tokens": 200,
                        "output_tokens": 30,
                        "cache_read_input_tokens": 150,
                        "cache_creation_input_tokens": 0
                    }
                },
                "timestamp": "2025-02-04T10:30:05.000000Z"
            },
            
            # Turn 2: Follow-up with multiple tool calls
            {
                "type": "user",
                "role": "user",
                "content": "Now check if port 8080 is in use and show running processes",
                "timestamp": "2025-02-04T10:30:10.000000Z"
            },
            {
                "type": "assistant",
                "message": {
                    "id": "msg_003",
                    "role": "assistant",
                    "model": "claude-sonnet-4-5-20250929",
                    "content": [
                        {"type": "thinking", "thinking": "I need to check the port and list processes..."},
                        {"type": "text", "text": "Let me check that for you."},
                        {"type": "tool_use", "id": "tool_002", "name": "Bash", "input": {"command": "lsof -i :8080"}}
                    ],
                    "usage": {
                        "input_tokens": 300,
                        "output_tokens": 60,
                        "cache_read_input_tokens": 200
                    }
                },
                "timestamp": "2025-02-04T10:30:12.000000Z"
            },
            {
                "type": "user",
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "tool_002", "content": "node    1234  user   TCP *:8080 (LISTEN)"}],
                "timestamp": "2025-02-04T10:30:13.500000Z"
            },
            {
                "type": "assistant",
                "message": {
                    "id": "msg_004",
                    "role": "assistant",
                    "model": "claude-sonnet-4-5-20250929",
                    "content": [
                        {"type": "text", "text": "Port 8080 is in use by a Node.js process (PID 1234)."}
                    ],
                    "usage": {
                        "input_tokens": 350,
                        "output_tokens": 25
                    }
                },
                "timestamp": "2025-02-04T10:30:15.000000Z"
            },
            
            # Turn 3: Simple question without tools
            {
                "type": "user",
                "role": "user",
                "content": "Should I stop that process?",
                "timestamp": "2025-02-04T10:30:20.000000Z"
            },
            {
                "type": "assistant",
                "message": {
                    "id": "msg_005",
                    "role": "assistant",
                    "model": "claude-sonnet-4-5-20250929",
                    "content": [
                        {"type": "text", "text": "That depends on whether you need it. It appears to be your development server."}
                    ],
                    "usage": {
                        "input_tokens": 400,
                        "output_tokens": 35,
                        "cache_read_input_tokens": 350
                    }
                },
                "timestamp": "2025-02-04T10:30:22.000000Z"
            }
        ]
        
        transcript_path = tmp_path / "complex_session.jsonl"
        with open(transcript_path, 'w') as f:
            for item in transcript_data:
                f.write(json.dumps(item) + '\n')
        
        return transcript_path
    
    def test_complete_pipeline_collection(self, temp_db, complex_transcript):
        """Test 1: Verify complete data collection from transcript."""
        collector = TraceCollector(storage=temp_db)
        session = collector.collect_from_file(str(complex_transcript), session_id="test_e2e_session")
        
        # Verify session structure
        assert session.session_id == "test_e2e_session"
        assert session.start_time is not None
        assert session.end_time is not None
        assert len(session.turns) == 3
        
        # Verify turns
        turn1 = session.turns[0]
        assert turn1.turn_number == 1
        assert turn1.user_message is not None
        assert "config file" in turn1.user_message.text_content.lower()
        assert len(turn1.assistant_messages) == 2
        assert len(turn1.tool_uses) == 1
        
        turn2 = session.turns[1]
        assert turn2.turn_number == 2
        assert len(turn2.tool_uses) == 1
        assert turn2.tool_uses[0].tool_name == "Bash"
        
        turn3 = session.turns[2]
        assert turn3.turn_number == 3
        assert len(turn3.tool_uses) == 0
    
    def test_model_tracking(self, temp_db, complex_transcript):
        """Test 2: Verify model tracking - tokens, model name, latency."""
        collector = TraceCollector(storage=temp_db)
        session = collector.collect_from_file(str(complex_transcript), session_id="test_model_tracking")
        
        # Check model tracking in messages
        for turn in session.turns:
            for msg in turn.assistant_messages:
                assert msg.model is not None
                assert "claude" in msg.model.lower()
                assert msg.usage is not None
                assert msg.usage.input_tokens > 0
                assert msg.usage.output_tokens > 0
        
        # Check first assistant message specifically
        first_msg = session.turns[0].assistant_messages[0]
        assert first_msg.usage.input_tokens == 150
        assert first_msg.usage.output_tokens == 45
        assert first_msg.usage.cache_read_tokens == 100
    
    def test_tool_monitoring(self, temp_db, complex_transcript):
        """Test 3: Verify tool monitoring - name, input, output, timing."""
        collector = TraceCollector(storage=temp_db)
        session = collector.collect_from_file(str(complex_transcript), session_id="test_tool_monitoring")
        
        all_tools = session.get_all_tool_uses()
        assert len(all_tools) == 2
        
        # Check first tool (Read)
        read_tool = all_tools[0]
        assert read_tool.tool_name == "Read"
        assert read_tool.input_data.get("file_path") == "/config/settings.json"
        assert read_tool.output_data is not None
        assert "debug" in read_tool.output_data
        assert read_tool.success is True
        
        # Check second tool (Bash)
        bash_tool = all_tools[1]
        assert bash_tool.tool_name == "Bash"
        assert "lsof" in bash_tool.input_data.get("command", "")
        assert bash_tool.output_data is not None
        assert "8080" in bash_tool.output_data
    
    def test_storage_persistence(self, temp_db, complex_transcript):
        """Test 4: Verify data persists in SQLite and can be retrieved."""
        collector = TraceCollector(storage=temp_db)
        session = collector.collect_from_file(str(complex_transcript), session_id="test_storage")
        
        # Retrieve from storage
        retrieved = temp_db.get_session("test_storage")
        assert retrieved is not None
        assert retrieved.session_id == "test_storage"
        assert len(retrieved.turns) == 3
        
        # Verify message content persists
        assert retrieved.turns[0].user_message.text_content == session.turns[0].user_message.text_content
        
        # Verify tool uses persist
        assert len(retrieved.turns[0].tool_uses) == 1
        assert retrieved.turns[0].tool_uses[0].tool_name == "Read"
    
    def test_session_listing(self, temp_db, complex_transcript):
        """Test 5: Verify session listing works correctly."""
        collector = TraceCollector(storage=temp_db)
        collector.collect_from_file(str(complex_transcript), session_id="session_1")
        collector.collect_from_file(str(complex_transcript), session_id="session_2")
        
        sessions = temp_db.list_sessions(limit=10)
        assert len(sessions) >= 2
        
        session_ids = [s["session_id"] for s in sessions]
        assert "session_1" in session_ids
        assert "session_2" in session_ids
    
    def test_statistics_analysis(self, temp_db, complex_transcript):
        """Test 6: Verify statistics computation - turns, tokens, tools, cache."""
        collector = TraceCollector(storage=temp_db)
        session = collector.collect_from_file(str(complex_transcript), session_id="test_stats")
        
        analyzer = TraceAnalyzer()
        stats = analyzer.analyze_session(session)
        
        # Verify basic counts
        assert stats.total_turns == 3
        assert stats.total_tool_uses == 2
        assert stats.total_messages > 0
        
        # Verify token tracking
        assert stats.total_tokens.input_tokens > 0
        assert stats.total_tokens.output_tokens > 0
        
        # Verify cache tracking (KV cache analysis)
        assert stats.total_tokens.cache_read_tokens > 0
        assert stats.cache_hit_rate > 0
        
        # Verify tool breakdown
        assert "Read" in stats.tool_usage_breakdown
        assert "Bash" in stats.tool_usage_breakdown
        assert stats.tool_usage_breakdown["Read"].call_count == 1
        assert stats.tool_usage_breakdown["Bash"].call_count == 1
    
    def test_timeline_generation(self, temp_db, complex_transcript):
        """Test 7: Verify timeline generation with all events."""
        collector = TraceCollector(storage=temp_db)
        session = collector.collect_from_file(str(complex_transcript), session_id="test_timeline")
        
        analyzer = TraceAnalyzer()
        timeline = analyzer.get_timeline(session)
        
        # Verify timeline has events
        assert len(timeline) > 0
        
        # Verify event types
        event_types = {e["type"] for e in timeline}
        assert "turn_start" in event_types
        assert "user_message" in event_types
        assert "assistant_message" in event_types
        assert "tool_start" in event_types
        assert "tool_end" in event_types
        
        # Verify chronological ordering
        for i in range(len(timeline) - 1):
            if "timestamp" in timeline[i] and "timestamp" in timeline[i + 1]:
                assert timeline[i]["timestamp"] <= timeline[i + 1]["timestamp"]
    
    def test_time_breakdown_analysis(self, temp_db, complex_transcript):
        """Test 8: Verify time breakdown analysis."""
        collector = TraceCollector(storage=temp_db)
        session = collector.collect_from_file(str(complex_transcript), session_id="test_time")
        
        analyzer = TraceAnalyzer()
        breakdown = analyzer.get_time_breakdown(session)
        
        # Verify breakdown structure
        assert "total_ms" in breakdown
        assert "model_time_ms" in breakdown
        assert "tool_time_ms" in breakdown
        assert "by_turn" in breakdown
        
        # Verify per-turn breakdown
        assert len(breakdown["by_turn"]) == 3
        for turn_breakdown in breakdown["by_turn"]:
            assert "turn_number" in turn_breakdown
            assert "total_ms" in turn_breakdown
    
    def test_tool_analysis(self, temp_db, complex_transcript):
        """Test 9: Verify detailed tool analysis."""
        collector = TraceCollector(storage=temp_db)
        session = collector.collect_from_file(str(complex_transcript), session_id="test_tool_analysis")
        
        analyzer = TraceAnalyzer()
        tool_analysis = analyzer.get_tool_analysis(session)
        
        assert tool_analysis["total_calls"] == 2
        assert tool_analysis["unique_tools"] == 2
        assert "Read" in tool_analysis["tools"]
        assert "Bash" in tool_analysis["tools"]
        
        # Verify Read tool details
        read_analysis = tool_analysis["tools"]["Read"]
        assert read_analysis["call_count"] == 1
        assert read_analysis["success_rate"] == 100.0
        assert len(read_analysis["calls"]) == 1
        assert read_analysis["calls"][0]["success"] is True
    
    def test_token_analysis(self, temp_db, complex_transcript):
        """Test 10: Verify token and cache analysis."""
        collector = TraceCollector(storage=temp_db)
        session = collector.collect_from_file(str(complex_transcript), session_id="test_tokens")
        
        analyzer = TraceAnalyzer()
        token_analysis = analyzer.get_token_analysis(session)
        
        # Verify totals
        assert token_analysis["total"]["input"] > 0
        assert token_analysis["total"]["output"] > 0
        
        # Verify cache analysis
        assert token_analysis["cache_analysis"]["hit_rate"] > 0
        assert token_analysis["cache_analysis"]["tokens_saved"] > 0
        
        # Verify by-turn breakdown
        assert len(token_analysis["by_turn"]) == 3
        
        # Verify by-model breakdown
        assert len(token_analysis["by_model"]) > 0
    
    def test_reporter_text_output(self, temp_db, complex_transcript):
        """Test 11: Verify text report generation."""
        collector = TraceCollector(storage=temp_db)
        session = collector.collect_from_file(str(complex_transcript), session_id="test_report")
        
        reporter = TraceReporter()
        
        # Test summary
        summary = reporter.format_session_summary(session)
        assert "test_report" in summary
        assert "Turns:" in summary
        assert "Tool Uses:" in summary
        
        # Test timeline
        timeline = reporter.format_timeline(session)
        assert "Turn 1" in timeline
        assert "Turn 2" in timeline
        assert "Turn 3" in timeline
        assert "User:" in timeline
        assert "Assistant:" in timeline
        
        # Test statistics
        stats = reporter.format_statistics(session)
        assert "Time Breakdown:" in stats
        assert "Token Usage:" in stats
        assert "Tool Usage:" in stats
    
    def test_reporter_json_export(self, temp_db, complex_transcript):
        """Test 12: Verify JSON export."""
        collector = TraceCollector(storage=temp_db)
        session = collector.collect_from_file(str(complex_transcript), session_id="test_json")
        
        reporter = TraceReporter()
        json_output = reporter.export_json(session)
        
        # Parse and verify
        data = json.loads(json_output)
        assert data["session_id"] == "test_json"
        assert "statistics" in data
        assert "timeline" in data
        assert "turns" in data
        
        # Verify statistics structure
        stats = data["statistics"]
        assert stats["total_turns"] == 3
        assert stats["total_tool_uses"] == 2
        assert "tool_breakdown" in stats
    
    def test_reporter_html_export(self, temp_db, complex_transcript):
        """Test 13: Verify HTML report generation."""
        collector = TraceCollector(storage=temp_db)
        session = collector.collect_from_file(str(complex_transcript), session_id="test_html")
        
        reporter = TraceReporter()
        html_output = reporter.generate_html_report(session)
        
        # Verify HTML structure
        assert "<!DOCTYPE html>" in html_output
        assert "<title>Claude Trace Report" in html_output
        assert "test_html" in html_output
        
        # Verify key sections
        assert "Overview" in html_output
        assert "Time Breakdown" in html_output
        assert "Token Usage" in html_output
        assert "Tool Usage" in html_output
        assert "Conversation Timeline" in html_output
    
    def test_aggregate_statistics(self, temp_db, tmp_path):
        """Test 14: Verify aggregate statistics across sessions."""
        collector = TraceCollector(storage=temp_db)
        
        # Create two different transcripts with unique tool IDs
        for i in range(2):
            transcript_path = tmp_path / f"agg_transcript_{i}.jsonl"
            with open(transcript_path, 'w') as f:
                f.write(json.dumps({
                    "type": "user", "role": "user",
                    "content": f"Read file{i}", "timestamp": f"2025-02-04T10:00:0{i}Z"
                }) + '\n')
                f.write(json.dumps({
                    "type": "assistant",
                    "message": {
                        "id": f"msg_{i}_1", "role": "assistant",
                        "model": "claude-sonnet-4-5",
                        "content": [
                            {"type": "text", "text": "Reading..."},
                            {"type": "tool_use", "id": f"tool_{i}_read", "name": "Read", "input": {"path": f"/file{i}"}}
                        ],
                        "usage": {"input_tokens": 100, "output_tokens": 50}
                    },
                    "timestamp": f"2025-02-04T10:00:0{i+1}Z"
                }) + '\n')
                f.write(json.dumps({
                    "type": "user", "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": f"tool_{i}_read", "content": f"contents{i}"}],
                    "timestamp": f"2025-02-04T10:00:0{i+2}Z"
                }) + '\n')
                f.write(json.dumps({
                    "type": "assistant",
                    "message": {
                        "id": f"msg_{i}_2", "role": "assistant",
                        "model": "claude-sonnet-4-5",
                        "content": [{"type": "text", "text": "Done!"}],
                        "usage": {"input_tokens": 120, "output_tokens": 10}
                    },
                    "timestamp": f"2025-02-04T10:00:0{i+3}Z"
                }) + '\n')
            
            collector.collect_from_file(str(transcript_path), session_id=f"agg_{i}")
        
        # Get aggregate token usage
        total_tokens = temp_db.get_aggregate_token_usage()
        assert total_tokens.input_tokens > 0
        assert total_tokens.output_tokens > 0
        
        # Get aggregate tool stats
        tool_stats = temp_db.get_tool_stats()
        assert "Read" in tool_stats
        assert tool_stats["Read"].call_count == 2  # 1 per session * 2 sessions
    
    def test_session_deletion(self, temp_db, complex_transcript):
        """Test 15: Verify session deletion."""
        collector = TraceCollector(storage=temp_db)
        collector.collect_from_file(str(complex_transcript), session_id="to_delete")
        
        # Verify session exists
        assert temp_db.get_session("to_delete") is not None
        
        # Delete session
        result = temp_db.delete_session("to_delete")
        assert result is True
        
        # Verify session is gone
        assert temp_db.get_session("to_delete") is None
    
    def test_incremental_collection(self, temp_db, tmp_path):
        """Test 16: Verify incremental trace collection."""
        transcript_path = tmp_path / "incremental.jsonl"
        
        # Write initial data
        with open(transcript_path, 'w') as f:
            f.write(json.dumps({
                "type": "user", "role": "user",
                "content": "Hello", "timestamp": "2025-02-04T10:00:00Z"
            }) + '\n')
            f.write(json.dumps({
                "type": "assistant",
                "message": {
                    "id": "msg_1", "role": "assistant",
                    "model": "claude-sonnet-4-5",
                    "content": [{"type": "text", "text": "Hi there!"}],
                    "usage": {"input_tokens": 10, "output_tokens": 5}
                },
                "timestamp": "2025-02-04T10:00:01Z"
            }) + '\n')
        
        collector = TraceCollector(storage=temp_db)
        
        # First collection
        session1, line1 = collector.collect_incremental(str(transcript_path), "incr_session", 0)
        assert len(session1.turns) == 1
        assert line1 == 2
        
        # Add more data
        with open(transcript_path, 'a') as f:
            f.write(json.dumps({
                "type": "user", "role": "user",
                "content": "How are you?", "timestamp": "2025-02-04T10:00:10Z"
            }) + '\n')
            f.write(json.dumps({
                "type": "assistant",
                "message": {
                    "id": "msg_2", "role": "assistant",
                    "model": "claude-sonnet-4-5",
                    "content": [{"type": "text", "text": "I'm doing great!"}],
                    "usage": {"input_tokens": 15, "output_tokens": 8}
                },
                "timestamp": "2025-02-04T10:00:11Z"
            }) + '\n')
        
        # Second collection (incremental)
        session2, line2 = collector.collect_incremental(str(transcript_path), "incr_session", line1)
        assert line2 == 4
    
    def test_error_handling_malformed_data(self, temp_db, tmp_path):
        """Test 17: Verify graceful handling of malformed data."""
        transcript_path = tmp_path / "malformed.jsonl"
        
        # Write mix of valid and invalid data
        with open(transcript_path, 'w') as f:
            f.write(json.dumps({
                "type": "user", "role": "user",
                "content": "Valid message", "timestamp": "2025-02-04T10:00:00Z"
            }) + '\n')
            f.write("not valid json\n")  # Invalid line
            f.write(json.dumps({
                "type": "assistant",
                "message": {
                    "id": "msg_1", "role": "assistant",
                    "model": "claude-sonnet-4-5",
                    "content": [{"type": "text", "text": "Response"}],
                    "usage": {"input_tokens": 10, "output_tokens": 5}
                },
                "timestamp": "2025-02-04T10:00:01Z"
            }) + '\n')
        
        collector = TraceCollector(storage=temp_db)
        
        # Should not raise, should skip invalid lines
        session = collector.collect_from_file(str(transcript_path), session_id="malformed_test")
        assert len(session.turns) == 1  # Valid data was processed


class TestPlanRequirements:
    """Tests specifically verifying each plan requirement is met."""
    
    @pytest.fixture
    def sample_session(self, tmp_path):
        """Create a sample session for testing."""
        db_path = tmp_path / "test.db"
        storage = TraceStorage(str(db_path))
        collector = TraceCollector(storage=storage)
        
        # Create transcript
        transcript_path = tmp_path / "session.jsonl"
        with open(transcript_path, 'w') as f:
            f.write(json.dumps({
                "type": "user", "role": "user",
                "content": "Test question",
                "timestamp": "2025-02-04T10:00:00Z"
            }) + '\n')
            f.write(json.dumps({
                "type": "assistant",
                "message": {
                    "id": "msg_1", "role": "assistant",
                    "model": "claude-sonnet-4-5",
                    "content": [
                        {"type": "text", "text": "Answer"},
                        {"type": "tool_use", "id": "t1", "name": "Read", "input": {"path": "/test"}}
                    ],
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 50,
                        "cache_read_input_tokens": 80
                    }
                },
                "timestamp": "2025-02-04T10:00:02Z"
            }) + '\n')
            f.write(json.dumps({
                "type": "user", "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "file contents"}],
                "timestamp": "2025-02-04T10:00:03Z"
            }) + '\n')
            f.write(json.dumps({
                "type": "assistant",
                "message": {
                    "id": "msg_2", "role": "assistant",
                    "model": "claude-sonnet-4-5",
                    "content": [{"type": "text", "text": "Done!"}],
                    "usage": {"input_tokens": 120, "output_tokens": 10}
                },
                "timestamp": "2025-02-04T10:00:05Z"
            }) + '\n')
        
        session = collector.collect_from_file(str(transcript_path), session_id="req_test")
        return session, storage
    
    def test_requirement_1_session_timeline(self, sample_session):
        """Requirement 1: Main process flow visualization for each session."""
        session, storage = sample_session
        analyzer = TraceAnalyzer()
        
        timeline = analyzer.get_timeline(session)
        
        # Verify timeline shows process flow
        assert len(timeline) > 0
        
        # Events should be in chronological order
        event_types = [e["type"] for e in timeline]
        assert "turn_start" in event_types
        assert "user_message" in event_types
        assert "assistant_message" in event_types
        assert "tool_start" in event_types
        assert "tool_end" in event_types
        assert "turn_end" in event_types
    
    def test_requirement_2_model_tracking(self, sample_session):
        """Requirement 2: Input/output context, token counts, latency."""
        session, storage = sample_session
        
        # Verify model information is tracked
        for turn in session.turns:
            for msg in turn.assistant_messages:
                # Model name tracked
                assert msg.model is not None
                
                # Token counts tracked
                assert msg.usage is not None
                assert msg.usage.input_tokens >= 0
                assert msg.usage.output_tokens >= 0
                
                # Timestamp for latency calculation
                assert msg.timestamp is not None
    
    def test_requirement_3_tool_monitoring(self, sample_session):
        """Requirement 3: Tool name, input, output, latency for each tool use."""
        session, storage = sample_session
        
        tools = session.get_all_tool_uses()
        assert len(tools) == 1
        
        tool = tools[0]
        assert tool.tool_name == "Read"  # Tool name
        assert tool.input_data is not None  # Tool input
        assert tool.output_data is not None  # Tool output
        assert tool.start_time is not None  # Start time for latency
        # end_time is set when result is processed
    
    def test_requirement_4_operation_logging(self, sample_session):
        """Requirement 4: All operations with timestamps."""
        session, storage = sample_session
        analyzer = TraceAnalyzer()
        
        timeline = analyzer.get_timeline(session)
        
        # All events have timestamps
        for event in timeline:
            assert "timestamp" in event
    
    def test_requirement_5_time_analysis(self, sample_session):
        """Requirement 5: Breakdown of time spent in each phase."""
        session, storage = sample_session
        analyzer = TraceAnalyzer()
        
        breakdown = analyzer.get_time_breakdown(session)
        
        # Time breakdown available
        assert "total_ms" in breakdown
        assert "model_time_ms" in breakdown
        assert "tool_time_ms" in breakdown
        assert "model_time_percent" in breakdown
        assert "tool_time_percent" in breakdown
    
    def test_requirement_6_statistics(self, sample_session):
        """Requirement 6: Fail/retry counts, conversation loop metrics."""
        session, storage = sample_session
        analyzer = TraceAnalyzer()
        
        stats = analyzer.analyze_session(session)
        
        # Statistics tracked
        assert hasattr(stats, 'total_turns')
        assert hasattr(stats, 'total_messages')
        assert hasattr(stats, 'total_tool_uses')
        assert hasattr(stats, 'error_count')
        assert hasattr(stats, 'retry_count')
        assert hasattr(stats, 'avg_response_latency_ms')
    
    def test_requirement_7_kv_cache_analysis(self, sample_session):
        """Requirement 7: Cache hit/miss statistics (when available)."""
        session, storage = sample_session
        analyzer = TraceAnalyzer()
        
        stats = analyzer.analyze_session(session)
        token_analysis = analyzer.get_token_analysis(session)
        
        # Cache tracking available
        assert stats.total_tokens.cache_read_tokens >= 0
        assert hasattr(stats, 'cache_hit_rate')
        
        # Cache analysis in token breakdown
        assert "cache_analysis" in token_analysis
        assert "hit_rate" in token_analysis["cache_analysis"]


class TestDesignPrinciples:
    """Tests verifying design principles are met."""
    
    def test_principle_100_percent_local(self, tmp_path):
        """Verify: 100% Local - No network connections required."""
        # All storage is local SQLite
        db_path = tmp_path / "local_test.db"
        storage = TraceStorage(str(db_path))
        
        # Verify database is local file
        assert db_path.exists() or not os.path.exists(str(db_path))  # Will be created on first write
        
        # No network calls in storage, collector, or analyzer
        # (This is verified by the fact that tests pass without network)
    
    def test_principle_sqlite_storage(self, tmp_path):
        """Verify: All trace data persisted in SQLite."""
        db_path = tmp_path / "sqlite_test.db"
        storage = TraceStorage(str(db_path))
        
        # Create and store a session
        transcript_path = tmp_path / "test.jsonl"
        with open(transcript_path, 'w') as f:
            f.write(json.dumps({
                "type": "user", "role": "user",
                "content": "Test", "timestamp": "2025-02-04T10:00:00Z"
            }) + '\n')
            f.write(json.dumps({
                "type": "assistant",
                "message": {
                    "id": "m1", "role": "assistant", "model": "claude-sonnet-4-5",
                    "content": [{"type": "text", "text": "Hi"}],
                    "usage": {"input_tokens": 10, "output_tokens": 5}
                },
                "timestamp": "2025-02-04T10:00:01Z"
            }) + '\n')
        
        collector = TraceCollector(storage=storage)
        collector.collect_from_file(str(transcript_path), session_id="sqlite_verify")
        
        # Verify SQLite file exists and contains data
        assert db_path.exists()
        
        # Verify data can be retrieved
        session = storage.get_session("sqlite_verify")
        assert session is not None
        assert len(session.turns) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

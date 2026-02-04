"""Tests for claude_trace.models module."""

import pytest
from datetime import datetime, timedelta

from claude_trace.models import (
    ContentBlock,
    ContentType,
    Message,
    MessageRole,
    Session,
    SessionStats,
    TokenUsage,
    ToolStats,
    ToolUse,
    Turn,
)


@pytest.mark.unit
class TestTokenUsage:
    """Tests for TokenUsage dataclass."""
    
    def test_total_tokens(self):
        """Test total_tokens property."""
        usage = TokenUsage(input_tokens=100, output_tokens=50)
        assert usage.total_tokens == 150
    
    def test_cache_hit_rate_with_hits(self):
        """Test cache_hit_rate with cache hits."""
        usage = TokenUsage(input_tokens=100, cache_read_tokens=40)
        assert usage.cache_hit_rate == 40.0
    
    def test_cache_hit_rate_zero_input(self):
        """Test cache_hit_rate with zero input tokens."""
        usage = TokenUsage(input_tokens=0, cache_read_tokens=10)
        assert usage.cache_hit_rate == 0.0
    
    def test_from_dict(self):
        """Test creating TokenUsage from dictionary."""
        data = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_read_input_tokens": 30,
            "cache_creation_input_tokens": 20
        }
        usage = TokenUsage.from_dict(data)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.cache_read_tokens == 30
        assert usage.cache_creation_tokens == 20
    
    def test_from_dict_none(self):
        """Test creating TokenUsage from None."""
        usage = TokenUsage.from_dict(None)
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
    
    def test_add_token_usage(self):
        """Test adding two TokenUsage objects."""
        usage1 = TokenUsage(input_tokens=100, output_tokens=50)
        usage2 = TokenUsage(input_tokens=80, output_tokens=40)
        result = usage1 + usage2
        assert result.input_tokens == 180
        assert result.output_tokens == 90


@pytest.mark.unit
class TestContentBlock:
    """Tests for ContentBlock dataclass."""
    
    def test_from_dict_text(self):
        """Test creating text content block."""
        data = {"type": "text", "text": "Hello world"}
        block = ContentBlock.from_dict(data)
        assert block.type == ContentType.TEXT
        assert block.text == "Hello world"
    
    def test_from_dict_thinking(self):
        """Test creating thinking content block."""
        data = {"type": "thinking", "thinking": "Let me think..."}
        block = ContentBlock.from_dict(data)
        assert block.type == ContentType.THINKING
        assert block.thinking == "Let me think..."
    
    def test_from_dict_tool_use(self):
        """Test creating tool_use content block."""
        data = {
            "type": "tool_use",
            "id": "tool_123",
            "name": "Read",
            "input": {"file_path": "/test.txt"}
        }
        block = ContentBlock.from_dict(data)
        assert block.type == ContentType.TOOL_USE
        assert block.tool_use_id == "tool_123"
        assert block.tool_name == "Read"
        assert block.tool_input == {"file_path": "/test.txt"}
    
    def test_from_dict_tool_result(self):
        """Test creating tool_result content block."""
        data = {
            "type": "tool_result",
            "tool_use_id": "tool_123",
            "content": "File contents here"
        }
        block = ContentBlock.from_dict(data)
        assert block.type == ContentType.TOOL_RESULT
        assert block.tool_use_id == "tool_123"
        assert block.tool_result == "File contents here"


@pytest.mark.unit
class TestMessage:
    """Tests for Message dataclass."""
    
    def test_text_content(self):
        """Test extracting text content from message."""
        msg = Message(
            message_id="msg_1",
            role=MessageRole.ASSISTANT,
            content=[
                ContentBlock(type=ContentType.TEXT, text="Hello"),
                ContentBlock(type=ContentType.THINKING, thinking="Hmm"),
                ContentBlock(type=ContentType.TEXT, text="World")
            ],
            timestamp=datetime.now()
        )
        assert msg.text_content == "Hello\nWorld"
    
    def test_has_tool_use(self):
        """Test detecting tool use in message."""
        msg = Message(
            message_id="msg_1",
            role=MessageRole.ASSISTANT,
            content=[
                ContentBlock(type=ContentType.TEXT, text="I'll help"),
                ContentBlock(
                    type=ContentType.TOOL_USE,
                    tool_use_id="tool_1",
                    tool_name="Read"
                )
            ],
            timestamp=datetime.now()
        )
        assert msg.has_tool_use is True
    
    def test_no_tool_use(self):
        """Test message without tool use."""
        msg = Message(
            message_id="msg_1",
            role=MessageRole.ASSISTANT,
            content=[ContentBlock(type=ContentType.TEXT, text="Hello")],
            timestamp=datetime.now()
        )
        assert msg.has_tool_use is False


@pytest.mark.unit
class TestToolUse:
    """Tests for ToolUse dataclass."""
    
    def test_duration_ms(self):
        """Test duration calculation."""
        start = datetime(2025, 1, 1, 10, 0, 0)
        end = datetime(2025, 1, 1, 10, 0, 1, 500000)  # 1.5 seconds later
        tool = ToolUse(
            tool_id="tool_1",
            tool_name="Bash",
            input_data={"command": "ls"},
            start_time=start,
            end_time=end
        )
        assert tool.duration_ms == 1500
    
    def test_duration_ms_no_times(self):
        """Test duration with missing times."""
        tool = ToolUse(
            tool_id="tool_1",
            tool_name="Bash",
            input_data={}
        )
        assert tool.duration_ms is None
    
    def test_duration_seconds(self):
        """Test duration in seconds."""
        start = datetime(2025, 1, 1, 10, 0, 0)
        end = datetime(2025, 1, 1, 10, 0, 2)  # 2 seconds later
        tool = ToolUse(
            tool_id="tool_1",
            tool_name="Bash",
            input_data={},
            start_time=start,
            end_time=end
        )
        assert tool.duration_seconds == 2.0


@pytest.mark.unit
class TestToolStats:
    """Tests for ToolStats dataclass."""
    
    def test_avg_duration(self):
        """Test average duration calculation."""
        stats = ToolStats(
            tool_name="Read",
            call_count=10,
            total_duration_ms=1000
        )
        assert stats.avg_duration_ms == 100.0
    
    def test_avg_duration_zero_calls(self):
        """Test average duration with zero calls."""
        stats = ToolStats(tool_name="Read", call_count=0)
        assert stats.avg_duration_ms == 0.0
    
    def test_success_rate(self):
        """Test success rate calculation."""
        stats = ToolStats(
            tool_name="Read",
            call_count=10,
            success_count=8,
            error_count=2
        )
        assert stats.success_rate == 80.0


@pytest.mark.unit
class TestTurn:
    """Tests for Turn dataclass."""
    
    def test_duration_ms(self):
        """Test turn duration calculation."""
        start = datetime(2025, 1, 1, 10, 0, 0)
        end = datetime(2025, 1, 1, 10, 0, 30)  # 30 seconds later
        
        user_msg = Message(
            message_id="u1",
            role=MessageRole.USER,
            content=[ContentBlock(type=ContentType.TEXT, text="Hi")],
            timestamp=start
        )
        
        turn = Turn(
            turn_id="turn_1",
            turn_number=1,
            user_message=user_msg,
            start_time=start,
            end_time=end
        )
        assert turn.duration_ms == 30000
    
    def test_total_tokens(self):
        """Test total tokens calculation."""
        user_msg = Message(
            message_id="u1",
            role=MessageRole.USER,
            content=[],
            timestamp=datetime.now()
        )
        
        assistant_msgs = [
            Message(
                message_id="a1",
                role=MessageRole.ASSISTANT,
                content=[],
                timestamp=datetime.now(),
                usage=TokenUsage(input_tokens=100, output_tokens=50)
            ),
            Message(
                message_id="a2",
                role=MessageRole.ASSISTANT,
                content=[],
                timestamp=datetime.now(),
                usage=TokenUsage(input_tokens=80, output_tokens=40)
            )
        ]
        
        turn = Turn(
            turn_id="turn_1",
            turn_number=1,
            user_message=user_msg,
            assistant_messages=assistant_msgs
        )
        
        total = turn.total_tokens
        assert total.input_tokens == 180
        assert total.output_tokens == 90


@pytest.mark.unit
class TestSession:
    """Tests for Session dataclass."""
    
    def test_duration_ms(self):
        """Test session duration calculation."""
        start = datetime(2025, 1, 1, 10, 0, 0)
        end = datetime(2025, 1, 1, 10, 5, 0)  # 5 minutes later
        
        session = Session(
            session_id="sess_1",
            start_time=start,
            end_time=end
        )
        assert session.duration_ms == 300000  # 5 minutes in ms
    
    def test_turn_count(self):
        """Test turn count property."""
        session = Session(
            session_id="sess_1",
            turns=[
                Turn(turn_id="t1", turn_number=1, user_message=None),
                Turn(turn_id="t2", turn_number=2, user_message=None)
            ]
        )
        assert session.turn_count == 2
    
    def test_get_all_tool_uses(self):
        """Test getting all tool uses from session."""
        tool1 = ToolUse(tool_id="t1", tool_name="Read", input_data={})
        tool2 = ToolUse(tool_id="t2", tool_name="Bash", input_data={})
        
        session = Session(
            session_id="sess_1",
            turns=[
                Turn(turn_id="turn1", turn_number=1, user_message=None, tool_uses=[tool1]),
                Turn(turn_id="turn2", turn_number=2, user_message=None, tool_uses=[tool2])
            ]
        )
        
        all_tools = session.get_all_tool_uses()
        assert len(all_tools) == 2
        assert all_tools[0].tool_name == "Read"
        assert all_tools[1].tool_name == "Bash"


@pytest.mark.unit
class TestSessionStats:
    """Tests for SessionStats dataclass."""
    
    def test_cache_hit_rate(self):
        """Test cache hit rate from total tokens."""
        stats = SessionStats(
            total_tokens=TokenUsage(input_tokens=100, cache_read_tokens=40)
        )
        assert stats.cache_hit_rate == 40.0
    
    def test_model_time_percent(self):
        """Test model time percentage calculation."""
        stats = SessionStats(
            total_duration_ms=100000,
            model_time_ms=70000
        )
        assert stats.model_time_percent == 70.0
    
    def test_tool_time_percent(self):
        """Test tool time percentage calculation."""
        stats = SessionStats(
            total_duration_ms=100000,
            tool_time_ms=30000
        )
        assert stats.tool_time_percent == 30.0

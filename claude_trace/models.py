"""
Data models for Claude Code local tracing.

These dataclasses represent the structured trace data collected from
Claude Code sessions.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


class MessageRole(str, Enum):
    """Role of a message in the conversation."""
    USER = "user"
    ASSISTANT = "assistant"


class ContentType(str, Enum):
    """Type of content block in a message."""
    TEXT = "text"
    THINKING = "thinking"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"


@dataclass
class ContentBlock:
    """A single content block within a message."""
    type: ContentType
    text: Optional[str] = None
    thinking: Optional[str] = None
    tool_use_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_result: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContentBlock":
        """Create ContentBlock from a dictionary."""
        block_type = data.get("type", "text")
        
        if block_type == "text":
            return cls(
                type=ContentType.TEXT,
                text=data.get("text", "")
            )
        elif block_type == "thinking":
            return cls(
                type=ContentType.THINKING,
                thinking=data.get("thinking", "")
            )
        elif block_type == "tool_use":
            return cls(
                type=ContentType.TOOL_USE,
                tool_use_id=data.get("id"),
                tool_name=data.get("name"),
                tool_input=data.get("input", {})
            )
        elif block_type == "tool_result":
            return cls(
                type=ContentType.TOOL_RESULT,
                tool_use_id=data.get("tool_use_id"),
                tool_result=str(data.get("content", ""))
            )
        else:
            return cls(type=ContentType.TEXT, text=str(data))


@dataclass
class TokenUsage:
    """Token usage statistics for a message or session."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    
    @property
    def total_tokens(self) -> int:
        """Calculate total tokens used."""
        return self.input_tokens + self.output_tokens
    
    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate as a percentage."""
        if self.input_tokens == 0:
            return 0.0
        return (self.cache_read_tokens / self.input_tokens) * 100
    
    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "TokenUsage":
        """Create TokenUsage from a dictionary."""
        if not data:
            return cls()
        return cls(
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            cache_read_tokens=data.get("cache_read_input_tokens", 0),
            cache_creation_tokens=data.get("cache_creation_input_tokens", 0)
        )
    
    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        """Add two TokenUsage objects together."""
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens
        )


@dataclass
class Message:
    """A single message in the conversation."""
    message_id: str
    role: MessageRole
    content: List[ContentBlock]
    timestamp: datetime
    model: Optional[str] = None
    usage: Optional[TokenUsage] = None
    raw_data: Optional[Dict[str, Any]] = None

    @property
    def text_content(self) -> str:
        """Get the combined text content of all text blocks."""
        texts = []
        for block in self.content:
            if block.type == ContentType.TEXT and block.text:
                texts.append(block.text)
        return "\n".join(texts)
    
    @property
    def tool_uses(self) -> List[ContentBlock]:
        """Get all tool_use blocks from this message."""
        return [b for b in self.content if b.type == ContentType.TOOL_USE]
    
    @property
    def has_tool_use(self) -> bool:
        """Check if this message contains tool uses."""
        return any(b.type == ContentType.TOOL_USE for b in self.content)


@dataclass
class ToolUse:
    """A tool use instance with timing and result information."""
    tool_id: str
    tool_name: str
    input_data: Dict[str, Any]
    output_data: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    success: bool = True
    error: Optional[str] = None
    
    @property
    def duration_ms(self) -> Optional[int]:
        """Calculate duration in milliseconds."""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() * 1000)
        return None
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate duration in seconds."""
        ms = self.duration_ms
        return ms / 1000.0 if ms else None


@dataclass
class ToolStats:
    """Statistics for a specific tool."""
    tool_name: str
    call_count: int = 0
    total_duration_ms: int = 0
    success_count: int = 0
    error_count: int = 0
    
    @property
    def avg_duration_ms(self) -> float:
        """Calculate average duration in milliseconds."""
        if self.call_count == 0:
            return 0.0
        return self.total_duration_ms / self.call_count
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        if self.call_count == 0:
            return 100.0
        return (self.success_count / self.call_count) * 100


@dataclass
class Turn:
    """A single conversation turn (user input + assistant response(s))."""
    turn_id: str
    turn_number: int
    user_message: Message
    assistant_messages: List[Message] = field(default_factory=list)
    tool_uses: List[ToolUse] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def duration_ms(self) -> Optional[int]:
        """Calculate duration in milliseconds."""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() * 1000)
        return None
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate duration in seconds."""
        ms = self.duration_ms
        return ms / 1000.0 if ms else None
    
    @property
    def total_tokens(self) -> TokenUsage:
        """Calculate total token usage for this turn."""
        total = TokenUsage()
        for msg in self.assistant_messages:
            if msg.usage:
                total = total + msg.usage
        return total
    
    @property
    def tool_count(self) -> int:
        """Get the number of tool uses in this turn."""
        return len(self.tool_uses)


@dataclass
class SessionStats:
    """Aggregate statistics for a session."""
    total_turns: int = 0
    total_messages: int = 0
    total_tool_uses: int = 0
    total_tokens: TokenUsage = field(default_factory=TokenUsage)
    avg_response_latency_ms: float = 0.0
    tool_usage_breakdown: Dict[str, ToolStats] = field(default_factory=dict)
    retry_count: int = 0
    error_count: int = 0
    
    # Time breakdown
    total_duration_ms: int = 0
    model_time_ms: int = 0
    tool_time_ms: int = 0
    
    @property
    def cache_hit_rate(self) -> float:
        """Calculate overall cache hit rate."""
        return self.total_tokens.cache_hit_rate
    
    @property
    def model_time_percent(self) -> float:
        """Calculate percentage of time spent in model inference."""
        if self.total_duration_ms == 0:
            return 0.0
        return (self.model_time_ms / self.total_duration_ms) * 100
    
    @property
    def tool_time_percent(self) -> float:
        """Calculate percentage of time spent in tool execution."""
        if self.total_duration_ms == 0:
            return 0.0
        return (self.tool_time_ms / self.total_duration_ms) * 100


@dataclass
class Session:
    """A complete Claude Code session with all trace data."""
    session_id: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    turns: List[Turn] = field(default_factory=list)
    statistics: Optional[SessionStats] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_ms(self) -> Optional[int]:
        """Calculate session duration in milliseconds."""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() * 1000)
        return None
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate session duration in seconds."""
        ms = self.duration_ms
        return ms / 1000.0 if ms else None
    
    @property
    def turn_count(self) -> int:
        """Get the number of turns in this session."""
        return len(self.turns)
    
    def get_all_tool_uses(self) -> List[ToolUse]:
        """Get all tool uses across all turns."""
        all_tools = []
        for turn in self.turns:
            all_tools.extend(turn.tool_uses)
        return all_tools
    
    def get_all_messages(self) -> List[Message]:
        """Get all messages (user + assistant) across all turns."""
        all_messages = []
        for turn in self.turns:
            all_messages.append(turn.user_message)
            all_messages.extend(turn.assistant_messages)
        return all_messages

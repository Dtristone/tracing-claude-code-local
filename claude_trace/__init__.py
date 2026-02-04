"""
Claude Code Local Tracing

A local-only tracing solution for Claude Code CLI that captures detailed traces
without requiring any remote server connections.
"""

__version__ = "0.1.0"
__author__ = "Claude Trace Contributors"

from claude_trace.models import (
    Session,
    Turn,
    Message,
    ContentBlock,
    ToolUse,
    TokenUsage,
    SessionStats,
    ToolStats,
)
from claude_trace.collector import TraceCollector
from claude_trace.analyzer import TraceAnalyzer
from claude_trace.storage import TraceStorage

__all__ = [
    "Session",
    "Turn",
    "Message",
    "ContentBlock",
    "ToolUse",
    "TokenUsage",
    "SessionStats",
    "ToolStats",
    "TraceCollector",
    "TraceAnalyzer",
    "TraceStorage",
]

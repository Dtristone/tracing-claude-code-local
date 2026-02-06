"""
Claude Code Local Tracing

A local-only tracing solution for Claude Code CLI that captures detailed traces
without requiring any remote server connections.

Supports:
- Transcript-based tracing from JSONL files
- OTEL metrics capture for token usage when OTEL_METRICS_EXPORTER=console
- Local resource monitoring (CPU, memory, network, disk I/O)
- Background process monitoring for Claude CLI
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
from claude_trace.otel_collector import (
    OtelMetricsCollector,
    OtelMetricsParser,
    OtelSessionMetrics,
    OtelMetric,
    OtelMetricDataPoint,
)
from claude_trace.resource_monitor import (
    ResourceMonitor,
    ResourceSnapshot,
    StageResourceUsage,
    ClaudeProcessMonitor,
    ProcessResourceSnapshot,
    get_resource_monitor_availability,
    align_resource_with_trace,
)

__all__ = [
    # Models
    "Session",
    "Turn",
    "Message",
    "ContentBlock",
    "ToolUse",
    "TokenUsage",
    "SessionStats",
    "ToolStats",
    # Core components
    "TraceCollector",
    "TraceAnalyzer",
    "TraceStorage",
    # OTEL components
    "OtelMetricsCollector",
    "OtelMetricsParser",
    "OtelSessionMetrics",
    "OtelMetric",
    "OtelMetricDataPoint",
    # Resource monitoring
    "ResourceMonitor",
    "ResourceSnapshot",
    "StageResourceUsage",
    "ClaudeProcessMonitor",
    "ProcessResourceSnapshot",
    "get_resource_monitor_availability",
    "align_resource_with_trace",
]

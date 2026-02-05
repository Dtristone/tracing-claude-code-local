"""
Trace analyzer for Claude Code local tracing.

Provides analysis and statistics computation for collected trace data.
"""

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from claude_trace.models import (
    Message,
    Session,
    SessionStats,
    TokenUsage,
    ToolStats,
    ToolUse,
    Turn,
)
from claude_trace.storage import TraceStorage


class TraceAnalyzer:
    """Analyzes trace data and computes statistics."""
    
    def __init__(self, storage: Optional[TraceStorage] = None):
        """
        Initialize the analyzer.
        
        Args:
            storage: Optional TraceStorage for loading sessions
        """
        self.storage = storage
    
    def analyze_session(self, session: Session) -> SessionStats:
        """
        Compute comprehensive statistics for a session.
        
        Args:
            session: Session to analyze
            
        Returns:
            SessionStats with computed metrics
        """
        stats = SessionStats()
        
        # Basic counts
        stats.total_turns = len(session.turns)
        stats.total_messages = sum(
            1 + len(turn.assistant_messages) 
            for turn in session.turns
        )
        stats.total_tool_uses = sum(
            len(turn.tool_uses) 
            for turn in session.turns
        )
        
        # Token usage
        for turn in session.turns:
            for msg in turn.assistant_messages:
                if msg.usage:
                    stats.total_tokens = stats.total_tokens + msg.usage
        
        # Tool usage breakdown
        tool_stats = defaultdict(lambda: ToolStats(tool_name=""))
        for turn in session.turns:
            for tool in turn.tool_uses:
                name = tool.tool_name
                if name not in tool_stats:
                    tool_stats[name] = ToolStats(tool_name=name)
                ts = tool_stats[name]
                ts.call_count += 1
                if tool.duration_ms:
                    ts.total_duration_ms += tool.duration_ms
                    stats.tool_time_ms += tool.duration_ms
                if tool.success:
                    ts.success_count += 1
                else:
                    ts.error_count += 1
                    stats.error_count += 1
        
        stats.tool_usage_breakdown = dict(tool_stats)
        
        # Response latency (time between user message and first assistant response)
        latencies = []
        for turn in session.turns:
            if turn.user_message and turn.assistant_messages:
                first_response = turn.assistant_messages[0]
                latency_ms = (
                    first_response.timestamp - turn.user_message.timestamp
                ).total_seconds() * 1000
                latencies.append(latency_ms)
        
        if latencies:
            stats.avg_response_latency_ms = sum(latencies) / len(latencies)
        
        # Time breakdown
        if session.duration_ms:
            stats.total_duration_ms = session.duration_ms
            # Estimate model time as total - tool time
            stats.model_time_ms = stats.total_duration_ms - stats.tool_time_ms
        
        return stats
    
    def analyze_session_with_otel(
        self, 
        session: Session,
        otel_summary: Optional[Dict[str, Any]] = None
    ) -> SessionStats:
        """
        Compute comprehensive statistics for a session, enriched with OTEL metrics.
        
        When transcript token counts are 0, uses OTEL metrics instead.
        
        Args:
            session: Session to analyze
            otel_summary: Optional OTEL metrics summary from storage
            
        Returns:
            SessionStats with computed metrics, enriched with OTEL data
        """
        stats = self.analyze_session(session)
        
        # If no OTEL data, return standard stats
        if not otel_summary:
            if self.storage:
                otel_summary = self.storage.get_otel_summary(session.session_id)
            if not otel_summary:
                return stats
        
        # Enrich stats with OTEL data when transcript data is missing/zero
        otel_tokens = TokenUsage(
            input_tokens=otel_summary.get('input_tokens', 0),
            output_tokens=otel_summary.get('output_tokens', 0),
            cache_read_tokens=otel_summary.get('cache_read_tokens', 0),
            cache_creation_tokens=otel_summary.get('cache_creation_tokens', 0)
        )
        
        # If transcript tokens are 0, use OTEL tokens
        if stats.total_tokens.total_tokens == 0 and otel_tokens.total_tokens > 0:
            stats.total_tokens = otel_tokens
        
        # Add OTEL-specific metrics if available
        if otel_summary.get('api_latency_ms', 0) > 0:
            if stats.avg_response_latency_ms == 0:
                stats.avg_response_latency_ms = otel_summary['api_latency_ms']
        
        if otel_summary.get('errors', 0) > stats.error_count:
            stats.error_count = otel_summary['errors']
        
        return stats
    
    def get_otel_analysis(self, session_id: str) -> Dict[str, Any]:
        """
        Get OTEL-specific analysis for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Dictionary with OTEL analysis
        """
        if not self.storage:
            return {"error": "No storage configured"}
        
        summary = self.storage.get_otel_summary(session_id)
        metrics = self.storage.get_otel_metrics(session_id)
        
        if not summary:
            return {"available": False, "message": "No OTEL metrics for this session"}
        
        # Group metrics by name
        metrics_by_name = defaultdict(list)
        for m in metrics:
            metrics_by_name[m['metric_name']].append(m)
        
        # Calculate statistics per metric
        metrics_analysis = {}
        for name, data_points in metrics_by_name.items():
            values = [dp['metric_value'] for dp in data_points]
            metrics_analysis[name] = {
                "count": len(values),
                "total": sum(values),
                "avg": sum(values) / len(values) if values else 0,
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
                "type": data_points[0].get('metric_type', 'counter') if data_points else 'counter',
                "unit": data_points[0].get('unit', '') if data_points else ''
            }
        
        return {
            "available": True,
            "session_id": session_id,
            "collected_at": summary.get('collected_at'),
            "summary": {
                "input_tokens": summary.get('input_tokens', 0),
                "output_tokens": summary.get('output_tokens', 0),
                "cache_read_tokens": summary.get('cache_read_tokens', 0),
                "cache_creation_tokens": summary.get('cache_creation_tokens', 0),
                "total_tokens": (
                    summary.get('input_tokens', 0) + 
                    summary.get('output_tokens', 0)
                ),
                "cache_hit_rate": (
                    summary.get('cache_read_tokens', 0) / 
                    max(summary.get('input_tokens', 1), 1) * 100
                ),
                "api_calls": summary.get('api_calls', 0),
                "api_latency_ms": summary.get('api_latency_ms', 0),
                "tool_calls": summary.get('tool_calls', 0),
                "errors": summary.get('errors', 0)
            },
            "metrics": metrics_analysis
        }
    
    def get_timeline(self, session: Session) -> List[Dict[str, Any]]:
        """
        Generate a timeline of events for a session.
        
        Args:
            session: Session to generate timeline for
            
        Returns:
            List of timeline events with timestamps
        """
        timeline = []
        
        for turn in session.turns:
            # Turn start
            if turn.start_time:
                timeline.append({
                    "type": "turn_start",
                    "turn_number": turn.turn_number,
                    "timestamp": turn.start_time.isoformat(),
                    "datetime": turn.start_time
                })
            
            # User message
            if turn.user_message:
                timeline.append({
                    "type": "user_message",
                    "turn_number": turn.turn_number,
                    "timestamp": turn.user_message.timestamp.isoformat(),
                    "datetime": turn.user_message.timestamp,
                    "content": turn.user_message.text_content[:200]
                })
            
            # Assistant messages
            for i, msg in enumerate(turn.assistant_messages):
                timeline.append({
                    "type": "assistant_message",
                    "turn_number": turn.turn_number,
                    "message_index": i,
                    "timestamp": msg.timestamp.isoformat(),
                    "datetime": msg.timestamp,
                    "model": msg.model,
                    "content": msg.text_content[:200],
                    "has_tool_use": msg.has_tool_use,
                    "tokens": {
                        "input": msg.usage.input_tokens if msg.usage else 0,
                        "output": msg.usage.output_tokens if msg.usage else 0,
                        "cache_read": msg.usage.cache_read_tokens if msg.usage else 0
                    }
                })
            
            # Tool uses
            for tool in turn.tool_uses:
                if tool.start_time:
                    timeline.append({
                        "type": "tool_start",
                        "turn_number": turn.turn_number,
                        "timestamp": tool.start_time.isoformat(),
                        "datetime": tool.start_time,
                        "tool_name": tool.tool_name,
                        "tool_id": tool.tool_id,
                        "input": tool.input_data
                    })
                
                if tool.end_time:
                    timeline.append({
                        "type": "tool_end",
                        "turn_number": turn.turn_number,
                        "timestamp": tool.end_time.isoformat(),
                        "datetime": tool.end_time,
                        "tool_name": tool.tool_name,
                        "tool_id": tool.tool_id,
                        "duration_ms": tool.duration_ms,
                        "success": tool.success,
                        "output_preview": (tool.output_data or "")[:200]
                    })
            
            # Turn end
            if turn.end_time:
                timeline.append({
                    "type": "turn_end",
                    "turn_number": turn.turn_number,
                    "timestamp": turn.end_time.isoformat(),
                    "datetime": turn.end_time,
                    "duration_ms": turn.duration_ms
                })
        
        # Sort by timestamp
        timeline.sort(key=lambda x: x.get("datetime", datetime.min))
        
        # Remove datetime objects (not JSON serializable)
        for event in timeline:
            event.pop("datetime", None)
        
        return timeline
    
    def get_tool_analysis(
        self, 
        session: Session,
        tool_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze tool usage in a session.
        
        Args:
            session: Session to analyze
            tool_name: Optional filter for specific tool
            
        Returns:
            Tool analysis with statistics and details
        """
        all_tools = session.get_all_tool_uses()
        
        if tool_name:
            all_tools = [t for t in all_tools if t.tool_name == tool_name]
        
        # Compute stats
        by_name = defaultdict(list)
        for tool in all_tools:
            by_name[tool.tool_name].append(tool)
        
        analysis = {
            "total_calls": len(all_tools),
            "unique_tools": len(by_name),
            "tools": {}
        }
        
        for name, tools in by_name.items():
            durations = [t.duration_ms for t in tools if t.duration_ms]
            successes = sum(1 for t in tools if t.success)
            errors = sum(1 for t in tools if not t.success)
            
            analysis["tools"][name] = {
                "call_count": len(tools),
                "success_count": successes,
                "error_count": errors,
                "success_rate": (successes / len(tools) * 100) if tools else 100,
                "total_duration_ms": sum(durations),
                "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
                "min_duration_ms": min(durations) if durations else 0,
                "max_duration_ms": max(durations) if durations else 0,
                "calls": [
                    {
                        "tool_id": t.tool_id,
                        "input": t.input_data,
                        "output_preview": (t.output_data or "")[:100],
                        "duration_ms": t.duration_ms,
                        "success": t.success,
                        "error": t.error
                    }
                    for t in tools
                ]
            }
        
        return analysis
    
    def get_token_analysis(self, session: Session) -> Dict[str, Any]:
        """
        Analyze token usage in a session.
        
        Args:
            session: Session to analyze
            
        Returns:
            Token analysis with breakdown by turn and model
        """
        analysis = {
            "total": {
                "input": 0,
                "output": 0,
                "cache_read": 0,
                "cache_creation": 0,
                "total": 0
            },
            "by_turn": [],
            "by_model": defaultdict(lambda: {
                "input": 0, "output": 0, "calls": 0
            }),
            "cache_analysis": {
                "hit_rate": 0,
                "tokens_saved": 0
            }
        }
        
        total_cache_read = 0
        total_input = 0
        
        for turn in session.turns:
            turn_tokens = TokenUsage()
            for msg in turn.assistant_messages:
                if msg.usage:
                    turn_tokens = turn_tokens + msg.usage
                    analysis["by_model"][msg.model or "unknown"]["input"] += msg.usage.input_tokens
                    analysis["by_model"][msg.model or "unknown"]["output"] += msg.usage.output_tokens
                    analysis["by_model"][msg.model or "unknown"]["calls"] += 1
            
            analysis["by_turn"].append({
                "turn_number": turn.turn_number,
                "input": turn_tokens.input_tokens,
                "output": turn_tokens.output_tokens,
                "cache_read": turn_tokens.cache_read_tokens,
                "cache_creation": turn_tokens.cache_creation_tokens,
                "total": turn_tokens.total_tokens
            })
            
            analysis["total"]["input"] += turn_tokens.input_tokens
            analysis["total"]["output"] += turn_tokens.output_tokens
            analysis["total"]["cache_read"] += turn_tokens.cache_read_tokens
            analysis["total"]["cache_creation"] += turn_tokens.cache_creation_tokens
            
            total_cache_read += turn_tokens.cache_read_tokens
            total_input += turn_tokens.input_tokens
        
        analysis["total"]["total"] = (
            analysis["total"]["input"] + analysis["total"]["output"]
        )
        
        # Cache analysis
        if total_input > 0:
            analysis["cache_analysis"]["hit_rate"] = (total_cache_read / total_input) * 100
            analysis["cache_analysis"]["tokens_saved"] = total_cache_read
        
        # Convert defaultdict to dict
        analysis["by_model"] = dict(analysis["by_model"])
        
        return analysis
    
    def get_time_breakdown(self, session: Session) -> Dict[str, Any]:
        """
        Analyze time spent in different phases.
        
        Args:
            session: Session to analyze
            
        Returns:
            Time breakdown analysis
        """
        total_ms = session.duration_ms or 0
        tool_time_ms = 0
        
        # Calculate tool time
        for turn in session.turns:
            for tool in turn.tool_uses:
                if tool.duration_ms:
                    tool_time_ms += tool.duration_ms
        
        # Estimate model time
        model_time_ms = max(0, total_ms - tool_time_ms)
        
        breakdown = {
            "total_ms": total_ms,
            "total_formatted": self._format_duration(total_ms),
            "model_time_ms": model_time_ms,
            "model_time_formatted": self._format_duration(model_time_ms),
            "model_time_percent": (model_time_ms / total_ms * 100) if total_ms > 0 else 0,
            "tool_time_ms": tool_time_ms,
            "tool_time_formatted": self._format_duration(tool_time_ms),
            "tool_time_percent": (tool_time_ms / total_ms * 100) if total_ms > 0 else 0,
            "by_turn": []
        }
        
        for turn in session.turns:
            turn_ms = turn.duration_ms or 0
            turn_tool_ms = sum(t.duration_ms or 0 for t in turn.tool_uses)
            turn_model_ms = max(0, turn_ms - turn_tool_ms)
            
            breakdown["by_turn"].append({
                "turn_number": turn.turn_number,
                "total_ms": turn_ms,
                "model_time_ms": turn_model_ms,
                "tool_time_ms": turn_tool_ms,
                "tool_count": len(turn.tool_uses)
            })
        
        return breakdown
    
    def compare_sessions(
        self, 
        sessions: List[Session]
    ) -> Dict[str, Any]:
        """
        Compare multiple sessions.
        
        Args:
            sessions: List of sessions to compare
            
        Returns:
            Comparison analysis
        """
        comparison = {
            "session_count": len(sessions),
            "sessions": [],
            "averages": {
                "turns": 0,
                "duration_ms": 0,
                "tokens": 0,
                "tool_uses": 0
            }
        }
        
        total_turns = 0
        total_duration = 0
        total_tokens = 0
        total_tools = 0
        
        for session in sessions:
            stats = self.analyze_session(session)
            
            session_data = {
                "session_id": session.session_id,
                "turns": stats.total_turns,
                "duration_ms": stats.total_duration_ms,
                "total_tokens": stats.total_tokens.total_tokens,
                "tool_uses": stats.total_tool_uses,
                "cache_hit_rate": stats.cache_hit_rate
            }
            comparison["sessions"].append(session_data)
            
            total_turns += stats.total_turns
            total_duration += stats.total_duration_ms
            total_tokens += stats.total_tokens.total_tokens
            total_tools += stats.total_tool_uses
        
        if sessions:
            comparison["averages"]["turns"] = total_turns / len(sessions)
            comparison["averages"]["duration_ms"] = total_duration / len(sessions)
            comparison["averages"]["tokens"] = total_tokens / len(sessions)
            comparison["averages"]["tool_uses"] = total_tools / len(sessions)
        
        return comparison
    
    def _format_duration(self, ms: int) -> str:
        """Format duration in milliseconds to human-readable string."""
        if ms < 1000:
            return f"{ms}ms"
        
        seconds = ms / 1000.0
        if seconds < 60:
            return f"{seconds:.1f}s"
        
        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.1f}s"

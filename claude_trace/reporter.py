"""
Report generation for Claude Code local tracing.

Provides formatted output for trace data in various formats.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from claude_trace.analyzer import TraceAnalyzer
from claude_trace.models import Session, SessionStats
from claude_trace.utils import (
    clean_model_name,
    format_bytes,
    format_duration,
    format_percentage,
    format_tokens,
    truncate_string,
)


class TraceReporter:
    """Generates formatted reports from trace data."""
    
    def __init__(self, analyzer: Optional[TraceAnalyzer] = None):
        """
        Initialize the reporter.
        
        Args:
            analyzer: Optional TraceAnalyzer instance
        """
        self.analyzer = analyzer or TraceAnalyzer()
    
    def format_session_summary(self, session: Session) -> str:
        """
        Format a brief summary of a session.
        
        Args:
            session: Session to summarize
            
        Returns:
            Formatted summary string
        """
        stats = self.analyzer.analyze_session(session)
        
        lines = [
            f"Session: {session.session_id}",
            f"Started: {session.start_time.strftime('%Y-%m-%d %H:%M:%S') if session.start_time else 'N/A'}",
            f"Duration: {format_duration(session.duration_ms)}",
            f"Turns: {stats.total_turns}",
            f"Tool Uses: {stats.total_tool_uses}",
            f"Total Tokens: {format_tokens(stats.total_tokens.total_tokens)}",
        ]
        
        return "\n".join(lines)
    
    def format_timeline(self, session: Session, verbose: bool = False) -> str:
        """
        Format a timeline view of a session.
        
        Args:
            session: Session to format
            verbose: Include detailed content
            
        Returns:
            Formatted timeline string
        """
        lines = [
            f"Session: {session.session_id}",
            f"Started: {session.start_time.strftime('%Y-%m-%d %H:%M:%S') if session.start_time else 'N/A'}",
            ""
        ]
        
        for turn in session.turns:
            # Turn header
            time_range = ""
            if turn.start_time and turn.end_time:
                start = turn.start_time.strftime('%H:%M:%S')
                end = turn.end_time.strftime('%H:%M:%S')
                duration = format_duration(turn.duration_ms)
                time_range = f"[{start} - {end}] ({duration})"
            
            lines.append(f"Turn {turn.turn_number} {time_range}")
            
            # User message
            user_content = turn.user_message.text_content if turn.user_message else ""
            user_preview = truncate_string(user_content.replace('\n', ' '), 60)
            lines.append(f"├── User: \"{user_preview}\"")
            
            # Assistant messages and tools
            items = []
            
            for msg in turn.assistant_messages:
                items.append(("assistant", msg.timestamp, msg))
            
            for tool in turn.tool_uses:
                if tool.start_time:
                    items.append(("tool", tool.start_time, tool))
            
            # Sort by timestamp
            items.sort(key=lambda x: x[1])
            
            for i, (item_type, _, item) in enumerate(items):
                is_last = (i == len(items) - 1)
                prefix = "└──" if is_last else "├──"
                
                if item_type == "assistant":
                    content_preview = truncate_string(
                        item.text_content.replace('\n', ' '), 
                        50
                    )
                    lines.append(f"{prefix} Assistant: \"{content_preview}\"")
                    
                    # Model and usage info
                    model = clean_model_name(item.model) if item.model else "unknown"
                    inner_prefix = "    " if is_last else "│   "
                    lines.append(f"{inner_prefix}├── Model: {model}")
                    
                    if item.usage:
                        tokens_in = format_tokens(item.usage.input_tokens)
                        tokens_out = format_tokens(item.usage.output_tokens)
                        cache = format_tokens(item.usage.cache_read_tokens)
                        lines.append(
                            f"{inner_prefix}├── Tokens: {tokens_in} in / {tokens_out} out (cache: {cache} read)"
                        )
                    
                    if item.has_tool_use:
                        tool_names = [b.tool_name for b in item.tool_uses]
                        lines.append(f"{inner_prefix}└── Tools called: {', '.join(tool_names)}")
                
                elif item_type == "tool":
                    tool_input = json.dumps(item.input_data) if item.input_data else ""
                    input_preview = truncate_string(tool_input, 40)
                    lines.append(f"{prefix} Tool: {item.tool_name} ({input_preview})")
                    
                    inner_prefix = "    " if is_last else "│   "
                    duration = format_duration(item.duration_ms)
                    lines.append(f"{inner_prefix}├── Duration: {duration}")
                    
                    if item.output_data:
                        output_preview = truncate_string(
                            item.output_data.replace('\n', ' '), 
                            50
                        )
                        lines.append(f"{inner_prefix}└── Output: {output_preview}")
                    
                    if not item.success:
                        lines.append(f"{inner_prefix}└── ERROR: {item.error}")
            
            lines.append("")
        
        # Summary
        stats = self.analyzer.analyze_session(session)
        lines.extend([
            "Summary:",
            f"  Total Duration: {format_duration(stats.total_duration_ms)}",
            f"  Turns: {stats.total_turns}",
            f"  Tool Uses: {stats.total_tool_uses}",
            f"  Total Tokens: {format_tokens(stats.total_tokens.input_tokens)} in / "
            f"{format_tokens(stats.total_tokens.output_tokens)} out",
            f"  Cache Hit Rate: {format_percentage(stats.cache_hit_rate)}",
        ])
        
        return "\n".join(lines)
    
    def format_statistics(self, session: Session) -> str:
        """
        Format detailed statistics for a session.
        
        Args:
            session: Session to format
            
        Returns:
            Formatted statistics string
        """
        stats = self.analyzer.analyze_session(session)
        time_breakdown = self.analyzer.get_time_breakdown(session)
        
        lines = [
            f"Session Statistics: {session.session_id}",
            "",
            "Time Breakdown:",
            f"  Total Duration:     {time_breakdown['total_formatted']}",
            f"  Model Inference:    {time_breakdown['model_time_formatted']} "
            f"({format_percentage(time_breakdown['model_time_percent'])})",
            f"  Tool Execution:     {time_breakdown['tool_time_formatted']} "
            f"({format_percentage(time_breakdown['tool_time_percent'])})",
            "",
            "Token Usage:",
            f"  Input Tokens:       {format_tokens(stats.total_tokens.input_tokens)}",
            f"  Output Tokens:      {format_tokens(stats.total_tokens.output_tokens)}",
            f"  Cache Read:         {format_tokens(stats.total_tokens.cache_read_tokens)} "
            f"({format_percentage(stats.cache_hit_rate)} hit rate)",
            f"  Cache Created:      {format_tokens(stats.total_tokens.cache_creation_tokens)}",
            "",
            "Tool Usage:",
        ]
        
        for name, tool_stats in stats.tool_usage_breakdown.items():
            avg_duration = format_duration(int(tool_stats.avg_duration_ms))
            total_duration = format_duration(tool_stats.total_duration_ms)
            lines.append(
                f"  {name:12s} {tool_stats.call_count:3d} calls, "
                f"avg {avg_duration:>8s}, total {total_duration:>8s}"
            )
        
        if not stats.tool_usage_breakdown:
            lines.append("  (no tools used)")
        
        lines.extend([
            "",
            "Performance:",
            f"  Avg Response Latency: {format_duration(int(stats.avg_response_latency_ms))}",
            f"  Retry Count: {stats.retry_count}",
            f"  Error Count: {stats.error_count}",
        ])
        
        return "\n".join(lines)
    
    def format_tool_report(
        self, 
        session: Session, 
        tool_name: Optional[str] = None
    ) -> str:
        """
        Format a tool usage report.
        
        Args:
            session: Session to report on
            tool_name: Optional filter for specific tool
            
        Returns:
            Formatted tool report string
        """
        analysis = self.analyzer.get_tool_analysis(session, tool_name)
        
        lines = [
            f"Tool Usage Report: {session.session_id}",
            "",
            f"Total Tool Calls: {analysis['total_calls']}",
            f"Unique Tools: {analysis['unique_tools']}",
            ""
        ]
        
        for name, data in analysis["tools"].items():
            lines.extend([
                f"Tool: {name}",
                f"  Calls: {data['call_count']}",
                f"  Success Rate: {format_percentage(data['success_rate'])}",
                f"  Total Duration: {format_duration(data['total_duration_ms'])}",
                f"  Avg Duration: {format_duration(int(data['avg_duration_ms']))}",
                f"  Min Duration: {format_duration(data['min_duration_ms'])}",
                f"  Max Duration: {format_duration(data['max_duration_ms'])}",
                ""
            ])
            
            # Show individual calls
            lines.append("  Calls:")
            for call in data["calls"][:10]:  # Limit to 10 calls
                status = "✓" if call["success"] else "✗"
                duration = format_duration(call["duration_ms"])
                input_preview = truncate_string(
                    json.dumps(call["input"]), 
                    40
                )
                lines.append(f"    {status} {duration:>8s} - {input_preview}")
            
            if len(data["calls"]) > 10:
                lines.append(f"    ... and {len(data['calls']) - 10} more")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def format_session_list(
        self, 
        sessions: List[Dict[str, Any]]
    ) -> str:
        """
        Format a list of sessions.
        
        Args:
            sessions: List of session summaries
            
        Returns:
            Formatted session list string
        """
        if not sessions:
            return "No sessions found."
        
        lines = [
            "Recent Sessions:",
            "",
            f"{'Session ID':<40} {'Started':<20} {'Turns':>6} {'Tools':>6} {'Duration':>10}",
            "-" * 90
        ]
        
        for s in sessions:
            session_id = truncate_string(s["session_id"], 38)
            started = s.get("start_time", "N/A")[:19]
            turns = s.get("turn_count", 0)
            tools = s.get("tool_count", 0)
            duration = format_duration(s.get("duration_ms"))
            
            lines.append(
                f"{session_id:<40} {started:<20} {turns:>6} {tools:>6} {duration:>10}"
            )
        
        return "\n".join(lines)
    
    def format_otel_metrics(self, session_id: str, otel_analysis: Dict[str, Any]) -> str:
        """
        Format OTEL metrics for display.
        
        Args:
            session_id: Session ID
            otel_analysis: OTEL analysis data from analyzer
            
        Returns:
            Formatted OTEL metrics string
        """
        if not otel_analysis.get('available', False):
            return f"No OTEL metrics available for session: {session_id}"
        
        summary = otel_analysis.get('summary', {})
        metrics = otel_analysis.get('metrics', {})
        
        lines = [
            f"OTEL Metrics: {session_id}",
            f"Collected: {otel_analysis.get('collected_at', 'N/A')}",
            "",
            "Token Usage (from OTEL):",
            f"  Input Tokens:       {format_tokens(summary.get('input_tokens', 0))}",
            f"  Output Tokens:      {format_tokens(summary.get('output_tokens', 0))}",
            f"  Total Tokens:       {format_tokens(summary.get('total_tokens', 0))}",
            f"  Cache Read:         {format_tokens(summary.get('cache_read_tokens', 0))}",
            f"  Cache Created:      {format_tokens(summary.get('cache_creation_tokens', 0))}",
            f"  Cache Hit Rate:     {format_percentage(summary.get('cache_hit_rate', 0))}",
            "",
            "API Metrics:",
            f"  API Calls:          {summary.get('api_calls', 0)}",
            f"  Avg Latency:        {format_duration(int(summary.get('api_latency_ms', 0)))}",
            f"  Tool Calls:         {summary.get('tool_calls', 0)}",
            f"  Errors:             {summary.get('errors', 0)}",
        ]
        
        if metrics:
            lines.extend(["", "All Metrics:"])
            for name, data in sorted(metrics.items()):
                unit = f" ({data.get('unit', '')})" if data.get('unit') else ""
                lines.append(
                    f"  {name}{unit}: total={data.get('total', 0):.2f}, "
                    f"avg={data.get('avg', 0):.2f}, count={data.get('count', 0)}"
                )
        
        return "\n".join(lines)
    
    def format_statistics_with_otel(
        self, 
        session: Session,
        include_otel: bool = True
    ) -> str:
        """
        Format detailed statistics for a session, including OTEL metrics.
        
        Args:
            session: Session to format
            include_otel: Whether to include OTEL metrics if available
            
        Returns:
            Formatted statistics string
        """
        # Use OTEL-enriched stats if available
        if include_otel:
            stats = self.analyzer.analyze_session_with_otel(session)
        else:
            stats = self.analyzer.analyze_session(session)
        
        time_breakdown = self.analyzer.get_time_breakdown(session)
        
        lines = [
            f"Session Statistics: {session.session_id}",
            "",
            "Time Breakdown:",
            f"  Total Duration:     {time_breakdown['total_formatted']}",
            f"  Model Inference:    {time_breakdown['model_time_formatted']} "
            f"({format_percentage(time_breakdown['model_time_percent'])})",
            f"  Tool Execution:     {time_breakdown['tool_time_formatted']} "
            f"({format_percentage(time_breakdown['tool_time_percent'])})",
            "",
            "Token Usage:",
            f"  Input Tokens:       {format_tokens(stats.total_tokens.input_tokens)}",
            f"  Output Tokens:      {format_tokens(stats.total_tokens.output_tokens)}",
            f"  Cache Read:         {format_tokens(stats.total_tokens.cache_read_tokens)} "
            f"({format_percentage(stats.cache_hit_rate)} hit rate)",
            f"  Cache Created:      {format_tokens(stats.total_tokens.cache_creation_tokens)}",
        ]
        
        # Check if we have OTEL data
        has_otel = False
        if self.analyzer.storage:
            has_otel = self.analyzer.storage.has_otel_metrics(session.session_id)
        
        if has_otel:
            lines.append("  (enriched with OTEL metrics)")
        
        lines.extend([
            "",
            "Tool Usage:",
        ])
        
        for name, tool_stats in stats.tool_usage_breakdown.items():
            avg_duration = format_duration(int(tool_stats.avg_duration_ms))
            total_duration = format_duration(tool_stats.total_duration_ms)
            lines.append(
                f"  {name:12s} {tool_stats.call_count:3d} calls, "
                f"avg {avg_duration:>8s}, total {total_duration:>8s}"
            )
        
        if not stats.tool_usage_breakdown:
            lines.append("  (no tools used)")
        
        lines.extend([
            "",
            "Performance:",
            f"  Avg Response Latency: {format_duration(int(stats.avg_response_latency_ms))}",
            f"  Retry Count: {stats.retry_count}",
            f"  Error Count: {stats.error_count}",
        ])
        
        return "\n".join(lines)
    
    def export_json(self, session: Session) -> str:
        """
        Export session data as JSON.
        
        Args:
            session: Session to export
            
        Returns:
            JSON string
        """
        stats = self.analyzer.analyze_session(session)
        timeline = self.analyzer.get_timeline(session)
        
        export_data = {
            "session_id": session.session_id,
            "start_time": session.start_time.isoformat() if session.start_time else None,
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "duration_ms": session.duration_ms,
            "statistics": {
                "total_turns": stats.total_turns,
                "total_messages": stats.total_messages,
                "total_tool_uses": stats.total_tool_uses,
                "total_tokens": {
                    "input": stats.total_tokens.input_tokens,
                    "output": stats.total_tokens.output_tokens,
                    "cache_read": stats.total_tokens.cache_read_tokens,
                    "cache_creation": stats.total_tokens.cache_creation_tokens
                },
                "cache_hit_rate": stats.cache_hit_rate,
                "avg_response_latency_ms": stats.avg_response_latency_ms,
                "error_count": stats.error_count,
                "tool_breakdown": {
                    name: {
                        "calls": ts.call_count,
                        "success_rate": ts.success_rate,
                        "total_duration_ms": ts.total_duration_ms,
                        "avg_duration_ms": ts.avg_duration_ms
                    }
                    for name, ts in stats.tool_usage_breakdown.items()
                }
            },
            "timeline": timeline,
            "turns": [
                {
                    "turn_number": turn.turn_number,
                    "start_time": turn.start_time.isoformat() if turn.start_time else None,
                    "end_time": turn.end_time.isoformat() if turn.end_time else None,
                    "duration_ms": turn.duration_ms,
                    "user_message": turn.user_message.text_content if turn.user_message else "",
                    "assistant_messages": [
                        {
                            "content": msg.text_content,
                            "model": msg.model,
                            "tokens": {
                                "input": msg.usage.input_tokens if msg.usage else 0,
                                "output": msg.usage.output_tokens if msg.usage else 0
                            }
                        }
                        for msg in turn.assistant_messages
                    ],
                    "tool_uses": [
                        {
                            "tool_name": t.tool_name,
                            "input": t.input_data,
                            "output_preview": (t.output_data or "")[:500],
                            "duration_ms": t.duration_ms,
                            "success": t.success
                        }
                        for t in turn.tool_uses
                    ]
                }
                for turn in session.turns
            ]
        }
        
        return json.dumps(export_data, indent=2)
    
    def generate_html_report(self, session: Session) -> str:
        """
        Generate an HTML report for a session.
        
        Args:
            session: Session to report on
            
        Returns:
            HTML string
        """
        stats = self.analyzer.analyze_session(session)
        time_breakdown = self.analyzer.get_time_breakdown(session)
        
        # Build HTML
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Claude Trace Report - {session.session_id}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1, h2, h3 {{
            color: #333;
            margin-top: 0;
        }}
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }}
        .stat-box {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #2563eb;
        }}
        .stat-label {{
            color: #666;
            font-size: 0.9em;
        }}
        .turn {{
            border-left: 3px solid #2563eb;
            padding-left: 15px;
            margin-bottom: 20px;
        }}
        .message {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
        }}
        .message.user {{
            background: #e3f2fd;
        }}
        .message.assistant {{
            background: #f3e5f5;
        }}
        .tool {{
            background: #fff3e0;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
            font-family: monospace;
            font-size: 0.9em;
        }}
        .success {{
            color: #2e7d32;
        }}
        .error {{
            color: #c62828;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            text-align: left;
            padding: 8px;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background: #f5f5f5;
        }}
    </style>
</head>
<body>
    <h1>Claude Trace Report</h1>
    <p>Session: <code>{session.session_id}</code></p>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <div class="card">
        <h2>Overview</h2>
        <div class="stat-grid">
            <div class="stat-box">
                <div class="stat-value">{format_duration(session.duration_ms)}</div>
                <div class="stat-label">Duration</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{stats.total_turns}</div>
                <div class="stat-label">Turns</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{stats.total_tool_uses}</div>
                <div class="stat-label">Tool Uses</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{format_tokens(stats.total_tokens.total_tokens)}</div>
                <div class="stat-label">Total Tokens</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{format_percentage(stats.cache_hit_rate)}</div>
                <div class="stat-label">Cache Hit Rate</div>
            </div>
        </div>
    </div>
    
    <div class="card">
        <h2>Time Breakdown</h2>
        <table>
            <tr>
                <th>Phase</th>
                <th>Duration</th>
                <th>Percentage</th>
            </tr>
            <tr>
                <td>Model Inference</td>
                <td>{time_breakdown['model_time_formatted']}</td>
                <td>{format_percentage(time_breakdown['model_time_percent'])}</td>
            </tr>
            <tr>
                <td>Tool Execution</td>
                <td>{time_breakdown['tool_time_formatted']}</td>
                <td>{format_percentage(time_breakdown['tool_time_percent'])}</td>
            </tr>
        </table>
    </div>
    
    <div class="card">
        <h2>Token Usage</h2>
        <table>
            <tr>
                <th>Type</th>
                <th>Count</th>
            </tr>
            <tr>
                <td>Input Tokens</td>
                <td>{format_tokens(stats.total_tokens.input_tokens)}</td>
            </tr>
            <tr>
                <td>Output Tokens</td>
                <td>{format_tokens(stats.total_tokens.output_tokens)}</td>
            </tr>
            <tr>
                <td>Cache Read</td>
                <td>{format_tokens(stats.total_tokens.cache_read_tokens)}</td>
            </tr>
            <tr>
                <td>Cache Created</td>
                <td>{format_tokens(stats.total_tokens.cache_creation_tokens)}</td>
            </tr>
        </table>
    </div>
    
    <div class="card">
        <h2>Tool Usage</h2>
        <table>
            <tr>
                <th>Tool</th>
                <th>Calls</th>
                <th>Success Rate</th>
                <th>Avg Duration</th>
                <th>Total Duration</th>
            </tr>
"""
        
        for name, tool_stats in stats.tool_usage_breakdown.items():
            html += f"""            <tr>
                <td>{name}</td>
                <td>{tool_stats.call_count}</td>
                <td>{format_percentage(tool_stats.success_rate)}</td>
                <td>{format_duration(int(tool_stats.avg_duration_ms))}</td>
                <td>{format_duration(tool_stats.total_duration_ms)}</td>
            </tr>
"""
        
        if not stats.tool_usage_breakdown:
            html += """            <tr><td colspan="5">No tools used</td></tr>
"""
        
        html += """        </table>
    </div>
    
    <div class="card">
        <h2>Conversation Timeline</h2>
"""
        
        for turn in session.turns:
            duration = format_duration(turn.duration_ms) if turn.duration_ms else "N/A"
            html += f"""        <div class="turn">
            <h3>Turn {turn.turn_number} ({duration})</h3>
"""
            
            if turn.user_message:
                content = truncate_string(turn.user_message.text_content, 500)
                html += f"""            <div class="message user">
                <strong>User:</strong> {content}
            </div>
"""
            
            for msg in turn.assistant_messages:
                content = truncate_string(msg.text_content, 500)
                model = clean_model_name(msg.model) if msg.model else "unknown"
                tokens = ""
                if msg.usage:
                    tokens = f" ({msg.usage.input_tokens} in / {msg.usage.output_tokens} out)"
                html += f"""            <div class="message assistant">
                <strong>Assistant</strong> [{model}]{tokens}: {content}
            </div>
"""
            
            for tool in turn.tool_uses:
                status_class = "success" if tool.success else "error"
                status = "✓" if tool.success else "✗"
                duration = format_duration(tool.duration_ms)
                input_str = json.dumps(tool.input_data, indent=2)[:200]
                output_str = (tool.output_data or "")[:200]
                html += f"""            <div class="tool">
                <span class="{status_class}">{status}</span> <strong>{tool.tool_name}</strong> ({duration})
                <br>Input: <pre>{input_str}</pre>
                <br>Output: {output_str}
            </div>
"""
            
            html += """        </div>
"""
        
        html += """    </div>
</body>
</html>
"""
        
        return html
    
    def generate_unified_timeline_report(
        self,
        session: Session,
        resource_data: Optional[Dict[str, Any]] = None,
        otel_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a unified timeline report with operations, time, resources, and I/O.
        
        Args:
            session: Session to report on
            resource_data: Optional resource monitoring data from storage
            otel_data: Optional OTEL metrics data from storage
            
        Returns:
            Formatted timeline report string
        """
        lines = [
            f"Unified Timeline Report: {session.session_id}",
            "=" * 60,
            f"Started: {session.start_time.strftime('%Y-%m-%d %H:%M:%S') if session.start_time else 'N/A'}",
            f"Duration: {format_duration(session.duration_ms)}",
            ""
        ]
        
        # Header for timeline table
        lines.append(f"{'Stage':<30} {'Time':>10} {'CPU':>8} {'Memory':>10} {'Net I/O':>15}")
        lines.append("-" * 80)
        
        # Build stage timeline
        for turn in session.turns:
            turn_name = f"Turn {turn.turn_number}"
            duration = format_duration(turn.duration_ms)
            
            # Get resource data for this turn if available
            cpu_str = "N/A"
            mem_str = "N/A"
            net_str = "N/A"
            
            if resource_data and "stages" in resource_data:
                for stage in resource_data["stages"]:
                    if stage.get("stage_id") == turn.turn_id:
                        cpu_str = f"{stage.get('avg_cpu_percent', 0):.1f}%"
                        mem_bytes = stage.get("max_memory_bytes", 0)
                        mem_str = format_bytes(mem_bytes)
                        net_in = stage.get("network_bytes_recv_delta", 0)
                        net_out = stage.get("network_bytes_sent_delta", 0)
                        net_str = f"↓{format_bytes(net_in)}/↑{format_bytes(net_out)}"
                        break
            
            lines.append(f"{turn_name:<30} {duration:>10} {cpu_str:>8} {mem_str:>10} {net_str:>15}")
            
            # Show tool operations within turn
            for tool in turn.tool_uses:
                tool_name = f"  └─ {tool.tool_name}"
                tool_duration = format_duration(tool.duration_ms)
                status = "✓" if tool.success else "✗"
                
                tool_cpu = "N/A"
                tool_mem = "N/A"
                tool_net = "N/A"
                
                if resource_data and "stages" in resource_data:
                    for stage in resource_data["stages"]:
                        if stage.get("stage_id") == tool.tool_id:
                            tool_cpu = f"{stage.get('avg_cpu_percent', 0):.1f}%"
                            tool_mem = format_bytes(stage.get("max_memory_bytes", 0))
                            tool_net_in = stage.get("network_bytes_recv_delta", 0)
                            tool_net_out = stage.get("network_bytes_sent_delta", 0)
                            tool_net = f"↓{format_bytes(tool_net_in)}/↑{format_bytes(tool_net_out)}"
                            break
                
                lines.append(f"{tool_name:<30} {tool_duration:>10} {tool_cpu:>8} {tool_mem:>10} {tool_net:>15} {status}")
        
        lines.append("")
        lines.append("=" * 60)
        
        # Summary section
        stats = self.analyzer.analyze_session(session)
        
        lines.extend([
            "Summary:",
            f"  Total Turns: {stats.total_turns}",
            f"  Total Tool Uses: {stats.total_tool_uses}",
            f"  Total Tokens: {format_tokens(stats.total_tokens.total_tokens)}",
            f"  Cache Hit Rate: {format_percentage(stats.cache_hit_rate)}",
        ])
        
        # Add resource summary if available
        if resource_data:
            summary = resource_data.get("resource_summary") or resource_data
            if summary:
                lines.extend([
                    "",
                    "Resource Summary:",
                    f"  Avg CPU: {summary.get('cpu', {}).get('avg_percent', 0):.1f}%",
                    f"  Max CPU: {summary.get('cpu', {}).get('max_percent', 0):.1f}%",
                    f"  Avg Memory: {summary.get('memory', {}).get('avg_percent', 0):.1f}%",
                    f"  Network: ↓{format_bytes(summary.get('network', {}).get('bytes_recv', 0))} / "
                    f"↑{format_bytes(summary.get('network', {}).get('bytes_sent', 0))}",
                    f"  Disk: R{format_bytes(summary.get('disk', {}).get('read_bytes', 0))} / "
                    f"W{format_bytes(summary.get('disk', {}).get('write_bytes', 0))}",
                ])
        
        # Add OTEL summary if available
        if otel_data:
            lines.extend([
                "",
                "OTEL Metrics:",
                f"  API Calls: {otel_data.get('api_calls', 0)}",
                f"  Avg API Latency: {format_duration(int(otel_data.get('api_latency_ms', 0)))}",
                f"  Errors: {otel_data.get('errors', 0)}",
            ])
        
        return "\n".join(lines)
    
    def generate_unified_html_report(
        self,
        session: Session,
        resource_data: Optional[Dict[str, Any]] = None,
        otel_data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate a unified HTML report with timeline, resources, and expandable details.
        
        Args:
            session: Session to report on
            resource_data: Optional resource monitoring data from storage
            otel_data: Optional OTEL metrics data from storage
            
        Returns:
            HTML string
        """
        stats = self.analyzer.analyze_session(session)
        time_breakdown = self.analyzer.get_time_breakdown(session)
        
        # Build stage data for timeline
        stages_json = []
        for turn in session.turns:
            stage_data = {
                "id": turn.turn_id,
                "name": f"Turn {turn.turn_number}",
                "type": "turn",
                "start": turn.start_time.isoformat() if turn.start_time else None,
                "end": turn.end_time.isoformat() if turn.end_time else None,
                "duration_ms": turn.duration_ms,
                "input_summary": truncate_string(
                    turn.user_message.text_content if turn.user_message else "",
                    100
                ),
                "output_summary": truncate_string(
                    turn.assistant_messages[-1].text_content if turn.assistant_messages else "",
                    100
                ),
                "tokens": {
                    "input": sum(m.usage.input_tokens for m in turn.assistant_messages if m.usage),
                    "output": sum(m.usage.output_tokens for m in turn.assistant_messages if m.usage),
                },
                "resources": {},
                "tools": []
            }
            
            # Add resource data if available
            if resource_data and "stages" in resource_data:
                for stage in resource_data["stages"]:
                    if stage.get("stage_id") == turn.turn_id:
                        stage_data["resources"] = {
                            "cpu_avg": stage.get("avg_cpu_percent", 0),
                            "cpu_max": stage.get("max_cpu_percent", 0),
                            "memory_max": stage.get("max_memory_bytes", 0),
                            "memory_delta": stage.get("memory_delta_bytes", 0),
                            "net_recv": stage.get("network_bytes_recv_delta", 0),
                            "net_sent": stage.get("network_bytes_sent_delta", 0),
                        }
                        break
            
            # Add tool data
            for tool in turn.tool_uses:
                tool_data = {
                    "id": tool.tool_id,
                    "name": tool.tool_name,
                    "duration_ms": tool.duration_ms,
                    "success": tool.success,
                    "input_summary": truncate_string(json.dumps(tool.input_data), 100),
                    "output_summary": truncate_string(tool.output_data or "", 100),
                    "resources": {},
                }
                
                # Add tool resource data if available
                if resource_data and "stages" in resource_data:
                    for stage in resource_data["stages"]:
                        if stage.get("stage_id") == tool.tool_id:
                            tool_data["resources"] = {
                                "cpu_avg": stage.get("avg_cpu_percent", 0),
                                "memory_max": stage.get("max_memory_bytes", 0),
                                "net_recv": stage.get("network_bytes_recv_delta", 0),
                                "net_sent": stage.get("network_bytes_sent_delta", 0),
                            }
                            break
                
                stage_data["tools"].append(tool_data)
            
            stages_json.append(stage_data)
        
        stages_json_str = json.dumps(stages_json, indent=2)
        
        # Resource summary
        resource_summary = {}
        if resource_data:
            rs = resource_data.get("resource_summary") or resource_data
            resource_summary = {
                "cpu_avg": rs.get("cpu", {}).get("avg_percent", 0),
                "cpu_max": rs.get("cpu", {}).get("max_percent", 0),
                "memory_avg": rs.get("memory", {}).get("avg_percent", 0),
                "memory_max": rs.get("memory", {}).get("max_percent", 0),
                "net_recv": rs.get("network", {}).get("bytes_recv", 0),
                "net_sent": rs.get("network", {}).get("bytes_sent", 0),
                "disk_read": rs.get("disk", {}).get("read_bytes", 0),
                "disk_write": rs.get("disk", {}).get("write_bytes", 0),
            }
        
        resource_summary_str = json.dumps(resource_summary, indent=2)
        
        # OTEL summary
        otel_summary_str = json.dumps(otel_data or {}, indent=2)
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Unified Timeline Report - {session.session_id}</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1, h2, h3 {{ color: #333; margin-top: 0; }}
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }}
        .stat-box {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 4px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 1.5em;
            font-weight: bold;
            color: #2563eb;
        }}
        .stat-label {{
            color: #666;
            font-size: 0.9em;
        }}
        .timeline {{
            position: relative;
            padding-left: 30px;
        }}
        .timeline::before {{
            content: '';
            position: absolute;
            left: 10px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: #2563eb;
        }}
        .stage {{
            position: relative;
            margin-bottom: 20px;
            padding: 15px;
            background: #fff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
        }}
        .stage::before {{
            content: '';
            position: absolute;
            left: -24px;
            top: 20px;
            width: 10px;
            height: 10px;
            background: #2563eb;
            border-radius: 50%;
        }}
        .stage-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
        }}
        .stage-title {{
            font-weight: bold;
            font-size: 1.1em;
        }}
        .stage-time {{
            color: #666;
            font-size: 0.9em;
        }}
        .stage-resources {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #e5e7eb;
        }}
        .resource-item {{
            text-align: center;
            padding: 8px;
            background: #f8f9fa;
            border-radius: 4px;
        }}
        .resource-value {{ font-weight: bold; color: #2563eb; }}
        .resource-label {{ font-size: 0.8em; color: #666; }}
        .stage-details {{
            display: none;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #e5e7eb;
        }}
        .stage.expanded .stage-details {{
            display: block;
        }}
        .io-section {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
        }}
        .io-title {{
            font-weight: bold;
            margin-bottom: 5px;
        }}
        .io-content {{
            font-family: monospace;
            font-size: 0.9em;
            white-space: pre-wrap;
            max-height: 150px;
            overflow-y: auto;
        }}
        .tool-item {{
            margin: 10px 0;
            padding: 10px;
            background: #fff3e0;
            border-radius: 4px;
            border-left: 3px solid #ff9800;
        }}
        .tool-header {{ display: flex; justify-content: space-between; align-items: center; }}
        .tool-name {{ font-weight: bold; }}
        .success {{ color: #2e7d32; }}
        .error {{ color: #c62828; }}
        .toggle-btn {{
            background: none;
            border: none;
            cursor: pointer;
            font-size: 1.2em;
        }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ text-align: left; padding: 8px; border-bottom: 1px solid #ddd; }}
        th {{ background: #f5f5f5; }}
    </style>
</head>
<body>
    <h1>Unified Timeline Report</h1>
    <p>Session: <code>{session.session_id}</code></p>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <div class="card">
        <h2>Overview</h2>
        <div class="stat-grid">
            <div class="stat-box">
                <div class="stat-value">{format_duration(session.duration_ms)}</div>
                <div class="stat-label">Duration</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{stats.total_turns}</div>
                <div class="stat-label">Turns</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{stats.total_tool_uses}</div>
                <div class="stat-label">Tool Uses</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{format_tokens(stats.total_tokens.total_tokens)}</div>
                <div class="stat-label">Tokens</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{format_percentage(stats.cache_hit_rate)}</div>
                <div class="stat-label">Cache Hit</div>
            </div>
"""
        
        # Add resource stats if available
        if resource_summary:
            html += f"""            <div class="stat-box">
                <div class="stat-value">{resource_summary.get('cpu_avg', 0):.1f}%</div>
                <div class="stat-label">Avg CPU</div>
            </div>
            <div class="stat-box">
                <div class="stat-value">{resource_summary.get('memory_avg', 0):.1f}%</div>
                <div class="stat-label">Avg Memory</div>
            </div>
"""
        
        html += """        </div>
    </div>
    
    <div class="card">
        <h2>Timeline</h2>
        <p><em>Click on a stage to expand details. Shows operation, time, resources, and I/O for each stage.</em></p>
        <div class="timeline" id="timeline">
"""
        
        # Generate timeline stages
        for i, turn in enumerate(session.turns):
            duration = format_duration(turn.duration_ms) if turn.duration_ms else "N/A"
            start_time = turn.start_time.strftime('%H:%M:%S') if turn.start_time else "N/A"
            
            # Get resources for this turn
            cpu_avg = "N/A"
            mem_max = "N/A"
            net_info = "N/A"
            
            if resource_data and "stages" in resource_data:
                for stage in resource_data["stages"]:
                    if stage.get("stage_id") == turn.turn_id:
                        cpu_avg = f"{stage.get('avg_cpu_percent', 0):.1f}%"
                        mem_max = format_bytes(stage.get("max_memory_bytes", 0))
                        net_recv = stage.get("network_bytes_recv_delta", 0)
                        net_sent = stage.get("network_bytes_sent_delta", 0)
                        net_info = f"↓{format_bytes(net_recv)} ↑{format_bytes(net_sent)}"
                        break
            
            user_content = truncate_string(
                turn.user_message.text_content.replace('\n', ' ') if turn.user_message else "",
                200
            )
            assistant_content = truncate_string(
                turn.assistant_messages[-1].text_content.replace('\n', ' ') if turn.assistant_messages else "",
                200
            )
            
            html += f"""            <div class="stage" onclick="toggleStage(this)">
                <div class="stage-header">
                    <span class="stage-title">Turn {turn.turn_number}</span>
                    <span class="stage-time">{start_time} • {duration}</span>
                    <button class="toggle-btn">▼</button>
                </div>
                <div class="stage-resources">
                    <div class="resource-item">
                        <div class="resource-value">{cpu_avg}</div>
                        <div class="resource-label">CPU</div>
                    </div>
                    <div class="resource-item">
                        <div class="resource-value">{mem_max}</div>
                        <div class="resource-label">Memory</div>
                    </div>
                    <div class="resource-item">
                        <div class="resource-value">{net_info}</div>
                        <div class="resource-label">Network</div>
                    </div>
                    <div class="resource-item">
                        <div class="resource-value">{len(turn.tool_uses)}</div>
                        <div class="resource-label">Tools</div>
                    </div>
                </div>
                <div class="stage-details">
                    <div class="io-section">
                        <div class="io-title">Input (User Message)</div>
                        <div class="io-content">{user_content}</div>
                    </div>
                    <div class="io-section">
                        <div class="io-title">Output (Assistant Response)</div>
                        <div class="io-content">{assistant_content}</div>
                    </div>
"""
            
            # Add tools
            if turn.tool_uses:
                html += """                    <h4>Tool Executions</h4>
"""
                for tool in turn.tool_uses:
                    status = "success" if tool.success else "error"
                    status_icon = "✓" if tool.success else "✗"
                    tool_duration = format_duration(tool.duration_ms)
                    tool_input = truncate_string(json.dumps(tool.input_data), 150)
                    tool_output = truncate_string(tool.output_data or "", 150)
                    
                    html += f"""                    <div class="tool-item">
                        <div class="tool-header">
                            <span class="tool-name">{tool.tool_name}</span>
                            <span class="{status}">{status_icon} {tool_duration}</span>
                        </div>
                        <div class="io-section">
                            <div class="io-title">Input</div>
                            <div class="io-content">{tool_input}</div>
                        </div>
                        <div class="io-section">
                            <div class="io-title">Output</div>
                            <div class="io-content">{tool_output}</div>
                        </div>
                    </div>
"""
            
            html += """                </div>
            </div>
"""
        
        html += """        </div>
    </div>
    
    <script>
        function toggleStage(element) {
            element.classList.toggle('expanded');
            const btn = element.querySelector('.toggle-btn');
            btn.textContent = element.classList.contains('expanded') ? '▲' : '▼';
        }
    </script>
</body>
</html>
"""
        
        return html

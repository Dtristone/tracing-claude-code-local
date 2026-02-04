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

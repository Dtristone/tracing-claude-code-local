"""
Command-line interface for Claude Code local tracing.

Provides commands for viewing, analyzing, and exporting trace data.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from claude_trace.analyzer import TraceAnalyzer
from claude_trace.collector import TraceCollector
from claude_trace.reporter import TraceReporter
from claude_trace.storage import TraceStorage


def get_storage() -> TraceStorage:
    """Get the default storage instance."""
    return TraceStorage()


def cmd_list(args) -> int:
    """List recent sessions."""
    storage = get_storage()
    
    since = None
    if args.since:
        try:
            since = datetime.fromisoformat(args.since)
        except ValueError:
            # Try relative time like "1d", "7d", "1w"
            if args.since.endswith('d'):
                days = int(args.since[:-1])
                since = datetime.now() - timedelta(days=days)
            elif args.since.endswith('w'):
                weeks = int(args.since[:-1])
                since = datetime.now() - timedelta(weeks=weeks)
            elif args.since.endswith('h'):
                hours = int(args.since[:-1])
                since = datetime.now() - timedelta(hours=hours)
    
    sessions = storage.list_sessions(limit=args.limit, since=since)
    
    reporter = TraceReporter()
    print(reporter.format_session_list(sessions))
    
    return 0


def cmd_show(args) -> int:
    """Show session details."""
    storage = get_storage()
    session = storage.get_session(args.session_id)
    
    if not session:
        print(f"Session not found: {args.session_id}", file=sys.stderr)
        return 1
    
    reporter = TraceReporter()
    print(reporter.format_session_summary(session))
    
    return 0


def cmd_timeline(args) -> int:
    """Show session timeline."""
    storage = get_storage()
    session = storage.get_session(args.session_id)
    
    if not session:
        print(f"Session not found: {args.session_id}", file=sys.stderr)
        return 1
    
    reporter = TraceReporter()
    print(reporter.format_timeline(session, verbose=args.verbose))
    
    return 0


def cmd_tools(args) -> int:
    """Show tool usage details."""
    storage = get_storage()
    session = storage.get_session(args.session_id)
    
    if not session:
        print(f"Session not found: {args.session_id}", file=sys.stderr)
        return 1
    
    reporter = TraceReporter()
    print(reporter.format_tool_report(session, tool_name=args.name))
    
    return 0


def cmd_stats(args) -> int:
    """Show statistics."""
    storage = get_storage()
    
    if args.all:
        # Show aggregate stats
        sessions = storage.list_sessions(limit=100)
        
        if not sessions:
            print("No sessions found.")
            return 0
        
        analyzer = TraceAnalyzer(storage)
        total_tokens = storage.get_aggregate_token_usage()
        tool_stats = storage.get_tool_stats()
        
        # Also get aggregate OTEL metrics
        otel_aggregate = storage.get_aggregate_otel_metrics()
        
        # Use OTEL tokens if transcript tokens are 0
        input_tokens = total_tokens.input_tokens
        output_tokens = total_tokens.output_tokens
        cache_read = total_tokens.cache_read_tokens
        cache_hit_rate = total_tokens.cache_hit_rate
        
        if input_tokens == 0 and otel_aggregate.get('input_tokens', 0) > 0:
            input_tokens = otel_aggregate['input_tokens']
            output_tokens = otel_aggregate['output_tokens']
            cache_read = otel_aggregate['cache_read_tokens']
            # Only calculate cache hit rate if we have valid input tokens
            cache_hit_rate = (cache_read / input_tokens * 100) if input_tokens > 0 else 0.0
        
        print(f"Aggregate Statistics ({len(sessions)} sessions)")
        print("")
        print("Token Usage:")
        print(f"  Input Tokens:  {input_tokens:,}")
        print(f"  Output Tokens: {output_tokens:,}")
        print(f"  Cache Read:    {cache_read:,}")
        print(f"  Cache Hit Rate: {cache_hit_rate:.1f}%")
        
        if otel_aggregate.get('session_count', 0) > 0:
            print(f"  (includes OTEL data from {otel_aggregate['session_count']} session(s))")
        
        print("")
        print("Tool Usage:")
        for name, stats in tool_stats.items():
            print(f"  {name}: {stats.call_count} calls, {stats.success_rate:.1f}% success")
    else:
        session = storage.get_session(args.session_id)
        
        if not session:
            print(f"Session not found: {args.session_id}", file=sys.stderr)
            return 1
        
        # Use OTEL-enriched reporter
        analyzer = TraceAnalyzer(storage)
        reporter = TraceReporter(analyzer)
        print(reporter.format_statistics_with_otel(session))
    
    return 0


def cmd_export(args) -> int:
    """Export session data."""
    storage = get_storage()
    session = storage.get_session(args.session_id)
    
    if not session:
        print(f"Session not found: {args.session_id}", file=sys.stderr)
        return 1
    
    reporter = TraceReporter()
    
    if args.format == "json":
        output = reporter.export_json(session)
    elif args.format == "html":
        output = reporter.generate_html_report(session)
    else:
        print(f"Unknown format: {args.format}", file=sys.stderr)
        return 1
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Exported to: {args.output}")
    else:
        print(output)
    
    return 0


def cmd_analyze(args) -> int:
    """Analyze a transcript file."""
    transcript_path = args.transcript
    
    if not os.path.exists(transcript_path):
        print(f"File not found: {transcript_path}", file=sys.stderr)
        return 1
    
    storage = get_storage() if args.save else None
    collector = TraceCollector(storage=storage)
    
    try:
        session = collector.collect_from_file(
            transcript_path, 
            session_id=args.session_id
        )
    except Exception as e:
        print(f"Error parsing transcript: {e}", file=sys.stderr)
        return 1
    
    reporter = TraceReporter()
    
    if args.timeline:
        print(reporter.format_timeline(session, verbose=args.verbose))
    elif args.stats:
        print(reporter.format_statistics(session))
    else:
        print(reporter.format_session_summary(session))
        print("")
        print(reporter.format_timeline(session))
    
    if args.save:
        print(f"\nSession saved to database: {session.session_id}")
    
    return 0


def cmd_delete(args) -> int:
    """Delete a session."""
    storage = get_storage()
    
    if not args.force:
        confirm = input(f"Delete session {args.session_id}? [y/N] ")
        if confirm.lower() != 'y':
            print("Cancelled.")
            return 0
    
    if storage.delete_session(args.session_id):
        print(f"Deleted session: {args.session_id}")
        return 0
    else:
        print(f"Session not found: {args.session_id}", file=sys.stderr)
        return 1


def cmd_watch(args) -> int:
    """Watch for new trace data (live mode)."""
    import time
    
    # Find the most recent transcript file
    claude_dir = Path.home() / ".claude" / "projects"
    
    if args.transcript:
        transcript_path = args.transcript
    elif claude_dir.exists():
        # Find most recent .jsonl file
        jsonl_files = list(claude_dir.glob("**/*.jsonl"))
        if not jsonl_files:
            print("No transcript files found.", file=sys.stderr)
            return 1
        transcript_path = max(jsonl_files, key=lambda p: p.stat().st_mtime)
        print(f"Watching: {transcript_path}")
    else:
        print("No Claude projects directory found.", file=sys.stderr)
        print("Use --transcript to specify a file path.", file=sys.stderr)
        return 1
    
    storage = get_storage()
    collector = TraceCollector(storage=storage)
    reporter = TraceReporter()
    
    session_id = args.session_id or Path(transcript_path).stem
    last_line = 0
    
    print(f"Watching session: {session_id}")
    print("Press Ctrl+C to stop.\n")
    
    try:
        while True:
            try:
                session, new_last_line = collector.collect_incremental(
                    str(transcript_path),
                    session_id,
                    last_line
                )
                
                if new_last_line > last_line:
                    # New data available
                    new_turns = session.turns[-(new_last_line - last_line):]
                    for turn in new_turns:
                        print(f"\n--- Turn {turn.turn_number} ---")
                        if turn.user_message:
                            print(f"User: {turn.user_message.text_content[:100]}...")
                        for msg in turn.assistant_messages:
                            model = msg.model or "unknown"
                            print(f"Assistant [{model}]: {msg.text_content[:100]}...")
                        for tool in turn.tool_uses:
                            status = "✓" if tool.success else "✗"
                            print(f"Tool {status} {tool.tool_name}")
                    
                    last_line = new_last_line
                
                time.sleep(args.interval)
                
            except FileNotFoundError:
                # File might not exist yet
                time.sleep(args.interval)
                continue
                
    except KeyboardInterrupt:
        print("\nStopped watching.")
        
        # Show final summary
        if last_line > 0:
            session = storage.get_session(session_id)
            if session:
                print("\nFinal Summary:")
                print(reporter.format_session_summary(session))
    
    return 0


def cmd_otel(args) -> int:
    """Show OTEL metrics for a session."""
    storage = get_storage()
    
    if args.all:
        # Show aggregate OTEL stats
        aggregate = storage.get_aggregate_otel_metrics()
        
        if aggregate.get('session_count', 0) == 0:
            print("No OTEL metrics found.")
            print("\nTo collect OTEL metrics, run Claude Code with:")
            print("  OTEL_METRICS_EXPORTER=console claude ...")
            print("\nThen use: claude-trace otel-import <session_id> <otel_output_file>")
            return 0
        
        print(f"Aggregate OTEL Metrics ({aggregate['session_count']} sessions)")
        print("")
        print("Token Usage:")
        print(f"  Input Tokens:       {aggregate['input_tokens']:,}")
        print(f"  Output Tokens:      {aggregate['output_tokens']:,}")
        print(f"  Cache Read:         {aggregate['cache_read_tokens']:,}")
        print(f"  Cache Created:      {aggregate['cache_creation_tokens']:,}")
        print("")
        print("API Metrics:")
        print(f"  Total API Calls:    {aggregate['api_calls']:,}")
        print(f"  Avg Latency:        {aggregate['api_latency_ms']:.1f}ms")
        print(f"  Total Tool Calls:   {aggregate['tool_calls']:,}")
        print(f"  Total Errors:       {aggregate['errors']:,}")
    else:
        # Check if we have OTEL metrics for this session (session may not exist)
        analyzer = TraceAnalyzer(storage)
        reporter = TraceReporter(analyzer)
        
        otel_analysis = analyzer.get_otel_analysis(args.session_id)
        print(reporter.format_otel_metrics(args.session_id, otel_analysis))
    
    return 0


def cmd_otel_import(args) -> int:
    """Import OTEL metrics from console output file."""
    from claude_trace.otel_collector import OtelMetricsCollector, OtelSessionMapping
    
    if not os.path.exists(args.otel_file):
        print(f"File not found: {args.otel_file}", file=sys.stderr)
        return 1
    
    storage = get_storage()
    collector = OtelMetricsCollector()
    mapping = OtelSessionMapping()
    
    try:
        # Collect from file
        metrics = collector.collect_from_file(
            args.otel_file,
            session_id=args.session_id
        )
        
        # Save to collector storage
        collector.save_metrics(metrics)
        
        # Save to database
        storage.save_otel_metrics(args.session_id, metrics.to_dict())
        
        # Register the session mapping
        mapping.register_session(
            args.session_id, 
            otel_log_file=os.path.abspath(args.otel_file),
            description=f"Imported from {os.path.basename(args.otel_file)}"
        )
        
        print(f"OTEL metrics imported for session: {args.session_id}")
        print("")
        print(f"  Input Tokens:  {metrics.input_tokens:,}")
        print(f"  Output Tokens: {metrics.output_tokens:,}")
        print(f"  API Calls:     {metrics.api_calls}")
        print(f"  Errors:        {metrics.errors}")
        print(f"  Metrics Found: {len(metrics.metrics)}")
        print(f"  Log File:      {os.path.abspath(args.otel_file)}")
        
        if args.verbose:
            print("\nMetrics:")
            for name, metric in sorted(metrics.metrics.items()):
                print(f"  {name}: {metric.total_value}")
        
    except Exception as e:
        print(f"Error importing OTEL metrics: {e}", file=sys.stderr)
        return 1
    
    return 0


def cmd_otel_capture(args) -> int:
    """Capture OTEL metrics from stdin (for use in hook scripts)."""
    import sys as sys_module
    from claude_trace.otel_collector import OtelMetricsCollector, OtelSessionMapping
    
    storage = get_storage()
    collector = OtelMetricsCollector()
    mapping = OtelSessionMapping()
    
    # Read from stdin or file
    if args.input_file:
        if not os.path.exists(args.input_file):
            print(f"File not found: {args.input_file}", file=sys.stderr)
            return 1
        with open(args.input_file, 'r') as f:
            otel_output = f.read()
    else:
        otel_output = sys_module.stdin.read()
    
    if not otel_output.strip():
        print("No OTEL output provided", file=sys.stderr)
        return 1
    
    try:
        # Collect metrics
        metrics = collector.collect_from_output(otel_output, args.session_id)
        
        # Save raw output (this returns the path to the saved file)
        raw_file_path = collector.save_raw_output(otel_output, args.session_id)
        
        # Save parsed metrics
        collector.save_metrics(metrics)
        
        # Save to database
        storage.save_otel_metrics(args.session_id, metrics.to_dict())
        
        # Register the session mapping
        otel_file = args.input_file if args.input_file else raw_file_path
        mapping.register_session(
            args.session_id,
            otel_log_file=os.path.abspath(otel_file),
            description="Captured from console output"
        )
        
        if not args.quiet:
            print(f"OTEL metrics captured for session: {args.session_id}")
            print(f"  Metrics: {len(metrics.metrics)}")
            print(f"  Tokens: {metrics.input_tokens + metrics.output_tokens}")
            print(f"  Log File: {otel_file}")
        
    except Exception as e:
        print(f"Error capturing OTEL metrics: {e}", file=sys.stderr)
        return 1
    
    return 0


def cmd_otel_mapping(args) -> int:
    """Manage OTEL session mappings."""
    from claude_trace.otel_collector import OtelSessionMapping
    
    mapping = OtelSessionMapping()
    
    if args.action == "list":
        # List all mappings
        mappings = mapping.list_mappings()
        
        if not mappings:
            print("No OTEL session mappings found.")
            print("\nTo create a mapping, use:")
            print("  claude-trace otel-mapping register <session_id>")
            return 0
        
        print(f"OTEL Session Mappings ({len(mappings)} entries)")
        print("")
        print(f"{'Session ID':<40} {'Timestamp':<20} {'OTEL Log File'}")
        print("-" * 100)
        
        for entry in mappings:
            ts_str = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            print(f"{entry.session_id:<40} {ts_str:<20} {entry.otel_log_file}")
        
    elif args.action == "get":
        # Get mapping for a specific session
        if not args.session_id:
            print("Error: session_id is required for 'get' action", file=sys.stderr)
            return 1
        
        entry = mapping.get_mapping(args.session_id)
        
        if not entry:
            print(f"No mapping found for session: {args.session_id}")
            return 1
        
        print(f"Session: {entry.session_id}")
        print(f"OTEL Log File: {entry.otel_log_file}")
        print(f"Timestamp: {entry.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        if entry.description:
            print(f"Description: {entry.description}")
        
        # Check if file exists
        if os.path.exists(entry.otel_log_file):
            print(f"File Status: exists")
        else:
            print(f"File Status: not found")
        
    elif args.action == "register":
        # Register a new mapping
        if not args.session_id:
            print("Error: session_id is required for 'register' action", file=sys.stderr)
            return 1
        
        otel_file = mapping.register_session(
            args.session_id,
            otel_log_file=args.otel_file,
            description=args.description or ""
        )
        
        print(f"Registered session mapping:")
        print(f"  Session ID: {args.session_id}")
        print(f"  OTEL Log File: {otel_file}")
        
    elif args.action == "remove":
        # Remove a mapping
        if not args.session_id:
            print("Error: session_id is required for 'remove' action", file=sys.stderr)
            return 1
        
        if mapping.remove_mapping(args.session_id):
            print(f"Removed mapping for session: {args.session_id}")
        else:
            print(f"No mapping found for session: {args.session_id}")
            return 1
        
    elif args.action == "generate-path":
        # Generate a default OTEL log file path for a session
        if not args.session_id:
            print("Error: session_id is required for 'generate-path' action", file=sys.stderr)
            return 1
        
        otel_path = mapping.generate_otel_filepath(args.session_id)
        print(otel_path)
        
    else:
        print(f"Unknown action: {args.action}", file=sys.stderr)
        return 1
    
    return 0


def cmd_otel_auto(args) -> int:
    """Get or generate an OTEL log file path for a session (for use in scripts)."""
    from claude_trace.otel_collector import OtelSessionMapping
    
    mapping = OtelSessionMapping()
    
    # Get existing or create new path
    otel_path = mapping.get_or_create_otel_file(
        args.session_id,
        description=args.description or "Auto-generated"
    )
    
    print(otel_path)
    return 0


def cmd_resource(args) -> int:
    """Show resource usage for a session."""
    storage = get_storage()
    
    if not storage.has_resource_data(args.session_id):
        print(f"No resource data found for session: {args.session_id}")
        print("\nResource monitoring data is collected when monitoring is enabled during session.")
        return 1
    
    # Get resource summary
    summary = storage.get_session_resource_summary(args.session_id)
    
    if args.verbose:
        # Show detailed snapshots
        snapshots = storage.get_resource_snapshots(args.session_id)
        print(f"Resource Snapshots: {args.session_id}")
        print(f"Total Snapshots: {len(snapshots)}")
        print("")
        print(f"{'Timestamp':<26} {'CPU':>8} {'Memory':>8} {'Net Recv':>12} {'Net Sent':>12}")
        print("-" * 70)
        
        for snap in snapshots[:50]:  # Limit to 50 for display
            from claude_trace.utils import format_bytes
            ts = snap.get("timestamp", "")[:19]
            cpu = f"{snap.get('cpu_percent', 0):.1f}%"
            mem = f"{snap.get('memory_percent', 0):.1f}%"
            net_recv = format_bytes(snap.get("network_bytes_recv", 0))
            net_sent = format_bytes(snap.get("network_bytes_sent", 0))
            print(f"{ts:<26} {cpu:>8} {mem:>8} {net_recv:>12} {net_sent:>12}")
        
        if len(snapshots) > 50:
            print(f"... and {len(snapshots) - 50} more snapshots")
    else:
        # Show summary
        from claude_trace.utils import format_bytes, format_duration
        
        print(f"Resource Summary: {args.session_id}")
        print("")
        print("CPU Usage:")
        print(f"  Average: {summary.get('cpu', {}).get('avg_percent', 0):.1f}%")
        print(f"  Maximum: {summary.get('cpu', {}).get('max_percent', 0):.1f}%")
        print("")
        print("Memory Usage:")
        print(f"  Average: {summary.get('memory', {}).get('avg_percent', 0):.1f}%")
        print(f"  Maximum: {summary.get('memory', {}).get('max_percent', 0):.1f}%")
        print(f"  Max Used: {format_bytes(summary.get('memory', {}).get('max_bytes', 0))}")
        print(f"  Delta: {format_bytes(abs(summary.get('memory', {}).get('delta_bytes', 0)))}")
        print("")
        print("Network:")
        print(f"  Received: {format_bytes(summary.get('network', {}).get('bytes_recv', 0))}")
        print(f"  Sent: {format_bytes(summary.get('network', {}).get('bytes_sent', 0))}")
        print("")
        print("Disk I/O:")
        print(f"  Read: {format_bytes(summary.get('disk', {}).get('read_bytes', 0))}")
        print(f"  Write: {format_bytes(summary.get('disk', {}).get('write_bytes', 0))}")
        print("")
        print(f"Snapshots: {summary.get('snapshot_count', 0)}")
        print(f"Stages: {summary.get('stage_count', 0)}")
    
    return 0


def cmd_find_logs(args) -> int:
    """Find all logs for a session."""
    storage = get_storage()
    
    logs = storage.find_all_session_logs(args.session_id)
    
    print(f"Session Logs: {args.session_id}")
    print("=" * 60)
    print("")
    
    # Trace data
    print(f"Trace Data: {'✓ Available' if logs['has_trace_data'] else '✗ Not found'}")
    if logs['has_trace_data'] and logs['trace_summary']:
        ts = logs['trace_summary']
        from claude_trace.utils import format_duration
        print(f"  Start Time: {ts.get('start_time', 'N/A')}")
        print(f"  Duration: {format_duration(ts.get('duration_ms'))}")
        print(f"  Turns: {ts.get('turn_count', 0)}")
        print(f"  Tools: {ts.get('tool_count', 0)}")
    print("")
    
    # OTEL data
    print(f"OTEL Metrics: {'✓ Available' if logs['has_otel_data'] else '✗ Not found'}")
    if logs['has_otel_data'] and logs['otel_summary']:
        otel = logs['otel_summary']
        print(f"  Input Tokens: {otel.get('input_tokens', 0):,}")
        print(f"  Output Tokens: {otel.get('output_tokens', 0):,}")
        print(f"  API Calls: {otel.get('api_calls', 0)}")
        print(f"  Errors: {otel.get('errors', 0)}")
    print("")
    
    # Resource data
    print(f"Resource Data: {'✓ Available' if logs['has_resource_data'] else '✗ Not found'}")
    if logs['has_resource_data'] and logs['resource_summary']:
        from claude_trace.utils import format_bytes
        rs = logs['resource_summary']
        print(f"  Avg CPU: {rs.get('cpu', {}).get('avg_percent', 0):.1f}%")
        print(f"  Max Memory: {rs.get('memory', {}).get('max_percent', 0):.1f}%")
        print(f"  Network: ↓{format_bytes(rs.get('network', {}).get('bytes_recv', 0))} / "
              f"↑{format_bytes(rs.get('network', {}).get('bytes_sent', 0))}")
        print(f"  Snapshots: {rs.get('snapshot_count', 0)}")
    print("")
    
    # Stage data
    if logs['stages']:
        print(f"Stage Resource Data: {len(logs['stages'])} stages")
        for stage in logs['stages'][:10]:
            from claude_trace.utils import format_duration
            name = stage.get('stage_name', 'unknown')
            duration = format_duration(stage.get('duration_ms'))
            cpu = f"{stage.get('avg_cpu_percent', 0):.1f}%"
            print(f"  - {name}: {duration} (CPU: {cpu})")
        if len(logs['stages']) > 10:
            print(f"  ... and {len(logs['stages']) - 10} more stages")
    
    return 0


def cmd_report(args) -> int:
    """Generate a unified timeline report."""
    storage = get_storage()
    session = storage.get_session(args.session_id)
    
    if not session:
        print(f"Session not found: {args.session_id}", file=sys.stderr)
        return 1
    
    # Get all available data
    resource_data = None
    otel_data = None
    
    if storage.has_resource_data(args.session_id):
        resource_data = {
            "resource_summary": storage.get_session_resource_summary(args.session_id),
            "stages": storage.get_stage_resource_usage(args.session_id),
        }
    
    if storage.has_otel_metrics(args.session_id):
        otel_data = storage.get_otel_summary(args.session_id)
    
    analyzer = TraceAnalyzer(storage)
    reporter = TraceReporter(analyzer)
    
    if args.format == "html":
        output = reporter.generate_unified_html_report(session, resource_data, otel_data)
    else:
        output = reporter.generate_unified_timeline_report(session, resource_data, otel_data)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        print(f"Report saved to: {args.output}")
    else:
        print(output)
    
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Claude Code Local Tracing - Analyze Claude Code sessions locally",
        prog="claude-trace"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # list command
    list_parser = subparsers.add_parser("list", help="List recent sessions")
    list_parser.add_argument(
        "--limit", "-n", 
        type=int, 
        default=20,
        help="Maximum number of sessions to show"
    )
    list_parser.add_argument(
        "--since", "-s",
        help="Show sessions since date (ISO format) or relative time (e.g., 1d, 7d, 1w)"
    )
    list_parser.set_defaults(func=cmd_list)
    
    # show command
    show_parser = subparsers.add_parser("show", help="Show session details")
    show_parser.add_argument("session_id", help="Session ID to show")
    show_parser.set_defaults(func=cmd_show)
    
    # timeline command
    timeline_parser = subparsers.add_parser("timeline", help="Show session timeline")
    timeline_parser.add_argument("session_id", help="Session ID")
    timeline_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed content"
    )
    timeline_parser.set_defaults(func=cmd_timeline)
    
    # tools command
    tools_parser = subparsers.add_parser("tools", help="Show tool usage details")
    tools_parser.add_argument("session_id", help="Session ID")
    tools_parser.add_argument(
        "--name", "-n",
        help="Filter by tool name"
    )
    tools_parser.set_defaults(func=cmd_tools)
    
    # stats command
    stats_parser = subparsers.add_parser("stats", help="Show statistics")
    stats_parser.add_argument(
        "session_id",
        nargs="?",
        help="Session ID (required unless --all is used)"
    )
    stats_parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Show aggregate statistics for all sessions"
    )
    stats_parser.set_defaults(func=cmd_stats)
    
    # export command
    export_parser = subparsers.add_parser("export", help="Export session data")
    export_parser.add_argument("session_id", help="Session ID")
    export_parser.add_argument(
        "--format", "-f",
        choices=["json", "html"],
        default="json",
        help="Export format"
    )
    export_parser.add_argument(
        "--output", "-o",
        help="Output file path"
    )
    export_parser.set_defaults(func=cmd_export)
    
    # analyze command
    analyze_parser = subparsers.add_parser(
        "analyze", 
        help="Analyze a transcript file"
    )
    analyze_parser.add_argument("transcript", help="Path to transcript JSONL file")
    analyze_parser.add_argument(
        "--session-id", "-s",
        help="Session ID (derived from filename if not specified)"
    )
    analyze_parser.add_argument(
        "--save",
        action="store_true",
        help="Save to database"
    )
    analyze_parser.add_argument(
        "--timeline", "-t",
        action="store_true",
        help="Show timeline view"
    )
    analyze_parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics only"
    )
    analyze_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed content"
    )
    analyze_parser.set_defaults(func=cmd_analyze)
    
    # delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a session")
    delete_parser.add_argument("session_id", help="Session ID to delete")
    delete_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Delete without confirmation"
    )
    delete_parser.set_defaults(func=cmd_delete)
    
    # watch command
    watch_parser = subparsers.add_parser(
        "watch", 
        help="Watch for new trace data (live mode)"
    )
    watch_parser.add_argument(
        "--session-id", "-s",
        help="Session ID to use"
    )
    watch_parser.add_argument(
        "--transcript", "-t",
        help="Path to transcript file to watch"
    )
    watch_parser.add_argument(
        "--interval", "-i",
        type=float,
        default=1.0,
        help="Check interval in seconds"
    )
    watch_parser.set_defaults(func=cmd_watch)
    
    # otel command - view OTEL metrics
    otel_parser = subparsers.add_parser(
        "otel",
        help="Show OTEL metrics for a session"
    )
    otel_parser.add_argument(
        "session_id",
        nargs="?",
        help="Session ID (required unless --all is used)"
    )
    otel_parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Show aggregate OTEL metrics for all sessions"
    )
    otel_parser.set_defaults(func=cmd_otel)
    
    # otel-import command - import from file
    otel_import_parser = subparsers.add_parser(
        "otel-import",
        help="Import OTEL metrics from console output file"
    )
    otel_import_parser.add_argument(
        "session_id",
        help="Session ID to associate metrics with"
    )
    otel_import_parser.add_argument(
        "otel_file",
        help="Path to file containing OTEL console output"
    )
    otel_import_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed metrics"
    )
    otel_import_parser.set_defaults(func=cmd_otel_import)
    
    # otel-capture command - capture from stdin
    otel_capture_parser = subparsers.add_parser(
        "otel-capture",
        help="Capture OTEL metrics from stdin (for use in hooks)"
    )
    otel_capture_parser.add_argument(
        "session_id",
        help="Session ID to associate metrics with"
    )
    otel_capture_parser.add_argument(
        "--input-file", "-i",
        help="Read from file instead of stdin"
    )
    otel_capture_parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress output"
    )
    otel_capture_parser.set_defaults(func=cmd_otel_capture)
    
    # otel-mapping command - manage session mappings
    otel_mapping_parser = subparsers.add_parser(
        "otel-mapping",
        help="Manage OTEL session to log file mappings"
    )
    otel_mapping_parser.add_argument(
        "action",
        choices=["list", "get", "register", "remove", "generate-path"],
        help="Action to perform: list all mappings, get/register/remove a specific mapping, or generate a path"
    )
    otel_mapping_parser.add_argument(
        "session_id",
        nargs="?",
        help="Session ID (required for get/register/remove/generate-path actions)"
    )
    otel_mapping_parser.add_argument(
        "--otel-file", "-f",
        help="OTEL log file path (optional for register, auto-generated if not provided)"
    )
    otel_mapping_parser.add_argument(
        "--description", "-d",
        help="Description for the mapping"
    )
    otel_mapping_parser.set_defaults(func=cmd_otel_mapping)
    
    # otel-auto command - get or generate OTEL log path (for scripts)
    otel_auto_parser = subparsers.add_parser(
        "otel-auto",
        help="Get or generate OTEL log file path for a session (for use in scripts)"
    )
    otel_auto_parser.add_argument(
        "session_id",
        help="Session ID"
    )
    otel_auto_parser.add_argument(
        "--description", "-d",
        help="Description for new mappings"
    )
    otel_auto_parser.set_defaults(func=cmd_otel_auto)
    
    # resource command - show resource usage for a session
    resource_parser = subparsers.add_parser(
        "resource",
        help="Show resource usage for a session"
    )
    resource_parser.add_argument(
        "session_id",
        help="Session ID to show resources for"
    )
    resource_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed snapshots instead of summary"
    )
    resource_parser.set_defaults(func=cmd_resource)
    
    # find-logs command - find all logs for a session
    find_logs_parser = subparsers.add_parser(
        "find-logs",
        help="Find all logs (trace, OTEL, resources) for a session"
    )
    find_logs_parser.add_argument(
        "session_id",
        help="Session ID to find logs for"
    )
    find_logs_parser.set_defaults(func=cmd_find_logs)
    
    # report command - generate unified timeline report
    report_parser = subparsers.add_parser(
        "report",
        help="Generate unified timeline report with resources and I/O"
    )
    report_parser.add_argument(
        "session_id",
        help="Session ID to generate report for"
    )
    report_parser.add_argument(
        "--format", "-f",
        choices=["text", "html"],
        default="text",
        help="Output format (default: text)"
    )
    report_parser.add_argument(
        "--output", "-o",
        help="Output file path"
    )
    report_parser.set_defaults(func=cmd_report)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    # Validate stats command
    if args.command == "stats" and not args.all and not args.session_id:
        print("Error: session_id is required unless --all is used", file=sys.stderr)
        return 1
    
    # Validate otel command
    if args.command == "otel" and not args.all and not args.session_id:
        print("Error: session_id is required unless --all is used", file=sys.stderr)
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

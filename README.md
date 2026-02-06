# Claude Code Local Tracing

A **100% local** tracing and observability solution for [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) that captures detailed session traces and OpenTelemetry metrics without requiring any remote server connections. All data stays on your machine.

## Key Features

- 🏠 **Completely Local**: All data stored in SQLite on your machine—no cloud dependencies
- 📡 **Automatic OTEL Integration**: Seamlessly captures OpenTelemetry metrics when transcript token data is unavailable
- 📊 **Session Timeline**: Visualize the complete flow of conversations with timing breakdowns
- 🔧 **Tool Tracking**: Detailed tool usage with inputs, outputs, latency, and success rates
- 📈 **Token Analysis**: Track input/output tokens, cache hit rates, and cost estimation
- ⏱️ **Time Breakdown**: Understand where time is spent (model inference vs tool execution)
- 📁 **Export Options**: JSON and HTML reports for sharing and archival
- 🔄 **Live Watch Mode**: Monitor active sessions in real-time
- 🔗 **Session-OTEL Mapping**: Automatic and manual mapping between sessions and OTEL log files
- 💻 **Resource Monitoring**: Track CPU, memory, network, and disk I/O for each stage
- 📋 **Unified Reports**: Generate timeline reports with resources, operations, and I/O aligned by time

## Table of Contents

- [Quick Start](#quick-start)
- [Automatic OTEL Metrics Integration](#automatic-otel-metrics-integration)
- [Resource Monitoring](#resource-monitoring)
- [CLI Command Reference](#cli-command-reference)
- [OTEL Commands](#otel-commands)
- [Output Examples](#output-examples)
- [Data Storage](#data-storage)
- [Environment Variables](#environment-variables)
- [Architecture](#architecture)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/Dtristone/tracing-claude-code-local
cd tracing-claude-code-local

# Install the package
pip install -e .

# Verify installation
claude-trace --help
```

### 2. Configure Claude Code Hook

Add the local trace hook to your Claude Code settings. This enables automatic trace collection after each session.

**Step 1**: Create or edit `~/.claude/settings.local.json`:

```json
{
  "hooks": {
    "stop": [
      {
        "command": "/absolute/path/to/tracing-claude-code-local/local_trace_hook.sh"
      }
    ]
  }
}
```

> **Note**: Replace `/absolute/path/to/` with the actual path where you cloned the repository.

**Step 2**: Enable tracing by setting environment variables:

```bash
# Add to your shell profile (~/.bashrc, ~/.zshrc, etc.)
export CLAUDE_TRACE_ENABLED=true
```

**Step 3** (Optional): Enable automatic OTEL metrics capture:

```bash
# Enable OTEL console exporter for Claude Code
export OTEL_METRICS_EXPORTER=console
export OTEL_METRICS_OUTPUT=~/.claude-trace/otel-output.txt
```

### 3. Verify Setup

After running a Claude Code session:

```bash
# List recent sessions
claude-trace list

# View the latest session timeline
claude-trace timeline <session_id>

# View session statistics with OTEL enrichment
claude-trace stats <session_id>
```

### 4. Analyze Existing Transcripts

You can analyze Claude Code transcript files directly without the hook:

```bash
# Analyze a specific transcript file
claude-trace analyze ~/.claude/projects/your-project/session.jsonl

# Save to database for later analysis
claude-trace analyze ~/.claude/projects/your-project/session.jsonl --save

# Show timeline during analysis
claude-trace analyze ~/.claude/projects/your-project/session.jsonl --timeline

# Show statistics during analysis
claude-trace analyze ~/.claude/projects/your-project/session.jsonl --stats
```

## Automatic OTEL Metrics Integration

When Claude Code transcript files have zero or missing token counts, `claude-trace` automatically enriches session data with OpenTelemetry metrics. This provides accurate token usage even when the transcript doesn't include that information.

### How It Works

1. **Hook Script**: The `local_trace_hook.sh` is triggered after each Claude Code session
2. **Transcript Parsing**: Parses the JSONL transcript and stores session data
3. **OTEL Detection**: Checks for OTEL console output files
4. **Automatic Capture**: If found, imports and maps OTEL metrics to the session
5. **Data Enrichment**: The `stats` command automatically uses OTEL data when transcript tokens are 0

### Setup for Automatic OTEL Capture

**Option A: Global OTEL Output File**

Set these environment variables before running Claude Code:

```bash
export OTEL_METRICS_EXPORTER=console
export OTEL_METRICS_OUTPUT=~/.claude-trace/otel-output.txt
```

The hook will automatically:
1. Detect the OTEL output file after each session
2. Parse and import the metrics
3. Map them to the session
4. Archive the raw output

**Option B: Capture OTEL During Session**

Run Claude Code with OTEL output captured:

```bash
OTEL_METRICS_EXPORTER=console claude "your prompt" 2>&1 | tee ~/.claude-trace/otel-output.txt
```

**Option C: Manual Import**

Import OTEL metrics manually:

```bash
# After capturing OTEL output to a file
claude-trace otel-import <session_id> /path/to/otel_output.txt
```

### OTEL Session Mapping System

The session-to-OTEL mapping system tracks which OTEL log files correspond to which sessions:

```bash
# List all session-to-OTEL mappings
claude-trace otel-mapping list

# Get mapping for a specific session
claude-trace otel-mapping get <session_id>

# Register a custom mapping
claude-trace otel-mapping register <session_id> -f /path/to/otel.txt -d "Custom capture"

# Generate a default OTEL log file path (without registering)
claude-trace otel-mapping generate-path <session_id>

# Remove a mapping
claude-trace otel-mapping remove <session_id>

# Get or create OTEL path for scripts
claude-trace otel-auto <session_id>
```

The mapping file is stored at `~/.claude-trace/otel-session-mapping.json`:

```json
{
  "version": "1.0",
  "updated_at": "2025-02-04T10:30:00",
  "mappings": [
    {
      "session_id": "abc-123-def",
      "otel_log_file": "~/.claude-trace/otel-metrics/abc-123-def_20250204_103000_otel.txt",
      "timestamp": "2025-02-04T10:30:00",
      "description": "Auto-captured from hook"
    }
  ]
}
```

## Resource Monitoring

The resource monitoring feature tracks local system resources (CPU, memory, network, disk I/O) during session execution, allowing you to correlate resource usage with each stage of your Claude Code sessions.

### Captured Metrics

- **CPU**: Usage percentage, user/system breakdown
- **Memory**: Used/available bytes, percentage, process memory (RSS/VMS)
- **Network**: Bytes sent/received, packets sent/received
- **Disk I/O**: Read/write bytes

### Background Process Monitoring

The preferred way to capture resource data is using the **background process monitor**, which automatically monitors the Claude CLI process and saves timestamped data to log files:

```python
from claude_trace import ClaudeProcessMonitor

# Start background monitoring for a session
monitor = ClaudeProcessMonitor("my-session-id", interval=1.0)
log_file = monitor.start()
print(f"Monitoring started, log file: {log_file}")

# ... Claude CLI runs, monitor captures process resources automatically ...

# Stop monitoring when done
monitor.stop()
summary = monitor.get_summary()
print(f"Captured {summary['snapshot_count']} snapshots")
print(f"Avg CPU: {summary['cpu']['avg_percent']:.1f}%")
print(f"Max Memory: {summary['memory']['max_bytes'] / 1024 / 1024:.1f}MB")
```

The monitor captures:
- **Process-specific CPU usage**: Only Claude process, not whole system
- **Process memory (RSS/VMS)**: Memory used by Claude
- **Process I/O**: Disk read/write by Claude
- **Thread count**: Number of threads in Claude process
- **Timestamps**: For alignment with trace data

### CLI Commands for Background Monitoring

```bash
# Start background monitoring for a session
claude-trace resource-start <session_id>

# Start with custom interval (0.5 seconds)
claude-trace resource-start <session_id> --interval 0.5

# Run in foreground with live output
claude-trace resource-start <session_id> --foreground

# Stop monitoring
claude-trace resource-stop <session_id>

# List available resource log files
claude-trace resource-logs
claude-trace resource-logs <session_id>  # Filter by session

# Import resource logs into database
claude-trace resource-import <session_id> /path/to/resource.jsonl
```

### Manual Stage Monitoring (Alternative)

For more control, you can use the manual ResourceMonitor:

```python
from claude_trace import ResourceMonitor, ResourceSnapshot

# Create a monitor for a session
monitor = ResourceMonitor("my-session-id")

# Start tracking a stage (e.g., model inference)
monitor.start_stage("stage-1", "model_inference")

# Capture snapshots during the stage
snapshot = monitor.capture_snapshot()
print(f"CPU: {snapshot.cpu_percent:.1f}%")
print(f"Memory: {snapshot.memory_percent:.1f}%")

# End the stage
stage = monitor.end_stage("stage-1")
print(f"Stage duration: {stage.duration_ms}ms")
print(f"Avg CPU: {stage.avg_cpu_percent:.1f}%")

# Get session summary
summary = monitor.get_session_summary()
```

### Viewing Resource Data

```bash
# View resource usage for a session
claude-trace resource <session_id>

# View detailed snapshots
claude-trace resource <session_id> --verbose

# Find all logs for a session (trace, OTEL, resources)
claude-trace find-logs <session_id>

# Generate unified timeline report with resources
claude-trace report <session_id>

# Generate HTML report with interactive timeline
claude-trace report <session_id> --format html --output report.html
```

### Aligning Resource Data with Traces

Resource snapshots are timestamped and can be automatically aligned with trace events:

```python
from claude_trace import ClaudeProcessMonitor, align_resource_with_trace

# Load resource logs
snapshots = ClaudeProcessMonitor.load_from_file("/path/to/resource.jsonl")

# Align with trace events (from session.turns, etc.)
trace_events = [
    {"timestamp": "2025-02-04T10:30:00", "event": "turn_start"},
    {"timestamp": "2025-02-04T10:30:15", "event": "tool_call"},
]

aligned = align_resource_with_trace(snapshots, trace_events)
# Each event now has a "resource" field with CPU, memory, I/O data
```

### Unified Timeline Report

The unified report combines trace data, OTEL metrics, and resource usage in a single timeline view:

```
Unified Timeline Report: abc-123-def
============================================================
Started: 2025-02-04 10:30:00
Duration: 45.3s

Stage                          Time       CPU      Memory         Net I/O
--------------------------------------------------------------------------------
Turn 1                         15.2s     8.5%      256MB     ↓1.2KB/↑0.5KB
  └─ Read                       0.1s     2.1%      256MB     ↓0.1KB/↑0.0KB
  └─ Bash                       8.0s    15.2%      280MB     ↓0.8KB/↑0.3KB ✓
Turn 2                         30.1s    12.3%      285MB     ↓2.5KB/↑1.2KB

============================================================
Summary:
  Total Turns: 2
  Total Tool Uses: 2
  Total Tokens: 1,630
  Cache Hit Rate: 42.0%

Resource Summary:
  Avg CPU: 10.4%
  Max CPU: 15.2%
  Avg Memory: 8.5%
  Network: ↓3.7KB / ↑1.7KB
  Disk: R0B / W0B
```

## CLI Command Reference

### Session Management

#### List Sessions

```bash
# List recent sessions (default: 20)
claude-trace list

# List with custom limit
claude-trace list --limit 10

# Sessions from last 7 days
claude-trace list --since 7d

# Sessions from last 24 hours
claude-trace list --since 24h

# Sessions since a specific date
claude-trace list --since 2025-02-01
```

#### View Session Details

```bash
# Show session summary
claude-trace show <session_id>

# Show detailed timeline
claude-trace timeline <session_id>

# Show timeline with full content (verbose)
claude-trace timeline <session_id> --verbose
```

#### Delete Sessions

```bash
# Delete a session (with confirmation)
claude-trace delete <session_id>

# Delete without confirmation
claude-trace delete <session_id> --force
```

### Analysis Commands

#### Tool Usage

```bash
# Show all tool usage for a session
claude-trace tools <session_id>

# Filter by tool name
claude-trace tools <session_id> --name Read
claude-trace tools <session_id> --name Bash
```

#### Statistics

```bash
# Session statistics (auto-enriched with OTEL data)
claude-trace stats <session_id>

# Aggregate statistics for all sessions
claude-trace stats --all
```

#### Live Watch Mode

Monitor an active session in real-time:

```bash
# Watch for new trace data (auto-detect latest transcript)
claude-trace watch

# Watch specific transcript file
claude-trace watch --transcript /path/to/session.jsonl

# Custom check interval (default: 1 second)
claude-trace watch --interval 2.0

# Specify session ID
claude-trace watch --session-id my-session
```

### Resource Commands

```bash
# View resource usage for a session
claude-trace resource <session_id>

# View detailed resource snapshots
claude-trace resource <session_id> --verbose
```

### Log Discovery

```bash
# Find all logs for a session (trace, OTEL, resources)
claude-trace find-logs <session_id>
```

### Unified Reports

```bash
# Generate unified timeline report (text format)
claude-trace report <session_id>

# Generate HTML report with interactive timeline
claude-trace report <session_id> --format html --output report.html
```

### Export Commands

```bash
# Export as JSON
claude-trace export <session_id> --format json

# Export as HTML report
claude-trace export <session_id> --format html --output report.html

# Export JSON to file
claude-trace export <session_id> --format json --output session.json
```

## OTEL Commands

### View OTEL Metrics

```bash
# View OTEL metrics for a specific session
claude-trace otel <session_id>

# View aggregate OTEL metrics for all sessions
claude-trace otel --all
```

### Import OTEL Metrics

```bash
# Import from file
claude-trace otel-import <session_id> /path/to/otel_output.txt

# Import with verbose output (shows individual metrics)
claude-trace otel-import <session_id> /path/to/otel_output.txt --verbose
```

### Capture OTEL Metrics (for Scripts/Hooks)

```bash
# Capture from a file (quiet mode for hooks)
claude-trace otel-capture <session_id> --input-file /path/to/otel.txt --quiet

# Capture from stdin
echo "otel output..." | claude-trace otel-capture <session_id>
```

### Manage OTEL Mappings

```bash
# List all mappings
claude-trace otel-mapping list

# Get mapping for a session
claude-trace otel-mapping get <session_id>

# Register a new mapping
claude-trace otel-mapping register <session_id> -f /path/to/otel.txt -d "Description"

# Remove a mapping
claude-trace otel-mapping remove <session_id>

# Generate default path (for session ID)
claude-trace otel-mapping generate-path <session_id>
```

### Auto OTEL Path (for Scripts)

```bash
# Get or generate OTEL log file path for a session
# Useful in hook scripts for automatic file path management
claude-trace otel-auto <session_id>
claude-trace otel-auto <session_id> --description "Auto-generated for hook"
```

## Output Examples

### Timeline View

```
Session: abc-123-def
Started: 2025-02-04 10:30:00

Turn 1 [10:30:00 - 10:30:15] (15.2s)
├── User: "Read the config file and summarize it"
├── Assistant: "I'll read the config file..."
│   ├── Model: claude-sonnet-4-5
│   ├── Tokens: 150 in / 45 out (cache: 100 read)
│   └── Tools called: Read
├── Tool: Read (/config/settings.json)
│   ├── Duration: 0.1s
│   └── Output: {"setting": "value"...
└── Assistant: "Here's the summary..."
    ├── Model: claude-sonnet-4-5
    └── Tokens: 250 in / 120 out (cache: 0 read)

Summary:
  Total Duration: 15.2s
  Turns: 1
  Tool Uses: 1
  Total Tokens: 400 in / 165 out
  Cache Hit Rate: 25.0%
```

### Statistics View (with OTEL Enrichment)

```
Session Statistics: abc-123-def

Time Breakdown:
  Total Duration:     45.3s
  Model Inference:    32.1s (70.9%)
  Tool Execution:      8.2s (18.1%)

Token Usage:
  Input Tokens:       1,250
  Output Tokens:        380
  Cache Read:           520 (41.6% hit rate)
  Cache Created:        180
  (enriched with OTEL metrics)

Tool Usage:
  Read         2 calls, avg   100ms, total   200ms
  Bash         1 call,  avg 8.00s,  total 8.00s

Performance:
  Avg Response Latency: 8.0s
  Retry Count: 0
  Error Count: 0

OTEL Metrics:
  API Calls:          5
  Avg API Latency:    1,200ms
```

### OTEL Aggregate View

```
Aggregate OTEL Metrics (15 sessions)

Token Usage:
  Input Tokens:       125,000
  Output Tokens:       38,000
  Cache Read:          52,000
  Cache Created:       18,000

API Metrics:
  Total API Calls:    450
  Avg Latency:        980.5ms
  Total Tool Calls:   280
  Total Errors:       3
```

## Data Storage

All trace data is stored locally:

| Location | Description |
|----------|-------------|
| `~/.claude-trace/traces.db` | SQLite database with all session data |
| `~/.claude-trace/hook.log` | Hook execution log |
| `~/.claude-trace/otel-session-mapping.json` | Session-to-OTEL file mappings |
| `~/.claude-trace/otel-metrics/` | Directory for OTEL metrics files |
| `~/.claude-trace/resource-logs/` | Directory for process resource log files (JSONL) |

### Database Schema

The SQLite database includes these tables:

- **`sessions`**: Session metadata and timing information
- **`turns`**: Conversation turns within sessions
- **`messages`**: User and assistant messages with token usage
- **`tool_uses`**: Tool invocations with inputs, outputs, and timing
- **`otel_metrics`**: OpenTelemetry metrics data points
- **`otel_session_summary`**: Aggregated OTEL metrics per session
- **`resource_snapshots`**: Point-in-time resource usage measurements (CPU, memory, network, disk)
- **`stage_resource_usage`**: Aggregated resource usage per stage/operation

### Resource Log Files

Resource log files are stored as JSONL (one JSON object per line) in `~/.claude-trace/resource-logs/`:

```
~/.claude-trace/resource-logs/
├── abc-123-def_20250204_103000_resource.jsonl
├── xyz-456-ghi_20250204_113000_resource.jsonl
└── ...
```

Each line contains a `ProcessResourceSnapshot` with timestamp, PID, CPU, memory, and I/O data.

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CLAUDE_TRACE_ENABLED` | Enable/disable local tracing (`true`/`false`) | `true` |
| `CLAUDE_TRACE_DEBUG` | Enable debug logging in hooks | `false` |
| `CLAUDE_TRACE_LOG` | Path to hook log file | `~/.claude-trace/hook.log` |
| `CLAUDE_TRACE_OTEL_DIR` | Directory for OTEL metrics files | `~/.claude-trace/otel-metrics` |
| `OTEL_METRICS_EXPORTER` | Set to `console` to enable OTEL console output | (not set) |
| `OTEL_METRICS_OUTPUT` | Path to OTEL console output file (for hook auto-capture) | `~/.claude-trace/otel-output.txt` |

### Recommended Shell Configuration

Add to your `~/.bashrc`, `~/.zshrc`, or equivalent:

```bash
# Enable Claude Code local tracing
export CLAUDE_TRACE_ENABLED=true

# Optional: Enable automatic OTEL metrics capture
export OTEL_METRICS_EXPORTER=console
export OTEL_METRICS_OUTPUT=~/.claude-trace/otel-output.txt

# Optional: Enable debug logging
# export CLAUDE_TRACE_DEBUG=true
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Claude Code CLI                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  local_trace_hook.sh (stop hook)                                      │  │
│  │  • Triggered after each Claude Code session                           │  │
│  │  • Reads transcript JSONL + OTEL console output                       │  │
│  │  • Auto-maps OTEL files to sessions                                   │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌─────────────────────────────────┐ ┌─────────────────────────────────────────┐
│    Transcript Parser            │ │    OTEL Metrics Collector               │
│  ┌───────────────────────────┐  │ │  ┌────────────────────────────────────┐ │
│  │  collector.py             │  │ │  │  otel_collector.py                 │ │
│  │  • Parse JSONL transcripts│  │ │  │  • Parse OTEL console output       │ │
│  │  • Extract session data   │  │ │  │  • Support multiple OTEL formats   │ │
│  │  • Token/tool tracking    │  │ │  │  • Session-OTEL mapping            │ │
│  └───────────────────────────┘  │ │  └────────────────────────────────────┘ │
└─────────────────────────────────┘ └─────────────────────────────────────────┘
                    │                               │
                    └───────────────┬───────────────┘
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Storage Layer (SQLite)                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  storage.py                     ~/.claude-trace/traces.db             │  │
│  │  • Session/turn/message storage                                       │  │
│  │  • OTEL metrics storage                                               │  │
│  │  • Aggregation queries                                                │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌─────────────────────────────────┐ ┌─────────────────────────────────────────┐
│    Analyzer                     │ │    Reporter                             │
│  ┌───────────────────────────┐  │ │  ┌────────────────────────────────────┐ │
│  │  analyzer.py              │  │ │  │  reporter.py                       │ │
│  │  • Statistics computation │  │ │  │  • Terminal output formatting      │ │
│  │  • OTEL data enrichment   │  │ │  │  • JSON/HTML export               │ │
│  │  • Time breakdown         │  │ │  │  • Timeline visualization         │ │
│  └───────────────────────────┘  │ │  └────────────────────────────────────┘ │
└─────────────────────────────────┘ └─────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLI (cli.py)                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  Commands: list, show, timeline, tools, stats, export, watch,         │  │
│  │            analyze, delete, otel, otel-import, otel-capture,          │  │
│  │            otel-mapping, otel-auto, resource, find-logs, report       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Comparison with LangSmith Tracing

| Feature | Local Tracing | LangSmith |
|---------|---------------|-----------|
| Network Required | ❌ No | ✅ Yes |
| Privacy | ✅ All data local | ⚠️ Data sent to cloud |
| Cost | ✅ Free | 💰 Pricing tiers |
| OTEL Integration | ✅ Automatic | ⚠️ Requires setup |
| Resource Monitoring | ✅ Built-in | ❌ Not available |
| Team Collaboration | ❌ Local only | ✅ Team sharing |
| Real-time Dashboards | ❌ No | ✅ Yes |
| Data Retention | ✅ You control | ⚠️ Based on plan |
| Offline Usage | ✅ Full functionality | ❌ Requires connectivity |

## Development

### Project Structure

```
tracing-claude-code-local/
├── claude_trace/              # Python package
│   ├── __init__.py
│   ├── models.py              # Data models (Session, Turn, Message, etc.)
│   ├── collector.py           # JSONL transcript parsing
│   ├── otel_collector.py      # OTEL metrics parsing and mapping
│   ├── resource_monitor.py    # Local resource monitoring (CPU, memory, network, disk)
│   ├── analyzer.py            # Statistics computation and OTEL enrichment
│   ├── storage.py             # SQLite persistence layer
│   ├── reporter.py            # Output formatting (terminal, JSON, HTML)
│   ├── cli.py                 # Command-line interface
│   └── utils.py               # Utility functions
├── local_trace_hook.sh        # Claude Code hook script (with OTEL auto-capture)
├── pyproject.toml             # Modern Python build configuration
├── setup.py                   # Package setup (legacy, for compatibility)
├── requirements.txt           # Dependencies
├── pytest.ini                 # Test configuration
├── PLAN.md                    # Implementation plan
├── README.md                  # This file
└── tests/                     # Test suite
    ├── unit/                  # Unit tests
    └── integration/           # End-to-end tests
```

### Running Tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run all tests
pytest

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests only
pytest tests/integration/ -v

# Run with coverage report
pytest tests/unit/ --cov=claude_trace --cov-report=html
```

### Adding New Features

1. Update data models in `models.py` if needed
2. Implement collection logic in `collector.py` or `otel_collector.py`
3. Add analysis functions to `analyzer.py`
4. Update reporting in `reporter.py`
5. Add CLI commands to `cli.py`
6. Write tests in `tests/`
7. Update this README

## Troubleshooting

### Hook Not Running

1. **Check hook configuration**: Verify `~/.claude/settings.local.json` is correctly formatted
2. **Check permissions**: `chmod +x /path/to/local_trace_hook.sh`
3. **Check logs**: `cat ~/.claude-trace/hook.log`
4. **Verify path**: Ensure the path in settings is absolute, not relative

### No Sessions Found

1. **Check tracing is enabled**: `echo $CLAUDE_TRACE_ENABLED` should output `true`
2. **Manually analyze**: `claude-trace analyze ~/.claude/projects/your-project/session.jsonl --save`
3. **Check database**: `ls -la ~/.claude-trace/traces.db`

### OTEL Metrics Not Captured

1. **Check OTEL exporter**: `echo $OTEL_METRICS_EXPORTER` should output `console`
2. **Check output file**: `ls -la ~/.claude-trace/otel-output.txt`
3. **Check hook log**: Look for OTEL-related messages in `~/.claude-trace/hook.log`
4. **Manual import**: Try `claude-trace otel-import <session_id> /path/to/otel.txt`

### Permission Errors

```bash
# Ensure proper directory permissions
mkdir -p ~/.claude-trace
chmod 755 ~/.claude-trace

# Fix database permissions if needed
chmod 644 ~/.claude-trace/traces.db
```

### Installation Hangs or Takes Too Long

If `pip install -e .` hangs at "Installing build dependencies":

1. **Upgrade pip**: `pip install --upgrade pip`
2. **Clear pip cache**: `pip cache purge`
3. **Try direct install**: `pip install --no-build-isolation -e .`
4. **Check Python version**: Ensure you're using Python 3.8 or newer

### Debug Mode

Enable debug logging for more detailed information:

```bash
export CLAUDE_TRACE_DEBUG=true
```

Check the debug output in `~/.claude-trace/hook.log`.

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Related Projects

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) - The official Claude Code CLI
- [LangSmith](https://smith.langchain.com/) - Cloud-based LLM tracing (requires network)
- [tracing-claude-code (LangChain)](https://github.com/langchain-ai/tracing-claude-code) - LangSmith integration
- [OpenTelemetry](https://opentelemetry.io/) - Open-source observability framework

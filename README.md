# Claude Code Local Tracing

A **100% local** tracing solution for [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) that captures detailed traces without requiring any remote server connections.

## Features

- 🏠 **Completely Local**: All data stored in SQLite on your machine
- 📊 **Session Timeline**: Visualize the complete flow of conversations
- 🔧 **Tool Tracking**: Detailed tool usage with inputs, outputs, and latency
- 📈 **Token Analysis**: Track input/output tokens and cache hit rates
- ⏱️ **Time Breakdown**: Understand where time is spent (model vs tools)
- 📁 **Export Options**: JSON and HTML reports
- 🔄 **Live Watch Mode**: Monitor sessions in real-time
- 📡 **OTEL Metrics**: Capture OpenTelemetry metrics locally when transcript tokens are missing

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/Dtristone/tracing-claude-code-local
cd tracing-claude-code-local

# Install the package
pip install -e .

# Verify installation
claude-trace --help
```

### Configure Claude Code Hook

Add the local trace hook to your Claude Code settings:

1. Create or edit `~/.claude/settings.local.json`:

```json
{
  "hooks": {
    "stop": [
      {
        "command": "/path/to/tracing-claude-code-local/local_trace_hook.sh"
      }
    ]
  }
}
```

2. Set environment variable to enable tracing:

```bash
export CLAUDE_TRACE_ENABLED=true
```

### Analyze Existing Transcripts

You can analyze Claude Code transcript files directly:

```bash
# Analyze a specific transcript file
claude-trace analyze ~/.claude/projects/your-project/session.jsonl

# Save to database for later analysis
claude-trace analyze ~/.claude/projects/your-project/session.jsonl --save
```

## CLI Commands

### List Sessions

```bash
# List recent sessions
claude-trace list

# List with limit
claude-trace list --limit 10

# Sessions from last 7 days
claude-trace list --since 7d
```

### View Session Details

```bash
# Show session summary
claude-trace show <session_id>

# Show detailed timeline
claude-trace timeline <session_id>

# Show timeline with full content
claude-trace timeline <session_id> --verbose
```

### Tool Usage Analysis

```bash
# Show all tool usage
claude-trace tools <session_id>

# Filter by tool name
claude-trace tools <session_id> --name Read
```

### Statistics

```bash
# Session statistics
claude-trace stats <session_id>

# Aggregate statistics for all sessions
claude-trace stats --all
```

### Export Data

```bash
# Export as JSON
claude-trace export <session_id> --format json

# Export as HTML report
claude-trace export <session_id> --format html --output report.html
```

### Live Watch Mode

Monitor a session in real-time:

```bash
# Watch for new trace data
claude-trace watch

# Watch specific transcript
claude-trace watch --transcript /path/to/session.jsonl
```

### OTEL Metrics (for Missing Token Data)

When transcript files have zero token counts, you can capture OTEL metrics from Claude Code:

```bash
# Run Claude Code with OTEL console exporter
OTEL_METRICS_EXPORTER=console claude ... 2>&1 | tee /tmp/otel_output.txt

# Import OTEL metrics for a session
claude-trace otel-import <session_id> /tmp/otel_output.txt

# View OTEL metrics for a session
claude-trace otel <session_id>

# View aggregate OTEL metrics
claude-trace otel --all
```

The stats command automatically enriches token data from OTEL when transcript tokens are 0:

```bash
# Stats will show OTEL token data when transcript tokens are missing
claude-trace stats <session_id>
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

### Statistics View

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

Tool Usage:
  Read         2 calls, avg   100ms, total   200ms
  Bash         1 call,  avg 8.00s, total 8.00s

Performance:
  Avg Response Latency: 8.0s
  Retry Count: 0
  Error Count: 0
```

## Data Storage

All trace data is stored locally in SQLite:

- **Database Location**: `~/.claude-trace/traces.db`
- **Hook Log**: `~/.claude-trace/hook.log`

### Database Schema

The database includes tables for:
- `sessions`: Session metadata and timing
- `turns`: Conversation turns
- `messages`: User and assistant messages with token usage
- `tool_uses`: Tool invocations with inputs, outputs, and timing
- `otel_metrics`: OpenTelemetry metrics data points
- `otel_session_summary`: Aggregated OTEL metrics per session

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CLAUDE_TRACE_ENABLED` | Enable/disable local tracing | `true` |
| `CLAUDE_TRACE_DEBUG` | Enable debug logging | `false` |
| `CLAUDE_TRACE_LOG` | Log file path | `~/.claude-trace/hook.log` |
| `CLAUDE_TRACE_OTEL_DIR` | Directory for OTEL metrics files | `~/.claude-trace/otel-metrics` |
| `OTEL_METRICS_OUTPUT` | Path to OTEL console output file (for hook) | `~/.claude-trace/otel-output.txt` |

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Claude Code CLI                               │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  local_trace_hook.sh                                        │    │
│  │  - Triggered on Claude Code stop events                     │    │
│  │  - Reads transcript JSONL                                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     claude_trace (Python)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  collector   │  │   analyzer   │  │   reporter   │               │
│  │  Parse JSONL │  │  Statistics  │  │  Formatting  │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                     storage (SQLite)                          │   │
│  │                   ~/.claude-trace/traces.db                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           CLI Output                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  Terminal    │  │  JSON Export │  │  HTML Report │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
└─────────────────────────────────────────────────────────────────────┘
```

## Comparison with LangSmith Tracing

| Feature | Local Tracing | LangSmith |
|---------|---------------|-----------|
| Network Required | ❌ No | ✅ Yes |
| Privacy | ✅ All data local | ⚠️ Data sent to cloud |
| Cost | ✅ Free | 💰 Pricing tiers |
| Team Collaboration | ❌ Local only | ✅ Team sharing |
| Real-time Dashboards | ❌ No | ✅ Yes |
| Data Retention | ✅ You control | ⚠️ Based on plan |

## Development

### Running Tests

```bash
# Install test dependencies
pip install -e ".[dev]"

# Run unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=claude_trace --cov-report=html
```

### Project Structure

```
tracing-claude-code-local/
├── claude_trace/          # Python package
│   ├── __init__.py
│   ├── models.py          # Data models
│   ├── collector.py       # JSONL parsing
│   ├── analyzer.py        # Statistics computation
│   ├── storage.py         # SQLite persistence
│   ├── reporter.py        # Output formatting
│   ├── cli.py             # Command-line interface
│   └── utils.py           # Utility functions
├── local_trace_hook.sh    # Claude Code hook script
├── setup.py               # Package setup
├── requirements.txt       # Dependencies
├── PLAN.md                # Implementation plan
├── README.md              # This file
└── tests/                 # Test suite
```

## Troubleshooting

### Hook Not Running

1. Check hook configuration in `~/.claude/settings.local.json`
2. Verify hook script is executable: `chmod +x local_trace_hook.sh`
3. Check log file: `cat ~/.claude-trace/hook.log`

### No Sessions Found

1. Ensure `CLAUDE_TRACE_ENABLED=true` is set
2. Run `claude-trace analyze` on an existing transcript file
3. Check if database exists: `ls ~/.claude-trace/traces.db`

### Permission Errors

```bash
# Ensure proper permissions
chmod 755 ~/.claude-trace
chmod 644 ~/.claude-trace/traces.db
```

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please read the contributing guidelines before submitting PRs.

## Related Projects

- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) - The official Claude Code CLI
- [LangSmith](https://smith.langchain.com/) - Cloud-based LLM tracing (requires network)
- [tracing-claude-code (LangChain)](https://github.com/langchain-ai/tracing-claude-code) - LangSmith integration

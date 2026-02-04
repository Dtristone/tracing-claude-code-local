# Claude Code Local Tracing Implementation Plan

## Overview

This document outlines the implementation plan for a local-only tracing solution for Claude Code CLI. The solution captures detailed traces without requiring any remote server connections, storing all data locally in SQLite and JSON formats.

## Requirements

### Core Features
1. **Session Timeline**: Main process flow visualization for each session
2. **Model Tracking**: Input/output context, token counts, latency
3. **Tool Monitoring**: Tool name, input, output, latency for each tool use
4. **Operation Logging**: All operations with timestamps
5. **Time Analysis**: Breakdown of time spent in each phase
6. **Statistics**: Fail/retry counts, conversation loop metrics
7. **KV Cache Analysis**: Cache hit/miss statistics (when available)

### Design Principles
- **100% Local**: No network connections required
- **Non-intrusive**: Works with existing Claude Code hook system
- **Lightweight**: Minimal overhead during trace collection
- **Comprehensive**: Captures all available trace data
- **Easy Analysis**: CLI tools and optional HTML reports

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Claude Code CLI                               │
├─────────────────────────────────────────────────────────────────────┤
│  Hook System (stop_hook)                                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  local_trace_hook.sh (New)                                   │    │
│  │  - Reads transcript from Claude Code                        │    │
│  │  - Passes data to Python analyzer                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Local Trace Collector                           │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  claude_trace/collector.py                                  │    │
│  │  - Parse JSONL transcripts                                  │    │
│  │  - Extract session, model, tool data                        │    │
│  │  - Store in SQLite database                                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Local Storage                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │  SQLite DB       │  │  Raw JSONL       │  │  Analysis Cache  │   │
│  │  ~/.claude-trace │  │  (original)      │  │  (JSON)          │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Analysis & Visualization                        │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │  CLI Commands    │  │  HTML Reports    │  │  JSON Export     │   │
│  │  claude-trace    │  │  (optional)      │  │  (for tools)     │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## File Structure

```
claude_trace/
├── __init__.py              # Package initialization
├── models.py                # Data models (Session, Turn, Message, Tool)
├── collector.py             # Trace collection from JSONL transcripts
├── analyzer.py              # Analysis engine (timeline, stats, etc.)
├── storage.py               # SQLite storage layer
├── cli.py                   # Command-line interface
├── reporter.py              # Report generation (text, JSON, HTML)
└── utils.py                 # Utility functions

local_trace_hook.sh          # Claude Code hook script
setup.py                     # Package installation
requirements.txt             # Python dependencies
README.md                    # User documentation (updated)
```

## Data Models

### Session
```python
@dataclass
class Session:
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    total_duration_ms: Optional[int]
    turns: List[Turn]
    statistics: SessionStats
```

### Turn
```python
@dataclass
class Turn:
    turn_id: str
    turn_number: int
    user_message: Message
    assistant_messages: List[Message]
    tool_uses: List[ToolUse]
    start_time: datetime
    end_time: datetime
    duration_ms: int
```

### Message
```python
@dataclass
class Message:
    message_id: str
    role: str  # "user" or "assistant"
    content: List[ContentBlock]
    model: Optional[str]
    timestamp: datetime
    usage: Optional[TokenUsage]
```

### TokenUsage
```python
@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    total_tokens: int = 0
```

### ToolUse
```python
@dataclass
class ToolUse:
    tool_id: str
    tool_name: str
    input_data: Dict[str, Any]
    output_data: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    duration_ms: Optional[int]
    success: bool
    error: Optional[str]
```

### SessionStats
```python
@dataclass
class SessionStats:
    total_turns: int
    total_messages: int
    total_tool_uses: int
    total_tokens: TokenUsage
    avg_response_latency_ms: float
    tool_usage_breakdown: Dict[str, ToolStats]
    cache_hit_rate: float
    retry_count: int
    error_count: int
```

## CLI Commands

```bash
# Install
pip install -e .

# View recent sessions
claude-trace list [--limit N] [--since DATE]

# Show session details
claude-trace show <session_id>

# Show timeline
claude-trace timeline <session_id> [--verbose]

# Show tool usage
claude-trace tools <session_id> [--name TOOL_NAME]

# Show statistics
claude-trace stats <session_id>
claude-trace stats --all  # Aggregate stats

# Export data
claude-trace export <session_id> --format json|csv|html

# Watch live (during active session)
claude-trace watch [--session SESSION_ID]

# Analyze specific transcript
claude-trace analyze /path/to/transcript.jsonl
```

## Implementation Steps

### Phase 1: Core Infrastructure
1. Create Python package structure
2. Implement data models
3. Implement JSONL parser (reuse existing logic)
4. Implement SQLite storage layer

### Phase 2: Collection & Analysis
1. Create collector module
2. Implement analysis functions
3. Create statistics calculator

### Phase 3: CLI & Reports
1. Implement CLI commands
2. Create text-based reports
3. Optional: HTML report generator

### Phase 4: Integration
1. Create local_trace_hook.sh
2. Update documentation
3. Add tests

## Storage Schema (SQLite)

```sql
-- Sessions table
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time TEXT,
    total_duration_ms INTEGER,
    metadata TEXT  -- JSON
);

-- Turns table
CREATE TABLE turns (
    turn_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    turn_number INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_ms INTEGER,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- Messages table
CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    turn_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT,  -- JSON
    model TEXT,
    timestamp TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cache_read_tokens INTEGER,
    cache_creation_tokens INTEGER,
    FOREIGN KEY (turn_id) REFERENCES turns(turn_id)
);

-- Tool uses table
CREATE TABLE tool_uses (
    tool_id TEXT PRIMARY KEY,
    turn_id TEXT NOT NULL,
    message_id TEXT,
    tool_name TEXT NOT NULL,
    input_data TEXT,  -- JSON
    output_data TEXT,
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_ms INTEGER,
    success INTEGER,
    error TEXT,
    FOREIGN KEY (turn_id) REFERENCES turns(turn_id),
    FOREIGN KEY (message_id) REFERENCES messages(message_id)
);

-- Indexes for common queries
CREATE INDEX idx_turns_session ON turns(session_id);
CREATE INDEX idx_messages_turn ON messages(turn_id);
CREATE INDEX idx_tool_uses_turn ON tool_uses(turn_id);
CREATE INDEX idx_tool_uses_name ON tool_uses(tool_name);
```

## Example Output

### Timeline View
```
Session: abc-123-def
Started: 2025-02-04 10:30:00

Turn 1 [10:30:00 - 10:30:15] (15.2s)
├── User: "Read the config file and summarize it"
├── Assistant: "I'll read the config file..."
│   ├── Model: claude-sonnet-4-5
│   ├── Tokens: 150 in / 45 out (cache: 100 read)
│   └── Latency: 2.3s
├── Tool: Read (/config/settings.json)
│   ├── Duration: 0.1s
│   └── Output: 2.4KB
└── Assistant: "Here's the summary..."
    ├── Model: claude-sonnet-4-5
    ├── Tokens: 250 in / 120 out
    └── Latency: 5.8s

Turn 2 [10:30:15 - 10:30:45] (30.1s)
...

Summary:
  Total Duration: 45.3s
  Turns: 2
  Tool Uses: 3 (Read: 2, Bash: 1)
  Total Tokens: 1,250 in / 380 out
  Cache Hit Rate: 42%
```

### Statistics View
```
Session Statistics: abc-123-def

Time Breakdown:
  Total Duration:     45.3s
  Model Inference:    32.1s (70.9%)
  Tool Execution:      8.2s (18.1%)
  Processing:          5.0s (11.0%)

Token Usage:
  Input Tokens:       1,250
  Output Tokens:        380
  Cache Read:           520 (41.6% hit rate)
  Cache Created:        180

Tool Usage:
  Read:    2 calls, avg 0.1s, total 0.2s
  Bash:    1 call,  avg 8.0s, total 8.0s

Performance:
  Avg Response Latency: 8.0s
  Retry Count: 0
  Error Count: 0
```

## Timeline

| Phase | Task | Estimated Time |
|-------|------|----------------|
| 1 | Core Infrastructure | 2-3 hours |
| 2 | Collection & Analysis | 2-3 hours |
| 3 | CLI & Reports | 2-3 hours |
| 4 | Integration & Docs | 1-2 hours |

**Total: ~8-11 hours**

## Success Criteria

- [ ] Can collect traces from Claude Code sessions locally
- [ ] All trace data persisted in SQLite
- [ ] CLI can show timeline, tools, and statistics
- [ ] Works without any network connection
- [ ] Minimal performance overhead
- [ ] Clear documentation for installation and usage

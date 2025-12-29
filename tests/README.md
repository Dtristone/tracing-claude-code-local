# Test Suite for stop_hook.sh

Comprehensive pytest-based test suite for `stop_hook.sh`, which implements tracing from Claude Code -> LangSmith.

## Quick Start

```bash
# Install test dependencies
.venv/bin/pip install -r tests/requirements-test.txt

# Run all unit tests (no API key needed)
.venv/bin/pytest tests/unit/ -v

# Run with coverage
.venv/bin/pytest tests/unit/ --cov=tests --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Test Results

Current Status: **279 passing unit tests** covering comprehensive functionality ✅

### Test Coverage

#### Core Functions
- **Message Parsing** (6 tests): ✅ get_content, is_tool_result, get_tool_uses
- **Content Formatting** (13 tests): ✅ format_content, merge_assistant_parts, get_usage_from_parts
- **Utilities** (6 tests): ✅ get_microseconds, get_file_size
- **Cost Tracking** (7 tests): ✅ usage_metadata calculation, cache token tracking
- **Trace Ordering** (16 tests): ✅ dotted_order format, chronological sorting, parent-child relationships
- **Model Name Formatting** (15 tests): ✅ Date suffix stripping for cleaner model names
- **State Management** (5 tests): ✅ load_state, save_state with isolated environment

#### API & Network Operations (35 tests)
- **API Call Function** (6 tests): ✅ HTTP request handling, headers, timeout configuration
- **API Error Handling** (3 tests): ✅ POST/PATCH structure, timeout handling
- **Multipart Batch Sending** (9 tests): ✅ Batch uploads, temp file management, endpoint usage
- **Cleanup on Exit** (7 tests): ✅ Pending turn cleanup, error handling, trap configuration
- **API Key Handling** (3 tests): ✅ Environment variable fallback, validation
- **HTTP Response Handling** (4 tests): ✅ Success codes, error logging, response body handling
- **Project Configuration** (3 tests): ✅ Project name, API base URL configuration

#### Main Entry Point & Workflow (54 tests)
- **Hook Input Parsing** (6 tests): ✅ session_id, transcript_path extraction and validation
- **Stop Hook Active Flag** (2 tests): ✅ Recursive execution prevention
- **Incremental Processing** (6 tests): ✅ last_line tracking, awk-based skipping
- **Turn Grouping** (8 tests): ✅ User/assistant/tool message grouping logic
- **SSE Streaming Merge** (6 tests): ✅ Message ID tracking, part accumulation
- **State Updates** (4 tests): ✅ Session-specific state persistence
- **Execution Time Tracking** (5 tests): ✅ Duration calculation, slow execution warnings
- **Tracing Disabled Check** (3 tests): ✅ TRACE_TO_LANGSMITH validation
- **Required Commands** (4 tests): ✅ jq, curl, uuidgen availability checks
- **Final Turn Processing** (2 tests): ✅ Pending message handling at EOF
- **Main Logging** (4 tests): ✅ Session start, message counts, turn tracking
- **Main Integration** (4 tests): ✅ End-to-end validation with mocked environment

#### Timestamp Conversion (21 tests)
- **ISO to Dotted Order** (9 tests): ✅ Format conversion, padding, delimiter removal
- **Dotted Order Format** (2 tests): ✅ Timestamp format validation
- **Chronological Ordering** (3 tests): ✅ Sort order verification across timestamps
- **Edge Cases** (5 tests): ✅ Midnight, end-of-day, zero milliseconds, leap years
- **Real Transcript Data** (2 tests): ✅ Actual timestamp format from cc_transcript.jsonl

#### Multipart Serialization (29 tests)
- **Serialize Function** (11 tests): ✅ Operation/run_json/temp_dir parameters, file creation
- **File Naming** (4 tests): ✅ Main/inputs/outputs file naming conventions
- **Data Separation** (4 tests): ✅ Excluding inputs/outputs from main data
- **Integration Tests** (6 tests): ✅ POST/PATCH operations, file existence validation
- **Curl Format** (4 tests): ✅ -F arguments, Content-Length headers, part naming

#### Trace Creation (65 tests)
- **Create Trace Function** (6 tests): ✅ Parameter acceptance and structure
- **Turn Run Creation** (8 tests): ✅ Chain type, UUID generation, dotted_order, tags
- **Assistant Run Creation** (8 tests): ✅ LLM type, parent relationships, model metadata
- **Tool Run Creation** (7 tests): ✅ Tool type, inputs, parent relationships
- **Tool Result Finding** (5 tests): ✅ Result lookup by ID, timestamp extraction
- **Usage Metadata** (6 tests): ✅ Token counts, cache tracking, input/output details
- **Dotted Order Hierarchy** (3 tests): ✅ Parent-child dotted_order relationships
- **Outputs Accumulation** (4 tests): ✅ Message accumulation across LLM calls
- **Batch Processing** (10 tests): ✅ POST/PATCH batch creation and submission
- **Current Turn Tracking** (2 tests): ✅ CURRENT_TURN_ID for cleanup
- **Multiple LLM Calls** (4 tests): ✅ Iteration, numbering, context accumulation
- **Logging** (2 tests): ✅ Turn creation, LLM call logging

## Test Structure

```
tests/
├── conftest.py              # Pytest fixtures
├── pytest.ini               # Pytest configuration
├── requirements-test.txt    # Test dependencies
├── unit/                    # Unit tests (no external dependencies)
│   ├── test_message_parsing.py      # Content extraction (6 tests)
│   ├── test_content_formatting.py   # LangSmith format (13 tests)
│   ├── test_state_management.py     # State persistence (5 tests)
│   ├── test_utilities.py            # Cross-platform utils (6 tests)
│   ├── test_cost_tracking.py        # Token usage & cost (7 tests)
│   ├── test_trace_ordering.py       # Timestamp ordering (16 tests)
│   ├── test_model_name_formatting.py # Model name cleaning (15 tests)
│   ├── test_api_calls.py            # API operations & batch sending (35 tests)
│   ├── test_main_entry.py           # Main workflow & entry point (54 tests)
│   ├── test_timestamp_conversion.py # ISO to dotted_order conversion (21 tests)
│   ├── test_multipart_serialization.py # Multipart file handling (29 tests)
│   └── test_trace_creation.py       # Trace structure & hierarchy (65 tests)
├── helpers/                 # Test utilities
│   ├── bash_runner.py       # Execute bash functions in isolation
│   ├── langsmith_client.py  # LangSmith API helpers
│   ├── transcript_parser.py # JSONL test data generation
│   └── state_manager.py     # State file management
└── test_data/              # Test fixtures
    ├── minimal_transcript.jsonl
    ├── multi_turn.jsonl
    ├── with_tools.jsonl
    └── streaming_sse.jsonl
```

## Key Features

### 1. BashRunner - Test Bash Functions in Isolation

```python
from tests.helpers.bash_runner import BashRunner

runner = BashRunner()

# Call any bash function from stop_hook.sh
result = runner.call_function("get_content", '{"message": {"content": "hello"}}')
print(result)  # "hello"
```

### 2. TranscriptBuilder - Generate Test Data

```python
from tests.helpers.transcript_parser import TranscriptBuilder

builder = TranscriptBuilder(Path("test.jsonl"))
builder.add_user_message("Hello")
builder.add_assistant_message("Hi there!")
builder, tool_id = builder.add_tool_use("Read", {"file_path": "/test.txt"})
builder.add_tool_result(tool_id, "File content")
builder.build()
```

### 3. LangSmith Client - Verify Traces

```python
from tests.helpers.langsmith_client import LangSmithTestClient

client = LangSmithTestClient()

# Fetch traces
traces = client.fetch_traces(limit=10)

# Get child runs
children = client.get_child_runs(parent_run_id)
```

## Running Tests

### Unit Tests Only (Default)

```bash
# Run all unit tests
.venv/bin/pytest tests/unit/ -v

# Run specific test file
.venv/bin/pytest tests/unit/test_message_parsing.py -v

# Run specific test
.venv/bin/pytest tests/unit/test_message_parsing.py::TestGetContent::test_get_content_from_message_wrapper -v
```

### With Coverage

```bash
# Generate coverage report
.venv/bin/pytest tests/unit/ --cov=tests --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/index.html
```

### Integration Tests (Future)

Integration tests require `CC_LANGSMITH_API_KEY`:

```bash
# Run integration tests
CC_LANGSMITH_API_KEY="your_key" .venv/bin/pytest tests/integration/ -v -m integration
```

## Test Fixtures

### Sample Data Fixtures (conftest.py)

- `sample_user_message` - Example user message
- `sample_assistant_message` - Assistant message with tool use
- `sample_tool_result` - Tool result message
- `sample_streaming_parts` - SSE streaming parts

### Helper Fixtures

- `bash_executor` - BashRunner instance
- `langsmith_client` - LangSmith API client
- `state_manager` - State file manager
- `transcript_builder` - Transcript generator
- `temp_state_file` - Isolated state file
- `temp_transcript` - Temporary transcript path

### Example Usage

```python
def test_example(bash_executor, sample_assistant_message):
    msg = json.dumps(sample_assistant_message)
    result = bash_executor.call_function("get_content", msg)
    content = json.loads(result)
    assert len(content) == 3
```

## Troubleshooting

### Tests Failing with "Function not found"

The bash_runner removes the early exit check from stop_hook.sh. If functions are not found, ensure:
1. stop_hook.sh is in the correct location
2. The sed pattern matches the early exit block

### State Management Tests Using Real State File

The `STATE_FILE` environment variable should point to a temp file, but stop_hook.sh has it hardcoded. To fix:
- Modify stop_hook.sh line 47 to: `STATE_FILE="${STATE_FILE:-$HOME/.claude/state/langsmith_state.json}"`
- Or: Run tests in isolation and clean up afterwards

### Integration Tests Require API Key

Integration tests need a valid LangSmith API key:

```bash
export CC_LANGSMITH_API_KEY="lsv2_pt_..."
.venv/bin/pytest tests/integration/ -v -m integration
```

## Contributing

When adding new functions to stop_hook.sh:

1. Add corresponding unit tests
2. Use BashRunner to test in isolation
3. Add sample fixtures if needed
4. Ensure 80%+ test coverage
5. Run tests before committing

Example:

```python
def test_new_function(bash_executor):
    """Test description"""
    result = bash_executor.call_function("new_function", "arg1", "arg2")
    assert result == "expected_value"
```
# Implementation Plan: Subagent Tracing in LangSmith

## Overview
Add comprehensive subagent tracing to `stop_hook.sh` to capture Task tool executions and their agent transcript conversations as nested runs in LangSmith.

## User Requirements
- Trace ALL Task tool invocations (all subagent_types: Explore, Plan, etc.)
- Create individual child runs for each agent message (user/assistant/tool within agent)
- Agent files stored in same directory as main transcript: `agent-{agentId}.jsonl`
- Correlate using `agentId` from `toolUseResult` field in main transcript

## Current Architecture

### Main Transcript Structure
- Location: Passed as `transcript_path` in hook input (e.g., `cc_transcript.jsonl`)
- Contains: User messages, assistant messages with tool_use, tool_result messages
- Task tools have special `toolUseResult.agentId` field in tool_result messages

### Agent Transcript Structure
- Location: Same directory as main transcript, named `agent-{agentId}.jsonl`
- Format: One JSON object per line, same schema as main transcript
- Contains: Agent's internal conversation (user prompts, assistant responses, tool calls)

### Current Tool Processing (stop_hook.sh lines 599-695)
- Iterates through tool_uses from assistant messages
- Creates tool runs as siblings of assistant (both children of turn)
- Matches tool results using `find_tool_result_with_timestamp()`
- Batches POST/PATCH operations with `send_multipart_batch()`

## Implementation Steps

### 1. Add Detection Functions (Insert after line 263)

**New functions:**
```bash
# Check if tool is a Task tool
is_task_tool() {
    local tool="$1"
    local tool_name=$(echo "$tool" | jq -r '.name // ""')
    [ "$tool_name" = "Task" ]
}

# Extract agentId from tool result
get_agent_id_from_result() {
    local tool_use_id="$1"
    local tool_results="$2"

    echo "$tool_results" | jq -r --arg id "$tool_use_id" '
        first(
            .[] |
            select(.toolUseResult.agentId != null) |
            select(
                (.message.content // .content) as $content |
                if $content | type == "array" then
                    $content[] | select(.type == "tool_result" and .tool_use_id == $id)
                else false end
            ) |
            .toolUseResult.agentId
        ) // ""
    '
}

# Get path to agent transcript file
get_agent_transcript_path() {
    local transcript_path="$1"
    local agent_id="$2"
    local transcript_dir=$(dirname "$transcript_path")
    echo "${transcript_dir}/agent-${agent_id}.jsonl"
}
```

**Purpose:** Identify Task tools and locate corresponding agent files

### 2. Add Agent Processing Function (Insert after detection functions)

**New function:** `process_agent_transcript()`

**Parameters:**
- `parent_tool_id`: Task tool's run ID (parent for agent messages)
- `agent_id`: Agent identifier (e.g., "558bc970")
- `main_transcript_path`: Path to main transcript for deriving agent file path
- `tool_result_timestamp`: Timestamp from tool_result for ordering
- `parent_dotted_order`: Task tool's dotted_order for hierarchy
- `trace_id`: Trace ID for all runs in this trace
- `posts_batch_ref`: Variable name containing posts batch array
- `patches_batch_ref`: Variable name containing patches batch array

**Logic:**
1. Derive agent file path from main transcript path + agent_id
2. Check if agent file exists (graceful exit if not)
3. Read agent file line by line
4. For each agent message:
   - Extract role (assistant/user), timestamp, content
   - Skip tool_result messages (they're already processed)
   - Create run with proper dotted_order: `{parent_tool_order}.{msg_timestamp}{msg_uuid}`
   - For assistant messages: Extract model, usage, tool_uses
   - For assistant with tool_uses: Create child tool runs
   - Add to posts_batch and patches_batch using indirect variable refs

**Key features:**
- Handles nested tool calls within agent
- Preserves timestamps from agent transcript
- Maintains proper hierarchy via dotted_order
- Efficient: line-by-line processing, no full file load

### 3. Integrate into Tool Processing Loop (Modify lines 599-695)

**Insert point:** Line 690 (after Task tool POST, before tool PATCH)

**Integration code:**
```bash
# After creating the tool run (POST)...

# Check if this is a Task tool
if is_task_tool "$tool"; then
    debug "Detected Task tool: $tool_name"

    # Extract agentId from tool result
    local agent_id
    agent_id=$(get_agent_id_from_result "$tool_use_id" "$tool_results")

    if [ -n "$agent_id" ]; then
        debug "Found agentId: $agent_id for tool $tool_use_id"

        # Process agent transcript
        process_agent_transcript \
            "$tool_id" \
            "$agent_id" \
            "$transcript_path" \
            "$tool_result_timestamp" \
            "$tool_dotted_order" \
            "$trace_id" \
            "posts_batch" \
            "patches_batch"
    else
        debug "No agentId found for Task tool $tool_use_id"
    fi
fi

# Then create tool completion (PATCH)...
```

**Rationale:**
- Task tool run must exist before agent messages can reference it as parent
- Agent processing happens between tool creation and completion
- All runs batched together for efficient API submission

### 4. Store Transcript Path (Modify line 805)

**Current:**
```bash
local transcript_path
transcript_path=$(echo "$hook_input" | jq -r '.transcript_path // ""' | sed "s|^~|$HOME|")
```

**Required:** Ensure `transcript_path` variable is accessible in `create_trace()` function scope

**Solution:** Pass `transcript_path` as parameter to `create_trace()` or make it a global variable accessible throughout the script

## LangSmith Run Hierarchy

**Before (current):**
```
Turn (Claude Code chain)
├── Assistant (llm)
├── Read (tool)
├── Assistant (llm)
└── Edit (tool)
```

**After (with agents):**
```
Turn (Claude Code chain)
├── Assistant (llm)
├── Task (tool)
│   ├── Agent: claude-haiku-4-5 (llm)
│   ├── Glob (tool)
│   ├── Read (tool)
│   ├── Agent: claude-haiku-4-5 (llm)
│   └── Bash (tool)
├── Assistant (llm)
└── Edit (tool)
```

**Key relationships:**
- Turn run = parent for both main assistant AND all tools (including Task)
- Task tool run = parent for all agent messages and agent tools
- Agent assistant runs = children of Task tool
- Agent tool calls = siblings of agent assistant runs (both children of Task tool)
- All share same trace_id for unified trace view

**Important:** Tools are siblings of assistants, not nested under them. This matches Claude Code's execution model where tool calls happen between assistant messages.

## Dotted Order Management

**Format:** `YYYYMMDDTHHMMSSffffffZ{uuid}`

**Hierarchy encoding:**
- Turn: `20251216T174404397000Z{turn_uuid}`
- Task tool: `{turn_order}.{tool_timestamp}{tool_uuid}`
- Agent message: `{tool_order}.{agent_msg_timestamp}{agent_msg_uuid}`
- Agent tool: `{agent_msg_order}.{agent_tool_timestamp}{agent_tool_uuid}`

**Example:**
```
Turn:         20251216T174404397000Za1b2c3d4
Task tool:    20251216T174404397000Za1b2c3d4.20251216T174455000000Zi9j0k1l2
Agent msg:    20251216T174404397000Za1b2c3d4.20251216T174455000000Zi9j0k1l2.20251216T174409317000Zm3n4o5p6
Agent tool:   20251216T174404397000Za1b2c3d4.20251216T174455000000Zi9j0k1l2.20251216T174409317000Zm3n4o5p6.20251216T174410733000Zq7r8s9t0
```

LangSmith sorts runs lexicographically by dotted_order, ensuring proper visual hierarchy.

## Error Handling

**Missing agent file:**
- Check: `[ ! -f "$agent_file" ]`
- Action: Log debug message, return gracefully
- Impact: Main trace completes normally, just without agent details

**Empty agent transcript:**
- Check: `[ -z "$agent_messages" ]`
- Action: Log debug message, return gracefully

**Invalid JSON in agent file:**
- Mitigation: Use `jq` with `2>/dev/null` and `|| echo ""` fallbacks
- Parse errors don't crash hook

**Large agent transcripts (100+ messages):**
- Solution: Line-by-line processing with `while read`
- Memory efficient, no timeout issues expected

## Performance Considerations

**Current:** 10 turns × 5 tools = ~100 operations → 2 API calls (POST + PATCH batches) → ~2-5s

**With agents:** 10 turns × 1 Task × 20 agent messages = +400 operations → Same 2 API calls → ~5-10s

**Optimization:**
- Agent runs added to existing batches (no extra API calls)
- Multipart batch endpoint handles large payloads efficiently
- Line-by-line processing prevents memory issues

## Testing Strategy

**Test cases:**
1. Single Task tool with 5 agent messages → Verify 1 Task + 5 child runs
2. Multiple Task tools in same turn → Verify independent agent hierarchies
3. Missing agent file → Verify graceful degradation
4. Agent with tool calls → Verify nested tool runs under agent assistant
5. Large agent (50+ messages) → Verify performance <10s

**Validation:**
- Agent runs appear as children of Task in LangSmith UI
- Timestamps accurate, dotted_order correct
- Usage metadata captured for agent LLM calls
- Tags distinguish agent runs ("agent", "subagent", "agent-tool")

## Critical Files

**Primary:**
- `/Users/tanushreesharma/tracing-claude-code/stop_hook.sh` - Main implementation file
  - Lines 263: Insert detection functions (~30 lines)
  - After 263: Insert processing function (~250 lines)
  - Line 690: Insert integration code (~20 lines)
  - Line 805: Ensure transcript_path accessible

**Reference:**
- `cc_transcript.jsonl` - Example main transcript with Task tools
- `agent-*.jsonl` - Example agent transcripts
- `$HOME/.claude/state/hook.log` - Debug output for troubleshooting

## Rollout Plan

**Phase 1: Core Implementation**
- Add detection and processing functions
- Integrate into tool loop
- Test with simple Task tool (single agent, few messages)

**Phase 2: Validation**
- Test with multiple Task tools
- Test with large agent transcripts
- Verify LangSmith UI displays correctly

**Phase 3: Production**
- Enable in production environment
- Monitor logs for errors
- Collect user feedback

## Success Criteria

✓ All Task tool invocations traced with agent details
✓ Agent messages appear as proper child runs in LangSmith
✓ Correct hierarchy and ordering maintained
✓ No performance degradation (hook completes in <10s)
✓ Graceful handling of missing/invalid agent files
✓ Clear debug logging for troubleshooting

## Edge Cases

**Nested Task tools:** Agent calls Task → creates sub-agent
- Handled: Recursive processing via `process_agent_transcript`
- Limit: Consider depth limit (max 3 levels) if performance issues

**Concurrent agents:** Multiple Task tools in same turn
- Handled: Each agent processed independently in loop
- No conflicts (unique agentId, separate files)

**Agent file not yet written:** Hook runs before agent file created
- Handled: File check returns gracefully
- Next hook execution will pick it up if tool_result present

## Implementation Estimate

**Code size:**
- Detection functions: ~30 lines
- Processing function: ~250 lines
- Integration code: ~20 lines
- **Total new code: ~300 lines**

**Effort:**
- Implementation: 4-6 hours
- Testing: 2-3 hours
- Documentation: 1 hour
- **Total: ~1 day**

**Risk level:** Medium
- Touching production hook script
- Complex nested structure
- Multiple edge cases to handle
- Mitigated by: Graceful error handling, extensive testing, debug logging

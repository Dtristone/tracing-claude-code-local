#!/bin/bash
###
# Claude Code Local Trace Hook
# Collects trace data locally without sending to any external server.
###

set -e

# Config
LOG_FILE="${CLAUDE_TRACE_LOG:-$HOME/.claude-trace/hook.log}"
DEBUG="${CLAUDE_TRACE_DEBUG:-false}"

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Logging functions
log() {
    local level="$1"
    shift
    echo "$(date '+%Y-%m-%d %H:%M:%S') [$level] $*" >> "$LOG_FILE"
}

debug() {
    if [ "$DEBUG" = "true" ]; then
        log "DEBUG" "$@"
    fi
}

debug "Local trace hook started"

# Exit early if local tracing disabled
if [ "$(echo "$CLAUDE_TRACE_ENABLED" | tr '[:upper:]' '[:lower:]')" = "false" ]; then
    debug "Local tracing disabled, exiting"
    exit 0
fi

# Read hook input from stdin
HOOK_INPUT=$(cat)

# Extract session info
SESSION_ID=$(echo "$HOOK_INPUT" | jq -r '.session_id // ""')
TRANSCRIPT_PATH=$(echo "$HOOK_INPUT" | jq -r '.transcript_path // ""' | sed "s|^~|$HOME|")

if [ -z "$SESSION_ID" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
    debug "Invalid input: session=$SESSION_ID, transcript=$TRANSCRIPT_PATH"
    exit 0
fi

log "INFO" "Processing session $SESSION_ID from $TRANSCRIPT_PATH"

# Run the Python collector
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if claude-trace is available
if command -v claude-trace &> /dev/null; then
    claude-trace analyze "$TRANSCRIPT_PATH" --session-id "$SESSION_ID" --save >> "$LOG_FILE" 2>&1 || {
        log "ERROR" "Failed to analyze transcript"
        exit 0
    }
elif [ -f "$SCRIPT_DIR/claude_trace/cli.py" ]; then
    # Try running directly with Python
    python3 "$SCRIPT_DIR/claude_trace/cli.py" analyze "$TRANSCRIPT_PATH" --session-id "$SESSION_ID" --save >> "$LOG_FILE" 2>&1 || {
        log "ERROR" "Failed to analyze transcript with Python"
        exit 0
    }
else
    log "ERROR" "claude-trace not found. Install with: pip install -e $SCRIPT_DIR"
    exit 0
fi

log "INFO" "Session $SESSION_ID processed successfully"
exit 0

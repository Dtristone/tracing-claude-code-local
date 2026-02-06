#!/bin/bash
###
# Claude Code Local Trace Hook
# Collects trace data locally without sending to any external server.
# Also captures OTEL metrics when OTEL_METRICS_EXPORTER=console is set.
###

set -e

# Config
LOG_FILE="${CLAUDE_TRACE_LOG:-$HOME/.claude-trace/hook.log}"
LOCAL_OTEL_DIR="${CLAUDE_TRACE_OTEL_DIR:-$HOME/.claude-trace/otel-metrics}"
DEBUG="${CLAUDE_TRACE_DEBUG:-false}"

# Ensure directories exist
mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$LOCAL_OTEL_DIR"

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

# Get or generate OTEL log file path for this session using the mapping system
OTEL_LOG_FILE=""
if command -v claude-trace &> /dev/null; then
    OTEL_LOG_FILE=$(claude-trace otel-auto "$SESSION_ID" --description "Auto-captured from hook" 2>/dev/null) || true
elif [ -f "$SCRIPT_DIR/claude_trace/cli.py" ]; then
    OTEL_LOG_FILE=$(python3 -m claude_trace.cli otel-auto "$SESSION_ID" --description "Auto-captured from hook" 2>/dev/null) || true
fi

if [ -n "$OTEL_LOG_FILE" ]; then
    log "INFO" "Using OTEL log file: $OTEL_LOG_FILE"
fi

# Capture OTEL metrics if available
# Check if OTEL console output file exists (created by OTEL_METRICS_EXPORTER=console)
OTEL_OUTPUT_FILE="${OTEL_METRICS_OUTPUT:-$HOME/.claude-trace/otel-output.txt}"

if [ -f "$OTEL_OUTPUT_FILE" ] && [ -s "$OTEL_OUTPUT_FILE" ]; then
    log "INFO" "Found OTEL metrics output, capturing for session $SESSION_ID"
    
    # Copy OTEL output to the mapped log file if available
    if [ -n "$OTEL_LOG_FILE" ]; then
        cp "$OTEL_OUTPUT_FILE" "$OTEL_LOG_FILE" 2>/dev/null || true
        log "INFO" "Copied OTEL output to mapped log file: $OTEL_LOG_FILE"
    fi
    
    # Import OTEL metrics
    if command -v claude-trace &> /dev/null; then
        claude-trace otel-capture "$SESSION_ID" --input-file "$OTEL_OUTPUT_FILE" --quiet >> "$LOG_FILE" 2>&1 || {
            log "WARN" "Failed to capture OTEL metrics"
        }
    elif [ -f "$SCRIPT_DIR/claude_trace/cli.py" ]; then
        python3 -m claude_trace.cli otel-capture "$SESSION_ID" --input-file "$OTEL_OUTPUT_FILE" --quiet >> "$LOG_FILE" 2>&1 || {
            log "WARN" "Failed to capture OTEL metrics with Python"
        }
    fi
    
    # Archive the OTEL output
    mv "$OTEL_OUTPUT_FILE" "$LOCAL_OTEL_DIR/${SESSION_ID}_raw.txt" 2>/dev/null || true
    log "INFO" "OTEL metrics captured and archived for session $SESSION_ID"
fi

# Also check for session-specific OTEL file (alternative naming)
SESSION_OTEL_FILE="$LOCAL_OTEL_DIR/${SESSION_ID}_otel.txt"
if [ -f "$SESSION_OTEL_FILE" ] && [ -s "$SESSION_OTEL_FILE" ]; then
    log "INFO" "Found session-specific OTEL file, capturing for session $SESSION_ID"
    
    if command -v claude-trace &> /dev/null; then
        claude-trace otel-capture "$SESSION_ID" --input-file "$SESSION_OTEL_FILE" --quiet >> "$LOG_FILE" 2>&1 || {
            log "WARN" "Failed to capture session OTEL metrics"
        }
    elif [ -f "$SCRIPT_DIR/claude_trace/cli.py" ]; then
        python3 -m claude_trace.cli otel-capture "$SESSION_ID" --input-file "$SESSION_OTEL_FILE" --quiet >> "$LOG_FILE" 2>&1 || {
            log "WARN" "Failed to capture session OTEL metrics with Python"
        }
    fi
    
    log "INFO" "Session OTEL metrics captured for session $SESSION_ID"
fi

# Import resource logs if available
RESOURCE_LOG_DIR="${CLAUDE_TRACE_RESOURCE_DIR:-$HOME/.claude-trace/resource-logs}"
if [ -d "$RESOURCE_LOG_DIR" ]; then
    # Find the most recent resource log for this session
    RESOURCE_LOG=$(ls -t "$RESOURCE_LOG_DIR/${SESSION_ID}"*_resource.jsonl 2>/dev/null | head -1)
    
    if [ -n "$RESOURCE_LOG" ] && [ -f "$RESOURCE_LOG" ] && [ -s "$RESOURCE_LOG" ]; then
        log "INFO" "Found resource log file, importing for session $SESSION_ID"
        
        if command -v claude-trace &> /dev/null; then
            claude-trace resource-import "$SESSION_ID" "$RESOURCE_LOG" >> "$LOG_FILE" 2>&1 || {
                log "WARN" "Failed to import resource logs"
            }
        elif [ -f "$SCRIPT_DIR/claude_trace/cli.py" ]; then
            python3 -m claude_trace.cli resource-import "$SESSION_ID" "$RESOURCE_LOG" >> "$LOG_FILE" 2>&1 || {
                log "WARN" "Failed to import resource logs with Python"
            }
        fi
        
        log "INFO" "Resource logs imported for session $SESSION_ID"
    fi
fi

exit 0

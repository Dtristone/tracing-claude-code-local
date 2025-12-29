#!/bin/bash

# Test script to manually trigger the stop hook with cc_transcript.jsonl

# Set the session ID from the transcript
SESSION_ID="6bb19f49-d296-485d-8eb8-c5cbb8a9b80d"
TRANSCRIPT_PATH="$HOME/tracing-claude-code/cc_transcript.jsonl"

# Create hook input
HOOK_INPUT=$(jq -n \
    --arg sid "$SESSION_ID" \
    --arg path "$TRANSCRIPT_PATH" \
    '{
        session_id: $sid,
        transcript_path: $path,
        stop_hook_active: false
    }')

echo "Testing hook with cc_transcript.jsonl..."
echo "Session ID: $SESSION_ID"
echo

# Call the hook
echo "$HOOK_INPUT" | bash ./stop_hook.sh

echo
echo "Done! Check ~/.claude/state/hook.log for details"

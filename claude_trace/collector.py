"""
Trace collector for Claude Code local tracing.

Parses JSONL transcript files from Claude Code and extracts structured trace data.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from claude_trace.models import (
    ContentBlock,
    ContentType,
    Message,
    MessageRole,
    Session,
    TokenUsage,
    ToolUse,
    Turn,
)
from claude_trace.utils import generate_id, get_nested, parse_timestamp


class TraceCollector:
    """Collects and parses trace data from Claude Code transcripts."""
    
    def __init__(self, storage=None):
        """
        Initialize the collector.
        
        Args:
            storage: Optional TraceStorage instance for persistence
        """
        self.storage = storage
        self._pending_tool_uses: Dict[str, ToolUse] = {}  # tool_use_id -> ToolUse
    
    def collect_from_file(
        self, 
        transcript_path: str,
        session_id: Optional[str] = None
    ) -> Session:
        """
        Collect trace data from a JSONL transcript file.
        
        Args:
            transcript_path: Path to the JSONL transcript file
            session_id: Optional session ID (derived from filename if not provided)
            
        Returns:
            Session object with collected trace data
        """
        path = Path(transcript_path)
        if not path.exists():
            raise FileNotFoundError(f"Transcript file not found: {transcript_path}")
        
        # Derive session ID from filename if not provided
        if not session_id:
            session_id = path.stem
        
        # Parse all messages from the file
        messages = list(self._parse_jsonl(transcript_path))
        
        if not messages:
            return Session(
                session_id=session_id,
                start_time=datetime.now(),
                turns=[]
            )
        
        # Group messages into turns
        turns = self._group_into_turns(messages)
        
        # Create session
        session = Session(
            session_id=session_id,
            turns=turns,
            metadata={"transcript_path": transcript_path}
        )
        
        # Set session times from turns
        if turns:
            session.start_time = turns[0].start_time
            session.end_time = turns[-1].end_time
        
        # Save to storage if available
        if self.storage:
            self.storage.save_session(session)
        
        return session
    
    def collect_incremental(
        self,
        transcript_path: str,
        session_id: str,
        last_line: int = 0
    ) -> Tuple[Session, int]:
        """
        Collect trace data incrementally from new lines in transcript.
        
        Args:
            transcript_path: Path to the JSONL transcript file
            session_id: Session ID
            last_line: Last processed line number
            
        Returns:
            Tuple of (Session with new turns, new last_line)
        """
        path = Path(transcript_path)
        if not path.exists():
            raise FileNotFoundError(f"Transcript file not found: {transcript_path}")
        
        # Read new lines
        new_messages = []
        current_line = 0
        
        with open(path, 'r') as f:
            for line in f:
                current_line += 1
                if current_line <= last_line:
                    continue
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        new_messages.append(data)
                    except json.JSONDecodeError:
                        continue
        
        if not new_messages:
            # Return existing session if available
            existing = self.storage.get_session(session_id) if self.storage else None
            if existing:
                return existing, last_line
            return Session(session_id=session_id, turns=[]), last_line
        
        # Group new messages into turns
        new_turns = self._group_into_turns(new_messages)
        
        # Get or create session
        session = None
        if self.storage:
            session = self.storage.get_session(session_id)
        
        if session:
            # Merge new turns
            existing_turn_count = len(session.turns)
            for i, turn in enumerate(new_turns):
                turn.turn_number = existing_turn_count + i + 1
            session.turns.extend(new_turns)
            if new_turns:
                session.end_time = new_turns[-1].end_time
        else:
            session = Session(
                session_id=session_id,
                turns=new_turns,
                metadata={"transcript_path": transcript_path}
            )
            if new_turns:
                session.start_time = new_turns[0].start_time
                session.end_time = new_turns[-1].end_time
        
        # Save to storage
        if self.storage:
            self.storage.save_session(session)
        
        return session, current_line
    
    def _parse_jsonl(self, path: str) -> Iterator[Dict[str, Any]]:
        """Parse JSONL file and yield message dictionaries."""
        with open(path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
    
    def _group_into_turns(self, messages: List[Dict[str, Any]]) -> List[Turn]:
        """
        Group messages into conversation turns.
        
        A turn starts with a user message (non-tool-result) and includes
        all subsequent assistant messages and tool results until the next
        user message.
        """
        turns = []
        current_turn: Optional[Turn] = None
        current_assistant_parts: Dict[str, List[Dict]] = {}  # msg_id -> parts
        turn_number = 0
        
        for msg_data in messages:
            role = self._get_role(msg_data)
            
            if role == "user":
                # Check if this is a tool result
                if self._is_tool_result(msg_data):
                    if current_turn:
                        # Finalize any pending assistant messages first
                        # so that tool_uses are in _pending_tool_uses
                        if current_assistant_parts:
                            self._finalize_assistant_messages(
                                current_turn,
                                current_assistant_parts
                            )
                            current_assistant_parts = {}
                        
                        # Process tool result
                        self._process_tool_result(current_turn, msg_data)
                else:
                    # Finalize previous turn
                    if current_turn and current_assistant_parts:
                        self._finalize_assistant_messages(
                            current_turn, 
                            current_assistant_parts
                        )
                    
                    if current_turn:
                        self._finalize_turn(current_turn)
                        turns.append(current_turn)
                    
                    # Start new turn
                    turn_number += 1
                    current_turn = Turn(
                        turn_id=generate_id(),
                        turn_number=turn_number,
                        user_message=self._parse_user_message(msg_data)
                    )
                    current_assistant_parts = {}
            
            elif role == "assistant" and current_turn:
                # Accumulate assistant message parts (for SSE streaming)
                msg_id = get_nested(msg_data, "message", "id") or generate_id()
                if msg_id not in current_assistant_parts:
                    current_assistant_parts[msg_id] = []
                current_assistant_parts[msg_id].append(msg_data)
        
        # Finalize last turn
        if current_turn:
            if current_assistant_parts:
                self._finalize_assistant_messages(current_turn, current_assistant_parts)
            self._finalize_turn(current_turn)
            turns.append(current_turn)
        
        return turns
    
    def _get_role(self, msg_data: Dict[str, Any]) -> str:
        """Extract role from message data."""
        if "message" in msg_data:
            return msg_data["message"].get("role", "unknown")
        return msg_data.get("role", "unknown")
    
    def _is_tool_result(self, msg_data: Dict[str, Any]) -> bool:
        """Check if message is a tool result."""
        content = self._get_content(msg_data)
        if isinstance(content, list):
            return any(
                isinstance(c, dict) and c.get("type") == "tool_result"
                for c in content
            )
        return False
    
    def _get_content(self, msg_data: Dict[str, Any]) -> Any:
        """Extract content from message data."""
        if "message" in msg_data:
            return msg_data["message"].get("content")
        return msg_data.get("content")
    
    def _parse_user_message(self, msg_data: Dict[str, Any]) -> Message:
        """Parse a user message from raw data."""
        content = self._get_content(msg_data)
        timestamp = parse_timestamp(msg_data.get("timestamp", ""))
        
        # Convert content to ContentBlocks
        content_blocks = []
        if isinstance(content, str):
            content_blocks = [ContentBlock(type=ContentType.TEXT, text=content)]
        elif isinstance(content, list):
            content_blocks = [ContentBlock.from_dict(c) for c in content]
        
        return Message(
            message_id=generate_id(),
            role=MessageRole.USER,
            content=content_blocks,
            timestamp=timestamp,
            raw_data=msg_data
        )
    
    def _parse_assistant_message(
        self, 
        parts: List[Dict[str, Any]]
    ) -> Message:
        """
        Parse an assistant message from accumulated parts.
        
        Handles SSE streaming where content arrives in chunks with the same message ID.
        """
        if not parts:
            return None
        
        # Use the last part for metadata (has final usage)
        last_part = parts[-1]
        msg = last_part.get("message", {})
        
        message_id = msg.get("id", generate_id())
        model = msg.get("model")
        timestamp = parse_timestamp(last_part.get("timestamp", ""))
        
        # Merge content from all parts
        all_content = []
        for part in parts:
            part_content = get_nested(part, "message", "content") or []
            if isinstance(part_content, list):
                all_content.extend(part_content)
            elif isinstance(part_content, str):
                all_content.append({"type": "text", "text": part_content})
        
        # Deduplicate and merge text content
        content_blocks = self._merge_content(all_content)
        
        # Get usage from last part
        usage = TokenUsage.from_dict(msg.get("usage"))
        
        # Extract tool uses and track them
        for block in content_blocks:
            if block.type == ContentType.TOOL_USE and block.tool_use_id:
                tool_use = ToolUse(
                    tool_id=block.tool_use_id,
                    tool_name=block.tool_name or "unknown",
                    input_data=block.tool_input or {},
                    start_time=timestamp
                )
                self._pending_tool_uses[block.tool_use_id] = tool_use
        
        return Message(
            message_id=message_id,
            role=MessageRole.ASSISTANT,
            content=content_blocks,
            model=model,
            timestamp=timestamp,
            usage=usage,
            raw_data=last_part
        )
    
    def _merge_content(self, content_list: List[Dict]) -> List[ContentBlock]:
        """Merge and deduplicate content blocks."""
        # Simple merge: keep unique blocks
        seen_texts = set()
        seen_tool_ids = set()
        blocks = []
        
        for item in content_list:
            if not isinstance(item, dict):
                continue
            
            block_type = item.get("type", "text")
            
            if block_type == "text":
                text = item.get("text", "")
                if text and text not in seen_texts:
                    seen_texts.add(text)
                    blocks.append(ContentBlock.from_dict(item))
            elif block_type == "thinking":
                thinking = item.get("thinking", "")
                if thinking and thinking not in seen_texts:
                    seen_texts.add(thinking)
                    blocks.append(ContentBlock.from_dict(item))
            elif block_type == "tool_use":
                tool_id = item.get("id", "")
                if tool_id and tool_id not in seen_tool_ids:
                    seen_tool_ids.add(tool_id)
                    blocks.append(ContentBlock.from_dict(item))
            else:
                blocks.append(ContentBlock.from_dict(item))
        
        return blocks
    
    def _process_tool_result(self, turn: Turn, msg_data: Dict[str, Any]) -> None:
        """Process a tool result message and update pending tool uses."""
        content = self._get_content(msg_data)
        timestamp = parse_timestamp(msg_data.get("timestamp", ""))
        
        if not isinstance(content, list):
            return
        
        for item in content:
            if isinstance(item, dict) and item.get("type") == "tool_result":
                tool_use_id = item.get("tool_use_id")
                result = item.get("content", "")
                
                if tool_use_id and tool_use_id in self._pending_tool_uses:
                    tool_use = self._pending_tool_uses.pop(tool_use_id)
                    tool_use.output_data = str(result) if result else ""
                    tool_use.end_time = timestamp
                    tool_use.success = not item.get("is_error", False)
                    if item.get("is_error"):
                        tool_use.error = str(result)
                    turn.tool_uses.append(tool_use)
    
    def _finalize_assistant_messages(
        self, 
        turn: Turn, 
        parts_by_id: Dict[str, List[Dict]]
    ) -> None:
        """Finalize assistant messages from accumulated parts."""
        for msg_id, parts in parts_by_id.items():
            msg = self._parse_assistant_message(parts)
            if msg:
                turn.assistant_messages.append(msg)
    
    def _finalize_turn(self, turn: Turn) -> None:
        """Finalize a turn by setting timing and moving pending tool uses."""
        # Set turn timing
        if turn.user_message:
            turn.start_time = turn.user_message.timestamp
        
        if turn.assistant_messages:
            # Use last assistant message timestamp as end time
            turn.end_time = turn.assistant_messages[-1].timestamp
        
        # Move any remaining pending tool uses to this turn
        for tool_id, tool_use in list(self._pending_tool_uses.items()):
            turn.tool_uses.append(tool_use)
        self._pending_tool_uses.clear()

"""
SQLite storage layer for Claude Code local tracing.

Provides persistent storage for trace data in a local SQLite database.
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from claude_trace.models import (
    ContentBlock,
    Message,
    MessageRole,
    Session,
    SessionStats,
    TokenUsage,
    ToolStats,
    ToolUse,
    Turn,
)
from claude_trace.utils import parse_timestamp


class TraceStorage:
    """SQLite-based storage for trace data."""
    
    DEFAULT_DB_PATH = os.path.expanduser("~/.claude-trace/traces.db")
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the storage.
        
        Args:
            db_path: Path to SQLite database file. Uses default if not specified.
        """
        self.db_path = db_path or self.DEFAULT_DB_PATH
        self._ensure_directory()
        self._init_db()
    
    def _ensure_directory(self):
        """Ensure the database directory exists."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    total_duration_ms INTEGER,
                    metadata TEXT
                )
            """)
            
            # Turns table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS turns (
                    turn_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    turn_number INTEGER NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_ms INTEGER,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            
            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    turn_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT,
                    model TEXT,
                    timestamp TEXT NOT NULL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    cache_read_tokens INTEGER,
                    cache_creation_tokens INTEGER,
                    raw_data TEXT,
                    FOREIGN KEY (turn_id) REFERENCES turns(turn_id)
                )
            """)
            
            # Tool uses table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tool_uses (
                    tool_id TEXT PRIMARY KEY,
                    turn_id TEXT NOT NULL,
                    message_id TEXT,
                    tool_name TEXT NOT NULL,
                    input_data TEXT,
                    output_data TEXT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_ms INTEGER,
                    success INTEGER DEFAULT 1,
                    error TEXT,
                    FOREIGN KEY (turn_id) REFERENCES turns(turn_id),
                    FOREIGN KEY (message_id) REFERENCES messages(message_id)
                )
            """)
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_turns_session 
                ON turns(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_turn 
                ON messages(turn_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tool_uses_turn 
                ON tool_uses(turn_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_tool_uses_name 
                ON tool_uses(tool_name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_start_time 
                ON sessions(start_time)
            """)
            
            conn.commit()
        finally:
            conn.close()
    
    def save_session(self, session: Session) -> None:
        """
        Save or update a session in the database.
        
        Args:
            session: Session to save
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Insert or replace session
            cursor.execute("""
                INSERT OR REPLACE INTO sessions 
                (session_id, start_time, end_time, total_duration_ms, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session.session_id,
                session.start_time.isoformat() if session.start_time else "",
                session.end_time.isoformat() if session.end_time else None,
                session.duration_ms,
                json.dumps(session.metadata) if session.metadata else None
            ))
            
            # Save turns
            for turn in session.turns:
                self._save_turn(cursor, session.session_id, turn)
            
            conn.commit()
        finally:
            conn.close()
    
    def _save_turn(self, cursor: sqlite3.Cursor, session_id: str, turn: Turn) -> None:
        """Save a turn and its messages/tools."""
        # Insert or replace turn
        cursor.execute("""
            INSERT OR REPLACE INTO turns
            (turn_id, session_id, turn_number, start_time, end_time, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            turn.turn_id,
            session_id,
            turn.turn_number,
            turn.start_time.isoformat() if turn.start_time else "",
            turn.end_time.isoformat() if turn.end_time else None,
            turn.duration_ms
        ))
        
        # Save user message
        self._save_message(cursor, turn.turn_id, turn.user_message)
        
        # Save assistant messages
        for msg in turn.assistant_messages:
            self._save_message(cursor, turn.turn_id, msg)
        
        # Save tool uses
        for tool in turn.tool_uses:
            self._save_tool_use(cursor, turn.turn_id, tool)
    
    def _save_message(self, cursor: sqlite3.Cursor, turn_id: str, message: Message) -> None:
        """Save a message."""
        content_json = json.dumps([
            {
                "type": block.type.value,
                "text": block.text,
                "thinking": block.thinking,
                "tool_use_id": block.tool_use_id,
                "tool_name": block.tool_name,
                "tool_input": block.tool_input,
                "tool_result": block.tool_result
            }
            for block in message.content
        ])
        
        cursor.execute("""
            INSERT OR REPLACE INTO messages
            (message_id, turn_id, role, content, model, timestamp,
             input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message.message_id,
            turn_id,
            message.role.value,
            content_json,
            message.model,
            message.timestamp.isoformat(),
            message.usage.input_tokens if message.usage else 0,
            message.usage.output_tokens if message.usage else 0,
            message.usage.cache_read_tokens if message.usage else 0,
            message.usage.cache_creation_tokens if message.usage else 0,
            json.dumps(message.raw_data) if message.raw_data else None
        ))
    
    def _save_tool_use(
        self, 
        cursor: sqlite3.Cursor, 
        turn_id: str, 
        tool: ToolUse,
        message_id: Optional[str] = None
    ) -> None:
        """Save a tool use."""
        cursor.execute("""
            INSERT OR REPLACE INTO tool_uses
            (tool_id, turn_id, message_id, tool_name, input_data, output_data,
             start_time, end_time, duration_ms, success, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tool.tool_id,
            turn_id,
            message_id,
            tool.tool_name,
            json.dumps(tool.input_data) if tool.input_data else None,
            tool.output_data,
            tool.start_time.isoformat() if tool.start_time else "",
            tool.end_time.isoformat() if tool.end_time else None,
            tool.duration_ms,
            1 if tool.success else 0,
            tool.error
        ))
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """
        Load a session from the database.
        
        Args:
            session_id: Session ID to load
            
        Returns:
            Session object or None if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Get session
            cursor.execute(
                "SELECT * FROM sessions WHERE session_id = ?", 
                (session_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            session = Session(
                session_id=row["session_id"],
                start_time=parse_timestamp(row["start_time"]) if row["start_time"] else None,
                end_time=parse_timestamp(row["end_time"]) if row["end_time"] else None,
                metadata=json.loads(row["metadata"]) if row["metadata"] else {}
            )
            
            # Get turns
            session.turns = self._load_turns(cursor, session_id)
            
            return session
        finally:
            conn.close()
    
    def _load_turns(self, cursor: sqlite3.Cursor, session_id: str) -> List[Turn]:
        """Load turns for a session."""
        cursor.execute(
            "SELECT * FROM turns WHERE session_id = ? ORDER BY turn_number",
            (session_id,)
        )
        turns = []
        for row in cursor.fetchall():
            turn = Turn(
                turn_id=row["turn_id"],
                turn_number=row["turn_number"],
                user_message=None,  # Will be set below
                start_time=parse_timestamp(row["start_time"]) if row["start_time"] else None,
                end_time=parse_timestamp(row["end_time"]) if row["end_time"] else None
            )
            
            # Load messages
            messages = self._load_messages(cursor, turn.turn_id)
            for msg in messages:
                if msg.role == MessageRole.USER:
                    turn.user_message = msg
                else:
                    turn.assistant_messages.append(msg)
            
            # Load tool uses
            turn.tool_uses = self._load_tool_uses(cursor, turn.turn_id)
            
            turns.append(turn)
        
        return turns
    
    def _load_messages(self, cursor: sqlite3.Cursor, turn_id: str) -> List[Message]:
        """Load messages for a turn."""
        cursor.execute(
            "SELECT * FROM messages WHERE turn_id = ? ORDER BY timestamp",
            (turn_id,)
        )
        messages = []
        for row in cursor.fetchall():
            content_data = json.loads(row["content"]) if row["content"] else []
            content = [ContentBlock.from_dict(c) for c in content_data]
            
            usage = TokenUsage(
                input_tokens=row["input_tokens"] or 0,
                output_tokens=row["output_tokens"] or 0,
                cache_read_tokens=row["cache_read_tokens"] or 0,
                cache_creation_tokens=row["cache_creation_tokens"] or 0
            )
            
            messages.append(Message(
                message_id=row["message_id"],
                role=MessageRole(row["role"]),
                content=content,
                model=row["model"],
                timestamp=parse_timestamp(row["timestamp"]),
                usage=usage,
                raw_data=json.loads(row["raw_data"]) if row["raw_data"] else None
            ))
        
        return messages
    
    def _load_tool_uses(self, cursor: sqlite3.Cursor, turn_id: str) -> List[ToolUse]:
        """Load tool uses for a turn."""
        cursor.execute(
            "SELECT * FROM tool_uses WHERE turn_id = ? ORDER BY start_time",
            (turn_id,)
        )
        tools = []
        for row in cursor.fetchall():
            tools.append(ToolUse(
                tool_id=row["tool_id"],
                tool_name=row["tool_name"],
                input_data=json.loads(row["input_data"]) if row["input_data"] else {},
                output_data=row["output_data"],
                start_time=parse_timestamp(row["start_time"]) if row["start_time"] else None,
                end_time=parse_timestamp(row["end_time"]) if row["end_time"] else None,
                success=bool(row["success"]),
                error=row["error"]
            ))
        return tools
    
    def list_sessions(
        self, 
        limit: int = 20, 
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        List sessions with summary information.
        
        Args:
            limit: Maximum number of sessions to return
            since: Only return sessions started after this time
            
        Returns:
            List of session summaries
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            if since:
                cursor.execute("""
                    SELECT s.*, 
                           COUNT(DISTINCT t.turn_id) as turn_count,
                           COUNT(DISTINCT tu.tool_id) as tool_count
                    FROM sessions s
                    LEFT JOIN turns t ON s.session_id = t.session_id
                    LEFT JOIN tool_uses tu ON t.turn_id = tu.turn_id
                    WHERE s.start_time >= ?
                    GROUP BY s.session_id
                    ORDER BY s.start_time DESC
                    LIMIT ?
                """, (since.isoformat(), limit))
            else:
                cursor.execute("""
                    SELECT s.*, 
                           COUNT(DISTINCT t.turn_id) as turn_count,
                           COUNT(DISTINCT tu.tool_id) as tool_count
                    FROM sessions s
                    LEFT JOIN turns t ON s.session_id = t.session_id
                    LEFT JOIN tool_uses tu ON t.turn_id = tu.turn_id
                    GROUP BY s.session_id
                    ORDER BY s.start_time DESC
                    LIMIT ?
                """, (limit,))
            
            sessions = []
            for row in cursor.fetchall():
                sessions.append({
                    "session_id": row["session_id"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "duration_ms": row["total_duration_ms"],
                    "turn_count": row["turn_count"],
                    "tool_count": row["tool_count"]
                })
            
            return sessions
        finally:
            conn.close()
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all its data.
        
        Args:
            session_id: Session ID to delete
            
        Returns:
            True if session was deleted, False if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Check if session exists
            cursor.execute(
                "SELECT 1 FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            if not cursor.fetchone():
                return False
            
            # Delete tool uses
            cursor.execute("""
                DELETE FROM tool_uses 
                WHERE turn_id IN (SELECT turn_id FROM turns WHERE session_id = ?)
            """, (session_id,))
            
            # Delete messages
            cursor.execute("""
                DELETE FROM messages 
                WHERE turn_id IN (SELECT turn_id FROM turns WHERE session_id = ?)
            """, (session_id,))
            
            # Delete turns
            cursor.execute(
                "DELETE FROM turns WHERE session_id = ?",
                (session_id,)
            )
            
            # Delete session
            cursor.execute(
                "DELETE FROM sessions WHERE session_id = ?",
                (session_id,)
            )
            
            conn.commit()
            return True
        finally:
            conn.close()
    
    def get_tool_stats(
        self, 
        session_id: Optional[str] = None
    ) -> Dict[str, ToolStats]:
        """
        Get tool usage statistics.
        
        Args:
            session_id: Optional session ID to filter by
            
        Returns:
            Dictionary of tool name to ToolStats
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            if session_id:
                cursor.execute("""
                    SELECT tool_name, 
                           COUNT(*) as call_count,
                           SUM(duration_ms) as total_duration,
                           SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                           SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
                    FROM tool_uses tu
                    JOIN turns t ON tu.turn_id = t.turn_id
                    WHERE t.session_id = ?
                    GROUP BY tool_name
                """, (session_id,))
            else:
                cursor.execute("""
                    SELECT tool_name, 
                           COUNT(*) as call_count,
                           SUM(duration_ms) as total_duration,
                           SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                           SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count
                    FROM tool_uses
                    GROUP BY tool_name
                """)
            
            stats = {}
            for row in cursor.fetchall():
                stats[row["tool_name"]] = ToolStats(
                    tool_name=row["tool_name"],
                    call_count=row["call_count"],
                    total_duration_ms=row["total_duration"] or 0,
                    success_count=row["success_count"] or 0,
                    error_count=row["error_count"] or 0
                )
            
            return stats
        finally:
            conn.close()
    
    def get_aggregate_token_usage(
        self, 
        session_id: Optional[str] = None
    ) -> TokenUsage:
        """
        Get aggregate token usage.
        
        Args:
            session_id: Optional session ID to filter by
            
        Returns:
            TokenUsage with aggregate totals
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            if session_id:
                cursor.execute("""
                    SELECT 
                        SUM(input_tokens) as total_input,
                        SUM(output_tokens) as total_output,
                        SUM(cache_read_tokens) as total_cache_read,
                        SUM(cache_creation_tokens) as total_cache_creation
                    FROM messages m
                    JOIN turns t ON m.turn_id = t.turn_id
                    WHERE t.session_id = ?
                """, (session_id,))
            else:
                cursor.execute("""
                    SELECT 
                        SUM(input_tokens) as total_input,
                        SUM(output_tokens) as total_output,
                        SUM(cache_read_tokens) as total_cache_read,
                        SUM(cache_creation_tokens) as total_cache_creation
                    FROM messages
                """)
            
            row = cursor.fetchone()
            return TokenUsage(
                input_tokens=row["total_input"] or 0,
                output_tokens=row["total_output"] or 0,
                cache_read_tokens=row["total_cache_read"] or 0,
                cache_creation_tokens=row["total_cache_creation"] or 0
            )
        finally:
            conn.close()

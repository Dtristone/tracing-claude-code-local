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
            
            # OTEL metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS otel_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    metric_type TEXT DEFAULT 'counter',
                    unit TEXT,
                    description TEXT,
                    attributes TEXT,
                    timestamp TEXT,
                    collected_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            
            # OTEL session summary table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS otel_session_summary (
                    session_id TEXT PRIMARY KEY,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    cache_read_tokens INTEGER DEFAULT 0,
                    cache_creation_tokens INTEGER DEFAULT 0,
                    api_calls INTEGER DEFAULT 0,
                    api_latency_ms REAL DEFAULT 0,
                    tool_calls INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    raw_output TEXT,
                    collected_at TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            
            # Resource snapshots table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS resource_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    stage_id TEXT,
                    stage_name TEXT,
                    timestamp TEXT NOT NULL,
                    cpu_percent REAL DEFAULT 0,
                    cpu_user_percent REAL DEFAULT 0,
                    cpu_system_percent REAL DEFAULT 0,
                    memory_used_bytes INTEGER DEFAULT 0,
                    memory_available_bytes INTEGER DEFAULT 0,
                    memory_total_bytes INTEGER DEFAULT 0,
                    memory_percent REAL DEFAULT 0,
                    process_memory_rss INTEGER DEFAULT 0,
                    process_memory_vms INTEGER DEFAULT 0,
                    network_bytes_sent INTEGER DEFAULT 0,
                    network_bytes_recv INTEGER DEFAULT 0,
                    network_packets_sent INTEGER DEFAULT 0,
                    network_packets_recv INTEGER DEFAULT 0,
                    disk_read_bytes INTEGER DEFAULT 0,
                    disk_write_bytes INTEGER DEFAULT 0,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            
            # Stage resource usage table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stage_resource_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    stage_id TEXT NOT NULL,
                    stage_name TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_ms INTEGER,
                    avg_cpu_percent REAL DEFAULT 0,
                    max_cpu_percent REAL DEFAULT 0,
                    avg_memory_percent REAL DEFAULT 0,
                    max_memory_bytes INTEGER DEFAULT 0,
                    memory_delta_bytes INTEGER DEFAULT 0,
                    network_bytes_sent_delta INTEGER DEFAULT 0,
                    network_bytes_recv_delta INTEGER DEFAULT 0,
                    disk_read_bytes_delta INTEGER DEFAULT 0,
                    disk_write_bytes_delta INTEGER DEFAULT 0,
                    snapshot_count INTEGER DEFAULT 0,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    UNIQUE(session_id, stage_id)
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
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_otel_metrics_session 
                ON otel_metrics(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_otel_metrics_name 
                ON otel_metrics(metric_name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_resource_snapshots_session 
                ON resource_snapshots(session_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_resource_snapshots_stage 
                ON resource_snapshots(stage_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_stage_resource_usage_session 
                ON stage_resource_usage(session_id)
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
    
    def save_otel_metrics(self, session_id: str, metrics_data: Dict[str, Any]) -> None:
        """
        Save OTEL metrics for a session.
        
        Args:
            session_id: Session ID
            metrics_data: Dictionary with metrics data from OtelSessionMetrics.to_dict()
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Save summary
            summary = metrics_data.get('summary', {})
            collected_at = metrics_data.get('collected_at') or datetime.now().isoformat()
            
            cursor.execute("""
                INSERT OR REPLACE INTO otel_session_summary
                (session_id, input_tokens, output_tokens, cache_read_tokens,
                 cache_creation_tokens, api_calls, api_latency_ms, tool_calls,
                 errors, collected_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                summary.get('input_tokens', 0),
                summary.get('output_tokens', 0),
                summary.get('cache_read_tokens', 0),
                summary.get('cache_creation_tokens', 0),
                summary.get('api_calls', 0),
                summary.get('api_latency_ms', 0),
                summary.get('tool_calls', 0),
                summary.get('errors', 0),
                collected_at
            ))
            
            # Save individual metrics
            for name, metric in metrics_data.get('metrics', {}).items():
                for dp in metric.get('data_points', []):
                    cursor.execute("""
                        INSERT INTO otel_metrics
                        (session_id, metric_name, metric_value, metric_type,
                         unit, description, attributes, timestamp, collected_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        session_id,
                        name,
                        dp.get('value', 0),
                        metric.get('type', 'counter'),
                        metric.get('unit', ''),
                        metric.get('description', ''),
                        json.dumps(dp.get('attributes', {})),
                        dp.get('timestamp'),
                        collected_at
                    ))
            
            conn.commit()
        finally:
            conn.close()
    
    def get_otel_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get OTEL metrics summary for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Dictionary with OTEL summary or None if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM otel_session_summary WHERE session_id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return {
                "session_id": row["session_id"],
                "input_tokens": row["input_tokens"],
                "output_tokens": row["output_tokens"],
                "cache_read_tokens": row["cache_read_tokens"],
                "cache_creation_tokens": row["cache_creation_tokens"],
                "api_calls": row["api_calls"],
                "api_latency_ms": row["api_latency_ms"],
                "tool_calls": row["tool_calls"],
                "errors": row["errors"],
                "collected_at": row["collected_at"]
            }
        finally:
            conn.close()
    
    def get_otel_metrics(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all OTEL metrics for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of metric dictionaries
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute(
                """SELECT * FROM otel_metrics WHERE session_id = ? 
                   ORDER BY metric_name, timestamp""",
                (session_id,)
            )
            
            metrics = []
            for row in cursor.fetchall():
                metrics.append({
                    "metric_name": row["metric_name"],
                    "metric_value": row["metric_value"],
                    "metric_type": row["metric_type"],
                    "unit": row["unit"],
                    "description": row["description"],
                    "attributes": json.loads(row["attributes"]) if row["attributes"] else {},
                    "timestamp": row["timestamp"],
                    "collected_at": row["collected_at"]
                })
            
            return metrics
        finally:
            conn.close()
    
    def get_aggregate_otel_metrics(self) -> Dict[str, Any]:
        """
        Get aggregate OTEL metrics across all sessions.
        
        Returns:
            Dictionary with aggregate metrics
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    SUM(input_tokens) as total_input_tokens,
                    SUM(output_tokens) as total_output_tokens,
                    SUM(cache_read_tokens) as total_cache_read_tokens,
                    SUM(cache_creation_tokens) as total_cache_creation_tokens,
                    SUM(api_calls) as total_api_calls,
                    AVG(api_latency_ms) as avg_api_latency_ms,
                    SUM(tool_calls) as total_tool_calls,
                    SUM(errors) as total_errors,
                    COUNT(*) as session_count
                FROM otel_session_summary
            """)
            
            row = cursor.fetchone()
            
            return {
                "input_tokens": row["total_input_tokens"] or 0,
                "output_tokens": row["total_output_tokens"] or 0,
                "cache_read_tokens": row["total_cache_read_tokens"] or 0,
                "cache_creation_tokens": row["total_cache_creation_tokens"] or 0,
                "api_calls": row["total_api_calls"] or 0,
                "api_latency_ms": row["avg_api_latency_ms"] or 0,
                "tool_calls": row["total_tool_calls"] or 0,
                "errors": row["total_errors"] or 0,
                "session_count": row["session_count"] or 0
            }
        finally:
            conn.close()
    
    def has_otel_metrics(self, session_id: str) -> bool:
        """
        Check if a session has OTEL metrics.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if session has OTEL metrics
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM otel_session_summary WHERE session_id = ?",
                (session_id,)
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()
    
    # ============ Resource Monitoring Methods ============
    
    def save_resource_snapshot(self, snapshot) -> None:
        """
        Save a resource snapshot to the database.
        
        Args:
            snapshot: ResourceSnapshot object
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO resource_snapshots
                (session_id, stage_id, stage_name, timestamp,
                 cpu_percent, cpu_user_percent, cpu_system_percent,
                 memory_used_bytes, memory_available_bytes, memory_total_bytes,
                 memory_percent, process_memory_rss, process_memory_vms,
                 network_bytes_sent, network_bytes_recv,
                 network_packets_sent, network_packets_recv,
                 disk_read_bytes, disk_write_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot.session_id,
                snapshot.stage_id,
                snapshot.stage_name,
                snapshot.timestamp.isoformat(),
                snapshot.cpu_percent,
                snapshot.cpu_user_percent,
                snapshot.cpu_system_percent,
                snapshot.memory_used_bytes,
                snapshot.memory_available_bytes,
                snapshot.memory_total_bytes,
                snapshot.memory_percent,
                snapshot.process_memory_rss,
                snapshot.process_memory_vms,
                snapshot.network_bytes_sent,
                snapshot.network_bytes_recv,
                snapshot.network_packets_sent,
                snapshot.network_packets_recv,
                snapshot.disk_read_bytes,
                snapshot.disk_write_bytes
            ))
            
            conn.commit()
        finally:
            conn.close()
    
    def save_stage_resource_usage(self, stage) -> None:
        """
        Save stage resource usage summary to the database.
        
        Args:
            stage: StageResourceUsage object
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO stage_resource_usage
                (session_id, stage_id, stage_name, start_time, end_time,
                 duration_ms, avg_cpu_percent, max_cpu_percent,
                 avg_memory_percent, max_memory_bytes, memory_delta_bytes,
                 network_bytes_sent_delta, network_bytes_recv_delta,
                 disk_read_bytes_delta, disk_write_bytes_delta, snapshot_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stage.session_id,
                stage.stage_id,
                stage.stage_name,
                stage.start_time.isoformat(),
                stage.end_time.isoformat() if stage.end_time else None,
                stage.duration_ms,
                stage.avg_cpu_percent,
                stage.max_cpu_percent,
                stage.avg_memory_percent,
                stage.max_memory_bytes,
                stage.memory_delta_bytes,
                stage.network_bytes_sent_delta,
                stage.network_bytes_recv_delta,
                stage.disk_read_bytes_delta,
                stage.disk_write_bytes_delta,
                len(stage.snapshots)
            ))
            
            conn.commit()
        finally:
            conn.close()
    
    def get_resource_snapshots(
        self,
        session_id: str,
        stage_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get resource snapshots for a session.
        
        Args:
            session_id: Session ID
            stage_id: Optional stage ID to filter by
            
        Returns:
            List of snapshot dictionaries
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            if stage_id:
                cursor.execute("""
                    SELECT * FROM resource_snapshots
                    WHERE session_id = ? AND stage_id = ?
                    ORDER BY timestamp
                """, (session_id, stage_id))
            else:
                cursor.execute("""
                    SELECT * FROM resource_snapshots
                    WHERE session_id = ?
                    ORDER BY timestamp
                """, (session_id,))
            
            snapshots = []
            for row in cursor.fetchall():
                snapshots.append({
                    "timestamp": row["timestamp"],
                    "session_id": row["session_id"],
                    "stage_id": row["stage_id"],
                    "stage_name": row["stage_name"],
                    "cpu_percent": row["cpu_percent"],
                    "cpu_user_percent": row["cpu_user_percent"],
                    "cpu_system_percent": row["cpu_system_percent"],
                    "memory_used_bytes": row["memory_used_bytes"],
                    "memory_available_bytes": row["memory_available_bytes"],
                    "memory_total_bytes": row["memory_total_bytes"],
                    "memory_percent": row["memory_percent"],
                    "process_memory_rss": row["process_memory_rss"],
                    "process_memory_vms": row["process_memory_vms"],
                    "network_bytes_sent": row["network_bytes_sent"],
                    "network_bytes_recv": row["network_bytes_recv"],
                    "network_packets_sent": row["network_packets_sent"],
                    "network_packets_recv": row["network_packets_recv"],
                    "disk_read_bytes": row["disk_read_bytes"],
                    "disk_write_bytes": row["disk_write_bytes"],
                })
            
            return snapshots
        finally:
            conn.close()
    
    def get_stage_resource_usage(
        self,
        session_id: str,
        stage_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get stage resource usage data for a session.
        
        Args:
            session_id: Session ID
            stage_id: Optional stage ID to get specific stage
            
        Returns:
            List of stage resource usage dictionaries
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            if stage_id:
                cursor.execute("""
                    SELECT * FROM stage_resource_usage
                    WHERE session_id = ? AND stage_id = ?
                    ORDER BY start_time
                """, (session_id, stage_id))
            else:
                cursor.execute("""
                    SELECT * FROM stage_resource_usage
                    WHERE session_id = ?
                    ORDER BY start_time
                """, (session_id,))
            
            stages = []
            for row in cursor.fetchall():
                stages.append({
                    "session_id": row["session_id"],
                    "stage_id": row["stage_id"],
                    "stage_name": row["stage_name"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "duration_ms": row["duration_ms"],
                    "avg_cpu_percent": row["avg_cpu_percent"],
                    "max_cpu_percent": row["max_cpu_percent"],
                    "avg_memory_percent": row["avg_memory_percent"],
                    "max_memory_bytes": row["max_memory_bytes"],
                    "memory_delta_bytes": row["memory_delta_bytes"],
                    "network_bytes_sent_delta": row["network_bytes_sent_delta"],
                    "network_bytes_recv_delta": row["network_bytes_recv_delta"],
                    "disk_read_bytes_delta": row["disk_read_bytes_delta"],
                    "disk_write_bytes_delta": row["disk_write_bytes_delta"],
                    "snapshot_count": row["snapshot_count"],
                })
            
            return stages
        finally:
            conn.close()
    
    def get_session_resource_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of resource usage for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Dictionary with resource summary or None if no data
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # Get aggregate stats from snapshots
            cursor.execute("""
                SELECT 
                    COUNT(*) as snapshot_count,
                    MIN(timestamp) as start_time,
                    MAX(timestamp) as end_time,
                    AVG(cpu_percent) as avg_cpu_percent,
                    MAX(cpu_percent) as max_cpu_percent,
                    AVG(memory_percent) as avg_memory_percent,
                    MAX(memory_percent) as max_memory_percent,
                    MAX(memory_used_bytes) as max_memory_bytes
                FROM resource_snapshots
                WHERE session_id = ?
            """, (session_id,))
            
            row = cursor.fetchone()
            
            if not row or row["snapshot_count"] == 0:
                return None
            
            # Get first and last snapshots for delta calculations
            cursor.execute("""
                SELECT * FROM resource_snapshots
                WHERE session_id = ?
                ORDER BY timestamp ASC LIMIT 1
            """, (session_id,))
            first = cursor.fetchone()
            
            cursor.execute("""
                SELECT * FROM resource_snapshots
                WHERE session_id = ?
                ORDER BY timestamp DESC LIMIT 1
            """, (session_id,))
            last = cursor.fetchone()
            
            # Get stage count
            cursor.execute("""
                SELECT COUNT(*) as stage_count
                FROM stage_resource_usage
                WHERE session_id = ?
            """, (session_id,))
            stage_row = cursor.fetchone()
            
            return {
                "session_id": session_id,
                "snapshot_count": row["snapshot_count"],
                "stage_count": stage_row["stage_count"] if stage_row else 0,
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "cpu": {
                    "avg_percent": row["avg_cpu_percent"] or 0,
                    "max_percent": row["max_cpu_percent"] or 0,
                },
                "memory": {
                    "avg_percent": row["avg_memory_percent"] or 0,
                    "max_percent": row["max_memory_percent"] or 0,
                    "max_bytes": row["max_memory_bytes"] or 0,
                    "delta_bytes": (last["memory_used_bytes"] - first["memory_used_bytes"]) if first and last else 0,
                },
                "network": {
                    "bytes_sent": (last["network_bytes_sent"] - first["network_bytes_sent"]) if first and last else 0,
                    "bytes_recv": (last["network_bytes_recv"] - first["network_bytes_recv"]) if first and last else 0,
                },
                "disk": {
                    "read_bytes": (last["disk_read_bytes"] - first["disk_read_bytes"]) if first and last else 0,
                    "write_bytes": (last["disk_write_bytes"] - first["disk_write_bytes"]) if first and last else 0,
                },
            }
        finally:
            conn.close()
    
    def has_resource_data(self, session_id: str) -> bool:
        """
        Check if a session has resource monitoring data.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if session has resource data
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM resource_snapshots WHERE session_id = ? LIMIT 1",
                (session_id,)
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()
    
    def find_all_session_logs(self, session_id: str) -> Dict[str, Any]:
        """
        Find all logs and data associated with a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Dictionary with all available log sources and their data
        """
        result = {
            "session_id": session_id,
            "has_trace_data": False,
            "has_otel_data": False,
            "has_resource_data": False,
            "trace_summary": None,
            "otel_summary": None,
            "resource_summary": None,
            "stages": [],
        }
        
        # Check for trace data
        session = self.get_session(session_id)
        if session:
            result["has_trace_data"] = True
            result["trace_summary"] = {
                "start_time": session.start_time.isoformat() if session.start_time else None,
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "duration_ms": session.duration_ms,
                "turn_count": len(session.turns),
                "tool_count": sum(len(t.tool_uses) for t in session.turns),
            }
        
        # Check for OTEL data
        otel_summary = self.get_otel_summary(session_id)
        if otel_summary:
            result["has_otel_data"] = True
            result["otel_summary"] = otel_summary
        
        # Check for resource data
        resource_summary = self.get_session_resource_summary(session_id)
        if resource_summary:
            result["has_resource_data"] = True
            result["resource_summary"] = resource_summary
        
        # Get stage-level data
        stages = self.get_stage_resource_usage(session_id)
        result["stages"] = stages
        
        return result

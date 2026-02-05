"""
OpenTelemetry metrics collector for Claude Code local tracing.

Captures OTEL metrics from console output when OTEL_METRICS_EXPORTER=console
and integrates them with session-level analysis.

Supported metric types:
- Counter: Cumulative values (e.g., token counts, API calls)
- Histogram: Distribution of values (e.g., latency)
- Gauge: Point-in-time values (e.g., cache size)
"""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class OtelMetricDataPoint:
    """A single data point from an OTEL metric."""
    value: float
    timestamp: Optional[datetime] = None
    attributes: Dict[str, str] = field(default_factory=dict)


@dataclass
class OtelMetric:
    """An OTEL metric with its data points."""
    name: str
    description: str = ""
    unit: str = ""
    metric_type: str = "counter"  # counter, histogram, gauge
    data_points: List[OtelMetricDataPoint] = field(default_factory=list)
    
    @property
    def total_value(self) -> float:
        """Get total/sum of all data points."""
        return sum(dp.value for dp in self.data_points)
    
    @property
    def last_value(self) -> float:
        """Get the most recent data point value."""
        if self.data_points:
            return self.data_points[-1].value
        return 0.0
    
    @property
    def avg_value(self) -> float:
        """Get the average of all data points."""
        if not self.data_points:
            return 0.0
        return self.total_value / len(self.data_points)


@dataclass
class OtelSessionMetrics:
    """OTEL metrics for a single Claude Code session."""
    session_id: str
    metrics: Dict[str, OtelMetric] = field(default_factory=dict)
    collected_at: Optional[datetime] = None
    raw_output: str = ""
    
    # Commonly expected Claude Code metrics
    @property
    def input_tokens(self) -> int:
        """Get total input tokens from OTEL metrics."""
        for name in ["claude_code.tokens.input", "tokens.input", "input_tokens", 
                     "anthropic.claude.tokens.input", "llm.tokens.input"]:
            if name in self.metrics:
                return int(self.metrics[name].total_value)
        return 0
    
    @property
    def output_tokens(self) -> int:
        """Get total output tokens from OTEL metrics."""
        for name in ["claude_code.tokens.output", "tokens.output", "output_tokens",
                     "anthropic.claude.tokens.output", "llm.tokens.output"]:
            if name in self.metrics:
                return int(self.metrics[name].total_value)
        return 0
    
    @property
    def cache_read_tokens(self) -> int:
        """Get cache read tokens from OTEL metrics."""
        for name in ["claude_code.tokens.cache_read", "tokens.cache_read", 
                     "cache_read_input_tokens", "anthropic.claude.cache_read"]:
            if name in self.metrics:
                return int(self.metrics[name].total_value)
        return 0
    
    @property
    def cache_creation_tokens(self) -> int:
        """Get cache creation tokens from OTEL metrics."""
        for name in ["claude_code.tokens.cache_creation", "tokens.cache_creation",
                     "cache_creation_input_tokens", "anthropic.claude.cache_creation"]:
            if name in self.metrics:
                return int(self.metrics[name].total_value)
        return 0
    
    @property
    def api_calls(self) -> int:
        """Get total API calls from OTEL metrics."""
        for name in ["claude_code.api.calls", "api.calls", "llm.calls",
                     "anthropic.claude.requests"]:
            if name in self.metrics:
                return int(self.metrics[name].total_value)
        return 0
    
    @property
    def api_latency_ms(self) -> float:
        """Get average API latency in milliseconds."""
        for name in ["claude_code.api.latency", "api.latency", "llm.latency",
                     "anthropic.claude.latency"]:
            if name in self.metrics:
                return self.metrics[name].avg_value
        return 0.0
    
    @property
    def tool_calls(self) -> int:
        """Get total tool calls from OTEL metrics."""
        for name in ["claude_code.tools.calls", "tools.calls", "tool_calls"]:
            if name in self.metrics:
                return int(self.metrics[name].total_value)
        return 0
    
    @property
    def errors(self) -> int:
        """Get error count from OTEL metrics."""
        for name in ["claude_code.errors", "errors", "api.errors",
                     "anthropic.claude.errors"]:
            if name in self.metrics:
                return int(self.metrics[name].total_value)
        return 0
    
    def get_metric(self, name: str) -> Optional[OtelMetric]:
        """Get a metric by name."""
        return self.metrics.get(name)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "collected_at": self.collected_at.isoformat() if self.collected_at else None,
            "summary": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
                "cache_read_tokens": self.cache_read_tokens,
                "cache_creation_tokens": self.cache_creation_tokens,
                "api_calls": self.api_calls,
                "api_latency_ms": self.api_latency_ms,
                "tool_calls": self.tool_calls,
                "errors": self.errors
            },
            "metrics": {
                name: {
                    "description": m.description,
                    "unit": m.unit,
                    "type": m.metric_type,
                    "total_value": m.total_value,
                    "data_points": [
                        {
                            "value": dp.value,
                            "timestamp": dp.timestamp.isoformat() if dp.timestamp else None,
                            "attributes": dp.attributes
                        }
                        for dp in m.data_points
                    ]
                }
                for name, m in self.metrics.items()
            }
        }


class OtelMetricsParser:
    """
    Parser for OTEL console exporter output.
    
    Handles various OTEL console output formats:
    1. Standard OTEL console exporter format
    2. JSON-based output
    3. Prometheus-style text format
    """
    
    # Regex patterns for parsing OTEL console output
    # Pattern for metric lines like: claude_code.tokens.input{...} 12345
    METRIC_LINE_PATTERN = re.compile(
        r'^(?P<name>[a-zA-Z_][a-zA-Z0-9_\.]+)'
        r'(?:\{(?P<labels>[^}]*)\})?'
        r'\s+(?P<value>[0-9.eE+-]+)'
        r'(?:\s+(?P<timestamp>\d+))?$'
    )
    
    # Pattern for OTEL SDK console format
    OTEL_CONSOLE_PATTERN = re.compile(
        r'^\{\s*"?name"?\s*:\s*"?(?P<name>[^"]+)"?'
    )
    
    # Pattern for key-value pairs in labels
    LABEL_PATTERN = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"')
    
    def __init__(self):
        """Initialize the parser."""
        pass
    
    def parse_console_output(self, output: str) -> Dict[str, OtelMetric]:
        """
        Parse OTEL console exporter output.
        
        Args:
            output: Raw console output from OTEL exporter
            
        Returns:
            Dictionary of metric name to OtelMetric
        """
        metrics = {}
        
        # Try JSON format first
        json_metrics = self._parse_json_format(output)
        if json_metrics:
            return json_metrics
        
        # Try standard text format
        text_metrics = self._parse_text_format(output)
        if text_metrics:
            return text_metrics
        
        # Try line-by-line parsing
        for line in output.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            metric = self._parse_metric_line(line)
            if metric:
                name = metric.name
                if name in metrics:
                    # Merge data points
                    metrics[name].data_points.extend(metric.data_points)
                else:
                    metrics[name] = metric
        
        return metrics
    
    def _parse_json_format(self, output: str) -> Dict[str, OtelMetric]:
        """Parse JSON-formatted OTEL output."""
        metrics = {}
        
        # Try to find JSON objects in the output
        for line in output.strip().split('\n'):
            line = line.strip()
            if not line or not line.startswith('{'):
                continue
            
            try:
                data = json.loads(line)
                metric = self._parse_json_metric(data)
                if metric:
                    if metric.name in metrics:
                        metrics[metric.name].data_points.extend(metric.data_points)
                    else:
                        metrics[metric.name] = metric
            except json.JSONDecodeError:
                continue
        
        return metrics
    
    def _parse_json_metric(self, data: Dict[str, Any]) -> Optional[OtelMetric]:
        """Parse a single JSON metric object."""
        if not isinstance(data, dict):
            return None
        
        # Handle various JSON formats
        name = data.get('name') or data.get('metric_name') or data.get('Name')
        if not name:
            return None
        
        description = data.get('description', '')
        unit = data.get('unit', '')
        metric_type = data.get('type', data.get('metric_type', 'counter'))
        
        data_points = []
        
        # Check for data points in various locations
        points = (data.get('data_points') or 
                  data.get('dataPoints') or 
                  data.get('points') or 
                  [data])
        
        for point in points:
            if isinstance(point, dict):
                value = (point.get('value') or 
                        point.get('asDouble') or 
                        point.get('asInt') or
                        point.get('sum') or
                        point.get('count') or 0)
                timestamp = None
                if 'timestamp' in point or 'time_unix_nano' in point:
                    ts_val = point.get('timestamp') or point.get('time_unix_nano')
                    if isinstance(ts_val, (int, float)):
                        # OTEL timestamps can be in nanoseconds, milliseconds, or seconds
                        # Nanoseconds: > 1e18 (e.g., 1609459200000000000)
                        NANOSECOND_THRESHOLD = 1e18
                        # Milliseconds: > 1e12 (e.g., 1609459200000)
                        MILLISECOND_THRESHOLD = 1e12
                        
                        if ts_val > NANOSECOND_THRESHOLD:
                            ts_val = ts_val / 1e9  # Convert ns to seconds
                        elif ts_val > MILLISECOND_THRESHOLD:
                            ts_val = ts_val / 1e3  # Convert ms to seconds
                        
                        try:
                            timestamp = datetime.fromtimestamp(ts_val)
                        except (ValueError, OSError):
                            pass
                
                attributes = point.get('attributes', {})
                if isinstance(attributes, list):
                    attributes = {a.get('key', ''): a.get('value', {}).get('stringValue', '') 
                                for a in attributes if isinstance(a, dict)}
                
                data_points.append(OtelMetricDataPoint(
                    value=float(value) if value else 0.0,
                    timestamp=timestamp,
                    attributes=attributes
                ))
            elif isinstance(point, (int, float)):
                data_points.append(OtelMetricDataPoint(value=float(point)))
        
        if not data_points:
            return None
        
        return OtelMetric(
            name=name,
            description=description,
            unit=unit,
            metric_type=metric_type,
            data_points=data_points
        )
    
    def _parse_text_format(self, output: str) -> Dict[str, OtelMetric]:
        """Parse Prometheus-style text format."""
        metrics = {}
        current_metric = None
        current_help = ""
        current_type = "counter"
        
        for line in output.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('# HELP'):
                parts = line[7:].split(' ', 1)
                if len(parts) >= 2:
                    current_help = parts[1]
            elif line.startswith('# TYPE'):
                parts = line[7:].split(' ', 1)
                if len(parts) >= 2:
                    current_type = parts[1].strip()
            elif not line.startswith('#'):
                match = self.METRIC_LINE_PATTERN.match(line)
                if match:
                    name = match.group('name')
                    value = float(match.group('value'))
                    labels_str = match.group('labels') or ''
                    
                    # Parse labels
                    attributes = {}
                    for label_match in self.LABEL_PATTERN.finditer(labels_str):
                        attributes[label_match.group(1)] = label_match.group(2)
                    
                    # Parse timestamp if present
                    timestamp = None
                    ts_str = match.group('timestamp')
                    if ts_str:
                        try:
                            ts_val = int(ts_str)
                            if ts_val > 1e12:  # Milliseconds
                                ts_val = ts_val / 1000
                            timestamp = datetime.fromtimestamp(ts_val)
                        except (ValueError, OSError):
                            pass
                    
                    dp = OtelMetricDataPoint(
                        value=value,
                        timestamp=timestamp,
                        attributes=attributes
                    )
                    
                    if name in metrics:
                        metrics[name].data_points.append(dp)
                    else:
                        metrics[name] = OtelMetric(
                            name=name,
                            description=current_help,
                            metric_type=current_type,
                            data_points=[dp]
                        )
        
        return metrics
    
    def _parse_metric_line(self, line: str) -> Optional[OtelMetric]:
        """Parse a single metric line."""
        match = self.METRIC_LINE_PATTERN.match(line)
        if not match:
            return None
        
        name = match.group('name')
        value = float(match.group('value'))
        labels_str = match.group('labels') or ''
        
        # Parse labels
        attributes = {}
        for label_match in self.LABEL_PATTERN.finditer(labels_str):
            attributes[label_match.group(1)] = label_match.group(2)
        
        return OtelMetric(
            name=name,
            data_points=[OtelMetricDataPoint(value=value, attributes=attributes)]
        )


class OtelMetricsCollector:
    """
    Collector for OTEL metrics from Claude Code sessions.
    
    Handles reading OTEL metrics from:
    1. Console output files
    2. OTEL metrics log files
    3. Inline metrics in session directories
    """
    
    DEFAULT_METRICS_DIR = os.path.expanduser("~/.claude-trace/otel-metrics")
    
    def __init__(self, metrics_dir: Optional[str] = None):
        """
        Initialize the collector.
        
        Args:
            metrics_dir: Directory to store/read OTEL metrics files
        """
        self.metrics_dir = metrics_dir or self.DEFAULT_METRICS_DIR
        self.parser = OtelMetricsParser()
        
        # Ensure metrics directory exists
        os.makedirs(self.metrics_dir, exist_ok=True)
    
    def collect_from_output(
        self, 
        output: str, 
        session_id: str
    ) -> OtelSessionMetrics:
        """
        Collect metrics from raw OTEL console output.
        
        Args:
            output: Raw console output
            session_id: Session ID to associate metrics with
            
        Returns:
            OtelSessionMetrics object
        """
        metrics = self.parser.parse_console_output(output)
        
        return OtelSessionMetrics(
            session_id=session_id,
            metrics=metrics,
            collected_at=datetime.now(),
            raw_output=output
        )
    
    def collect_from_file(
        self, 
        file_path: str,
        session_id: Optional[str] = None
    ) -> OtelSessionMetrics:
        """
        Collect metrics from an OTEL output file.
        
        Args:
            file_path: Path to the OTEL output file
            session_id: Optional session ID (derived from filename if not provided)
            
        Returns:
            OtelSessionMetrics object
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"OTEL metrics file not found: {file_path}")
        
        if not session_id:
            session_id = path.stem.replace("_metrics", "").replace("otel_", "")
        
        with open(path, 'r') as f:
            output = f.read()
        
        return self.collect_from_output(output, session_id)
    
    def save_metrics(self, metrics: OtelSessionMetrics) -> str:
        """
        Save OTEL metrics to a file.
        
        Args:
            metrics: OtelSessionMetrics to save
            
        Returns:
            Path to saved file
        """
        file_path = os.path.join(self.metrics_dir, f"{metrics.session_id}_metrics.json")
        
        with open(file_path, 'w') as f:
            json.dump(metrics.to_dict(), f, indent=2)
        
        return file_path
    
    def save_raw_output(self, output: str, session_id: str) -> str:
        """
        Save raw OTEL console output for a session.
        
        Args:
            output: Raw console output
            session_id: Session ID
            
        Returns:
            Path to saved file
        """
        file_path = os.path.join(self.metrics_dir, f"{session_id}_raw.txt")
        
        with open(file_path, 'w') as f:
            f.write(output)
        
        return file_path
    
    def load_metrics(self, session_id: str) -> Optional[OtelSessionMetrics]:
        """
        Load OTEL metrics for a session.
        
        Args:
            session_id: Session ID to load metrics for
            
        Returns:
            OtelSessionMetrics or None if not found
        """
        file_path = os.path.join(self.metrics_dir, f"{session_id}_metrics.json")
        
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            return self._dict_to_metrics(data)
        except (json.JSONDecodeError, KeyError) as e:
            return None
    
    def _dict_to_metrics(self, data: Dict[str, Any]) -> OtelSessionMetrics:
        """Convert dictionary back to OtelSessionMetrics."""
        metrics = {}
        
        for name, metric_data in data.get('metrics', {}).items():
            data_points = []
            for dp_data in metric_data.get('data_points', []):
                timestamp = None
                if dp_data.get('timestamp'):
                    try:
                        timestamp = datetime.fromisoformat(dp_data['timestamp'])
                    except (ValueError, TypeError):
                        pass
                
                data_points.append(OtelMetricDataPoint(
                    value=dp_data.get('value', 0.0),
                    timestamp=timestamp,
                    attributes=dp_data.get('attributes', {})
                ))
            
            metrics[name] = OtelMetric(
                name=name,
                description=metric_data.get('description', ''),
                unit=metric_data.get('unit', ''),
                metric_type=metric_data.get('type', 'counter'),
                data_points=data_points
            )
        
        collected_at = None
        if data.get('collected_at'):
            try:
                collected_at = datetime.fromisoformat(data['collected_at'])
            except (ValueError, TypeError):
                pass
        
        return OtelSessionMetrics(
            session_id=data.get('session_id', ''),
            metrics=metrics,
            collected_at=collected_at
        )
    
    def list_sessions_with_metrics(self) -> List[str]:
        """
        List all sessions that have OTEL metrics.
        
        Returns:
            List of session IDs
        """
        sessions = []
        
        for file_name in os.listdir(self.metrics_dir):
            if file_name.endswith('_metrics.json'):
                session_id = file_name.replace('_metrics.json', '')
                sessions.append(session_id)
        
        return sorted(sessions)
    
    def get_session_metrics_file(self, session_id: str) -> Optional[str]:
        """
        Get the path to a session's OTEL metrics file.
        
        Args:
            session_id: Session ID
            
        Returns:
            Path to metrics file or None if not found
        """
        file_path = os.path.join(self.metrics_dir, f"{session_id}_metrics.json")
        
        if os.path.exists(file_path):
            return file_path
        return None


@dataclass
class OtelSessionMappingEntry:
    """Entry in the OTEL session mapping."""
    session_id: str
    otel_log_file: str
    timestamp: datetime
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "otel_log_file": self.otel_log_file,
            "timestamp": self.timestamp.isoformat(),
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OtelSessionMappingEntry":
        """Create from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except (ValueError, TypeError):
                timestamp = datetime.now()
        elif timestamp is None:
            timestamp = datetime.now()
        
        return cls(
            session_id=data.get("session_id", ""),
            otel_log_file=data.get("otel_log_file", ""),
            timestamp=timestamp,
            description=data.get("description", "")
        )


class OtelSessionMapping:
    """
    Manager for session ID to OTEL log file mappings.
    
    Provides:
    - Default naming convention for OTEL log files: {session_id}_{timestamp}_otel.txt
    - Persistent mapping storage in JSON format
    - Lookup of OTEL log files by session ID
    - Automatic timestamp tracking
    """
    
    DEFAULT_MAPPING_FILE = os.path.expanduser("~/.claude-trace/otel-session-mapping.json")
    DEFAULT_OTEL_DIR = os.path.expanduser("~/.claude-trace/otel-metrics")
    
    def __init__(
        self, 
        mapping_file: Optional[str] = None,
        otel_dir: Optional[str] = None
    ):
        """
        Initialize the session mapping manager.
        
        Args:
            mapping_file: Path to the mapping JSON file
            otel_dir: Directory for OTEL log files
        """
        self.mapping_file = mapping_file or self.DEFAULT_MAPPING_FILE
        self.otel_dir = otel_dir or self.DEFAULT_OTEL_DIR
        self._mappings: Dict[str, OtelSessionMappingEntry] = {}
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(self.mapping_file), exist_ok=True)
        os.makedirs(self.otel_dir, exist_ok=True)
        
        # Load existing mappings
        self._load_mappings()
    
    def _load_mappings(self) -> None:
        """Load mappings from the JSON file."""
        if not os.path.exists(self.mapping_file):
            return
        
        try:
            with open(self.mapping_file, 'r') as f:
                data = json.load(f)
            
            for entry_data in data.get("mappings", []):
                entry = OtelSessionMappingEntry.from_dict(entry_data)
                self._mappings[entry.session_id] = entry
        except (json.JSONDecodeError, IOError):
            # If file is corrupted, start fresh
            self._mappings = {}
    
    def _save_mappings(self) -> None:
        """Save mappings to the JSON file."""
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "mappings": [entry.to_dict() for entry in self._mappings.values()]
        }
        
        with open(self.mapping_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def generate_otel_filename(
        self, 
        session_id: str, 
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Generate a default OTEL log filename for a session.
        
        Format: {session_id}_{YYYYMMDD_HHMMSS}_otel.txt
        
        Args:
            session_id: Session ID
            timestamp: Optional timestamp (uses current time if not provided)
            
        Returns:
            Generated filename (not full path)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Format timestamp for filename
        ts_str = timestamp.strftime("%Y%m%d_%H%M%S")
        
        # Clean session_id to be filesystem-safe
        safe_session_id = session_id.replace("/", "_").replace("\\", "_")
        
        return f"{safe_session_id}_{ts_str}_otel.txt"
    
    def generate_otel_filepath(
        self, 
        session_id: str, 
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Generate a full OTEL log file path for a session.
        
        Args:
            session_id: Session ID
            timestamp: Optional timestamp (uses current time if not provided)
            
        Returns:
            Full path to the OTEL log file
        """
        filename = self.generate_otel_filename(session_id, timestamp)
        return os.path.join(self.otel_dir, filename)
    
    def register_session(
        self, 
        session_id: str, 
        otel_log_file: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        description: str = ""
    ) -> str:
        """
        Register a session with its OTEL log file mapping.
        
        If no otel_log_file is provided, generates one automatically.
        
        Args:
            session_id: Session ID
            otel_log_file: Path to the OTEL log file (generated if not provided)
            timestamp: Timestamp for the mapping (uses current time if not provided)
            description: Optional description for the mapping
            
        Returns:
            Path to the OTEL log file (generated or provided)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        if otel_log_file is None:
            otel_log_file = self.generate_otel_filepath(session_id, timestamp)
        
        entry = OtelSessionMappingEntry(
            session_id=session_id,
            otel_log_file=otel_log_file,
            timestamp=timestamp,
            description=description
        )
        
        self._mappings[session_id] = entry
        self._save_mappings()
        
        return otel_log_file
    
    def get_otel_file(self, session_id: str) -> Optional[str]:
        """
        Get the OTEL log file path for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Path to OTEL log file or None if not found
        """
        entry = self._mappings.get(session_id)
        if entry:
            return entry.otel_log_file
        return None
    
    def get_mapping(self, session_id: str) -> Optional[OtelSessionMappingEntry]:
        """
        Get the full mapping entry for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            OtelSessionMappingEntry or None if not found
        """
        return self._mappings.get(session_id)
    
    def list_mappings(self) -> List[OtelSessionMappingEntry]:
        """
        List all session mappings.
        
        Returns:
            List of OtelSessionMappingEntry objects, sorted by timestamp (newest first)
        """
        return sorted(
            self._mappings.values(),
            key=lambda e: e.timestamp,
            reverse=True
        )
    
    def remove_mapping(self, session_id: str) -> bool:
        """
        Remove a session mapping.
        
        Args:
            session_id: Session ID to remove
            
        Returns:
            True if mapping was removed, False if not found
        """
        if session_id in self._mappings:
            del self._mappings[session_id]
            self._save_mappings()
            return True
        return False
    
    def find_by_otel_file(self, otel_log_file: str) -> Optional[OtelSessionMappingEntry]:
        """
        Find a mapping by OTEL log file path.
        
        Args:
            otel_log_file: Path to the OTEL log file
            
        Returns:
            OtelSessionMappingEntry or None if not found
        """
        for entry in self._mappings.values():
            if entry.otel_log_file == otel_log_file:
                return entry
        return None
    
    def get_or_create_otel_file(
        self, 
        session_id: str, 
        description: str = ""
    ) -> str:
        """
        Get existing OTEL log file for a session or create a new one.
        
        Args:
            session_id: Session ID
            description: Optional description if creating new mapping
            
        Returns:
            Path to the OTEL log file
        """
        existing = self.get_otel_file(session_id)
        if existing:
            return existing
        
        return self.register_session(session_id, description=description)

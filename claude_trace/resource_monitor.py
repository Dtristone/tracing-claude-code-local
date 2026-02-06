"""
Resource monitoring for Claude Code local tracing.

Monitors local system resources (CPU, memory, network) and associates
them with session stages for time-aligned analysis.
"""

import os
import time
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable

# Try to import psutil for resource monitoring
# If not available, fall back to basic /proc reading on Linux
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


@dataclass
class ResourceSnapshot:
    """A single snapshot of resource usage at a point in time."""
    timestamp: datetime
    session_id: str
    stage_id: Optional[str] = None
    stage_name: Optional[str] = None
    
    # CPU metrics (percentages 0-100)
    cpu_percent: float = 0.0
    cpu_user_percent: float = 0.0
    cpu_system_percent: float = 0.0
    
    # Memory metrics (bytes)
    memory_used_bytes: int = 0
    memory_available_bytes: int = 0
    memory_total_bytes: int = 0
    memory_percent: float = 0.0
    
    # Process memory (bytes) - memory used by the current process
    process_memory_rss: int = 0
    process_memory_vms: int = 0
    
    # Network metrics (bytes since boot or last reset)
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0
    network_packets_sent: int = 0
    network_packets_recv: int = 0
    
    # I/O metrics (bytes)
    disk_read_bytes: int = 0
    disk_write_bytes: int = 0
    
    @classmethod
    def capture(
        cls,
        session_id: str,
        stage_id: Optional[str] = None,
        stage_name: Optional[str] = None
    ) -> "ResourceSnapshot":
        """
        Capture current resource usage.
        
        Args:
            session_id: Session ID to associate with
            stage_id: Optional stage/turn ID
            stage_name: Optional stage name (e.g., "tool_execution", "model_inference")
            
        Returns:
            ResourceSnapshot with current resource metrics
        """
        snapshot = cls(
            timestamp=datetime.now(),
            session_id=session_id,
            stage_id=stage_id,
            stage_name=stage_name
        )
        
        if HAS_PSUTIL:
            snapshot._capture_with_psutil()
        else:
            snapshot._capture_basic()
        
        return snapshot
    
    def _capture_with_psutil(self):
        """
        Capture metrics using psutil library.
        
        Note: This method has a 0.1 second blocking delay for CPU time measurement.
        For high-frequency monitoring, consider using non-blocking alternatives.
        """
        # CPU metrics (0.1s blocking delay for accurate CPU percentage)
        cpu_times = psutil.cpu_times_percent(interval=0.1)
        self.cpu_percent = psutil.cpu_percent(interval=None)
        self.cpu_user_percent = cpu_times.user
        self.cpu_system_percent = cpu_times.system
        
        # Memory metrics
        mem = psutil.virtual_memory()
        self.memory_used_bytes = mem.used
        self.memory_available_bytes = mem.available
        self.memory_total_bytes = mem.total
        self.memory_percent = mem.percent
        
        # Process memory
        try:
            process = psutil.Process()
            mem_info = process.memory_info()
            self.process_memory_rss = mem_info.rss
            self.process_memory_vms = mem_info.vms
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        
        # Network metrics
        try:
            net = psutil.net_io_counters()
            self.network_bytes_sent = net.bytes_sent
            self.network_bytes_recv = net.bytes_recv
            self.network_packets_sent = net.packets_sent
            self.network_packets_recv = net.packets_recv
        except Exception:
            pass
        
        # Disk I/O
        try:
            disk = psutil.disk_io_counters()
            if disk:
                self.disk_read_bytes = disk.read_bytes
                self.disk_write_bytes = disk.write_bytes
        except Exception:
            pass
    
    def _capture_basic(self):
        """Capture basic metrics without psutil (Linux only)."""
        # Try to read from /proc on Linux
        try:
            # CPU stats from /proc/stat
            with open('/proc/stat', 'r') as f:
                cpu_line = f.readline()
                parts = cpu_line.split()
                if len(parts) >= 5:
                    user = int(parts[1])
                    system = int(parts[3])
                    idle = int(parts[4])
                    total = user + system + idle
                    if total > 0:
                        self.cpu_percent = ((user + system) / total) * 100
                        self.cpu_user_percent = (user / total) * 100
                        self.cpu_system_percent = (system / total) * 100
        except (FileNotFoundError, PermissionError, IndexError):
            pass
        
        try:
            # Memory stats from /proc/meminfo
            with open('/proc/meminfo', 'r') as f:
                meminfo = {}
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(':')
                        value = int(parts[1]) * 1024  # Convert KB to bytes
                        meminfo[key] = value
                
                self.memory_total_bytes = meminfo.get('MemTotal', 0)
                self.memory_available_bytes = meminfo.get('MemAvailable', 
                    meminfo.get('MemFree', 0))
                self.memory_used_bytes = self.memory_total_bytes - self.memory_available_bytes
                if self.memory_total_bytes > 0:
                    self.memory_percent = (self.memory_used_bytes / self.memory_total_bytes) * 100
        except (FileNotFoundError, PermissionError, KeyError):
            pass
        
        try:
            # Network stats from /proc/net/dev
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()[2:]  # Skip headers
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 10 and not parts[0].startswith('lo'):
                        # Accumulate non-loopback interfaces
                        self.network_bytes_recv += int(parts[1])
                        self.network_bytes_sent += int(parts[9])
                        self.network_packets_recv += int(parts[2])
                        self.network_packets_sent += int(parts[10])
        except (FileNotFoundError, PermissionError, IndexError, ValueError):
            pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "stage_id": self.stage_id,
            "stage_name": self.stage_name,
            "cpu_percent": self.cpu_percent,
            "cpu_user_percent": self.cpu_user_percent,
            "cpu_system_percent": self.cpu_system_percent,
            "memory_used_bytes": self.memory_used_bytes,
            "memory_available_bytes": self.memory_available_bytes,
            "memory_total_bytes": self.memory_total_bytes,
            "memory_percent": self.memory_percent,
            "process_memory_rss": self.process_memory_rss,
            "process_memory_vms": self.process_memory_vms,
            "network_bytes_sent": self.network_bytes_sent,
            "network_bytes_recv": self.network_bytes_recv,
            "network_packets_sent": self.network_packets_sent,
            "network_packets_recv": self.network_packets_recv,
            "disk_read_bytes": self.disk_read_bytes,
            "disk_write_bytes": self.disk_write_bytes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResourceSnapshot":
        """Create from dictionary."""
        from claude_trace.utils import parse_timestamp
        return cls(
            timestamp=parse_timestamp(data.get("timestamp", "")),
            session_id=data.get("session_id", ""),
            stage_id=data.get("stage_id"),
            stage_name=data.get("stage_name"),
            cpu_percent=data.get("cpu_percent", 0.0),
            cpu_user_percent=data.get("cpu_user_percent", 0.0),
            cpu_system_percent=data.get("cpu_system_percent", 0.0),
            memory_used_bytes=data.get("memory_used_bytes", 0),
            memory_available_bytes=data.get("memory_available_bytes", 0),
            memory_total_bytes=data.get("memory_total_bytes", 0),
            memory_percent=data.get("memory_percent", 0.0),
            process_memory_rss=data.get("process_memory_rss", 0),
            process_memory_vms=data.get("process_memory_vms", 0),
            network_bytes_sent=data.get("network_bytes_sent", 0),
            network_bytes_recv=data.get("network_bytes_recv", 0),
            network_packets_sent=data.get("network_packets_sent", 0),
            network_packets_recv=data.get("network_packets_recv", 0),
            disk_read_bytes=data.get("disk_read_bytes", 0),
            disk_write_bytes=data.get("disk_write_bytes", 0),
        )


@dataclass
class StageResourceUsage:
    """Aggregated resource usage for a stage/operation."""
    session_id: str
    stage_id: str
    stage_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    
    # Aggregated CPU metrics
    avg_cpu_percent: float = 0.0
    max_cpu_percent: float = 0.0
    
    # Aggregated memory metrics
    avg_memory_percent: float = 0.0
    max_memory_bytes: int = 0
    memory_delta_bytes: int = 0  # Change from start to end
    
    # Network delta (during this stage)
    network_bytes_sent_delta: int = 0
    network_bytes_recv_delta: int = 0
    
    # Disk I/O delta
    disk_read_bytes_delta: int = 0
    disk_write_bytes_delta: int = 0
    
    # Raw snapshots
    snapshots: List[ResourceSnapshot] = field(default_factory=list)
    
    @property
    def duration_ms(self) -> Optional[int]:
        """Calculate duration in milliseconds."""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return int(delta.total_seconds() * 1000)
        return None
    
    def add_snapshot(self, snapshot: ResourceSnapshot):
        """Add a snapshot and update aggregated metrics."""
        self.snapshots.append(snapshot)
        self._recalculate_aggregates()
    
    def _recalculate_aggregates(self):
        """Recalculate aggregate metrics from snapshots."""
        if not self.snapshots:
            return
        
        # CPU averages and max
        cpu_values = [s.cpu_percent for s in self.snapshots]
        self.avg_cpu_percent = sum(cpu_values) / len(cpu_values)
        self.max_cpu_percent = max(cpu_values)
        
        # Memory averages and max
        mem_values = [s.memory_percent for s in self.snapshots]
        mem_bytes = [s.memory_used_bytes for s in self.snapshots]
        self.avg_memory_percent = sum(mem_values) / len(mem_values)
        self.max_memory_bytes = max(mem_bytes)
        
        # Deltas (first to last)
        if len(self.snapshots) >= 2:
            first = self.snapshots[0]
            last = self.snapshots[-1]
            
            self.memory_delta_bytes = last.memory_used_bytes - first.memory_used_bytes
            self.network_bytes_sent_delta = last.network_bytes_sent - first.network_bytes_sent
            self.network_bytes_recv_delta = last.network_bytes_recv - first.network_bytes_recv
            self.disk_read_bytes_delta = last.disk_read_bytes - first.disk_read_bytes
            self.disk_write_bytes_delta = last.disk_write_bytes - first.disk_write_bytes
    
    def finalize(self, end_time: Optional[datetime] = None):
        """Finalize the stage with an end time."""
        self.end_time = end_time or datetime.now()
        self._recalculate_aggregates()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization."""
        return {
            "session_id": self.session_id,
            "stage_id": self.stage_id,
            "stage_name": self.stage_name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "avg_cpu_percent": self.avg_cpu_percent,
            "max_cpu_percent": self.max_cpu_percent,
            "avg_memory_percent": self.avg_memory_percent,
            "max_memory_bytes": self.max_memory_bytes,
            "memory_delta_bytes": self.memory_delta_bytes,
            "network_bytes_sent_delta": self.network_bytes_sent_delta,
            "network_bytes_recv_delta": self.network_bytes_recv_delta,
            "disk_read_bytes_delta": self.disk_read_bytes_delta,
            "disk_write_bytes_delta": self.disk_write_bytes_delta,
            "snapshot_count": len(self.snapshots),
        }


class ResourceMonitor:
    """
    Monitors system resources during session execution.
    
    Can be used in two modes:
    1. Manual: Call capture_snapshot() at specific points
    2. Automatic: Use start_monitoring() for periodic capture
    """
    
    def __init__(self, session_id: str, storage=None, interval: float = 0.5):
        """
        Initialize the resource monitor.
        
        Args:
            session_id: Session ID to associate snapshots with
            storage: Optional TraceStorage for persistence
            interval: Capture interval in seconds for automatic monitoring
        """
        self.session_id = session_id
        self.storage = storage
        self.interval = interval
        
        self._snapshots: List[ResourceSnapshot] = []
        self._stages: Dict[str, StageResourceUsage] = {}
        self._current_stage: Optional[str] = None
        
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def capture_snapshot(
        self,
        stage_id: Optional[str] = None,
        stage_name: Optional[str] = None
    ) -> ResourceSnapshot:
        """
        Capture a single resource snapshot.
        
        Args:
            stage_id: Optional stage/turn ID
            stage_name: Optional stage name
            
        Returns:
            The captured ResourceSnapshot
        """
        # Use current stage if not specified
        if stage_id is None and self._current_stage:
            stage_id = self._current_stage
            if self._current_stage in self._stages:
                stage_name = self._stages[self._current_stage].stage_name
        
        snapshot = ResourceSnapshot.capture(
            session_id=self.session_id,
            stage_id=stage_id,
            stage_name=stage_name
        )
        
        self._snapshots.append(snapshot)
        
        # Add to stage if we're tracking one
        if stage_id and stage_id in self._stages:
            self._stages[stage_id].add_snapshot(snapshot)
        
        # Save to storage if available
        if self.storage:
            self.storage.save_resource_snapshot(snapshot)
        
        return snapshot
    
    def start_stage(
        self,
        stage_id: str,
        stage_name: str
    ) -> StageResourceUsage:
        """
        Start tracking a new stage.
        
        Args:
            stage_id: Unique stage identifier
            stage_name: Name of the stage (e.g., "model_inference", "tool_execution")
            
        Returns:
            StageResourceUsage for the new stage
        """
        stage = StageResourceUsage(
            session_id=self.session_id,
            stage_id=stage_id,
            stage_name=stage_name,
            start_time=datetime.now()
        )
        
        self._stages[stage_id] = stage
        self._current_stage = stage_id
        
        # Capture initial snapshot
        self.capture_snapshot(stage_id, stage_name)
        
        return stage
    
    def end_stage(self, stage_id: str) -> Optional[StageResourceUsage]:
        """
        End a stage and finalize its metrics.
        
        Args:
            stage_id: Stage ID to end
            
        Returns:
            Finalized StageResourceUsage or None if not found
        """
        if stage_id not in self._stages:
            return None
        
        # Capture final snapshot
        self.capture_snapshot(stage_id)
        
        stage = self._stages[stage_id]
        stage.finalize()
        
        if self._current_stage == stage_id:
            self._current_stage = None
        
        # Save stage summary to storage
        if self.storage:
            self.storage.save_stage_resource_usage(stage)
        
        return stage
    
    def start_monitoring(self, callback: Optional[Callable[[ResourceSnapshot], None]] = None):
        """
        Start automatic periodic resource monitoring.
        
        Args:
            callback: Optional callback for each snapshot
        """
        if self._monitoring:
            return
        
        self._monitoring = True
        self._stop_event.clear()
        
        def monitor_loop():
            while not self._stop_event.is_set():
                snapshot = self.capture_snapshot()
                if callback:
                    callback(snapshot)
                self._stop_event.wait(self.interval)
        
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop automatic resource monitoring."""
        if not self._monitoring:
            return
        
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        self._monitoring = False
    
    def get_snapshots(self) -> List[ResourceSnapshot]:
        """Get all captured snapshots."""
        return self._snapshots.copy()
    
    def get_stage(self, stage_id: str) -> Optional[StageResourceUsage]:
        """Get a specific stage's resource usage."""
        return self._stages.get(stage_id)
    
    def get_all_stages(self) -> Dict[str, StageResourceUsage]:
        """Get all stage resource usage data."""
        return self._stages.copy()
    
    def get_session_summary(self) -> Dict[str, Any]:
        """
        Get a summary of resource usage for the entire session.
        
        Returns:
            Dictionary with session resource summary
        """
        if not self._snapshots:
            return {
                "session_id": self.session_id,
                "snapshot_count": 0,
                "stage_count": len(self._stages),
            }
        
        cpu_values = [s.cpu_percent for s in self._snapshots]
        mem_values = [s.memory_percent for s in self._snapshots]
        
        first = self._snapshots[0]
        last = self._snapshots[-1]
        
        return {
            "session_id": self.session_id,
            "start_time": first.timestamp.isoformat(),
            "end_time": last.timestamp.isoformat(),
            "duration_ms": int((last.timestamp - first.timestamp).total_seconds() * 1000),
            "snapshot_count": len(self._snapshots),
            "stage_count": len(self._stages),
            "cpu": {
                "avg_percent": sum(cpu_values) / len(cpu_values),
                "max_percent": max(cpu_values),
                "min_percent": min(cpu_values),
            },
            "memory": {
                "avg_percent": sum(mem_values) / len(mem_values),
                "max_percent": max(mem_values),
                "min_percent": min(mem_values),
                "delta_bytes": last.memory_used_bytes - first.memory_used_bytes,
            },
            "network": {
                "bytes_sent": last.network_bytes_sent - first.network_bytes_sent,
                "bytes_recv": last.network_bytes_recv - first.network_bytes_recv,
            },
            "disk": {
                "read_bytes": last.disk_read_bytes - first.disk_read_bytes,
                "write_bytes": last.disk_write_bytes - first.disk_write_bytes,
            },
            "stages": {
                stage_id: stage.to_dict()
                for stage_id, stage in self._stages.items()
            }
        }


def get_resource_monitor_availability() -> Dict[str, bool]:
    """
    Check what resource monitoring capabilities are available.
    
    Returns:
        Dictionary of capability name to availability
    """
    capabilities = {
        "psutil_available": HAS_PSUTIL,
        "proc_available": os.path.exists("/proc"),
        "cpu_monitoring": False,
        "memory_monitoring": False,
        "network_monitoring": False,
        "disk_monitoring": False,
    }
    
    if HAS_PSUTIL:
        capabilities["cpu_monitoring"] = True
        capabilities["memory_monitoring"] = True
        capabilities["network_monitoring"] = True
        capabilities["disk_monitoring"] = True
    elif os.path.exists("/proc"):
        capabilities["cpu_monitoring"] = os.path.exists("/proc/stat")
        capabilities["memory_monitoring"] = os.path.exists("/proc/meminfo")
        capabilities["network_monitoring"] = os.path.exists("/proc/net/dev")
        capabilities["disk_monitoring"] = os.path.exists("/proc/diskstats")
    
    return capabilities


@dataclass
class ProcessResourceSnapshot:
    """A snapshot of resource usage for a specific process (Claude CLI)."""
    timestamp: datetime
    session_id: str
    
    # Process identification
    pid: int = 0
    process_name: str = ""
    cmdline: str = ""
    
    # Process CPU (percentage 0-100+)
    cpu_percent: float = 0.0
    
    # Process memory (bytes)
    memory_rss: int = 0  # Resident Set Size
    memory_vms: int = 0  # Virtual Memory Size
    memory_percent: float = 0.0
    
    # Process I/O (bytes)
    io_read_bytes: int = 0
    io_write_bytes: int = 0
    io_read_count: int = 0
    io_write_count: int = 0
    
    # Process threads
    num_threads: int = 0
    
    # System context (for alignment)
    system_cpu_percent: float = 0.0
    system_memory_percent: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "pid": self.pid,
            "process_name": self.process_name,
            "cmdline": self.cmdline,
            "cpu_percent": self.cpu_percent,
            "memory_rss": self.memory_rss,
            "memory_vms": self.memory_vms,
            "memory_percent": self.memory_percent,
            "io_read_bytes": self.io_read_bytes,
            "io_write_bytes": self.io_write_bytes,
            "io_read_count": self.io_read_count,
            "io_write_count": self.io_write_count,
            "num_threads": self.num_threads,
            "system_cpu_percent": self.system_cpu_percent,
            "system_memory_percent": self.system_memory_percent,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessResourceSnapshot":
        """Create from dictionary."""
        from claude_trace.utils import parse_timestamp
        return cls(
            timestamp=parse_timestamp(data.get("timestamp", "")),
            session_id=data.get("session_id", ""),
            pid=data.get("pid", 0),
            process_name=data.get("process_name", ""),
            cmdline=data.get("cmdline", ""),
            cpu_percent=data.get("cpu_percent", 0.0),
            memory_rss=data.get("memory_rss", 0),
            memory_vms=data.get("memory_vms", 0),
            memory_percent=data.get("memory_percent", 0.0),
            io_read_bytes=data.get("io_read_bytes", 0),
            io_write_bytes=data.get("io_write_bytes", 0),
            io_read_count=data.get("io_read_count", 0),
            io_write_count=data.get("io_write_count", 0),
            num_threads=data.get("num_threads", 0),
            system_cpu_percent=data.get("system_cpu_percent", 0.0),
            system_memory_percent=data.get("system_memory_percent", 0.0),
        )
    
    def to_log_line(self) -> str:
        """Convert to a single log line for file output."""
        import json
        return json.dumps(self.to_dict())


class ClaudeProcessMonitor:
    """
    Background monitor for Claude CLI process resource usage.
    
    Runs as a daemon thread and auto-saves resource logs to file,
    similar to how OTEL metrics are captured. Monitors only the Claude
    process (by finding it by name), not the whole system.
    
    Usage:
        monitor = ClaudeProcessMonitor("session-123")
        monitor.start()
        # ... Claude CLI runs ...
        monitor.stop()  # Saves to file automatically
    """
    
    DEFAULT_LOG_DIR = os.path.expanduser("~/.claude-trace/resource-logs")
    PROCESS_NAMES = ["claude", "node"]  # Claude CLI runs as node process
    
    def __init__(
        self, 
        session_id: str,
        log_dir: Optional[str] = None,
        interval: float = 1.0,
        auto_save: bool = True
    ):
        """
        Initialize the Claude process monitor.
        
        Args:
            session_id: Session ID to associate with resource logs
            log_dir: Directory to save resource log files (default: ~/.claude-trace/resource-logs)
            interval: Capture interval in seconds (default: 1.0)
            auto_save: Automatically save to file on stop (default: True)
        """
        self.session_id = session_id
        self.log_dir = log_dir or self.DEFAULT_LOG_DIR
        self.interval = interval
        self.auto_save = auto_save
        
        self._snapshots: List[ProcessResourceSnapshot] = []
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._log_file: Optional[str] = None
        self._file_handle = None
        self._claude_pid: Optional[int] = None
        
        # Ensure log directory exists
        os.makedirs(self.log_dir, exist_ok=True)
    
    def _find_claude_process(self) -> Optional[int]:
        """
        Find the Claude CLI process by name.
        
        Returns:
            PID of Claude process or None if not found
        """
        if HAS_PSUTIL:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    info = proc.info
                    name = info.get('name', '').lower()
                    cmdline = ' '.join(info.get('cmdline', []) or []).lower()
                    
                    # Check if it's a Claude process
                    if 'claude' in name or 'claude' in cmdline:
                        return info['pid']
                    
                    # Check for node process running Claude
                    if name == 'node' and 'claude' in cmdline:
                        return info['pid']
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        else:
            # Fallback to /proc on Linux
            if os.path.exists("/proc"):
                for pid_dir in os.listdir("/proc"):
                    if not pid_dir.isdigit():
                        continue
                    try:
                        cmdline_file = f"/proc/{pid_dir}/cmdline"
                        if os.path.exists(cmdline_file):
                            with open(cmdline_file, 'r') as f:
                                cmdline = f.read().replace('\0', ' ').lower()
                            if 'claude' in cmdline:
                                return int(pid_dir)
                    except (PermissionError, FileNotFoundError, ValueError):
                        continue
        
        return None
    
    def _capture_process_snapshot(self) -> Optional[ProcessResourceSnapshot]:
        """
        Capture resource usage for the Claude process.
        
        Returns:
            ProcessResourceSnapshot or None if process not found
        """
        # Find Claude process if we don't have a PID yet
        if self._claude_pid is None:
            self._claude_pid = self._find_claude_process()
        
        if self._claude_pid is None:
            return None
        
        snapshot = ProcessResourceSnapshot(
            timestamp=datetime.now(),
            session_id=self.session_id,
            pid=self._claude_pid
        )
        
        if HAS_PSUTIL:
            try:
                proc = psutil.Process(self._claude_pid)
                
                # Process info
                snapshot.process_name = proc.name()
                try:
                    # Limit cmdline length to avoid excessive storage/memory usage
                    cmdline = ' '.join(proc.cmdline())
                    snapshot.cmdline = cmdline[:200] if len(cmdline) > 200 else cmdline
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
                
                # CPU (non-blocking call)
                snapshot.cpu_percent = proc.cpu_percent(interval=None)
                
                # Memory
                mem_info = proc.memory_info()
                snapshot.memory_rss = mem_info.rss
                snapshot.memory_vms = mem_info.vms
                snapshot.memory_percent = proc.memory_percent()
                
                # I/O
                try:
                    io_counters = proc.io_counters()
                    snapshot.io_read_bytes = io_counters.read_bytes
                    snapshot.io_write_bytes = io_counters.write_bytes
                    snapshot.io_read_count = io_counters.read_count
                    snapshot.io_write_count = io_counters.write_count
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass
                
                # Threads
                snapshot.num_threads = proc.num_threads()
                
                # System context
                snapshot.system_cpu_percent = psutil.cpu_percent(interval=None)
                snapshot.system_memory_percent = psutil.virtual_memory().percent
                
            except psutil.NoSuchProcess:
                # Process ended, try to find it again
                self._claude_pid = None
                return None
            except psutil.AccessDenied:
                pass
        else:
            # Fallback to /proc reading on Linux
            try:
                proc_dir = f"/proc/{self._claude_pid}"
                if not os.path.exists(proc_dir):
                    self._claude_pid = None
                    return None
                
                # Process name
                with open(f"{proc_dir}/comm", 'r') as f:
                    snapshot.process_name = f.read().strip()
                
                # Memory from /proc/[pid]/status
                with open(f"{proc_dir}/status", 'r') as f:
                    for line in f:
                        if line.startswith('VmRSS:'):
                            snapshot.memory_rss = int(line.split()[1]) * 1024
                        elif line.startswith('VmSize:'):
                            snapshot.memory_vms = int(line.split()[1]) * 1024
                        elif line.startswith('Threads:'):
                            snapshot.num_threads = int(line.split()[1])
                
                # I/O from /proc/[pid]/io
                try:
                    with open(f"{proc_dir}/io", 'r') as f:
                        for line in f:
                            if line.startswith('read_bytes:'):
                                snapshot.io_read_bytes = int(line.split()[1])
                            elif line.startswith('write_bytes:'):
                                snapshot.io_write_bytes = int(line.split()[1])
                except PermissionError:
                    pass
                
            except (FileNotFoundError, PermissionError, ValueError):
                self._claude_pid = None
                return None
        
        return snapshot
    
    def _generate_log_filename(self) -> str:
        """Generate a log filename for the current session."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(
            self.log_dir, 
            f"{self.session_id}_{timestamp}_resource.jsonl"
        )
    
    def start(self) -> str:
        """
        Start background resource monitoring.
        
        Returns:
            Path to the log file being written
        """
        if self._monitoring:
            return self._log_file or ""
        
        self._log_file = self._generate_log_filename()
        self._monitoring = True
        self._stop_event.clear()
        self._snapshots = []
        
        # Open file for writing
        if self.auto_save:
            self._file_handle = open(self._log_file, 'w')
        
        def monitor_loop():
            while not self._stop_event.is_set():
                snapshot = self._capture_process_snapshot()
                if snapshot:
                    self._snapshots.append(snapshot)
                    
                    # Write to file immediately if auto_save
                    if self.auto_save and self._file_handle:
                        self._file_handle.write(snapshot.to_log_line() + "\n")
                        self._file_handle.flush()
                
                self._stop_event.wait(self.interval)
        
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        return self._log_file
    
    def stop(self) -> str:
        """
        Stop monitoring and finalize the log file.
        
        Returns:
            Path to the saved log file
        """
        if not self._monitoring:
            return self._log_file or ""
        
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        self._monitoring = False
        
        # Close file handle
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
        
        return self._log_file or ""
    
    def get_snapshots(self) -> List[ProcessResourceSnapshot]:
        """Get all captured snapshots."""
        return self._snapshots.copy()
    
    def get_log_file(self) -> Optional[str]:
        """Get the current log file path."""
        return self._log_file
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for captured data.
        
        Returns:
            Dictionary with summary statistics
        """
        if not self._snapshots:
            return {
                "session_id": self.session_id,
                "snapshot_count": 0,
                "log_file": self._log_file,
            }
        
        cpu_values = [s.cpu_percent for s in self._snapshots]
        mem_values = [s.memory_rss for s in self._snapshots]
        
        first = self._snapshots[0]
        last = self._snapshots[-1]
        
        return {
            "session_id": self.session_id,
            "log_file": self._log_file,
            "start_time": first.timestamp.isoformat(),
            "end_time": last.timestamp.isoformat(),
            "duration_seconds": (last.timestamp - first.timestamp).total_seconds(),
            "snapshot_count": len(self._snapshots),
            "pid": first.pid,
            "process_name": first.process_name,
            "cpu": {
                "avg_percent": sum(cpu_values) / len(cpu_values),
                "max_percent": max(cpu_values),
                "min_percent": min(cpu_values),
            },
            "memory": {
                "avg_bytes": sum(mem_values) / len(mem_values),
                "max_bytes": max(mem_values),
                "min_bytes": min(mem_values),
                "delta_bytes": last.memory_rss - first.memory_rss,
            },
            "io": {
                "read_bytes": last.io_read_bytes - first.io_read_bytes,
                "write_bytes": last.io_write_bytes - first.io_write_bytes,
            },
        }
    
    @classmethod
    def load_from_file(cls, file_path: str) -> List[ProcessResourceSnapshot]:
        """
        Load resource snapshots from a log file.
        
        Args:
            file_path: Path to the JSONL log file
            
        Returns:
            List of ProcessResourceSnapshot objects
        """
        import json
        snapshots = []
        
        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        snapshots.append(ProcessResourceSnapshot.from_dict(data))
                    except (json.JSONDecodeError, KeyError):
                        continue
        
        return snapshots
    
    @classmethod
    def list_log_files(cls, log_dir: Optional[str] = None, session_id: Optional[str] = None) -> List[str]:
        """
        List available resource log files.
        
        Args:
            log_dir: Directory to search (default: ~/.claude-trace/resource-logs)
            session_id: Optional filter by session ID
            
        Returns:
            List of log file paths
        """
        log_dir = log_dir or cls.DEFAULT_LOG_DIR
        
        if not os.path.exists(log_dir):
            return []
        
        files = []
        for filename in os.listdir(log_dir):
            if filename.endswith("_resource.jsonl"):
                if session_id is None or filename.startswith(session_id):
                    files.append(os.path.join(log_dir, filename))
        
        return sorted(files, reverse=True)  # Most recent first


def align_resource_with_trace(
    resource_snapshots: List[ProcessResourceSnapshot],
    trace_events: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Align resource snapshots with trace events by timestamp.
    
    Args:
        resource_snapshots: List of resource snapshots with timestamps
        trace_events: List of trace events with timestamps
        
    Returns:
        List of aligned events with resource data attached
    """
    if not resource_snapshots or not trace_events:
        return trace_events
    
    from claude_trace.utils import parse_timestamp
    
    aligned = []
    
    for event in trace_events:
        event_time = event.get("timestamp")
        if isinstance(event_time, str):
            event_time = parse_timestamp(event_time)
        
        # Find closest resource snapshot
        closest_snapshot = None
        min_diff = float('inf')
        
        for snapshot in resource_snapshots:
            diff = abs((snapshot.timestamp - event_time).total_seconds())
            if diff < min_diff:
                min_diff = diff
                closest_snapshot = snapshot
        
        # Attach resource data if within 5 seconds
        event_with_resources = event.copy()
        if closest_snapshot and min_diff <= 5.0:
            event_with_resources["resource"] = {
                "cpu_percent": closest_snapshot.cpu_percent,
                "memory_rss": closest_snapshot.memory_rss,
                "memory_percent": closest_snapshot.memory_percent,
                "io_read_bytes": closest_snapshot.io_read_bytes,
                "io_write_bytes": closest_snapshot.io_write_bytes,
                "time_offset_seconds": min_diff,
            }
        
        aligned.append(event_with_resources)
    
    return aligned

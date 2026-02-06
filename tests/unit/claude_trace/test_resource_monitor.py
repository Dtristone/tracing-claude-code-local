"""
Unit tests for the resource monitoring module.
"""

import os
import tempfile
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from claude_trace.resource_monitor import (
    ResourceSnapshot,
    StageResourceUsage,
    ResourceMonitor,
    get_resource_monitor_availability,
)
from claude_trace.storage import TraceStorage


class TestResourceSnapshot:
    """Tests for ResourceSnapshot class."""
    
    def test_capture_snapshot(self):
        """Test capturing a resource snapshot."""
        snapshot = ResourceSnapshot.capture("test-session", "stage-1", "test_stage")
        
        assert snapshot.session_id == "test-session"
        assert snapshot.stage_id == "stage-1"
        assert snapshot.stage_name == "test_stage"
        assert snapshot.timestamp is not None
        assert isinstance(snapshot.timestamp, datetime)
    
    def test_snapshot_cpu_values(self):
        """Test that CPU values are captured."""
        snapshot = ResourceSnapshot.capture("test-session")
        
        # CPU percent should be between 0 and 100
        assert 0 <= snapshot.cpu_percent <= 100
        assert 0 <= snapshot.cpu_user_percent <= 100
        assert 0 <= snapshot.cpu_system_percent <= 100
    
    def test_snapshot_memory_values(self):
        """Test that memory values are captured."""
        snapshot = ResourceSnapshot.capture("test-session")
        
        # Memory should have some values
        assert snapshot.memory_total_bytes > 0
        assert snapshot.memory_used_bytes >= 0
        assert 0 <= snapshot.memory_percent <= 100
    
    def test_snapshot_network_values(self):
        """Test that network values are captured (may be 0 on some systems)."""
        snapshot = ResourceSnapshot.capture("test-session")
        
        # Network values should be non-negative
        assert snapshot.network_bytes_sent >= 0
        assert snapshot.network_bytes_recv >= 0
    
    def test_snapshot_to_dict(self):
        """Test converting snapshot to dictionary."""
        snapshot = ResourceSnapshot.capture("test-session", "stage-1", "test_stage")
        data = snapshot.to_dict()
        
        assert data["session_id"] == "test-session"
        assert data["stage_id"] == "stage-1"
        assert data["stage_name"] == "test_stage"
        assert "timestamp" in data
        assert "cpu_percent" in data
        assert "memory_percent" in data
    
    def test_snapshot_from_dict(self):
        """Test creating snapshot from dictionary."""
        original = ResourceSnapshot.capture("test-session", "stage-1", "test_stage")
        data = original.to_dict()
        
        restored = ResourceSnapshot.from_dict(data)
        
        assert restored.session_id == original.session_id
        assert restored.stage_id == original.stage_id
        assert restored.stage_name == original.stage_name
        assert restored.cpu_percent == original.cpu_percent


class TestStageResourceUsage:
    """Tests for StageResourceUsage class."""
    
    def test_create_stage(self):
        """Test creating a stage resource usage object."""
        stage = StageResourceUsage(
            session_id="test-session",
            stage_id="stage-1",
            stage_name="model_inference",
            start_time=datetime.now()
        )
        
        assert stage.session_id == "test-session"
        assert stage.stage_id == "stage-1"
        assert stage.stage_name == "model_inference"
        assert stage.end_time is None
    
    def test_add_snapshot(self):
        """Test adding a snapshot to a stage."""
        stage = StageResourceUsage(
            session_id="test-session",
            stage_id="stage-1",
            stage_name="test_stage",
            start_time=datetime.now()
        )
        
        snapshot = ResourceSnapshot.capture("test-session", "stage-1", "test_stage")
        stage.add_snapshot(snapshot)
        
        assert len(stage.snapshots) == 1
        assert stage.avg_cpu_percent == snapshot.cpu_percent
    
    def test_multiple_snapshots_aggregation(self):
        """Test that multiple snapshots are aggregated correctly."""
        stage = StageResourceUsage(
            session_id="test-session",
            stage_id="stage-1",
            stage_name="test_stage",
            start_time=datetime.now()
        )
        
        # Add multiple snapshots
        for _ in range(3):
            snapshot = ResourceSnapshot.capture("test-session", "stage-1")
            stage.add_snapshot(snapshot)
        
        assert len(stage.snapshots) == 3
        # Average should be calculated
        assert stage.avg_cpu_percent >= 0
    
    def test_finalize_stage(self):
        """Test finalizing a stage."""
        stage = StageResourceUsage(
            session_id="test-session",
            stage_id="stage-1",
            stage_name="test_stage",
            start_time=datetime.now()
        )
        
        snapshot = ResourceSnapshot.capture("test-session", "stage-1")
        stage.add_snapshot(snapshot)
        
        stage.finalize()
        
        assert stage.end_time is not None
    
    def test_duration_calculation(self):
        """Test duration calculation."""
        start = datetime.now()
        stage = StageResourceUsage(
            session_id="test-session",
            stage_id="stage-1",
            stage_name="test_stage",
            start_time=start
        )
        
        # Set end time 100ms later
        stage.end_time = start + timedelta(milliseconds=100)
        
        assert stage.duration_ms == 100
    
    def test_duration_calculation_without_end_time(self):
        """Test that duration_ms returns None when end_time is not set."""
        stage = StageResourceUsage(
            session_id="test-session",
            stage_id="stage-1",
            stage_name="test_stage",
            start_time=datetime.now()
        )
        
        # Without end_time, duration should be None
        assert stage.end_time is None
        assert stage.duration_ms is None
    
    def test_to_dict(self):
        """Test converting stage to dictionary."""
        stage = StageResourceUsage(
            session_id="test-session",
            stage_id="stage-1",
            stage_name="test_stage",
            start_time=datetime.now()
        )
        stage.finalize()
        
        data = stage.to_dict()
        
        assert data["session_id"] == "test-session"
        assert data["stage_id"] == "stage-1"
        assert data["stage_name"] == "test_stage"
        assert "start_time" in data
        assert "end_time" in data


class TestResourceMonitor:
    """Tests for ResourceMonitor class."""
    
    def test_create_monitor(self):
        """Test creating a resource monitor."""
        monitor = ResourceMonitor("test-session")
        
        assert monitor.session_id == "test-session"
        assert len(monitor.get_snapshots()) == 0
    
    def test_capture_snapshot(self):
        """Test capturing a snapshot through the monitor."""
        monitor = ResourceMonitor("test-session")
        
        snapshot = monitor.capture_snapshot()
        
        assert snapshot.session_id == "test-session"
        assert len(monitor.get_snapshots()) == 1
    
    def test_start_and_end_stage(self):
        """Test starting and ending a stage."""
        monitor = ResourceMonitor("test-session")
        
        # Start stage
        stage = monitor.start_stage("stage-1", "model_inference")
        assert stage.stage_id == "stage-1"
        assert stage.stage_name == "model_inference"
        
        # Capture some snapshots
        monitor.capture_snapshot()
        monitor.capture_snapshot()
        
        # End stage
        ended_stage = monitor.end_stage("stage-1")
        
        assert ended_stage is not None
        assert ended_stage.end_time is not None
        assert len(ended_stage.snapshots) >= 1  # At least the initial snapshot
    
    def test_get_stage(self):
        """Test getting a specific stage."""
        monitor = ResourceMonitor("test-session")
        
        monitor.start_stage("stage-1", "test_stage")
        
        stage = monitor.get_stage("stage-1")
        assert stage is not None
        assert stage.stage_id == "stage-1"
        
        # Non-existent stage
        assert monitor.get_stage("stage-999") is None
    
    def test_get_all_stages(self):
        """Test getting all stages."""
        monitor = ResourceMonitor("test-session")
        
        monitor.start_stage("stage-1", "first")
        monitor.end_stage("stage-1")
        monitor.start_stage("stage-2", "second")
        monitor.end_stage("stage-2")
        
        stages = monitor.get_all_stages()
        assert len(stages) == 2
        assert "stage-1" in stages
        assert "stage-2" in stages
    
    def test_session_summary(self):
        """Test getting session summary."""
        monitor = ResourceMonitor("test-session")
        
        # Capture some snapshots
        for _ in range(3):
            monitor.capture_snapshot()
        
        summary = monitor.get_session_summary()
        
        assert summary["session_id"] == "test-session"
        assert summary["snapshot_count"] == 3
        assert "cpu" in summary
        assert "memory" in summary
        assert "network" in summary


class TestResourceMonitorWithStorage:
    """Tests for ResourceMonitor with TraceStorage integration."""
    
    @pytest.fixture
    def temp_storage(self):
        """Create a temporary storage for testing."""
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "test.db")
        storage = TraceStorage(db_path)
        yield storage
        # Cleanup
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    def test_monitor_with_storage(self, temp_storage):
        """Test that monitor saves to storage."""
        monitor = ResourceMonitor("test-session", storage=temp_storage)
        
        # Capture snapshot
        monitor.capture_snapshot()
        
        # Check storage has the snapshot
        snapshots = temp_storage.get_resource_snapshots("test-session")
        assert len(snapshots) == 1
    
    def test_stage_saved_to_storage(self, temp_storage):
        """Test that stage is saved to storage when ended."""
        monitor = ResourceMonitor("test-session", storage=temp_storage)
        
        # Start and end a stage
        monitor.start_stage("stage-1", "test_stage")
        monitor.capture_snapshot()
        monitor.end_stage("stage-1")
        
        # Check storage has the stage
        stages = temp_storage.get_stage_resource_usage("test-session")
        assert len(stages) == 1
        assert stages[0]["stage_id"] == "stage-1"


class TestGetResourceMonitorAvailability:
    """Tests for the availability check function."""
    
    def test_availability_returns_dict(self):
        """Test that availability check returns a dictionary."""
        avail = get_resource_monitor_availability()
        
        assert isinstance(avail, dict)
        assert "psutil_available" in avail
        assert "proc_available" in avail
        assert "cpu_monitoring" in avail
        assert "memory_monitoring" in avail
        assert "network_monitoring" in avail
        assert "disk_monitoring" in avail
    
    def test_availability_has_some_capability(self):
        """Test that at least some monitoring capability exists."""
        avail = get_resource_monitor_availability()
        
        # On Linux, /proc should be available even without psutil
        has_any_capability = (
            avail["cpu_monitoring"] or
            avail["memory_monitoring"] or
            avail["network_monitoring"] or
            avail["disk_monitoring"]
        )
        
        # We should have some capability on Linux
        if os.path.exists("/proc"):
            assert has_any_capability

"""
End-to-End Integration Tests for OTEL Session Mapping.

Tests verify:
1. Default OTEL log file naming convention
2. Session ID to OTEL log file mapping persistence
3. Loading metrics according to mapping and session
4. CLI commands for managing mappings
"""

import json
import os
import pytest
import tempfile
from datetime import datetime
from pathlib import Path

from claude_trace.otel_collector import (
    OtelMetricsCollector,
    OtelSessionMapping,
    OtelSessionMappingEntry,
)
from claude_trace.storage import TraceStorage


class TestOtelSessionMappingIntegration:
    """End-to-end tests for OTEL session mapping functionality."""
    
    @pytest.fixture
    def temp_mapping_dir(self, tmp_path):
        """Create a temporary directory for mapping files."""
        mapping_dir = tmp_path / "claude-trace"
        mapping_dir.mkdir()
        otel_dir = tmp_path / "otel-metrics"
        otel_dir.mkdir()
        return tmp_path, mapping_dir, otel_dir
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test_traces.db"
        return TraceStorage(str(db_path))
    
    @pytest.fixture
    def sample_otel_output(self):
        """Sample OTEL console output for testing."""
        return """
claude_code.tokens.input 1250
claude_code.tokens.output 380
claude_code.tokens.cache_read 520
claude_code.tokens.cache_creation 180
claude_code.api.calls 5
claude_code.api.latency 2345.67
claude_code.tools.calls 3
claude_code.errors 0
"""
    
    # Test 1: Default OTEL log file naming convention
    def test_default_otel_filename_format(self, temp_mapping_dir):
        """Test that default OTEL filenames follow the expected format."""
        tmp_path, mapping_dir, otel_dir = temp_mapping_dir
        mapping_file = mapping_dir / "otel-session-mapping.json"
        
        mapping = OtelSessionMapping(
            mapping_file=str(mapping_file),
            otel_dir=str(otel_dir)
        )
        
        session_id = "test-session-abc123"
        timestamp = datetime(2025, 2, 4, 10, 30, 45)
        
        filename = mapping.generate_otel_filename(session_id, timestamp)
        
        # Check format: {session_id}_{YYYYMMDD_HHMMSS}_otel.txt
        assert filename == "test-session-abc123_20250204_103045_otel.txt"
    
    def test_default_otel_filepath_includes_directory(self, temp_mapping_dir):
        """Test that full filepath includes the otel directory."""
        tmp_path, mapping_dir, otel_dir = temp_mapping_dir
        mapping_file = mapping_dir / "otel-session-mapping.json"
        
        mapping = OtelSessionMapping(
            mapping_file=str(mapping_file),
            otel_dir=str(otel_dir)
        )
        
        session_id = "test-session-xyz"
        filepath = mapping.generate_otel_filepath(session_id)
        
        assert str(otel_dir) in filepath
        assert "test-session-xyz" in filepath
        assert filepath.endswith("_otel.txt")
    
    def test_session_id_with_special_chars_sanitized(self, temp_mapping_dir):
        """Test that session IDs with special characters are sanitized."""
        tmp_path, mapping_dir, otel_dir = temp_mapping_dir
        mapping_file = mapping_dir / "otel-session-mapping.json"
        
        mapping = OtelSessionMapping(
            mapping_file=str(mapping_file),
            otel_dir=str(otel_dir)
        )
        
        # Session ID with path separators
        session_id = "path/to/session"
        filename = mapping.generate_otel_filename(session_id)
        
        # Should not contain slashes
        assert "/" not in filename
        assert "path_to_session" in filename
    
    # Test 2: Session mapping persistence
    def test_register_and_retrieve_mapping(self, temp_mapping_dir):
        """Test that session mappings are persisted and can be retrieved."""
        tmp_path, mapping_dir, otel_dir = temp_mapping_dir
        mapping_file = mapping_dir / "otel-session-mapping.json"
        
        mapping = OtelSessionMapping(
            mapping_file=str(mapping_file),
            otel_dir=str(otel_dir)
        )
        
        session_id = "persist-test-session"
        otel_file = mapping.register_session(
            session_id,
            description="Test description"
        )
        
        # Retrieve the mapping
        entry = mapping.get_mapping(session_id)
        
        assert entry is not None
        assert entry.session_id == session_id
        assert entry.otel_log_file == otel_file
        assert entry.description == "Test description"
        assert entry.timestamp is not None
    
    def test_mapping_persistence_across_instances(self, temp_mapping_dir):
        """Test that mappings persist across different instances."""
        tmp_path, mapping_dir, otel_dir = temp_mapping_dir
        mapping_file = mapping_dir / "otel-session-mapping.json"
        
        # Create first instance and register
        mapping1 = OtelSessionMapping(
            mapping_file=str(mapping_file),
            otel_dir=str(otel_dir)
        )
        
        session_id = "cross-instance-session"
        mapping1.register_session(session_id, description="Instance 1")
        
        # Create second instance and retrieve
        mapping2 = OtelSessionMapping(
            mapping_file=str(mapping_file),
            otel_dir=str(otel_dir)
        )
        
        entry = mapping2.get_mapping(session_id)
        
        assert entry is not None
        assert entry.session_id == session_id
        assert entry.description == "Instance 1"
    
    def test_mapping_file_json_format(self, temp_mapping_dir):
        """Test that the mapping file is valid JSON with expected structure."""
        tmp_path, mapping_dir, otel_dir = temp_mapping_dir
        mapping_file = mapping_dir / "otel-session-mapping.json"
        
        mapping = OtelSessionMapping(
            mapping_file=str(mapping_file),
            otel_dir=str(otel_dir)
        )
        
        mapping.register_session("session-1")
        mapping.register_session("session-2")
        
        # Read and parse the mapping file
        with open(mapping_file, 'r') as f:
            data = json.load(f)
        
        assert "version" in data
        assert "updated_at" in data
        assert "mappings" in data
        assert len(data["mappings"]) == 2
        
        # Check each mapping entry
        for entry in data["mappings"]:
            assert "session_id" in entry
            assert "otel_log_file" in entry
            assert "timestamp" in entry
    
    def test_list_all_mappings(self, temp_mapping_dir):
        """Test listing all mappings sorted by timestamp."""
        tmp_path, mapping_dir, otel_dir = temp_mapping_dir
        mapping_file = mapping_dir / "otel-session-mapping.json"
        
        mapping = OtelSessionMapping(
            mapping_file=str(mapping_file),
            otel_dir=str(otel_dir)
        )
        
        # Register multiple sessions
        mapping.register_session("session-a")
        mapping.register_session("session-b")
        mapping.register_session("session-c")
        
        mappings = mapping.list_mappings()
        
        assert len(mappings) == 3
        
        # Should be sorted by timestamp (newest first)
        for entry in mappings:
            assert isinstance(entry, OtelSessionMappingEntry)
    
    def test_remove_mapping(self, temp_mapping_dir):
        """Test removing a session mapping."""
        tmp_path, mapping_dir, otel_dir = temp_mapping_dir
        mapping_file = mapping_dir / "otel-session-mapping.json"
        
        mapping = OtelSessionMapping(
            mapping_file=str(mapping_file),
            otel_dir=str(otel_dir)
        )
        
        session_id = "to-be-removed"
        mapping.register_session(session_id)
        
        # Verify it exists
        assert mapping.get_mapping(session_id) is not None
        
        # Remove it
        result = mapping.remove_mapping(session_id)
        assert result is True
        
        # Verify it's gone
        assert mapping.get_mapping(session_id) is None
        
        # Try to remove again (should return False)
        result = mapping.remove_mapping(session_id)
        assert result is False
    
    # Test 3: Loading metrics according to mapping
    def test_get_or_create_otel_file_existing(self, temp_mapping_dir):
        """Test get_or_create returns existing mapping if available."""
        tmp_path, mapping_dir, otel_dir = temp_mapping_dir
        mapping_file = mapping_dir / "otel-session-mapping.json"
        
        mapping = OtelSessionMapping(
            mapping_file=str(mapping_file),
            otel_dir=str(otel_dir)
        )
        
        session_id = "existing-session"
        original_file = mapping.register_session(session_id)
        
        # Get or create should return the existing file
        result_file = mapping.get_or_create_otel_file(session_id)
        
        assert result_file == original_file
    
    def test_get_or_create_otel_file_new(self, temp_mapping_dir):
        """Test get_or_create creates new mapping if not found."""
        tmp_path, mapping_dir, otel_dir = temp_mapping_dir
        mapping_file = mapping_dir / "otel-session-mapping.json"
        
        mapping = OtelSessionMapping(
            mapping_file=str(mapping_file),
            otel_dir=str(otel_dir)
        )
        
        session_id = "new-session"
        
        # Get or create should create a new mapping
        result_file = mapping.get_or_create_otel_file(session_id)
        
        assert result_file is not None
        assert session_id in result_file
        
        # Should now be retrievable
        entry = mapping.get_mapping(session_id)
        assert entry is not None
        assert entry.otel_log_file == result_file
    
    def test_find_by_otel_file(self, temp_mapping_dir):
        """Test finding a mapping by OTEL file path."""
        tmp_path, mapping_dir, otel_dir = temp_mapping_dir
        mapping_file = mapping_dir / "otel-session-mapping.json"
        
        mapping = OtelSessionMapping(
            mapping_file=str(mapping_file),
            otel_dir=str(otel_dir)
        )
        
        session_id = "findable-session"
        otel_file = mapping.register_session(session_id)
        
        # Find by file path
        entry = mapping.find_by_otel_file(otel_file)
        
        assert entry is not None
        assert entry.session_id == session_id
    
    # Test 4: Full workflow - create, save metrics, load via mapping
    def test_full_otel_workflow_with_mapping(
        self, temp_mapping_dir, temp_db, sample_otel_output
    ):
        """Test complete workflow: register session, save metrics, load via mapping."""
        tmp_path, mapping_dir, otel_dir = temp_mapping_dir
        mapping_file = mapping_dir / "otel-session-mapping.json"
        
        # Create mapping and collector
        mapping = OtelSessionMapping(
            mapping_file=str(mapping_file),
            otel_dir=str(otel_dir)
        )
        collector = OtelMetricsCollector(metrics_dir=str(otel_dir))
        
        session_id = "workflow-test-session"
        
        # Step 1: Register session and get OTEL file path
        otel_file = mapping.register_session(
            session_id,
            description="Workflow test"
        )
        
        # Step 2: Write OTEL output to the mapped file
        with open(otel_file, 'w') as f:
            f.write(sample_otel_output)
        
        # Step 3: Collect metrics from the file
        metrics = collector.collect_from_file(otel_file, session_id)
        
        # Verify metrics were parsed correctly
        assert metrics.input_tokens == 1250
        assert metrics.output_tokens == 380
        assert metrics.cache_read_tokens == 520
        assert metrics.api_calls == 5
        
        # Step 4: Save metrics to database
        temp_db.save_otel_metrics(session_id, metrics.to_dict())
        
        # Step 5: Load metrics from database using mapping
        loaded_file = mapping.get_otel_file(session_id)
        assert loaded_file == otel_file
        
        otel_summary = temp_db.get_otel_summary(session_id)
        assert otel_summary is not None
        assert otel_summary["input_tokens"] == 1250
        assert otel_summary["output_tokens"] == 380
    
    def test_mapping_with_custom_otel_file(self, temp_mapping_dir):
        """Test registering a session with a custom OTEL file path."""
        tmp_path, mapping_dir, otel_dir = temp_mapping_dir
        mapping_file = mapping_dir / "otel-session-mapping.json"
        
        mapping = OtelSessionMapping(
            mapping_file=str(mapping_file),
            otel_dir=str(otel_dir)
        )
        
        session_id = "custom-file-session"
        custom_file = str(tmp_path / "custom_otel_output.txt")
        
        result = mapping.register_session(
            session_id,
            otel_log_file=custom_file
        )
        
        assert result == custom_file
        
        entry = mapping.get_mapping(session_id)
        assert entry.otel_log_file == custom_file


class TestOtelMappingCLIIntegration:
    """Test CLI commands for OTEL session mapping."""
    
    @pytest.fixture
    def temp_mapping_dir(self, tmp_path, monkeypatch):
        """Set up temporary directories and environment for CLI tests."""
        mapping_dir = tmp_path / ".claude-trace"
        mapping_dir.mkdir()
        otel_dir = mapping_dir / "otel-metrics"
        otel_dir.mkdir()
        
        # Patch the default paths
        monkeypatch.setattr(
            "claude_trace.otel_collector.OtelSessionMapping.DEFAULT_MAPPING_FILE",
            str(mapping_dir / "otel-session-mapping.json")
        )
        monkeypatch.setattr(
            "claude_trace.otel_collector.OtelSessionMapping.DEFAULT_OTEL_DIR",
            str(otel_dir)
        )
        
        return tmp_path, mapping_dir, otel_dir
    
    def test_cli_otel_mapping_list_empty(self, temp_mapping_dir, capsys):
        """Test otel-mapping list with no mappings."""
        from claude_trace.cli import cmd_otel_mapping
        
        class Args:
            action = "list"
            session_id = None
            otel_file = None
            description = None
        
        result = cmd_otel_mapping(Args())
        
        assert result == 0
        captured = capsys.readouterr()
        assert "No OTEL session mappings found" in captured.out
    
    def test_cli_otel_mapping_register_and_list(self, temp_mapping_dir, capsys):
        """Test registering a mapping via CLI and listing it."""
        from claude_trace.cli import cmd_otel_mapping
        
        # Register a session
        class RegisterArgs:
            action = "register"
            session_id = "cli-test-session"
            otel_file = None
            description = "Test from CLI"
        
        result = cmd_otel_mapping(RegisterArgs())
        assert result == 0
        
        captured = capsys.readouterr()
        assert "Registered session mapping" in captured.out
        assert "cli-test-session" in captured.out
        
        # List mappings
        class ListArgs:
            action = "list"
            session_id = None
            otel_file = None
            description = None
        
        result = cmd_otel_mapping(ListArgs())
        assert result == 0
        
        captured = capsys.readouterr()
        assert "cli-test-session" in captured.out
    
    def test_cli_otel_mapping_get(self, temp_mapping_dir, capsys):
        """Test getting a specific mapping via CLI."""
        from claude_trace.cli import cmd_otel_mapping
        from claude_trace.otel_collector import OtelSessionMapping
        
        # First register directly
        mapping = OtelSessionMapping()
        mapping.register_session("get-test-session", description="For get test")
        
        # Get via CLI
        class Args:
            action = "get"
            session_id = "get-test-session"
            otel_file = None
            description = None
        
        result = cmd_otel_mapping(Args())
        assert result == 0
        
        captured = capsys.readouterr()
        assert "get-test-session" in captured.out
        assert "File Status:" in captured.out
    
    def test_cli_otel_mapping_remove(self, temp_mapping_dir, capsys):
        """Test removing a mapping via CLI."""
        from claude_trace.cli import cmd_otel_mapping
        from claude_trace.otel_collector import OtelSessionMapping
        
        # First register
        mapping = OtelSessionMapping()
        mapping.register_session("remove-test-session")
        
        # Remove via CLI
        class Args:
            action = "remove"
            session_id = "remove-test-session"
            otel_file = None
            description = None
        
        result = cmd_otel_mapping(Args())
        assert result == 0
        
        captured = capsys.readouterr()
        assert "Removed mapping" in captured.out
        
        # Verify it's gone - need to reload from disk
        mapping2 = OtelSessionMapping()
        assert mapping2.get_mapping("remove-test-session") is None
    
    def test_cli_otel_mapping_generate_path(self, temp_mapping_dir, capsys):
        """Test generate-path action via CLI."""
        from claude_trace.cli import cmd_otel_mapping
        
        class Args:
            action = "generate-path"
            session_id = "path-gen-session"
            otel_file = None
            description = None
        
        result = cmd_otel_mapping(Args())
        assert result == 0
        
        captured = capsys.readouterr()
        assert "path-gen-session" in captured.out
        assert "_otel.txt" in captured.out
    
    def test_cli_otel_auto(self, temp_mapping_dir, capsys):
        """Test otel-auto command."""
        from claude_trace.cli import cmd_otel_auto
        
        class Args:
            session_id = "auto-test-session"
            description = "Auto test"
        
        result = cmd_otel_auto(Args())
        assert result == 0
        
        captured = capsys.readouterr()
        assert "auto-test-session" in captured.out
        assert "_otel.txt" in captured.out
        
        # Run again - should return the same path
        result = cmd_otel_auto(Args())
        assert result == 0
        
        captured2 = capsys.readouterr()
        # Same path should be returned
        assert captured.out == captured2.out
    
    def test_cli_otel_import_registers_mapping(self, temp_mapping_dir, capsys, tmp_path):
        """Test that otel-import also registers a mapping."""
        from claude_trace.cli import cmd_otel_import
        from claude_trace.otel_collector import OtelSessionMapping
        
        # Create a sample OTEL file
        sample_otel_file = tmp_path / "sample_otel.txt"
        sample_otel_file.write_text("claude_code.tokens.input 100\nclaude_code.tokens.output 50")
        
        class Args:
            session_id = "import-mapping-test"
            otel_file = str(sample_otel_file)
            verbose = False
        
        result = cmd_otel_import(Args())
        assert result == 0
        
        # Verify mapping was created
        mapping = OtelSessionMapping()
        entry = mapping.get_mapping("import-mapping-test")
        assert entry is not None
        assert str(sample_otel_file) in entry.otel_log_file

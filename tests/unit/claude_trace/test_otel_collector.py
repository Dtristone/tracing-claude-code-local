"""
Unit tests for OTEL metrics collector.

Tests:
- OtelMetricsParser - parsing various OTEL console output formats
- OtelMetricsCollector - collecting and storing metrics
- OtelSessionMetrics - metrics data structure
"""

import json
import os
import pytest
import tempfile
from datetime import datetime
from pathlib import Path

from claude_trace.otel_collector import (
    OtelMetricsParser,
    OtelMetricsCollector,
    OtelSessionMetrics,
    OtelMetric,
    OtelMetricDataPoint,
)


class TestOtelMetricDataPoint:
    """Tests for OtelMetricDataPoint dataclass."""
    
    def test_create_data_point(self):
        """Test creating a data point."""
        dp = OtelMetricDataPoint(value=100.5)
        assert dp.value == 100.5
        assert dp.timestamp is None
        assert dp.attributes == {}
    
    def test_create_data_point_with_all_fields(self):
        """Test creating a data point with all fields."""
        now = datetime.now()
        dp = OtelMetricDataPoint(
            value=250.0,
            timestamp=now,
            attributes={"model": "claude-sonnet-4-5"}
        )
        assert dp.value == 250.0
        assert dp.timestamp == now
        assert dp.attributes["model"] == "claude-sonnet-4-5"


class TestOtelMetric:
    """Tests for OtelMetric dataclass."""
    
    def test_create_metric(self):
        """Test creating a metric."""
        metric = OtelMetric(name="tokens.input")
        assert metric.name == "tokens.input"
        assert metric.metric_type == "counter"
        assert metric.data_points == []
    
    def test_metric_total_value(self):
        """Test calculating total value."""
        metric = OtelMetric(
            name="tokens.input",
            data_points=[
                OtelMetricDataPoint(value=100),
                OtelMetricDataPoint(value=200),
                OtelMetricDataPoint(value=150)
            ]
        )
        assert metric.total_value == 450
    
    def test_metric_avg_value(self):
        """Test calculating average value."""
        metric = OtelMetric(
            name="latency",
            data_points=[
                OtelMetricDataPoint(value=100),
                OtelMetricDataPoint(value=200),
                OtelMetricDataPoint(value=300)
            ]
        )
        assert metric.avg_value == 200.0
    
    def test_metric_last_value(self):
        """Test getting last value."""
        metric = OtelMetric(
            name="gauge",
            data_points=[
                OtelMetricDataPoint(value=100),
                OtelMetricDataPoint(value=250)
            ]
        )
        assert metric.last_value == 250
    
    def test_empty_metric_values(self):
        """Test empty metric value calculations."""
        metric = OtelMetric(name="empty")
        assert metric.total_value == 0
        assert metric.avg_value == 0.0
        assert metric.last_value == 0.0


class TestOtelSessionMetrics:
    """Tests for OtelSessionMetrics dataclass."""
    
    def test_create_session_metrics(self):
        """Test creating session metrics."""
        metrics = OtelSessionMetrics(session_id="test-123")
        assert metrics.session_id == "test-123"
        assert metrics.metrics == {}
    
    def test_input_tokens_property(self):
        """Test input_tokens property extracts from various metric names."""
        # Test with claude_code.tokens.input
        metrics = OtelSessionMetrics(
            session_id="test",
            metrics={
                "claude_code.tokens.input": OtelMetric(
                    name="claude_code.tokens.input",
                    data_points=[OtelMetricDataPoint(value=1500)]
                )
            }
        )
        assert metrics.input_tokens == 1500
    
    def test_output_tokens_property(self):
        """Test output_tokens property."""
        metrics = OtelSessionMetrics(
            session_id="test",
            metrics={
                "claude_code.tokens.output": OtelMetric(
                    name="claude_code.tokens.output",
                    data_points=[OtelMetricDataPoint(value=500)]
                )
            }
        )
        assert metrics.output_tokens == 500
    
    def test_cache_read_tokens_property(self):
        """Test cache_read_tokens property."""
        metrics = OtelSessionMetrics(
            session_id="test",
            metrics={
                "claude_code.tokens.cache_read": OtelMetric(
                    name="claude_code.tokens.cache_read",
                    data_points=[OtelMetricDataPoint(value=1000)]
                )
            }
        )
        assert metrics.cache_read_tokens == 1000
    
    def test_api_calls_property(self):
        """Test api_calls property."""
        metrics = OtelSessionMetrics(
            session_id="test",
            metrics={
                "claude_code.api.calls": OtelMetric(
                    name="claude_code.api.calls",
                    data_points=[OtelMetricDataPoint(value=5)]
                )
            }
        )
        assert metrics.api_calls == 5
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        now = datetime.now()
        metrics = OtelSessionMetrics(
            session_id="test-123",
            collected_at=now,
            metrics={
                "tokens.input": OtelMetric(
                    name="tokens.input",
                    data_points=[OtelMetricDataPoint(value=100)]
                )
            }
        )
        
        result = metrics.to_dict()
        assert result["session_id"] == "test-123"
        assert result["collected_at"] == now.isoformat()
        assert "summary" in result
        assert "metrics" in result


class TestOtelMetricsParser:
    """Tests for OtelMetricsParser."""
    
    @pytest.fixture
    def parser(self):
        return OtelMetricsParser()
    
    def test_parse_prometheus_format(self, parser):
        """Test parsing Prometheus-style text format."""
        output = """
# HELP claude_code.tokens.input Total input tokens
# TYPE claude_code.tokens.input counter
claude_code.tokens.input{model="claude-sonnet-4-5"} 1500
claude_code.tokens.input{model="claude-sonnet-4-5"} 2000
# HELP claude_code.tokens.output Total output tokens
# TYPE claude_code.tokens.output counter
claude_code.tokens.output{} 500
"""
        metrics = parser.parse_console_output(output)
        
        assert "claude_code.tokens.input" in metrics
        assert metrics["claude_code.tokens.input"].total_value == 3500
        assert "claude_code.tokens.output" in metrics
        assert metrics["claude_code.tokens.output"].total_value == 500
    
    def test_parse_simple_metric_line(self, parser):
        """Test parsing simple metric lines."""
        output = """
tokens.input 1000
tokens.output 250
latency 150.5
"""
        metrics = parser.parse_console_output(output)
        
        assert "tokens.input" in metrics
        assert metrics["tokens.input"].total_value == 1000
        assert "tokens.output" in metrics
        assert metrics["tokens.output"].total_value == 250
        assert "latency" in metrics
        assert metrics["latency"].total_value == 150.5
    
    def test_parse_metric_with_labels(self, parser):
        """Test parsing metrics with labels."""
        output = 'api.calls{service="claude",version="1.0"} 10'
        metrics = parser.parse_console_output(output)
        
        assert "api.calls" in metrics
        dp = metrics["api.calls"].data_points[0]
        assert dp.value == 10
        assert dp.attributes.get("service") == "claude"
        assert dp.attributes.get("version") == "1.0"
    
    def test_parse_json_format(self, parser):
        """Test parsing JSON-formatted output."""
        output = json.dumps({
            "name": "claude_code.tokens.input",
            "description": "Input tokens",
            "unit": "tokens",
            "type": "counter",
            "data_points": [
                {"value": 500, "attributes": {"model": "claude"}},
                {"value": 300, "attributes": {"model": "claude"}}
            ]
        })
        
        metrics = parser.parse_console_output(output)
        
        assert "claude_code.tokens.input" in metrics
        assert metrics["claude_code.tokens.input"].total_value == 800
    
    def test_parse_empty_output(self, parser):
        """Test parsing empty output."""
        metrics = parser.parse_console_output("")
        assert metrics == {}
    
    def test_parse_comments_only(self, parser):
        """Test parsing output with only comments."""
        output = """
# This is a comment
# Another comment
"""
        metrics = parser.parse_console_output(output)
        assert metrics == {}
    
    def test_parse_multiple_json_lines(self, parser):
        """Test parsing multiple JSON objects."""
        lines = [
            json.dumps({"name": "metric1", "data_points": [{"value": 100}]}),
            json.dumps({"name": "metric2", "data_points": [{"value": 200}]})
        ]
        output = "\n".join(lines)
        
        metrics = parser.parse_console_output(output)
        
        assert len(metrics) == 2
        assert "metric1" in metrics
        assert "metric2" in metrics


class TestOtelMetricsCollector:
    """Tests for OtelMetricsCollector."""
    
    @pytest.fixture
    def temp_metrics_dir(self, tmp_path):
        return str(tmp_path / "otel-metrics")
    
    @pytest.fixture
    def collector(self, temp_metrics_dir):
        return OtelMetricsCollector(metrics_dir=temp_metrics_dir)
    
    def test_collect_from_output(self, collector):
        """Test collecting metrics from raw output."""
        output = """
claude_code.tokens.input 1500
claude_code.tokens.output 500
claude_code.api.calls 3
"""
        metrics = collector.collect_from_output(output, "test-session")
        
        assert metrics.session_id == "test-session"
        assert metrics.input_tokens == 1500
        assert metrics.output_tokens == 500
        assert metrics.api_calls == 3
    
    def test_collect_from_file(self, collector, tmp_path):
        """Test collecting metrics from file."""
        metrics_file = tmp_path / "otel_output.txt"
        metrics_file.write_text("""
tokens.input 2000
tokens.output 800
""")
        
        metrics = collector.collect_from_file(str(metrics_file), "file-session")
        
        assert metrics.session_id == "file-session"
        assert len(metrics.metrics) > 0
    
    def test_save_and_load_metrics(self, collector):
        """Test saving and loading metrics."""
        output = """
claude_code.tokens.input 1000
claude_code.tokens.output 250
"""
        original = collector.collect_from_output(output, "save-test")
        
        # Save
        file_path = collector.save_metrics(original)
        assert os.path.exists(file_path)
        
        # Load
        loaded = collector.load_metrics("save-test")
        assert loaded is not None
        assert loaded.session_id == "save-test"
        assert loaded.input_tokens == original.input_tokens
    
    def test_save_raw_output(self, collector):
        """Test saving raw output."""
        raw_output = "some raw OTEL output\nmetric_name 123"
        file_path = collector.save_raw_output(raw_output, "raw-session")
        
        assert os.path.exists(file_path)
        with open(file_path) as f:
            content = f.read()
        assert content == raw_output
    
    def test_list_sessions_with_metrics(self, collector):
        """Test listing sessions with metrics."""
        # Create some metrics
        for i in range(3):
            output = f"metric_{i} {i * 100}"
            metrics = collector.collect_from_output(output, f"session-{i}")
            collector.save_metrics(metrics)
        
        sessions = collector.list_sessions_with_metrics()
        assert len(sessions) == 3
        assert "session-0" in sessions
        assert "session-1" in sessions
        assert "session-2" in sessions
    
    def test_metrics_dir_created(self, temp_metrics_dir):
        """Test that metrics directory is created."""
        assert not os.path.exists(temp_metrics_dir)
        collector = OtelMetricsCollector(metrics_dir=temp_metrics_dir)
        assert os.path.exists(temp_metrics_dir)
    
    def test_load_nonexistent_session(self, collector):
        """Test loading metrics for nonexistent session."""
        result = collector.load_metrics("nonexistent")
        assert result is None
    
    def test_collect_from_nonexistent_file(self, collector):
        """Test collecting from nonexistent file raises FileNotFoundError with path."""
        nonexistent_path = "/nonexistent/path.txt"
        with pytest.raises(FileNotFoundError) as exc_info:
            collector.collect_from_file(nonexistent_path)
        assert nonexistent_path in str(exc_info.value)


class TestOtelParserErrorHandling:
    """Tests for OTEL parser error handling with malformed input."""
    
    @pytest.fixture
    def parser(self):
        return OtelMetricsParser()
    
    def test_parse_malformed_json(self, parser):
        """Test parsing malformed JSON gracefully."""
        output = '{"name": "metric", "invalid json here'
        metrics = parser.parse_console_output(output)
        # Should not crash, just return empty or partial results
        assert isinstance(metrics, dict)
    
    def test_parse_invalid_metric_values(self, parser):
        """Test parsing metrics with non-numeric values."""
        output = 'metric_name abc'  # 'abc' is not a valid number
        metrics = parser.parse_console_output(output)
        # Should skip invalid lines
        assert "metric_name" not in metrics
    
    def test_parse_mixed_valid_invalid(self, parser):
        """Test parsing output with mix of valid and invalid lines."""
        output = """
metric1 100
invalid_line_without_value
metric2 200
not_a_metric
metric3 300
"""
        metrics = parser.parse_console_output(output)
        # Should extract only valid metrics
        assert "metric1" in metrics
        assert "metric2" in metrics
        assert "metric3" in metrics
        assert metrics["metric1"].total_value == 100
        assert metrics["metric2"].total_value == 200
        assert metrics["metric3"].total_value == 300


class TestOtelIntegrationWithStorage:
    """Integration tests for OTEL metrics with storage."""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        from claude_trace.storage import TraceStorage
        db_path = tmp_path / "test.db"
        return TraceStorage(str(db_path))
    
    def test_save_otel_to_storage(self, temp_db):
        """Test saving OTEL metrics to storage."""
        collector = OtelMetricsCollector()
        
        output = """
claude_code.tokens.input 3000
claude_code.tokens.output 1000
claude_code.tokens.cache_read 1500
claude_code.api.calls 5
"""
        metrics = collector.collect_from_output(output, "storage-test")
        temp_db.save_otel_metrics("storage-test", metrics.to_dict())
        
        # Verify saved
        summary = temp_db.get_otel_summary("storage-test")
        assert summary is not None
        assert summary["input_tokens"] == 3000
        assert summary["output_tokens"] == 1000
        assert summary["cache_read_tokens"] == 1500
        assert summary["api_calls"] == 5
    
    def test_get_aggregate_otel_metrics(self, temp_db):
        """Test getting aggregate OTEL metrics."""
        collector = OtelMetricsCollector()
        
        # Add metrics for multiple sessions
        for i in range(3):
            output = f"""
claude_code.tokens.input {1000 * (i + 1)}
claude_code.tokens.output {500 * (i + 1)}
"""
            metrics = collector.collect_from_output(output, f"agg-session-{i}")
            temp_db.save_otel_metrics(f"agg-session-{i}", metrics.to_dict())
        
        aggregate = temp_db.get_aggregate_otel_metrics()
        assert aggregate["session_count"] == 3
        # 1000 + 2000 + 3000 = 6000
        assert aggregate["input_tokens"] == 6000
        # 500 + 1000 + 1500 = 3000
        assert aggregate["output_tokens"] == 3000
    
    def test_has_otel_metrics(self, temp_db):
        """Test checking if session has OTEL metrics."""
        collector = OtelMetricsCollector()
        
        assert not temp_db.has_otel_metrics("nonexistent")
        
        output = "tokens.input 100"
        metrics = collector.collect_from_output(output, "has-test")
        temp_db.save_otel_metrics("has-test", metrics.to_dict())
        
        assert temp_db.has_otel_metrics("has-test")

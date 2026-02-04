"""Tests for claude_trace.utils module."""

import pytest
from datetime import datetime

from claude_trace.utils import (
    parse_timestamp,
    format_duration,
    format_tokens,
    format_percentage,
    format_bytes,
    truncate_string,
    clean_model_name,
    generate_id,
    safe_json_loads,
    get_nested,
)


@pytest.mark.unit
class TestParseTimestamp:
    """Tests for parse_timestamp function."""
    
    def test_iso_with_microseconds(self):
        """Test parsing ISO timestamp with microseconds."""
        result = parse_timestamp("2025-02-04T10:30:00.123456Z")
        assert result.year == 2025
        assert result.month == 2
        assert result.day == 4
        assert result.hour == 10
        assert result.minute == 30
        assert result.microsecond == 123456
    
    def test_iso_without_microseconds(self):
        """Test parsing ISO timestamp without microseconds."""
        result = parse_timestamp("2025-02-04T10:30:00Z")
        assert result.year == 2025
        assert result.hour == 10
    
    def test_iso_with_milliseconds(self):
        """Test parsing ISO timestamp with milliseconds."""
        result = parse_timestamp("2025-02-04T10:30:00.123Z")
        assert result.microsecond == 123000
    
    def test_empty_string(self):
        """Test parsing empty string returns current time."""
        result = parse_timestamp("")
        assert isinstance(result, datetime)


@pytest.mark.unit
class TestFormatDuration:
    """Tests for format_duration function."""
    
    def test_milliseconds(self):
        """Test formatting milliseconds."""
        assert format_duration(500) == "500ms"
    
    def test_seconds(self):
        """Test formatting seconds."""
        assert format_duration(2500) == "2.5s"
    
    def test_minutes(self):
        """Test formatting minutes."""
        assert format_duration(90000) == "1m 30.0s"
    
    def test_hours(self):
        """Test formatting hours."""
        assert format_duration(3700000) == "1h 1m 40s"
    
    def test_none(self):
        """Test formatting None."""
        assert format_duration(None) == "N/A"


@pytest.mark.unit
class TestFormatTokens:
    """Tests for format_tokens function."""
    
    def test_small_number(self):
        """Test formatting small number."""
        assert format_tokens(100) == "100"
    
    def test_thousands(self):
        """Test formatting thousands."""
        assert format_tokens(1234) == "1,234"
    
    def test_millions(self):
        """Test formatting millions."""
        assert format_tokens(1234567) == "1,234,567"


@pytest.mark.unit
class TestFormatPercentage:
    """Tests for format_percentage function."""
    
    def test_whole_number(self):
        """Test formatting whole percentage."""
        assert format_percentage(50.0) == "50.0%"
    
    def test_decimal(self):
        """Test formatting decimal percentage."""
        assert format_percentage(42.567) == "42.6%"


@pytest.mark.unit
class TestFormatBytes:
    """Tests for format_bytes function."""
    
    def test_bytes(self):
        """Test formatting bytes."""
        assert format_bytes(500) == "500B"
    
    def test_kilobytes(self):
        """Test formatting kilobytes."""
        assert format_bytes(2048) == "2.0KB"
    
    def test_megabytes(self):
        """Test formatting megabytes."""
        assert format_bytes(1048576) == "1.0MB"
    
    def test_gigabytes(self):
        """Test formatting gigabytes."""
        assert format_bytes(2147483648) == "2.00GB"


@pytest.mark.unit
class TestTruncateString:
    """Tests for truncate_string function."""
    
    def test_short_string(self):
        """Test truncating short string."""
        assert truncate_string("hello", 10) == "hello"
    
    def test_long_string(self):
        """Test truncating long string."""
        assert truncate_string("hello world", 8) == "hello..."
    
    def test_custom_suffix(self):
        """Test truncating with custom suffix."""
        assert truncate_string("hello world", 10, "~") == "hello wor~"


@pytest.mark.unit
class TestCleanModelName:
    """Tests for clean_model_name function."""
    
    def test_with_date_suffix(self):
        """Test cleaning model name with date suffix."""
        assert clean_model_name("claude-sonnet-4-5-20250929") == "claude-sonnet-4-5"
    
    def test_without_date_suffix(self):
        """Test cleaning model name without date suffix."""
        assert clean_model_name("claude-sonnet-4-5") == "claude-sonnet-4-5"
    
    def test_empty_string(self):
        """Test cleaning empty string."""
        assert clean_model_name("") == "unknown"
    
    def test_none(self):
        """Test cleaning None."""
        assert clean_model_name(None) == "unknown"


@pytest.mark.unit
class TestGenerateId:
    """Tests for generate_id function."""
    
    def test_returns_string(self):
        """Test that generate_id returns a string."""
        result = generate_id()
        assert isinstance(result, str)
    
    def test_unique_ids(self):
        """Test that generate_id returns unique IDs."""
        ids = [generate_id() for _ in range(100)]
        assert len(set(ids)) == 100


@pytest.mark.unit
class TestSafeJsonLoads:
    """Tests for safe_json_loads function."""
    
    def test_valid_json(self):
        """Test parsing valid JSON."""
        result = safe_json_loads('{"key": "value"}')
        assert result == {"key": "value"}
    
    def test_invalid_json(self):
        """Test parsing invalid JSON."""
        result = safe_json_loads('not json')
        assert result is None
    
    def test_none_input(self):
        """Test parsing None."""
        result = safe_json_loads(None)
        assert result is None


@pytest.mark.unit
class TestGetNested:
    """Tests for get_nested function."""
    
    def test_simple_path(self):
        """Test getting simple nested value."""
        data = {"a": {"b": {"c": "value"}}}
        assert get_nested(data, "a", "b", "c") == "value"
    
    def test_missing_key(self):
        """Test getting missing key."""
        data = {"a": {"b": {}}}
        assert get_nested(data, "a", "b", "c") is None
    
    def test_default_value(self):
        """Test getting with default value."""
        data = {"a": {}}
        assert get_nested(data, "a", "b", "c", default="default") == "default"
    
    def test_non_dict_intermediate(self):
        """Test getting with non-dict intermediate."""
        data = {"a": "string"}
        assert get_nested(data, "a", "b") is None

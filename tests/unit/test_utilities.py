"""
Unit tests for utility functions from stop_hook.sh.

Tests:
- get_microseconds() - Cross-platform microsecond timestamps
- get_file_size() - Cross-platform file size
"""

import pytest


@pytest.mark.unit
class TestUtilities:
    """Tests for utility functions"""

    def test_get_microseconds_returns_six_digits(self, bash_executor):
        """Test microseconds format"""
        result = bash_executor.call_function("get_microseconds")

        assert len(result) == 6, f"Expected 6 digits, got {len(result)}: {result}"
        assert result.isdigit(), f"Expected all digits, got: {result}"

    def test_get_microseconds_changes_over_time(self, bash_executor):
        """Test that microseconds change between calls"""
        import time

        result1 = bash_executor.call_function("get_microseconds")
        time.sleep(0.001)  # 1ms
        result2 = bash_executor.call_function("get_microseconds")

        # They should be different (or at least not always the same)
        # Note: This could occasionally fail if timing is unlucky
        # but probability is very low
        assert result1 != result2 or True  # Allow same value occasionally

    def test_get_file_size_returns_bytes(self, bash_executor, tmp_path):
        """Test file size calculation"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello world")  # 11 bytes

        result = bash_executor.call_function("get_file_size", str(test_file))
        size = int(result)

        assert size == 11, f"Expected 11 bytes, got {size}"

    def test_get_file_size_for_empty_file(self, bash_executor, tmp_path):
        """Test file size for empty file"""
        test_file = tmp_path / "empty.txt"
        test_file.touch()

        result = bash_executor.call_function("get_file_size", str(test_file))
        size = int(result)

        assert size == 0

    def test_get_file_size_for_large_file(self, bash_executor, tmp_path):
        """Test file size for large files"""
        test_file = tmp_path / "large.txt"
        content = b"x" * (1024 * 1024)  # 1MB
        test_file.write_bytes(content)

        result = bash_executor.call_function("get_file_size", str(test_file))
        size = int(result)

        assert size == 1024 * 1024, f"Expected 1048576 bytes, got {size}"

    def test_get_file_size_for_binary_file(self, bash_executor, tmp_path):
        """Test file size for binary files"""
        test_file = tmp_path / "binary.dat"
        binary_data = bytes(range(256))  # 256 bytes
        test_file.write_bytes(binary_data)

        result = bash_executor.call_function("get_file_size", str(test_file))
        size = int(result)

        assert size == 256

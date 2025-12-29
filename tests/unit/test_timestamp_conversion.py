"""
Unit tests for timestamp conversion in stop_hook.sh.

Tests the ISO timestamp to dotted_order format conversion:
- ISO format: 2025-12-16T17:44:04.397Z
- dotted_order format: 20251216T174404397000Z

This conversion is critical for proper trace ordering in LangSmith.
"""

import json
import subprocess
import pytest
from datetime import datetime


@pytest.mark.unit
class TestISOToDottedOrderConversion:
    """Tests for ISO timestamp to dotted_order conversion using sed"""

    def test_converts_iso_to_dotted_order_format(self):
        """Test basic ISO to dotted_order conversion"""
        # The sed command from stop_hook.sh line 537:
        # sed 's/[-:]//g; s/\.\([0-9]*\)Z$/\1000Z/; s/T\([0-9]*\)\([0-9]\{3\}\)000Z$/T\1\2000Z/'

        iso_timestamp = "2025-12-16T17:44:04.397Z"
        expected = "20251216T174404397000Z"

        cmd = f"echo '{iso_timestamp}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True
        )

        assert result.stdout.strip() == expected

    def test_converts_single_digit_milliseconds(self):
        """Test conversion with single digit milliseconds (e.g., .1Z)"""
        iso_timestamp = "2025-12-16T17:44:04.1Z"
        # .1 -> 1000Z (padded to microseconds)

        cmd = f"echo '{iso_timestamp}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True
        )

        # Should produce 1000 (1 padded with zeros for microseconds)
        output = result.stdout.strip()
        assert "T1744041000Z" in output

    def test_converts_two_digit_milliseconds(self):
        """Test conversion with two digit milliseconds (e.g., .12Z)"""
        iso_timestamp = "2025-12-16T17:44:04.12Z"

        cmd = f"echo '{iso_timestamp}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True
        )

        output = result.stdout.strip()
        assert "T17440412000Z" in output

    def test_converts_full_milliseconds(self):
        """Test conversion with full 3-digit milliseconds"""
        iso_timestamp = "2025-12-16T17:44:04.123Z"
        expected = "20251216T174404123000Z"

        cmd = f"echo '{iso_timestamp}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True
        )

        assert result.stdout.strip() == expected

    def test_removes_dashes_from_date(self):
        """Test that dashes are removed from date portion"""
        iso_timestamp = "2025-12-16T17:44:04.000Z"

        cmd = f"echo '{iso_timestamp}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True
        )

        output = result.stdout.strip()
        # Date should be 20251216 not 2025-12-16
        assert output.startswith("20251216T")
        assert "-" not in output

    def test_removes_colons_from_time(self):
        """Test that colons are removed from time portion"""
        iso_timestamp = "2025-12-16T17:44:04.000Z"

        cmd = f"echo '{iso_timestamp}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True
        )

        output = result.stdout.strip()
        # Time should be 174404 not 17:44:04
        assert "T174404" in output
        assert ":" not in output

    def test_preserves_z_suffix(self):
        """Test that Z suffix is preserved"""
        iso_timestamp = "2025-12-16T17:44:04.123Z"

        cmd = f"echo '{iso_timestamp}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True
        )

        assert result.stdout.strip().endswith("Z")

    def test_pads_milliseconds_to_microseconds(self):
        """Test that milliseconds are padded to 6 digits (microseconds)"""
        # 397 milliseconds should become 397000 microseconds
        iso_timestamp = "2025-12-16T17:44:04.397Z"

        cmd = f"echo '{iso_timestamp}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True
        )

        output = result.stdout.strip()
        # 397 padded to 397000
        assert "397000Z" in output


@pytest.mark.unit
class TestDottedOrderTimestampFormat:
    """Tests for generating dotted_order timestamps"""

    def test_dotted_timestamp_format(self, bash_executor):
        """Test that dotted timestamp has correct format"""
        # Generate a timestamp using the same logic as stop_hook.sh
        script = """
        set -e
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)

        dotted_timestamp=$(date -u +"%Y%m%dT%H%M%S")
        microseconds=$(get_microseconds)
        dotted_timestamp="${dotted_timestamp}${microseconds}Z"
        echo "$dotted_timestamp"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        output = result.stdout.strip()

        # Format should be: YYYYMMDDTHHMMSSffffffZ (22 chars)
        # YYYYMMDD (8) + T (1) + HHMMSS (6) + ffffff (6) + Z (1) = 22
        assert len(output) == 22
        assert output[8] == "T"  # T separator
        assert output[-1] == "Z"  # Z suffix
        assert output[:8].isdigit()  # Date digits
        assert output[9:21].isdigit()  # Time + microseconds (HHMMSS + ffffff)

    def test_dotted_timestamp_year_month_day(self, bash_executor):
        """Test that date portion is correct format"""
        script = """
        dotted_timestamp=$(date -u +"%Y%m%dT%H%M%S")
        echo "${dotted_timestamp:0:8}"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True
        )

        output = result.stdout.strip()

        # Should be YYYYMMDD
        assert len(output) == 8
        year = int(output[:4])
        month = int(output[4:6])
        day = int(output[6:8])

        assert 2020 <= year <= 2030
        assert 1 <= month <= 12
        assert 1 <= day <= 31


@pytest.mark.unit
class TestTimestampChronologicalOrdering:
    """Tests verifying timestamps sort chronologically"""

    def test_earlier_timestamp_sorts_first(self):
        """Test that earlier ISO timestamps produce earlier dotted_orders"""
        timestamps = [
            "2025-12-16T17:44:04.100Z",
            "2025-12-16T17:44:04.200Z",
            "2025-12-16T17:44:04.300Z",
        ]

        dotted_orders = []
        for ts in timestamps:
            cmd = f"echo '{ts}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
            result = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True,
                text=True
            )
            dotted_orders.append(result.stdout.strip())

        # Should already be sorted chronologically
        assert dotted_orders == sorted(dotted_orders)

    def test_different_seconds_sort_correctly(self):
        """Test that timestamps with different seconds sort correctly"""
        timestamps = [
            "2025-12-16T17:44:05.000Z",  # Later
            "2025-12-16T17:44:04.999Z",  # Earlier (despite higher ms)
        ]

        dotted_orders = []
        for ts in timestamps:
            cmd = f"echo '{ts}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
            result = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True,
                text=True
            )
            dotted_orders.append(result.stdout.strip())

        # Sort and verify order
        sorted_orders = sorted(dotted_orders)
        # The 04.999 should come before 05.000
        assert "174404" in sorted_orders[0]
        assert "174405" in sorted_orders[1]

    def test_different_dates_sort_correctly(self):
        """Test that different dates sort correctly"""
        timestamps = [
            "2025-12-17T00:00:00.000Z",
            "2025-12-16T23:59:59.999Z",
        ]

        dotted_orders = []
        for ts in timestamps:
            cmd = f"echo '{ts}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
            result = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True,
                text=True
            )
            dotted_orders.append(result.stdout.strip())

        sorted_orders = sorted(dotted_orders)
        # Dec 16 should come before Dec 17
        assert "20251216" in sorted_orders[0]
        assert "20251217" in sorted_orders[1]


@pytest.mark.unit
class TestTimestampEdgeCases:
    """Tests for edge cases in timestamp handling"""

    def test_handles_midnight_timestamp(self):
        """Test handling of midnight timestamp"""
        iso_timestamp = "2025-12-16T00:00:00.000Z"
        expected = "20251216T000000000000Z"

        cmd = f"echo '{iso_timestamp}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True
        )

        assert result.stdout.strip() == expected

    def test_handles_end_of_day_timestamp(self):
        """Test handling of 23:59:59.999 timestamp"""
        iso_timestamp = "2025-12-16T23:59:59.999Z"
        expected = "20251216T235959999000Z"

        cmd = f"echo '{iso_timestamp}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True
        )

        assert result.stdout.strip() == expected

    def test_handles_zero_milliseconds(self):
        """Test handling of .000 milliseconds"""
        iso_timestamp = "2025-12-16T12:30:45.000Z"

        cmd = f"echo '{iso_timestamp}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True
        )

        output = result.stdout.strip()
        assert "000000Z" in output  # 000 padded to 000000

    def test_handles_leap_year_date(self):
        """Test handling of Feb 29 in a leap year"""
        iso_timestamp = "2024-02-29T12:00:00.500Z"

        cmd = f"echo '{iso_timestamp}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True
        )

        output = result.stdout.strip()
        assert output.startswith("20240229T")


@pytest.mark.unit
class TestTimestampWithRealTranscriptData:
    """Tests using real timestamp formats from cc_transcript.jsonl"""

    def test_converts_real_transcript_timestamp(self):
        """Test with actual timestamp format from cc_transcript.jsonl"""
        # Example from line 2: "timestamp":"2024-12-06T06:42:11.556Z"
        iso_timestamp = "2024-12-06T06:42:11.556Z"
        expected = "20241206T064211556000Z"

        cmd = f"echo '{iso_timestamp}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True
        )

        assert result.stdout.strip() == expected

    def test_multiple_transcript_timestamps_maintain_order(self):
        """Test that multiple timestamps from transcript maintain chronological order"""
        # Simulated sequence of timestamps from a transcript
        timestamps = [
            "2024-12-06T06:42:11.556Z",  # User message
            "2024-12-06T06:42:12.100Z",  # Assistant response
            "2024-12-06T06:42:12.500Z",  # Tool result
            "2024-12-06T06:42:13.200Z",  # Final response
        ]

        dotted_orders = []
        for ts in timestamps:
            cmd = f"echo '{ts}' | sed 's/[-:]//g; s/\\.\\([0-9]*\\)Z$/\\1000Z/; s/T\\([0-9]*\\)\\([0-9]\\{{3\\}}\\)000Z$/T\\1\\2000Z/'"
            result = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True,
                text=True
            )
            dotted_orders.append(result.stdout.strip())

        # Verify they're in chronological order
        assert dotted_orders == sorted(dotted_orders)

        # Verify each is unique
        assert len(set(dotted_orders)) == len(dotted_orders)

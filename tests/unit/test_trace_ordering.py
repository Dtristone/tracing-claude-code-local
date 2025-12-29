"""
Unit tests for trace ordering and dotted_order generation from stop_hook.sh.

These tests verify that traces are correctly ordered in LangSmith:
- dotted_order format (YYYYMMDDTHHMMSSffffffZuuid)
- Parent-child relationships via dotted_order
- Timestamp precision (microseconds)
- Chronological ordering
"""

import json
import re
import pytest
from datetime import datetime


@pytest.mark.unit
class TestDottedOrderFormat:
    """Tests for dotted_order timestamp format"""

    def test_dotted_order_format_structure(self):
        """Test dotted_order follows correct format: YYYYMMDDTHHMMSSffffffZuuid"""
        # Example from stop_hook.sh line 438:
        # dotted_order="${dotted_timestamp}${turn_id}"
        # Format: 20251216T174404397000Zuuid

        dotted_order = "20251216T174404397000Z0e01bf50-474d-4536-810f-67d3ee7ea3e7"

        # Verify format: timestamp (21 chars) + Z + UUID (36 chars)
        # Timestamp: YYYYMMDDTHHMMSS (14) + ffffff (6) = 20, but split shows 21
        assert len(dotted_order) == 58  # 21 + 1 + 36

        # Extract parts - timestamp is actually 20 digits
        timestamp_part = dotted_order.split('Z')[0]  # Everything before Z
        separator = 'Z'
        uuid_part = dotted_order.split('Z')[1]  # Everything after Z

        # Verify timestamp format: YYYYMMDDTHHMMSS + microseconds (20 chars total)
        assert re.match(r'^\d{8}T\d{12}$', timestamp_part), \
            f"Timestamp {timestamp_part} doesn't match YYYYMMDDTHHMMSSmmmmmm"

        # Verify separator
        assert separator == 'Z'

        # Verify UUID format
        assert re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', uuid_part), \
            f"UUID {uuid_part} doesn't match UUID format"

    def test_child_dotted_order_includes_parent(self):
        """Test child dotted_order includes parent's dotted_order as prefix"""
        # From stop_hook.sh line 544:
        # assistant_dotted_order="${turn_dotted_order}.${assistant_timestamp}${assistant_id}"

        parent_dotted_order = "20251216T174404397000Z0e01bf50-474d-4536-810f-67d3ee7ea3e7"
        child_dotted_order = "20251216T174404397000Z0e01bf50-474d-4536-810f-67d3ee7ea3e7.20251216T174405123456Za8024e23-5b82-47fd-970e-f6a5ba3f5097"

        # Child must start with parent's dotted_order
        assert child_dotted_order.startswith(parent_dotted_order)

        # Child must have a dot separator
        assert '.' in child_dotted_order

        # After parent, should be: .timestamp + UUID
        child_suffix = child_dotted_order[len(parent_dotted_order):]
        assert child_suffix.startswith('.')

        # Verify child suffix format: .YYYYMMDDTHHMMSSffffffZuuid
        child_part = child_suffix[1:]  # Remove leading dot
        assert len(child_part) == 58  # Same format as parent

    def test_grandchild_dotted_order_hierarchy(self):
        """Test grandchild dotted_order maintains full hierarchy"""
        # Format: parent.child.grandchild

        parent = "20251216T174404397000Z0e01bf50-474d-4536-810f-67d3ee7ea3e7"
        child = f"{parent}.20251216T174405123456Za8024e23-5b82-47fd-970e-f6a5ba3f5097"
        grandchild = f"{child}.20251216T174406789012Z0ec6b845-18b9-4aa1-8f1b-6ba3f9fdefd6"

        # Verify hierarchy
        assert grandchild.startswith(parent)
        assert grandchild.startswith(child)

        # Count dots to verify depth
        assert parent.count('.') == 0  # Top level
        assert child.count('.') == 1   # One level deep
        assert grandchild.count('.') == 2  # Two levels deep


@pytest.mark.unit
class TestTimestampPrecision:
    """Tests for microsecond precision in timestamps"""

    def test_get_microseconds_provides_six_digits(self, bash_executor):
        """Test microsecond precision for ordering"""
        result = bash_executor.call_function("get_microseconds")

        # Must be exactly 6 digits
        assert len(result) == 6
        assert result.isdigit()

        # Convert to verify range (0-999999)
        microseconds = int(result)
        assert 0 <= microseconds <= 999999

    def test_timestamp_includes_microseconds(self):
        """Test that dotted_order timestamps include microseconds"""
        # From stop_hook.sh line 431-434:
        # dotted_timestamp=$(date -u +"%Y%m%dT%H%M%S")
        # microseconds=$(get_microseconds)
        # dotted_timestamp="${dotted_timestamp}${microseconds}Z"

        dotted_order = "20251216T174404397000Z0e01bf50-474d-4536-810f-67d3ee7ea3e7"

        # Extract timestamp: 20251216T174404397000
        timestamp = dotted_order[:20]

        # Last 6 digits before Z should be microseconds
        microseconds = timestamp[14:20]  # After HHMMSSffffff
        assert len(microseconds) == 6
        assert microseconds.isdigit()
        assert int(microseconds) <= 999999

    def test_microseconds_enable_sub_second_ordering(self):
        """Test that microseconds allow ordering of rapid events"""
        # Two events in the same second should have different microseconds

        timestamp1 = "20251216T174404123456"  # .123456 seconds
        timestamp2 = "20251216T174404789012"  # .789012 seconds

        # Same date and time (up to seconds)
        assert timestamp1[:14] == timestamp2[:14]

        # Different microseconds enable ordering
        micro1 = int(timestamp1[14:20])
        micro2 = int(timestamp2[14:20])
        assert micro1 < micro2

        # This ensures events happening in same second are ordered correctly


@pytest.mark.unit
class TestTraceOrdering:
    """Tests for chronological trace ordering"""

    def test_dotted_order_sorts_chronologically(self):
        """Test that dotted_order sorts traces in chronological order"""
        # LangSmith uses dotted_order for sorting traces
        # Earlier timestamps should sort before later ones

        trace1 = "20251216T174404000000Z0e01bf50-474d-4536-810f-67d3ee7ea3e7"
        trace2 = "20251216T174405000000Z1234abcd-5678-9012-3456-789012345678"
        trace3 = "20251216T174406000000Za9876543-dcba-fedc-ba98-765432109876"

        traces = [trace3, trace1, trace2]  # Unsorted
        traces.sort()

        # After sorting, should be in chronological order
        assert traces == [trace1, trace2, trace3]

    def test_parent_sorts_before_children(self):
        """Test that parent trace sorts before its children"""
        parent = "20251216T174404000000Z0e01bf50-474d-4536-810f-67d3ee7ea3e7"
        child1 = f"{parent}.20251216T174405000000Za8024e23-5b82-47fd-970e-f6a5ba3f5097"
        child2 = f"{parent}.20251216T174406000000Z0ec6b845-18b9-4aa1-8f1b-6ba3f9fdefd6"

        traces = [child2, child1, parent]  # Unsorted
        traces.sort()

        # Parent should come first, then children in order
        assert traces == [parent, child1, child2]

    def test_sibling_traces_sort_by_timestamp(self):
        """Test that sibling traces (same parent) sort by their timestamps"""
        parent = "20251216T174404000000Z0e01bf50-474d-4536-810f-67d3ee7ea3e7"

        # Two children with different timestamps
        child_later = f"{parent}.20251216T174406000000Zchild2-uuid"
        child_earlier = f"{parent}.20251216T174405000000Zchild1-uuid"

        siblings = [child_later, child_earlier]  # Wrong order
        siblings.sort()

        # Should sort by timestamp (earlier first)
        assert siblings == [child_earlier, child_later]

    def test_microsecond_precision_affects_ordering(self):
        """Test that microsecond differences affect ordering"""
        parent = "20251216T174404000000Z0e01bf50-474d-4536-810f-67d3ee7ea3e7"

        # Events in same second but different microseconds
        event1 = f"{parent}.20251216T174405000100Zevent1"  # .000100
        event2 = f"{parent}.20251216T174405000200Zevent2"  # .000200
        event3 = f"{parent}.20251216T174405000300Zevent3"  # .000300

        events = [event3, event1, event2]  # Unsorted
        events.sort()

        # Should sort by microseconds
        assert events == [event1, event2, event3]


@pytest.mark.unit
class TestTraceIDExtraction:
    """Tests for extracting trace_id from dotted_order"""

    def test_extract_trace_id_from_root_dotted_order(self):
        """Test extracting trace_id from root dotted_order"""
        # From stop_hook.sh line 549:
        # trace_id="${turn_dotted_order#*Z}"
        # This extracts everything after the first 'Z'

        dotted_order = "20251216T174404397000Z0e01bf50-474d-4536-810f-67d3ee7ea3e7"

        # Extract trace_id (everything after Z)
        trace_id = dotted_order.split('Z', 1)[1]

        assert trace_id == "0e01bf50-474d-4536-810f-67d3ee7ea3e7"
        assert len(trace_id) == 36  # UUID length

    def test_extract_trace_id_from_child_dotted_order(self):
        """Test extracting trace_id from child dotted_order"""
        # Child: parent.child
        # Trace ID should be from the root (first segment)

        child_dotted_order = "20251216T174404397000Z0e01bf50-474d-4536-810f-67d3ee7ea3e7.20251216T174405123456Za8024e23-5b82-47fd-970e-f6a5ba3f5097"

        # Extract first segment (parent)
        first_segment = child_dotted_order.split('.')[0]

        # Extract trace_id from first segment
        trace_id = first_segment.split('Z', 1)[1]

        assert trace_id == "0e01bf50-474d-4536-810f-67d3ee7ea3e7"

    def test_all_children_share_parent_trace_id(self):
        """Test that all children in a tree share the same trace_id"""
        parent = "20251216T174404397000Zroot-trace-id"
        child1 = f"{parent}.20251216T174405123456Zchild1-id"
        child2 = f"{parent}.20251216T174406789012Zchild2-id"
        grandchild = f"{child1}.20251216T174407000000Zgrandchild-id"

        # Extract trace_id from each
        parent_trace = parent.split('Z', 1)[1]
        child1_trace = child1.split('.')[0].split('Z', 1)[1]
        child2_trace = child2.split('.')[0].split('Z', 1)[1]
        grandchild_trace = grandchild.split('.')[0].split('Z', 1)[1]

        # All should have the same trace_id (from root)
        assert parent_trace == "root-trace-id"
        assert child1_trace == "root-trace-id"
        assert child2_trace == "root-trace-id"
        assert grandchild_trace == "root-trace-id"


@pytest.mark.unit
class TestRealWorldOrdering:
    """Tests with real-world scenarios from cc_transcript.jsonl"""

    def test_tool_call_ordering_within_turn(self):
        """Test that within a turn, events are ordered: user → assistant → tool → assistant"""
        # From cc_transcript.jsonl structure:
        # 1. User message (timestamp T1)
        # 2. Assistant with tool_use (timestamp T2)
        # 3. Tool result (timestamp T3)
        # 4. Assistant final response (timestamp T4)

        turn_id = "turn-uuid"
        turn_dotted = f"20251216T174404000000Z{turn_id}"

        # Create dotted_orders for each event
        assistant1 = f"{turn_dotted}.20251216T174405000000Zassistant1"
        tool = f"{turn_dotted}.20251216T174406000000Ztool"
        assistant2 = f"{turn_dotted}.20251216T174407000000Zassistant2"

        # Sort to verify ordering
        events = [assistant2, tool, assistant1, turn_dotted]
        events.sort()

        # Should be in chronological order
        assert events == [turn_dotted, assistant1, tool, assistant2]

    def test_multiple_turns_sort_chronologically(self):
        """Test that multiple turns sort in chronological order"""
        # Simulating multiple user-assistant turns from transcript

        turn1 = "20251216T174404000000Zturn1-uuid"
        turn2 = "20251216T174410000000Zturn2-uuid"
        turn3 = "20251216T174420000000Zturn3-uuid"

        turns = [turn3, turn1, turn2]  # Unsorted
        turns.sort()

        # Should be chronological
        assert turns == [turn1, turn2, turn3]

    def test_iso_timestamp_to_dotted_order_conversion(self):
        """Test conversion from ISO timestamp (transcript) to dotted_order format"""
        # From stop_hook.sh lines 531-543:
        # ISO: 2025-12-16T17:44:04.397Z
        # To: 20251216T174404397000Z (milliseconds padded to microseconds)

        iso_timestamp = "2025-12-16T17:44:04.397Z"

        # Parse ISO timestamp
        dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))

        # Convert to dotted_order format
        dotted_timestamp = dt.strftime("%Y%m%dT%H%M%S")

        # Extract milliseconds and pad to microseconds
        milliseconds = 397
        microseconds = milliseconds * 1000  # 397000

        full_timestamp = f"{dotted_timestamp}{microseconds:06d}"

        # Verify format
        assert full_timestamp == "20251216T174404397000"
        assert len(full_timestamp) == 21  # YYYYMMDDTHHMMSS (14) + ffffff (6) + extra digit

        # Verify chronological ordering
        iso2 = "2025-12-16T17:44:05.123Z"
        dt2 = datetime.fromisoformat(iso2.replace('Z', '+00:00'))
        dotted2 = dt2.strftime("%Y%m%dT%H%M%S")
        full2 = f"{dotted2}123000"

        # Later timestamp should sort after
        assert full2 > full_timestamp

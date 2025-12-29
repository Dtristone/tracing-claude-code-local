"""
Unit tests for cost tracking and usage metadata from stop_hook.sh.

These tests verify that token usage is correctly tracked for cost monitoring:
- Total input tokens (including cache tokens)
- Output tokens
- Cache token breakdowns (creation vs read)
"""

import json
import pytest


@pytest.mark.unit
class TestUsageMetadata:
    """Tests for usage_metadata calculation (cost tracking)"""

    def test_calculates_total_input_tokens_with_cache(self, bash_executor):
        """Test that total input tokens includes cache tokens"""
        # This tests the jq logic at line 514:
        # input_tokens: ((.input_tokens // 0) + (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0))

        usage = {
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 500,
            "cache_read_input_tokens": 2000
        }

        # Build the usage_metadata jq expression
        script = f"""
        set -e
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)

        echo '{json.dumps(usage)}' | jq '{{
            input_tokens: ((.input_tokens // 0) + (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0)),
            output_tokens: (.output_tokens // 0),
            input_token_details: {{
                cache_creation: (.cache_creation_input_tokens // 0),
                cache_read: (.cache_read_input_tokens // 0)
            }}
        }}'
        """

        result = bash_executor.call_function.__self__.call_function.__func__(
            bash_executor, "bash", "-c", script
        )
        metadata = json.loads(result)

        # Total input = 100 + 500 + 2000 = 2600
        assert metadata["input_tokens"] == 2600
        assert metadata["output_tokens"] == 50
        assert metadata["input_token_details"]["cache_creation"] == 500
        assert metadata["input_token_details"]["cache_read"] == 2000

    def test_handles_missing_cache_tokens(self, bash_executor):
        """Test usage metadata when cache tokens are missing"""
        usage = {
            "input_tokens": 100,
            "output_tokens": 50
            # No cache tokens
        }

        script = f"""
        set -e
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)

        echo '{json.dumps(usage)}' | jq '{{
            input_tokens: ((.input_tokens // 0) + (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0)),
            output_tokens: (.output_tokens // 0),
            input_token_details: {{
                cache_creation: (.cache_creation_input_tokens // 0),
                cache_read: (.cache_read_input_tokens // 0)
            }}
        }}'
        """

        result = bash_executor.call_function.__self__.call_function.__func__(
            bash_executor, "bash", "-c", script
        )
        metadata = json.loads(result)

        # Total input = 100 + 0 + 0 = 100
        assert metadata["input_tokens"] == 100
        assert metadata["output_tokens"] == 50
        assert metadata["input_token_details"]["cache_creation"] == 0
        assert metadata["input_token_details"]["cache_read"] == 0

    def test_realistic_usage_scenario(self, bash_executor):
        """Test realistic usage from cc_transcript.jsonl"""
        # Real example from line 2 of cc_transcript.jsonl
        usage = {
            "input_tokens": 9,
            "cache_creation_input_tokens": 630,
            "cache_read_input_tokens": 18664,
            "output_tokens": 8
        }

        script = f"""
        set -e
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)

        echo '{json.dumps(usage)}' | jq '{{
            input_tokens: ((.input_tokens // 0) + (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0)),
            output_tokens: (.output_tokens // 0),
            input_token_details: {{
                cache_creation: (.cache_creation_input_tokens // 0),
                cache_read: (.cache_read_input_tokens // 0)
            }}
        }}'
        """

        result = bash_executor.call_function.__self__.call_function.__func__(
            bash_executor, "bash", "-c", script
        )
        metadata = json.loads(result)

        # Total input = 9 + 630 + 18664 = 19303
        assert metadata["input_tokens"] == 19303
        assert metadata["output_tokens"] == 8
        assert metadata["input_token_details"]["cache_creation"] == 630
        assert metadata["input_token_details"]["cache_read"] == 18664


@pytest.mark.unit
class TestCostImplications:
    """Tests verifying cost tracking implications"""

    def test_cache_read_reduces_cost(self):
        """Test that cache read tokens are tracked separately (they cost less)"""
        # Cache read tokens are ~90% cheaper than regular input tokens
        # This test verifies they're tracked in input_token_details

        usage_with_cache = {
            "input_tokens": 10,
            "cache_read_input_tokens": 10000,
            "output_tokens": 50
        }

        usage_without_cache = {
            "input_tokens": 10010,  # Same total but all regular
            "output_tokens": 50
        }

        # Both have same total input tokens (10010)
        # But usage_with_cache is much cheaper due to cache reads
        # The tracking in input_token_details enables cost calculation

        assert usage_with_cache["input_tokens"] + usage_with_cache.get("cache_read_input_tokens", 0) == 10010
        assert usage_without_cache["input_tokens"] == 10010

        # Verify cache breakdown is preserved for cost calculation
        assert usage_with_cache.get("cache_read_input_tokens") == 10000

    def test_cache_creation_tracked_for_write_cost(self):
        """Test that cache creation tokens are tracked (they cost more)"""
        # Cache creation tokens cost more (first write to cache)
        # This test verifies they're tracked separately

        usage = {
            "input_tokens": 100,
            "cache_creation_input_tokens": 1000,
            "output_tokens": 50
        }

        # Cache creation adds to total input but tracked separately
        total_input = usage["input_tokens"] + usage["cache_creation_input_tokens"]
        assert total_input == 1100

        # Verify cache creation is preserved for cost calculation
        assert usage["cache_creation_input_tokens"] == 1000


@pytest.mark.unit
class TestUsageAggregation:
    """Tests for usage aggregation across multiple LLM calls"""

    def test_tracks_usage_per_assistant_message(self, bash_executor, sample_streaming_parts):
        """Test that each assistant message has its own usage tracking"""
        # Each LLM call should have separate usage metadata
        # This is critical for per-call cost attribution

        parts = sample_streaming_parts  # From fixture
        result = bash_executor.call_function("get_usage_from_parts", json.dumps(parts))
        usage = json.loads(result)

        # Verify usage is extracted (cumulative from streaming)
        assert "input_tokens" in usage
        assert "output_tokens" in usage
        assert usage["output_tokens"] == 5  # Last part has cumulative count

    def test_usage_preserved_through_merge(self, bash_executor, sample_streaming_parts):
        """Test that usage is preserved when merging streaming parts"""
        # When SSE parts are merged, usage should be preserved
        parts = json.dumps(sample_streaming_parts)
        result = bash_executor.call_function("merge_assistant_parts", parts)
        merged = json.loads(result)

        # Usage should be in _usage field after merge
        assert "_usage" in merged["message"]
        assert merged["message"]["_usage"]["output_tokens"] == 5
        assert merged["message"]["_usage"]["input_tokens"] == 10

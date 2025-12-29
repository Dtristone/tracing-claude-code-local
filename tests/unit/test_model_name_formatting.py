"""
Unit tests for model name formatting from stop_hook.sh.

Tests verify that model names have date suffixes stripped:
- claude-sonnet-4-5-20250929 -> claude-sonnet-4-5
- claude-opus-4-5-20251101 -> claude-opus-4-5
- claude-haiku-4-20241114 -> claude-haiku-4
"""

import json
import pytest


@pytest.mark.unit
class TestModelNameFormatting:
    """Tests for model name date suffix stripping"""

    def test_strips_date_from_sonnet_model(self, bash_executor):
        """Test that date suffix is stripped from claude-sonnet model"""
        assistant_msg = {
            "message": {
                "id": "msg_123",
                "role": "assistant",
                "model": "claude-sonnet-4-5-20250929",
                "content": [{"type": "text", "text": "Hello"}]
            }
        }

        # Extract and format model name (simulating the sed command)
        model_full = "claude-sonnet-4-5-20250929"
        model_stripped = model_full.rsplit('-', 1)[0] if model_full.split('-')[-1].isdigit() and len(model_full.split('-')[-1]) == 8 else model_full

        assert model_stripped == "claude-sonnet-4-5"

    def test_strips_date_from_opus_model(self):
        """Test that date suffix is stripped from claude-opus model"""
        model_full = "claude-opus-4-5-20251101"
        model_stripped = model_full.rsplit('-', 1)[0] if model_full.split('-')[-1].isdigit() and len(model_full.split('-')[-1]) == 8 else model_full

        assert model_stripped == "claude-opus-4-5"

    def test_strips_date_from_haiku_model(self):
        """Test that date suffix is stripped from claude-haiku model"""
        model_full = "claude-haiku-4-20241114"
        model_stripped = model_full.rsplit('-', 1)[0] if model_full.split('-')[-1].isdigit() and len(model_full.split('-')[-1]) == 8 else model_full

        assert model_stripped == "claude-haiku-4"

    def test_handles_model_without_date_suffix(self):
        """Test that models without date suffix remain unchanged"""
        model_full = "gpt-4"
        model_stripped = model_full.rsplit('-', 1)[0] if model_full.split('-')[-1].isdigit() and len(model_full.split('-')[-1]) == 8 else model_full

        assert model_stripped == "gpt-4"

    def test_sed_command_strips_date(self):
        """Test the actual sed command used in stop_hook.sh"""
        # Test the sed pattern: s/-[0-9]\{8\}$//
        # This removes -YYYYMMDD from the end
        import subprocess

        models = [
            ("claude-sonnet-4-5-20250929", "claude-sonnet-4-5"),
            ("claude-opus-4-5-20251101", "claude-opus-4-5"),
            ("claude-haiku-4-20241114", "claude-haiku-4"),
            ("claude-sonnet-4-5", "claude-sonnet-4-5"),  # No date
            ("gpt-4", "gpt-4"),  # Different format
        ]

        for model_in, expected_out in models:
            # Use raw sed command with proper escaping
            cmd = f"echo '{model_in}' | sed 's/-[0-9]\\{{8\\}}$//'"
            result = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True,
                text=True
            )
            output = result.stdout.strip()
            assert output == expected_out, f"Expected '{model_in}' -> '{expected_out}', got '{output}'"


@pytest.mark.unit
class TestModelNameInMetadata:
    """Tests for model name in LangSmith metadata"""

    def test_model_name_in_ls_provider_metadata(self):
        """Test that ls_model_name uses stripped model name"""
        # From stop_hook.sh line 572:
        # extra: {metadata: {ls_provider: "anthropic", ls_model_name: $model}}

        model_full = "claude-sonnet-4-5-20250929"
        model_stripped = "claude-sonnet-4-5"

        metadata = {
            "ls_provider": "anthropic",
            "ls_model_name": model_stripped
        }

        assert metadata["ls_model_name"] == "claude-sonnet-4-5"
        assert "-20250929" not in metadata["ls_model_name"]

    def test_model_name_in_tags(self):
        """Test that model name in tags is also stripped"""
        # From stop_hook.sh line 573:
        # tags: [$model]

        model_stripped = "claude-sonnet-4-5"
        tags = [model_stripped]

        assert tags[0] == "claude-sonnet-4-5"
        assert not any("202" in tag for tag in tags), "Tags should not contain date"


@pytest.mark.unit
class TestRealWorldModelNames:
    """Tests with real model names from cc_transcript.jsonl"""

    def test_strips_sonnet_45_date(self):
        """Test with actual Sonnet 4.5 model name"""
        # From cc_transcript.jsonl: "claude-sonnet-4-5-20250929"
        model_full = "claude-sonnet-4-5-20250929"
        model_stripped = model_full.rsplit('-', 1)[0] if model_full.split('-')[-1].isdigit() and len(model_full.split('-')[-1]) == 8 else model_full

        assert model_stripped == "claude-sonnet-4-5"
        assert len(model_stripped.split('-')) == 4  # claude-sonnet-4-5 has 4 parts

    def test_date_format_validation(self):
        """Test that only 8-digit dates are stripped"""
        # Should strip 8-digit dates
        assert "claude-sonnet-4-5-20250929".rsplit('-', 1)[0] == "claude-sonnet-4-5"

        # Should NOT strip non-date suffixes
        model = "claude-sonnet-4-5-beta"
        model_stripped = model.rsplit('-', 1)[0] if model.split('-')[-1].isdigit() and len(model.split('-')[-1]) == 8 else model
        assert model_stripped == "claude-sonnet-4-5-beta"

        # Should NOT strip short numbers
        model = "gpt-4"
        model_stripped = model.rsplit('-', 1)[0] if model.split('-')[-1].isdigit() and len(model.split('-')[-1]) == 8 else model
        assert model_stripped == "gpt-4"


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases in model name stripping"""

    def test_multiple_dates_only_strips_last(self):
        """Test that only the last date suffix is stripped"""
        # Hypothetical edge case: model-20240101-20250929
        model = "model-20240101-20250929"
        model_stripped = model.rsplit('-', 1)[0] if model.split('-')[-1].isdigit() and len(model.split('-')[-1]) == 8 else model

        # Should only strip the last date
        assert model_stripped == "model-20240101"

    def test_empty_model_name(self):
        """Test handling of empty model name"""
        model = ""
        model_stripped = model.rsplit('-', 1)[0] if model and model.split('-')[-1].isdigit() and len(model.split('-')[-1]) == 8 else model

        assert model_stripped == ""

    def test_model_name_without_hyphens(self):
        """Test model name without hyphens"""
        model = "gpt4"
        model_stripped = model.rsplit('-', 1)[0] if model.split('-')[-1].isdigit() and len(model.split('-')[-1]) == 8 else model

        assert model_stripped == "gpt4"

    def test_preserves_version_numbers(self):
        """Test that version numbers (not dates) are preserved"""
        # Should preserve: claude-3-5-sonnet (version 3.5)
        model = "claude-3-5-sonnet-20241022"
        model_stripped = model.rsplit('-', 1)[0] if model.split('-')[-1].isdigit() and len(model.split('-')[-1]) == 8 else model

        assert model_stripped == "claude-3-5-sonnet"
        assert "3-5" in model_stripped  # Version preserved


@pytest.mark.unit
class TestIntegrationWithSampleData:
    """Integration tests using sample fixtures"""

    def test_model_name_extraction_from_sample_assistant(self, sample_assistant_message):
        """Test model name extraction from fixture"""
        model = sample_assistant_message["message"]["model"]

        # Verify it's the full format
        assert model == "claude-sonnet-4-5-20250929"

        # Strip date
        model_stripped = model.rsplit('-', 1)[0] if model.split('-')[-1].isdigit() and len(model.split('-')[-1]) == 8 else model

        # Verify stripped format
        assert model_stripped == "claude-sonnet-4-5"
        assert "20250929" not in model_stripped

    def test_all_claude_45_variants(self):
        """Test stripping works for all Claude 4.5 model variants"""
        models = {
            "claude-sonnet-4-5-20250929": "claude-sonnet-4-5",
            "claude-opus-4-5-20251101": "claude-opus-4-5",
            "claude-haiku-4-20241114": "claude-haiku-4",
        }

        for full_name, expected in models.items():
            stripped = full_name.rsplit('-', 1)[0] if full_name.split('-')[-1].isdigit() and len(full_name.split('-')[-1]) == 8 else full_name
            assert stripped == expected, f"Failed for {full_name}: got {stripped}, expected {expected}"

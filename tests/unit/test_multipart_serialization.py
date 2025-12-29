"""
Unit tests for multipart serialization in stop_hook.sh.

Tests:
- serialize_for_multipart() - Serialize run data for multipart upload
- File creation with Content-Length headers
- Inputs/outputs extraction and serialization
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.mark.unit
class TestSerializeForMultipart:
    """Tests for serialize_for_multipart() function"""

    def test_function_exists(self, bash_executor):
        """Test that serialize_for_multipart function exists"""
        source = bash_executor.get_function_source("serialize_for_multipart")
        assert "serialize_for_multipart" in source

    def test_accepts_operation_parameter(self, bash_executor):
        """Test that function accepts operation parameter (post/patch)"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        assert "operation" in source

    def test_accepts_run_json_parameter(self, bash_executor):
        """Test that function accepts run_json parameter"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        assert "run_json" in source

    def test_accepts_temp_dir_parameter(self, bash_executor):
        """Test that function accepts temp_dir parameter"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        assert "temp_dir" in source

    def test_extracts_run_id(self, bash_executor):
        """Test that run_id is extracted from run_json"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        assert "run_id" in source
        assert ".id" in source  # jq extraction

    def test_extracts_inputs(self, bash_executor):
        """Test that inputs are extracted from run_json"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        assert "inputs" in source
        assert ".inputs" in source  # jq extraction

    def test_extracts_outputs(self, bash_executor):
        """Test that outputs are extracted from run_json"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        assert "outputs" in source
        assert ".outputs" in source  # jq extraction

    def test_creates_main_data_file(self, bash_executor):
        """Test that main run data file is created"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        # Should create main file
        assert "main_file" in source
        assert "_main.json" in source

    def test_uses_get_file_size(self, bash_executor):
        """Test that get_file_size is used for Content-Length"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        assert "get_file_size" in source

    def test_outputs_curl_f_arguments(self, bash_executor):
        """Test that function outputs curl -F arguments"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        # Should output -F flag
        assert '"-F"' in source or "echo \"-F\"" in source

    def test_includes_content_length_header(self, bash_executor):
        """Test that Content-Length header is included"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        assert "Content-Length" in source


@pytest.mark.unit
class TestMultipartFileFormat:
    """Tests for multipart file format and naming"""

    def test_main_file_naming_convention(self, bash_executor):
        """Test main file naming: {operation}_{run_id}_main.json"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        # Should include operation and run_id in filename
        assert "${operation}" in source or "$operation" in source
        assert "${run_id}" in source or "$run_id" in source
        assert "_main.json" in source

    def test_inputs_file_naming_convention(self, bash_executor):
        """Test inputs file naming: {operation}_{run_id}_inputs.json"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        assert "_inputs.json" in source

    def test_outputs_file_naming_convention(self, bash_executor):
        """Test outputs file naming: {operation}_{run_id}_outputs.json"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        assert "_outputs.json" in source

    def test_multipart_part_naming(self, bash_executor):
        """Test multipart part naming: {operation}.{run_id}"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        # Part name format: post.uuid or patch.uuid
        assert "${operation}.${run_id}" in source or "$operation.$run_id" in source


@pytest.mark.unit
class TestMultipartDataSeparation:
    """Tests for separating main data from inputs/outputs"""

    def test_main_data_excludes_inputs(self, bash_executor):
        """Test that main_data excludes inputs field"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        # Should use jq to delete inputs
        assert "del(.inputs" in source

    def test_main_data_excludes_outputs(self, bash_executor):
        """Test that main_data excludes outputs field"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        # Should use jq to delete outputs
        assert "del(" in source
        assert ".outputs" in source

    def test_inputs_only_created_if_present(self, bash_executor):
        """Test that inputs file is only created if inputs exist"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        # Should check if inputs is not null/empty
        assert '"null"' in source or "null" in source
        assert "-n" in source  # Test for non-empty

    def test_outputs_only_created_if_present(self, bash_executor):
        """Test that outputs file is only created if outputs exist"""
        source = bash_executor.get_function_source("serialize_for_multipart")

        # Should check if outputs is not null/empty
        assert "outputs" in source


@pytest.mark.unit
class TestSerializeForMultipartIntegration:
    """Integration tests for serialize_for_multipart with actual data"""

    def test_serialize_post_run(self, tmp_path):
        """Test serializing a POST run"""
        run_data = {
            "id": "test-run-123",
            "name": "Test Run",
            "run_type": "llm",
            "inputs": {"messages": [{"role": "user", "content": "Hello"}]},
            "start_time": "2025-01-01T00:00:00Z"
        }

        script = f"""
        set -e
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)

        temp_dir="{tmp_path}"
        run_json='{json.dumps(run_data)}'

        serialize_for_multipart "post" "$run_json" "$temp_dir"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        # Check output contains -F arguments
        output = result.stdout
        assert "-F" in output
        assert "post.test-run-123" in output

        # Check that main file was created
        main_file = tmp_path / "post_test-run-123_main.json"
        assert main_file.exists()

        # Check that inputs file was created
        inputs_file = tmp_path / "post_test-run-123_inputs.json"
        assert inputs_file.exists()

    def test_serialize_patch_run(self, tmp_path):
        """Test serializing a PATCH run"""
        run_data = {
            "id": "test-run-456",
            "outputs": {"messages": [{"role": "assistant", "content": "Hi"}]},
            "end_time": "2025-01-01T00:00:01Z"
        }

        script = f"""
        set -e
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)

        temp_dir="{tmp_path}"
        run_json='{json.dumps(run_data)}'

        serialize_for_multipart "patch" "$run_json" "$temp_dir"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        output = result.stdout
        assert "-F" in output
        assert "patch.test-run-456" in output

        # Check that outputs file was created
        outputs_file = tmp_path / "patch_test-run-456_outputs.json"
        assert outputs_file.exists()

    def test_serialize_run_without_inputs(self, tmp_path):
        """Test serializing a run without inputs"""
        run_data = {
            "id": "test-run-789",
            "name": "Test Run",
            "run_type": "llm",
            "start_time": "2025-01-01T00:00:00Z"
        }

        script = f"""
        set -e
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)

        temp_dir="{tmp_path}"
        run_json='{json.dumps(run_data)}'

        serialize_for_multipart "post" "$run_json" "$temp_dir"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        # Main file should exist
        main_file = tmp_path / "post_test-run-789_main.json"
        assert main_file.exists()

        # Inputs file should NOT exist (no inputs)
        inputs_file = tmp_path / "post_test-run-789_inputs.json"
        assert not inputs_file.exists()

    def test_main_file_excludes_inputs_outputs(self, tmp_path):
        """Test that main file doesn't contain inputs/outputs"""
        run_data = {
            "id": "test-run-abc",
            "name": "Test Run",
            "run_type": "llm",
            "inputs": {"messages": []},
            "outputs": {"messages": []},
            "start_time": "2025-01-01T00:00:00Z"
        }

        script = f"""
        set -e
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)

        temp_dir="{tmp_path}"
        run_json='{json.dumps(run_data)}'

        serialize_for_multipart "post" "$run_json" "$temp_dir"
        """

        subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        # Read main file and verify it doesn't have inputs/outputs
        main_file = tmp_path / "post_test-run-abc_main.json"
        main_content = json.loads(main_file.read_text())

        assert "inputs" not in main_content
        assert "outputs" not in main_content
        assert main_content["id"] == "test-run-abc"
        assert main_content["name"] == "Test Run"

    def test_content_length_header_is_accurate(self, tmp_path):
        """Test that Content-Length header matches actual file size"""
        run_data = {
            "id": "test-run-size",
            "name": "Size Test",
            "run_type": "llm",
            "inputs": {"data": "test" * 100},  # Some data
            "start_time": "2025-01-01T00:00:00Z"
        }

        script = f"""
        set -e
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)

        temp_dir="{tmp_path}"
        run_json='{json.dumps(run_data)}'

        serialize_for_multipart "post" "$run_json" "$temp_dir"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        output = result.stdout

        # Extract Content-Length from output
        for line in output.split("\n"):
            if "Content-Length:" in line:
                # Parse the size
                size_str = line.split("Content-Length:")[1].strip()
                claimed_size = int(size_str)

                # Find the corresponding file and check its actual size
                if "_main.json" in line:
                    actual_size = os.path.getsize(tmp_path / "post_test-run-size_main.json")
                    assert claimed_size == actual_size
                elif "_inputs.json" in line:
                    actual_size = os.path.getsize(tmp_path / "post_test-run-size_inputs.json")
                    assert claimed_size == actual_size


@pytest.mark.unit
class TestMultipartCurlFormat:
    """Tests for curl -F argument format"""

    def test_curl_f_format_with_file_reference(self, tmp_path):
        """Test that -F uses file reference with <"""
        run_data = {
            "id": "test-curl-format",
            "name": "Test",
            "run_type": "llm",
            "start_time": "2025-01-01T00:00:00Z"
        }

        script = f"""
        set -e
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)

        temp_dir="{tmp_path}"
        run_json='{json.dumps(run_data)}'

        serialize_for_multipart "post" "$run_json" "$temp_dir"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        output = result.stdout

        # Should use < for file reference
        assert "<" in output or "@" in output  # curl uses < or @ for files

    def test_curl_f_includes_content_type(self, tmp_path):
        """Test that -F includes application/json content type"""
        run_data = {
            "id": "test-content-type",
            "name": "Test",
            "run_type": "llm",
            "start_time": "2025-01-01T00:00:00Z"
        }

        script = f"""
        set -e
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)

        temp_dir="{tmp_path}"
        run_json='{json.dumps(run_data)}'

        serialize_for_multipart "post" "$run_json" "$temp_dir"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        output = result.stdout

        # Should include content type
        assert "application/json" in output

    def test_inputs_part_naming(self, tmp_path):
        """Test that inputs part is named correctly: {operation}.{run_id}.inputs"""
        run_data = {
            "id": "test-inputs-name",
            "inputs": {"test": "data"},
            "start_time": "2025-01-01T00:00:00Z"
        }

        script = f"""
        set -e
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)

        temp_dir="{tmp_path}"
        run_json='{json.dumps(run_data)}'

        serialize_for_multipart "post" "$run_json" "$temp_dir"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        output = result.stdout

        # Should have inputs part named post.{id}.inputs
        assert "post.test-inputs-name.inputs" in output

    def test_outputs_part_naming(self, tmp_path):
        """Test that outputs part is named correctly: {operation}.{run_id}.outputs"""
        run_data = {
            "id": "test-outputs-name",
            "outputs": {"test": "data"},
            "end_time": "2025-01-01T00:00:00Z"
        }

        script = f"""
        set -e
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)

        temp_dir="{tmp_path}"
        run_json='{json.dumps(run_data)}'

        serialize_for_multipart "patch" "$run_json" "$temp_dir"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        output = result.stdout

        # Should have outputs part named patch.{id}.outputs
        assert "patch.test-outputs-name.outputs" in output

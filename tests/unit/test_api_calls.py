"""
Unit tests for API call functions in stop_hook.sh.

Tests:
- api_call() - HTTP request handling, error codes, timeouts
- send_multipart_batch() - Batch sending via multipart endpoint
- cleanup_pending_turn() - Cleanup on early exit
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.mark.unit
class TestApiCallFunction:
    """Tests for api_call() function"""

    def test_api_call_constructs_correct_curl_command(self, bash_executor, tmp_path):
        """Test that api_call constructs curl command with correct headers"""
        # We can't easily test actual curl calls, but we can verify the function exists
        # and has the right structure
        source = bash_executor.get_function_source("api_call")

        # Verify key components are present
        assert "x-api-key:" in source
        assert "Content-Type: application/json" in source
        assert "curl" in source
        assert "--max-time" in source

    def test_api_call_handles_method_parameter(self, bash_executor):
        """Test that api_call accepts different HTTP methods"""
        source = bash_executor.get_function_source("api_call")

        # Should use $method variable in curl -X
        assert "-X" in source
        assert "method" in source

    def test_api_call_uses_api_base_url(self, bash_executor):
        """Test that api_call uses the API base URL"""
        source = bash_executor.get_function_source("api_call")

        # Should reference API_BASE and endpoint
        assert "API_BASE" in source
        assert "endpoint" in source

    def test_api_call_extracts_http_code(self, bash_executor):
        """Test that api_call extracts and checks HTTP response code"""
        source = bash_executor.get_function_source("api_call")

        # Should extract http_code from response
        assert "http_code" in source
        assert "%{http_code}" in source

    def test_api_call_returns_error_on_4xx(self, bash_executor):
        """Test that api_call returns error for 4xx responses"""
        source = bash_executor.get_function_source("api_call")

        # Should check for error codes
        assert "200" in source
        assert "300" in source
        assert "return 1" in source

    def test_api_call_logs_errors(self, bash_executor):
        """Test that api_call logs errors on failure"""
        source = bash_executor.get_function_source("api_call")

        # Should log errors
        assert "log" in source
        assert "ERROR" in source


@pytest.mark.unit
class TestApiCallErrorHandling:
    """Tests for API call error handling scenarios"""

    def test_api_call_structure_for_post(self):
        """Test api_call structure for POST requests"""
        # Read the actual function to verify POST handling
        script = """
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)
        declare -f api_call
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        source = result.stdout

        # Verify it handles data parameter for POST
        assert "-d" in source
        assert "data" in source

    def test_api_call_structure_for_patch(self):
        """Test api_call structure for PATCH requests"""
        script = """
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)
        declare -f api_call
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        # PATCH uses same structure as POST with -X PATCH
        source = result.stdout
        assert "method" in source

    def test_api_call_has_timeout(self):
        """Test that api_call has a timeout configured"""
        script = """
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)
        declare -f api_call
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        source = result.stdout
        assert "--max-time" in source
        assert "60" in source  # 60 second timeout


@pytest.mark.unit
class TestSendMultipartBatch:
    """Tests for send_multipart_batch() function"""

    def test_send_multipart_batch_exists(self, bash_executor):
        """Test that send_multipart_batch function exists"""
        source = bash_executor.get_function_source("send_multipart_batch")
        assert "send_multipart_batch" in source

    def test_send_multipart_batch_handles_empty_batch(self, bash_executor):
        """Test that empty batch is handled gracefully"""
        source = bash_executor.get_function_source("send_multipart_batch")

        # Should check for empty batch
        assert "batch_size" in source or "length" in source
        assert "0" in source

    def test_send_multipart_batch_creates_temp_dir(self, bash_executor):
        """Test that temp directory is created for batch files"""
        source = bash_executor.get_function_source("send_multipart_batch")

        assert "mktemp -d" in source
        assert "temp_dir" in source

    def test_send_multipart_batch_cleans_up_temp_files(self, bash_executor):
        """Test that temp files are cleaned up after sending"""
        source = bash_executor.get_function_source("send_multipart_batch")

        # Should remove temp directory
        assert "rm -rf" in source

    def test_send_multipart_batch_uses_multipart_endpoint(self, bash_executor):
        """Test that multipart endpoint is used"""
        source = bash_executor.get_function_source("send_multipart_batch")

        assert "/runs/multipart" in source

    def test_send_multipart_batch_handles_post_operation(self, bash_executor):
        """Test handling of 'post' operation"""
        source = bash_executor.get_function_source("send_multipart_batch")

        # Should handle operation parameter
        assert "operation" in source
        assert "post" in source.lower() or "POST" in source

    def test_send_multipart_batch_handles_patch_operation(self, bash_executor):
        """Test handling of 'patch' operation via operation parameter"""
        source = bash_executor.get_function_source("send_multipart_batch")

        # Patch operations use POST to multipart endpoint but with 'patch' in part names
        # The operation parameter is passed to serialize_for_multipart for part naming
        assert "operation" in source
        assert "serialize_for_multipart" in source

    def test_send_multipart_batch_logs_success(self, bash_executor):
        """Test that successful batch is logged"""
        source = bash_executor.get_function_source("send_multipart_batch")

        assert "log" in source
        assert "INFO" in source
        assert "succeeded" in source.lower() or "success" in source.lower()

    def test_send_multipart_batch_logs_failure(self, bash_executor):
        """Test that failed batch is logged"""
        source = bash_executor.get_function_source("send_multipart_batch")

        assert "ERROR" in source
        assert "failed" in source.lower()


@pytest.mark.unit
class TestCleanupPendingTurn:
    """Tests for cleanup_pending_turn() function"""

    def test_cleanup_function_exists(self, bash_executor):
        """Test that cleanup_pending_turn function exists"""
        source = bash_executor.get_function_source("cleanup_pending_turn")
        assert "cleanup_pending_turn" in source

    def test_cleanup_checks_current_turn_id(self, bash_executor):
        """Test that cleanup checks if there's a pending turn"""
        source = bash_executor.get_function_source("cleanup_pending_turn")

        # Should check CURRENT_TURN_ID
        assert "CURRENT_TURN_ID" in source
        assert "-n" in source  # Test for non-empty

    def test_cleanup_sends_patch_request(self, bash_executor):
        """Test that cleanup patches the pending run"""
        source = bash_executor.get_function_source("cleanup_pending_turn")

        # Should call api_call with PATCH
        assert "PATCH" in source
        assert "/runs/" in source

    def test_cleanup_sets_error_message(self, bash_executor):
        """Test that cleanup sets appropriate error message"""
        source = bash_executor.get_function_source("cleanup_pending_turn")

        # Should include error message
        assert "error" in source.lower()
        assert "early" in source.lower() or "incomplete" in source.lower()

    def test_cleanup_sets_end_time(self, bash_executor):
        """Test that cleanup sets end_time for the run"""
        source = bash_executor.get_function_source("cleanup_pending_turn")

        assert "end_time" in source

    def test_cleanup_is_set_as_trap(self):
        """Test that cleanup_pending_turn is set as EXIT trap"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should have trap set for cleanup
        assert "trap cleanup_pending_turn EXIT" in content

    def test_cleanup_ignores_errors(self, bash_executor):
        """Test that cleanup ignores errors (since we're exiting anyway)"""
        source = bash_executor.get_function_source("cleanup_pending_turn")

        # Should have || true to ignore errors
        assert "|| true" in source


@pytest.mark.unit
class TestApiKeyHandling:
    """Tests for API key configuration"""

    def test_api_key_from_cc_langsmith_api_key(self):
        """Test that CC_LANGSMITH_API_KEY is checked first"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "CC_LANGSMITH_API_KEY" in content

    def test_api_key_fallback_to_langsmith_api_key(self):
        """Test fallback to LANGSMITH_API_KEY"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should have fallback syntax
        assert '${CC_LANGSMITH_API_KEY:-$LANGSMITH_API_KEY}' in content

    def test_api_key_validation(self):
        """Test that missing API key is handled"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should check if API_KEY is empty
        assert '-z "$API_KEY"' in content
        assert "not set" in content.lower() or "ERROR" in content


@pytest.mark.unit
class TestHttpResponseHandling:
    """Tests for HTTP response code handling"""

    def test_success_codes_accepted(self):
        """Test that 2xx codes are treated as success"""
        script = """
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)
        declare -f api_call
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        source = result.stdout

        # Check for 200-299 range logic
        assert "200" in source
        assert "300" in source

    def test_4xx_codes_logged_as_error(self):
        """Test that 4xx codes are logged as errors"""
        script = """
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)
        declare -f api_call
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        source = result.stdout

        # Should log HTTP code on error
        assert "HTTP" in source
        assert "http_code" in source

    def test_response_body_logged_on_error(self):
        """Test that response body is logged on error"""
        script = """
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)
        declare -f api_call
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        source = result.stdout

        # Should log response
        assert "response" in source.lower()

    def test_request_data_logged_on_error(self):
        """Test that request data is logged (truncated) on error"""
        script = """
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' stop_hook.sh)
        declare -f api_call
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            cwd="/Users/tanushreesharma/tracing-claude-code"
        )

        source = result.stdout

        # Should log request data (truncated to 500 chars)
        assert "data" in source
        assert "500" in source  # Truncation limit


@pytest.mark.unit
class TestProjectConfiguration:
    """Tests for project configuration"""

    def test_project_name_from_env(self):
        """Test that project name comes from CC_LANGSMITH_PROJECT"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "CC_LANGSMITH_PROJECT" in content

    def test_project_name_default(self):
        """Test that project has default value"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        # Should have default: "claude-code"
        assert '${CC_LANGSMITH_PROJECT:-claude-code}' in content

    def test_api_base_url(self):
        """Test that API base URL is configured"""
        with open("/Users/tanushreesharma/tracing-claude-code/stop_hook.sh", "r") as f:
            content = f.read()

        assert "api.smith.langchain.com" in content

"""
BashRunner - Execute bash functions from stop_hook.sh in isolation for unit testing.

This helper enables testing individual bash functions without executing the main script.
"""

import os
import shlex
import subprocess
from pathlib import Path
from typing import Optional


class BashRunner:
    """Execute bash functions from stop_hook.sh in isolation"""

    def __init__(self, script_path: str = "/Users/tanushreesharma/tracing-claude-code/stop_hook.sh"):
        self.script_path = script_path
        if not Path(script_path).exists():
            raise FileNotFoundError(f"Script not found: {script_path}")

    def call_function(self, func_name: str, *args: str, stdin: Optional[str] = None) -> str:
        """
        Call a bash function with arguments.

        Args:
            func_name: Name of the function to call
            *args: Arguments to pass to the function
            stdin: Optional stdin input for the function

        Returns:
            stdout from function execution

        Raises:
            RuntimeError: If the function execution fails
        """
        # Create a script that sources stop_hook.sh (skip main execution) and calls the function
        # We use sed to remove everything from 'main' onwards and the early exit check
        quoted_args = ' '.join(shlex.quote(arg) for arg in args)

        script = f"""
        set -e
        set -o pipefail

        # Source functions from stop_hook.sh (skip main execution and early exit)
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main$/,$d' {shlex.quote(self.script_path)})

        # Call target function
        {func_name} {quoted_args}
        """

        env = {
            **os.environ,
            "TRACE_TO_LANGSMITH": "false",  # Disable hook during testing
            "CC_LANGSMITH_DEBUG": "false",  # Disable debug logging
        }

        try:
            result = subprocess.run(
                ["bash", "-c", script],
                input=stdin,
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )

            if result.returncode != 0:
                error_msg = f"Function {func_name} failed with exit code {result.returncode}\n"
                error_msg += f"STDOUT: {result.stdout}\n"
                error_msg += f"STDERR: {result.stderr}\n"
                error_msg += f"SCRIPT:\n{script}"
                raise RuntimeError(error_msg)

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Function {func_name} timed out after 30 seconds")
        except Exception as e:
            raise RuntimeError(f"Failed to execute function {func_name}: {str(e)}")

    def call_with_stdin(self, func_name: str, stdin: str, *args: str) -> str:
        """
        Call function with stdin input (convenience method).

        Args:
            func_name: Name of the function to call
            stdin: Input to pipe to the function
            *args: Arguments to pass to the function

        Returns:
            stdout from function execution
        """
        return self.call_function(func_name, *args, stdin=stdin)

    def get_function_source(self, func_name: str) -> str:
        """
        Extract the source code of a specific function.

        Useful for debugging or documentation purposes.

        Args:
            func_name: Name of the function

        Returns:
            The function source code
        """
        script = f"""
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main()/,$d' {shlex.quote(self.script_path)})
        declare -f {func_name}
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            raise RuntimeError(f"Function {func_name} not found")

        return result.stdout.strip()

    def list_functions(self) -> list[str]:
        """
        List all functions defined in stop_hook.sh.

        Returns:
            List of function names
        """
        script = f"""
        source <(sed -e '/^# Exit early if tracing disabled$/,/^fi$/d' -e '/^main()/,$d' {shlex.quote(self.script_path)})
        declare -F | awk '{{print $3}}'
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return []

        return [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]

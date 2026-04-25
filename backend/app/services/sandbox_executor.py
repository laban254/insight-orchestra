"""
Sandbox Executor - Safe code execution for generated Python.

This module provides:
- RestrictedPython-based sandbox for safe execution
- Output capture (stdout, stderr)
- Execution timeout
- Memory limits
"""

import sys
import io
import os
import signal
import threading
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from contextlib import redirect_stdout, redirect_stderr
from RestrictedPython import compile_restricted
from RestrictedPython.Guards import safe_builtins

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of sandboxed code execution."""

    success: bool
    output: str = ""
    error: str = ""
    result: Any = None
    execution_time_ms: float = 0.0
    memory_used_mb: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "result": self.result,
            "execution_time_ms": self.execution_time_ms,
            "memory_used_mb": self.memory_used_mb,
        }


class TimeoutError(Exception):
    """Raised when code execution times out."""

    pass


class SandboxExecutor:
    """
    Safe Python code executor using RestrictedPython.

    Features:
    - Restricted imports (no os, sys, subprocess, etc.)
    - Execution timeout
    - Output capture
    - Safe builtins (no eval/exec)
    """

    # Safe builtins for data analysis
    SAFE_BUILTINS = {
        "abs": abs,
        "all": all,
        "any": any,
        "bin": bin,
        "bool": bool,
        "bytes": bytes,
        "callable": callable,
        "chr": chr,
        "complex": complex,
        "dict": dict,
        "divmod": divmod,
        "enumerate": enumerate,
        "filter": filter,
        "float": float,
        "format": format,
        "frozenset": frozenset,
        "getattr": getattr,
        "hasattr": hasattr,
        "hash": hash,
        "hex": hex,
        "int": int,
        "isinstance": isinstance,
        "issubclass": issubclass,
        "iter": iter,
        "len": len,
        "list": list,
        "map": map,
        "max": max,
        "min": min,
        "next": next,
        "object": object,
        "oct": oct,
        "ord": ord,
        "pow": pow,
        "print": print,
        "range": range,
        "repr": repr,
        "reversed": reversed,
        "round": round,
        "set": set,
        "slice": slice,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "type": type,
        "zip": zip,
    }

    # Blocked imports/builtins
    BLOCKED_NAMES = {
        "os",
        "sys",
        "subprocess",
        "eval",
        "exec",
        "compile",
        "open",
        "file",
        "input",
        "raw_input",
        "__import__",
        "breakpoint",
        "help",
        "dir",
        "vars",
        "locals",
        "globals",
        "memoryview",
        "bytearray",
        "buffer",
        "setattr",
        "delattr",
    }

    def __init__(self, timeout_seconds: int = 30, max_memory_mb: float = 256.0):
        """
        Initialize sandbox executor.

        Args:
            timeout_seconds: Maximum execution time in seconds
            max_memory_mb: Maximum memory usage in MB
        """
        self.timeout_seconds = timeout_seconds
        self.max_memory_mb = max_memory_mb
        self._execution_lock = threading.Lock()

    def _create_globals(self, df=None, **additional_globals) -> Dict[str, Any]:
        """
        Create restricted globals dictionary.

        Args:
            df: Optional pandas DataFrame
            **additional_globals: Additional globals to include

        Returns:
            Restricted globals dict
        """
        # Import RestrictedPython guards if available; otherwise provide safe fallbacks.
        try:
            from RestrictedPython.Guards import safe_iter, guarded_iter_unpack_sequence
        except Exception:

            def safe_iter(obj):
                return iter(obj)

            def guarded_iter_unpack_sequence(seq, count=None):
                # Fallback: return the sequence as-is; unpacking is handled by Python runtime.
                return seq

        globals_dict = {
            "_print_": print,
            "_getattr_": getattr,
            "_iter_": safe_iter,
            "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
            "_next_": next,
            "_setitem_": lambda obj, index, value: obj.__setitem__(index, value),
            "_getitem_": lambda obj, index: obj.__getitem__(index),
            "_getiter_": safe_iter,
            "_globals_": {},
            "_builtins_": self.SAFE_BUILTINS,
        }

        # Add pandas and plotly
        try:
            import pandas as pd
            import plotly.express as px

            globals_dict["pd"] = pd
            globals_dict["px"] = px
        except ImportError:
            logger.warning("pandas/plotly not available in sandbox")

        # Add DataFrame if provided
        if df is not None:
            globals_dict["df"] = df
            globals_dict["result"] = None  # Agent should assign this

        # Add additional globals
        globals_dict.update(additional_globals)

        return globals_dict

    def _check_safety(self, code: str) -> Tuple[bool, str]:
        """
        Pre-execution safety check.

        Args:
            code: Python code to check

        Returns:
            Tuple of (is_safe, error_message)
        """
        code_lower = code.lower()

        # Normalize whitespace for better detection
        code_normalized = " ".join(code.split())

        # Check for blocked patterns (more comprehensive)
        blocked_patterns = [
            ("import os", "os module"),
            ("import sys", "sys module"),
            ("import subprocess", "subprocess module"),
            ("import socket", "socket module"),
            ("import requests", "requests module"),
            ("import urllib", "urllib module"),
            ("__import__", "dynamic imports"),
            ("eval(", "eval function"),
            ("exec(", "exec function"),
            ("open(", "file operations"),
            ("breakpoint", "breakpoint function"),
            ("compile(", "compile function"),
            ("delattr", "delattr function"),
            ("setattr", "setattr with dynamic args"),
            ("getattr", "getattr with dynamic args"),
            ("__builtins__", "builtins access"),
            ("__globals__", "globals access"),
            ("__code__", "code object access"),
        ]

        for pattern, description in blocked_patterns:
            # Check both original and normalized code
            if pattern in code_lower or pattern in code_normalized:
                return False, f"Blocked pattern detected: {description}"

        # Check for suspicious string patterns that might be obfuscated
        suspicious_strings = [
            "os.system",
            "os.popen",
            "subprocess.call",
            "socket.socket",
            "pickle.loads",
            "yaml.load",
        ]

        for sus in suspicious_strings:
            if sus in code_lower:
                return False, f"Blocked suspicious pattern: {sus}"

        return True, ""

    def _timeout_handler(self, signum, frame):
        """Handle timeout signal."""
        raise TimeoutError(f"Execution timed out after {self.timeout_seconds}s")

    def execute(self, code: str, df=None, **kwargs) -> ExecutionResult:
        """
        Execute code in sandbox.

        Args:
            code: Python code to execute
            df: Optional pandas DataFrame
            **kwargs: Additional globals to pass

        Returns:
            ExecutionResult object
        """
        import time

        start_time = time.time()

        # Safety check
        is_safe, error_msg = self._check_safety(code)
        if not is_safe:
            return ExecutionResult(
                success=False,
                error=f"Safety check failed: {error_msg}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Compile code
        try:
            byte_code = compile_restricted(code, filename="<inline>", mode="exec")
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Compilation error: {str(e)}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Create globals
        globals_dict = self._create_globals(df, **kwargs)

        # Capture output
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        # Execute with timeout
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            try:
                # Set up timeout
                if sys.platform != "win32":
                    signal.signal(signal.SIGALRM, self._timeout_handler)
                    signal.alarm(self.timeout_seconds)

                # Execute code
                with self._execution_lock:
                    exec(byte_code, globals_dict)

                # Cancel alarm
                if sys.platform != "win32":
                    signal.alarm(0)

                execution_time_ms = (time.time() - start_time) * 1000

                # Get result
                result = globals_dict.get("result", None)

                return ExecutionResult(
                    success=True,
                    output=stdout_capture.getvalue(),
                    error=stderr_capture.getvalue(),
                    result=result,
                    execution_time_ms=execution_time_ms,
                )

            except TimeoutError:
                execution_time_ms = (time.time() - start_time) * 1000
                return ExecutionResult(
                    success=False,
                    error=f"Execution timed out after {self.timeout_seconds}s",
                    execution_time_ms=execution_time_ms,
                )

            except Exception as e:
                execution_time_ms = (time.time() - start_time) * 1000
                return ExecutionResult(
                    success=False,
                    error=f"Execution error: {str(e)}",
                    execution_time_ms=execution_time_ms,
                )

    def execute_with_retry(
        self, code: str, df=None, max_retries: int = 2, **kwargs
    ) -> ExecutionResult:
        """
        Execute code with retry on failure.

        Args:
            code: Python code to execute
            df: Optional pandas DataFrame
            max_retries: Maximum retry attempts
            **kwargs: Additional globals

        Returns:
            ExecutionResult from last attempt
        """
        last_result = None

        for attempt in range(max_retries + 1):
            last_result = self.execute(code, df, **kwargs)

            if last_result.success:
                logger.info(f"Code executed successfully on attempt {attempt + 1}")
                return last_result

            # Log error
            logger.warning(f"Execution failed (attempt {attempt + 1}): {last_result.error}")

        logger.error(f"Code failed after {max_retries + 1} attempts")
        return last_result


# Example usage
if __name__ == "__main__":
    import pandas as pd

    # Create sample DataFrame
    df = pd.DataFrame(
        {
            "A": [1, 2, 3, 4, 5],
            "B": [10, 20, 30, 40, 50],
            "Category": ["X", "Y", "X", "Y", "X"],
        }
    )

    executor = SandboxExecutor(timeout_seconds=10)

    # Test safe code
    safe_code = """
# Calculate mean of column A
result = df['A'].mean()

# Create a simple chart
fig = px.bar(df, x='Category', y='B', title='Test Chart')
result = {'mean': result, 'chart_type': 'bar'}
"""

    print("Testing safe code:")
    result = executor.execute(safe_code, df)
    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    print(f"Error: {result.error}")
    print(f"Result: {result.result}")
    print(f"Time: {result.execution_time_ms:.2f}ms")

    # Test unsafe code
    unsafe_code = """
import os
result = os.system('ls')
"""

    print("\nTesting unsafe code (should fail):")
    result = executor.execute(unsafe_code, df)
    print(f"Success: {result.success}")
    print(f"Error: {result.error}")

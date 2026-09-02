"""
Sandbox Executor - Safe code execution for generated Python.

This module provides:
- AST-based safety analysis (replaces fragile string matching)
- RestrictedPython-based sandbox for safe execution
- ThreadPoolExecutor timeout (works correctly in worker threads)
- Output capture (stdout, stderr)
"""

import ast
import concurrent.futures
import io
import logging
import time
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from typing import Any

from RestrictedPython import compile_restricted

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

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "result": self.result,
            "execution_time_ms": self.execution_time_ms,
            "memory_used_mb": self.memory_used_mb,
        }


class SandboxExecutor:
    """
    Safe Python code executor using RestrictedPython.

    Features:
    - AST-based safety analysis (not bypassable via string obfuscation)
    - Restricted imports (no os, sys, subprocess, etc.)
    - ThreadPoolExecutor timeout (safe in worker threads, unlike SIGALRM)
    - Output capture
    """

    BLOCKED_MODULES = {
        "os",
        "sys",
        "subprocess",
        "socket",
        "requests",
        "urllib",
        "shutil",
        "pathlib",
        "tempfile",
        "glob",
        "fnmatch",
        "pickle",
        "shelve",
        "marshal",
        "ctypes",
        "cffi",
        "importlib",
        "imp",
        "runpy",
        "code",
        "codeop",
        "pty",
        "tty",
        "termios",
        "fcntl",
        "signal",
        "multiprocessing",
        "threading",
        "concurrent",
        "asyncio",
        "selectors",
        "ssl",
    }

    BLOCKED_CALLS = {"eval", "exec", "compile", "open", "breakpoint", "__import__"}

    BLOCKED_DUNDERS = {
        "__globals__",
        "__code__",
        "__builtins__",
        "__import__",
        "__subclasses__",
        "__mro__",
        "__bases__",
        "__loader__",
        "__spec__",
        "__reduce__",
        "__reduce_ex__",
    }

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
        "zip": zip,
    }

    def __init__(self, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds
        # One persistent pool so threads are reused across requests.
        # NOTE: a wall-clock timeout on a thread cannot interrupt CPU-bound
        # code (future.cancel() can't stop a running thread), and per-call
        # memory cannot be capped while sharing this process. True isolation
        # needs a subprocess with resource limits; deferred, since running
        # one worker (see backend/Dockerfile) keeps a wedged query from
        # starving the whole server.
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    def _check_safety(self, code: str) -> tuple[bool, str]:
        """
        AST-based safety analysis — not bypassable via string obfuscation.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

        for node in ast.walk(tree):
            # Block dangerous imports
            if isinstance(node, ast.Import | ast.ImportFrom):
                for alias in getattr(node, "names", []):
                    module_root = alias.name.split(".")[0]
                    if module_root in self.BLOCKED_MODULES:
                        return False, f"Import of '{module_root}' is not allowed"
                if isinstance(node, ast.ImportFrom) and node.module:
                    module_root = node.module.split(".")[0]
                    if module_root in self.BLOCKED_MODULES:
                        return False, f"Import from '{module_root}' is not allowed"

            # Block calls to dangerous builtins
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name) and func.id in self.BLOCKED_CALLS:
                    return False, f"Call to '{func.id}' is not allowed"
                # Block attribute calls like os.system, subprocess.run
                if isinstance(func, ast.Attribute):
                    if isinstance(func.value, ast.Name):
                        full = f"{func.value.id}.{func.attr}"
                        dangerous = {
                            "os.system",
                            "os.popen",
                            "os.execve",
                            "os.execvp",
                            "subprocess.call",
                            "subprocess.run",
                            "subprocess.Popen",
                            "socket.socket",
                            "pickle.loads",
                            "pickle.load",
                            "yaml.load",
                            "marshal.loads",
                        }
                        if full in dangerous:
                            return False, f"Call to '{full}' is not allowed"

            # Block access to dangerous dunder attributes
            if isinstance(node, ast.Attribute):
                if node.attr in self.BLOCKED_DUNDERS:
                    return False, f"Access to '{node.attr}' is not allowed"

            # Block Name access to dangerous builtins not in safe set
            if isinstance(node, ast.Name) and node.id in self.BLOCKED_CALLS:
                if not isinstance(node.ctx, ast.Store):
                    return False, f"Reference to '{node.id}' is not allowed"

        return True, ""

    def _create_globals(self, df=None, **additional_globals) -> dict[str, Any]:
        """Create restricted globals dictionary."""
        try:
            from RestrictedPython.Guards import (
                guarded_iter_unpack_sequence,
                safe_iter,
                safer_getattr,
            )
        except Exception:

            def safe_iter(obj):
                return iter(obj)

            def guarded_iter_unpack_sequence(seq, count=None):
                return seq

            def safer_getattr(obj, name, *args):
                # Fallback guard (RestrictedPython absent): block access to
                # underscore-prefixed names, which is the route to __class__ /
                # __globals__ and the classic sandbox escape.
                if not isinstance(name, str):
                    raise TypeError("attribute name must be a string")
                if name.startswith("_"):
                    raise AttributeError(f"access to '{name}' is not allowed")
                return getattr(obj, name, *args)

        # Restricted builtins: a copy of the allowlist plus an import hook that
        # honours the module denylist, so legitimate `import plotly.express`
        # works while os/sys/subprocess/etc. are refused at the import machinery
        # itself (the AST pass screens import statements too — this is the
        # runtime backstop).
        safe_builtins = dict(self.SAFE_BUILTINS)
        _blocked = self.BLOCKED_MODULES

        def _guarded_import(name, _globals=None, _locals=None, fromlist=(), level=0):
            root = name.split(".")[0]
            if root in _blocked:
                raise ImportError(f"import of '{root}' is not allowed")
            return __import__(name, _globals, _locals, fromlist, level)

        safe_builtins["__import__"] = _guarded_import

        globals_dict = {
            "_print_": print,
            "_getattr_": safer_getattr,
            "_iter_": safe_iter,
            "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
            "_next_": next,
            "_setitem_": lambda obj, index, value: obj.__setitem__(index, value),
            "_getitem_": lambda obj, index: obj.__getitem__(index),
            "_getiter_": safe_iter,
            "_globals_": {},
            # Correct key: with the misnamed "_builtins_" Python silently
            # injected the *real* builtins and the allowlist never applied.
            # "__builtins__" is what exec actually reads.
            "__builtins__": safe_builtins,
        }

        try:
            import pandas as pd
            import plotly.express as px

            globals_dict["pd"] = pd
            globals_dict["px"] = px
        except ImportError:
            logger.warning("pandas/plotly not available in sandbox")

        if df is not None:
            globals_dict["df"] = df
            globals_dict["result"] = None

        globals_dict.update(additional_globals)
        return globals_dict

    def execute(self, code: str, df=None, **kwargs) -> ExecutionResult:
        """Execute code in sandbox with AST safety check and thread-based timeout."""
        start_time = time.time()

        is_safe, error_msg = self._check_safety(code)
        if not is_safe:
            return ExecutionResult(
                success=False,
                error=f"Safety check failed: {error_msg}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        try:
            byte_code = compile_restricted(code, filename="<inline>", mode="exec")
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Compilation error: {str(e)}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        globals_dict = self._create_globals(df, **kwargs)
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        def _run():
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(byte_code, globals_dict)
            return globals_dict.get("result", None)

        future = self._executor.submit(_run)
        try:
            result = future.result(timeout=self.timeout_seconds)
            return ExecutionResult(
                success=True,
                output=stdout_capture.getvalue(),
                error=stderr_capture.getvalue(),
                result=result,
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except concurrent.futures.TimeoutError:
            future.cancel()
            return ExecutionResult(
                success=False,
                error=f"Execution timed out after {self.timeout_seconds}s",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error=f"Execution error: {str(e)}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def execute_with_retry(
        self, code: str, df=None, max_retries: int = 2, **kwargs
    ) -> ExecutionResult:
        """Execute code, retrying on failure up to `max_retries` extra times."""
        last_result: ExecutionResult | None = None
        for attempt in range(max_retries + 1):
            last_result = self.execute(code, df, **kwargs)
            if last_result.success:
                logger.info(f"Code executed successfully on attempt {attempt + 1}")
                return last_result
            logger.warning(f"Execution failed (attempt {attempt + 1}): {last_result.error}")

        logger.error(f"Code failed after {max_retries + 1} attempts")
        # The loop always runs at least once, so last_result is set here.
        assert last_result is not None
        return last_result

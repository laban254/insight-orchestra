from typing import Any


def safe_log_value(value: Any) -> str:
    """Escape CR/LF in untrusted values before writing them to logs, to
    prevent log injection (forged log entries via embedded newlines)."""
    return str(value).replace("\r", "\\r").replace("\n", "\\n")

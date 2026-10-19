"""The app version, resolved at runtime.

Priority: the ``IO_VERSION`` env var (injected from the release tag when the
image is built — see ``.github/workflows/publish-images.yml``), then the
``version`` field in ``pyproject.toml`` (local dev run from a checkout), then
``"dev"``. One place so ``/health`` can report exactly which build is running.
"""

from __future__ import annotations

import os
from pathlib import Path


def _from_pyproject() -> str | None:
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
        return None
    # In a checkout: backend/app/version.py -> repo root is two levels up. In
    # the container there is no pyproject.toml (the build context is backend/),
    # so this returns None and IO_VERSION carries the version instead.
    for root in (Path(__file__).resolve().parents[2], Path("/app")):
        candidate = root / "pyproject.toml"
        if candidate.is_file():
            try:
                with candidate.open("rb") as fh:
                    data = tomllib.load(fh)
            except (OSError, ValueError):
                return None
            value = data.get("project", {}).get("version")
            return value if isinstance(value, str) else None
    return None


def version() -> str:
    """The running version, e.g. "1.2.0", "edge", or "dev"."""
    return os.environ.get("IO_VERSION") or _from_pyproject() or "dev"

"""
Retention sweep — the backend has never deleted an uploaded file on its own.

Two separate messes accumulate without this:

* Registered datasets outlive their usefulness. A workspace has no TTL by
  design (see workspace_store.py), so a dataset an upload or a demo load
  wrote could sit on disk indefinitely. `dev` on this repo alone reached
  91 files / 114 MB in `backend/uploads/` before this existed.
* Orphaned files: a CSV written by `save_upload_file` whose registration
  never completed (a crash between the write and `register()`), or a file
  left over from before the dataset registry existed at all — the same
  91 files above, none of which any registry record points at.

The sweep is deliberately conservative: age-based reaping only touches
datasets the registry knows about and only past a generous, sliding TTL
(`DATASET_TTL_SECONDS`, reset on every access — see DatasetRegistry.touch),
and orphan cleanup only removes a file once it has sat unreferenced past a
grace period, so a file mid-upload or mid-registration is never touched.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

from app.config import settings
from app.services.dataset_registry import DATASET_DIR, get_dataset_registry
from app.utils.file_utils import UPLOAD_DIR

logger = logging.getLogger(__name__)

# How long a file may sit unreferenced by any registry record before the
# orphan sweep removes it. Long enough to comfortably outlast the upload ->
# parse -> register sequence for even a 50 MB file on a slow disk.
_ORPHAN_GRACE_SECONDS = 3600

# Extensions the orphan sweep considers. Only files this codebase itself
# writes into these directories, so nothing a user placed there for SQLite/
# DuckDB browsing (see connectors.py's local-files listing) is ever touched.
_MANAGED_SUFFIXES = (".csv", ".tsv")


def _registered_paths() -> set[str]:
    registry = get_dataset_registry()
    return {os.path.abspath(r["path"]) for r in registry.all()}


def _sweep_orphans(directory: str, referenced: set[str]) -> list[str]:
    removed: list[str] = []
    try:
        entries = os.listdir(directory)
    except OSError:
        return removed

    now = time.time()
    for name in entries:
        if not name.lower().endswith(_MANAGED_SUFFIXES):
            continue
        path = os.path.join(directory, name)
        if os.path.abspath(path) in referenced:
            continue
        try:
            age = now - os.path.getmtime(path)
        except OSError:
            continue
        if age < _ORPHAN_GRACE_SECONDS:
            continue
        try:
            os.remove(path)
            removed.append(path)
        except OSError as e:
            logger.warning("Could not remove orphaned file %s: %s", path, e)
    return removed


def sweep_once() -> dict[str, int]:
    """Run one retention pass. Returns counts for logging/testing."""
    registry = get_dataset_registry()
    expired = registry.reap_expired(settings.dataset_ttl_seconds)

    # Re-read after reaping so a just-expired dataset's file (already
    # removed by reap_expired -> delete) isn't double-counted as an orphan.
    referenced = _registered_paths()
    orphans = _sweep_orphans(UPLOAD_DIR, referenced) + _sweep_orphans(DATASET_DIR, referenced)

    if expired or orphans:
        logger.info(
            "Retention sweep: %d expired dataset(s), %d orphaned file(s) removed",
            len(expired),
            len(orphans),
        )
    return {"expired": len(expired), "orphans": len(orphans)}


async def run_periodic_sweep(interval_seconds: int) -> None:
    """Run `sweep_once` forever, spaced `interval_seconds` apart.

    Intended to be launched once as a background task from the app's
    lifespan and cancelled on shutdown; a raised exception from one pass
    is logged and swallowed so a transient error (e.g. Redis briefly
    unreachable) doesn't kill the sweeper for the life of the process.
    """
    while True:
        try:
            await asyncio.to_thread(sweep_once)
        except Exception:
            logger.exception("Retention sweep failed")
        await asyncio.sleep(interval_seconds)

"""
In-process cache for cleaned DataFrames.

`/nlq` re-read the CSV and re-ran the full Data Janitor for *every* question,
so each follow-up paid the parse, dedupe, impute and outlier-scan cost again
on data that had not changed. Cleaning is deterministic, so the result can be
reused for the life of the file.

The cache is per-process (the backend runs multiple uvicorn workers, and a
DataFrame cannot be shared between them through Redis without paying the
serialization cost this exists to avoid), bounded to a few entries, and
invalidated by the file's modification time so a re-materialized dataset is
never served stale.
"""

from __future__ import annotations

import logging
import os
import threading
from collections import OrderedDict
from typing import Any, NamedTuple

import pandas as pd

logger = logging.getLogger(__name__)

# Bounded because each entry holds a full DataFrame. Enough to keep a
# conversation about one or two datasets fast without pinning memory.
MAX_ENTRIES = 3


class CleanedDataset(NamedTuple):
    df: pd.DataFrame
    report: dict[str, Any]
    # Whether the analysis was capped, so a cache hit reports it too rather
    # than quietly implying full coverage on follow-up questions.
    sampling: dict[str, Any] | None


class _Entry(NamedTuple):
    mtime: float
    cleaned: CleanedDataset


_cache: OrderedDict[str, _Entry] = OrderedDict()
_lock = threading.Lock()


def _mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return -1.0


def get_cleaned(dataset_id: str, path: str, clean: Any) -> tuple[CleanedDataset, bool]:
    """Return the cleaned dataset for `dataset_id`, cleaning it if needed.

    `clean` is a zero-argument callable producing `{"cleaned_df", "report"}`.
    Returns the result and whether it came from the cache, so callers can
    report an honest duration.
    """
    mtime = _mtime(path)

    with _lock:
        entry = _cache.get(dataset_id)
        if entry is not None and entry.mtime == mtime:
            _cache.move_to_end(dataset_id)
            return entry.cleaned, True

    # Cleaning happens outside the lock: it is the slow part, and holding the
    # lock across it would serialize unrelated datasets.
    result = clean()
    cleaned = CleanedDataset(
        df=result["cleaned_df"],
        report=result["report"],
        sampling=result.get("sampling"),
    )

    with _lock:
        _cache[dataset_id] = _Entry(mtime=mtime, cleaned=cleaned)
        _cache.move_to_end(dataset_id)
        while len(_cache) > MAX_ENTRIES:
            evicted, _ = _cache.popitem(last=False)
            logger.debug("Evicted cleaned dataset %s from cache", evicted)

    return cleaned, False


def invalidate(dataset_id: str) -> None:
    with _lock:
        _cache.pop(dataset_id, None)


def clear() -> None:
    with _lock:
        _cache.clear()

"""Cleaned-frame cache.

/nlq re-read the CSV and re-ran the full Data Janitor for every question, so
each follow-up paid the parse, dedupe, impute and outlier-scan cost again on
data that had not changed.
"""

import os

import pandas as pd
import pytest

from app.services import dataset_cache
from app.services.dataset_cache import clear, get_cleaned, invalidate


@pytest.fixture(autouse=True)
def clean_cache():
    clear()
    yield
    clear()


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text("a,b\n1,2\n3,4\n")
    return str(path)


def make_cleaner(counter, sampling=None):
    def clean():
        counter.append(1)
        return {
            "cleaned_df": pd.DataFrame({"a": [1, 3], "b": [2, 4]}),
            "report": {"duplicates_removed": 0, "call": len(counter)},
            "sampling": sampling,
        }

    return clean


def test_first_call_cleans_and_reports_a_miss(csv_file):
    calls = []
    cleaned, from_cache = get_cleaned("ds1", csv_file, make_cleaner(calls))
    assert from_cache is False
    assert len(calls) == 1
    assert cleaned.df["a"].tolist() == [1, 3]


def test_second_call_reuses_the_result(csv_file):
    calls = []
    get_cleaned("ds1", csv_file, make_cleaner(calls))
    cleaned, from_cache = get_cleaned("ds1", csv_file, make_cleaner(calls))

    assert from_cache is True
    assert len(calls) == 1, "the janitor must not run again for the same file"
    assert cleaned.report["call"] == 1


def test_a_changed_file_invalidates_the_entry(csv_file):
    calls = []
    get_cleaned("ds1", csv_file, make_cleaner(calls))

    # Re-materialized dataset: same id, new contents.
    with open(csv_file, "a") as fh:
        fh.write("5,6\n")
    os.utime(csv_file, (0, 0))

    _, from_cache = get_cleaned("ds1", csv_file, make_cleaner(calls))
    assert from_cache is False
    assert len(calls) == 2


def test_sampling_notice_survives_a_cache_hit(csv_file):
    """A cached follow-up must not imply the analysis covered every row."""
    notice = {"sampled": True, "analyzed_rows": 10, "total_rows": 99}
    calls = []
    get_cleaned("ds1", csv_file, make_cleaner(calls, sampling=notice))
    cleaned, from_cache = get_cleaned("ds1", csv_file, make_cleaner(calls, sampling=notice))

    assert from_cache is True
    assert cleaned.sampling == notice


def test_cache_is_bounded(csv_file, monkeypatch):
    monkeypatch.setattr(dataset_cache, "MAX_ENTRIES", 2)
    calls = []
    for dataset_id in ("a", "b", "c"):
        get_cleaned(dataset_id, csv_file, make_cleaner(calls))

    # "a" was evicted, so it has to be cleaned again.
    _, from_cache = get_cleaned("a", csv_file, make_cleaner(calls))
    assert from_cache is False


def test_recently_used_entries_are_kept(csv_file, monkeypatch):
    monkeypatch.setattr(dataset_cache, "MAX_ENTRIES", 2)
    calls = []
    get_cleaned("a", csv_file, make_cleaner(calls))
    get_cleaned("b", csv_file, make_cleaner(calls))
    get_cleaned("a", csv_file, make_cleaner(calls))  # refresh "a"
    get_cleaned("c", csv_file, make_cleaner(calls))  # evicts "b", not "a"

    _, a_cached = get_cleaned("a", csv_file, make_cleaner(calls))
    assert a_cached is True


def test_invalidate_drops_an_entry(csv_file):
    calls = []
    get_cleaned("ds1", csv_file, make_cleaner(calls))
    invalidate("ds1")
    _, from_cache = get_cleaned("ds1", csv_file, make_cleaner(calls))
    assert from_cache is False


def test_missing_file_still_cleans(tmp_path):
    """A vanished file has no mtime; that must not wedge the cache."""
    calls = []
    missing = str(tmp_path / "gone.csv")
    _, first = get_cleaned("ds1", missing, make_cleaner(calls))
    _, second = get_cleaned("ds1", missing, make_cleaner(calls))
    assert first is False
    assert second is True

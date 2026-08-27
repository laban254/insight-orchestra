"""Tests for the shared dataset reader.

These cover the real-world CSV shapes that used to be rejected at upload or
that parsed into something wrong: European semicolon exports, single-column
files, non-UTF-8 encodings, and date columns silently left as text.
"""

import pandas as pd
import pytest

from app.utils.dataset_io import (
    coerce_datetimes,
    describe_dataset,
    detect_delimiter,
    detect_encoding,
    looks_binary,
    read_dataset,
)


def write(tmp_path, name: str, data, encoding: str | None = None):
    path = tmp_path / name
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding=encoding or "utf-8")
    return str(path)


# --- delimiters ---------------------------------------------------------


@pytest.mark.parametrize(
    "name,content,expected_cols",
    [
        ("comma", "a,b,c\n1,2,3\n4,5,6\n", 3),
        ("semicolon", "date;region;revenue\n2024-01-01;North;100\n2024-01-02;South;90\n", 3),
        ("pipe", "a|b|c\n1|2|3\n4|5|6\n", 3),
        ("tab", "a\tb\n1\t2\n3\t4\n", 2),
        ("single_column", "revenue\n100\n200\n300\n", 1),
    ],
)
def test_reads_common_delimiters(tmp_path, name, content, expected_cols):
    result = read_dataset(write(tmp_path, f"{name}.csv", content))
    assert len(result.df.columns) == expected_cols


def test_single_column_file_is_valid(tmp_path):
    """No delimiter to sniff is not the same as malformed."""
    result = read_dataset(write(tmp_path, "one.csv", "revenue\n100\n200\n"))
    assert result.df.columns.tolist() == ["revenue"]
    assert result.df["revenue"].tolist() == [100, 200]


def test_detect_delimiter_falls_back_to_comma():
    assert detect_delimiter("just_one_column\n1\n2\n") == ","


# --- encodings ----------------------------------------------------------


def test_reads_latin1_file(tmp_path):
    """Used to pass upload validation then die with a raw UnicodeDecodeError."""
    path = write(tmp_path, "l1.csv", "name,city\nJosé,Málaga\n", encoding="latin-1")
    result = read_dataset(path)
    assert result.df["city"].tolist() == ["Málaga"]


def test_reads_utf8_bom_without_polluting_header(tmp_path):
    path = write(tmp_path, "bom.csv", "﻿date,value\n2024-01-01,5\n")
    result = read_dataset(path)
    assert result.df.columns.tolist() == ["date", "value"]
    assert result.encoding == "utf-8-sig"


def test_detect_encoding_prefers_utf8(tmp_path):
    assert detect_encoding(write(tmp_path, "u.csv", "a,b\né,2\n")) == "utf-8"


# --- binary rejection ---------------------------------------------------


def test_looks_binary_catches_renamed_spreadsheet():
    assert looks_binary(b"PK\x03\x04\x14\x00,\x00rest of a xlsx")
    assert looks_binary(b"\xd0\xcf\x11\xe0legacy xls")
    assert not looks_binary(b"a,b,c\n1,2,3")


def test_read_dataset_rejects_binary(tmp_path):
    path = write(tmp_path, "sneaky.csv", b"PK\x03\x04\x14\x00,\x00\x08\x00fake xlsx")
    with pytest.raises(ValueError, match="binary file"):
        read_dataset(path)


# --- datetime coercion --------------------------------------------------


def test_date_column_becomes_datetime(tmp_path):
    """The core fix: a CSV round-trip used to leave dates as text, so every
    agent downstream treated them as categorical."""
    content = "date,revenue\n" + "".join(
        f"2024-01-{d:02d},{d * 10}\n" for d in range(1, 21)
    )
    result = read_dataset(write(tmp_path, "ts.csv", content))
    assert pd.api.types.is_datetime64_any_dtype(result.df["date"])
    assert result.datetime_columns == ["date"]


def test_datetime_with_time_component(tmp_path):
    content = "ts,v\n" + "".join(f"2024-01-01 0{h}:30:00,{h}\n" for h in range(1, 10))
    result = read_dataset(write(tmp_path, "ts2.csv", content))
    assert pd.api.types.is_datetime64_any_dtype(result.df["ts"])


def test_integer_ids_are_not_parsed_as_dates(tmp_path):
    """pandas will happily read bare ints as nanosecond timestamps."""
    content = "user_id,name\n" + "".join(f"{1000 + i},user{i}\n" for i in range(20))
    result = read_dataset(write(tmp_path, "ids.csv", content))
    assert result.datetime_columns == []
    assert pd.api.types.is_numeric_dtype(result.df["user_id"])


def test_text_column_with_a_few_dates_is_left_alone(tmp_path):
    """Below the parse-ratio threshold, so it stays text."""
    rows = ["note"] + ["2024-01-01"] + [f"free text {i}" for i in range(20)]
    content = "notes\n" + "\n".join(rows) + "\n"
    result = read_dataset(write(tmp_path, "notes.csv", content))
    assert result.datetime_columns == []


def test_coerce_datetimes_ignores_all_null_column():
    df = pd.DataFrame({"empty": [None, None, None]})
    assert coerce_datetimes(df) == []


# --- errors -------------------------------------------------------------


def test_missing_file_raises(tmp_path):
    with pytest.raises(ValueError, match="File not found"):
        read_dataset(str(tmp_path / "nope.csv"))


def test_empty_file_raises(tmp_path):
    with pytest.raises(ValueError, match="empty"):
        read_dataset(write(tmp_path, "empty.csv", ""))


# --- describe -----------------------------------------------------------


def test_describe_dataset_shape_and_preview():
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", None]})
    info = describe_dataset(df, preview_rows=2)
    assert info["rows"] == 3
    assert info["columns"] == 2
    assert info["column_names"] == ["a", "b"]
    assert info["null_counts"]["b"] == 1
    assert len(info["preview"]) == 2


def test_describe_dataset_serializes_datetimes():
    df = pd.DataFrame({"date": pd.to_datetime(["2024-01-01", "2024-01-02"])})
    info = describe_dataset(df)
    assert info["dtypes"]["date"].startswith("datetime64")
    assert info["preview"][0]["date"].startswith("2024-01-01")

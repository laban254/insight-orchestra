"""
Single entry point for turning a file on disk into a DataFrame.

Every ingestion path — CSV upload, demo dataset, materialized DB table,
BigQuery result — ends up as a CSV that this module reads back. A bare
`pd.read_csv` was too naive for that job in three ways that users hit
immediately:

* **Encoding.** A latin-1/cp1252 export (anything with an accented character
  saved out of Excel) passed upload validation and then died in the analysis
  step with a raw `UnicodeDecodeError`.
* **Delimiter.** Semicolon-separated files — the default CSV export across
  most of Europe — and pipe-separated files parsed as a single column.
* **Dates.** `read_csv` leaves dates as strings, so every downstream agent
  treated a date column as categorical: the Janitor mode-imputed it, and
  Viz Whiz drew a bar chart of 15 arbitrary days instead of a time series.

So reading is sniff-then-parse-then-coerce, and the detected settings are
returned alongside the frame so callers can show the user what was assumed.
"""

from __future__ import annotations

import codecs
import csv
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Bytes read to sniff encoding and delimiter. Large enough to cover a header
# plus several rows, small enough to stay cheap on a 50 MB file.
SNIFF_BYTES = 64 * 1024

# Tried in order; latin-1 never raises, so it terminates the list.
_ENCODINGS = ("utf-8", "cp1252", "latin-1")

# Delimiters csv.Sniffer is allowed to choose between. Restricting the set
# stops it picking something absurd (a letter that happens to recur) on
# short or unusual files.
_DELIMITERS = ",;\t|"

# Leading bytes of formats that are definitely not CSV, however the file is
# named. ZIP covers .xlsx/.docx; OLE2 covers legacy .xls.
_BINARY_MAGIC = (
    b"PK\x03\x04",  # zip / xlsx / ods
    b"\xd0\xcf\x11\xe0",  # OLE2 / legacy xls
    b"%PDF",
    b"\x89PNG",
    b"GIF8",
    b"\xff\xd8\xff",  # jpeg
    b"\x1f\x8b",  # gzip
    b"SQLite format 3\x00",
)

# A column is converted to datetime only if this fraction of its non-null
# values parse. Set high so a text column containing a few date-like values
# isn't silently destroyed.
_MIN_PARSE_RATIO = 0.9

# Values sampled per column when deciding whether it looks like a date.
_DATE_SAMPLE = 200


@dataclass
class DatasetReadResult:
    """A parsed dataset plus what had to be assumed to parse it."""

    df: pd.DataFrame
    encoding: str
    delimiter: str
    datetime_columns: list[str] = field(default_factory=list)

    @property
    def assumptions(self) -> dict[str, Any]:
        """Detected settings, for surfacing to the user after an upload."""
        return {
            "encoding": self.encoding,
            "delimiter": self.delimiter,
            "datetime_columns": self.datetime_columns,
        }


def looks_binary(header: bytes) -> bool:
    """True if these leading bytes belong to a known non-CSV binary format.

    Catches the common "renamed a spreadsheet to .csv" mistake, which the
    old extension-plus-comma check waved through — a zip header contains a
    comma often enough to pass.
    """
    if header.startswith(_BINARY_MAGIC):
        return True
    # A NUL in the first block means binary for any text encoding we accept.
    # (UTF-16 is handled separately by its BOM before this is reached.)
    return b"\x00" in header


def _decodes(sample: bytes, encoding: str) -> bool:
    """Can `sample` be decoded as `encoding`, ignoring a truncated tail?

    The sample is cut at a fixed byte count, which can split a multi-byte
    character. A failure in the last few bytes is an artefact of that cut,
    not evidence of the wrong encoding.
    """
    try:
        sample.decode(encoding)
        return True
    except UnicodeDecodeError as e:
        return e.start >= len(sample) - 4


def detect_encoding(path: str) -> str:
    """Best-guess text encoding for a file, honouring a BOM if present."""
    with open(path, "rb") as fh:
        sample = fh.read(SNIFF_BYTES)

    if sample.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if sample.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return "utf-16"
    if sample.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        return "utf-32"

    for encoding in _ENCODINGS:
        if _decodes(sample, encoding):
            return encoding
    return "latin-1"  # unreachable: latin-1 decodes any byte string


def detect_delimiter(text: str) -> str:
    """Best-guess field delimiter for a block of decoded CSV text.

    A single-column file has no delimiter to find and makes Sniffer raise;
    that is a valid CSV, so it falls back to a comma and parses as one
    column rather than being rejected.
    """
    try:
        return csv.Sniffer().sniff(text, delimiters=_DELIMITERS).delimiter
    except csv.Error:
        return ","


def _to_datetime_or_none(series: pd.Series) -> pd.Series | None:
    """Parse a string column to datetime, or None if it isn't dates.

    Requires date-ish punctuation before attempting a parse, so bare integer
    IDs — which pandas will happily read as nanosecond timestamps — are left
    alone.
    """
    non_null = series.dropna()
    if non_null.empty:
        return None

    sample = non_null.astype(str).head(_DATE_SAMPLE)
    has_separator = sample.str.contains(r"[-/:]", regex=True).mean()
    has_digit = sample.str.contains(r"\d", regex=True).mean()
    if has_separator < _MIN_PARSE_RATIO or has_digit < _MIN_PARSE_RATIO:
        return None

    for fmt in ("ISO8601", "mixed"):
        try:
            parsed = pd.to_datetime(series, format=fmt, errors="coerce")
        except (ValueError, TypeError):
            continue
        # Measure success against the values that were actually present:
        # pre-existing nulls shouldn't count as parse failures.
        if parsed.notna().sum() / len(non_null) >= _MIN_PARSE_RATIO:
            return parsed
    return None


def coerce_datetimes(df: pd.DataFrame) -> list[str]:
    """Convert date-like text columns to datetime in place; return their names."""
    converted: list[str] = []
    for col in df.columns:
        if not (pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col])):
            continue
        parsed = _to_datetime_or_none(df[col])
        if parsed is not None:
            df[col] = parsed
            converted.append(str(col))
    return converted


def read_dataset(path: str, nrows: int | None = None) -> DatasetReadResult:
    """Read a CSV from disk, sniffing encoding and delimiter, parsing dates.

    Raises ValueError with a message meant for the user — callers translate
    it into an HTTP error.
    """
    if not os.path.isfile(path):
        raise ValueError("File not found.")

    encoding = detect_encoding(path)
    with open(path, "rb") as fh:
        raw = fh.read(SNIFF_BYTES)

    if (
        looks_binary(raw)
        and not encoding.startswith("utf-16")
        and not encoding.startswith("utf-32")
    ):
        raise ValueError(
            "This looks like a binary file (a spreadsheet, archive or image) "
            "rather than a CSV. Export it as CSV and try again."
        )

    try:
        text = raw.decode(encoding, errors="replace")
    except LookupError as e:  # pragma: no cover - guarded by detect_encoding
        raise ValueError(f"Unsupported text encoding: {encoding}") from e

    delimiter = detect_delimiter(text)

    try:
        df = pd.read_csv(path, sep=delimiter, encoding=encoding, nrows=nrows)
    except UnicodeDecodeError as e:
        raise ValueError(
            f"Could not read the file as {encoding} text. If it came from a "
            f"spreadsheet, re-export it as UTF-8 CSV."
        ) from e
    except pd.errors.EmptyDataError as e:
        raise ValueError("The file is empty.") from e
    except pd.errors.ParserError as e:
        raise ValueError(f"Could not parse the file as CSV: {e}") from e
    except Exception as e:
        # Anything else pandas throws is still a bad-input problem from the
        # caller's point of view, so it stays a 400 rather than a 500.
        raise ValueError(f"Could not read the file: {e}") from e

    if df.empty and not df.columns.tolist():
        raise ValueError("The file contains no columns.")

    datetime_columns = coerce_datetimes(df)
    logger.info(
        "Read dataset %s: %d rows x %d cols (encoding=%s, delimiter=%r, dates=%s)",
        os.path.basename(path),
        len(df),
        len(df.columns),
        encoding,
        delimiter,
        datetime_columns,
    )
    return DatasetReadResult(
        df=df, encoding=encoding, delimiter=delimiter, datetime_columns=datetime_columns
    )


def describe_dataset(df: pd.DataFrame, preview_rows: int = 20) -> dict[str, Any]:
    """Shape, per-column types and a preview — what the UI shows after ingest."""
    import json

    return {
        "rows": int(len(df)),
        "columns": int(len(df.columns)),
        "column_names": [str(c) for c in df.columns],
        "dtypes": {str(c): str(df[c].dtype) for c in df.columns},
        "null_counts": {str(c): int(df[c].isnull().sum()) for c in df.columns},
        "preview": json.loads(df.head(preview_rows).to_json(orient="records", date_format="iso")),
    }

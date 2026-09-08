import os
import uuid

from fastapi import UploadFile

from app.utils.dataset_io import (
    EXCEL_SUFFIXES,
    JSON_SUFFIXES,
    PARQUET_SUFFIXES,
    SNIFF_BYTES,
    looks_binary,
)

UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "uploads")
)

os.makedirs(UPLOAD_DIR, exist_ok=True)

# Maximum upload size: 50 MB
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Extensions accepted. The content check below is what actually decides —
# these just stop obviously wrong files before anything is written. `.txt`
# is deliberately excluded from the CSV suffixes: a prose file would parse
# as a valid one-column CSV, so the extension is the only thing that can
# rule it out.
CSV_SUFFIXES = (".csv", ".tsv")
ALLOWED_SUFFIXES = CSV_SUFFIXES + EXCEL_SUFFIXES + JSON_SUFFIXES + PARQUET_SUFFIXES

# Leading bytes for the non-CSV formats we accept, so a file merely *named*
# `.xlsx`/`.parquet` (or a CSV misnamed as one) is still rejected up front
# rather than failing confusingly deep inside a format-specific reader.
_XLSX_MAGIC = b"PK\x03\x04"  # xlsx is a zip archive
_PARQUET_MAGIC = b"PAR1"

# Copy the upload in chunks so the size limit can be enforced while writing.
_COPY_CHUNK = 1024 * 1024


def save_upload_file(upload_file: UploadFile) -> str:
    """Persist an uploaded dataset file and return its path.

    Validation is deliberately shallow here — it rejects content that
    obviously doesn't match its extension and enforces the size limit.
    Whether the bytes actually parse is decided by `read_dataset`, so that
    format-specific handling lives in exactly one place.
    """
    filename = upload_file.filename or ""
    lower = filename.lower()
    if not lower.endswith(ALLOWED_SUFFIXES):
        raise ValueError("Only CSV, TSV, Excel (.xlsx), JSON, or Parquet files are allowed.")

    header = upload_file.file.read(SNIFF_BYTES)
    if not header:
        raise ValueError("The file is empty.")

    if lower.endswith(CSV_SUFFIXES):
        if looks_binary(header):
            raise ValueError(
                "This looks like a spreadsheet or archive rather than a CSV. "
                "Export it as CSV and try again."
            )
    elif lower.endswith(EXCEL_SUFFIXES):
        if not header.startswith(_XLSX_MAGIC):
            raise ValueError("This doesn't look like a valid .xlsx file.")
    elif lower.endswith(PARQUET_SUFFIXES):
        if not header.startswith(_PARQUET_MAGIC):
            raise ValueError("This doesn't look like a valid Parquet file.")
    elif lower.endswith(JSON_SUFFIXES) and looks_binary(header):
        raise ValueError("This doesn't look like valid JSON text.")

    upload_file.file.seek(0)

    # basename() so a crafted filename can't contribute path segments of its
    # own to the destination.
    unique_filename = f"{uuid.uuid4()}_{os.path.basename(filename)}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    # Enforce the limit while copying. Checking the size afterwards meant an
    # oversized upload was written to disk in full before being rejected.
    written = 0
    try:
        with open(file_path, "wb") as out_file:
            while chunk := upload_file.file.read(_COPY_CHUNK):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise ValueError(
                        f"File too large. Maximum is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
                    )
                out_file.write(chunk)
    except Exception:
        discard_upload(file_path)
        raise

    return file_path


def discard_upload(file_path: str) -> None:
    """Remove a stored upload, ignoring an already-missing file."""
    try:
        os.remove(file_path)
    except OSError:
        pass

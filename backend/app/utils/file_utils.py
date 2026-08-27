import os
import uuid

from fastapi import UploadFile

from app.utils.dataset_io import SNIFF_BYTES, looks_binary

UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "uploads")
)

os.makedirs(UPLOAD_DIR, exist_ok=True)

# Maximum upload size: 50 MB
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Extensions accepted. The content check below is what actually decides —
# these just stop obviously wrong files before anything is written. `.txt`
# is deliberately excluded: a prose file would parse as a valid one-column
# CSV, so the extension is the only thing that can rule it out.
ALLOWED_SUFFIXES = (".csv", ".tsv")

# Copy the upload in chunks so the size limit can be enforced while writing.
_COPY_CHUNK = 1024 * 1024


def save_upload_file(upload_file: UploadFile) -> str:
    """Persist an uploaded delimited-text file and return its path.

    Validation is deliberately shallow here — it rejects what is definitely
    not a CSV (wrong extension, binary content) and enforces the size limit.
    Whether the bytes actually parse is decided by `read_dataset`, so that
    delimiter and encoding handling live in exactly one place.
    """
    filename = upload_file.filename or ""
    if not filename.lower().endswith(ALLOWED_SUFFIXES):
        raise ValueError("Only CSV files are allowed (.csv or .tsv).")

    header = upload_file.file.read(SNIFF_BYTES)
    if not header:
        raise ValueError("The file is empty.")
    if looks_binary(header):
        raise ValueError(
            "This looks like a spreadsheet or archive rather than a CSV. "
            "Export it as CSV and try again."
        )
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

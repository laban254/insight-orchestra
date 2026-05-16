import os
import uuid
import shutil
from fastapi import UploadFile

UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'uploads')
)

os.makedirs(UPLOAD_DIR, exist_ok=True)

# Maximum upload size: 50 MB
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Minimum bytes needed to sniff CSV content
_SNIFF_BYTES = 512


def _looks_like_csv(header_bytes: bytes) -> bool:
    """
    Return True if the file content looks like CSV.
    Checks for printable text and the presence of a comma or tab on the first line.
    """
    try:
        sample = header_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        try:
            sample = header_bytes.decode("latin-1", errors="strict")
        except UnicodeDecodeError:
            return False

    first_line = sample.split("\n")[0]
    # Must have at least one field separator
    return "," in first_line or "\t" in first_line


def save_upload_file(upload_file: UploadFile) -> str:
    filename = upload_file.filename or ""
    if not filename.lower().endswith(".csv"):
        raise ValueError("Only CSV files are allowed.")

    # Read the sniff header without consuming the whole stream
    header = upload_file.file.read(_SNIFF_BYTES)
    if not _looks_like_csv(header):
        raise ValueError("File content does not appear to be valid CSV.")

    # Rewind so the full file can be written
    upload_file.file.seek(0)

    unique_filename = f"{uuid.uuid4()}_{filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    with open(file_path, "wb") as out_file:
        shutil.copyfileobj(upload_file.file, out_file)

    # Enforce size limit after writing (avoids loading into memory)
    actual_size = os.path.getsize(file_path)
    if actual_size > MAX_UPLOAD_BYTES:
        os.remove(file_path)
        raise ValueError(
            f"File too large ({actual_size // (1024*1024)} MB). Maximum is {MAX_UPLOAD_BYTES // (1024*1024)} MB."
        )

    return file_path

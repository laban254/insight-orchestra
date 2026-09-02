"""Upload gate: what is stored, what is refused, and what the limit costs.

The previous gate checked for a `.csv` extension plus a comma in the first
512 bytes, then enforced the size limit *after* writing the whole file. That
rejected legitimate exports, accepted renamed spreadsheets, and let an
oversized upload hit the disk in full before being turned away.
"""

from io import BytesIO

import pytest
from app.utils import file_utils
from app.utils.file_utils import MAX_UPLOAD_BYTES, save_upload_file
from starlette.datastructures import UploadFile


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    """Keep test uploads out of the real uploads directory."""
    monkeypatch.setattr(file_utils, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


def upload(name: str, data: bytes) -> UploadFile:
    return UploadFile(filename=name, file=BytesIO(data))


# --- accepted -----------------------------------------------------------


@pytest.mark.parametrize(
    "name,data",
    [
        ("plain.csv", b"a,b,c\n1,2,3\n"),
        ("euro.csv", b"date;region;revenue\n2024-01-01;North;100\n"),
        ("single_column.csv", b"revenue\n100\n200\n"),
        ("tabbed.tsv", b"a\tb\n1\t2\n"),
        ("accented.csv", "name,city\nJosé,Málaga\n".encode("latin-1")),
    ],
)
def test_accepts_real_world_csvs(name, data, upload_dir):
    path = save_upload_file(upload(name, data))
    assert path.startswith(str(upload_dir))
    with open(path, "rb") as fh:
        assert fh.read() == data


# --- refused ------------------------------------------------------------


def test_rejects_wrong_extension():
    with pytest.raises(ValueError, match="Only CSV files"):
        save_upload_file(upload("notes.txt", b"a,b\n1,2\n"))


def test_rejects_renamed_spreadsheet():
    """A zip header contains a comma often enough to pass the old check."""
    with pytest.raises(ValueError, match="spreadsheet or archive"):
        save_upload_file(upload("book.csv", b"PK\x03\x04\x14\x00,\x00\x08\x00xlsx body"))


def test_rejects_empty_file():
    with pytest.raises(ValueError, match="empty"):
        save_upload_file(upload("nothing.csv", b""))


def test_oversized_upload_is_refused_and_leaves_nothing_behind(upload_dir, monkeypatch):
    monkeypatch.setattr(file_utils, "MAX_UPLOAD_BYTES", 1024)
    payload = b"a,b\n" + b"1,2\n" * 1000

    with pytest.raises(ValueError, match="too large"):
        save_upload_file(upload("big.csv", payload))

    assert list(upload_dir.iterdir()) == [], "partial upload should be cleaned up"


def test_limit_is_enforced_while_writing_not_after(upload_dir, monkeypatch):
    """The whole point: the bytes over the limit are never written."""
    monkeypatch.setattr(file_utils, "MAX_UPLOAD_BYTES", 4096)
    written = []

    real_open = open

    def counting_open(path, mode="r", *args, **kwargs):
        handle = real_open(path, mode, *args, **kwargs)
        if "w" in mode:
            original_write = handle.write

            def write(chunk):
                written.append(len(chunk))
                return original_write(chunk)

            handle.write = write
        return handle

    monkeypatch.setattr("builtins.open", counting_open)

    with pytest.raises(ValueError, match="too large"):
        save_upload_file(upload("big.csv", b"x" * (5 * 1024 * 1024)))

    assert sum(written) <= MAX_UPLOAD_BYTES


# --- stored filename ----------------------------------------------------


def test_filename_cannot_contribute_path_segments(upload_dir):
    path = save_upload_file(upload("../../escape.csv", b"a,b\n1,2\n"))
    assert path.startswith(str(upload_dir))
    assert ".." not in path

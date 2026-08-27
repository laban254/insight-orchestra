"""Dataset registry: opaque ids instead of client-supplied paths.

The client used to hold a server filesystem path and hand it back on every
request, which forced /process and /nlq to accept anything under /tmp and
left saved workspaces pointing at files that vanish on a container recreate.
"""

import os

import pytest

from app.services.dataset_registry import (
    DATASET_DIR,
    DatasetMissingError,
    DatasetRegistry,
)


@pytest.fixture
def registry():
    return DatasetRegistry()


@pytest.fixture
def csv_file(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text("a,b\n1,2\n3,4\n")
    return str(path)


def test_register_returns_an_opaque_id(registry, csv_file):
    dataset_id = registry.register(csv_file, name="data.csv")
    assert dataset_id
    # An id, not a path: nothing about the filesystem leaks to the client.
    assert os.sep not in dataset_id
    assert csv_file not in dataset_id


def test_resolve_returns_the_registered_path(registry, csv_file):
    dataset_id = registry.register(csv_file, name="data.csv")
    assert registry.resolve_path(dataset_id) == csv_file


def test_unknown_id_is_rejected(registry):
    with pytest.raises(DatasetMissingError, match="no longer available"):
        registry.resolve_path("not-a-real-id")


def test_a_path_is_not_a_valid_id(registry):
    """The old contract accepted any /tmp path; ids are not paths."""
    for candidate in ("/tmp/demo_sales.csv", "/etc/passwd", "../../etc/passwd"):
        with pytest.raises(DatasetMissingError):
            registry.resolve_path(candidate)


def test_missing_file_reports_the_dataset_name(registry, tmp_path):
    path = tmp_path / "gone.csv"
    path.write_text("a\n1\n")
    dataset_id = registry.register(str(path), name="Quarterly numbers")
    os.remove(path)

    with pytest.raises(DatasetMissingError, match="Quarterly numbers"):
        registry.resolve_path(dataset_id)


def test_demo_dataset_is_regenerated_when_its_file_is_lost(registry):
    """Demo data is generated, so an old workspace should reopen rather than
    dead-end after the file it was written to disappears."""
    path = os.path.join(DATASET_DIR, "test_regen_demo.csv")
    dataset_id = registry.register(path, name="Sales", source="demo:sales")
    if os.path.exists(path):
        os.remove(path)

    try:
        resolved = registry.resolve_path(dataset_id)
        assert os.path.isfile(resolved)
        with open(resolved) as fh:
            assert "region" in fh.readline()
    finally:
        registry.delete(dataset_id)


def test_unknown_demo_source_still_fails_cleanly(registry, tmp_path):
    path = tmp_path / "nope.csv"
    dataset_id = registry.register(str(path), name="Ghost", source="demo:does_not_exist")
    with pytest.raises(DatasetMissingError):
        registry.resolve_path(dataset_id)


def test_delete_removes_record_and_file(registry, csv_file):
    dataset_id = registry.register(csv_file, name="data.csv")
    assert registry.delete(dataset_id) is True
    assert registry.get(dataset_id) is None
    assert not os.path.exists(csv_file)


def test_delete_can_keep_the_file(registry, csv_file):
    dataset_id = registry.register(csv_file, name="data.csv")
    registry.delete(dataset_id, remove_file=False)
    assert os.path.exists(csv_file)


def test_delete_unknown_id_is_false(registry):
    assert registry.delete("nope") is False


def test_all_lists_registered_datasets(registry, csv_file):
    dataset_id = registry.register(csv_file, name="data.csv")
    try:
        assert dataset_id in {r["id"] for r in registry.all()}
    finally:
        registry.delete(dataset_id, remove_file=False)


def test_datasets_live_on_the_mounted_volume():
    """Not /tmp: those files do not survive a container recreate."""
    assert not DATASET_DIR.startswith("/tmp")
    assert DATASET_DIR.endswith(os.path.join("uploads", "datasets"))

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


# --- retention: sliding TTL ----------------------------------------------


def test_register_sets_last_accessed_at(registry, csv_file):
    dataset_id = registry.register(csv_file, name="data.csv")
    record = registry.get(dataset_id)
    assert record["last_accessed_at"] == record["created_at"]


def test_resolve_path_touches_the_dataset(registry, csv_file):
    dataset_id = registry.register(csv_file, name="data.csv")

    # Force a stale timestamp so a resolution deterministically bumps it.
    # The in-memory backend hands back the same dict it stores, so the
    # comparison value is copied out as a plain float rather than kept as a
    # dict reference — otherwise both sides of the assertion mutate together.
    stale = registry.get(dataset_id)
    stale["last_accessed_at"] -= 100
    registry._write(stale)
    stale_value = stale["last_accessed_at"]

    registry.resolve_path(dataset_id)
    assert registry.get(dataset_id)["last_accessed_at"] > stale_value


def test_touch_updates_last_accessed_at(registry, csv_file):
    dataset_id = registry.register(csv_file, name="data.csv")
    record = registry.get(dataset_id)
    record["last_accessed_at"] -= 1000
    registry._write(record)
    old_value = record["last_accessed_at"]

    registry.touch(dataset_id)
    assert registry.get(dataset_id)["last_accessed_at"] > old_value


def test_touch_unknown_id_is_a_noop(registry):
    registry.touch("does-not-exist")  # must not raise


def test_reap_expired_removes_idle_datasets(registry, csv_file):
    dataset_id = registry.register(csv_file, name="data.csv")
    record = registry.get(dataset_id)
    record["last_accessed_at"] = 0  # arbitrarily long ago
    registry._write(record)

    removed = registry.reap_expired(ttl_seconds=3600)
    assert removed == [dataset_id]
    assert registry.get(dataset_id) is None
    assert not os.path.exists(csv_file)


def test_reap_expired_keeps_recently_used_datasets(registry, csv_file):
    dataset_id = registry.register(csv_file, name="data.csv")
    try:
        removed = registry.reap_expired(ttl_seconds=3600)
        assert removed == []
        assert registry.get(dataset_id) is not None
    finally:
        registry.delete(dataset_id, remove_file=False)


def test_reap_expired_disabled_at_zero(registry, csv_file):
    dataset_id = registry.register(csv_file, name="data.csv")
    record = registry.get(dataset_id)
    record["last_accessed_at"] = 0
    registry._write(record)

    try:
        assert registry.reap_expired(ttl_seconds=0) == []
        assert registry.get(dataset_id) is not None
    finally:
        registry.delete(dataset_id, remove_file=False)

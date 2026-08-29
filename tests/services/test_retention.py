"""Retention sweep: nothing else in the backend ever deletes an upload.

Before this existed, this repo's own dev environment had 91 files and
114 MB sitting in backend/uploads/ — none of them referenced by anything,
none of them ever going away on their own.
"""

import os

import pytest

from app.services import retention
from app.services.dataset_registry import get_dataset_registry


@pytest.fixture
def registry():
    return get_dataset_registry()


@pytest.fixture
def managed_dir(tmp_path, monkeypatch):
    """Point both swept directories at an isolated tmp_path."""
    upload_dir = tmp_path / "uploads"
    dataset_dir = tmp_path / "uploads" / "datasets"
    dataset_dir.mkdir(parents=True)
    monkeypatch.setattr(retention, "UPLOAD_DIR", str(upload_dir))
    monkeypatch.setattr(retention, "DATASET_DIR", str(dataset_dir))
    return upload_dir, dataset_dir


def _age(path, seconds_ago):
    t = os.path.getmtime(path) - seconds_ago
    os.utime(path, (t, t))


class TestExpiredReap:
    def test_sweep_reaps_an_idle_dataset(self, registry, tmp_path, monkeypatch):
        monkeypatch.setattr(retention.settings, "dataset_ttl_seconds", 100)
        path = tmp_path / "old.csv"
        path.write_text("a\n1\n")
        dataset_id = registry.register(str(path), name="old.csv")
        record = registry.get(dataset_id)
        record["last_accessed_at"] = 0
        registry._write(record)

        counts = retention.sweep_once()
        assert counts["expired"] == 1
        assert registry.get(dataset_id) is None

    def test_sweep_leaves_active_datasets_alone(self, registry, tmp_path, monkeypatch):
        monkeypatch.setattr(retention.settings, "dataset_ttl_seconds", 3600)
        path = tmp_path / "fresh.csv"
        path.write_text("a\n1\n")
        dataset_id = registry.register(str(path), name="fresh.csv")
        try:
            counts = retention.sweep_once()
            assert counts["expired"] == 0
            assert registry.get(dataset_id) is not None
        finally:
            registry.delete(dataset_id, remove_file=False)


class TestOrphanSweep:
    def test_old_unreferenced_file_is_removed(self, managed_dir, monkeypatch):
        upload_dir, _ = managed_dir
        monkeypatch.setattr(retention.settings, "dataset_ttl_seconds", 0)
        orphan = upload_dir / "leftover.csv"
        orphan.write_text("a\n1\n")
        _age(orphan, retention._ORPHAN_GRACE_SECONDS + 10)

        counts = retention.sweep_once()
        assert counts["orphans"] == 1
        assert not orphan.exists()

    def test_recent_unreferenced_file_survives_the_grace_period(self, managed_dir, monkeypatch):
        """A file mid-upload/mid-registration must never be swept."""
        upload_dir, _ = managed_dir
        monkeypatch.setattr(retention.settings, "dataset_ttl_seconds", 0)
        fresh = upload_dir / "just_written.csv"
        fresh.write_text("a\n1\n")

        counts = retention.sweep_once()
        assert counts["orphans"] == 0
        assert fresh.exists()

    def test_registered_file_is_never_swept_as_an_orphan(
        self, managed_dir, registry, monkeypatch
    ):
        upload_dir, _ = managed_dir
        monkeypatch.setattr(retention.settings, "dataset_ttl_seconds", 3600)
        path = upload_dir / "known.csv"
        path.write_text("a\n1\n")
        _age(str(path), retention._ORPHAN_GRACE_SECONDS + 10)
        dataset_id = registry.register(str(path), name="known.csv")

        try:
            counts = retention.sweep_once()
            assert counts["orphans"] == 0
            assert path.exists()
        finally:
            registry.delete(dataset_id, remove_file=False)

    def test_non_managed_extensions_are_ignored(self, managed_dir):
        """A .sqlite file a user placed for the DB-connect flow must survive."""
        upload_dir, _ = managed_dir
        db_file = upload_dir / "mydata.sqlite"
        db_file.write_text("not really sqlite, just checking it's untouched")
        _age(db_file, retention._ORPHAN_GRACE_SECONDS + 10)

        retention.sweep_once()
        assert db_file.exists()

    def test_sweeps_both_directories(self, managed_dir):
        upload_dir, dataset_dir = managed_dir
        a = upload_dir / "a.csv"
        b = dataset_dir / "b.csv"
        a.write_text("a\n1\n")
        b.write_text("a\n1\n")
        _age(a, retention._ORPHAN_GRACE_SECONDS + 10)
        _age(b, retention._ORPHAN_GRACE_SECONDS + 10)

        counts = retention.sweep_once()
        assert counts["orphans"] == 2
        assert not a.exists()
        assert not b.exists()


class TestPeriodicSweep:
    @pytest.mark.asyncio
    async def test_run_periodic_sweep_survives_a_failing_pass(self, monkeypatch):
        """A transient failure (e.g. Redis briefly unreachable) must not
        kill the sweeper for the life of the process."""
        import asyncio

        calls = []

        def failing_sweep():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("boom")

        monkeypatch.setattr(retention, "sweep_once", failing_sweep)

        task = asyncio.create_task(retention.run_periodic_sweep(interval_seconds=0))
        for _ in range(50):
            if len(calls) >= 2:
                break
            await asyncio.sleep(0.01)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        assert len(calls) >= 2, "a failed pass must not stop the loop"

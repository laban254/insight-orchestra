"""
Unit tests for app.main._bootstrap_admin: creating the first admin account
from ADMIN_EMAIL/ADMIN_PASSWORD on startup.
"""

from app import main as main_module
from app.services.user_store import UserStore


def make_store() -> UserStore:
    store = UserStore()
    store._use_redis = False
    return store


class TestBootstrapAdmin:
    def test_noop_when_auth_disabled(self, monkeypatch):
        store = make_store()
        monkeypatch.setattr(main_module, "get_user_store", lambda: store)
        monkeypatch.setattr(main_module.settings, "auth_enabled", True)
        monkeypatch.setattr(main_module.settings, "admin_email", "")
        monkeypatch.setattr(main_module.settings, "admin_password", "")

        main_module._bootstrap_admin()

        assert store.count() == 0

    def test_noop_when_credentials_unset(self, monkeypatch):
        store = make_store()
        monkeypatch.setattr(main_module, "get_user_store", lambda: store)
        monkeypatch.setattr(main_module.settings, "auth_enabled", False)
        monkeypatch.setattr(main_module.settings, "admin_email", "admin@example.com")
        monkeypatch.setattr(main_module.settings, "admin_password", "hunter22")

        main_module._bootstrap_admin()

        assert store.count() == 0

    def test_creates_admin_when_configured(self, monkeypatch):
        store = make_store()
        monkeypatch.setattr(main_module, "get_user_store", lambda: store)
        monkeypatch.setattr(main_module.settings, "auth_enabled", True)
        monkeypatch.setattr(main_module.settings, "admin_email", "admin@example.com")
        monkeypatch.setattr(main_module.settings, "admin_password", "hunter22")

        main_module._bootstrap_admin()

        record = store.get_by_email("admin@example.com")
        assert record is not None
        assert record["role"] == "admin"
        assert record["password_hash"] is not None

    def test_does_not_recreate_when_users_already_exist(self, monkeypatch):
        store = make_store()
        store.create(email="existing@example.com", name="Existing", role="member")
        monkeypatch.setattr(main_module, "get_user_store", lambda: store)
        monkeypatch.setattr(main_module.settings, "auth_enabled", True)
        monkeypatch.setattr(main_module.settings, "admin_email", "admin@example.com")
        monkeypatch.setattr(main_module.settings, "admin_password", "hunter22")

        main_module._bootstrap_admin()

        assert store.count() == 1
        assert store.get_by_email("admin@example.com") is None

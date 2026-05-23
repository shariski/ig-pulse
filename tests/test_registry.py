from __future__ import annotations

import sqlite3

import pytest

from app import registry


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(registry.settings, "registry_path", tmp_path / "registry.db")
    monkeypatch.setattr(registry.settings, "data_dir", tmp_path / "data")
    c = registry.connect()
    registry.run_migrations(c)
    yield c
    c.close()


def test_create_and_get_user(conn):
    uid = registry.create_user(conn, "alice", "hash123")
    u = registry.get_user_by_name(conn, "alice")
    assert u["id"] == uid and u["password_hash"] == "hash123"


def test_username_unique(conn):
    registry.create_user(conn, "bob", "h")
    with pytest.raises(sqlite3.IntegrityError):
        registry.create_user(conn, "bob", "h2")


def test_create_list_get_account(conn):
    uid = registry.create_user(conn, "carol", "h")
    aid = registry.create_account(conn, uid, ig_user_id="111", username="carol_ig",
                                  access_token="tok", token_expires_at=None)
    accounts = registry.list_accounts(conn, uid)
    assert len(accounts) == 1 and accounts[0]["id"] == aid
    acct = registry.get_account(conn, aid)
    assert acct["ig_user_id"] == "111"
    assert acct["db_path"].endswith(f"acct_{aid}.db")


def test_update_account_token(conn):
    uid = registry.create_user(conn, "dave", "h")
    aid = registry.create_account(conn, uid, "1", "dave_ig", "old", None)
    registry.update_account_token(conn, aid, "new", "2026-07-01T00:00:00Z")
    acct = registry.get_account(conn, aid)
    assert acct["access_token"] == "new"
    assert acct["token_expires_at"] == "2026-07-01T00:00:00Z"

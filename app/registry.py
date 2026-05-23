"""Registry DB: login users + their IG accounts (with per-account tokens + db paths)."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings

_MIGRATIONS = Path(__file__).parent / "registry_migrations"


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or settings.registry_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _migrations (version TEXT PRIMARY KEY, applied_at TEXT)"
    )
    applied = {r[0] for r in conn.execute("SELECT version FROM _migrations")}
    for sql_file in sorted(_MIGRATIONS.glob("*.sql")):
        if sql_file.name in applied:
            continue
        conn.executescript(sql_file.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO _migrations (version, applied_at) VALUES (?, ?)",
            (sql_file.name, datetime.now(UTC).isoformat()),
        )
    conn.commit()


def create_user(conn: sqlite3.Connection, username: str, password_hash: str) -> int:
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, password_hash, datetime.now(UTC).isoformat()),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_user_by_name(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def get_user(conn: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def create_account(
    conn: sqlite3.Connection,
    user_id: int,
    ig_user_id: str,
    username: str | None,
    access_token: str,
    token_expires_at: str | None,
) -> int:
    cur = conn.execute(
        """INSERT INTO ig_accounts
           (user_id, ig_user_id, username, access_token, token_expires_at, db_path, created_at)
           VALUES (?, ?, ?, ?, ?, '', ?)""",
        (user_id, ig_user_id, username, access_token, token_expires_at,
         datetime.now(UTC).isoformat()),
    )
    aid = int(cur.lastrowid)
    db_path = str(settings.data_dir / f"acct_{aid}.db")
    conn.execute("UPDATE ig_accounts SET db_path = ? WHERE id = ?", (db_path, aid))
    conn.commit()
    return aid


def list_accounts(conn: sqlite3.Connection, user_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM ig_accounts WHERE user_id = ? ORDER BY id", (user_id,)
    ).fetchall()


def get_account(conn: sqlite3.Connection, account_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM ig_accounts WHERE id = ?", (account_id,)).fetchone()


def update_account_token(
    conn: sqlite3.Connection, account_id: int, access_token: str, token_expires_at: str | None
) -> None:
    conn.execute(
        "UPDATE ig_accounts SET access_token = ?, token_expires_at = ? WHERE id = ?",
        (access_token, token_expires_at, account_id),
    )
    conn.commit()

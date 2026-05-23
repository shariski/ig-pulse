"""Authentication: argon2 password hashing + session-backed dependencies."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import Depends, Request

from app import registry

_ph = PasswordHasher()  # argon2id defaults (OWASP-reasonable)


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _ph.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


class _Redirect(Exception):
    def __init__(self, to: str):
        self.to = to


def _require_user(request: Request):
    uid = request.session.get("user_id")
    if not uid:
        raise _Redirect("/login")
    conn = registry.connect()
    try:
        user = registry.get_user(conn, uid)
    finally:
        conn.close()
    if user is None:
        raise _Redirect("/login")
    return user


_current_user_dep = Depends(_require_user)


def _require_account(request: Request, user=_current_user_dep):  # noqa: B008
    aid = request.session.get("account_id")
    if not aid:
        raise _Redirect("/accounts")
    conn = registry.connect()
    try:
        account = registry.get_account(conn, aid)
    finally:
        conn.close()
    # Cross-account guard: the account MUST belong to the logged-in user.
    if account is None or account["user_id"] != user["id"]:
        raise _Redirect("/accounts")
    return account


current_user = Depends(_require_user)
current_account = Depends(_require_account)

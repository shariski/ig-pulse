"""Tests for password hashing + (later) auth dependencies."""

from app.auth import hash_password, verify_password


def test_hash_is_not_plaintext_and_verifies():
    h = hash_password("correct horse")
    assert h != "correct horse"
    assert h.startswith("$argon2")
    assert verify_password(h, "correct horse") is True


def test_verify_rejects_wrong_password():
    h = hash_password("s3cret-pass")
    assert verify_password(h, "wrong") is False


def test_hashes_are_salted_unique():
    assert hash_password("same") != hash_password("same")

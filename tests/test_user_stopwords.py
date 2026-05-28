"""Tests for app.analysis.user_stopwords — SQLite overlay CRUD."""

import pytest

from app.analysis.user_stopwords import (
    add_user_stopword,
    list_user_stopwords,
    remove_user_stopword,
)
from app.db import connect, run_migrations


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.db"
    conn = connect(db_path)
    run_migrations(conn)
    yield conn
    conn.close()


def test_list_empty_initially(conn):
    assert list_user_stopwords(conn) == []


def test_add_inserts_lowercase(conn):
    add_user_stopword(conn, "Mantap")
    assert list_user_stopwords(conn) == ["mantap"]


def test_add_strips_whitespace(conn):
    add_user_stopword(conn, "  iya  ")
    assert list_user_stopwords(conn) == ["iya"]


def test_add_is_idempotent(conn):
    add_user_stopword(conn, "iya")
    add_user_stopword(conn, "iya")
    add_user_stopword(conn, "IYA")  # same after lowercasing
    assert list_user_stopwords(conn) == ["iya"]


def test_add_rejects_empty_after_strip(conn):
    with pytest.raises(ValueError):
        add_user_stopword(conn, "   ")
    with pytest.raises(ValueError):
        add_user_stopword(conn, "")


def test_add_truncates_to_50_chars(conn):
    long_word = "a" * 80
    add_user_stopword(conn, long_word)
    assert list_user_stopwords(conn) == ["a" * 50]


def test_remove(conn):
    add_user_stopword(conn, "iya")
    add_user_stopword(conn, "mantap")
    remove_user_stopword(conn, "iya")
    assert list_user_stopwords(conn) == ["mantap"]


def test_remove_missing_is_noop(conn):
    remove_user_stopword(conn, "does-not-exist")
    assert list_user_stopwords(conn) == []


def test_list_sorted_alphabetically(conn):
    for w in ["zeta", "alpha", "mu"]:
        add_user_stopword(conn, w)
    assert list_user_stopwords(conn) == ["alpha", "mu", "zeta"]

"""Tests for ig_client's data-independent logic: header parsing, usage
thresholds, and 429 backoff. Uses httpx.MockTransport to exercise OUR retry /
error handling without faking Instagram response *shapes* (CLAUDE.md B10)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.ig_client import (
    IGClient,
    IGTokenError,
    Page,
    parse_business_use_case_usage,
    usage_action,
)

# --------------------------------------------------------------------------- #
# parse_business_use_case_usage
# --------------------------------------------------------------------------- #


def test_parse_usage_returns_max_pct():
    header = (
        '{"123456": [{"type": "instagram", "call_count": 30, '
        '"total_cputime": 12, "total_time": 47}]}'
    )
    assert parse_business_use_case_usage(header) == 47.0


def test_parse_usage_missing_or_empty():
    assert parse_business_use_case_usage(None) is None
    assert parse_business_use_case_usage("") is None


def test_parse_usage_malformed_returns_none():
    assert parse_business_use_case_usage("not json {{{") is None
    assert parse_business_use_case_usage('{"123": "not-a-list"}') is None


# --------------------------------------------------------------------------- #
# usage_action thresholds (architecture.md: <75 proceed, 75-90 warn, >=90 sleep)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "pct,expected",
    [
        (None, "proceed"),
        (0.0, "proceed"),
        (74.9, "proceed"),
        (75.0, "warn"),
        (89.9, "warn"),
        (90.0, "sleep"),
        (100.0, "sleep"),
    ],
)
def test_usage_action(pct, expected):
    assert usage_action(pct) == expected


# --------------------------------------------------------------------------- #
# IGClient._get — 429 backoff and token-error handling
# --------------------------------------------------------------------------- #


def _client_with_responses(responses: list[httpx.Response]) -> IGClient:
    state = {"i": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        # The token must always be injected, never missing.
        assert "access_token=tok" in str(request.url)
        resp = responses[state["i"]]
        state["i"] += 1
        return resp

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="https://example")
    return IGClient(access_token="tok", client=http, backoff_schedule=(60.0, 120.0))


async def test_get_retries_on_429_then_succeeds(monkeypatch):
    slept: list[float] = []

    async def fake_sleep(delay: float) -> None:
        slept.append(delay)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    ig = _client_with_responses(
        [
            httpx.Response(429),
            httpx.Response(429),
            httpx.Response(
                200, json={"data": [{"id": "1"}], "paging": {"cursors": {"after": "X"}}}
            ),
        ]
    )
    resp = await ig._get("me/media")
    assert resp.status_code == 200
    assert slept == [60.0, 120.0]  # followed the configured schedule
    assert ig.api_calls_made == 3
    await ig.aclose()


async def test_get_raises_after_backoff_exhausted(monkeypatch):
    async def _noop(*_a, **_k):
        return None

    monkeypatch.setattr(asyncio, "sleep", _noop)
    ig = _client_with_responses([httpx.Response(429)] * 3)
    with pytest.raises(httpx.HTTPStatusError):
        await ig._get("me/media")
    assert ig.api_calls_made == 3  # 1 initial + 2 retries
    await ig.aclose()


async def test_get_raises_token_error_on_oauth_400():
    ig = _client_with_responses(
        [httpx.Response(400, json={"error": {"type": "OAuthException", "code": 190}})]
    )
    with pytest.raises(IGTokenError):
        await ig._get("me")
    await ig.aclose()


async def test_page_parsing_extracts_cursor():
    ig = _client_with_responses(
        [httpx.Response(200, json={"data": [{"id": "1"}], "paging": {"cursors": {"after": "C2"}}})]
    )
    resp = await ig._get("me/media")
    page = IGClient._page(resp.json())
    assert isinstance(page, Page)
    assert page.data == [{"id": "1"}]
    assert page.after == "C2"
    await ig.aclose()

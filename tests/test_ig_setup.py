from __future__ import annotations

import httpx
import pytest

from app.ig_setup import IGSetupError, discover_account


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler),
                        base_url="https://graph.facebook.com/v21.0")


def test_discover_account_happy_path():
    def handler(request: httpx.Request) -> httpx.Response:
        p = str(request.url)
        if "me/accounts" in p:
            return httpx.Response(200, json={"data": [{"id": "PAGE1", "name": "P"}]})
        if "PAGE1" in p and "instagram_business_account" in p:
            return httpx.Response(200, json={"instagram_business_account": {"id": "IG99"}})
        if "oauth/access_token" in p:
            return httpx.Response(200, json={"access_token": "LONG", "expires_in": 5184000})
        if request.url.path.rstrip("/").endswith("/IG99"):
            return httpx.Response(200, json={"username": "handle99"})
        return httpx.Response(404, json={"error": {"message": "no"}})

    info = discover_account("SHORT", app_secret="sek", client=_client(handler))
    assert info.ig_user_id == "IG99"
    assert info.username == "handle99"
    assert info.access_token == "LONG"
    assert info.token_expires_at is not None


def test_discover_account_no_pages():
    def handler(request):
        return httpx.Response(200, json={"data": []})
    with pytest.raises(IGSetupError):
        discover_account("SHORT", app_secret="sek", client=_client(handler))

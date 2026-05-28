"""Smoke tests for the sqladmin dashboard.

We don't test sqladmin's UI (it has its own suite). We verify:
    - The Lead/Message ModelView classes are constructable.
    - parse_admin_users() handles common formats.
    - The auth backend rejects empty creds and accepts configured ones.
"""
from __future__ import annotations

import pytest
from starlette.requests import Request

from outreach.admin import (
    BookingAdmin,
    LeadAdmin,
    MessageAdmin,
    UsernamePasswordAuth,
    _parse_pks,
)
from outreach.config import Settings
from outreach.models import Lead, Message


def test_modelviews_are_bound_to_models() -> None:
    """Expected use: each ModelView is wired to the right SQLModel table."""
    assert LeadAdmin.model is Lead
    assert MessageAdmin.model is Message


def test_booking_admin_uses_distinct_identity_on_lead_model() -> None:
    """BookingAdmin shares the Lead model but lives at a separate URL.

    Without a distinct ``identity`` sqladmin would 500 on startup with a
    duplicate-route error; this test pins that down so a regression is caught
    immediately rather than at the first ``outreach serve``.
    """
    assert BookingAdmin.model is Lead
    assert BookingAdmin.identity == "booking"
    assert LeadAdmin.identity != BookingAdmin.identity


def test_parse_admin_users_two_pairs() -> None:
    """Expected use: comma-separated user:pass pairs parse correctly."""
    settings = Settings(admin_users="miracle:pw1, abdul:pw2 ")
    assert settings.parse_admin_users() == {"miracle": "pw1", "abdul": "pw2"}


def test_parse_admin_users_empty() -> None:
    """Edge case: blank ADMIN_USERS yields an empty dict, not an error."""
    assert Settings(admin_users="").parse_admin_users() == {}


def test_parse_admin_users_ignores_malformed_entries() -> None:
    """Failure case: malformed entries are skipped, not crashed on."""
    settings = Settings(admin_users="ok:fine,no-colon,:nopass,user:")
    assert settings.parse_admin_users() == {"ok": "fine"}


def _make_request_with_form(form: dict[str, str]) -> Request:
    """Build a minimal Starlette Request whose .form() returns ``form``."""

    async def receive() -> dict:
        return {"type": "http.disconnect"}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/admin/login",
        "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
        "query_string": b"",
    }
    request = Request(scope, receive=receive)
    # Monkeypatch the cached _form so calling .form() returns our dict.
    from starlette.datastructures import FormData

    request._form = FormData(form)  # type: ignore[attr-defined]
    request._session = {}  # type: ignore[attr-defined]
    return request


@pytest.mark.asyncio
async def test_login_accepts_correct_credentials() -> None:
    """Expected use: correct username + password logs the user in."""
    auth = UsernamePasswordAuth(secret_key="x" * 32, users={"miracle": "topsecret"})
    request = _make_request_with_form({"username": "miracle", "password": "topsecret"})
    request.scope["session"] = {}

    # Patch session dict access pattern used by Starlette.
    class _SessionDict(dict):
        pass

    request.scope["session"] = _SessionDict()
    # The Request.session property reads from scope["session"]; works as long
    # as SessionMiddleware would have populated it. We populate manually here.

    ok = await auth.login(request)
    assert ok is True
    assert request.scope["session"]["user"] == "miracle"


@pytest.mark.asyncio
async def test_login_rejects_wrong_password() -> None:
    """Failure case: wrong password yields False without raising."""
    auth = UsernamePasswordAuth(secret_key="x" * 32, users={"miracle": "topsecret"})
    request = _make_request_with_form({"username": "miracle", "password": "WRONG"})
    request.scope["session"] = {}
    ok = await auth.login(request)
    assert ok is False
    assert "user" not in request.scope["session"]


def _make_request_with_query(query: str) -> Request:
    """Build a Starlette Request with the given raw query string."""

    async def receive() -> dict:
        return {"type": "http.disconnect"}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/admin/lead/action",
        "headers": [],
        "query_string": query.encode("utf-8"),
    }
    return Request(scope, receive=receive)


def test_parse_pks_extracts_integers() -> None:
    """Expected use: comma-separated integer pks are parsed in order."""
    req = _make_request_with_query("pks=3,1,4,1,5")
    assert _parse_pks(req) == [3, 1, 4, 1, 5]


def test_parse_pks_handles_empty_and_garbage() -> None:
    """Edge + failure cases: empty/missing/non-numeric values are dropped."""
    assert _parse_pks(_make_request_with_query("")) == []
    assert _parse_pks(_make_request_with_query("pks=")) == []
    assert _parse_pks(_make_request_with_query("pks=foo,1,bar,2,")) == [1, 2]


@pytest.mark.asyncio
async def test_authenticate_requires_session_user() -> None:
    """Edge case: missing session entry means not authenticated."""
    auth = UsernamePasswordAuth(secret_key="x" * 32, users={"miracle": "pw"})
    request = _make_request_with_form({})
    request.scope["session"] = {}
    assert await auth.authenticate(request) is False

    request.scope["session"] = {"user": "miracle"}
    assert await auth.authenticate(request) is True

"""Tests for the :mod:`outreach.api` FastAPI router.

Covers:
    * Bearer-token auth (rejects missing/wrong tokens, accepts the right one)
    * /api/jobs/qualify happy path with an empty DB
    * /api/jobs and /api/jobs/{id} listing endpoints
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine
from sqlmodel.pool import StaticPool


API_TOKEN = "test-token-123"


@pytest.fixture()
def client(monkeypatch):
    """A FastAPI TestClient with an in-memory DB and a known API token."""
    from outreach import db, models  # noqa: F401
    from outreach.api import router
    from outreach.config import get_settings

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)

    # Override the settings token without touching the developer's .env.
    settings = get_settings()
    monkeypatch.setattr(settings, "api_token", API_TOKEN)

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        yield c


def test_missing_auth_returns_401(client):
    """Failure case: no Authorization header -> 401."""
    resp = client.post("/api/jobs/qualify", json={"limit": 1, "only_new": True})
    assert resp.status_code == 401


def test_wrong_token_returns_401(client):
    """Failure case: bad bearer token -> 401."""
    resp = client.post(
        "/api/jobs/qualify",
        json={"limit": 1, "only_new": True},
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp.status_code == 401


def test_qualify_endpoint_accepts_token_and_returns_pending_job(client):
    """Expected-use: valid token -> 202 + pending JobRun JSON."""
    resp = client.post(
        "/api/jobs/qualify",
        json={"limit": 1, "only_new": True},
        headers={"Authorization": f"Bearer {API_TOKEN}"},
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["name"] == "qualify"
    assert body["status"] in {"pending", "running", "success"}
    # The background task may or may not have finished by the time the
    # response is returned, so we don't assert on `finished_at`.


def test_list_and_get_job(client):
    """Edge case: after triggering a job, list+get endpoints find it."""
    headers = {"Authorization": f"Bearer {API_TOKEN}"}

    client.post(
        "/api/jobs/qualify",
        json={"limit": 1, "only_new": True},
        headers=headers,
    )
    # Give the BackgroundTasks queue a chance to flush.
    rows = client.get("/api/jobs", headers=headers).json()
    assert isinstance(rows, list)
    # At least the qualify run (background task may have added/replaced rows).
    assert any(r["name"] == "qualify" for r in rows)

    first_id = rows[0]["id"]
    one = client.get(f"/api/jobs/{first_id}", headers=headers).json()
    assert one["id"] == first_id


def test_send_icebreakers_requires_lead_or_batch(client):
    """Failure case: payload with no target -> 400."""
    resp = client.post(
        "/api/jobs/send-icebreakers",
        json={"batch": 0, "use_template": False},
        headers={"Authorization": f"Bearer {API_TOKEN}"},
    )
    assert resp.status_code == 400

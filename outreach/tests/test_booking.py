"""Tests for the Cal.com booking webhook integration."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime

import pytest

from outreach.booking import (
    _handle_booking_cancelled,
    _handle_booking_created,
    _handle_booking_rescheduled,
    _verify_signature,
    parse_cal_payload,
)
from outreach.crm import (
    create_or_update_lead,
    get_lead_by_booking_external_id,
)
from outreach.models import LeadSource, LeadStatus


SECRET = "shhh-its-a-secret"


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# ---------------------------------------------------------------- signature
def test_verify_signature_accepts_correct_hmac() -> None:
    """Expected use: HMAC computed with the right secret validates."""
    body = b'{"hello":"world"}'
    sig = _sign(SECRET, body)
    assert _verify_signature(SECRET, body, sig) is True


def test_verify_signature_rejects_wrong_signature() -> None:
    """Failure case: any tampering with body or signature fails."""
    body = b'{"hello":"world"}'
    assert _verify_signature(SECRET, body, "deadbeef") is False
    assert _verify_signature(SECRET, b"different", _sign(SECRET, body)) is False


def test_verify_signature_fails_closed_on_empty_inputs() -> None:
    """Edge case: empty secret or empty signature both return False."""
    body = b'{"x":1}'
    assert _verify_signature("", body, _sign(SECRET, body)) is False
    assert _verify_signature(SECRET, body, "") is False


# ------------------------------------------------------------------ parsing
def _envelope(
    event: str = "BOOKING_CREATED",
    *,
    uid: str = "abc123",
    name: str = "Jane Doe",
    email: str = "jane@example.com",
    phone: str | None = "+2348012345678",
    notes: str | None = "Looking forward to it",
    start: str = "2026-06-01T10:00:00.000Z",
    event_slug: str = "salon-audit",
    status: str = "ACCEPTED",
) -> dict:
    return {
        "triggerEvent": event,
        "createdAt": "2026-05-29T12:00:00.000Z",
        "payload": {
            "type": event_slug,
            "title": f"Salon Audit between Miracle and {name}",
            "additionalNotes": notes,
            "startTime": start,
            "endTime": "2026-06-01T11:00:00.000Z",
            "uid": uid,
            "attendees": [
                {"name": name, "email": email, "timeZone": "Africa/Lagos"}
            ],
            "responses": {
                "name": {"value": name, "label": "Your name"},
                "email": {"value": email, "label": "Email"},
                "phone": {"value": phone, "label": "Phone"} if phone else None,
                "notes": {"value": notes, "label": "Notes"} if notes else None,
            },
            "eventType": {"slug": event_slug},
            "status": status,
        },
    }


def test_parse_cal_payload_full_shape() -> None:
    """Expected use: every documented field is extracted."""
    parsed = parse_cal_payload(_envelope())
    assert parsed["uid"] == "abc123"
    assert parsed["contact_name"] == "Jane Doe"
    assert parsed["contact_email"] == "jane@example.com"
    assert parsed["phone"] == "+2348012345678"
    assert parsed["booking_event_type"] == "salon-audit"
    assert parsed["booking_status"] == "ACCEPTED"
    assert parsed["booking_notes"] == "Looking forward to it"
    assert isinstance(parsed["booking_at"], datetime)


def test_parse_cal_payload_handles_flat_response_shape() -> None:
    """Edge case: some Cal versions ship raw values, not {value: ...} dicts."""
    envelope = _envelope()
    envelope["payload"]["responses"] = {
        "name": "Solo String Jane",
        "phone": "+2349099999999",
        "notes": "flat note",
    }
    # Wipe attendees so the parser falls through to responses for name/email.
    envelope["payload"]["attendees"] = []
    parsed = parse_cal_payload(envelope)
    assert parsed["contact_name"] == "Solo String Jane"
    assert parsed["phone"] == "+2349099999999"
    assert parsed["booking_notes"] == "flat note"


def test_parse_cal_payload_missing_fields_dont_crash() -> None:
    """Failure case: an empty / minimal envelope yields all-None parsed dict."""
    parsed = parse_cal_payload({})
    assert parsed["uid"] is None
    assert parsed["contact_email"] is None
    assert parsed["booking_at"] is None


# ------------------------------------------------------------------ handlers
def test_booking_created_inserts_new_lead(session, monkeypatch) -> None:
    """Expected use: a new email creates a fresh BOOKING-source lead."""
    _patch_session_scope(monkeypatch, session)

    parsed = parse_cal_payload(_envelope(uid="new-1", email="new@example.com"))
    result = _handle_booking_created(parsed)
    session.commit()

    assert result["status"] == "ok"
    lead = get_lead_by_booking_external_id(session, "new-1")
    assert lead is not None
    assert lead.source is LeadSource.BOOKING
    assert lead.status is LeadStatus.BOOKED
    assert lead.contact_email == "new@example.com"
    assert lead.contact_name == "Jane Doe"
    assert lead.booking_event_type == "salon-audit"
    # Booking notes also produce an INBOUND Message row.
    assert lead.booking_notes == "Looking forward to it"


def test_booking_created_matches_existing_email(session, monkeypatch) -> None:
    """Edge case: booking by an already-scraped lead's email upgrades that lead.

    Avoids a duplicate row and lets us see "Lead X scraped 3 weeks ago, then
    booked themselves yesterday" — the most valuable funnel signal.
    """
    _patch_session_scope(monkeypatch, session)

    existing = create_or_update_lead(
        session,
        place_id="ChIJ-real-google-id",
        business_name="Hairitage Hub",
        contact_email="owner@hairitagehub.ng",
    )
    session.commit()
    assert existing.id is not None
    assert existing.source is LeadSource.PLACES

    parsed = parse_cal_payload(
        _envelope(uid="b-1", email="owner@hairitagehub.ng", name="Owner X")
    )
    _handle_booking_created(parsed)
    session.commit()
    session.refresh(existing)

    assert existing.status is LeadStatus.BOOKED
    assert existing.booking_external_id == "b-1"
    assert existing.contact_name == "Owner X"
    # Source stays PLACES — we don't downgrade the original signal,
    # but booking_status + booking_at flag the upgrade.
    assert existing.source is LeadSource.PLACES


def test_booking_rescheduled_updates_existing(session, monkeypatch) -> None:
    """Expected use: RESCHEDULED bumps booking_at and flips booking_status."""
    _patch_session_scope(monkeypatch, session)

    _handle_booking_created(parse_cal_payload(_envelope(uid="r-1")))
    session.commit()

    later = "2026-07-01T15:00:00.000Z"
    parsed = parse_cal_payload(
        _envelope(event="BOOKING_RESCHEDULED", uid="r-1", start=later)
    )
    result = _handle_booking_rescheduled(parsed)
    session.commit()

    lead = get_lead_by_booking_external_id(session, "r-1")
    assert result["action"] == "rescheduled"
    assert lead is not None
    assert lead.booking_status == "RESCHEDULED"
    # Hour matches the new start time.
    assert lead.booking_at is not None and lead.booking_at.hour == 15


def test_booking_cancelled_marks_existing(session, monkeypatch) -> None:
    """Failure case: cancellation flips booking_status to CANCELLED.

    Note: lead.status stays BOOKED — you may still want to follow up, and
    the dashboard surfaces booking_status separately.
    """
    _patch_session_scope(monkeypatch, session)

    _handle_booking_created(parse_cal_payload(_envelope(uid="c-1")))
    session.commit()

    parsed = parse_cal_payload(_envelope(event="BOOKING_CANCELLED", uid="c-1"))
    _handle_booking_cancelled(parsed)
    session.commit()

    lead = get_lead_by_booking_external_id(session, "c-1")
    assert lead is not None
    assert lead.booking_status == "CANCELLED"
    assert lead.status is LeadStatus.BOOKED  # unchanged


# --------------------------------------------------------------- test helpers
def _patch_session_scope(monkeypatch, session) -> None:
    """Make ``with session_scope() as s`` yield our in-memory test session.

    The handlers in :mod:`outreach.booking` call ``session_scope()``
    internally; without this patch they'd open a real engine session
    against the on-disk leads.db.
    """
    from contextlib import contextmanager

    @contextmanager
    def _fake_scope():
        # Don't commit/close — the test fixture owns the lifecycle.
        yield session

    monkeypatch.setattr("outreach.booking.session_scope", _fake_scope)

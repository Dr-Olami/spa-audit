"""Cal.com booking webhook integration.

Receives ``BOOKING_CREATED`` / ``BOOKING_RESCHEDULED`` / ``BOOKING_CANCELLED``
events from a Cal.com webhook subscription, validates the HMAC-SHA256
signature, and upserts the booking into the local CRM as a
:class:`~outreach.models.Lead` with ``source=BOOKING``.

Setup (one-time):

1. In Cal.com: **Settings -> Developer -> Webhooks -> New**.
2. Subscribe to events: ``BOOKING_CREATED``, ``BOOKING_RESCHEDULED``,
   ``BOOKING_CANCELLED``.
3. Set the URL to ``https://<your-host>/webhook/cal``.
4. Copy the webhook **Secret** into ``outreach/.env`` as
   ``CAL_WEBHOOK_SECRET=...``.
5. Restart ``outreach serve``.

The endpoint is mounted on the same FastAPI app as the WhatsApp webhook
and the admin dashboard, so a single ``outreach serve`` exposes all three.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, FastAPI, HTTPException, Request

from .config import get_settings
from .crm import (
    get_lead_by_booking_external_id,
    get_lead_by_email,
    log_message,
    upsert_booking_lead,
)
from .db import session_scope
from .models import MessageDirection

logger = logging.getLogger(__name__)

router = APIRouter()


# --------------------------------------------------------------- signature
def _verify_signature(secret: str, raw_body: bytes, signature: str) -> bool:
    """Return ``True`` iff ``signature`` matches HMAC-SHA256(secret, body).

    Uses :func:`hmac.compare_digest` to avoid timing leaks. An empty
    ``secret`` or ``signature`` always returns ``False`` (fail-closed).
    """
    if not secret or not signature:
        return False
    expected = hmac.new(
        secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature.strip())


# --------------------------------------------------------------- parsing
def _response_value(responses: Any, key: str) -> Optional[str]:
    """Extract a single field from Cal's ``responses`` dict.

    Cal's payload shape varies by version: a field may be ``"Jane"``
    directly, or a nested ``{"value": "Jane", "label": "..."}``. This
    handles both without crashing on missing/oddly-shaped fields.
    """
    if not isinstance(responses, dict):
        return None
    raw = responses.get(key)
    if raw is None:
        return None
    if isinstance(raw, dict):
        value = raw.get("value")
        return str(value) if value else None
    return str(raw) if raw else None


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    """Best-effort parse of Cal's ISO-8601 datetimes (handles ``Z`` suffix)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Could not parse Cal datetime: %r", value)
        return None


def parse_cal_payload(envelope: dict) -> dict:
    """Normalise a Cal webhook envelope into our flat upsert dict.

    Args:
        envelope: The full JSON body Cal POSTs (with ``triggerEvent`` and
            ``payload`` keys).

    Returns:
        A dict with keys ``uid``, ``contact_name``, ``contact_email``,
        ``phone``, ``booking_at``, ``booking_event_type``,
        ``booking_status``, ``booking_notes``. Missing fields are ``None``.
    """
    payload = envelope.get("payload") or {}
    attendees = payload.get("attendees") or []
    primary = attendees[0] if attendees else {}
    responses = payload.get("responses") or {}

    name = (
        primary.get("name")
        or _response_value(responses, "name")
    )
    email = (
        primary.get("email")
        or _response_value(responses, "email")
    )
    phone = (
        _response_value(responses, "phone")
        or _response_value(responses, "smsReminderNumber")
        or _response_value(responses, "attendeePhoneNumber")
    )
    notes = (
        _response_value(responses, "notes")
        or payload.get("additionalNotes")
    )
    event_type = (
        (payload.get("eventType") or {}).get("slug")
        or payload.get("type")
    )

    return {
        "uid": payload.get("uid"),
        "contact_name": name,
        "contact_email": email,
        "phone": phone,
        "booking_at": _parse_iso_datetime(payload.get("startTime")),
        "booking_event_type": event_type,
        "booking_status": payload.get("status") or "ACCEPTED",
        "booking_notes": notes,
    }


# --------------------------------------------------------------- handlers
def _handle_booking_created(parsed: dict) -> dict:
    """Create-or-update a Lead and log the booking notes as an inbound message."""
    with session_scope() as session:
        lead = upsert_booking_lead(session, parsed)
        if parsed.get("booking_notes") and lead.id is not None:
            log_message(
                session=session,
                lead_id=lead.id,
                direction=MessageDirection.INBOUND,
                body=f"[Booking note via Cal] {parsed['booking_notes']}",
                status="received",
            )
        return {"status": "ok", "action": "created", "lead_id": lead.id}


def _handle_booking_rescheduled(parsed: dict) -> dict:
    """Update ``booking_at`` on an existing Lead, or create one if unmatched."""
    with session_scope() as session:
        existing = None
        if parsed.get("uid"):
            existing = get_lead_by_booking_external_id(session, parsed["uid"])
        if existing is None and parsed.get("contact_email"):
            existing = get_lead_by_email(session, parsed["contact_email"])
        if existing is None:
            # Fall through to "create" so we still capture the booking.
            return _handle_booking_created(parsed)
        if parsed.get("booking_at"):
            existing.booking_at = parsed["booking_at"]
        if parsed.get("uid"):
            existing.booking_external_id = parsed["uid"]
        existing.booking_status = "RESCHEDULED"
        existing.updated_at = datetime.utcnow()
        session.add(existing)
        return {"status": "ok", "action": "rescheduled", "lead_id": existing.id}


def _handle_booking_cancelled(parsed: dict) -> dict:
    """Mark the booking cancelled (lead.status stays BOOKED — you may follow up)."""
    with session_scope() as session:
        existing = None
        if parsed.get("uid"):
            existing = get_lead_by_booking_external_id(session, parsed["uid"])
        if existing is None and parsed.get("contact_email"):
            existing = get_lead_by_email(session, parsed["contact_email"])
        if existing is None:
            logger.warning(
                "Cal cancellation for unknown booking uid=%s email=%s",
                parsed.get("uid"),
                parsed.get("contact_email"),
            )
            return {"status": "not_found"}
        existing.booking_status = "CANCELLED"
        existing.updated_at = datetime.utcnow()
        session.add(existing)
        return {"status": "ok", "action": "cancelled", "lead_id": existing.id}


# --------------------------------------------------------------- route
@router.post("/webhook/cal")
async def cal_webhook(request: Request) -> dict:
    """Receive a Cal.com webhook, validate signature, dispatch to handler."""
    settings = get_settings()
    raw_body = await request.body()

    if settings.cal_webhook_secret:
        signature = request.headers.get("X-Cal-Signature-256", "")
        if not _verify_signature(
            settings.cal_webhook_secret, raw_body, signature
        ):
            logger.warning("Cal webhook: rejected request with bad signature")
            raise HTTPException(status_code=403, detail="Invalid Cal signature")
    else:
        logger.warning(
            "CAL_WEBHOOK_SECRET is empty — accepting Cal webhook without "
            "signature validation. Only safe for local development."
        )

    try:
        envelope = json.loads(raw_body.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}")

    event = envelope.get("triggerEvent") or envelope.get("event") or ""
    parsed = parse_cal_payload(envelope)
    logger.info(
        "Cal webhook event=%s uid=%s email=%s",
        event,
        parsed.get("uid"),
        parsed.get("contact_email"),
    )

    if event == "BOOKING_CREATED":
        return _handle_booking_created(parsed)
    if event == "BOOKING_RESCHEDULED":
        return _handle_booking_rescheduled(parsed)
    if event == "BOOKING_CANCELLED":
        return _handle_booking_cancelled(parsed)

    logger.info("Cal webhook: ignoring unhandled event %r", event)
    return {"status": "ignored", "event": event}


# --------------------------------------------------------------- setup
def setup_booking_webhook(app: FastAPI) -> None:
    """Mount the ``/webhook/cal`` route on ``app``."""
    app.include_router(router)

"""FastAPI webhook that records inbound WhatsApp messages from Twilio.

Twilio will POST ``application/x-www-form-urlencoded`` to this endpoint when a
lead replies. We persist the reply, flip the lead to ``REPLIED``, and answer
with an empty TwiML response (you can also reply automatically — see
``AUTO_REPLY`` below).

Run with:

    uvicorn outreach.whatsapp.webhook:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request, Response
from twilio.request_validator import RequestValidator

from ..config import get_settings
from ..crm import get_lead_by_phone, log_message
from ..db import init_db, session_scope
from ..models import MessageDirection

logger = logging.getLogger(__name__)

app = FastAPI(title="Salon Outreach — WhatsApp webhook + admin")

# Mount the sqladmin CRUD dashboard at /admin, the Cal.com booking webhook
# at /webhook/cal, and the jobs HTTP API at /api on the same FastAPI app.
# Imported lazily after `app` exists to avoid a circular import.
from ..admin import setup_admin  # noqa: E402
from ..api import router as api_router  # noqa: E402
from ..booking import setup_booking_webhook  # noqa: E402
from ..scheduler import shutdown_scheduler, start_scheduler  # noqa: E402

setup_admin(app)
setup_booking_webhook(app)
app.include_router(api_router)

AUTO_REPLY: Optional[str] = (
    "Thanks for replying! A real human from our team will get back to you "
    "shortly. Meanwhile, here's a 1-min overview: https://your-domain.com"
)


@app.on_event("startup")
def _startup() -> None:
    """Make sure tables exist + start the background scheduler."""
    init_db()
    start_scheduler()


@app.on_event("shutdown")
def _shutdown() -> None:
    """Stop the background scheduler cleanly on FastAPI shutdown."""
    shutdown_scheduler()


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(""),
    MessageSid: str = Form(""),
    ProfileName: str = Form(""),
) -> Response:
    """Receive an inbound WhatsApp message from Twilio.

    Args:
        From: WhatsApp address of the sender, e.g. ``whatsapp:+234...``.
        Body: Message text.
        MessageSid: Twilio message SID.
        ProfileName: WhatsApp display name of the sender.
    """
    settings = get_settings()

    if settings.twilio_webhook_validate:
        _validate_twilio_signature(request, settings.twilio_auth_token)

    phone = From.replace("whatsapp:", "").strip()
    logger.info("Inbound WhatsApp from %s (%s): %s", phone, ProfileName, Body)

    with session_scope() as session:
        lead = get_lead_by_phone(session, phone)
        if lead is None or lead.id is None:
            logger.warning("Inbound from unknown number %s", phone)
        else:
            log_message(
                session=session,
                lead_id=lead.id,
                direction=MessageDirection.INBOUND,
                body=Body,
                twilio_sid=MessageSid or None,
                status="received",
            )

    # Empty TwiML = no automatic reply. Set AUTO_REPLY to send one instead.
    if AUTO_REPLY:
        twiml = (
            "<?xml version='1.0' encoding='UTF-8'?>"
            f"<Response><Message>{AUTO_REPLY}</Message></Response>"
        )
    else:
        twiml = "<?xml version='1.0' encoding='UTF-8'?><Response></Response>"
    return Response(content=twiml, media_type="application/xml")


async def _validate_twilio_signature(request: Request, auth_token: str) -> None:
    """Reject requests whose ``X-Twilio-Signature`` header does not validate."""
    signature = request.headers.get("X-Twilio-Signature", "")
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    url = str(request.url)
    validator = RequestValidator(auth_token)
    if not validator.validate(url, params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

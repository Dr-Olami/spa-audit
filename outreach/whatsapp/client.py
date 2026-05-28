"""Twilio WhatsApp client wrapper."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from ..config import get_settings

logger = logging.getLogger(__name__)


def format_whatsapp_address(phone: str) -> str:
    """Return a Twilio-style WhatsApp address (``whatsapp:+<E.164>``).

    Args:
        phone: Phone number, with or without ``whatsapp:`` prefix.

    Raises:
        ValueError: If the number cannot be coerced into E.164.
    """
    if not phone:
        raise ValueError("phone is required")
    p = phone.strip()
    if p.startswith("whatsapp:"):
        return p
    if not p.startswith("+"):
        # Naive default: caller must provide E.164; reject otherwise.
        raise ValueError(f"phone must be E.164 (start with '+'): {phone!r}")
    return f"whatsapp:{p}"


@dataclass(slots=True)
class SendResult:
    """Result of attempting to send a WhatsApp message."""

    sid: Optional[str]
    status: str  # 'sent' | 'queued' | 'failed'
    error: Optional[str] = None


class TwilioWhatsAppClient:
    """Thin wrapper around :class:`twilio.rest.Client` for WhatsApp sends."""

    def __init__(self, client: Optional[Client] = None) -> None:
        settings = get_settings()
        self._settings = settings
        if client is not None:
            self._client = client
        else:
            if not settings.twilio_account_sid or not settings.twilio_auth_token:
                raise RuntimeError(
                    "TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set."
                )
            self._client = Client(
                settings.twilio_account_sid, settings.twilio_auth_token
            )

    # ------------------------------------------------------------------ sends
    def send_freeform(self, to_phone: str, body: str) -> SendResult:
        """Send a freeform message.

        Works in the Twilio sandbox or inside the 24h customer-service window
        after a lead has replied. Will be silently dropped by Meta otherwise.
        """
        return self._send(to_phone=to_phone, body=body, content_sid=None, variables=None)

    def send_template(
        self,
        to_phone: str,
        content_sid: str,
        variables: dict[str, str],
    ) -> SendResult:
        """Send a Meta-approved Content template.

        Use this for the first cold-outreach touch in production.
        """
        if not content_sid:
            raise ValueError("content_sid is required for template sends")
        return self._send(
            to_phone=to_phone, body=None, content_sid=content_sid, variables=variables
        )

    # ----------------------------------------------------------------- internal
    def _send(
        self,
        *,
        to_phone: str,
        body: Optional[str],
        content_sid: Optional[str],
        variables: Optional[dict[str, str]],
    ) -> SendResult:
        to = format_whatsapp_address(to_phone)
        sender = self._settings.whatsapp_sender
        try:
            kwargs: dict = {"from_": sender, "to": to}
            if content_sid:
                kwargs["content_sid"] = content_sid
                if variables:
                    kwargs["content_variables"] = json.dumps(variables)
            else:
                kwargs["body"] = body or ""
            message = self._client.messages.create(**kwargs)
            return SendResult(sid=message.sid, status=message.status or "queued")
        except TwilioRestException as exc:
            logger.exception("Twilio send failed for %s", to)
            return SendResult(sid=None, status="failed", error=str(exc))

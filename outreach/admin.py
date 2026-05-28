"""sqladmin-powered CRUD dashboard mounted at ``/admin``.

Exposes ``Lead`` and ``Message`` with list / search / filter / create /
edit / delete views. Multi-user safe (per-request SQLAlchemy session) with
form-based username/password authentication backed by a signed session
cookie.

Mounted from :mod:`outreach.whatsapp.webhook` at module import time so a
single ``outreach serve`` exposes the webhook and the dashboard on the
same port.
"""
from __future__ import annotations

import logging
import secrets
from typing import Optional

from fastapi import FastAPI
from sqladmin import Admin, ModelView, action
from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse

from .admin_jobs import JobRunAdmin, JobsControlView
from .config import get_settings
from .crm import log_message
from .db import engine, session_scope
from .models import Lead, LeadSource, LeadStatus, Message, MessageDirection
from .whatsapp import (
    TwilioWhatsAppClient,
    build_followup_link,
    build_icebreaker_freeform,
)
from .whatsapp.templates import build_template_variables_icebreaker

# Hard cap on how many leads a single bulk-action click may message.
# Protects against accidental 200-row blasts and request timeouts.
MAX_BULK_SEND = 10

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------- views
class LeadAdmin(ModelView, model=Lead):
    """CRUD view for the ``leads`` table."""

    name = "Lead"
    name_plural = "Leads"
    icon = "fa-solid fa-user-group"
    category = "CRM"

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    column_list = [
        Lead.id,
        Lead.business_name,
        Lead.source,
        Lead.status,
        Lead.qualification_score,
        Lead.contact_name,
        Lead.contact_email,
        Lead.booking_at,
        Lead.city,
        Lead.phone,
        Lead.rating,
        Lead.has_website,
        Lead.has_booking_system,
        Lead.last_message_sent_at,
        Lead.last_reply_at,
        Lead.updated_at,
    ]
    column_details_list = [
        Lead.id,
        Lead.source,
        Lead.place_id,
        Lead.business_name,
        Lead.category,
        Lead.status,
        Lead.qualification_score,
        Lead.qualification_notes,
        # Booking fields ------------------------------------------------
        Lead.contact_name,
        Lead.contact_email,
        Lead.booking_at,
        Lead.booking_event_type,
        Lead.booking_status,
        Lead.booking_external_id,
        Lead.booking_notes,
        # Business fields -----------------------------------------------
        Lead.city,
        Lead.address,
        Lead.phone,
        Lead.website,
        Lead.google_maps_url,
        Lead.instagram_handle,
        Lead.rating,
        Lead.review_count,
        Lead.has_website,
        Lead.has_booking_system,
        Lead.last_message_sent_at,
        Lead.last_reply_at,
        Lead.last_reply_text,
        Lead.notes,
        Lead.created_at,
        Lead.updated_at,
    ]
    form_columns = [
        Lead.business_name,
        Lead.source,
        Lead.category,
        Lead.contact_name,
        Lead.contact_email,
        Lead.city,
        Lead.address,
        Lead.phone,
        Lead.website,
        Lead.instagram_handle,
        Lead.status,
        Lead.qualification_score,
        Lead.qualification_notes,
        Lead.has_website,
        Lead.has_booking_system,
        Lead.rating,
        Lead.review_count,
        Lead.notes,
    ]

    column_searchable_list = [
        Lead.business_name,
        Lead.phone,
        Lead.address,
        Lead.contact_email,
        Lead.contact_name,
    ]
    column_sortable_list = [
        Lead.qualification_score,
        Lead.rating,
        Lead.review_count,
        Lead.updated_at,
        Lead.last_reply_at,
        Lead.booking_at,
        Lead.status,
        Lead.source,
    ]
    column_default_sort = [(Lead.qualification_score, True), (Lead.updated_at, True)]

    can_create = True
    can_edit = True
    can_delete = True
    can_export = True

    # ---------------------------------------------------------- bulk actions
    @action(
        name="send_icebreaker",
        label="Send Icebreaker (WhatsApp)",
        confirmation_message=(
            "Send the WhatsApp icebreaker to the selected lead(s)? "
            f"At most {MAX_BULK_SEND} will be sent per click."
        ),
        add_in_detail=True,
        add_in_list=True,
    )
    async def send_icebreaker_action(self, request: Request) -> RedirectResponse:
        """Send the icebreaker via Twilio. Auto-picks freeform vs template.

        Reads :data:`TWILIO_USE_SANDBOX` from settings:
            - sandbox -> freeform message (sandbox sender)
            - production -> Meta-approved template (TWILIO_TEMPLATE_ICEBREAKER_SID)
        """
        ids = _parse_pks(request)
        if not ids:
            return _redirect_back(request, self.identity)

        settings = get_settings()
        client = TwilioWhatsAppClient()
        sent = failed = skipped = 0

        with session_scope() as session:
            for lead_id in ids[:MAX_BULK_SEND]:
                lead = session.get(Lead, lead_id)
                if lead is None or not lead.phone or lead.id is None:
                    skipped += 1
                    continue
                body = build_icebreaker_freeform(lead.business_name)
                try:
                    if settings.twilio_use_sandbox:
                        result = client.send_freeform(lead.phone, body)
                    else:
                        if not settings.twilio_template_icebreaker_sid:
                            logger.warning(
                                "Lead %s skipped: production mode but "
                                "TWILIO_TEMPLATE_ICEBREAKER_SID is empty.",
                                lead_id,
                            )
                            skipped += 1
                            continue
                        result = client.send_template(
                            lead.phone,
                            content_sid=settings.twilio_template_icebreaker_sid,
                            variables=build_template_variables_icebreaker(
                                lead.business_name
                            ),
                        )
                    log_message(
                        session=session,
                        lead_id=lead.id,
                        direction=MessageDirection.OUTBOUND,
                        body=body,
                        twilio_sid=result.sid,
                        status=result.status,
                    )
                    if result.sid:
                        sent += 1
                    else:
                        failed += 1
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "send_icebreaker failed for lead %s", lead_id
                    )
                    failed += 1

        logger.info(
            "Icebreaker bulk action: sent=%d failed=%d skipped=%d (of %d ids)",
            sent,
            failed,
            skipped,
            len(ids),
        )
        return _redirect_back(request, self.identity)

    @action(
        name="send_followup",
        label="Send Follow-up Link (WhatsApp)",
        confirmation_message=(
            "Send the landing-page + Cal link to the selected lead(s)? "
            "Only valid for leads who replied within the last 24h."
        ),
        add_in_detail=True,
        add_in_list=True,
    )
    async def send_followup_action(self, request: Request) -> RedirectResponse:
        """Send the second-touch follow-up message (landing + Cal link).

        Always freeform: this is the post-reply response within the
        24-hour customer-service window where Twilio allows freeform.
        """
        ids = _parse_pks(request)
        if not ids:
            return _redirect_back(request, self.identity)

        settings = get_settings()
        client = TwilioWhatsAppClient()
        body = build_followup_link(settings.landing_url, settings.cal_url)
        sent = failed = skipped = 0

        with session_scope() as session:
            for lead_id in ids[:MAX_BULK_SEND]:
                lead = session.get(Lead, lead_id)
                if lead is None or not lead.phone or lead.id is None:
                    skipped += 1
                    continue
                try:
                    result = client.send_freeform(lead.phone, body)
                    log_message(
                        session=session,
                        lead_id=lead.id,
                        direction=MessageDirection.OUTBOUND,
                        body=body,
                        twilio_sid=result.sid,
                        status=result.status,
                    )
                    if result.sid:
                        sent += 1
                    else:
                        failed += 1
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "send_followup failed for lead %s", lead_id
                    )
                    failed += 1

        logger.info(
            "Follow-up bulk action: sent=%d failed=%d skipped=%d (of %d ids)",
            sent,
            failed,
            skipped,
            len(ids),
        )
        return _redirect_back(request, self.identity)

    @action(
        name="mark_not_interested",
        label="Mark Not Interested",
        confirmation_message="Mark the selected lead(s) as NOT_INTERESTED?",
        add_in_detail=True,
        add_in_list=True,
    )
    async def mark_not_interested_action(
        self, request: Request
    ) -> RedirectResponse:
        """Move the selected leads to ``NOT_INTERESTED`` status."""
        ids = _parse_pks(request)
        if not ids:
            return _redirect_back(request, self.identity)
        with session_scope() as session:
            for lead_id in ids:
                lead = session.get(Lead, lead_id)
                if lead is not None:
                    lead.status = LeadStatus.NOT_INTERESTED
                    session.add(lead)
        return _redirect_back(request, self.identity)


class BookingAdmin(LeadAdmin, model=Lead):
    """Pre-filtered Leads view: only ``source=BOOKING`` rows.

    Reuses every column / action / search config from :class:`LeadAdmin`.
    The only differences are:

    - Distinct ``identity`` so it lives at ``/admin/booking/list`` instead
      of clashing with the main Leads URL. sqladmin's metaclass overwrites
      ``identity`` from the model name when ``model=`` is passed, so we
      re-assign it below the class body to make the override stick.
    - Overridden :meth:`list_query` adds a ``WHERE source = BOOKING`` clause.
    - Default sort is by ``booking_at`` desc (next booking first).
    """

    name = "Booking"
    name_plural = "Bookings"
    icon = "fa-solid fa-calendar-check"
    category = "CRM"

    # Newest / soonest booking first (sqladmin's tuple = (col, desc)).
    column_default_sort = [(Lead.booking_at, True)]

    def list_query(self, request: Request):
        """Filter the base list query down to self-booked leads only."""
        query = super().list_query(request)
        return query.where(Lead.source == LeadSource.BOOKING)


# Reason: sqladmin's ModelViewMeta.__new__ (sqladmin/models.py line ~103)
# unconditionally sets ``cls.identity = slugify_class_name(model.__name__)``
# whenever ``model=`` is supplied via class kwargs, ignoring any value set
# in the class body. We override after the class is built so the URL stays
# ``/admin/booking/list`` and doesn't collide with ``/admin/lead/list``.
BookingAdmin.identity = "booking"


class MessageAdmin(ModelView, model=Message):
    """CRUD view for the ``messages`` audit log."""

    name = "Message"
    name_plural = "Messages"
    icon = "fa-solid fa-comment"
    category = "CRM"

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    column_list = [
        Message.id,
        Message.lead_id,
        Message.direction,
        Message.body,
        Message.status,
        Message.twilio_sid,
        Message.created_at,
    ]
    column_details_list = [
        Message.id,
        Message.lead_id,
        Message.direction,
        Message.body,
        Message.status,
        Message.twilio_sid,
        Message.created_at,
    ]
    form_columns = [
        Message.lead_id,
        Message.direction,
        Message.body,
        Message.status,
        Message.twilio_sid,
    ]
    column_searchable_list = [Message.body, Message.twilio_sid]
    column_sortable_list = [Message.created_at, Message.lead_id, Message.direction]
    column_default_sort = [(Message.created_at, True)]

    can_create = True
    can_edit = True
    can_delete = True
    can_export = True




# ------------------------------------------------------------ authentication
class UsernamePasswordAuth(AuthenticationBackend):
    """Simple form-based auth against a static ``{user: password}`` map.

    Passwords are compared with :func:`secrets.compare_digest` to avoid
    timing leaks. For two trusted teammates this is plenty; swap in OAuth
    or a hashed-password store if the team grows.
    """

    def __init__(self, secret_key: str, users: dict[str, str]) -> None:
        super().__init__(secret_key=secret_key)
        self._users = users

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username = str(form.get("username", "")).strip()
        password = str(form.get("password", ""))
        expected = self._users.get(username)
        if expected is None:
            return False
        if not secrets.compare_digest(password, expected):
            return False
        request.session["user"] = username
        return True

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        return "user" in request.session


# ----------------------------------------------------------------- helpers
def _parse_pks(request: Request) -> list[int]:
    """Return the list of integer primary keys selected for a bulk action.

    sqladmin packs them into the ``pks`` query string as comma-separated.
    """
    raw = request.query_params.get("pks", "")
    return [int(p) for p in raw.split(",") if p.strip().isdigit()]


def _redirect_back(request: Request, identity: str) -> RedirectResponse:
    """Redirect to the page the action was invoked from, or the list view."""
    referer = request.headers.get("referer")
    if referer:
        return RedirectResponse(referer, status_code=302)
    return RedirectResponse(
        request.url_for("admin:list", identity=identity), status_code=302
    )


# ---------------------------------------------------------------------- setup
def setup_admin(app: FastAPI) -> Admin:
    """Mount the admin on ``app`` at ``/admin`` and return the :class:`Admin`.

    Reads ``ADMIN_USERS`` and ``ADMIN_SESSION_SECRET`` from settings. If no
    users are configured, the admin is still mounted but **without auth**;
    a loud warning is logged. Do not expose that mode outside localhost.
    """
    settings = get_settings()
    users = settings.parse_admin_users()
    secret = settings.admin_session_secret or secrets.token_urlsafe(32)

    auth_backend: Optional[AuthenticationBackend]
    if users:
        if not settings.admin_session_secret:
            logger.warning(
                "ADMIN_SESSION_SECRET is empty; generated an ephemeral one. "
                "Sessions will not survive a restart -- set ADMIN_SESSION_SECRET in .env."
            )
        auth_backend = UsernamePasswordAuth(secret_key=secret, users=users)
    else:
        logger.warning(
            "ADMIN_USERS is empty -- /admin is mounted WITHOUT authentication. "
            "Only safe for localhost; set ADMIN_USERS=user:pass,... in .env before exposing."
        )
        auth_backend = None

    admin = Admin(
        app=app,
        engine=engine,
        title="Salon & Spa Outreach",
        base_url="/admin",
        authentication_backend=auth_backend,
    )
    admin.add_view(LeadAdmin)
    admin.add_view(BookingAdmin)
    admin.add_view(MessageAdmin)
    admin.add_view(JobRunAdmin)
    admin.add_view(JobsControlView)
    return admin

"""CRUD operations over the Lead and Message tables."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Session, select

from ..models import Lead, LeadSource, LeadStatus, Message, MessageDirection


def get_lead(session: Session, lead_id: int) -> Optional[Lead]:
    """Fetch a lead by primary key."""
    return session.get(Lead, lead_id)


def get_lead_by_place_id(session: Session, place_id: str) -> Optional[Lead]:
    """Fetch a lead by its Google ``place_id``."""
    statement = select(Lead).where(Lead.place_id == place_id)
    return session.exec(statement).first()


def get_lead_by_phone(session: Session, phone: str) -> Optional[Lead]:
    """Fetch a lead by phone number (E.164, no ``whatsapp:`` prefix).

    Args:
        session: Active SQLModel session.
        phone: E.164 phone number, e.g. ``+2348012345678``.
    """
    statement = select(Lead).where(Lead.phone == phone)
    return session.exec(statement).first()


def get_lead_by_email(session: Session, email: str) -> Optional[Lead]:
    """Fetch a lead by ``contact_email`` (used when matching Cal.com bookings)."""
    statement = select(Lead).where(Lead.contact_email == email)
    return session.exec(statement).first()


def get_lead_by_booking_external_id(
    session: Session, booking_id: str
) -> Optional[Lead]:
    """Fetch a lead by Cal.com booking UID (used for reschedule / cancel)."""
    statement = select(Lead).where(Lead.booking_external_id == booking_id)
    return session.exec(statement).first()


def list_leads(
    session: Session,
    status: Optional[LeadStatus] = None,
    city: Optional[str] = None,
    limit: int = 200,
) -> list[Lead]:
    """List leads filtered by status and / or city."""
    statement = select(Lead)
    if status is not None:
        statement = statement.where(Lead.status == status)
    if city is not None:
        statement = statement.where(Lead.city == city)
    statement = statement.order_by(Lead.qualification_score.desc(), Lead.id.desc()).limit(limit)
    return list(session.exec(statement).all())


def create_or_update_lead(session: Session, **fields) -> Lead:
    """Insert or update a lead keyed by ``place_id``.

    Args:
        session: Active SQLModel session.
        **fields: Lead column values; ``place_id`` is required.

    Returns:
        The persisted :class:`Lead` instance.
    """
    place_id = fields.get("place_id")
    if not place_id:
        raise ValueError("place_id is required")

    existing = get_lead_by_place_id(session, place_id)
    if existing is None:
        lead = Lead(**fields)
        session.add(lead)
        session.flush()
        return lead

    for key, value in fields.items():
        if value is not None and hasattr(existing, key):
            setattr(existing, key, value)
    existing.updated_at = datetime.utcnow()
    session.add(existing)
    session.flush()
    return existing


def update_lead_status(
    session: Session,
    lead_id: int,
    status: LeadStatus,
    note: Optional[str] = None,
) -> Optional[Lead]:
    """Set a lead's status (and optional note) and bump ``updated_at``."""
    lead = session.get(Lead, lead_id)
    if lead is None:
        return None
    lead.status = status
    if note:
        lead.notes = ((lead.notes + "\n") if lead.notes else "") + note
    lead.updated_at = datetime.utcnow()
    session.add(lead)
    return lead


def upsert_booking_lead(session: Session, parsed: dict) -> Lead:
    """Find or create a :class:`Lead` from a parsed Cal.com booking payload.

    Match priority:
        1. ``booking_external_id`` (handles reschedules / cancellations).
        2. ``contact_email``.
        3. ``phone``.
        4. Otherwise, create a new lead with ``source=BOOKING``.

    The matched-or-created lead always has booking fields applied and is
    advanced to :attr:`LeadStatus.BOOKED`.

    Args:
        session: Active SQLModel session.
        parsed: Dict produced by :func:`outreach.booking.parse_cal_payload`
            with keys ``uid``, ``contact_name``, ``contact_email``, ``phone``,
            ``booking_at``, ``booking_event_type``, ``booking_status``,
            ``booking_notes``.
    """
    existing: Optional[Lead] = None
    if parsed.get("uid"):
        existing = get_lead_by_booking_external_id(session, parsed["uid"])
    if existing is None and parsed.get("contact_email"):
        existing = get_lead_by_email(session, parsed["contact_email"])
    if existing is None and parsed.get("phone"):
        existing = get_lead_by_phone(session, parsed["phone"])

    if existing is not None:
        return _apply_booking_fields(session, existing, parsed)

    # Create a fresh lead. Synthetic place_id keeps the unique index happy
    # without colliding with any real Google Place ID (which never start
    # with "cal:").
    uid = parsed.get("uid") or datetime.utcnow().isoformat()
    name = (
        parsed.get("contact_name")
        or parsed.get("contact_email")
        or "Unknown booker"
    )
    lead = Lead(
        place_id=f"cal:{uid}",
        business_name=name,
        contact_name=parsed.get("contact_name"),
        contact_email=parsed.get("contact_email"),
        phone=parsed.get("phone"),
        source=LeadSource.BOOKING,
        status=LeadStatus.BOOKED,
        booking_at=parsed.get("booking_at"),
        booking_event_type=parsed.get("booking_event_type"),
        booking_status=parsed.get("booking_status") or "ACCEPTED",
        booking_external_id=parsed.get("uid"),
        booking_notes=parsed.get("booking_notes"),
    )
    session.add(lead)
    session.flush()
    return lead


def _apply_booking_fields(
    session: Session, lead: Lead, parsed: dict
) -> Lead:
    """Copy booking fields onto an existing lead and bump status to BOOKED."""
    if parsed.get("contact_name"):
        lead.contact_name = parsed["contact_name"]
    if parsed.get("contact_email"):
        lead.contact_email = parsed["contact_email"]
    if parsed.get("phone") and not lead.phone:
        # Don't clobber a phone we already verified; only fill if missing.
        lead.phone = parsed["phone"]
    if parsed.get("booking_at"):
        lead.booking_at = parsed["booking_at"]
    if parsed.get("booking_event_type"):
        lead.booking_event_type = parsed["booking_event_type"]
    if parsed.get("booking_status"):
        lead.booking_status = parsed["booking_status"]
    if parsed.get("uid"):
        lead.booking_external_id = parsed["uid"]
    if parsed.get("booking_notes"):
        lead.booking_notes = parsed["booking_notes"]
    lead.status = LeadStatus.BOOKED
    lead.updated_at = datetime.utcnow()
    session.add(lead)
    session.flush()
    return lead


def log_message(
    session: Session,
    lead_id: int,
    direction: MessageDirection,
    body: str,
    twilio_sid: Optional[str] = None,
    status: Optional[str] = None,
) -> Message:
    """Persist an outbound or inbound WhatsApp message and update the lead."""
    msg = Message(
        lead_id=lead_id,
        direction=direction,
        body=body,
        twilio_sid=twilio_sid,
        status=status,
    )
    session.add(msg)

    lead = session.get(Lead, lead_id)
    if lead is not None:
        now = datetime.utcnow()
        if direction is MessageDirection.OUTBOUND:
            lead.last_message_sent_at = now
            if lead.status in (LeadStatus.NEW, LeadStatus.QUALIFIED):
                lead.status = LeadStatus.CONTACTED
        else:
            lead.last_reply_at = now
            lead.last_reply_text = body
            if lead.status in (LeadStatus.CONTACTED, LeadStatus.QUALIFIED, LeadStatus.NEW):
                lead.status = LeadStatus.REPLIED
        lead.updated_at = now
        session.add(lead)
    return msg

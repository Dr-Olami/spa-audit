"""SQLModel tables for the outreach CRM."""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class LeadStatus(str, enum.Enum):
    """Lifecycle states for a lead."""

    NEW = "new"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    REPLIED = "replied"
    BOOKED = "booked"
    NOT_INTERESTED = "not_interested"
    BOUNCED = "bounced"
    SKIPPED = "skipped"


class LeadSource(str, enum.Enum):
    """Where the lead originated.

    Lets us tell scraped prospects apart from people who walked into the
    funnel themselves (booked the free audit, filled the contact form,
    DM'd us on Instagram).
    """

    PLACES = "places"        # Google Places API scrape
    BOOKING = "booking"      # Self-booked via Cal.com webhook
    MANUAL = "manual"        # Hand-added in the admin dashboard
    INSTAGRAM = "instagram"  # Future: IG DM / referral


class MessageDirection(str, enum.Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class Lead(SQLModel, table=True):
    """A salon / spa business we are reaching out to.

    Indexed by Google ``place_id`` to make re-scrapes idempotent.
    """

    __tablename__ = "leads"

    id: Optional[int] = Field(default=None, primary_key=True)
    place_id: str = Field(index=True, unique=True)
    business_name: str
    category: Optional[str] = None
    city: Optional[str] = Field(default=None, index=True)
    address: Optional[str] = None
    phone: Optional[str] = Field(default=None, index=True)
    website: Optional[str] = None
    google_maps_url: Optional[str] = None
    instagram_handle: Optional[str] = None

    rating: Optional[float] = None
    review_count: Optional[int] = None

    has_website: bool = False
    has_booking_system: bool = False
    qualification_score: int = 0
    qualification_notes: Optional[str] = None

    status: LeadStatus = Field(default=LeadStatus.NEW, index=True)
    last_message_sent_at: Optional[datetime] = None
    last_reply_at: Optional[datetime] = None
    last_reply_text: Optional[str] = None

    notes: Optional[str] = None

    # Provenance / segmentation -------------------------------------------
    source: LeadSource = Field(default=LeadSource.PLACES, index=True)

    # Self-booking fields (populated by Cal.com webhook) ------------------
    contact_name: Optional[str] = None
    contact_email: Optional[str] = Field(default=None, index=True)
    booking_at: Optional[datetime] = None
    booking_event_type: Optional[str] = None  # Cal event slug, e.g. "salon-audit"
    booking_status: Optional[str] = None      # ACCEPTED|RESCHEDULED|CANCELLED
    booking_external_id: Optional[str] = Field(default=None, index=True)
    booking_notes: Optional[str] = None       # "Notes to host" from the booking form

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class JobStatus(str, enum.Enum):
    """Lifecycle states for a background job run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class JobRun(SQLModel, table=True):
    """Audit trail for every scrape / qualify / send job triggered.

    A job is created in ``PENDING`` state, flipped to ``RUNNING`` when the
    worker picks it up, and finally ``SUCCESS`` / ``FAILED`` with a one-line
    ``summary`` (or ``error`` traceback). Drives the dashboard's job log.
    """

    __tablename__ = "job_runs"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)              # e.g. "scrape", "qualify", "send_icebreaker"
    trigger: str = Field(default="manual")     # "manual" | "api" | "scheduler"
    status: JobStatus = Field(default=JobStatus.PENDING, index=True)
    params_json: Optional[str] = None          # JSON-encoded input params
    summary: Optional[str] = None              # Short success message
    error: Optional[str] = None                # Exception message on failure
    items_processed: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    finished_at: Optional[datetime] = None


class Message(SQLModel, table=True):
    """A WhatsApp message we sent or received for a lead."""

    __tablename__ = "messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    lead_id: int = Field(foreign_key="leads.id", index=True)
    direction: MessageDirection
    body: str
    twilio_sid: Optional[str] = Field(default=None, index=True)
    status: Optional[str] = None  # queued | sent | delivered | read | failed
    created_at: datetime = Field(default_factory=datetime.utcnow)

"""Tests for CRUD operations in outreach.crm.repo."""
import pytest

from outreach.crm import (
    create_or_update_lead,
    get_lead_by_place_id,
    list_leads,
    log_message,
    update_lead_status,
)
from outreach.models import LeadStatus, MessageDirection


def test_create_or_update_lead_inserts_then_updates(session) -> None:
    """Expected use: same place_id upserts in place."""
    lead = create_or_update_lead(
        session, place_id="p1", business_name="A", rating=4.0
    )
    session.commit()
    assert lead.business_name == "A"

    again = create_or_update_lead(
        session, place_id="p1", business_name="A renamed", rating=4.5
    )
    session.commit()
    assert again.id == lead.id
    assert again.business_name == "A renamed"
    assert again.rating == 4.5


def test_list_leads_filters_by_status(session) -> None:
    """Edge case: list_leads honours the status filter."""
    create_or_update_lead(session, place_id="p1", business_name="A")
    create_or_update_lead(
        session, place_id="p2", business_name="B", qualification_score=80
    )
    session.commit()

    qualified = list_leads(session, status=LeadStatus.QUALIFIED)
    assert qualified == []

    new_leads = list_leads(session, status=LeadStatus.NEW)
    # Highest qualification_score comes first.
    assert new_leads[0].business_name == "B"


def test_log_message_outbound_moves_lead_to_contacted(session) -> None:
    """Expected use: an outbound message flips a NEW lead to CONTACTED."""
    lead = create_or_update_lead(session, place_id="p1", business_name="A")
    session.commit()
    assert lead.id is not None

    log_message(
        session,
        lead_id=lead.id,
        direction=MessageDirection.OUTBOUND,
        body="hi",
        twilio_sid="SMxxx",
        status="queued",
    )
    session.commit()
    session.refresh(lead)
    assert lead.status is LeadStatus.CONTACTED
    assert lead.last_message_sent_at is not None


def test_log_message_inbound_moves_lead_to_replied(session) -> None:
    """An inbound message flips CONTACTED -> REPLIED and stores the body."""
    lead = create_or_update_lead(session, place_id="p1", business_name="A")
    session.commit()
    assert lead.id is not None

    update_lead_status(session, lead.id, LeadStatus.CONTACTED)
    session.commit()

    log_message(
        session,
        lead_id=lead.id,
        direction=MessageDirection.INBOUND,
        body="yes please send it",
    )
    session.commit()
    session.refresh(lead)
    assert lead.status is LeadStatus.REPLIED
    assert lead.last_reply_text == "yes please send it"


def test_create_lead_requires_place_id(session) -> None:
    """Failure case: missing place_id raises."""
    with pytest.raises(ValueError):
        create_or_update_lead(session, business_name="A")


def test_get_lead_by_place_id(session) -> None:
    """Expected use: round-trip lookup by place_id."""
    create_or_update_lead(session, place_id="p1", business_name="A")
    session.commit()
    found = get_lead_by_place_id(session, "p1")
    assert found is not None
    assert found.business_name == "A"
    assert get_lead_by_place_id(session, "missing") is None

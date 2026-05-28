"""Smoke tests for the SQLModel tables."""
from outreach.models import Lead, LeadStatus, Message, MessageDirection


def test_lead_defaults(session) -> None:
    """Expected use: inserting a minimal lead persists with NEW status."""
    lead = Lead(place_id="abc123", business_name="Glow Spa")
    session.add(lead)
    session.commit()
    session.refresh(lead)

    assert lead.id is not None
    assert lead.status is LeadStatus.NEW
    assert lead.has_website is False
    assert lead.qualification_score == 0


def test_message_foreign_key(session) -> None:
    """Edge case: a Message can be linked to an existing Lead."""
    lead = Lead(place_id="xyz", business_name="Test")
    session.add(lead)
    session.commit()
    session.refresh(lead)
    assert lead.id is not None

    msg = Message(
        lead_id=lead.id,
        direction=MessageDirection.OUTBOUND,
        body="Hello",
    )
    session.add(msg)
    session.commit()
    assert msg.id is not None


def test_unique_place_id(session) -> None:
    """Failure case: re-inserting the same place_id raises."""
    session.add(Lead(place_id="dup", business_name="A"))
    session.commit()
    session.add(Lead(place_id="dup", business_name="B"))
    import pytest
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        session.commit()

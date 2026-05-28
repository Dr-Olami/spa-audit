"""Tests for WhatsApp message-body builders + address formatting."""
import pytest

from outreach.whatsapp import (
    build_followup_link,
    build_icebreaker_freeform,
    format_whatsapp_address,
)


def test_icebreaker_contains_business_name_and_no_link() -> None:
    """Expected use: icebreaker must mention the business and not contain a URL."""
    msg = build_icebreaker_freeform("Glow Spa")
    assert "Glow Spa" in msg
    assert "http" not in msg.lower()


def test_followup_link_contains_both_links() -> None:
    """Edge case: follow-up message must include landing URL and Cal URL."""
    msg = build_followup_link("https://land.example", "https://cal.com/x/y")
    assert "https://land.example" in msg
    assert "https://cal.com/x/y" in msg


def test_format_whatsapp_address_prefixed() -> None:
    """Expected use: already-prefixed address is returned unchanged."""
    assert format_whatsapp_address("whatsapp:+2348012345678") == "whatsapp:+2348012345678"


def test_format_whatsapp_address_adds_prefix() -> None:
    """Expected use: bare E.164 gets the 'whatsapp:' prefix."""
    assert format_whatsapp_address("+2348012345678") == "whatsapp:+2348012345678"


def test_format_whatsapp_address_rejects_non_e164() -> None:
    """Failure case: numbers without '+' are rejected."""
    with pytest.raises(ValueError):
        format_whatsapp_address("2348012345678")

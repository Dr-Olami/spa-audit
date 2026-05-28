"""Tests for lead enrichment + qualification scoring."""
from outreach.scraper.enrich import detect_booking_system, qualify_lead


def test_detect_booking_system_calendly() -> None:
    """Expected use: Calendly link in HTML returns True."""
    html = "<a href='https://calendly.com/jane'>Book now</a>"
    assert detect_booking_system(html) is True


def test_detect_booking_system_book_appointment_text() -> None:
    """Plain text 'book an appointment' is also a signal."""
    html = "<p>Click here to book an appointment</p>"
    assert detect_booking_system(html) is True


def test_detect_booking_system_negative() -> None:
    """Edge case: bare marketing page with no booking signal."""
    html = "<h1>Welcome to Glow Spa</h1><p>Call us on 080...</p>"
    assert detect_booking_system(html) is False


def test_qualify_lead_high_score_no_website_no_booking() -> None:
    """Expected use: ideal target -> high score."""
    score, notes = qualify_lead(
        has_website=False,
        has_booking_system=False,
        rating=4.0,
        review_count=30,
        phone="+2348012345678",
    )
    # 40 (no booking) + 20 (no website) + 15 (rating range) + 10 (small) + 15 (phone) = 100
    assert score == 100
    assert "no booking system detected" in notes
    assert "phone reachable" in notes


def test_qualify_lead_already_has_booking_system_lower_score() -> None:
    """Failure case for *us*: business already automated -> low score."""
    score, _ = qualify_lead(
        has_website=True,
        has_booking_system=True,
        rating=4.8,
        review_count=200,
        phone="+2348012345678",
    )
    # 0 + 0 + 0 + 10 (proven demand) + 0 + 15 = 25
    assert score == 25

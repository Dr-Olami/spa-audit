"""Lead enrichment: fetch website, detect booking system, score qualification."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import httpx
from bs4 import BeautifulSoup

# Booking-system / scheduling keywords. Presence of any of these on the
# business website strongly suggests they ALREADY have an automated booking
# system — so they are LESS qualified for us.
BOOKING_KEYWORDS = (
    "calendly.com",
    "cal.com",
    "fresha.com",
    "booksy.com",
    "squareup.com/appointments",
    "vagaro.com",
    "setmore.com",
    "acuityscheduling.com",
    "schedulista.com",
    "simplybook.me",
    "treatwell.com",
    "book now",
    "book an appointment",
    "schedule appointment",
    "online booking",
)

INSTAGRAM_HANDLE_RE = re.compile(r"instagram\.com/([A-Za-z0-9_.]+)")


@dataclass(slots=True)
class EnrichmentResult:
    """Result of enriching a single lead's online presence."""

    has_website: bool
    has_booking_system: bool
    instagram_handle: Optional[str]
    fetch_error: Optional[str] = None


def _is_real_website(url: Optional[str]) -> bool:
    """Treat Linktree / Instagram / Facebook as 'no real website'."""
    if not url:
        return False
    lowered = url.lower()
    weak_hosts = (
        "linktr.ee",
        "linktree.com",
        "instagram.com",
        "facebook.com",
        "fb.com",
        "tiktok.com",
    )
    return not any(host in lowered for host in weak_hosts)


async def enrich_lead(website: Optional[str]) -> EnrichmentResult:
    """Fetch a lead's website and detect booking-system presence.

    Args:
        website: Public-facing URL for the business (may be ``None``).

    Returns:
        :class:`EnrichmentResult` with detection flags.
    """
    has_real_website = _is_real_website(website)
    if not has_real_website:
        return EnrichmentResult(
            has_website=False,
            has_booking_system=False,
            instagram_handle=_extract_instagram(website),
        )

    try:
        async with httpx.AsyncClient(
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; SalonOutreachBot/0.1)"},
        ) as client:
            response = await client.get(website)  # type: ignore[arg-type]
            response.raise_for_status()
            html = response.text
    except (httpx.HTTPError, ValueError) as exc:
        return EnrichmentResult(
            has_website=True,
            has_booking_system=False,
            instagram_handle=None,
            fetch_error=str(exc)[:200],
        )

    has_booking = detect_booking_system(html)
    instagram = _extract_instagram(html)

    return EnrichmentResult(
        has_website=True,
        has_booking_system=has_booking,
        instagram_handle=instagram,
    )


def detect_booking_system(html: str) -> bool:
    """Return ``True`` if the HTML contains any known booking-system signal."""
    if not html:
        return False
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).lower()
    raw = html.lower()
    return any(kw in raw or kw in text for kw in BOOKING_KEYWORDS)


def _extract_instagram(html_or_url: Optional[str]) -> Optional[str]:
    """Pull the first Instagram handle out of a URL or HTML blob."""
    if not html_or_url:
        return None
    match = INSTAGRAM_HANDLE_RE.search(html_or_url)
    if not match:
        return None
    handle = match.group(1).strip("/")
    # Filter out generic paths like 'p', 'explore', 'reel'.
    if handle.lower() in {"p", "explore", "reel", "reels", "stories", "tv"}:
        return None
    return handle


def qualify_lead(
    *,
    has_website: bool,
    has_booking_system: bool,
    rating: Optional[float],
    review_count: Optional[int],
    phone: Optional[str],
) -> tuple[int, str]:
    """Compute a qualification score (0-100) and explanation.

    The higher the score, the better a fit they are for our pitch — i.e. they
    are MORE likely to need our help.

    Scoring (additive):
        +40  no booking system on their site
        +20  no real website at all
        +15  rating between 3.5 and 4.3 (room to grow)
        +10  fewer than 50 reviews (small / growing business)
        +10  rating >= 4.3 and >= 50 reviews (proven demand)
        +15  phone number is present (we can actually reach them)
    """
    score = 0
    reasons: list[str] = []

    if not has_booking_system:
        score += 40
        reasons.append("no booking system detected")
    if not has_website:
        score += 20
        reasons.append("no real website")
    if rating is not None:
        if 3.5 <= rating <= 4.3:
            score += 15
            reasons.append(f"rating {rating} has room to grow")
        elif rating >= 4.3 and (review_count or 0) >= 50:
            score += 10
            reasons.append(f"proven demand (rating {rating}, {review_count} reviews)")
    if review_count is not None and review_count < 50:
        score += 10
        reasons.append(f"small business ({review_count} reviews)")
    if phone:
        score += 15
        reasons.append("phone reachable")

    return min(score, 100), "; ".join(reasons)

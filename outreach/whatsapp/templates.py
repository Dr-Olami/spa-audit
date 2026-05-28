"""WhatsApp message bodies.

Two flavours:

1. **Freeform** (this module) — used in the Twilio sandbox and inside the
   24-hour customer service window after a lead replies.
2. **Approved templates** — registered in Twilio Content Editor and approved by
   Meta. The CLI references them by SID via
   :attr:`outreach.config.Settings.twilio_template_icebreaker_sid`.

Both flavours follow the *icebreaker → link* sequence from the strategy doc:
no link in the first message; the link goes out only after the lead opts in.
"""
from __future__ import annotations


def build_icebreaker_freeform(business_name: str) -> str:
    """First-touch icebreaker message — no link, asks permission to send one.

    Args:
        business_name: The business name as it appears on Google Maps / IG.
    """
    return (
        f"Hi {business_name}! Love the work on your page. I'm reaching out "
        "because we help salons and spas in Nigeria automate WhatsApp bookings "
        "and deposit collection — so you stop losing clients while you're with "
        "another client.\n\n"
        "Can I send you a quick 1-min breakdown of how it works?"
    )


def build_followup_link(landing_url: str, cal_url: str) -> str:
    """Second-touch message: short pitch + landing page + booking link."""
    return (
        "Awesome — here's how it works in under a minute:\n\n"
        f"{landing_url}\n\n"
        "If it looks useful, you can grab a free 20-min audit slot here "
        f"(no obligation): {cal_url}"
    )


def build_template_variables_icebreaker(business_name: str) -> dict[str, str]:
    """Variable map for an approved icebreaker template.

    The Twilio Content template should declare a single ``{{1}}`` placeholder
    for the business name.
    """
    return {"1": business_name}

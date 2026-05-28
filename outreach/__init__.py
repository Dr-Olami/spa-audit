"""Salon & Spa outreach toolkit.

Modules:
    config: Settings loaded from .env.
    db: SQLModel engine + session helpers.
    models: Lead and Message SQLModel tables.
    scraper: Google Places API client + website enrichment.
    whatsapp: Twilio WhatsApp client, templates and inbound webhook.
    crm: Lead repository (CRUD + queries).
    cli: Typer entrypoint.
"""

__version__ = "0.1.0"

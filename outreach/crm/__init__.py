"""Lead repository (CRUD + queries)."""
from .repo import (
    create_or_update_lead,
    get_lead,
    get_lead_by_booking_external_id,
    get_lead_by_email,
    get_lead_by_phone,
    get_lead_by_place_id,
    list_leads,
    log_message,
    update_lead_status,
    upsert_booking_lead,
)

__all__ = [
    "create_or_update_lead",
    "get_lead",
    "get_lead_by_booking_external_id",
    "get_lead_by_email",
    "get_lead_by_phone",
    "get_lead_by_place_id",
    "list_leads",
    "log_message",
    "update_lead_status",
    "upsert_booking_lead",
]

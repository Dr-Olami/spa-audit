"""Background job service layer.

Pure functions that perform the same work as the ``scrape`` / ``qualify`` /
``send-icebreaker`` CLI commands, but return a structured ``JobRun`` row so
the dashboard, the HTTP API and the scheduler can all share one
implementation.

Design notes:
    * Each ``run_*`` returns the persisted :class:`JobRun` instance (already
      committed). Callers never need to manage their own session.
    * Long-running work happens inside a fresh ``session_scope`` so the
      caller can fire-and-forget on a FastAPI ``BackgroundTasks`` queue.
    * Errors are caught and stored on the ``JobRun`` row — the worker never
      raises into a background task (which would only be logged silently).
"""
from __future__ import annotations

import asyncio
import json
import logging
import traceback
from datetime import datetime
from typing import Any, Callable, Optional

from sqlmodel import Session

from .config import get_settings
from .crm import (
    create_or_update_lead,
    get_lead,
    list_leads,
    log_message,
)
from .db import session_scope
from .models import JobRun, JobStatus, LeadStatus, MessageDirection
from .scraper import PlacesClient, enrich_lead, qualify_lead
from .whatsapp import TwilioWhatsAppClient, build_icebreaker_freeform
from .whatsapp.templates import build_template_variables_icebreaker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- job registry
def _create_job(
    session: Session,
    name: str,
    trigger: str,
    params: dict[str, Any],
) -> JobRun:
    """Insert a ``RUNNING`` JobRun row and return it (already flushed)."""
    job = JobRun(
        name=name,
        trigger=trigger,
        status=JobStatus.RUNNING,
        params_json=json.dumps(params, default=str),
        started_at=datetime.utcnow(),
    )
    session.add(job)
    session.flush()
    return job


def _finalize_job(
    session: Session,
    job: JobRun,
    *,
    status: JobStatus,
    summary: Optional[str] = None,
    error: Optional[str] = None,
    items_processed: int = 0,
) -> JobRun:
    job.status = status
    job.summary = summary
    job.error = error
    job.items_processed = items_processed
    job.finished_at = datetime.utcnow()
    session.add(job)
    session.flush()
    return job


def _run_with_tracking(
    name: str,
    trigger: str,
    params: dict[str, Any],
    worker: Callable[[Session, JobRun], tuple[str, int]],
) -> JobRun:
    """Boilerplate: create a JobRun, run ``worker``, persist result.

    ``worker`` returns ``(summary, items_processed)`` on success or raises.
    """
    with session_scope() as session:
        job = _create_job(session, name=name, trigger=trigger, params=params)
        job_id = job.id

    try:
        with session_scope() as session:
            job = session.get(JobRun, job_id)
            assert job is not None
            summary, items = worker(session, job)
            return _finalize_job(
                session, job,
                status=JobStatus.SUCCESS,
                summary=summary,
                items_processed=items,
            )
    except Exception as exc:  # noqa: BLE001 — we want the full message on the row
        logger.exception("Job %s (%s) failed", name, job_id)
        with session_scope() as session:
            job = session.get(JobRun, job_id)
            if job is None:
                raise
            return _finalize_job(
                session, job,
                status=JobStatus.FAILED,
                error=f"{exc.__class__.__name__}: {exc}\n{traceback.format_exc(limit=4)}",
            )


# ----------------------------------------------------------------------- scrape
def run_scrape_job(
    query: str,
    *,
    city: Optional[str] = None,
    max_results: int = 20,
    trigger: str = "manual",
) -> JobRun:
    """Search Google Places for ``query`` and upsert leads. Returns the JobRun."""
    params = {"query": query, "city": city, "max_results": max_results}

    def _worker(session: Session, job: JobRun) -> tuple[str, int]:
        client = PlacesClient()
        results = asyncio.run(client.text_search(query, page_size=max_results))
        inserted = 0
        for r in results:
            if not r.place_id:
                continue
            create_or_update_lead(
                session,
                place_id=r.place_id,
                business_name=r.business_name,
                category=r.category,
                city=city,
                address=r.address,
                phone=r.phone,
                website=r.website,
                google_maps_url=r.google_maps_url,
                rating=r.rating,
                review_count=r.review_count,
            )
            inserted += 1
        return f"Persisted {inserted} leads for {query!r}", inserted

    return _run_with_tracking("scrape", trigger, params, _worker)


# ---------------------------------------------------------------------- qualify
def run_qualify_job(
    *,
    limit: int = 50,
    only_new: bool = True,
    trigger: str = "manual",
) -> JobRun:
    """Re-enrich and score leads. Returns the JobRun."""
    params = {"limit": limit, "only_new": only_new}

    def _worker(session: Session, job: JobRun) -> tuple[str, int]:
        status_filter = LeadStatus.NEW if only_new else None
        leads = list_leads(session, status=status_filter, limit=limit)
        if not leads:
            return "No leads to qualify", 0

        async def _enrich_all() -> int:
            processed = 0
            for lead in leads:
                result = await enrich_lead(lead.website)
                score, notes = qualify_lead(
                    has_website=result.has_website,
                    has_booking_system=result.has_booking_system,
                    rating=lead.rating,
                    review_count=lead.review_count,
                    phone=lead.phone,
                )
                lead.has_website = result.has_website
                lead.has_booking_system = result.has_booking_system
                lead.qualification_score = score
                lead.qualification_notes = notes
                if result.instagram_handle and not lead.instagram_handle:
                    lead.instagram_handle = result.instagram_handle
                if lead.status is LeadStatus.NEW and score >= 50:
                    lead.status = LeadStatus.QUALIFIED
                session.add(lead)
                processed += 1
            return processed

        processed = asyncio.run(_enrich_all())
        return f"Qualified {processed} leads", processed

    return _run_with_tracking("qualify", trigger, params, _worker)


# ------------------------------------------------------------- send icebreakers
def run_send_icebreakers_job(
    *,
    lead_id: Optional[int] = None,
    batch: int = 0,
    use_template: bool = False,
    trigger: str = "manual",
) -> JobRun:
    """Send first-touch icebreaker to one lead or a batch of QUALIFIED leads."""
    params = {"lead_id": lead_id, "batch": batch, "use_template": use_template}

    def _worker(session: Session, job: JobRun) -> tuple[str, int]:
        settings = get_settings()
        client = TwilioWhatsAppClient()

        if lead_id is not None:
            lead = get_lead(session, lead_id)
            targets = [lead] if lead else []
        elif batch > 0:
            targets = list_leads(session, status=LeadStatus.QUALIFIED, limit=batch)
        else:
            raise ValueError("Provide lead_id or batch>0")

        if use_template and not settings.twilio_template_icebreaker_sid:
            raise ValueError("TWILIO_TEMPLATE_ICEBREAKER_SID is empty; cannot use template")

        sent = failed = skipped = 0
        for lead in targets:
            if lead is None or not lead.phone or lead.id is None:
                skipped += 1
                continue
            body = build_icebreaker_freeform(lead.business_name)
            try:
                if use_template:
                    result = client.send_template(
                        lead.phone,
                        content_sid=settings.twilio_template_icebreaker_sid,
                        variables=build_template_variables_icebreaker(lead.business_name),
                    )
                else:
                    result = client.send_freeform(lead.phone, body)
            except Exception as exc:  # noqa: BLE001 — record per-lead error, continue batch
                logger.exception("Icebreaker send failed for lead %s", lead.id)
                log_message(
                    session=session,
                    lead_id=lead.id,
                    direction=MessageDirection.OUTBOUND,
                    body=body,
                    twilio_sid=None,
                    status=f"failed: {exc}",
                )
                failed += 1
                continue

            log_message(
                session=session,
                lead_id=lead.id,
                direction=MessageDirection.OUTBOUND,
                body=body,
                twilio_sid=result.sid,
                status=result.status,
            )
            if result.sid:
                sent += 1
            else:
                failed += 1

        summary = f"sent={sent} failed={failed} skipped={skipped}"
        return summary, sent

    return _run_with_tracking("send_icebreaker", trigger, params, _worker)

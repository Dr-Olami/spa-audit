"""Tests for the :mod:`outreach.jobs` service layer.

We patch the module-level ``engine`` in :mod:`outreach.db` to point at an
in-memory SQLite database, so the production ``leads.db`` is never touched.
"""
from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool


@pytest.fixture()
def fake_engine(monkeypatch):
    """Swap the global engine for an in-memory SQLite + create tables."""
    from outreach import db, models  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "engine", engine)
    yield engine


def test_qualify_job_with_empty_db_succeeds_with_zero_items(fake_engine):
    """Expected-use: a qualify pass on an empty DB succeeds with 0 items."""
    from outreach.jobs import run_qualify_job
    from outreach.models import JobRun, JobStatus

    job = run_qualify_job(limit=10, only_new=True, trigger="test")
    assert job.status is JobStatus.SUCCESS
    assert job.items_processed == 0
    assert "No leads" in (job.summary or "")

    with Session(fake_engine) as s:
        rows = s.exec(select(JobRun)).all()
        assert len(rows) == 1
        assert rows[0].name == "qualify"
        assert rows[0].trigger == "test"


def test_send_icebreakers_with_no_target_raises_recorded_on_jobrun(fake_engine):
    """Failure case: invalid args (lead_id=None, batch=0) -> JobRun.FAILED."""
    from outreach.jobs import run_send_icebreakers_job
    from outreach.models import JobStatus

    job = run_send_icebreakers_job(lead_id=None, batch=0, trigger="test")
    assert job.status is JobStatus.FAILED
    assert job.error and "lead_id or batch" in job.error


def test_qualify_job_processes_existing_lead(fake_engine, monkeypatch):
    """Edge case: 1 lead with website -> job processes it & updates score."""
    from outreach import jobs as jobs_mod
    from outreach.crm import create_or_update_lead
    from outreach.db import session_scope
    from outreach.models import JobStatus, LeadStatus
    from outreach.scraper.enrich import EnrichmentResult

    async def fake_enrich(_url):
        return EnrichmentResult(
            has_website=True,
            has_booking_system=False,
            instagram_handle=None,
        )

    monkeypatch.setattr(jobs_mod, "enrich_lead", fake_enrich)

    with session_scope() as session:
        create_or_update_lead(
            session,
            place_id="test-1",
            business_name="Test Salon",
            phone="+2348000000000",
            website="https://example.com",
            rating=4.5,
            review_count=50,
        )

    job = jobs_mod.run_qualify_job(limit=10, only_new=True, trigger="test")
    assert job.status is JobStatus.SUCCESS
    assert job.items_processed == 1

    # The lead should now have a non-zero score and possibly a status change.
    from outreach.models import Lead
    with Session(fake_engine) as s:
        lead = s.exec(select(Lead)).first()
        assert lead is not None
        assert lead.has_website is True
        assert lead.qualification_score > 0
        # Either QUALIFIED (if score >= 50) or still NEW.
        assert lead.status in {LeadStatus.NEW, LeadStatus.QUALIFIED}

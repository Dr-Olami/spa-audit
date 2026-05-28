"""HTTP API for triggering background jobs from the dashboard / cron / curl.

Mounted under ``/api`` by :mod:`outreach.whatsapp.webhook`.

Auth model:
    * If ``API_TOKEN`` is set, every request must send
      ``Authorization: Bearer <token>``.
    * If the request carries a valid admin session cookie, it is also
      accepted (so the dashboard JS can call the API without exposing the
      token in the browser).
    * If ``API_TOKEN`` is empty *and* there is no admin session, the request
      is rejected — we never want an unauthenticated job trigger.

Endpoints (all return JobRun JSON):
    POST /api/jobs/scrape            { query, city?, max_results? }
    POST /api/jobs/qualify           { limit?, only_new? }
    POST /api/jobs/send-icebreakers  { lead_id? | batch?, use_template? }
    GET  /api/jobs                   ?limit=50  -> recent runs
    GET  /api/jobs/{id}              single run
"""
from __future__ import annotations

import secrets
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlmodel import desc, select

from .config import get_settings
from .db import session_scope
from .jobs import run_qualify_job, run_scrape_job, run_send_icebreakers_job
from .models import JobRun

router = APIRouter(prefix="/api", tags=["api"])


# ------------------------------------------------------------------- auth
def require_auth(request: Request) -> str:
    """Allow either a Bearer token or an authenticated admin session.

    Returns the principal name (``"api"`` for tokens, ``request.session["user"]``
    for admin cookies) so handlers can attribute jobs in a future iteration.
    """
    settings = get_settings()

    # 1) Admin session cookie (set by sqladmin's AuthenticationBackend).
    try:
        sess_user = request.session.get("user")
    except AssertionError:
        # SessionMiddleware not installed (e.g. no ADMIN_USERS configured).
        sess_user = None
    if sess_user:
        return str(sess_user)

    # 2) Bearer token.
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer ") and settings.api_token:
        token = header.split(" ", 1)[1].strip()
        if secrets.compare_digest(token, settings.api_token):
            return "api"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ---------------------------------------------------------------- payloads
class ScrapeRequest(BaseModel):
    """Body for ``POST /api/jobs/scrape``."""

    query: str = Field(..., min_length=2, examples=["salon in Lekki, Lagos"])
    city: Optional[str] = None
    max_results: int = Field(20, ge=1, le=20)


class QualifyRequest(BaseModel):
    """Body for ``POST /api/jobs/qualify``."""

    limit: int = Field(50, ge=1, le=500)
    only_new: bool = True


class SendIcebreakerRequest(BaseModel):
    """Body for ``POST /api/jobs/send-icebreakers``."""

    lead_id: Optional[int] = Field(None, ge=1)
    batch: int = Field(0, ge=0, le=50)
    use_template: bool = False


class JobOut(BaseModel):
    """JSON shape returned for ``JobRun`` rows."""

    id: int
    name: str
    trigger: str
    status: str
    params_json: Optional[str]
    summary: Optional[str]
    error: Optional[str]
    items_processed: int
    started_at: str
    finished_at: Optional[str]

    @classmethod
    def from_orm_row(cls, job: JobRun) -> "JobOut":
        return cls(
            id=job.id or 0,
            name=job.name,
            trigger=job.trigger,
            status=job.status.value if hasattr(job.status, "value") else str(job.status),
            params_json=job.params_json,
            summary=job.summary,
            error=job.error,
            items_processed=job.items_processed,
            started_at=job.started_at.isoformat(),
            finished_at=job.finished_at.isoformat() if job.finished_at else None,
        )


# ---------------------------------------------------------------- handlers
@router.post("/jobs/scrape", status_code=202, response_model=JobOut)
def scrape_endpoint(
    payload: ScrapeRequest,
    background: BackgroundTasks,
    _principal: str = Depends(require_auth),
) -> JobOut:
    """Kick off a scrape in the background, returning the seed JobRun row."""
    # We persist a PENDING row synchronously so the API can hand back an id
    # the caller can poll. The heavy lifting then runs in BackgroundTasks.
    from .models import JobStatus
    with session_scope() as session:
        job = JobRun(
            name="scrape",
            trigger="api",
            status=JobStatus.PENDING,
            params_json=payload.model_dump_json(),
        )
        session.add(job)
        session.flush()
        job_id = job.id
        out = JobOut.from_orm_row(job)

    def _runner() -> None:
        # Replace the PENDING placeholder with the real run.
        _delete_job(job_id)
        run_scrape_job(
            payload.query,
            city=payload.city,
            max_results=payload.max_results,
            trigger="api",
        )

    background.add_task(_runner)
    return out


@router.post("/jobs/qualify", status_code=202, response_model=JobOut)
def qualify_endpoint(
    payload: QualifyRequest,
    background: BackgroundTasks,
    _principal: str = Depends(require_auth),
) -> JobOut:
    """Kick off a qualify pass in the background."""
    from .models import JobStatus
    with session_scope() as session:
        job = JobRun(
            name="qualify",
            trigger="api",
            status=JobStatus.PENDING,
            params_json=payload.model_dump_json(),
        )
        session.add(job)
        session.flush()
        job_id = job.id
        out = JobOut.from_orm_row(job)

    def _runner() -> None:
        _delete_job(job_id)
        run_qualify_job(
            limit=payload.limit,
            only_new=payload.only_new,
            trigger="api",
        )

    background.add_task(_runner)
    return out


@router.post("/jobs/send-icebreakers", status_code=202, response_model=JobOut)
def send_icebreakers_endpoint(
    payload: SendIcebreakerRequest,
    background: BackgroundTasks,
    _principal: str = Depends(require_auth),
) -> JobOut:
    """Kick off an icebreaker send batch in the background."""
    if payload.lead_id is None and payload.batch == 0:
        raise HTTPException(400, "Provide lead_id or batch>0")

    from .models import JobStatus
    with session_scope() as session:
        job = JobRun(
            name="send_icebreaker",
            trigger="api",
            status=JobStatus.PENDING,
            params_json=payload.model_dump_json(),
        )
        session.add(job)
        session.flush()
        job_id = job.id
        out = JobOut.from_orm_row(job)

    def _runner() -> None:
        _delete_job(job_id)
        run_send_icebreakers_job(
            lead_id=payload.lead_id,
            batch=payload.batch,
            use_template=payload.use_template,
            trigger="api",
        )

    background.add_task(_runner)
    return out


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    limit: int = 50,
    _principal: str = Depends(require_auth),
) -> list[JobOut]:
    """Return the most recent JobRun rows, newest first."""
    limit = max(1, min(limit, 500))
    with session_scope() as session:
        rows = session.exec(
            select(JobRun).order_by(desc(JobRun.started_at)).limit(limit)
        ).all()
        return [JobOut.from_orm_row(r) for r in rows]


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    _principal: str = Depends(require_auth),
) -> JobOut:
    """Return a single JobRun by id."""
    with session_scope() as session:
        job = session.get(JobRun, job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        return JobOut.from_orm_row(job)


# ---------------------------------------------------------------- internals
def _delete_job(job_id: Optional[int]) -> None:
    """Drop a synchronously-created PENDING placeholder row.

    The real ``run_*_job`` worker writes its own RUNNING/SUCCESS/FAILED
    row, so the placeholder is no longer useful once the BackgroundTasks
    queue starts executing.
    """
    if job_id is None:
        return
    with session_scope() as session:
        job = session.get(JobRun, job_id)
        if job is not None:
            session.delete(job)

"""APScheduler glue for daily cron jobs.

Runs in-process alongside ``outreach serve``. Two cron triggers are wired:

    * Daily ``qualify`` at ``DAILY_QUALIFY_HOUR:DAILY_QUALIFY_MINUTE``
    * Daily ``scrape`` for each query in ``DAILY_SCRAPE_QUERIES``
      (skipped entirely if the list is empty).

Both fire through the same :mod:`outreach.jobs` service layer so every
cron run gets logged to ``job_runs`` and shows up in the dashboard.
"""
from __future__ import annotations

import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import get_settings
from .jobs import run_qualify_job, run_scrape_job

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None


def _qualify_tick() -> None:
    """APScheduler entry point — wraps run_qualify_job with logging."""
    settings = get_settings()
    try:
        job = run_qualify_job(
            limit=settings.daily_qualify_limit,
            only_new=True,
            trigger="scheduler",
        )
        logger.info("Scheduled qualify finished: %s", job.summary or job.error)
    except Exception:
        logger.exception("Scheduled qualify crashed")


def _scrape_tick(query: str, city: Optional[str], max_results: int) -> None:
    """APScheduler entry point — wraps run_scrape_job with logging."""
    try:
        job = run_scrape_job(
            query,
            city=city,
            max_results=max_results,
            trigger="scheduler",
        )
        logger.info("Scheduled scrape %r finished: %s", query, job.summary or job.error)
    except Exception:
        logger.exception("Scheduled scrape %r crashed", query)


def start_scheduler() -> Optional[BackgroundScheduler]:
    """Start the in-process scheduler if ``SCHEDULER_ENABLED`` is true.

    Idempotent: re-calling returns the already-running scheduler.
    """
    global _scheduler
    settings = get_settings()
    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled (SCHEDULER_ENABLED=false)")
        return None
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    sched = BackgroundScheduler(daemon=True, timezone="UTC")

    sched.add_job(
        _qualify_tick,
        trigger=CronTrigger(
            hour=settings.daily_qualify_hour,
            minute=settings.daily_qualify_minute,
        ),
        id="daily_qualify",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    logger.info(
        "Scheduled daily qualify at %02d:%02d UTC",
        settings.daily_qualify_hour,
        settings.daily_qualify_minute,
    )

    queries = settings.parse_daily_scrape_queries()
    city = settings.daily_scrape_city or None
    for idx, q in enumerate(queries):
        sched.add_job(
            _scrape_tick,
            trigger=CronTrigger(
                hour=settings.daily_scrape_hour,
                minute=settings.daily_scrape_minute,
            ),
            args=[q, city, settings.daily_scrape_max],
            id=f"daily_scrape_{idx}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    if queries:
        logger.info(
            "Scheduled daily scrape (%d queries) at %02d:%02d UTC",
            len(queries),
            settings.daily_scrape_hour,
            settings.daily_scrape_minute,
        )

    sched.start()
    _scheduler = sched
    return sched


def shutdown_scheduler() -> None:
    """Stop the scheduler if running. Used on FastAPI shutdown."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None


def get_scheduler() -> Optional[BackgroundScheduler]:
    """Return the active scheduler (or None if disabled)."""
    return _scheduler

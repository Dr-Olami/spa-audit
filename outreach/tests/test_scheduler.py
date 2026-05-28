"""Smoke tests for :mod:`outreach.scheduler`.

We don't actually start the scheduler in the test process; we just verify
that ``start_scheduler`` short-circuits when the feature is disabled and
that the daily-query parser works as expected.
"""
from __future__ import annotations

import pytest


def test_start_scheduler_returns_none_when_disabled(monkeypatch):
    """Expected-use: SCHEDULER_ENABLED=false -> start_scheduler returns None."""
    pytest.importorskip("apscheduler")
    from outreach.config import get_settings
    from outreach.scheduler import shutdown_scheduler, start_scheduler

    settings = get_settings()
    monkeypatch.setattr(settings, "scheduler_enabled", False)
    try:
        assert start_scheduler() is None
    finally:
        shutdown_scheduler()


def test_parse_daily_scrape_queries_splits_on_comma(monkeypatch):
    """Edge case: spaces / blanks in the env are tolerated."""
    from outreach.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(
        settings,
        "daily_scrape_queries",
        "salon in Lekki, , spa in Victoria Island  ,  ",
    )
    parsed = settings.parse_daily_scrape_queries()
    assert parsed == ["salon in Lekki", "spa in Victoria Island"]


def test_parse_daily_scrape_queries_empty_returns_empty_list(monkeypatch):
    """Failure-ish case: empty env yields an empty list (not [''])."""
    from outreach.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "daily_scrape_queries", "")
    assert settings.parse_daily_scrape_queries() == []

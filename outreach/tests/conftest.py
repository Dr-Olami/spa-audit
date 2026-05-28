"""Pytest fixtures: in-memory SQLite session for fast, isolated tests."""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


@pytest.fixture()
def session() -> Iterator[Session]:
    """Yield a SQLModel session backed by an in-memory SQLite DB.

    The database is fully isolated to a single test.
    """
    # Import models so SQLModel.metadata is populated.
    from outreach import models  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s

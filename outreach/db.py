"""Database engine + session helpers."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

_settings = get_settings()
_connect_args = (
    {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(
    _settings.database_url,
    echo=False,
    connect_args=_connect_args,
)


def init_db() -> None:
    """Create all tables if they do not yet exist, then apply column migrations."""
    # Import models so SQLModel.metadata is populated before create_all.
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _migrate_lead_columns()


def _migrate_lead_columns() -> None:
    """Idempotent ALTER TABLE for columns added after the initial schema.

    SQLAlchemy's ``create_all`` only creates *missing* tables, never adds
    *missing columns* to existing ones. For our 2-user SQLite deployment a
    full migration framework is overkill; we just diff the live schema and
    issue ``ALTER TABLE ... ADD COLUMN`` for whatever's missing.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "leads" not in inspector.get_table_names():
        return  # Fresh DB — create_all already added everything.

    existing_cols = {c["name"] for c in inspector.get_columns("leads")}

    # SQLite-flavoured DDL. Each tuple is (column_name, type_with_default).
    #
    # IMPORTANT: SQLAlchemy's Enum column stores the Python enum *name*
    # (``PLACES``), not its value (``places``). When we ADD COLUMN with a
    # DEFAULT we must therefore use the uppercase name, otherwise reads
    # blow up with ``LookupError: 'places' is not among the defined enum
    # values``.
    additions: list[tuple[str, str]] = [
        ("source", "VARCHAR(20) NOT NULL DEFAULT 'PLACES'"),
        ("contact_name", "VARCHAR"),
        ("contact_email", "VARCHAR"),
        ("booking_at", "DATETIME"),
        ("booking_event_type", "VARCHAR"),
        ("booking_status", "VARCHAR"),
        ("booking_external_id", "VARCHAR"),
        ("booking_notes", "TEXT"),
    ]
    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_leads_source ON leads(source)",
        "CREATE INDEX IF NOT EXISTS ix_leads_contact_email ON leads(contact_email)",
        "CREATE INDEX IF NOT EXISTS ix_leads_booking_external_id ON leads(booking_external_id)",
    ]
    # One-time repair: an earlier version of this migration wrote the
    # lowercase enum VALUE instead of NAME, leaving rows un-readable by
    # SQLAlchemy. UPDATE is idempotent — once everything is uppercase the
    # WHERE clause matches nothing.
    repairs = [
        "UPDATE leads SET source = 'PLACES' WHERE source = 'places'",
        "UPDATE leads SET source = 'BOOKING' WHERE source = 'booking'",
        "UPDATE leads SET source = 'MANUAL' WHERE source = 'manual'",
        "UPDATE leads SET source = 'INSTAGRAM' WHERE source = 'instagram'",
    ]

    with engine.begin() as conn:
        for name, ddl in additions:
            if name not in existing_cols:
                conn.execute(text(f"ALTER TABLE leads ADD COLUMN {name} {ddl}"))
        # Indexes are safe to re-run thanks to IF NOT EXISTS.
        for stmt in indexes:
            conn.execute(text(stmt))
        for stmt in repairs:
            conn.execute(text(stmt))


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context-managed SQLModel session with commit/rollback handling."""
    # expire_on_commit=False keeps attributes usable after commit so callers
    # can read columns without triggering a refresh on a closed session.
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

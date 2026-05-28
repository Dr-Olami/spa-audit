"""Centralised settings loaded from environment / .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PATH = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    """Application settings.

    All values are read from environment variables or ``outreach/.env``.
    """

    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14099083940"
    twilio_whatsapp_sandbox_from: str = "whatsapp:+14155238886"
    twilio_use_sandbox: bool = True
    twilio_template_icebreaker_sid: str = ""
    twilio_webhook_validate: bool = False

    # Google Places
    google_places_api_key: str = ""

    # Links used inside messages
    landing_url: str = "https://example.com"
    cal_url: str = "https://cal.com/miracle-edeh/salon-audit"

    # Storage / server
    database_url: str = "sqlite:///./leads.db"
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8000

    # Admin dashboard
    admin_users: str = ""  # "user1:pass1,user2:pass2"
    admin_session_secret: str = ""

    # Cal.com webhook
    # If empty, signature validation is skipped (only safe for local dev).
    cal_webhook_secret: str = ""

    # HTTP API
    # Token required as ``Authorization: Bearer <token>`` on /api/* routes.
    # Empty token disables Bearer auth (admin session cookie still works).
    api_token: str = ""

    # Background scheduler (APScheduler, in-process while ``outreach serve`` runs)
    scheduler_enabled: bool = False
    # 24-h clock in the server's local tz. Default: 02:00.
    daily_qualify_hour: int = 2
    daily_qualify_minute: int = 0
    daily_qualify_limit: int = 100
    # Optional daily scrape. Comma-separated list of queries; empty disables it.
    daily_scrape_queries: str = ""  # e.g. "salon in Lekki, spa in Victoria Island"
    daily_scrape_city: str = ""
    daily_scrape_max: int = 20
    daily_scrape_hour: int = 1
    daily_scrape_minute: int = 0

    def parse_daily_scrape_queries(self) -> list[str]:
        """Return the configured daily-scrape queries as a list."""
        return [q.strip() for q in self.daily_scrape_queries.split(",") if q.strip()]

    @property
    def whatsapp_sender(self) -> str:
        """Return the active sender (sandbox or production)."""
        return (
            self.twilio_whatsapp_sandbox_from
            if self.twilio_use_sandbox
            else self.twilio_whatsapp_from
        )

    def parse_admin_users(self) -> dict[str, str]:
        """Return ``{username: password}`` parsed from ``ADMIN_USERS``."""
        users: dict[str, str] = {}
        if not self.admin_users:
            return users
        for pair in self.admin_users.split(","):
            pair = pair.strip()
            if not pair or ":" not in pair:
                continue
            username, password = pair.split(":", 1)
            username = username.strip()
            password = password.strip()
            if username and password:
                users[username] = password
        return users


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()

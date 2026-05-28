# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Backend container for spa-audit (FastAPI + sqladmin + APScheduler).
#
# The Next.js frontend lives at the repo root and is built by Vercel; this
# image deliberately ignores it (see .dockerignore) and only ships the
# Python `outreach/` package.
#
# Image goals:
#   * Small  -- python:3.11-slim base, no compiler toolchain in final layer.
#   * Fast cold start  -- deps are cached separately from source.
#   * Single uvicorn worker  -- APScheduler is in-process, multiple workers
#     would duplicate every scheduled run (see outreach/README.md).
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system deps needed by lxml / cryptography wheels are pure-python in
# 3.11-slim, but keep curl for the Fly health-check + tini for clean signals.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl tini \
    && rm -rf /var/lib/apt/lists/*

# 1. Dependency layer (cached unless requirements.txt changes).
COPY outreach/requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# 2. Source code.
COPY outreach /app/outreach
COPY pyproject.toml /app/pyproject.toml

# Install our package in editable mode so `outreach` resolves on PYTHONPATH.
RUN pip install -e .

# Fly will mount a persistent volume here. Reason: SQLite needs durable disk;
# the container filesystem is ephemeral and would lose every lead on deploy.
RUN mkdir -p /data
ENV DATABASE_URL=sqlite:////data/leads.db \
    WEBHOOK_HOST=0.0.0.0 \
    WEBHOOK_PORT=8000

EXPOSE 8000

# Reason: tini reaps zombies + forwards SIGTERM to uvicorn so APScheduler's
# `shutdown_scheduler()` hook fires cleanly during `fly deploy` rolling
# restarts (otherwise jobs in flight would be force-killed at SIGKILL).
ENTRYPOINT ["/usr/bin/tini", "--"]

# Single worker is intentional -- see APScheduler note in outreach/README.md.
CMD ["uvicorn", "outreach.whatsapp.webhook:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "1", "--proxy-headers", "--forwarded-allow-ips=*"]

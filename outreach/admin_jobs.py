"""sqladmin views for the background-jobs subsystem.

Kept in its own module so :mod:`outreach.admin` stays under the 500-line
project cap. Exposes:

    * :class:`JobRunAdmin` — read-only ModelView of the ``job_runs`` table.
    * :class:`JobsControlView` — custom HTML page with one-click forms to
      trigger scrape / qualify / send-icebreakers without touching a shell.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from sqladmin import BaseView, ModelView, expose
from sqlmodel import desc, select
from starlette.requests import Request
from starlette.responses import HTMLResponse

from .db import session_scope
from .jobs import run_qualify_job, run_scrape_job, run_send_icebreakers_job
from .models import JobRun, JobStatus

logger = logging.getLogger(__name__)

# Mirror of MAX_BULK_SEND in :mod:`outreach.admin`. Duplicated here to avoid
# a circular import; if you change one, change the other.
MAX_BULK_SEND = 10


class JobRunAdmin(ModelView, model=JobRun):
    """Read-only audit log of background jobs (scrape / qualify / sends)."""

    name = "Job run"
    name_plural = "Job runs"
    icon = "fa-solid fa-list-check"
    category = "Operations"

    page_size = 50
    page_size_options = [25, 50, 100, 200]

    column_list = [
        JobRun.id,
        JobRun.name,
        JobRun.trigger,
        JobRun.status,
        JobRun.items_processed,
        JobRun.summary,
        JobRun.started_at,
        JobRun.finished_at,
    ]
    column_details_list = [
        JobRun.id,
        JobRun.name,
        JobRun.trigger,
        JobRun.status,
        JobRun.params_json,
        JobRun.summary,
        JobRun.error,
        JobRun.items_processed,
        JobRun.started_at,
        JobRun.finished_at,
    ]
    column_searchable_list = [JobRun.name, JobRun.summary, JobRun.error]
    column_sortable_list = [JobRun.started_at, JobRun.name, JobRun.status]
    column_default_sort = [(JobRun.started_at, True)]

    can_create = False
    can_edit = False
    can_delete = False  # Audit log — keep history.
    can_export = True


class JobsControlView(BaseView):
    """Dashboard page with one-click trigger forms.

    Lives at ``/admin/jobs-control``. Each form runs its job *synchronously*
    in the request thread so the operator sees the outcome immediately;
    swap to FastAPI BackgroundTasks if scrape/qualify ever take long enough
    to time out the request.
    """

    name = "Run jobs"
    icon = "fa-solid fa-play"
    category = "Operations"

    # Reason: sqladmin builds the sidebar link via `url_for("admin:{identity}")`
    # where `identity` defaults to the method name. A method named `index`
    # collides with sqladmin's built-in `admin:index` route (the dashboard
    # root `/`), so the sidebar entry would silently point at `/admin/`.
    # Passing an explicit `identity=` makes both the route name and the
    # sidebar URL resolve to `/admin/jobs-control` as intended.
    @expose("/jobs-control", methods=["GET", "POST"], identity="jobs-control")
    async def index(self, request: Request):  # noqa: ANN201 — sqladmin signature
        flash: Optional[str] = None
        flash_kind = "ok"

        if request.method == "POST":
            flash, flash_kind = await _handle_post(request)

        return HTMLResponse(_render_jobs_control(flash, flash_kind))


async def _handle_post(request: Request) -> tuple[str, str]:
    """Dispatch a POSTed form to the right ``run_*_job`` helper.

    Returns ``(flash_message, "ok"|"err")`` for the rendered banner.
    """
    form = await request.form()
    action_name = str(form.get("action", "")).strip()
    try:
        if action_name == "scrape":
            query = str(form.get("query", "")).strip()
            if not query:
                raise ValueError("Query is required")
            city = str(form.get("city", "")).strip() or None
            max_results = max(1, min(int(form.get("max_results", "20") or 20), 20))
            # Reason: run_scrape_job is sync and uses asyncio.run() internally.
            # We are inside FastAPI's running event loop, so we must dispatch
            # the work to a worker thread (clean thread = no running loop).
            job = await asyncio.to_thread(
                run_scrape_job,
                query,
                city=city,
                max_results=max_results,
                trigger="manual",
            )
            return _flash_for(job, "Scrape")

        if action_name == "qualify":
            limit = max(1, min(int(form.get("limit", "50") or 50), 500))
            only_new = form.get("only_new") == "on"
            job = await asyncio.to_thread(
                run_qualify_job, limit=limit, only_new=only_new, trigger="manual"
            )
            return _flash_for(job, "Qualify")

        if action_name == "send_icebreakers":
            batch = max(1, min(int(form.get("batch", "0") or 0), MAX_BULK_SEND))
            use_template = form.get("use_template") == "on"
            job = await asyncio.to_thread(
                run_send_icebreakers_job,
                batch=batch,
                use_template=use_template,
                trigger="manual",
            )
            return _flash_for(job, "Send")

        raise ValueError(f"Unknown action: {action_name!r}")
    except Exception as exc:  # noqa: BLE001 — surface to the operator
        logger.exception("JobsControlView action failed: %s", action_name)
        return f"{type(exc).__name__}: {exc}", "err"


def _flash_for(job: JobRun, label: str) -> tuple[str, str]:
    kind = "ok" if job.status is JobStatus.SUCCESS else "err"
    return f"{label} #{job.id}: {job.summary or job.error}", kind


def _render_jobs_control(flash: Optional[str], flash_kind: str) -> str:
    """Build the standalone HTML page for :class:`JobsControlView`.

    Markup is hand-rolled (no Jinja template file) so the view is one
    self-contained module. Replace with a template if it grows further.
    """
    banner = ""
    if flash:
        colour = "#0f5132" if flash_kind == "ok" else "#842029"
        bg = "#d1e7dd" if flash_kind == "ok" else "#f8d7da"
        banner = (
            f'<div style="padding:.75rem 1rem;margin-bottom:1rem;'
            f'border-radius:.375rem;color:{colour};background:{bg};">{flash}</div>'
        )

    rows_html = ""
    with session_scope() as session:
        recent = session.exec(
            select(JobRun).order_by(desc(JobRun.started_at)).limit(10)
        ).all()
        for j in recent:
            status_val = j.status.value if hasattr(j.status, "value") else str(j.status)
            rows_html += (
                f"<tr><td>{j.id}</td><td>{j.name}</td><td>{j.trigger}</td>"
                f"<td>{status_val}</td><td>{j.items_processed}</td>"
                f"<td>{(j.summary or j.error or '')[:80]}</td>"
                f"<td>{j.started_at.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>"
            )

    return f"""
<!doctype html>
<html><head><meta charset="utf-8"><title>Run jobs</title>
<style>
  body{{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#222;}}
  h1{{margin-top:0;}}
  .card{{border:1px solid #dee2e6;border-radius:.5rem;padding:1rem 1.25rem;margin-bottom:1rem;background:#fff;}}
  .card h2{{margin:.25rem 0 1rem;font-size:1.1rem;}}
  label{{display:block;margin:.5rem 0 .25rem;font-size:.85rem;color:#555;}}
  input[type=text],input[type=number]{{width:100%;padding:.4rem .5rem;border:1px solid #ced4da;border-radius:.25rem;}}
  button{{margin-top:.75rem;padding:.5rem 1rem;border:0;border-radius:.25rem;background:#0d6efd;color:#fff;cursor:pointer;}}
  button:hover{{background:#0b5ed7;}}
  table{{width:100%;border-collapse:collapse;font-size:.85rem;}}
  th,td{{padding:.4rem .5rem;border-bottom:1px solid #eee;text-align:left;}}
  th{{background:#f8f9fa;}}
  .back{{display:inline-block;margin-bottom:1rem;color:#0d6efd;text-decoration:none;}}
</style></head>
<body>
<a class="back" href="/admin">&larr; Back to dashboard</a>
<h1>Run jobs</h1>
{banner}

<div class="card">
  <h2>Scrape Google Places</h2>
  <form method="post">
    <input type="hidden" name="action" value="scrape">
    <label>Query (required)</label>
    <input type="text" name="query" placeholder="salon in Lekki, Lagos" required>
    <label>City tag (optional)</label>
    <input type="text" name="city" placeholder="Lagos">
    <label>Max results (1-20)</label>
    <input type="number" name="max_results" value="20" min="1" max="20">
    <button type="submit">Run scrape</button>
  </form>
</div>

<div class="card">
  <h2>Qualify leads</h2>
  <form method="post">
    <input type="hidden" name="action" value="qualify">
    <label>Limit (1-500)</label>
    <input type="number" name="limit" value="50" min="1" max="500">
    <label><input type="checkbox" name="only_new" checked> Only NEW leads</label>
    <button type="submit">Run qualify</button>
  </form>
</div>

<div class="card">
  <h2>Send icebreakers (top-scoring QUALIFIED)</h2>
  <form method="post">
    <input type="hidden" name="action" value="send_icebreakers">
    <label>Batch size (max {MAX_BULK_SEND})</label>
    <input type="number" name="batch" value="5" min="1" max="{MAX_BULK_SEND}">
    <label><input type="checkbox" name="use_template"> Use approved template (production)</label>
    <button type="submit">Send</button>
  </form>
</div>

<div class="card">
  <h2>Recent runs</h2>
  <table>
    <thead><tr><th>ID</th><th>Name</th><th>Trigger</th><th>Status</th>
      <th>#</th><th>Summary</th><th>Started</th></tr></thead>
    <tbody>{rows_html or '<tr><td colspan=7>No runs yet.</td></tr>'}</tbody>
  </table>
</div>
</body></html>
"""

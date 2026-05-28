"""Typer-based CLI: ``python -m outreach.cli ...``

Commands:
    init-db          Create / migrate the SQLite tables.
    scrape           Search Google Places and persist new leads.
    qualify          Re-enrich existing leads (fetch website, score).
    list             Show leads, optionally filtered by status / city.
    send-icebreaker  Send first-touch message to one lead or a batch.
    send-followup    Send the landing-page + Cal link follow-up.
    mark             Manually move a lead to a new status.
    serve            Run the FastAPI webhook server for inbound replies.
"""
from __future__ import annotations

import logging
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .config import get_settings
from .crm import (
    get_lead,
    list_leads,
    log_message,
    update_lead_status,
)
from .db import init_db, session_scope
from .jobs import run_qualify_job, run_scrape_job, run_send_icebreakers_job
from .models import JobStatus, LeadStatus, MessageDirection
from .whatsapp import (
    TwilioWhatsAppClient,
    build_followup_link,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = typer.Typer(add_completion=False, help="Salon & Spa outreach toolkit.")
console = Console()


# --------------------------------------------------------------------- helpers
def _status_or_die(value: str) -> LeadStatus:
    try:
        return LeadStatus(value)
    except ValueError as exc:
        valid = ", ".join(s.value for s in LeadStatus)
        raise typer.BadParameter(f"Unknown status {value!r}. Try: {valid}") from exc


# ------------------------------------------------------------------- commands
@app.command("init-db")
def cmd_init_db() -> None:
    """Create database tables."""
    init_db()
    console.print("[green]Database initialised.[/green]")


@app.command()
def scrape(
    query: str = typer.Option(..., "--query", "-q", help="e.g. 'salon in Lekki, Lagos'"),
    city: Optional[str] = typer.Option(None, "--city", help="Tag leads with this city."),
    max_results: int = typer.Option(20, "--max", min=1, max=20),
) -> None:
    """Search Google Places and insert any new leads."""
    init_db()
    job = run_scrape_job(query, city=city, max_results=max_results, trigger="cli")
    colour = "green" if job.status is JobStatus.SUCCESS else "red"
    console.print(f"[{colour}]{job.summary or job.error}[/{colour}]")


@app.command()
def qualify(
    limit: int = typer.Option(50, "--limit", min=1, max=500),
    only_new: bool = typer.Option(True, "--only-new/--all", help="Skip already-qualified leads."),
) -> None:
    """Fetch each lead's website, detect booking systems, score, and persist."""
    init_db()
    job = run_qualify_job(limit=limit, only_new=only_new, trigger="cli")
    colour = "green" if job.status is JobStatus.SUCCESS else "red"
    console.print(f"[{colour}]{job.summary or job.error}[/{colour}]")


@app.command("list")
def cmd_list(
    status: Optional[str] = typer.Option(None, "--status", "-s"),
    city: Optional[str] = typer.Option(None, "--city", "-c"),
    limit: int = typer.Option(50, "--limit", min=1, max=500),
) -> None:
    """Print leads as a table, sorted by qualification score."""
    init_db()
    status_enum = _status_or_die(status) if status else None
    with session_scope() as session:
        rows = list_leads(session, status=status_enum, city=city, limit=limit)
        table = Table(title=f"Leads ({len(rows)})")
        for col in ("ID", "Score", "Status", "Business", "City", "Phone", "Rating", "Website"):
            table.add_column(col)
        for lead in rows:
            table.add_row(
                str(lead.id),
                str(lead.qualification_score),
                lead.status.value,
                (lead.business_name or "")[:34],
                lead.city or "",
                lead.phone or "",
                f"{lead.rating:.1f}" if lead.rating else "",
                "yes" if lead.has_website else "no",
            )
    console.print(table)


@app.command("send-icebreaker")
def cmd_send_icebreaker(
    lead_id: Optional[int] = typer.Option(None, "--lead", help="Single lead ID."),
    batch: int = typer.Option(0, "--batch", help="Send to N top-scoring QUALIFIED leads."),
    use_template: bool = typer.Option(
        False,
        "--template/--freeform",
        help="Use a Meta-approved Twilio template (production) vs freeform (sandbox).",
    ),
) -> None:
    """Send the first-touch icebreaker. No links are included by design."""
    if lead_id is None and batch <= 0:
        raise typer.BadParameter("Provide --lead <id> or --batch <n>.")
    init_db()
    job = run_send_icebreakers_job(
        lead_id=lead_id,
        batch=batch,
        use_template=use_template,
        trigger="cli",
    )
    colour = "green" if job.status is JobStatus.SUCCESS else "red"
    console.print(f"[{colour}]{job.summary or job.error}[/{colour}]")


@app.command("send-followup")
def cmd_send_followup(lead_id: int = typer.Argument(...)) -> None:
    """Send the landing-page + Cal link as a second-touch (after a reply)."""
    init_db()
    settings = get_settings()
    client = TwilioWhatsAppClient()
    body = build_followup_link(settings.landing_url, settings.cal_url)

    with session_scope() as session:
        lead = get_lead(session, lead_id)
        if not lead or not lead.phone or lead.id is None:
            raise typer.BadParameter(f"Lead {lead_id} not found or missing phone.")
        result = client.send_freeform(lead.phone, body)
        log_message(
            session=session,
            lead_id=lead.id,
            direction=MessageDirection.OUTBOUND,
            body=body,
            twilio_sid=result.sid,
            status=result.status,
        )
    console.print(f"[green]Follow-up sent: {result.status}[/green]")


@app.command()
def mark(
    lead_id: int = typer.Argument(...),
    status: str = typer.Argument(...),
    note: Optional[str] = typer.Option(None, "--note", "-n"),
) -> None:
    """Manually set a lead's status."""
    init_db()
    status_enum = _status_or_die(status)
    with session_scope() as session:
        lead = update_lead_status(session, lead_id, status_enum, note=note)
        if not lead:
            raise typer.BadParameter(f"Lead {lead_id} not found.")
    console.print(f"[green]Lead {lead_id} -> {status_enum.value}[/green]")


@app.command()
def serve() -> None:
    """Run the FastAPI webhook (uvicorn) for inbound WhatsApp replies."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "outreach.whatsapp.webhook:app",
        host=settings.webhook_host,
        port=settings.webhook_port,
        reload=False,
    )


if __name__ == "__main__":
    app()

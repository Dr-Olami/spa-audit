# TASK.md

## Active

### 2026-05-25 — Mobile-optimized, SEO-friendly landing page (Nigerian salon automation)
- [x] Scaffold Next.js 14 + TS + Tailwind
- [x] SEO foundation (metadata, OG, Twitter, JSON-LD, sitemap, robots)
- [x] Hero, ProblemSolution, Interactive DemoChat, Features, Testimonials, FAQ
- [x] cal.com embed (BookingSection) with dark theme + brand color
- [x] Sticky WhatsApp CTA
- [x] README + .env.example

### 2026-05-25 — Iteration 2: broaden + de-risk copy
- [x] Broaden positioning from salons-only to salons, spas & beauty businesses across SEO, Hero, ProblemSolution, DemoChat (added massage/facial/nails intents), Features, Testimonials (added spa), FAQ
- [x] Replace over-promised "custom booking link" deliverable with honest audit summary: written review + revenue-loss estimate + prioritised next steps
- [x] Remove "Chat on WhatsApp" CTAs from Header + Hero; remove `<StickyWhatsapp />` from page (component kept on disk for later)
- [x] Fix `NEXT_PUBLIC_CAL_LINK` format (must be `miracle-edeh/salon-audit`, not full URL)
- [x] Default `siteConfig.calLink` to `miracle-edeh/salon-audit`

## Discovered During Work
- [ ] Add real OG image at `/public/og.png` (1200×630)
- [ ] Add favicon + apple-touch-icon under `/public/`
- [ ] Optional: connect a Formspree/Resend endpoint for "WhatsApp me" lead capture fallback
- [ ] Optional: add `/thank-you` post-booking page with WhatsApp CTA for instant follow-up

### 2026-05-25 — Iteration 3: outreach toolkit (Python)
- [x] Twilio WhatsApp client (sandbox + production template support) — sender `whatsapp:+14099083940`
- [x] Lead CRM (SQLModel + SQLite) with `Lead` and `Message` tables, status lifecycle (NEW → QUALIFIED → CONTACTED → REPLIED → BOOKED)
- [x] Google Places API (New) client — chosen over Maps scraping (legal, reliable, structured)
- [x] Website enrichment: fetch site, detect booking systems (Calendly/Cal.com/Fresha/Booksy/etc.), pick out IG handle
- [x] Qualification scoring (additive 0–100) — auto-promotes NEW → QUALIFIED at score ≥ 50
- [x] FastAPI inbound webhook (`/webhook/whatsapp`) with optional Twilio signature validation
- [x] Typer CLI: `init-db`, `scrape`, `qualify`, `list`, `send-icebreaker`, `send-followup`, `mark`, `serve`
- [x] Pytest suite (in-memory SQLite, no Twilio/Google calls) — expected/edge/failure per model+repo+enrich+templates
- [x] README with setup, sandbox-vs-production guidance, ngrok webhook flow, daily workflow

### 2026-05-26 — Iteration 4: admin dashboard + bug fixes
- [x] Fix `DetachedInstanceError` in `outreach list` (build Rich table inside session) + set `expire_on_commit=False` on `session_scope` to prevent recurrence
- [x] Add **sqladmin** CRUD dashboard mounted at `/admin` on the same FastAPI app as the webhook — single `outreach serve` exposes both
- [x] `LeadAdmin` (search/sort/filter, CSV export, 50/page) + `MessageAdmin` views with sensible read-only vs editable column split
- [x] Form-based username/password auth backend (`UsernamePasswordAuth`) — multi-user via comma-separated `ADMIN_USERS=user:pass,...`, timing-safe compare with `secrets.compare_digest`
- [x] Signed-cookie sessions via `ADMIN_SESSION_SECRET` (loud warning when missing)
- [x] `pytest` suite for admin auth + config parsing (expected / edge / failure)

## Backlog (next phase)
- [ ] Create + submit the Meta-approved icebreaker template in Twilio Content Editor
- [ ] Selenium / Playwright fallback for IG-handle discovery when Places gives only a phone
- [ ] Outbound status webhook (`/webhook/status`) to capture delivered/read receipts
- [ ] Daily cron: re-scrape new queries, re-qualify stale leads, send N icebreakers/day with throttling
- [ ] Pipeline kanban view (HTMX) on top of sqladmin baseline if daily ops warrant it

### 2026-05-29 — Iteration 6: Cal.com booking integration + lead provenance
- [x] `LeadSource` enum (`PLACES` / `BOOKING` / `MANUAL` / `INSTAGRAM`) on `Lead` — distinguish scraped prospects from self-booked inbound leads
- [x] Booking-specific columns on `Lead`: `contact_name`, `contact_email`, `booking_at`, `booking_event_type`, `booking_status`, `booking_external_id`, `booking_notes`
- [x] Idempotent column migration helper in `db.py` (`ALTER TABLE ... ADD COLUMN` for existing 40-row DB) — no Alembic needed
- [x] New repo helpers: `get_lead_by_email`, `get_lead_by_booking_external_id`, `upsert_booking_lead` (priority: booking_uid → email → phone → create new)
- [x] **Cal.com webhook** `/webhook/cal` (mounted on the same FastAPI app as Twilio + admin) — handles `BOOKING_CREATED`, `BOOKING_RESCHEDULED`, `BOOKING_CANCELLED`
- [x] HMAC-SHA256 signature validation with `hmac.compare_digest`, defensive payload parser handling Cal's two `responses` shape variants
- [x] Booking notes from Cal automatically logged as an inbound `Message` so the conversation thread is unified
- [x] `LeadAdmin` shows source + booking fields in list/detail/form; searchable by email, sortable by `booking_at` and `source`
- [x] 10 new pytest cases for signature / parsing / handlers (expected / edge / failure)
- [x] **Bookings** sidebar shortcut: `BookingAdmin` subclasses `LeadAdmin`, overrides `list_query` to filter `source=BOOKING`, lives at `/admin/booking/list`, sorted by `booking_at` desc

### 2026-05-29 — Iteration 7: CLI → HTTP API, scheduler, jobs control panel
- [x] Fix `setup_admin` syntax error (truncated `get_settings()` / `BookingAdmin` call) and register `BookingAdmin` view
- [x] Work around sqladmin metaclass overwriting `identity` — reassign `BookingAdmin.identity = "booking"` after class definition (with `# Reason:` comment)
- [x] **`JobRun` model + `JobStatus` enum** in `models.py` — audit log of every scrape / qualify / send job (name, trigger, params_json, summary, error, items_processed, started_at, finished_at)
- [x] **`outreach.jobs` service layer** — `run_scrape_job`, `run_qualify_job`, `run_send_icebreakers_job` share one implementation across CLI, HTTP API, scheduler, and dashboard; every call creates a `JobRun` row, errors are caught and recorded (never propagate into BackgroundTasks)
- [x] **HTTP API (`outreach.api`)** mounted at `/api`: `POST /api/jobs/scrape`, `/api/jobs/qualify`, `/api/jobs/send-icebreakers` (202 + JobRun JSON, work runs in `BackgroundTasks`), `GET /api/jobs`, `GET /api/jobs/{id}`. Auth = `Authorization: Bearer ${API_TOKEN}` **or** valid admin session cookie (so the dashboard never has to expose the token)
- [x] **APScheduler (`outreach.scheduler`)** wired into the FastAPI startup/shutdown hooks — daily qualify cron at `DAILY_QUALIFY_HOUR:DAILY_QUALIFY_MINUTE` (UTC) + optional daily scrape over `DAILY_SCRAPE_QUERIES` (comma-list). Master switch `SCHEDULER_ENABLED=false` by default so it's opt-in
- [x] **Dashboard jobs control panel** (`outreach/admin_jobs.py`): `JobRunAdmin` read-only audit view + `JobsControlView` (custom `BaseView` at `/admin/jobs-control`) with one-click forms for scrape / qualify / send + last-10-runs table. Split into its own module so `admin.py` stays under the 500-line project cap
- [x] **CLI is now a thin shell** over `outreach.jobs` (DRY): `scrape`, `qualify`, `send-icebreaker` delegate; CLI rows are tagged with `trigger="cli"` and show up in the same job log
- [x] New settings: `API_TOKEN`, `SCHEDULER_ENABLED`, `DAILY_QUALIFY_*`, `DAILY_SCRAPE_*` (documented in `outreach/.env.example`); `apscheduler>=3.10` added to `requirements.txt` + `pyproject.toml`
- [x] New tests: `test_jobs.py` (3), `test_api.py` (5), `test_scheduler.py` (3). **All 50 tests pass.**

### 2026-05-26 — Iteration 5: dashboard bulk actions
- [x] **Send Icebreaker (WhatsApp)** action on `LeadAdmin` — auto-picks freeform (sandbox) vs template (production), logs Message, advances status, hard cap of 10/click
- [x] **Send Follow-up Link (WhatsApp)** action — landing + Cal link, freeform-only (24h CSW window)
- [x] **Mark Not Interested** quick action — bulk status update without messaging
- [x] Reuses existing `TwilioWhatsAppClient` + `log_message` + `build_*` helpers (zero duplication with CLI)
- [x] Test for `_parse_pks` helper (expected / edge / failure)

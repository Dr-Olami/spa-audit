# Outreach Toolkit

Python tooling that powers the WhatsApp outreach funnel feeding the landing page.

**Three jobs:**

1. **Source leads** — find salons & spas in Lagos / Abuja via the Google Places API (preferred over scraping Google Maps directly).
2. **Qualify leads** — fetch each business' website, detect whether they already have a booking system, score them.
3. **Reach out & track** — send Twilio WhatsApp messages, log every send and reply in a local SQLite CRM, and receive replies via a FastAPI webhook.

## Why Places API instead of scraping Google Maps?

| | Google Places API (New) | Selenium/Playwright scraping |
| --- | --- | --- |
| **Legal / ToS** | Allowed by Google | Violates Google Maps ToS |
| **Reliability** | Structured JSON, stable | Breaks every few weeks (DOM changes, captchas, IP bans) |
| **Speed** | ~200ms per query, 20 results | 30s+ per query, with captcha risk |
| **Cost** | ~$0.017 per Text Search | "Free" until your IP gets blocked |
| **Data quality** | Place ID, phone, website, rating, review count, status | Same fields, brittle parsing |

We use **Text Search** with a tight field mask so a single request returns everything we need to qualify a lead.

## Setup

Run these from the **workspace root** (`fixerai/`), not from `fixerai/outreach/`:

```powershell
python -m venv outreach\.venv
outreach\.venv\Scripts\activate
pip install -e ".[dev]"
copy outreach\.env.example outreach\.env
notepad outreach\.env       # fill in keys (see below)
outreach init-db            # console script registered by pyproject.toml
```

After `pip install -e .` you can use either form interchangeably from anywhere:

```powershell
outreach init-db
python -m outreach.cli init-db
```

> If you already created `outreach\.venv` and ran `pip install -r outreach\requirements.txt`,
> just run `pip install -e ..` from inside `outreach\` (with the venv active) — that
> registers the package and gives you the `outreach` command without re-creating the venv.

### Required env vars

| Variable | Where to get it |
| --- | --- |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` | https://console.twilio.com (top-right account info) |
| `TWILIO_WHATSAPP_FROM` | Your approved sender: `whatsapp:+14099083940` |
| `TWILIO_USE_SANDBOX` | `true` while testing, `false` once your templates are approved |
| `TWILIO_TEMPLATE_ICEBREAKER_SID` | Created in **Twilio Console → Content Editor**, then submitted to Meta for approval |
| `GOOGLE_PLACES_API_KEY` | https://console.cloud.google.com → enable "Places API (New)" |
| `LANDING_URL` | Your deployed landing page URL |
| `CAL_URL` | `https://cal.com/miracle-edeh/salon-audit` |

## Twilio: sandbox vs production

**Sandbox** (`TWILIO_USE_SANDBOX=true`):

- Sender is Twilio's shared `whatsapp:+14155238886`.
- **Each lead must first text `join <your-sandbox-keyword>` to the sandbox number** before you can message them. This makes sandbox useful for testing the pipeline end-to-end with friends/teammates, not for cold outreach.
- Freeform messages are allowed.

**Production** (`TWILIO_USE_SANDBOX=false`):

- Sender is your own `whatsapp:+14099083940`.
- **Cold outreach to new leads requires a Meta-approved Content template** (template SID `HX...`). Create it in Twilio Console → Content Editor. Once Meta approves it, set `TWILIO_TEMPLATE_ICEBREAKER_SID`.
- After a lead replies, you have a 24-hour customer-service window where freeform messages work — that's when `send-followup` (with the landing page + Cal link) is sent.

This matches the strategy doc: **icebreaker → opt-in reply → link**. We never send a link in the cold first touch.

## Daily workflow

```powershell
# 1. Source leads (run a few targeted queries — cheap)
outreach scrape --query "salon in Lekki, Lagos"           --city Lagos
outreach scrape --query "spa in Victoria Island, Lagos"   --city Lagos
outreach scrape --query "barbershop in Wuse, Abuja"       --city Abuja
outreach scrape --query "nail studio in Maitama, Abuja"   --city Abuja

# 2. Enrich + score (fetches each website, looks for existing booking systems)
outreach qualify --limit 50

# 3. Review the top-scoring leads
outreach list --status qualified --limit 20

# 4. Send icebreakers (sandbox first; production once template is approved)
outreach send-icebreaker --batch 5             # freeform / sandbox
outreach send-icebreaker --batch 5 --template  # production template

# 5. Run the webhook so replies flow in
outreach serve     # binds to WEBHOOK_HOST:WEBHOOK_PORT
# Point Twilio "When a message comes in" to https://<your-public-host>/webhook/whatsapp
# Use ngrok or Cloudflare Tunnel during local dev.

# 6. When a lead replies, send them the landing page + Cal link
outreach send-followup <lead_id>

# 7. Track progress manually if needed
outreach mark <lead_id> booked  --note "Booked Sat 10am"
outreach mark <lead_id> not_interested
```

## Admin dashboard (`/admin`)

When `outreach serve` runs, the **same FastAPI app** also exposes a sqladmin-powered CRUD dashboard at `http://<host>:<port>/admin`. You and your partner can each have credentials, browse / search / filter / edit / create / delete leads and messages, and export to CSV.

Setup (one-time):

```powershell
# Generate a session secret
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Then in `outreach\.env`:

```ini
ADMIN_USERS=miracle:choose-a-strong-pass,abdul:choose-another
ADMIN_SESSION_SECRET=<paste the generated string>
```

Start the server:

```powershell
outreach serve
# Visit http://localhost:8000/admin → log in with one of the configured users
```

What's editable from the dashboard:

- **Leads**: business name, category, city, address, phone, website, IG handle, status, qualification score / notes, has_website, has_booking_system, rating, review_count, free-text notes.
- **Messages**: full CRUD on the WhatsApp audit log (rarely needed — useful for backfilling messages sent outside the system).

### Bulk actions on the Leads list

Tick the checkboxes on one or more rows, then open the **Actions** dropdown:

- **Send Icebreaker (WhatsApp)** — auto-picks freeform (sandbox) vs Meta-approved template (production) based on `TWILIO_USE_SANDBOX`. Logs each send in `Message`, advances lead status to `CONTACTED`.
- **Send Follow-up Link (WhatsApp)** — sends the landing-page + Cal link as freeform. Use this on `REPLIED` leads inside the 24h customer-service window.
- **Mark Not Interested** — bulk-update status to `NOT_INTERESTED` (no message sent).

A hard cap of **10 leads per click** is enforced for the WhatsApp actions to prevent runaway sends and request timeouts.

What's read-only by design (managed by the code):

- `place_id`, `created_at`, `updated_at`, `last_message_sent_at`, `last_reply_at`, `last_reply_text` — all visible on the detail page, hidden from the edit form.

> **Security note:** if `ADMIN_USERS` is empty, the dashboard mounts **without** authentication. That's fine on `localhost` for development, but **never** expose port 8000 publicly in that state. The startup log emits a loud warning when this happens.

## Cal.com booking webhook (`/webhook/cal`)

When a visitor books the free audit on the embedded Cal.com widget, we want them in the same dashboard as our scraped leads — but **flagged as self-booked**, not cold outreach. Cal.com's webhook system makes this automatic.

### One-time setup

1. **Cal.com → Settings → Developer → Webhooks → New**.
2. Subscribe to events: `BOOKING_CREATED`, `BOOKING_RESCHEDULED`, `BOOKING_CANCELLED`.
3. URL: `https://<your-public-host>/webhook/cal` (use ngrok during dev).
4. Copy the **Secret** Cal generates and paste into `outreach\.env`:
   ```ini
   CAL_WEBHOOK_SECRET=<paste-from-cal>
   ```
5. Restart `outreach serve`.

### What happens on each event

| Cal event | Our action |
| --- | --- |
| `BOOKING_CREATED` | Match by `booking_external_id` → email → phone. If a scraped lead matches, **upgrade it** to `BOOKED` and store booking fields. Otherwise insert a fresh lead with `source=BOOKING`, `status=BOOKED`. The "Notes to host" become an inbound `Message`. |
| `BOOKING_RESCHEDULED` | Update `booking_at` on the matched lead, set `booking_status=RESCHEDULED`. |
| `BOOKING_CANCELLED` | Set `booking_status=CANCELLED`. `lead.status` stays `BOOKED` — you can still follow up. |

Signature validation: every request must carry `X-Cal-Signature-256` matching `HMAC-SHA256(CAL_WEBHOOK_SECRET, raw_body)`. Wrong/missing signatures get **403**. If `CAL_WEBHOOK_SECRET` is empty, validation is skipped and a warning is logged (only safe for `localhost`).

### Lead provenance: `source` field

Every Lead now has a `source` enum surfaced as a column in the dashboard:

- **`places`** — scraped from Google Places (cold outreach pool)
- **`booking`** — self-booked via Cal.com webhook (hot inbound lead)
- **`manual`** — added directly through the admin form
- **`instagram`** — placeholder for a future IG-DM integration

In the Leads list, the `source` column lets you sort by source. There's also a dedicated **Bookings** sidebar entry (`/admin/booking/list`) that pre-filters down to `source=BOOKING` and sorts by `booking_at` descending — the fastest way to see "who booked the free audit recently". It inherits every column, search, and bulk action from the main Leads view.

## Run jobs from the dashboard (no terminal needed)

Once `outreach serve` is up, the **Operations → Run jobs** sidebar entry (`/admin/jobs-control`) gives you one-click forms for:

- **Scrape Google Places** — same as `outreach scrape --query "..." --city "..." --max N`.
- **Qualify leads** — same as `outreach qualify --limit N`.
- **Send icebreakers** — same as `outreach send-icebreaker --batch N` (hard-capped at 10).

Every job (CLI, dashboard, HTTP API, or scheduler) is appended to the **Operations → Job runs** audit log: name, trigger, params, status, summary / error, items processed, started / finished timestamps.

## HTTP API (`/api/jobs/*`)

The same jobs are exposed as HTTP endpoints so external cron, Zapier, or the dashboard's own JS can fire them off:

| Method + path | Body | Behaviour |
| --- | --- | --- |
| `POST /api/jobs/scrape` | `{ "query": "salon in Lekki", "city": "Lagos", "max_results": 20 }` | 202 + JobRun JSON; work runs in BackgroundTasks |
| `POST /api/jobs/qualify` | `{ "limit": 50, "only_new": true }` | 202 + JobRun JSON |
| `POST /api/jobs/send-icebreakers` | `{ "batch": 5, "use_template": false }` or `{ "lead_id": 42 }` | 202 + JobRun JSON |
| `GET /api/jobs` | — | List the latest 50 JobRun rows (newest first) |
| `GET /api/jobs/{id}` | — | One JobRun row |

**Auth** is either a Bearer token (`Authorization: Bearer ${API_TOKEN}`) or a valid admin session cookie. Leaving `API_TOKEN` blank disables token auth — only safe on localhost.

```powershell
curl -X POST http://localhost:8000/api/jobs/qualify `
  -H "Authorization: Bearer $env:API_TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"limit":50,"only_new":true}'
```

## Daily cron via in-process scheduler

Set `SCHEDULER_ENABLED=true` in `.env` and APScheduler will run inside `outreach serve`:

- **Daily qualify** at `DAILY_QUALIFY_HOUR:DAILY_QUALIFY_MINUTE` (UTC) over the latest `DAILY_QUALIFY_LIMIT` NEW leads.
- **Daily scrape** at `DAILY_SCRAPE_HOUR:DAILY_SCRAPE_MINUTE` for each query in `DAILY_SCRAPE_QUERIES` (comma-separated; leave blank to skip).

Both scheduled runs land in the same `Job runs` audit log with `trigger=scheduler`. For multi-process deployments use an external cron hitting `/api/jobs/*` instead — APScheduler is in-process and not safe to run in more than one worker.

## Webhook setup (Twilio → us)

1. Run `python -m outreach.cli serve` (or `uvicorn outreach.whatsapp.webhook:app --port 8000`).
2. Expose it publicly during dev: `ngrok http 8000`.
3. In **Twilio Console → Phone Numbers → your WhatsApp sender → Messaging**, set "A message comes in" to: `https://<your-ngrok>.ngrok-free.app/webhook/whatsapp` (POST).
4. Set `TWILIO_WEBHOOK_VALIDATE=true` in production so unsigned requests are rejected.

## Qualification scoring

`outreach.scraper.enrich.qualify_lead` is additive:

| Signal | Points |
| --- | --- |
| No booking system detected on their site | **+40** |
| No "real" website (or only Linktree/Instagram/Facebook) | **+20** |
| Rating between 3.5 and 4.3 (room to grow) | **+15** |
| Fewer than 50 reviews (small / growing) | **+10** |
| Rating ≥ 4.3 with ≥ 50 reviews (proven demand) | **+10** |
| Phone number present (we can reach them) | **+15** |

A lead with score ≥ 50 is auto-promoted from `NEW` to `QUALIFIED` during `qualify`.

## Running tests

```powershell
pytest
```

Tests run on an in-memory SQLite and do not touch Twilio / Google.

## Project layout

```
outreach/
  config.py            Pydantic Settings (.env loader)
  db.py                SQLModel engine + session_scope
  models.py            Lead + Message + LeadStatus
  cli.py               Typer entrypoint (`python -m outreach.cli ...`)
  crm/
    repo.py            CRUD: create_or_update_lead, log_message, ...
  scraper/
    places.py          Google Places API (New) client
    enrich.py          Website fetch + booking detection + scoring
  whatsapp/
    client.py          TwilioWhatsAppClient (freeform + template sends)
    templates.py       Message bodies (icebreaker, follow-up)
    webhook.py         FastAPI app for inbound replies
  tests/
    conftest.py        In-memory SQLite session fixture
    test_models.py
    test_repo.py
    test_enrich.py
    test_templates.py
```

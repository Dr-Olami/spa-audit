# Deploy guide -- spa-audit (frontend on Vercel, backend on Fly.io)

This is a monorepo. The Next.js landing page at the repo root is hosted on
Vercel; the Python FastAPI backend in `outreach/` is hosted on Fly.io. They
do **not** call each other at runtime -- they only meet through Cal.com and
Twilio webhooks pointed at the backend.

```
                                  +---------------+
 visitor --> Vercel (Next.js) --> |   Cal.com     |--(webhook)--> backend /webhook/cal
                                  +---------------+
 visitor reply --> Twilio --(webhook)--> backend /webhook/whatsapp
 you / partner --> browser --> backend /admin  (sqladmin + /admin/jobs-control)
```

---

## 1. One-time prep (local machine)

```powershell
# Verify the backend boots locally
.venv\Scripts\python.exe -m pytest outreach\tests -q

# Make sure outreach/ is NOT in .gitignore (it was earlier -- check line 60-62)
git status outreach    # should now list files, not "ignored"
git add outreach pyproject.toml Dockerfile fly.toml .dockerignore DEPLOY.md
git commit -m "Add Python outreach backend + Fly.io deploy config"
git push origin main
```

## 2. Frontend (Vercel) -- one-time tweak

You already have `spa-audit.vercel.app`. To stop unnecessary rebuilds when
only the backend changes, set **Vercel project --> Settings --> Git --> Ignored
Build Step**:

```bash
git diff HEAD^ HEAD --quiet -- . ':(exclude)outreach' ':(exclude)*.md' ':(exclude)Dockerfile' ':(exclude)fly.toml' ':(exclude).dockerignore'
```

Vercel rebuilds only when files outside `outreach/` and the deploy configs
change. No other Vercel changes needed -- the frontend has zero coupling to
the backend at runtime.

## 3. Backend (Fly.io) -- first deploy

```powershell
# 3.1 Install flyctl + sign up (free, no card required for hobby tier)
iwr https://fly.io/install.ps1 -useb | iex
fly auth signup

# 3.2 Initialise the app from the existing fly.toml.
#     --no-deploy lets us create the volume + secrets BEFORE the first boot.
fly launch --no-deploy --copy-config

# When prompted:
#   - App name: spa-audit-api    (or pick another -- update fly.toml app=)
#   - Region:   pick lhr (London) or jnb (Johannesburg) for Africa latency
#   - Postgres / Redis / sentry: NO to all (we use SQLite on a volume)

# 3.3 Create the persistent disk for SQLite (1 GB, free quota = 3 GB).
fly volume create leads_data --size 1 --region lhr

# 3.4 Push every secret from .env to Fly. Run this once; rotate later via
#     `fly secrets set NAME=newvalue`.
fly secrets set `
    TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" `
    TWILIO_AUTH_TOKEN="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" `
    TWILIO_WHATSAPP_FROM="whatsapp:+14099083940" `
    TWILIO_WHATSAPP_SANDBOX_FROM="whatsapp:+14155238886" `
    TWILIO_TEMPLATE_ICEBREAKER_SID="" `
    GOOGLE_PLACES_API_KEY="AIzaSy..." `
    LANDING_URL="https://spa-audit.vercel.app" `
    CAL_URL="https://cal.com/miracle-edeh/salon-audit" `
    ADMIN_USERS="miracle:CHANGE_ME,abdul:CHANGE_ME" `
    ADMIN_SESSION_SECRET="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" `
    API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" `
    CAL_WEBHOOK_SECRET="from-cal-dot-com-webhook-settings"

# 3.5 First deploy.
fly deploy

# 3.6 Open the dashboard.
fly open /admin     # -> https://spa-audit-api.fly.dev/admin
```

## 4. Wire up the webhooks (one-time)

Once `fly deploy` succeeds, you have a stable HTTPS URL like
`https://spa-audit-api.fly.dev`. Set:

| Service | Where | Value |
| --- | --- | --- |
| **Twilio** | Console -> Phone Numbers -> WhatsApp sender -> "When a message comes in" | `https://spa-audit-api.fly.dev/webhook/whatsapp` (POST) |
| **Cal.com** | Settings -> Developer -> Webhooks -> New | `https://spa-audit-api.fly.dev/webhook/cal`. Subscribe to `BOOKING_CREATED`, `BOOKING_RESCHEDULED`, `BOOKING_CANCELLED`. Copy the secret into `fly secrets set CAL_WEBHOOK_SECRET=...` if it differs from what you set above. |

## 5. Day-2 ops

```powershell
# Tail logs
fly logs

# Open SSH shell into the running container (debug DB, run a one-off CLI)
fly ssh console
# inside:  outreach list --limit 10

# Trigger a job manually via the HTTP API (token from step 3.4)
curl -X POST https://spa-audit-api.fly.dev/api/jobs/qualify `
     -H "Authorization: Bearer $env:API_TOKEN" `
     -H "Content-Type: application/json" `
     -d '{"limit":50,"only_new":true}'

# Backup the SQLite file off the volume to your laptop
fly ssh sftp shell
> get /data/leads.db ./leads-backup.db

# Redeploy after a code change
git push      # then:
fly deploy
```

## 6. Cost-control checklist

- **Single VM, single uvicorn worker.** APScheduler is in-process; multiple
  workers would duplicate every cron run.
- **`auto_stop_machines = false`.** Stopping the VM kills the scheduler and
  forces a 5-10s cold start on the next Twilio webhook (Twilio gives up
  after ~15s, so usually fine, but still annoying).
- **Volume size = 1 GB.** Free tier ceiling is 3 GB total; bump only if
  `messages` rows balloon past ~1M.
- **Logs.** Fly retains 7 days of logs free. Use `fly logs` for live tail;
  long-term retention requires an external sink (skip for now).

## 7. Rollback

```powershell
fly releases             # list deployments
fly releases rollback v<N>
```

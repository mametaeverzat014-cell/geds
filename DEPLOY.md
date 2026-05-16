# GEDS Deployment Guide

Two services, two providers:

- **Frontend (Next.js)** → Vercel — free, native Next.js host
- **Backend (FastAPI + numpy + spaCy)** → Render — free Python web service

> **Why not Supabase for the backend?**
> Supabase is Postgres + Auth + Storage + Edge Functions (Deno only).
> You cannot push a Python FastAPI app to Supabase.
> If you eventually want persistent storage for the news overlay history,
> calibration runs, or the ML dataset, *then* add a Supabase Postgres on top —
> but it's not required for the basic deploy.

---

## 1. Push the repo to GitHub

```bash
cd D:\GEDS
git init
git add .
git commit -m "Initial GEDS commit"
gh repo create geds --public --source=. --remote=origin --push
```

(Or use the GitHub UI — create empty repo, then `git remote add origin <url>` and `git push -u origin main`.)

---

## 2. Deploy the backend to Render

### Option A — Blueprint (one-click, uses `backend/render.yaml`)

1. https://render.com → sign in with GitHub
2. **New** → **Blueprint** → pick your `geds` repo
3. Render detects `backend/render.yaml` automatically and creates the service
4. In the new service's **Environment** tab, set:
   - `GROK_API_KEY` = your xAI key
   - `NEWSAPI_KEY` = your NewsAPI key
   - `GNEWS_KEY` = (optional) your GNews key
   - `GEDS_CORS_ALLOW_ORIGIN_REGEX` = `^https://<your-vercel-project>-.*\.vercel\.app$|^https://<your-vercel-project>\.vercel\.app$`
5. Save → first build takes ~5 min (numpy/scipy/spaCy compile)
6. Note the URL Render gives you: `https://geds-backend-xxxx.onrender.com`

### Option B — manual web service

1. **New** → **Web Service** → connect repo
2. **Root Directory**: `backend`
3. **Runtime**: Python 3
4. **Build Command**:
   ```
   pip install --upgrade pip && pip install -r requirements.txt && python -m spacy download en_core_web_sm
   ```
5. **Start Command**:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
6. Add env vars as above

### Verify backend is up

```bash
curl https://geds-backend-xxxx.onrender.com/api/v1/graph/stats
```

First call may take ~30 s if the free instance is asleep.

---

## 3. Deploy the frontend to Vercel

### Option A — CLI

```bash
cd frontend
npm i -g vercel
vercel link              # follow prompts to create a project
vercel env add NEXT_PUBLIC_API_URL    # paste https://geds-backend-xxxx.onrender.com
vercel env add NEXT_PUBLIC_WS_URL     # paste wss://geds-backend-xxxx.onrender.com
vercel --prod
```

### Option B — Vercel dashboard

1. https://vercel.com → **New Project** → import your `geds` repo
2. **Root Directory**: `frontend`
3. **Framework Preset**: Next.js (auto-detected)
4. **Environment Variables**:
   - `NEXT_PUBLIC_API_URL` = `https://geds-backend-xxxx.onrender.com`
   - `NEXT_PUBLIC_WS_URL` = `wss://geds-backend-xxxx.onrender.com`
5. Deploy

After deploy, your frontend lives at `https://geds-<hash>.vercel.app`.

---

## 4. Update backend CORS to allow the Vercel URL

Once Vercel gives you the real project hostname, update Render's
`GEDS_CORS_ALLOW_ORIGIN_REGEX` to match it (e.g. `^https://geds-yourusername.vercel.app$|^https://geds-yourusername-.*\.vercel\.app$` to allow both production and preview deploys).

Render auto-redeploys on env-var change.

---

## 5. (Optional) Add Supabase Postgres for persistence

If you want news overlays, calibration runs, and the ML dataset to survive
backend restarts (free Render instances lose in-memory state every ~15 min):

1. https://supabase.com → new project (free tier: 500 MB Postgres)
2. Create tables (run in SQL editor):
   ```sql
   create table news_overlays (
     id           uuid primary key default gen_random_uuid(),
     applied_at   timestamptz not null,
     active_until timestamptz not null,
     deltas       jsonb not null
   );
   create table calibration_runs (
     id                 uuid primary key default gen_random_uuid(),
     calibration_date   timestamptz not null,
     best_params        jsonb not null,
     pass_rate_25pct    real not null,
     weighted_rmse      real not null
   );
   create table ml_events (
     id            uuid primary key default gen_random_uuid(),
     ts            timestamptz not null,
     headline      jsonb not null,
     event_type    text,
     matched_nodes text[],
     prediction    jsonb,
     observed      jsonb
   );
   ```
3. Add `supabase-py` to requirements.txt: `pip install supabase`
4. Add `SUPABASE_URL` and `SUPABASE_KEY` to Render env vars
5. In `app/services/event_logger.py` and `app/api/routes.py`, swap the JSONL
   writes for Supabase `client.table('ml_events').insert(...)` calls.

(This step is optional. Skip until you actually need cross-restart persistence.)

---

## Cost summary

| | Free tier | Paid tier (when you need it) |
|---|---|---|
| Vercel Hobby | Yes — fine for ISEF demo | — |
| Render Web (free) | 512 MB RAM, sleeps after 15 min idle | $7/mo Starter — always-on |
| Supabase (free) | 500 MB Postgres | $25/mo Pro |

For an ISEF demo: stick with free. For a public demo with judges hitting it live, upgrade Render to Starter ($7/mo) so the first request isn't a 30-second cold start.

---

## Cold-start mitigation (free-tier hack)

If you stay on Render free, add a cron job in Render that pings your own backend every 10 minutes to keep it warm:

```yaml
# Add to render.yaml under services:
  - type: cron
    name: geds-keepalive
    schedule: "*/10 * * * *"
    runtime: docker
    dockerfilePath: ./keepalive.Dockerfile
    buildCommand: ""
    startCommand: "curl -fsS https://geds-backend-xxxx.onrender.com/api/v1/graph/stats || true"
```

Or just use a free uptime monitor (UptimeRobot) pinging the same URL.

---

## Local dev unchanged

After this is set up, local dev still works the same way:

```cmd
cd /d D:\GEDS\backend
"C:\Users\speed\AppData\Local\Programs\Python\Python311\python.exe" -m uvicorn app.main:app --reload

cd /d D:\GEDS\frontend
npm run dev
```

The frontend defaults to `http://127.0.0.1:8000` when `NEXT_PUBLIC_API_URL` is unset.

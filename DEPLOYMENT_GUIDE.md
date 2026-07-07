# AwakeMovies Scraper — Deployment Guide

> **Written by Agent · 2026-07-07**
> This guide covers all three deployment targets: **Replit**, **Render** (API + Telegram bot), and **Netlify / Vercel** (frontend).
> ⚠️ Read the [Known Bugs](#known-bugs) section first — two critical bugs block deployment.

---

## Table of Contents

1. [Architecture overview](#architecture-overview)
2. [Known Bugs](#known-bugs) ← **Read this first**
3. [Required environment variables](#required-environment-variables)
4. [Part 1 — Deploy on Replit](#part-1--deploy-on-replit)
5. [Part 2 — Deploy API + Telegram bot on Render](#part-2--deploy-api--telegram-bot-on-render)
6. [Part 3 — Deploy Frontend on Netlify](#part-3--deploy-frontend-on-netlify)
7. [Part 4 — Deploy Frontend on Vercel](#part-4--deploy-frontend-on-vercel)
8. [Setting up the Telegram bot](#setting-up-the-telegram-bot)
9. [Keeping the bot alive on Render free tier](#keeping-the-bot-alive-on-render-free-tier)
10. [Post-deployment checklist](#post-deployment-checklist)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                       AwakeMovies Scraper                           │
├───────────────────────────┬─────────────────────────────────────────┤
│  artifacts/api-server     │  artifacts/awakemovies-scraper           │
│  (Node.js + Express 5)    │  (React + Vite)                         │
│                           │                                         │
│  • REST API /api/scrape/* │  • Frontend UI                          │
│  • Telegram bot (Telegraf)│  • Calls API over HTTP                  │
│  • Python scrapers (BS4)  │                                         │
│    ↳ naijaprey.py         │                                         │
│    ↳ ninejarocks.py       │                                         │
│    ↳ nkiri_dramakey.py    │                                         │
└───────────────────────────┴─────────────────────────────────────────┘
```

**Deployment targets:**
- **API server + Telegram bot** → Render (Docker-based Web Service)
- **Frontend** → Netlify or Vercel (static site)
- **Development** → Replit (all-in-one)

---

## Known Bugs

> ⚠️ Fix these before deploying. The fixes are small — confirm with the user/developer first.

### 🔴 Bug 1 — Telegram bot never starts (Critical)

**File:** `artifacts/api-server/src/index.ts`

`startTelegramBot` is imported at the top but **never called**. The HTTP server starts, but the Telegram bot will never launch.

**How to fix:** In `index.ts`, after the `app.listen(...)` block, add:

```typescript
// Start Telegram bot if token is configured
if (process.env["TELEGRAM_BOT_TOKEN"]) {
  startTelegramBot();
} else {
  logger.warn("TELEGRAM_BOT_TOKEN not set — Telegram bot will not start");
}
```

> The `if` guard is important: without it, the bot throws and **crashes the entire Node process** if `TELEGRAM_BOT_TOKEN` is not set. This would take down the HTTP API too.

---

### 🔴 Bug 2 — Frontend missing pages and config files (Critical)

**File:** `artifacts/awakemovies-scraper/src/App.tsx`

App.tsx imports `@/pages/home` and `@/pages/not-found`, but these files **do not exist** in the project. Additionally missing:
- `vite.config.ts`
- `tsconfig.json`
- `tailwind.config.ts`

**The Vite build will fail** — the frontend cannot be deployed until these files are restored.

Contact the original developer for the missing files, or rebuild the missing pages.

---

### 🟡 Bug 3 — scraper-form.tsx is empty (Medium)

**File:** `artifacts/awakemovies-scraper/src/components/scraper-form.tsx`

The file exists but has 0 bytes. Even after Bug 2 is fixed, the scraper form UI will be blank.

---

## Required Environment Variables

| Variable | Service | Required? | Notes |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | api-server | Optional* | Bot won't start without it. Get from @BotFather |
| `PORT` | api-server | Required | Render sets this automatically. Do NOT hardcode. |
| `PYTHON_BIN` | api-server | Auto-set | Dockerfile sets it. Only needed if running outside Docker. |
| `ALLOWED_ORIGIN` | api-server | Optional | CORS. Defaults to `*`. Set to your frontend URL in production. |
| `NODE_ENV` | api-server | Optional | Dockerfile sets `production`. |
| `VITE_API_URL` | frontend | Needed in prod | The URL of your deployed Render API server. |

*Required if you want the Telegram bot to work.

---

## Part 1 — Deploy on Replit

Replit is the all-in-one development environment. It runs everything locally with hot-reload.

### Step 1 — Set secrets

In your Replit project, click the 🔒 **Secrets** tab (or open the Secrets panel) and add:

```
TELEGRAM_BOT_TOKEN = <your token from BotFather>
```

You do **not** need to set `PORT` or `PYTHON_BIN` — Replit and the workflow configs handle those.

### Step 2 — Install Python dependencies

Open the Shell tab and run:
```bash
pip install -r artifacts/api-server/requirements.txt
```

This installs `beautifulsoup4`, `lxml`, and `requests` into Replit's managed Python environment.

### Step 3 — Install Node dependencies

```bash
pnpm install
```

### Step 4 — Run codegen (generate API types)

```bash
pnpm --filter @workspace/api-spec run codegen
```

### Step 5 — Start the API server

The Replit workflow `artifacts/api-server: API Server` handles this. Click **Run** or ask the agent to start the workflow.

To start manually in the shell:
```bash
pnpm --filter @workspace/api-server run dev
```

### Step 6 — Start the frontend

The Replit workflow `artifacts/awakemovies-scraper: web` handles this.

To start manually:
```bash
pnpm --filter @workspace/awakemovies-scraper run dev
```

### Step 7 — Verify

- API health check: `curl localhost:80/api/healthz`
- Frontend: open the preview pane (it should show the scraper UI)
- Telegram bot: send `/start` to your bot in Telegram — it should reply

---

## Part 2 — Deploy API + Telegram Bot on Render

Render is the best option for the backend because it supports Docker, persistent processes (needed for Telegram polling), and environment variables.

### Step 1 — Push your code to GitHub

Render deploys from a Git repository.

```bash
git init
git add .
git commit -m "initial commit"
# Create a repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/awake-bot.git
git push -u origin main
```

### Step 2 — Create a Render account

Go to [render.com](https://render.com) and sign up (free tier works for testing).

### Step 3 — Create a new Web Service

1. In Render dashboard → click **New +** → **Web Service**
2. Connect your GitHub account and select your repository
3. Configure the service:

| Setting | Value |
|---|---|
| **Name** | `awake-bot-api` |
| **Region** | Oregon (US West) or closest to you |
| **Branch** | `main` |
| **Runtime** | **Docker** (not Node — the project uses a Dockerfile) |
| **Dockerfile Path** | `artifacts/api-server/Dockerfile` |
| **Docker Context** | `.` (the repo root) |
| **Instance Type** | Free (for testing) or Starter ($7/mo for always-on) |

> ⚠️ **Important:** Select **Docker** as the runtime. The Dockerfile is at `artifacts/api-server/Dockerfile` and the build context must be the repo root (`.`) because it copies `lib/` and `pnpm-lock.yaml` from the root.

### Step 4 — Set environment variables on Render

In the service settings → **Environment** tab, add:

| Key | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Paste your bot token from BotFather |
| `ALLOWED_ORIGIN` | `https://your-frontend.netlify.app` (or `*` for now) |
| `NODE_ENV` | `production` (already set in Dockerfile, but good to be explicit) |

> Do NOT set `PORT` — Render injects it automatically.
> Do NOT set `PYTHON_BIN` — the Dockerfile sets it to `/repo/.pyvenv/bin/python3`.

### Step 5 — Deploy

Click **Create Web Service**. Render will:
1. Clone your repo
2. Build the Docker image (runs `pnpm install`, creates Python venv, installs `requirements.txt`, runs `pnpm build`)
3. Start the container: `node --enable-source-maps artifacts/api-server/dist/index.mjs`

Build takes ~3–5 minutes on first run. Watch the logs in the Render dashboard.

### Step 6 — Verify the API

Once deployed, Render gives you a URL like `https://awake-bot-api.onrender.com`. Test:

```bash
curl https://awake-bot-api.onrender.com/api/healthz
```

Expected response: `{"status": "ok"}` (or similar)

Test a scrape endpoint:
```bash
curl -X POST https://awake-bot-api.onrender.com/api/scrape/naijaprey \
  -H "Content-Type: application/json" \
  -d '{"url": "https://naijaprey.tv/some-movie/", "mode": "movie"}'
```

### Step 7 — Verify the Telegram bot

After fixing Bug 1 (see above), send `/start` to your Telegram bot. It should respond with the welcome message within a few seconds of the service starting.

### Render free tier limitation

Free tier services **sleep after 15 minutes of inactivity**. A sleeping service takes ~30s to wake up when a request arrives. This means:
- The HTTP API will have cold-start delays
- **The Telegram bot stops receiving messages while sleeping** (polling stops)

To prevent this, see [Keeping the bot alive on Render free tier](#keeping-the-bot-alive-on-render-free-tier).

---

## Part 3 — Deploy Frontend on Netlify

> ⚠️ Requires Bug 2 to be fixed first (missing pages).

### Step 1 — Build the frontend locally (optional test)

```bash
pnpm --filter @workspace/awakemovies-scraper run build
```

Output goes to `artifacts/awakemovies-scraper/dist/`.

### Step 2 — Set the API URL

The frontend needs to know where the API lives in production. Before building, set:

```bash
# In your .env file or CI environment:
VITE_API_URL=https://awake-bot-api.onrender.com
```

In your frontend code, wherever you call the API, use:
```typescript
const API_BASE = import.meta.env.VITE_API_URL ?? "";
```

### Step 3 — Deploy to Netlify

**Option A — Drag and drop (quickest)**
1. Run `pnpm --filter @workspace/awakemovies-scraper run build`
2. Go to [netlify.com](https://netlify.com) → drag the `artifacts/awakemovies-scraper/dist` folder onto the deploy zone
3. Netlify gives you a URL immediately (e.g. `https://random-name.netlify.app`)

**Option B — Git-based deploy (recommended)**
1. Push your code to GitHub
2. On Netlify → **Add new site** → **Import an existing project** → Connect GitHub
3. Configure build settings:

| Setting | Value |
|---|---|
| **Base directory** | `artifacts/awakemovies-scraper` |
| **Build command** | `cd ../.. && pnpm install && pnpm --filter @workspace/awakemovies-scraper run build` |
| **Publish directory** | `artifacts/awakemovies-scraper/dist` |
| **Node version** | 22 (set in Environment Variables: `NODE_VERSION=22`) |

4. Add environment variable: `VITE_API_URL` = your Render URL
5. Click **Deploy site**

### Step 4 — Configure SPA routing

Since the frontend uses `wouter` for client-side routing, Netlify needs to redirect all paths to `index.html`.

Create `artifacts/awakemovies-scraper/public/_redirects`:
```
/*  /index.html  200
```

This file gets copied into the build output automatically.

### Step 5 — Set CORS on your API

Update the `ALLOWED_ORIGIN` environment variable on Render to your Netlify URL:
```
ALLOWED_ORIGIN=https://your-site-name.netlify.app
```

Redeploy the Render service for this to take effect.

---

## Part 4 — Deploy Frontend on Vercel

> ⚠️ Requires Bug 2 to be fixed first (missing pages).

### Step 1 — Install Vercel CLI (optional)

```bash
npm i -g vercel
```

### Step 2 — Deploy with Vercel CLI

```bash
cd artifacts/awakemovies-scraper
vercel
```

Follow the prompts. When asked for build settings:
- **Build command:** `pnpm run build`
- **Output directory:** `dist`
- **Install command:** `cd ../.. && pnpm install`

### Step 3 — Deploy via Vercel Dashboard (no CLI needed)

1. Go to [vercel.com](https://vercel.com) → **Add New Project**
2. Import your GitHub repository
3. Configure:

| Setting | Value |
|---|---|
| **Root Directory** | `artifacts/awakemovies-scraper` |
| **Framework Preset** | Vite |
| **Build Command** | `cd ../.. && pnpm install && pnpm --filter @workspace/awakemovies-scraper run build` |
| **Output Directory** | `dist` |

4. Add Environment Variable: `VITE_API_URL` = your Render API URL
5. Click **Deploy**

### Step 4 — Configure SPA routing on Vercel

Create `artifacts/awakemovies-scraper/vercel.json`:
```json
{
  "rewrites": [
    { "source": "/((?!api).*)", "destination": "/index.html" }
  ]
}
```

---

## Setting Up the Telegram Bot

You need a bot token from Telegram's @BotFather before anything works.

### Step 1 — Create the bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g. "AwakeMovies Scraper")
4. Choose a username (must end in `bot`, e.g. `awakemovies_scraper_bot`)
5. BotFather sends you a token like: `7123456789:AAHxxxx...`

### Step 2 — Set bot commands (optional but recommended)

Still in @BotFather, send `/setcommands` and select your bot. Paste:

```
start - Start the bot and see help
scrape - Scrape a movie or series: /scrape <url>
```

### Step 3 — Add the token to your environment

- **Render:** add `TELEGRAM_BOT_TOKEN` in the service's Environment tab
- **Replit:** add to Secrets panel
- **Local dev:** add to a `.env` file (never commit this file)

### Step 4 — Test the bot

1. Go to Telegram and open your bot
2. Send `/start` — you should see the welcome message
3. Send `/scrape https://naijaprey.tv/some-movie/` — you should get movie/series selection buttons

---

## Keeping the Bot Alive on Render Free Tier

Render free tier sleeps after 15 minutes of inactivity. The Telegram bot uses long-polling, which stops when the process sleeps.

### Option A — Upgrade to Render Starter ($7/month)

This keeps the service always running. Recommended for a production bot.

In Render dashboard → your service → **Settings** → **Instance Type** → select **Starter**.

### Option B — Use a free uptime monitor (keeps free tier awake)

Services like [UptimeRobot](https://uptimerobot.com) (free) ping your API every 5 minutes to prevent sleeping.

1. Sign up at [uptimerobot.com](https://uptimerobot.com)
2. Click **Add New Monitor**:
   - Monitor Type: HTTP(s)
   - Friendly Name: `AwakeBot Keep-Alive`
   - URL: `https://your-awake-bot.onrender.com/api/healthz`
   - Monitoring Interval: **5 minutes**
3. Click **Create Monitor**

Render will no longer sleep as long as UptimeRobot keeps pinging it.

> Note: Render's free tier terms technically discourage keep-alive pinging. For a real production bot, use the Starter plan.

### Option C — Switch to webhook mode (advanced)

Instead of polling (where the bot pulls updates), webhooks push updates to your server. This is more efficient and immune to sleeping issues on paid tiers, but requires HTTPS and a public URL.

This requires changes to `bot.ts` — replace `bot.launch()` with:
```typescript
// Webhook mode (requires HTTPS public URL)
app.use(bot.webhookCallback("/api/telegram-webhook"));
await bot.telegram.setWebhook("https://your-render-url.onrender.com/api/telegram-webhook");
```

---

## Post-Deployment Checklist

### API Server (Render)

- [ ] `GET /api/healthz` returns `{"status":"ok"}` (or similar)
- [ ] `GET /api/scrape/sources` returns the list of 3 sources
- [ ] `POST /api/scrape/naijaprey` with a valid NaijaPrey URL returns movie/series data
- [ ] Render logs show no Python errors (`PYTHON_BIN` path is correct)
- [ ] Telegram bot replies to `/start` in under 5 seconds

### Frontend (Netlify / Vercel)

- [ ] Site loads without a blank page
- [ ] Scraper form is visible (requires Bug 3 fix)
- [ ] API calls from the frontend succeed (check browser DevTools → Network tab)
- [ ] No CORS errors in the browser console

### Telegram Bot

- [ ] `/start` replies with the welcome message
- [ ] `/scrape <naijaprey-url>` shows Movie/Series buttons
- [ ] After selecting Movie or Series, the bot returns the scrape result with poster
- [ ] "View Full JSON", "Copy JSON", and "Download JSON File" buttons work

---

## Troubleshooting

### "PYTHON_BIN not found" or Python errors

The Dockerfile sets `PYTHON_BIN=/repo/.pyvenv/bin/python3`. If you're running outside Docker (e.g. bare Node.js on Render without Docker), set:
```
PYTHON_BIN=/usr/bin/python3
```
And ensure `requirements.txt` deps are installed on the host.

### "TELEGRAM_BOT_TOKEN is required" crash

The bot token is not set. Add it to environment variables. The server will crash and restart repeatedly until the token is provided (until Bug 1 is fixed with the conditional guard).

### Bot doesn't respond after deploying

1. Check Render logs — is there a Python error or "Telegram bot started" log line?
2. Confirm Bug 1 is fixed (bot must actually be started in `index.ts`)
3. Check if the service has gone to sleep (free tier) — try pinging the health endpoint first

### Frontend shows blank page after deploy

1. Bug 2: missing `src/pages/home.tsx` — the Vite build will have failed
2. Check Netlify/Vercel build logs for error details
3. Ensure `vite.config.ts` exists in the frontend directory

### CORS errors in browser

Set `ALLOWED_ORIGIN` on Render to your frontend domain:
```
ALLOWED_ORIGIN=https://your-site.netlify.app
```

---

## Summary of Deploy URLs

After everything is deployed, your URLs will look like:

| Service | URL |
|---|---|
| Render API | `https://awake-bot-api.onrender.com` |
| Health check | `https://awake-bot-api.onrender.com/api/healthz` |
| Scrape sources | `https://awake-bot-api.onrender.com/api/scrape/sources` |
| Netlify frontend | `https://your-site-name.netlify.app` |
| Vercel frontend | `https://your-site-name.vercel.app` |
| Telegram bot | Direct message via Telegram |

---
name: Render-Awake-Bot project audit
description: Full code audit results, bug inventory, and deployment readiness status for the AwakeMovies Scraper project uploaded by user on 2026-07-07.
---

# Render-Awake-Bot — Project Audit

## What this project is

**AwakeMovies Scraper** — a monorepo with two artifacts:

| Artifact | Tech | Purpose |
|---|---|---|
| `artifacts/api-server` | Express 5 + TypeScript + Python (BeautifulSoup) | REST API + Telegram bot |
| `artifacts/awakemovies-scraper` | React + Vite | Frontend scraper UI |

The backend spawns Python scrapers via `child_process.spawn` (stdin→stdout JSON bridge). Three scrapers: 9jarocks, NaijaPrey, Nkiri/Dramakey. Telegram bot uses Telegraf in polling mode.

## Status: 2026-07-07

Current work:
- ✅ Full code audit completed
- ✅ Deployment guide written to `DEPLOYMENT_GUIDE.md`
- ❌ Bugs NOT yet fixed (user must confirm scope)
- ❌ Project NOT yet wired into current Replit workspace artifacts

## Bug Inventory (3 found)

### 🔴 Bug 1 — CRITICAL: Telegram bot is imported but never started
**File:** `artifacts/api-server/src/index.ts`

`startTelegramBot` is imported at the top of `index.ts` but the function is never called anywhere in that file. The HTTP server starts fine, but the Telegram bot will never launch regardless of whether `TELEGRAM_BOT_TOKEN` is set.

**Fix needed:** Add `startTelegramBot();` call inside `index.ts` after `app.listen(...)` succeeds (or unconditionally after the listen block, guarded by `if (process.env.TELEGRAM_BOT_TOKEN)`).

**Why conditional guard matters:** On Render, if `TELEGRAM_BOT_TOKEN` is not set, the current `startTelegramBot()` throws immediately and crashes the entire Node process. A guard lets the HTTP server stay up even when the bot token is absent.

### 🔴 Bug 2 — CRITICAL: Frontend pages are missing from the zip
**File:** `artifacts/awakemovies-scraper/src/App.tsx`

App.tsx imports:
```ts
import Home from "@/pages/home";
import NotFound from "@/pages/not-found";
```

Neither `src/pages/home.tsx` nor `src/pages/not-found.tsx` exist in the uploaded zip. The Vite build will fail immediately. These files were either never created or were accidentally excluded from the zip.

**Also missing:** `vite.config.ts`, `tsconfig.json`, `tailwind.config.ts` (or `.js`) for the frontend artifact.

**Fix needed:** User must provide the missing pages, OR the frontend needs to be rebuilt. Without these files the frontend cannot build or run.

### 🟡 Bug 3 — MEDIUM: scraper-form.tsx is completely empty
**File:** `artifacts/awakemovies-scraper/src/components/scraper-form.tsx`

The file exists but has 0 bytes. This file is the main UI component for the scraper form. Even if the missing pages are restored, this component will cause an empty/broken UI.

**Fix needed:** Component needs to be written/restored by user.

## Architecture notes for deployment

- **Python scrapers:** Not bundled by esbuild. The `.py` files are loaded from source path at runtime. Dockerfile already copies `artifacts/api-server/src/scrapers/` — ✅ correct.
- **Python venv path:** `PYTHON_BIN` env var controls which Python is used. Defaults to `.pythonlibs/bin/python3` (Replit dev). Docker overrides to `/repo/.pyvenv/bin/python3` — ✅ correct.
- **Telegram bot mode:** Long-polling (not webhook). This means the Node process must stay running continuously — fine for Render Web Service but will sleep on free tier after 15 min inactivity. Needs Render free-tier keep-alive OR upgrade to paid.
- **CORS:** `ALLOWED_ORIGIN` env var controls allowed origin, defaults to `*`.
- **Port:** Reads from `PORT` env var (required — throws if missing).

## Deployment readiness

| Component | Render | Netlify/Vercel | Notes |
|---|---|---|---|
| API server | ✅ Dockerfile ready | N/A | Fix Bug 1 first |
| Telegram bot | ⚠️ Fix Bug 1 first | N/A | Will crash if token missing |
| Frontend | ❌ Bug 2 blocks build | ❌ Bug 2 blocks build | Missing pages + vite.config.ts |

## Required environment variables

| Variable | Where used | Notes |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | `artifacts/api-server/src/telegram/bot.ts` | Required for bot, crashes if missing |
| `PORT` | `artifacts/api-server/src/index.ts` | Required, Render sets this automatically |
| `PYTHON_BIN` | `artifacts/api-server/src/lib/pythonRuntime.ts` | Set in Dockerfile as `/repo/.pyvenv/bin/python3` |
| `ALLOWED_ORIGIN` | `artifacts/api-server/src/app.ts` | Optional, defaults to `*` |
| `NODE_ENV` | standard | Set to `production` in Dockerfile |

## Files I must NOT modify (per user instruction)

All source code files. Only allowed to create:
- Documentation files
- Memory files
- Configuration/deployment helper files

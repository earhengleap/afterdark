# AfterDark - Telegram Bot

## Overview
A Python Telegram bot (Pyrogram/Pyrofork) for downloading media from X (Twitter), RedGifs, Porn91, Videy and more, with bulk downloads, AI-powered categorization, and group sync. Imported from GitHub in a "bot-only" state — a previous commit ("Bot-only deployment: removed TWA dashboard") deleted the `dashboard/` FastAPI mini-app referenced in `GEMINI.md`, so only the Telegram bot runs here; there is no web UI.

## Running it
- **Telegram Bot** workflow runs `python afterdark.py` — this is the only workflow/service in the project.
- Deployment is configured as a VM (always-on process) running `python afterdark.py`.

## Configuration
Bot credentials (`BOT_TOKEN`, `API_ID`, `API_HASH`, `CHAT_ID`) are read from environment variables via `config/config.py` → `config/config_loader.py` → `config/settings.py`. They are currently set as shared env vars in this repl (not files).

## Setup notes (2026-07-14)
- Installed missing Python dependencies (`pyrogram`/`pyrofork`, `httpx`, etc. from `requirements.txt`) and the `ffmpeg` system package — the bot now starts and connects successfully.
- Removed the stale "Video Gallery Server" workflow, since `dashboard/server.py` no longer exists in this repo.
- `config/config.py` previously had the bot token, Telegram API credentials, a Neon Postgres connection string (with password), and an UploadThing token hardcoded in plaintext and committed to git. Rewrote it to read all values from environment variables instead; removed the unused Neon/UploadThing constants entirely (nothing in the current codebase uses them since the dashboard was removed). **Note: the old hardcoded values are still visible in this repo's git history** — if this bot token/API credentials are meant to stay private, consider rotating them (regenerate the bot token via @BotFather, and new API_ID/API_HASH via my.telegram.org).

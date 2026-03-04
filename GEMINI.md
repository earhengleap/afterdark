# AfterDark - AI Agent Guidelines

This document provides foundational mandates, architectural context, and coding conventions for AI agents working within the AfterDark project workspace.

## Project Overview
**AfterDark** is a robust Telegram bot platform paired with a locally-hosted Telegram Mini App (TWA) dashboard. It primarily focuses on media management (downloading, organizing, and categorizing) from platforms like X (Twitter), RedGifs, Porn91, and Videy. 

## Tech Stack
- **Language:** Python 3.10+
- **Telegram Framework:** Pyrogram (with Pyrofork extensions)
- **Web Framework (TWA Backend):** FastAPI with Uvicorn
- **Database:** SQLite (managed via `core/database.py`)
- **Media Processing:** `yt-dlp`, `gallery-dl`, `ffmpeg`
- **Optional AI:** Ollama (for auto-categorizing titles)

## Architectural Structure
The workspace is organized into distinct domain boundaries. Ensure code modifications respect these layers:

- `afterdark.py`: The main entry point. Bootstraps both the Telegram bot and background services (like the FastAPI dashboard server and tunnels).
- `config/`: Configuration loaders and environment variable definitions.
- `core/`: Core business logic, independent media downloaders (e.g., `reddit_service.py`, `x_media_service.py`), auto-scheduler, and the SQLite `database.py`.
- `dashboard/`: The TWA (Telegram Mini App) components.
  - `server.py`: FastAPI server serving the Mini App.
  - `public/`: Frontend HTML, CSS (vanilla), and JS for the dashboard.
- `handlers/`: Pyrogram handlers for commands (`command_handlers.py`), callbacks (`callback_handlers.py`), and AI integrations.
- `data/`: Runtime states, PID files, lock files, and the SQLite `.db` file. **Never commit the `.db` files or sensitive data here.**
- `models/`: Data models and Enums used across the application.
- `resources/` / `ui/`: Shared UI elements, keyboards, and language strings.
- `tests/`: Testing suites (Integration, Scraping, Unit). 

## Engineering Mandates

1. **Environment Variables & Secrets:**
   - Never hardcode API keys, tokens, or personal identifiers.
   - Always route configuration through the `config/` module, which should read from `.env`.

2. **Database Operations:**
   - All persistence should be routed through `core/database.py` (SQLite). 
   - Avoid creating new database files unless strictly required; extend `HistoryDB` if adding new tables or models.

3. **Telegram Bot Handlers:**
   - Follow Pyrogram conventions for handlers.
   - Keep handlers lightweight. Offload heavy processing to `core/` services.
   - For long-running operations (like media downloading), utilize background tasks or the `progress_tracker` to avoid blocking the main event loop.

4. **TWA Dashboard (FastAPI):**
   - The dashboard is built with FastAPI and Vanilla CSS/JS. Avoid introducing heavy frontend frameworks (like React or Tailwind) unless explicitly requested.
   - New dashboard API endpoints should be added to `dashboard/server.py`.

5. **Testing:**
   - Run tests located in the `tests/` directory to validate changes when modifying core download logic or providers.

6. **Media Processing:**
   - Fallback to `yt-dlp` or `gallery-dl` for supported extractions. Use `ffmpeg` for thumbnail generation and media manipulation. Ensure robust error handling for external network requests.

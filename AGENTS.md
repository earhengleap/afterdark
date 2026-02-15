# Repository Guidelines

## Project Structure
- `x_telegram.py`: main Telegram bot entrypoint (Pyrogram).
- `core/`: download/upload pipeline, persistence, scheduling, health/metrics.
- `handlers/`: bot commands and callback handlers.
- `config/`: configuration + settings (`config/settings.py` reads env + cookie file).
- `ui/`: message templates and keyboards.
- `utils/`, `models/`: shared helpers and data models.
- `telegram-bot-websites/`: Telegram Mini App (TWA) gallery:
  - Frontend: `index.html`, `script.js`, `style.css`
  - Backend: `server.py` (FastAPI + Pyrogram history sync)
- `tests/`: `unittest` test suite (`test_*.py`).
- Runtime state (ignored by git): `data/`, `users/`, `telegram-bot-websites/media_cache/`, `*.session*`.

## Build, Test, and Development Commands
Install deps (Windows PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the bot:
```powershell
python x_telegram.py
```

Run the Mini App server locally:
```powershell
$env:TELEGRAM_GALLERY_AUTH='user'
python telegram-bot-websites/server.py
```

Run tests:
```powershell
python -m unittest discover -s tests
```

## API Endpoints (Mini App)
- `GET /api/health`
- `GET /api/media`, `GET /api/media/page`, `GET /api/media/recent`
- `GET /api/file/{message_id}`, `GET /api/thumb/{message_id}`
- `POST /api/sync`, `POST /api/ai-titles`

## Coding Style & Naming Conventions
- Python, 4-space indentation; prefer type hints and small focused functions.
- Use `pathlib.Path` for filesystem paths (Windows-safe).
- Tests: name files `tests/test_*.py` and test functions `test_*`.

## Commit & Pull Request Guidelines
- Commit messages commonly use prefixes like `feat:`, `fix:`, `chore:`; follow this where practical.
- Never commit secrets or local state (cookies, DBs, sessions). Keep these untracked:
  `config/twitter_cookies.txt`, `data/*.db`, `users/*.json`, `telegram-bot-websites/media_cache/`, `*.session*`.
- PRs: include a short description, how to test, and screenshots/GIFs for Mini App UI changes.

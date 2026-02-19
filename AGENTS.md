# Repository Guidelines

## Project Structure

- `x_telegram.py`: Main Telegram bot entrypoint (Pyrogram).
- `core/`: Download/upload pipeline, persistence, scheduling, health/metrics.
- `handlers/`: Bot commands and callback handlers.
- `config/`: Configuration and settings (`config/settings.py` reads env + cookie file).
- `ui/`: Message templates and keyboards.
- `utils/`, `models/`: Shared helpers and data models.
- `telegram-bot-websites/`: Telegram Mini App (TWA) gallery:
  - Frontend: `index.html`, `script.js`, `style.css`
  - Backend: `server.py` (FastAPI + Pyrogram history sync)
- `tests/`: `unittest` test suite (`test_*.py`).
- Runtime state (ignored by git): `data/`, `users/`, `telegram-bot-websites/media_cache/`, `*.session*`.

## Build, Test, and Development Commands

### Install Dependencies (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Run the Bot

```powershell
python x_telegram.py
```

### Run the Mini App Server Locally

```powershell
$env:TELEGRAM_GALLERY_AUTH='user'
python telegram-bot-websites/server.py
```

### Run Tests

Run all tests:
```powershell
python -m unittest discover -s tests
```

Run a single test file:
```powershell
python -m unittest tests.test_image_downloader_rename
```

Run a single test function:
```powershell
python -m unittest tests.test_image_downloader_rename.TestImageDownloaderSafeRename.test_safe_rename_does_not_double_prefix
```

### Linting and Type Checking

This project does not have a configured linter. If adding one, consider:
- `ruff` for fast linting (install: `pip install ruff`)
- `mypy` for type checking (install: `pip install mypy`)

Run ruff:
```powershell
ruff check .
```

Run mypy:
```powershell
mypy .
```

## API Endpoints (Mini App)

- `GET /api/health`
- `GET /api/media`, `GET /api/media/page`, `GET /api/media/recent`
- `GET /api/file/{message_id}`, `GET /api/thumb/{message_id}`
- `POST /api/sync`, `POST /api/ai-titles`

## Coding Style & Naming Conventions

### General Principles

- **Python**: Use Python 3.10+ features (type hints, match/case, etc.)
- **Indentation**: 4 spaces (no tabs)
- **Line Length**: Prefer under 100 characters; hard limit at 120
- **Encoding**: UTF-8 for all files

### Type Hints

- Always use type hints for function parameters and return types
- Use `Optional[X]` instead of `X | None` for compatibility
- Use `from typing import List, Dict, Tuple, Optional, Any` as needed
- Use `pathlib.Path` for filesystem paths (Windows-safe)

```python
# Good
def process_file(path: Path, options: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    ...

# Avoid
def process_file(path, options=None):
    ...
```

### Imports

Group imports in this order (separate with blank lines):

1. Standard library
2. Third-party packages
3. Local application imports

Within each group, sort alphabetically:

```python
import asyncio
import json
import logging
from pathlib import Path
from typing import List, Optional, Tuple

import aiofiles
from pyrogram import Client, filters
from pyrogram.types import Message

from config.settings import BOT_TOKEN
from core.downloader import VideoDownloader
from handlers.command_handlers import handle_start
from models.data_models import DownloadResult
```

### Naming Conventions

- **Functions/variables**: `snake_case` (e.g., `download_video`, `max_retries`)
- **Classes**: `PascalCase` (e.g., `VideoDownloader`, `ImageHandler`)
- **Constants**: `SCREAMING_SNAKE_CASE` (e.g., `MAX_FILE_SIZE`, `DEFAULT_TIMEOUT`)
- **Private methods**: Prefix with underscore (e.g., `_internal_method`)
- **Test functions**: `test_<description>` (e.g., `test_download_handles_timeout`)

### Functions and Classes

- Keep functions small and focused (ideally under 50 lines)
- Use docstrings for public APIs and complex logic
- Use logging instead of print statements
- Define logger at module level: `logger = logging.getLogger(__name__)` or `logger = setup_logger("ModuleName")`

```python
logger = logging.getLogger(__name__)


class ImageDownloader:
    """Handle image downloads from X (Twitter) using gallery-dl."""

    @staticmethod
    async def download(
        url: str,
        message: Optional[Message] = None,
        status_callback=None,
        index: int = 1,
        total: int = 1
    ) -> Tuple[Optional[List[str]], Optional[Dict]]:
        """Download images from X URL.
        
        Args:
            url: The URL to download from.
            message: Optional Telegram message for progress updates.
            status_callback: Optional callback for status updates.
            index: Current download index in batch.
            total: Total downloads in batch.
            
        Returns:
            Tuple of (file paths, error info) or (None, None) on failure.
        """
        try:
            # Implementation here
            pass
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None, {"error": str(e)}
```

### Error Handling

- Use try/except blocks with specific exception types when possible
- Log errors with appropriate level (error, warning, debug)
- Return meaningful error information rather than raising generic exceptions
- Use optional return types to indicate failure (e.g., `Tuple[X, None]` vs `Tuple[None, Dict]`)

```python
# Good - return error info
def fetch_data(url: str) -> Optional[Dict]:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logger.warning(f"Request failed: {e}")
        return None
```

### Async/Await Patterns

- Use `asyncio` for concurrent operations
- Check for coroutines with `asyncio.iscoroutine()` before awaiting
- Use `asyncio.gather()` for parallel operations when appropriate

```python
async def process_batch(items: List[str]) -> List[Result]:
    tasks = [process_item(item) for item in items]
    return await asyncio.gather(*tasks)
```

### Testing Conventions

- Test files: `tests/test_*.py`
- Test classes: `Test<Description>(unittest.TestCase)`
- Test functions: `test_<expected_behavior>`
- Use `unittest.mock.patch` for mocking
- Use `contextlib.contextmanager` for temp directory setup in tests

```python
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


@contextmanager
def _writable_temp_dir() -> str:
    """Create a writable temp directory for tests."""
    base = Path(__file__).resolve().parent / "_tmp"
    base.mkdir(parents=True, exist_ok=True)
    target = base / f"tmp_{uuid.uuid4().hex}"
    target.mkdir()
    try:
        yield str(target)
    finally:
        shutil.rmtree(target, ignore_errors=True)


class TestImageDownloaderRename(unittest.TestCase):
    def test_safe_rename_does_not_double_prefix(self) -> None:
        with _writable_temp_dir() as tmp:
            # Test implementation
            pass
```

### Database and Persistence

- Use SQLite for local storage (stored in `data/` directory)
- Use JSON files for user-specific data (stored in `users/` directory)
- Follow the patterns in `core/database.py` for DB operations
- Follow the patterns in `users/users.py` for user data

## Commit & Pull Request Guidelines

- **Commit messages**: Use prefixes like `feat:`, `fix:`, `chore:`, `refactor:`, `test:`
- **Never commit secrets**: Keep these untracked:
  - `config/twitter_cookies.txt`
  - `data/*.db`
  - `users/*.json`
  - `telegram-bot-websites/media_cache/`
  - `*.session*`
- **PR description**: Include short description, how to test, and screenshots/GIFs for UI changes

## Key Dependencies

- **Pyrogram** / **pyrofork**: Telegram bot framework
- **FastAPI**: Mini App server
- **gallery-dl**: Media downloading
- **yt-dlp**: Video downloading
- **pydantic**: Data validation
- **asyncio**: Async operations

## Common Patterns

### Logger Setup

```python
from core.logger import setup_logger

logger = setup_logger("ComponentName")
```

### Configuration Access

```python
from config.settings import BOT_TOKEN, API_ID, API_HASH

# Or load from environment
import os
custom_value = os.environ.get("CUSTOM_VAR", "default")
```

### Telegram Message Handling

```python
from pyrogram import Client, filters
from pyrogram.types import Message

@client.on_message(filters.command("start"))
async def handle_start(client: Client, message: Message) -> None:
    await message.reply("Hello!")
```

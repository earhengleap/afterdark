#!/usr/bin/env python3
"""
Telegram Mini App Gallery Server.

- Pulls media (videos/images) from configured Telegram group (CHAT_ID)
- Serves a Telegram Web App (Mini App) frontend
- Supports auth modes for history access:
  - bot  : bot token session (cannot read full history; limited)
  - user : user session (recommended for history)
  - auto : prefer user session if available, otherwise bot
"""

from __future__ import annotations

import asyncio
from collections import deque
from contextlib import asynccontextmanager, suppress
import base64
import hashlib
import hmac
import io
import json
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl
import urllib.request

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pyrogram import Client
from pyrogram.errors import RPCError
try:
    from PIL import Image
except Exception:
    Image = None

if os.name == "nt":
    # Selector loop is more stable than Proactor for high churn TCP closes on Windows.
    with suppress(Exception):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())  # type: ignore[attr-defined]

WEB_DIR = Path(__file__).resolve().parent
ROOT_DIR = WEB_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import API_HASH, API_ID, BOT_TOKEN, BOT_USERNAME, CHAT_ID  # noqa: E402

try:  # noqa: E402
    from config.settings import FFMPEG_PATH as SETTINGS_FFMPEG_PATH
except Exception:  # noqa: E402
    SETTINGS_FFMPEG_PATH = ""

try:
    PORT = int(os.getenv("TWA_PORT", "5000").strip() or "5000")
except ValueError:
    PORT = 5000
DEFAULT_SYNC_LIMIT = 250
STRICT_TWA_VERIFY = os.getenv("TWA_VERIFY_STRICT", "0") == "1"
SYNC_TIMEOUT_SECONDS = max(10, int(os.getenv("TWA_SYNC_TIMEOUT_SECONDS", "90")))
DOWNLOAD_TIMEOUT_SECONDS = max(10, int(os.getenv("TWA_DOWNLOAD_TIMEOUT_SECONDS", "180")))
SERVICE_START_TIMEOUT_SECONDS = max(5, int(os.getenv("TWA_SERVICE_START_TIMEOUT_SECONDS", "20")))
try:
    SYNC_API_MAX_WAIT_SECONDS = max(3, int(os.getenv("TWA_SYNC_API_MAX_WAIT_SECONDS", "18").strip() or "18"))
except ValueError:
    SYNC_API_MAX_WAIT_SECONDS = 18
EAGER_DOWNLOAD_MEDIA = os.getenv("TWA_EAGER_DOWNLOAD_MEDIA", "0").strip() == "1"
EAGER_VIDEO_THUMBS = os.getenv("TWA_EAGER_VIDEO_THUMBS", "0").strip() == "1"
LIVE_SYNC_ENABLED = os.getenv("TWA_LIVE_SYNC", "1").strip().lower() not in {"0", "off", "false", "disabled", "no"}
try:
    LIVE_SYNC_SECONDS = max(5, int(os.getenv("TWA_LIVE_SYNC_SECONDS", "8").strip() or "8"))
except ValueError:
    LIVE_SYNC_SECONDS = 8
try:
    _live_limit_raw = int(os.getenv("TWA_LIVE_SYNC_LIMIT", "120").strip() or "120")
except ValueError:
    _live_limit_raw = 120
if _live_limit_raw <= 0:
    _live_limit_raw = 120
LIVE_SYNC_LIMIT = max(20, min(_live_limit_raw, 500))
AI_TITLE_ENABLED = os.getenv("TWA_AI_TITLES", "1").strip().lower() not in {"0", "off", "false", "disabled", "no"}
AI_TITLE_PROVIDER = os.getenv("TWA_AI_TITLE_PROVIDER", "ollama").strip().lower() or "ollama"
AI_TITLE_OLLAMA_URL = os.getenv("TWA_AI_OLLAMA_URL", "http://127.0.0.1:11434/api/generate").strip()
# Default to a lightweight local vision model that runs reliably on low resources.
AI_TITLE_MODEL = os.getenv("TWA_AI_MODEL", "moondream:latest").strip() or "moondream:latest"
_fallback_models_raw = os.getenv("TWA_AI_FALLBACK_MODELS", "").strip()
AI_TITLE_FALLBACK_MODELS: List[str] = []
_seen_models: set[str] = set()
for _candidate in [AI_TITLE_MODEL] + [x.strip() for x in _fallback_models_raw.split(",") if x.strip()]:
    if not _candidate or _candidate in _seen_models:
        continue
    _seen_models.add(_candidate)
    if _candidate != AI_TITLE_MODEL:
        AI_TITLE_FALLBACK_MODELS.append(_candidate)
del _seen_models, _fallback_models_raw, _candidate
AI_TITLE_STYLE = os.getenv("TWA_AI_TITLE_STYLE", "explicit").strip().lower() or "explicit"
if AI_TITLE_STYLE not in {"tasteful", "explicit"}:
    AI_TITLE_STYLE = "explicit"
AI_TITLE_TEXT_MODEL = os.getenv("TWA_AI_TEXT_MODEL", "dolphin-llama3:8b").strip() or "dolphin-llama3:8b"
_text_fallback_raw = os.getenv("TWA_AI_TEXT_FALLBACK_MODELS", "").strip()
AI_TITLE_TEXT_FALLBACK_MODELS: List[str] = []
_seen_text_models: set[str] = set()
for _candidate in [AI_TITLE_TEXT_MODEL] + [x.strip() for x in _text_fallback_raw.split(",") if x.strip()]:
    if not _candidate or _candidate in _seen_text_models:
        continue
    _seen_text_models.add(_candidate)
    if _candidate != AI_TITLE_TEXT_MODEL:
        AI_TITLE_TEXT_FALLBACK_MODELS.append(_candidate)
del _seen_text_models, _text_fallback_raw, _candidate
# Default safety fallback so misconfigured/missing text models still produce titles.
if not AI_TITLE_TEXT_FALLBACK_MODELS and AI_TITLE_TEXT_MODEL != "gemma3:4b":
    AI_TITLE_TEXT_FALLBACK_MODELS.append("gemma3:4b")
AI_TITLE_POLISH_ENABLED = (
    os.getenv("TWA_AI_POLISH_TITLES", "1" if AI_TITLE_STYLE == "explicit" else "0").strip().lower()
    not in {"0", "off", "false", "disabled", "no"}
)
# Default to missing-only so we don't keep rewriting existing titles automatically.
# When you want to improve older titles, manually call POST /api/ai-titles?mode=style or set TWA_AI_RETITLE_MODE=style temporarily.
AI_TITLE_RETITLE_MODE = os.getenv("TWA_AI_RETITLE_MODE", "missing").strip().lower() or "missing"
if AI_TITLE_RETITLE_MODE not in {"missing", "fallback", "style", "force"}:
    AI_TITLE_RETITLE_MODE = "missing"
try:
    AI_TITLE_TIMEOUT_SECONDS = max(20, int(os.getenv("TWA_AI_TIMEOUT_SECONDS", "240").strip() or "240"))
except ValueError:
    AI_TITLE_TIMEOUT_SECONDS = 240
try:
    _per_item_raw = int(os.getenv("TWA_AI_PER_ITEM_TIMEOUT_SECONDS", "0").strip() or "0")
    # 0 disables extra per-item timeout; we still rely on AI_TITLE_TIMEOUT_SECONDS for the HTTP request.
    AI_TITLE_PER_ITEM_TIMEOUT_SECONDS = 0 if _per_item_raw <= 0 else max(8, _per_item_raw)
except ValueError:
    AI_TITLE_PER_ITEM_TIMEOUT_SECONDS = 0
try:
    AI_TITLE_BATCH_SIZE_MAX = max(1, int(os.getenv("TWA_AI_BATCH_SIZE_MAX", "25").strip() or "25"))
except ValueError:
    AI_TITLE_BATCH_SIZE_MAX = 25
# Keep this bounded so a misconfig doesn't accidentally hang the server.
AI_TITLE_BATCH_SIZE_MAX = max(1, min(AI_TITLE_BATCH_SIZE_MAX, 5000))
try:
    AI_TITLE_BATCH_SIZE = max(1, min(int(os.getenv("TWA_AI_BATCH_SIZE", "3").strip() or "3"), AI_TITLE_BATCH_SIZE_MAX))
except ValueError:
    AI_TITLE_BATCH_SIZE = 3
try:
    # 0 means scan full cached index (backfill titles for older media).
    _scan_raw = int(os.getenv("TWA_AI_RECENT_SCAN_LIMIT", "0").strip() or "0")
    AI_TITLE_RECENT_SCAN_LIMIT = 0 if _scan_raw <= 0 else _scan_raw
except ValueError:
    AI_TITLE_RECENT_SCAN_LIMIT = 0
try:
    AI_TITLE_POLL_SECONDS = max(5, int(os.getenv("TWA_AI_POLL_SECONDS", "12").strip() or "12"))
except ValueError:
    AI_TITLE_POLL_SECONDS = 12
try:
    AI_TITLE_FAILURE_COOLDOWN_SECONDS = max(5, int(os.getenv("TWA_AI_FAILURE_COOLDOWN_SECONDS", "45").strip() or "45"))
except ValueError:
    AI_TITLE_FAILURE_COOLDOWN_SECONDS = 45
try:
    AI_TITLE_API_MAX_WAIT_SECONDS = max(5, int(os.getenv("TWA_AI_API_MAX_WAIT_SECONDS", "25").strip() or "25"))
except ValueError:
    AI_TITLE_API_MAX_WAIT_SECONDS = 25
try:
    AI_TITLE_MAX_IMAGE_SIDE = max(320, int(os.getenv("TWA_AI_MAX_IMAGE_SIDE", "896").strip() or "896"))
except ValueError:
    AI_TITLE_MAX_IMAGE_SIDE = 896
try:
    AI_TITLE_IMAGE_QUALITY = max(40, min(int(os.getenv("TWA_AI_IMAGE_QUALITY", "80").strip() or "80"), 95))
except ValueError:
    AI_TITLE_IMAGE_QUALITY = 80
AI_TITLE_IMAGE_PRIORITY = os.getenv("TWA_AI_IMAGE_PRIORITY", "1").strip().lower() not in {"0", "off", "false", "disabled", "no"}
try:
    AI_TITLE_QUEUE_MAX = max(100, int(os.getenv("TWA_AI_QUEUE_MAX", "1200").strip() or "1200"))
except ValueError:
    AI_TITLE_QUEUE_MAX = 1200
SESSION_LOCK_RECOVERY_ENABLED = os.getenv("TWA_SESSION_LOCK_RECOVERY", "1").strip().lower() not in {"0", "off", "false", "disabled", "no"}
SESSION_CLONE_CLEANUP = os.getenv("TWA_SESSION_CLONE_CLEANUP", "1").strip().lower() not in {"0", "off", "false", "disabled", "no"}

GALLERY_AUTH_MODE = os.getenv("TELEGRAM_GALLERY_AUTH", "auto").strip().lower()
if GALLERY_AUTH_MODE not in {"auto", "bot", "user"}:
    GALLERY_AUTH_MODE = "auto"

GALLERY_USER_SESSION = os.getenv("TELEGRAM_GALLERY_SESSION", "twa_user")
NO_LIMIT_TOKENS = {"", "all", "none", "nolimit", "no-limit", "0", "-1", "inf", "infinite"}
logger = logging.getLogger("twa.gallery")


def parse_limit_value(raw: str | int | None, default: Optional[int] = None) -> Optional[int]:
    if raw is None:
        return default

    if isinstance(raw, int):
        return None if raw <= 0 else raw

    text = str(raw).strip().lower()
    if text in NO_LIMIT_TOKENS:
        return None

    value = int(text)
    return None if value <= 0 else value


def apply_limit(items: List[Dict[str, Any]], limit: Optional[int]) -> List[Dict[str, Any]]:
    if limit is None:
        return items
    return items[:limit]


def latest_message_id(items: List[Dict[str, Any]]) -> int:
    if not items:
        return 0
    try:
        return int(items[0].get("message_id", 0))
    except (TypeError, ValueError, AttributeError):
        return 0


def count_ai_titled_items(items: List[Dict[str, Any]]) -> int:
    return sum(1 for item in items if str(item.get("ai_title", "")).strip())

def compute_gallery_stats(items: List[Dict[str, Any]]) -> Dict[str, int]:
    total = len(items)
    videos = 0
    images = 0
    total_bytes = 0
    for item in items:
        if str(item.get("media_kind", "")) == "video":
            videos += 1
        else:
            images += 1
        try:
            total_bytes += int(item.get("size") or 0)
        except (TypeError, ValueError):
            pass
    return {"total": total, "videos": videos, "images": images, "bytes": total_bytes}


class TelegramMiniAppAuth:
    @staticmethod
    def _build_data_check_string(init_data: str) -> Tuple[str, str]:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", "")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        return data_check_string, received_hash

    @staticmethod
    def verify(init_data: str, bot_token: str) -> bool:
        if not init_data:
            return False

        data_check_string, received_hash = TelegramMiniAppAuth._build_data_check_string(init_data)
        if not received_hash:
            return False

        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(calculated_hash, received_hash)

    @staticmethod
    def extract_payload(init_data: str) -> Dict[str, Any]:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        payload: Dict[str, Any] = {
            "query_id": pairs.get("query_id"),
            "auth_date": pairs.get("auth_date"),
            "start_param": pairs.get("start_param"),
            "chat_type": pairs.get("chat_type"),
            "chat_instance": pairs.get("chat_instance"),
        }

        for key in ("user", "chat", "receiver"):
            raw = pairs.get(key)
            if raw:
                try:
                    payload[key] = json.loads(raw)
                except ValueError:
                    payload[key] = None
            else:
                payload[key] = None

        return payload


class TelegramGalleryService:
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.index_path = self.cache_dir / "media_index.json"
        self.last_sync_at: Optional[str] = None
        self.last_sync_limit = 0
        self.last_sync_full = False
        self.media_index: List[Dict[str, Any]] = []
        self.last_sync_error: Optional[str] = None
        self._lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()
        self._ai_title_lock = asyncio.Lock()
        self._started = False
        self._last_ai_failure_at = 0.0
        self._ai_queue: deque[int] = deque()
        self._ai_queue_ids: set[int] = set()
        self._background_sync_task: Optional[asyncio.Task] = None
        self._ollama_models_cached_at = 0.0
        self._ollama_models_cache: set[str] = set()
        self._base_session_name = GALLERY_USER_SESSION
        self._active_session_name = GALLERY_USER_SESSION
        self._session_clone_name: Optional[str] = None

        self.session_mode = self._resolve_session_mode()
        if self.session_mode == "user":
            self._active_session_name = GALLERY_USER_SESSION
        else:
            self._active_session_name = "web_gallery_session"
        self.client = self._build_client(self.session_mode, session_name=self._active_session_name)
        self.ffmpeg_bin = self._resolve_ffmpeg_bin()
        # Load cached index immediately so the Mini App can render even if Telegram auth/start is slow.
        self._load_index()

    @staticmethod
    def _resolve_ffmpeg_bin() -> Optional[str]:
        override = os.getenv("TWA_FFMPEG_BIN", "").strip()
        if override:
            override_path = Path(override)
            if override_path.exists():
                return str(override_path)
            found_override = shutil.which(override)
            if found_override:
                return found_override

        configured = str(SETTINGS_FFMPEG_PATH or "").strip()
        if configured and Path(configured).exists():
            return configured

        return shutil.which("ffmpeg")

    def _resolve_session_mode(self) -> str:
        if GALLERY_AUTH_MODE in {"bot", "user"}:
            return GALLERY_AUTH_MODE

        user_session_path = self.cache_dir / f"{GALLERY_USER_SESSION}.session"
        if user_session_path.exists():
            return "user"

        return "bot"

    def _build_client(self, mode: str, session_name: Optional[str] = None) -> Client:
        if mode == "user":
            resolved_name = session_name or GALLERY_USER_SESSION
            return Client(
                name=resolved_name,
                api_id=API_ID,
                api_hash=API_HASH,
                workdir=str(self.cache_dir),
            )

        resolved_name = session_name or "web_gallery_session"
        return Client(
            name=resolved_name,
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            # Bot sessions do not need to persist on disk; keeping them in-memory avoids sqlite locks
            # when multiple TWA backends are accidentally started.
            in_memory=True,
            workdir=str(self.cache_dir),
        )

    @staticmethod
    def _is_session_locked_error(exc: Exception) -> bool:
        return "database is locked" in str(exc).lower()

    def _session_file_path(self, session_name: str, suffix: str = ".session") -> Path:
        return self.cache_dir / f"{session_name}{suffix}"

    def _clone_locked_user_session(self) -> Optional[str]:
        source_name = self._base_session_name
        source_main = self._session_file_path(source_name, ".session")
        if not source_main.exists():
            return None

        clone_name = f"{source_name}_clone_{os.getpid()}_{int(time.time())}"
        artifacts = (".session", ".session-journal", ".session-wal", ".session-shm")

        copied: List[Path] = []
        try:
            for suffix in artifacts:
                src = self._session_file_path(source_name, suffix)
                dst = self._session_file_path(clone_name, suffix)
                if not src.exists():
                    continue
                shutil.copy2(src, dst)
                copied.append(dst)
        except OSError:
            for path in copied:
                with suppress(OSError):
                    path.unlink(missing_ok=True)
            return None

        clone_main = self._session_file_path(clone_name, ".session")
        if not clone_main.exists():
            return None

        return clone_name

    def _cleanup_session_artifacts(self, session_name: str) -> None:
        artifacts = (".session", ".session-journal", ".session-wal", ".session-shm")
        for suffix in artifacts:
            path = self._session_file_path(session_name, suffix)
            with suppress(OSError):
                path.unlink(missing_ok=True)

    def _enqueue_ai_title(self, message_id: int) -> None:
        if message_id <= 0:
            return
        if message_id in self._ai_queue_ids:
            return

        self._ai_queue.append(message_id)
        self._ai_queue_ids.add(message_id)

        while len(self._ai_queue) > AI_TITLE_QUEUE_MAX:
            dropped = self._ai_queue.popleft()
            self._ai_queue_ids.discard(dropped)

    async def start(self) -> None:
        async with self._start_lock:
            if self._started:
                return

            try:
                await self.client.start()
            except Exception as exc:
                if not (SESSION_LOCK_RECOVERY_ENABLED and self._is_session_locked_error(exc)):
                    raise

                if self.session_mode == "user":
                    clone_name = self._clone_locked_user_session()
                    if clone_name:
                        fallback_client = self._build_client("user", session_name=clone_name)
                        await fallback_client.start()
                        self.client = fallback_client
                        self._active_session_name = clone_name
                        self._session_clone_name = clone_name
                        logger.warning(
                            "Recovered from locked user session '%s' by using cloned session '%s'.",
                            self._base_session_name,
                            clone_name,
                        )
                        self.last_sync_error = (
                            f"Session lock detected on '{self._base_session_name}'. "
                            f"Recovered using cloned session '{clone_name}'."
                        )
                    else:
                        # Windows can deny copying a locked sqlite session file. In that case, degrade gracefully:
                        # fall back to bot auth so the Mini App still loads from cache/recent media.
                        fallback_name = f"web_gallery_fallback_{os.getpid()}_{int(time.time())}"
                        fallback_client = self._build_client("bot", session_name=fallback_name)
                        await fallback_client.start()
                        self.client = fallback_client
                        self.session_mode = "bot"
                        self._active_session_name = fallback_name
                        self._session_clone_name = None
                        logger.warning(
                            "User session '%s' is locked and clone could not be created; falling back to bot session '%s'.",
                            self._base_session_name,
                            fallback_name,
                        )
                        self.last_sync_error = (
                            f"Session lock detected on '{self._base_session_name}' and clone failed. "
                            "Fell back to bot auth (history may be limited)."
                        )
                else:
                    # Bot auth should be in-memory (no sqlite), but handle any lock edge-cases anyway.
                    previous_name = self._active_session_name
                    fallback_name = f"web_gallery_inmem_{os.getpid()}_{int(time.time())}"
                    fallback_client = self._build_client("bot", session_name=fallback_name)
                    await fallback_client.start()
                    self.client = fallback_client
                    self.session_mode = "bot"
                    self._active_session_name = fallback_name
                    self._session_clone_name = None
                    logger.warning(
                        "Bot session '%s' reported locked; recovered using in-memory session '%s'.",
                        previous_name,
                        fallback_name,
                    )
                    self.last_sync_error = (
                        "Session lock detected for bot auth. Recovered using in-memory bot session."
                    )

            self._started = True
            self._load_index()

    async def stop(self) -> None:
        if self._started:
            await self.client.stop()
            self._started = False
        if self._session_clone_name and SESSION_CLONE_CLEANUP:
            self._cleanup_session_artifacts(self._session_clone_name)
            self._session_clone_name = None

    def _load_index(self) -> None:
        if not self.index_path.exists():
            self._load_index_from_cache_files()
            return
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
            self.media_index = payload.get("items", [])
            self.last_sync_at = payload.get("synced_at")
            raw_limit = payload.get("limit", 0)
            self.last_sync_limit = int(raw_limit) if raw_limit is not None else 0
            self.last_sync_full = bool(payload.get("full_sync", False))
            self.last_sync_error = payload.get("last_error")
        except (ValueError, OSError):
            self.media_index = []
            self._load_index_from_cache_files()
        else:
            # Scrub any previously-stored unsafe titles (e.g., "teen/school") so they never reach the UI.
            self._scrub_blocked_ai_titles()

    def _load_index_from_cache_files(self) -> None:
        # Fallback index path for fast UI boot when no JSON index exists yet.
        # Files are named like "<message_id>_video.mp4" or "<message_id>_image.jpg".
        file_pattern = re.compile(r"^(?P<message_id>\d+)_(?P<kind>video|image)\.[^.]+$")
        items: List[Dict[str, Any]] = []

        for local_path in self.cache_dir.iterdir():
            if not local_path.is_file():
                continue

            match = file_pattern.match(local_path.name)
            if not match:
                continue

            try:
                stat = local_path.stat()
                message_id = int(match.group("message_id"))
                media_kind = match.group("kind")
                guessed_mime, _ = mimetypes.guess_type(local_path.name)
                mime_type = guessed_mime or ("video/mp4" if media_kind == "video" else "image/jpeg")
                modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            except OSError:
                continue

            items.append(
                {
                    "message_id": message_id,
                    "media_kind": media_kind,
                    "file_name": local_path.name,
                    "url": f"/media/{local_path.name}",
                    "thumb_url": (
                        f"/media/{self._thumb_file_name(message_id)}"
                        if (media_kind == "video" and self._thumb_path(message_id).exists())
                        else (f"/media/{local_path.name}" if media_kind == "image" else f"/assets/video-placeholder.svg")
                    ),
                    "mime_type": mime_type,
                    "size": int(stat.st_size),
                    "is_cached": True,
                    "width": None,
                    "height": None,
                    "duration": None,
                    "caption": "",
                    "ai_title": "",
                    "date": modified_at,
                }
            )

        if not items:
            return

        items.sort(key=lambda item: item["message_id"], reverse=True)
        self.media_index = items
        self.last_sync_limit = len(items)
        self.last_sync_full = False
        self.last_sync_at = datetime.now(timezone.utc).isoformat()
        self.last_sync_error = None
        self._save_index()

    def _save_index(self) -> None:
        payload = {
            "synced_at": self.last_sync_at,
            "limit": self.last_sync_limit,
            "full_sync": self.last_sync_full,
            "items": self.media_index,
            "last_error": self.last_sync_error,
            "session_mode": self.session_mode,
        }
        self.index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _scrub_blocked_ai_titles(self) -> None:
        if not self.media_index:
            return

        changed = False
        for entry in self.media_index:
            title = str(entry.get("ai_title", "")).strip()
            if not title:
                continue
            if not self._contains_blocked_title_terms(title):
                continue

            # Remove unsafe title and re-enqueue for adult-only re-analysis.
            entry["ai_title"] = ""
            entry["ai_title_style"] = ""
            entry["ai_title_model"] = ""
            entry["ai_title_generated_at"] = None
            entry["ai_title_is_fallback"] = False
            try:
                msg_id = int(entry.get("message_id", 0))
            except (TypeError, ValueError):
                msg_id = 0
            if msg_id > 0:
                self._enqueue_ai_title(msg_id)
            changed = True

        if changed:
            self._save_index()

    def _merge_partial_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        existing_by_id = {int(x.get("message_id", 0)): x for x in self.media_index}
        incoming_by_id = {int(x.get("message_id", 0)): x for x in items}

        merged_map: Dict[int, Dict[str, Any]] = {}
        for msg_id, old_item in existing_by_id.items():
            if msg_id in incoming_by_id:
                merged_item = {**old_item, **incoming_by_id[msg_id]}
                incoming_title = str(merged_item.get("ai_title", "")).strip()
                if incoming_title and self._contains_blocked_title_terms(incoming_title):
                    merged_item["ai_title"] = ""
                    merged_item["ai_title_style"] = ""
                    merged_item["ai_title_model"] = ""
                    merged_item["ai_title_generated_at"] = None
                    merged_item["ai_title_is_fallback"] = False

                if not str(merged_item.get("ai_title", "")).strip():
                    old_ai_title = str(old_item.get("ai_title", "")).strip()
                    if old_ai_title and not self._contains_blocked_title_terms(old_ai_title):
                        merged_item["ai_title"] = old_ai_title
                merged_map[msg_id] = merged_item
            else:
                merged_map[msg_id] = old_item

        for msg_id, new_item in incoming_by_id.items():
            if msg_id not in merged_map:
                merged_map[msg_id] = new_item

        merged = list(merged_map.values())
        merged.sort(key=lambda item: int(item.get("message_id", 0)), reverse=True)
        return merged

    @staticmethod
    def _thumb_file_name(message_id: int) -> str:
        return f"{message_id}_thumb.jpg"

    def _thumb_path(self, message_id: int) -> Path:
        return self.cache_dir / self._thumb_file_name(message_id)

    def _thumb_url_if_cached(self, message_id: int) -> Optional[str]:
        thumb_path = self._thumb_path(message_id)
        if thumb_path.exists():
            return f"/media/{thumb_path.name}"
        return None

    @staticmethod
    def _pick_best_thumb(media_obj: Any) -> Optional[Any]:
        thumbs = getattr(media_obj, "thumbs", None)
        if not thumbs:
            return None
        if isinstance(thumbs, list):
            return thumbs[-1] if thumbs else None
        return thumbs

    async def _ensure_video_thumb(self, message: Any, media_obj: Any, message_id: int) -> Optional[Path]:
        thumb_path = self._thumb_path(message_id)
        if thumb_path.exists():
            return thumb_path

        thumb_obj = self._pick_best_thumb(media_obj)
        if not thumb_obj:
            return None

        try:
            downloaded = await asyncio.wait_for(
                self.client.download_media(thumb_obj, file_name=str(thumb_path)),
                timeout=min(30, DOWNLOAD_TIMEOUT_SECONDS),
            )
        except Exception:
            return None

        if not downloaded:
            return None

        downloaded_path = Path(downloaded)
        if downloaded_path != thumb_path and downloaded_path.exists():
            # Normalize to predictable thumb file name for stable URLs.
            try:
                downloaded_path.replace(thumb_path)
            except OSError:
                return downloaded_path
        return thumb_path if thumb_path.exists() else downloaded_path

    def _ai_generation_ready(self) -> bool:
        if not AI_TITLE_ENABLED:
            return False
        if AI_TITLE_PROVIDER != "ollama":
            return False
        if not AI_TITLE_OLLAMA_URL:
            return False
        if self._last_ai_failure_at and (time.time() - self._last_ai_failure_at) < AI_TITLE_FAILURE_COOLDOWN_SECONDS:
            return False
        return True

    def _mark_ai_failure(self) -> None:
        self._last_ai_failure_at = time.time()

    def _clear_ai_failure(self) -> None:
        self._last_ai_failure_at = 0.0

    @staticmethod
    def _sanitize_ai_title(value: str) -> str:
        cleaned = " ".join((value or "").replace("\r", " ").replace("\n", " ").split()).strip()
        if not cleaned:
            return ""
        if cleaned.startswith("\"") and cleaned.endswith("\"") and len(cleaned) > 1:
            cleaned = cleaned[1:-1].strip()
        cleaned = cleaned[:100].strip(" .,:;!?-_")
        return cleaned

    @staticmethod
    def _sanitize_ai_vision_text(value: str, max_chars: int = 800) -> str:
        """Looser sanitizer for vision captions (do not truncate to 100 chars)."""
        cleaned = " ".join((value or "").replace("\r", " ").replace("\n", " ").split()).strip()
        if not cleaned:
            return ""
        if cleaned.startswith("\"") and cleaned.endswith("\"") and len(cleaned) > 1:
            cleaned = cleaned[1:-1].strip()
        if max_chars > 0 and len(cleaned) > max_chars:
            cleaned = cleaned[:max_chars].rstrip()
        return cleaned.strip()

    @staticmethod
    def _normalize_title_key(value: str) -> str:
        return " ".join(str(value or "").strip().lower().split())

    def _unique_title_variant(self, base_title: str, message_id: int) -> Optional[str]:
        """Ask the text model for an alternate phrasing when a title collides."""
        if not base_title:
            return None
        if not AI_TITLE_POLISH_ENABLED:
            return None
        if AI_TITLE_PROVIDER != "ollama" or not AI_TITLE_OLLAMA_URL:
            return None
        if AI_TITLE_STYLE != "explicit":
            return None

        prompt = (
            "Create a UNIQUE porn-site style explicit adult gallery title. "
            "Plain text only, 4 to 10 words, no emojis, no hashtags, no quotes. "
            "Make it DIFFERENT wording than the base title while keeping the same meaning. "
            "Always include at least one explicit anatomy word: boobs/tits/pussy/dick/cock. "
            "Do not mention or imply age, teens, students, school terms, ethnicity, race, or nationality. "
            "Do not describe coercion or violence.\n"
            f"Unique seed: {int(message_id)}\n"
            f"Base title: {base_title}\n"
            "Return only the title."
        )

        result = self._ollama_generate_text_with_fallback(
            prompt=prompt,
            timeout_seconds=min(60, max(15, AI_TITLE_TIMEOUT_SECONDS)),
            models=[AI_TITLE_TEXT_MODEL] + list(AI_TITLE_TEXT_FALLBACK_MODELS),
        )
        if not result:
            return None
        candidate, _used_model = result
        candidate = self._clamp_title_words(candidate, min_words=3, max_words=10)
        if not candidate:
            return None
        if self._contains_blocked_title_terms(candidate):
            return None
        if not self._has_explicit_anatomy_signal(candidate):
            return None
        # Ensure we actually changed phrasing.
        if self._normalize_title_key(candidate) == self._normalize_title_key(base_title):
            return None
        return candidate

    def _ensure_unique_ai_title(self, title: str, message_id: int, used_keys: set[str]) -> str:
        if not title:
            return title

        base = self._sanitize_ai_title(title)
        base_key = self._normalize_title_key(base)
        if not base_key:
            return title
        if base_key not in used_keys:
            used_keys.add(base_key)
            return base

        # Title collided: ask the model for a different phrasing (preferred over hard-coded adjective arrays).
        rerolled = self._unique_title_variant(base, message_id=message_id)
        if rerolled:
            reroll_key = self._normalize_title_key(rerolled)
            if reroll_key and reroll_key not in used_keys:
                used_keys.add(reroll_key)
                return self._sanitize_ai_title(rerolled)

        # Last resort: add a stable "scene" marker with message id.
        words = base.split()
        suffix = ["Scene", str(int(message_id))]
        max_words = 10
        if len(words) + len(suffix) > max_words:
            words = words[: max(1, max_words - len(suffix))]
        candidate = self._sanitize_ai_title(" ".join([*words, *suffix]))
        key = self._normalize_title_key(candidate)
        if key and key not in used_keys:
            used_keys.add(key)
            return candidate

        return base

    @staticmethod
    def _has_explicit_signal(value: str) -> bool:
        if not value:
            return False
        lowered = f" {value.lower()} "
        tokens = (
            " nude ",
            " naked ",
            " sex ",
            " fuck ",
            " fucking ",
            " blowjob ",
            " oral ",
            " anal ",
            " pussy ",
            " dick ",
            " cock ",
            " tits ",
            " boobs ",
            " nipples ",
            " penetration ",
            " cum ",
            " orgasm ",
        )
        return any(tok in lowered for tok in tokens)

    @staticmethod
    def _has_explicit_anatomy_signal(value: str) -> bool:
        if not value:
            return False
        lowered = f" {value.lower()} "
        tokens = (
            " pussy ",
            " dick ",
            " cock ",
            " tits ",
            " boobs ",
            " nipples ",
        )
        return any(tok in lowered for tok in tokens)

    @staticmethod
    def _contains_blocked_title_terms(value: str) -> bool:
        if not value:
            return False
        lowered = f" {value.lower()} "

        # Safety guardrails: never allow titles that imply minors, age, or sensitive attributes.
        always_blocked_terms = (
            " teen ",
            " teenage ",
            " schoolgirl ",
            " school girl ",
            " schoolboy ",
            " school boy ",
            " student ",
            " underage ",
            " minor ",
            " child ",
            " kid ",
            " loli ",
            " shota ",
            " barely legal ",
            " young girl ",
            " young boy ",
            " rape ",
            " raped ",
            " raping ",
            " forced ",
            " non-consensual ",
            " nonconsensual ",
            " asian ",
            " european ",
            " latina ",
            " ebony ",
            " caucasian ",
            " japanese ",
            " chinese ",
            " korean ",
            " thai ",
            " vietnamese ",
            " filipina ",
            " russian ",
        )
        if any(term in lowered for term in always_blocked_terms):
            return True

        # Block explicit anatomy words unless user explicitly opts into explicit mode.
        tasteful_only_terms = (
            " pussy ",
            " dick ",
            " cock ",
            " penis ",
            " vagina ",
            " tits ",
            " nipples ",
        )
        if AI_TITLE_STYLE == "tasteful" and any(term in lowered for term in tasteful_only_terms):
            return True

        # Block explicit age mentions (we never guess or label ages).
        if re.search(r"\b(1[0-7]|18|19|20|21)\b", lowered):
            return True

        return False

    @staticmethod
    def _fallback_ai_title(media_kind: str, seed: int = 0) -> str:
        if AI_TITLE_STYLE == "explicit":
            # Keep fallback titles porn-site style (adult-only) so the UI never shows bland placeholders.
            # Avoid the word "tease" (users reported it gets overused and feels generic).
            safe_seed = int(seed or 0)
            video_templates = (
                "Dirty nude fucking with hard cock and pussy",
                "Hot naked cock pumping wet pussy",
                "Horny nude sex with cock and pussy",
                "Hard cock pounding wet pussy",
                "Naked fucking: cock and wet pussy",
                "Raw nude sex: hard cock, wet pussy",
                "Sloppy nude fucking with cock and pussy",
                "Hot nude sex with tits and hard cock",
            )
            image_templates = (
                "Nude tits and wet pussy close-up",
                "Hot naked body, tits out, wet pussy",
                "Horny nude babe showing tits and pussy",
                "Naked tits, juicy pussy, horny pose",
                "Dirty nude boobs and wet pussy shot",
                "Nude body with tits and pussy on display",
                "Wet pussy and tits, horny nude selfie",
                "Hot naked tits and pussy closeup",
            )

            templates = video_templates if media_kind == "video" else image_templates
            idx = abs(safe_seed) % len(templates)
            return templates[idx]
        return "Romantic Adult Video Moment" if media_kind == "video" else "Romantic Adult Moment"

    @staticmethod
    def _is_fallback_ai_title(value: str) -> bool:
        title = (value or "").strip()
        if not title:
            return False
        return title in {
            "Romantic Adult Video Moment",
            "Romantic Adult Moment",
            "Explicit Adult Video Clip",
            "Explicit Adult Moment",
            "Hot nude cock and pussy tease",
            "Hot nude tits and pussy tease",
        }

    @staticmethod
    def _ai_title_needs_generation(entry: Dict[str, Any], mode: str) -> bool:
        """Return True if this entry should be (re)analyzed according to retitle mode."""
        current_title = str(entry.get("ai_title", "")).strip()
        if not current_title:
            return True
        # If a previously-generated title contains blocked terms, always retitle.
        if TelegramGalleryService._contains_blocked_title_terms(current_title):
            return True

        mode_norm = (mode or "missing").strip().lower() or "missing"
        if mode_norm == "missing":
            return False
        if mode_norm == "force":
            return True
        if mode_norm == "fallback":
            if bool(entry.get("ai_title_is_fallback")):
                return True
            return TelegramGalleryService._is_fallback_ai_title(current_title)
        if mode_norm == "style":
            prev_style = str(entry.get("ai_title_style", "")).strip().lower()
            # Treat missing metadata as eligible for re-title when mode=style.
            if not prev_style or prev_style != AI_TITLE_STYLE:
                return True
            # If user wants porn-site style explicit titles, "tease" ends up massively overused and generic.
            # Consider it eligible for re-title so older titles can be refreshed into more dynamic wording.
            if AI_TITLE_STYLE == "explicit" and re.search(r"\bteas(e|ing)\b", current_title.lower()):
                return True
            # In explicit mode, re-title older "romantic/neutral" outputs so porn keywords appear.
            if AI_TITLE_STYLE == "explicit" and not TelegramGalleryService._has_explicit_anatomy_signal(current_title):
                return True
            if bool(entry.get("ai_title_is_fallback")):
                return True
            return TelegramGalleryService._is_fallback_ai_title(current_title)

        return False

    @staticmethod
    def _prepare_ai_image_bytes(image_path: Path) -> Optional[bytes]:
        try:
            original = image_path.read_bytes()
        except OSError:
            return None

        if not original:
            return None
        if Image is None:
            return original

        try:
            with Image.open(io.BytesIO(original)) as image:
                # Normalize to RGB jpeg and downscale large media for faster vision inference.
                image = image.convert("RGB")
                width, height = image.size
                longest_side = max(width, height)
                if longest_side > AI_TITLE_MAX_IMAGE_SIDE:
                    scale = AI_TITLE_MAX_IMAGE_SIDE / float(longest_side)
                    resized = (
                        max(1, int(width * scale)),
                        max(1, int(height * scale)),
                    )
                    image = image.resize(resized, Image.Resampling.LANCZOS)

                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=AI_TITLE_IMAGE_QUALITY, optimize=True)
                optimized = buffer.getvalue()
                if optimized:
                    return optimized
        except Exception:
            return original

        return original

    @staticmethod
    def _clamp_title_words(title: str, min_words: int = 3, max_words: int = 10) -> str:
        words = (title or "").split()
        if not words:
            return ""
        if len(words) > max_words:
            words = words[:max_words]
        if len(words) < min_words:
            return ""
        return " ".join(words).strip()

    @staticmethod
    def _compress_vision_text(value: str, max_chars: int = 360) -> str:
        text = " ".join((value or "").split()).strip()
        if not text:
            return ""
        if max_chars <= 0 or len(text) <= max_chars:
            return text
        head = max(80, int(max_chars * 0.62))
        tail = max(40, max_chars - head - 5)
        return f"{text[:head].rstrip()} ... {text[-tail:].lstrip()}".strip()

    @staticmethod
    def _looks_informative_vision_text(value: str) -> bool:
        text = (value or "").strip()
        if len(text) < 4:
            return False
        return re.search(r"[A-Za-z0-9]", text) is not None

    @staticmethod
    def _looks_like_refusal_text(value: str) -> bool:
        text = (value or "").strip().lower()
        if not text:
            return False
        tokens = (
            "i can't",
            "i cannot",
            "can't help",
            "cannot help",
            "can't assist",
            "cannot assist",
            "unable to",
            "i'm sorry",
            "i am sorry",
            "as an ai",
            "policy",
            "guidelines",
            "cannot comply",
            "can't comply",
        )
        return any(tok in text for tok in tokens)

    @staticmethod
    def _ollama_tags_url() -> str:
        base = AI_TITLE_OLLAMA_URL
        if "/api/" in base:
            base = base.split("/api/", 1)[0]
        return base.rstrip("/") + "/api/tags"

    def _ollama_installed_models(self, max_age_seconds: int = 90) -> set[str]:
        """Return a cached set of Ollama model tags, best-effort."""
        now = time.time()
        if self._ollama_models_cache and (now - self._ollama_models_cached_at) < max_age_seconds:
            return set(self._ollama_models_cache)

        tags_url = self._ollama_tags_url()
        request = urllib.request.Request(tags_url, headers={"Content-Type": "application/json"}, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                body = response.read().decode("utf-8", errors="ignore")
            parsed = json.loads(body)
            models = parsed.get("models") or []
            found: set[str] = set()
            for entry in models:
                name = str(entry.get("name", "")).strip()
                if name:
                    found.add(name)
            if found:
                self._ollama_models_cache = found
            self._ollama_models_cached_at = now
        except Exception:
            # Keep previous cache; update timestamp to avoid hammering when Ollama is down.
            self._ollama_models_cached_at = now
        return set(self._ollama_models_cache)

    def _ollama_generate_text(self, model: str, prompt: str, timeout_seconds: int) -> Optional[str]:
        if not model:
            return None
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                # A bit more variety in explicit mode, while staying readable.
                "temperature": 0.55 if AI_TITLE_STYLE == "explicit" else 0.35,
                "num_predict": 56,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            AI_TITLE_OLLAMA_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="ignore")
            parsed = json.loads(body)
        except Exception:
            return None

        # Ollama returns {"error": "..."} for missing models or other failures.
        if parsed.get("error"):
            return None

        return self._sanitize_ai_title(str(parsed.get("response", "")))

    def _ollama_generate_text_with_fallback(
        self,
        prompt: str,
        timeout_seconds: int,
        models: Optional[List[str]] = None,
    ) -> Optional[Tuple[str, str]]:
        """Try multiple text models in order, returning (text, model_used)."""
        candidates = models or []
        installed = self._ollama_installed_models()
        seen: set[str] = set()
        for model in candidates:
            model_name = str(model or "").strip()
            if not model_name or model_name in seen:
                continue
            seen.add(model_name)
            if installed and model_name not in installed:
                continue
            text = self._ollama_generate_text(model=model_name, prompt=prompt, timeout_seconds=timeout_seconds)
            if text:
                return text, model_name
        return None

    def _ollama_polish_title_with_model(
        self,
        base_title: str,
        media_kind: str,
        caption: str,
        message_id: int,
    ) -> Optional[Tuple[str, str]]:
        if not AI_TITLE_POLISH_ENABLED:
            return None
        if AI_TITLE_STYLE != "explicit":
            return None
        if not base_title:
            return None

        prompt = (
            "Rewrite this into a porn-site style explicit adult gallery title. "
            "Plain text only, 4 to 10 words, no emojis, no hashtags, no quotes. "
            "Keep it aligned with what's visible/implied; if uncertain, stay generic and do not invent niche acts. "
            "Always include at least one explicit anatomy word: boobs/tits/pussy/dick/cock. "
            "For videos, include one action verb when possible: fuck/fucking/ride/riding/suck/sucking/pound/pounding/thrust/thrusting. "
            "Only include very specific act keywords when clearly implied (blowjob/oral/penetration/cum/orgasm). "
            "Avoid the word 'tease/teasing' (it gets overused and sounds generic). "
            "If nudity is implied, include 'nude' or 'naked'; otherwise use 'sexy body' or 'lingerie'. "
            "Avoid bland repeated phrases like 'Adult moment' or 'Preview'. "
            "Add 1-2 spicy adjectives when they fit: hot/dirty/horny/naughty/juicy/throbbing/filthy/kinky/raw/wet/sloppy/creamy/deep/hard. "
            "Make it feel like a real porn-site listing title and keep it catchy. "
            "Do not mention or imply age, teens, students, school terms, ethnicity, race, or nationality. "
            "Do not describe coercion or violence.\n"
            f"Media kind: {media_kind}\n"
            f"Unique seed: {int(message_id)}\n"
            f"Original title: {base_title}\n"
        )
        if caption:
            prompt += f"Caption context: {caption[:220]}\n"
        prompt += "Return only the rewritten title."

        rewrite_result = self._ollama_generate_text_with_fallback(
            prompt=prompt,
            timeout_seconds=min(60, max(15, AI_TITLE_TIMEOUT_SECONDS)),
            models=[AI_TITLE_TEXT_MODEL] + list(AI_TITLE_TEXT_FALLBACK_MODELS),
        )
        if not rewrite_result:
            return None
        rewritten, used_model = rewrite_result
        rewritten = self._clamp_title_words(rewritten, min_words=3, max_words=10)
        if not rewritten:
            return None
        if self._contains_blocked_title_terms(rewritten):
            return None
        if not self._has_explicit_anatomy_signal(rewritten):
            return None
        return rewritten, used_model

    def _ollama_polish_title(self, base_title: str, media_kind: str, caption: str, message_id: int) -> Optional[str]:
        result = self._ollama_polish_title_with_model(
            base_title=base_title,
            media_kind=media_kind,
            caption=caption,
            message_id=message_id,
        )
        if not result:
            return None
        title, _model = result
        return title

    def _ollama_title_from_image_path(
        self,
        image_path: Path,
        media_kind: str,
        caption: str,
        message_id: int,
    ) -> Optional[Tuple[str, str, bool]]:
        if not image_path.exists():
            return None

        image_bytes = self._prepare_ai_image_bytes(image_path)
        if not image_bytes:
            return None

        prompt_suffix = ""
        if media_kind == "video":
            prompt_suffix += " The image is a video preview frame."
        if caption:
            prompt_suffix += f" Context caption: {caption[:220]}"

        if AI_TITLE_STYLE == "explicit":
            # Keep vision prompts direct and avoid long "porn keyword lists" which some models respond to poorly.
            # We apply porn-site title wording via the text polisher model (adult-only; no age/teen/school/ethnicity).
            prompt_candidates = [
                (
                    "Describe the scene in plain words. "
                    "Be direct and specific about what is visible. "
                    "Mention setting, pose, nudity, and any obvious sex act (if visible). "
                    "Avoid guessing personal attributes like age or ethnicity. "
                    "Avoid describing violence or coercion."
                ),
                (
                    "Write one blunt sentence describing what is visible. "
                    "Mention nudity if present and any obvious sexual activity if visible. "
                    "Avoid guessing age or ethnicity. "
                    "Avoid violence or coercion."
                ),
                (
                    "List 3 to 6 short key phrases describing visible elements. "
                    "Avoid age or ethnicity. Avoid violence or coercion."
                ),
            ]
        else:
            prompt_candidates = [
                (
                    "Create one concise gallery title for this adult media preview. "
                    "Output plain text only, 4 to 10 words, no emojis, no hashtags. "
                    "Use romantic, tasteful wording. "
                    "Do not mention ethnicity, race, nationality, age, school terms, or explicit anatomy words."
                )
            ]

        prompts_to_try = [p + prompt_suffix for p in prompt_candidates]

        encoded_image = base64.b64encode(image_bytes).decode("ascii")
        models_to_try = [AI_TITLE_MODEL] + list(AI_TITLE_FALLBACK_MODELS)
        last_error: Optional[Exception] = None

        for model_name in models_to_try:
            if not model_name:
                continue
            for prompt in prompts_to_try:
                payload = {
                    "model": model_name,
                    "prompt": prompt,
                    "images": [encoded_image],
                    "stream": False,
                    "options": {"temperature": 0.22, "num_predict": 84},
                }

                data = json.dumps(payload).encode("utf-8")
                request = urllib.request.Request(
                    AI_TITLE_OLLAMA_URL,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )

                try:
                    with urllib.request.urlopen(request, timeout=AI_TITLE_TIMEOUT_SECONDS) as response:
                        body = response.read().decode("utf-8", errors="ignore")
                    parsed = json.loads(body)
                    if parsed.get("error"):
                        # Model missing / incompatible; try next model.
                        break
                    raw = self._sanitize_ai_vision_text(str(parsed.get("response", "")))
                    if self._looks_like_refusal_text(raw):
                        continue
                    if not self._looks_informative_vision_text(raw):
                        continue

                    if AI_TITLE_STYLE == "explicit" and AI_TITLE_POLISH_ENABLED:
                        title = self._compress_vision_text(raw, max_chars=360)
                    else:
                        title = self._clamp_title_words(raw, min_words=3, max_words=10)

                    if not title:
                        continue

                    self._clear_ai_failure()

                    # If the model emits blocked terms, fall back to a safe explicit title and optionally polish it.
                    if self._contains_blocked_title_terms(title):
                        fallback_title = self._fallback_ai_title(media_kind, seed=message_id)
                        if AI_TITLE_STYLE == "explicit" and AI_TITLE_POLISH_ENABLED:
                            polished_result = self._ollama_polish_title_with_model(
                                fallback_title,
                                media_kind=media_kind,
                                caption=caption,
                                message_id=message_id,
                            )
                            if polished_result:
                                polished, text_model = polished_result
                                return polished, f"{model_name}+{text_model}", True
                        return fallback_title, model_name, True

                    # In explicit mode, always rewrite into a porn-style title so anatomy keywords are present.
                    if AI_TITLE_STYLE == "explicit" and AI_TITLE_POLISH_ENABLED:
                        polished_result = self._ollama_polish_title_with_model(
                            title,
                            media_kind=media_kind,
                            caption=caption,
                            message_id=message_id,
                        )
                        if polished_result:
                            polished, text_model = polished_result
                            return polished, f"{model_name}+{text_model}", False
                        if not self._has_explicit_anatomy_signal(title):
                            fallback_title = self._fallback_ai_title(media_kind, seed=message_id)
                            polished_fallback_result = self._ollama_polish_title_with_model(
                                fallback_title,
                                media_kind=media_kind,
                                caption=caption,
                                message_id=message_id,
                            )
                            if polished_fallback_result:
                                polished_fallback, text_model = polished_fallback_result
                                return polished_fallback, f"{model_name}+{text_model}", True
                            return fallback_title, model_name, True

                    return title, model_name, False
                except Exception as exc:
                    last_error = exc
                    continue

        # Total failure: still return a deterministic safe explicit title so the UI doesn't stay blank.
        if last_error is not None:
            self._mark_ai_failure()
        fallback_title = self._fallback_ai_title(media_kind, seed=message_id)
        if AI_TITLE_STYLE == "explicit" and AI_TITLE_POLISH_ENABLED:
            polished_result = self._ollama_polish_title_with_model(
                fallback_title,
                media_kind=media_kind,
                caption=caption,
                message_id=message_id,
            )
            if polished_result:
                polished, text_model = polished_result
                return polished, f"fallback+{text_model}", True
        return fallback_title, "fallback", True

    def _video_frame_path(self, message_id: int) -> Path:
        return self.cache_dir / f"{message_id}_frame.jpg"

    def _extract_video_frame(self, video_path: Path, message_id: int) -> Optional[Path]:
        if not self.ffmpeg_bin:
            return None
        if not video_path.exists():
            return None

        frame_path = self._video_frame_path(message_id)
        if frame_path.exists():
            return frame_path

        command = [
            self.ffmpeg_bin,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            "00:00:01.000",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "4",
            str(frame_path),
        ]
        try:
            subprocess.run(command, check=False, timeout=25)
        except Exception:
            return None

        if frame_path.exists() and frame_path.stat().st_size > 0:
            return frame_path
        return None

    async def _ensure_image_cached_for_ai(self, item: Dict[str, Any], message: Any) -> Optional[Path]:
        local_path = self.cache_dir / str(item.get("file_name", ""))
        if local_path.exists():
            return local_path

        try:
            downloaded = await asyncio.wait_for(
                self.client.download_media(message, file_name=str(local_path)),
                timeout=DOWNLOAD_TIMEOUT_SECONDS,
            )
        except Exception:
            return None

        if not downloaded:
            return None

        local_path = Path(downloaded)
        item["file_name"] = local_path.name
        item["url"] = f"/media/{local_path.name}"
        item["is_cached"] = True
        try:
            item["size"] = int(local_path.stat().st_size)
        except OSError:
            pass
        return local_path

    def _image_ai_thumb_path(self, message_id: int) -> Path:
        return self.cache_dir / f"{message_id}_image_ai_thumb.jpg"

    async def _ensure_image_thumb_for_ai(self, media_obj: Any, message_id: int) -> Optional[Path]:
        thumb_path = self._image_ai_thumb_path(message_id)
        if thumb_path.exists():
            return thumb_path

        thumb_obj = self._pick_best_thumb(media_obj)
        if not thumb_obj:
            return None

        try:
            downloaded = await asyncio.wait_for(
                self.client.download_media(thumb_obj, file_name=str(thumb_path)),
                timeout=min(25, DOWNLOAD_TIMEOUT_SECONDS),
            )
        except Exception:
            return None

        if not downloaded:
            return None

        downloaded_path = Path(downloaded)
        if downloaded_path != thumb_path and downloaded_path.exists():
            try:
                downloaded_path.replace(thumb_path)
            except OSError:
                return downloaded_path
        return thumb_path if thumb_path.exists() else downloaded_path

    async def _ensure_video_cached_for_ai(self, item: Dict[str, Any], message: Any) -> Optional[Path]:
        local_path = self.cache_dir / str(item.get("file_name", ""))
        if local_path.exists():
            return local_path

        try:
            downloaded = await asyncio.wait_for(
                self.client.download_media(message, file_name=str(local_path)),
                timeout=DOWNLOAD_TIMEOUT_SECONDS,
            )
        except Exception:
            return None

        if not downloaded:
            return None

        local_path = Path(downloaded)
        item["file_name"] = local_path.name
        item["url"] = f"/media/{local_path.name}"
        item["is_cached"] = True
        try:
            item["size"] = int(local_path.stat().st_size)
        except OSError:
            pass
        return local_path

    async def _resolve_ai_source_image(
        self,
        item: Dict[str, Any],
        message: Any,
        media_obj: Any,
    ) -> Optional[Path]:
        message_id = int(item.get("message_id", 0))
        media_kind = str(item.get("media_kind", ""))

        if media_kind == "image":
            local_image = self.cache_dir / str(item.get("file_name", ""))
            if local_image.exists():
                return local_image
            thumb_image = await self._ensure_image_thumb_for_ai(media_obj, message_id)
            if thumb_image and thumb_image.exists():
                return thumb_image
            # Full downloads can be slow; only fall back to caching the full image if we couldn't get a thumb.
            cached_image = await self._ensure_image_cached_for_ai(item, message)
            if cached_image and cached_image.exists():
                return cached_image
            return None

        if media_kind == "video":
            thumb_path = self._thumb_path(message_id)
            if thumb_path.exists():
                return thumb_path

            downloaded_thumb = await self._ensure_video_thumb(message, media_obj, message_id)
            if downloaded_thumb and downloaded_thumb.exists():
                return downloaded_thumb

            local_video = self.cache_dir / str(item.get("file_name", ""))
            if not local_video.exists():
                downloaded_video = await self._ensure_video_cached_for_ai(item, message)
                if downloaded_video:
                    local_video = downloaded_video
            if local_video.exists():
                return await asyncio.to_thread(self._extract_video_frame, local_video, message_id)

        return None

    async def _generate_ai_title_for_item(self, item: Dict[str, Any], mode: str = "missing") -> Optional[str]:
        if not self._ai_generation_ready():
            return None
        if not self._ai_title_needs_generation(item, mode):
            return None

        message_id = int(item.get("message_id", 0))
        if message_id <= 0:
            return None

        try:
            message = await self.client.get_messages(CHAT_ID, message_id)
        except Exception:
            return None

        media_tuple = self._extract_media(message)
        if not media_tuple:
            return None

        media_kind, media_obj, _, _ = media_tuple
        source_image = await self._resolve_ai_source_image(item, message, media_obj)
        if not source_image:
            return None

        caption_text = str(item.get("caption") or message.caption or "").strip()
        result: Optional[Tuple[str, str, bool]]
        if AI_TITLE_PER_ITEM_TIMEOUT_SECONDS > 0:
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._ollama_title_from_image_path,
                        source_image,
                        media_kind,
                        caption_text,
                        message_id,
                    ),
                    timeout=AI_TITLE_PER_ITEM_TIMEOUT_SECONDS,
                )
            except TimeoutError:
                return None
        else:
            result = await asyncio.to_thread(
                self._ollama_title_from_image_path,
                source_image,
                media_kind,
                caption_text,
                message_id,
            )
        if not result:
            return None
        title, used_model, is_fallback = result
        # If we only had a low-res Telegram thumb for an image and it yielded a fallback title,
        # download the full image once and retry for better analysis.
        if (
            media_kind == "image"
            and bool(is_fallback)
            and source_image.name.endswith("_image_ai_thumb.jpg")
        ):
            full_image = await self._ensure_image_cached_for_ai(item, message)
            if full_image and full_image.exists():
                try:
                    retry_result = await asyncio.to_thread(
                        self._ollama_title_from_image_path,
                        full_image,
                        media_kind,
                        caption_text,
                        message_id,
                    )
                except Exception:
                    retry_result = None
                if retry_result:
                    retry_title, retry_model, retry_is_fallback = retry_result
                    if retry_title and not retry_is_fallback:
                        title, used_model, is_fallback = retry_title, retry_model, retry_is_fallback
        if not title:
            return None

        # Metadata for future re-titling decisions.
        item["ai_title_style"] = AI_TITLE_STYLE
        item["ai_title_model"] = used_model
        item["ai_title_generated_at"] = datetime.now(timezone.utc).isoformat()
        item["ai_title_is_fallback"] = bool(is_fallback)
        return title

    async def generate_missing_ai_titles(self, batch_size: int, recent_limit: int, mode: str = "missing") -> int:
        async with self._ai_title_lock:
            if not self._ai_generation_ready():
                return 0
            if not self._started:
                return 0
            if not self.media_index:
                return 0

            batch = max(1, min(int(batch_size), AI_TITLE_BATCH_SIZE_MAX))
            requested_scan = int(recent_limit)
            if requested_scan <= 0:
                scan_limit = len(self.media_index)
            else:
                scan_limit = max(batch, min(requested_scan, len(self.media_index)))

            async with self._lock:
                by_id = {int(x.get("message_id", 0)): x for x in self.media_index}

                # Newest queued items first (real-time priority for new media).
                # Do not drain the queue up-front; only remove items once they get titled.
                queue_budget = min(len(self._ai_queue), max(batch * 4, 12))
                if queue_budget:
                    queued_ids = list(reversed(list(self._ai_queue)[-queue_budget:]))
                else:
                    queued_ids = []

                queued_set = set(queued_ids)
                queued_candidates = [
                    dict(by_id[msg_id])
                    for msg_id in queued_ids
                    if msg_id in by_id and self._ai_title_needs_generation(by_id[msg_id], mode)
                ]

                scan_candidates = [
                    dict(x)
                    for x in self.media_index[:scan_limit]
                    if int(x.get("message_id", 0)) not in queued_set
                    and self._ai_title_needs_generation(x, mode)
                ]

                candidates = queued_candidates + scan_candidates

            if not candidates:
                return 0

                if AI_TITLE_IMAGE_PRIORITY:
                    image_candidates = [x for x in candidates if str(x.get("media_kind", "")) == "image"]
                    non_image_candidates = [x for x in candidates if str(x.get("media_kind", "")) != "image"]

                def _candidate_key(entry: Dict[str, Any]) -> tuple[int, int, int]:
                    # Prioritize: missing title -> fallback title -> other re-titles.
                    # This makes "regen all titles" complete faster and avoids spending cycles polishing already-titled items.
                    title = str(entry.get("ai_title", "") or "").strip()
                    if not title:
                        title_state = 0
                    else:
                        is_fallback = bool(entry.get("ai_title_is_fallback"))
                        title_state = 1 if is_fallback or self._is_fallback_ai_title(title) else 2

                    # No caption + no AI title usually shows raw filename (e.g. ".mp4/.jpg"); prioritize those.
                    caption = str(entry.get("caption", "") or "").strip()
                    has_caption = 1 if caption else 0
                    cached = 0 if bool(entry.get("is_cached")) else 1
                    try:
                        size = int(entry.get("size") or 0)
                    except (TypeError, ValueError):
                        size = 0
                    return (title_state, has_caption, cached, size)

                image_candidates.sort(key=_candidate_key)
                non_image_candidates.sort(key=_candidate_key)
                candidates = image_candidates + non_image_candidates

            async with self._lock:
                used_title_keys = {
                    self._normalize_title_key(str(x.get("ai_title", "")))
                    for x in self.media_index
                    if str(x.get("ai_title", "")).strip()
                }

            generated = 0
            changed = False
            attempts = 0
            max_attempts = max(batch, min(len(candidates), batch * 4))

            for item in candidates:
                if generated >= batch or attempts >= max_attempts:
                    break
                attempts += 1
                try:
                    title = await self._generate_ai_title_for_item(item, mode=mode)
                except Exception:
                    continue
                if not title:
                    continue

                message_id = int(item.get("message_id", 0))
                if message_id <= 0:
                    continue

                async with self._lock:
                    current = next(
                        (x for x in self.media_index if int(x.get("message_id", 0)) == message_id),
                        None,
                    )
                    if not current:
                        continue
                    if not self._ai_title_needs_generation(current, mode):
                        continue

                    # Carry over metadata updates if AI generation downloaded media for analysis.
                    for field in (
                        "file_name",
                        "url",
                        "is_cached",
                        "size",
                        "thumb_url",
                        "ai_title_style",
                        "ai_title_model",
                        "ai_title_generated_at",
                        "ai_title_is_fallback",
                    ):
                        value = item.get(field)
                        if value not in (None, ""):
                            current[field] = value

                    old_key = self._normalize_title_key(str(current.get("ai_title", "")))
                    if old_key:
                        used_title_keys.discard(old_key)

                    title = self._ensure_unique_ai_title(title, message_id=message_id, used_keys=used_title_keys)
                    current["ai_title"] = title
                    generated += 1
                    changed = True
                    if message_id in self._ai_queue_ids:
                        self._ai_queue_ids.discard(message_id)
                        with suppress(ValueError):
                            self._ai_queue.remove(message_id)

            if generated and changed:
                async with self._lock:
                    self._save_index()

            return generated

    @staticmethod
    def _guess_extension(file_name: str, mime_type: str, fallback: str) -> str:
        ext = Path(file_name or "").suffix.lower()
        if ext:
            return ext
        guessed = mimetypes.guess_extension(mime_type or "")
        if guessed:
            return guessed.lower()
        return fallback

    def _extract_media(self, message: Any) -> Optional[Tuple[str, Any, str, str]]:
        if message.video:
            mime_type = message.video.mime_type or "video/mp4"
            ext = self._guess_extension(message.video.file_name or "", mime_type, ".mp4")
            return "video", message.video, mime_type, ext

        if message.photo:
            return "image", message.photo, "image/jpeg", ".jpg"

        if message.document and message.document.mime_type:
            mime_type = message.document.mime_type
            if mime_type.startswith("video/"):
                ext = self._guess_extension(message.document.file_name or "", mime_type, ".mp4")
                return "video", message.document, mime_type, ext
            if mime_type.startswith("image/"):
                ext = self._guess_extension(message.document.file_name or "", mime_type, ".jpg")
                return "image", message.document, mime_type, ext

        return None

    async def sync_group_media(self, limit: Optional[int], force_redownload: bool = False) -> List[Dict[str, Any]]:
        if limit is not None:
            limit = max(1, limit)

        if not self._started:
            try:
                await asyncio.wait_for(self.start(), timeout=SERVICE_START_TIMEOUT_SECONDS)
            except TimeoutError as exc:
                self.last_sync_error = (
                    f"Gallery session start timed out after {SERVICE_START_TIMEOUT_SECONDS}s."
                )
                raise HTTPException(status_code=504, detail=self.last_sync_error) from exc

        async with self._lock:

            items: List[Dict[str, Any]] = []
            skipped_timeouts = 0
            existing_items_by_id = {int(x.get("message_id", 0)): x for x in self.media_index}

            async def collect_history() -> None:
                nonlocal skipped_timeouts
                history_kwargs: Dict[str, int] = {}
                if limit is not None:
                    history_kwargs["limit"] = limit

                async for message in self.client.get_chat_history(CHAT_ID, **history_kwargs):
                    media_tuple = self._extract_media(message)
                    if not media_tuple:
                        continue

                    media_kind, media_obj, mime_type, ext = media_tuple
                    local_name = f"{message.id}_{media_kind}{ext}"
                    local_path = self.cache_dir / local_name

                    if force_redownload and local_path.exists():
                        local_path.unlink(missing_ok=True)

                    is_cached = local_path.exists()
                    if EAGER_DOWNLOAD_MEDIA and not is_cached:
                        try:
                            downloaded_path = await asyncio.wait_for(
                                self.client.download_media(message, file_name=str(local_path)),
                                timeout=DOWNLOAD_TIMEOUT_SECONDS,
                            )
                        except TimeoutError:
                            skipped_timeouts += 1
                            downloaded_path = None
                        if downloaded_path:
                            local_path = Path(downloaded_path)
                            local_name = local_path.name
                            is_cached = True

                    msg_date = message.date
                    if msg_date and msg_date.tzinfo is None:
                        msg_date = msg_date.replace(tzinfo=timezone.utc)

                    item_url = f"/media/{local_name}" if is_cached else f"/api/file/{message.id}"
                    media_size = getattr(media_obj, "file_size", None)
                    if media_size is None:
                        media_size = local_path.stat().st_size if local_path.exists() else 0
                    existing_item = existing_items_by_id.get(int(message.id), {})
                    existing_ai_title = str(existing_item.get("ai_title", "")).strip()
                    if existing_ai_title and self._contains_blocked_title_terms(existing_ai_title):
                        # Never surface unsafe prior titles; re-analyze instead.
                        existing_ai_title = ""

                    thumb_url: Optional[str]
                    if media_kind == "image":
                        thumb_url = item_url
                    else:
                        if EAGER_VIDEO_THUMBS:
                            await self._ensure_video_thumb(message, media_obj, message.id)
                        cached_thumb = self._thumb_url_if_cached(message.id)
                        if cached_thumb:
                            thumb_url = cached_thumb
                        elif self._pick_best_thumb(media_obj):
                            thumb_url = f"/api/thumb/{message.id}"
                        else:
                            thumb_url = "/assets/video-placeholder.svg"

                    item = {
                        "message_id": message.id,
                        "media_kind": media_kind,
                        "file_name": local_name,
                        "url": item_url,
                        "thumb_url": thumb_url,
                        "mime_type": mime_type,
                        "size": int(media_size or 0),
                        "is_cached": is_cached,
                        "width": getattr(media_obj, "width", None),
                        "height": getattr(media_obj, "height", None),
                        "duration": getattr(media_obj, "duration", None),
                        "caption": (message.caption or "").strip(),
                        "ai_title": existing_ai_title,
                        "ai_title_style": str(existing_item.get("ai_title_style", "")).strip(),
                        "ai_title_model": str(existing_item.get("ai_title_model", "")).strip(),
                        "ai_title_generated_at": existing_item.get("ai_title_generated_at"),
                        "ai_title_is_fallback": bool(existing_item.get("ai_title_is_fallback")),
                        "date": (msg_date or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
                    }
                    items.append(item)
                    if limit is not None and not existing_ai_title:
                        # Prefer near real-time titles for recent media (live sync + UI polls).
                        self._enqueue_ai_title(int(message.id))

            try:
                if limit is None:
                    await collect_history()
                else:
                    async with asyncio.timeout(SYNC_TIMEOUT_SECONDS):
                        await collect_history()
            except TimeoutError as exc:
                self.last_sync_error = (
                    f"Sync timed out after {SYNC_TIMEOUT_SECONDS}s. "
                    "Showing cached items."
                )
                if items:
                    items.sort(key=lambda item: item["message_id"], reverse=True)
                    if limit is None:
                        self.media_index = items
                        self.last_sync_limit = len(items)
                        self.last_sync_full = True
                    else:
                        if self.media_index:
                            self.media_index = self._merge_partial_items(items)
                        else:
                            self.media_index = items
                        self.last_sync_limit = max(self.last_sync_limit, int(limit))
                        self.last_sync_full = self.last_sync_full and len(self.media_index) > 0
                    self.last_sync_at = datetime.now(timezone.utc).isoformat()
                self._save_index()
                raise HTTPException(status_code=504, detail=self.last_sync_error) from exc

            except RPCError as exc:
                error_text = str(exc)

                if "BOT_METHOD_INVALID" in error_text:
                    self.last_sync_error = (
                        "Bot session cannot read chat history. Use user session mode. "
                        "Run login_user_session.py and set TELEGRAM_GALLERY_AUTH=user"
                    )
                    self._save_index()
                    raise HTTPException(status_code=424, detail=self.last_sync_error) from exc

                self.last_sync_error = f"Telegram API error: {error_text}"
                self._save_index()
                raise HTTPException(status_code=502, detail=self.last_sync_error) from exc
            except Exception as exc:
                self.last_sync_error = f"Sync failed: {exc}"
                self._save_index()
                raise HTTPException(status_code=500, detail=self.last_sync_error) from exc

            items.sort(key=lambda item: item["message_id"], reverse=True)

            if limit is None:
                self.media_index = items
                self.last_sync_limit = len(items)
                self.last_sync_full = True
            else:
                if self.media_index and len(items) < len(self.media_index):
                    self.media_index = self._merge_partial_items(items)
                else:
                    self.media_index = items
                self.last_sync_limit = max(self.last_sync_limit, int(limit))
                # Partial sync never guarantees full coverage.
                self.last_sync_full = self.last_sync_full and len(self.media_index) > 0
            self.last_sync_at = datetime.now(timezone.utc).isoformat()
            if skipped_timeouts:
                self.last_sync_error = (
                    f"Skipped {skipped_timeouts} media file(s) due download timeout "
                    f"({DOWNLOAD_TIMEOUT_SECONDS}s each)."
                )
            else:
                self.last_sync_error = None
            self._save_index()

            return self.media_index


service = TelegramGalleryService(cache_dir=WEB_DIR / "media_cache")


@asynccontextmanager
async def lifespan(_: FastAPI):
    startup_sync_task: Optional[asyncio.Task] = None
    live_sync_task: Optional[asyncio.Task] = None
    ai_title_task: Optional[asyncio.Task] = None
    connect_task: Optional[asyncio.Task] = None

    async def run_startup_sync() -> None:
        startup_raw = os.getenv("TWA_STARTUP_SYNC_LIMIT", "all").strip().lower()
        if startup_raw in {"off", "disable", "disabled", "false", "0"}:
            return
        try:
            startup_limit = parse_limit_value(startup_raw, default=None)
        except ValueError:
            startup_limit = DEFAULT_SYNC_LIMIT
        try:
            await service.sync_group_media(limit=startup_limit, force_redownload=False)
        except HTTPException:
            pass

    async def run_live_sync() -> None:
        if not LIVE_SYNC_ENABLED:
            return

        # Let startup sync warm cache first, then keep recent messages updated.
        await asyncio.sleep(3)
        while True:
            try:
                await service.sync_group_media(limit=LIVE_SYNC_LIMIT, force_redownload=False)
            except HTTPException:
                pass
            except Exception:
                pass
            await asyncio.sleep(LIVE_SYNC_SECONDS)

    async def run_ai_title_worker() -> None:
        if not AI_TITLE_ENABLED:
            return

        # Wait a bit so cache and live sync can warm first.
        await asyncio.sleep(6)
        while True:
            try:
                # Prefer quick, real-time titling for newly fetched media.
                queue_len = len(service._ai_queue)  # noqa: SLF001 - internal queue for real-time prioritization
                batch = AI_TITLE_BATCH_SIZE
                if queue_len > 0:
                    batch = max(batch, min(12, max(4, queue_len)))
                await service.generate_missing_ai_titles(batch_size=batch, recent_limit=AI_TITLE_RECENT_SCAN_LIMIT, mode=AI_TITLE_RETITLE_MODE)
            except Exception:
                pass
            await asyncio.sleep(AI_TITLE_POLL_SECONDS)

    try:
        async def connect_gallery() -> None:
            try:
                await asyncio.wait_for(service.start(), timeout=SERVICE_START_TIMEOUT_SECONDS)
            except Exception as exc:
                # Don't block app startup; cached index can still render.
                service.last_sync_error = f"Gallery session start unavailable: {exc}"

        # Never block FastAPI startup on Telegram auth. If Telegram start is slow/hung,
        # we still want /api/health and cached index endpoints to respond.
        connect_task = asyncio.create_task(connect_gallery())
        startup_sync_task = asyncio.create_task(run_startup_sync())
        live_sync_task = asyncio.create_task(run_live_sync())
        ai_title_task = asyncio.create_task(run_ai_title_worker())
    except Exception as exc:
        # Keep app booting so UI and health endpoint stay reachable.
        service.last_sync_error = f"Startup sync unavailable: {exc}"
    try:
        yield
    finally:
        if connect_task and not connect_task.done():
            connect_task.cancel()
            with suppress(asyncio.CancelledError):
                await connect_task
        if startup_sync_task and not startup_sync_task.done():
            startup_sync_task.cancel()
            with suppress(asyncio.CancelledError):
                await startup_sync_task
        if live_sync_task and not live_sync_task.done():
            live_sync_task.cancel()
            with suppress(asyncio.CancelledError):
                await live_sync_task
        if ai_title_task and not ai_title_task.done():
            ai_title_task.cancel()
            with suppress(asyncio.CancelledError):
                await ai_title_task
        await service.stop()


app = FastAPI(title="Telegram Mini App Gallery", version="3.2.0", lifespan=lifespan)

app.mount("/media", StaticFiles(directory=str(service.cache_dir)), name="media")
app.mount("/assets", StaticFiles(directory=str(WEB_DIR)), name="assets")


def resolve_webapp_context(
    init_data: Optional[str],
    user_agent: Optional[str],
) -> Dict[str, Any]:
    if not init_data:
        return {
            "is_telegram_webapp": False,
            "verified": False,
            "strict_mode": STRICT_TWA_VERIFY,
            "payload": None,
            "bot_username": BOT_USERNAME,
            "chat_id": CHAT_ID,
            "user_agent": user_agent,
        }

    verified = TelegramMiniAppAuth.verify(init_data, BOT_TOKEN)
    if STRICT_TWA_VERIFY and not verified:
        raise HTTPException(status_code=401, detail="Invalid Telegram WebApp signature")

    payload = TelegramMiniAppAuth.extract_payload(init_data)
    return {
        "is_telegram_webapp": True,
        "verified": verified,
        "strict_mode": STRICT_TWA_VERIFY,
        "payload": payload,
        "bot_username": BOT_USERNAME,
        "chat_id": CHAT_ID,
        "user_agent": user_agent,
    }


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/style.css")
async def style() -> FileResponse:
    return FileResponse(WEB_DIR / "style.css")


@app.get("/script.js")
async def script() -> FileResponse:
    return FileResponse(WEB_DIR / "script.js")


@app.get("/api/webapp/context")
async def api_webapp_context(
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    return resolve_webapp_context(init_data=init_data, user_agent=user_agent)


@app.get("/api/file/{message_id}")
async def api_file(message_id: int) -> FileResponse:
    try:
        if not service._started:
            await asyncio.wait_for(service.start(), timeout=SERVICE_START_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Gallery session start timed out after {SERVICE_START_TIMEOUT_SECONDS}s",
        ) from exc

    item = next((x for x in service.media_index if int(x.get("message_id", 0)) == message_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Media item not found")

    local_path = service.cache_dir / str(item.get("file_name", ""))
    if local_path.exists():
        item["is_cached"] = True
        item["url"] = f"/media/{local_path.name}"
        return FileResponse(local_path)

    async with service._lock:
        # Re-check after lock in case concurrent request already downloaded.
        if local_path.exists():
            item["is_cached"] = True
            item["url"] = f"/media/{local_path.name}"
            return FileResponse(local_path)

        message = await service.client.get_messages(CHAT_ID, message_id)
        media_tuple = service._extract_media(message)
        if not media_tuple:
            raise HTTPException(status_code=404, detail="Message has no downloadable media")

        try:
            downloaded_path = await asyncio.wait_for(
                service.client.download_media(message, file_name=str(local_path)),
                timeout=DOWNLOAD_TIMEOUT_SECONDS,
            )
        except TimeoutError as exc:
            raise HTTPException(
                status_code=504,
                detail=f"Media download timed out after {DOWNLOAD_TIMEOUT_SECONDS}s",
            ) from exc

        if not downloaded_path:
            raise HTTPException(status_code=404, detail="Failed to download media")

        local_path = Path(downloaded_path)
        item["file_name"] = local_path.name
        item["is_cached"] = True
        item["url"] = f"/media/{local_path.name}"
        service._save_index()

    return FileResponse(local_path)


@app.get("/api/thumb/{message_id}")
async def api_thumb(message_id: int) -> FileResponse:
    try:
        if not service._started:
            await asyncio.wait_for(service.start(), timeout=SERVICE_START_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Gallery session start timed out after {SERVICE_START_TIMEOUT_SECONDS}s",
        ) from exc

    item = next((x for x in service.media_index if int(x.get("message_id", 0)) == message_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Media item not found")

    media_kind = str(item.get("media_kind", ""))
    if media_kind != "video":
        # Images can use the original file as thumbnail.
        local_path = service.cache_dir / str(item.get("file_name", ""))
        if local_path.exists():
            return FileResponse(local_path)
        raise HTTPException(status_code=404, detail="Thumbnail not required for this media kind")

    thumb_path = service._thumb_path(message_id)
    if thumb_path.exists():
        item["thumb_url"] = f"/media/{thumb_path.name}"
        return FileResponse(thumb_path)

    async with service._lock:
        if thumb_path.exists():
            item["thumb_url"] = f"/media/{thumb_path.name}"
            return FileResponse(thumb_path)

        message = await service.client.get_messages(CHAT_ID, message_id)
        media_tuple = service._extract_media(message)
        if not media_tuple:
            raise HTTPException(status_code=404, detail="Message has no downloadable media")

        media_kind, media_obj, _, _ = media_tuple
        if media_kind != "video":
            raise HTTPException(status_code=404, detail="Video thumbnail not available")

        downloaded_thumb = await service._ensure_video_thumb(message, media_obj, message_id)
        if not downloaded_thumb or not downloaded_thumb.exists():
            item["thumb_url"] = "/assets/video-placeholder.svg"
            service._save_index()
            return FileResponse(WEB_DIR / "video-placeholder.svg")

        item["thumb_url"] = f"/media/{downloaded_thumb.name}"
        service._save_index()
        return FileResponse(downloaded_thumb)


@app.get("/api/media")
async def api_media(
    limit: str = Query("all"),
    refresh: bool = Query(False),
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)
    try:
        limit_value = parse_limit_value(limit, default=None)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid limit '{limit}': {exc}") from exc

    sync_error: Optional[str] = None
    # Default to serving cached index (fast + avoids Telegram session churn).
    # Callers can request a refresh explicitly.
    needs_sync = refresh or not service.media_index

    if needs_sync:
        try:
            items = await service.sync_group_media(limit=limit_value, force_redownload=False)
        except HTTPException as exc:
            items = service.media_index
            sync_error = str(exc.detail)
    else:
        items = service.media_index

    response_items = apply_limit(items, limit_value)

    # Enqueue AI titles for a small recent slice so initial page load triggers real-time titles,
    # even when the UI is calling /api/media?limit=all.
    if AI_TITLE_ENABLED and response_items:
        enqueue_limit = min(len(response_items), max(120, LIVE_SYNC_LIMIT))
        for entry in response_items[:enqueue_limit]:
            try:
                msg_id = int(entry.get("message_id", 0))
            except (TypeError, ValueError):
                continue
            if msg_id <= 0:
                continue
            if str(entry.get("ai_title", "")).strip():
                continue
            service._enqueue_ai_title(msg_id)

        if not service._ai_title_lock.locked():
            asyncio.create_task(
                service.generate_missing_ai_titles(
                    batch_size=min(6, max(1, AI_TITLE_BATCH_SIZE)),
                    recent_limit=max(enqueue_limit, AI_TITLE_RECENT_SCAN_LIMIT),
                    mode=AI_TITLE_RETITLE_MODE,
                )
            )

    effective_sync_error = sync_error or service.last_sync_error
    if items and not refresh:
        # Avoid noisy warnings for normal reads when cached media is available.
        effective_sync_error = None

    return {
        "items": response_items,
        "total": len(items),
        "stats": compute_gallery_stats(items),
        "ai_titled_count": count_ai_titled_items(items),
        "requested_limit": "all" if limit_value is None else limit_value,
        "latest_message_id": latest_message_id(items),
        "synced_at": service.last_sync_at,
        "chat_id": CHAT_ID,
        "webapp": context,
        "sync_error": effective_sync_error,
        "session_mode": service.session_mode,
    }


@app.get("/api/media/page")
async def api_media_page(
    limit: int = Query(240, ge=1, le=2000),
    before: Optional[int] = Query(None),
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    """Paginated media list for the Mini App.

    This avoids returning a huge JSON payload over tunnels (serveo/localhost.run),
    while still allowing the UI to load the entire gallery by paging.
    """
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)

    if not service.media_index:
        # Warm the cache with a small sync so first page isn't empty.
        with suppress(HTTPException):
            await service.sync_group_media(limit=LIVE_SYNC_LIMIT, force_redownload=False)

    items = service.media_index
    total = len(items)

    before_id = int(before or 0)
    start = 0
    if before_id > 0:
        # Find first item older than the cursor.
        for idx, entry in enumerate(items):
            try:
                msg_id = int(entry.get("message_id", 0))
            except (TypeError, ValueError):
                continue
            if msg_id < before_id:
                start = idx
                break
        else:
            start = total

    page_items = items[start : start + int(limit)]
    next_before: Optional[int] = None
    if page_items:
        try:
            next_before = int(page_items[-1].get("message_id", 0))
        except (TypeError, ValueError):
            next_before = None

    has_more = start + len(page_items) < total

    # Enqueue AI titles for the page so titles fill in while user scrolls.
    if AI_TITLE_ENABLED and page_items:
        for entry in page_items:
            try:
                msg_id = int(entry.get("message_id", 0))
            except (TypeError, ValueError):
                continue
            if msg_id <= 0:
                continue
            if str(entry.get("ai_title", "")).strip():
                continue
            service._enqueue_ai_title(msg_id)

        if not service._ai_title_lock.locked():
            asyncio.create_task(
                service.generate_missing_ai_titles(
                    batch_size=min(6, max(1, AI_TITLE_BATCH_SIZE)),
                    recent_limit=max(int(limit), AI_TITLE_RECENT_SCAN_LIMIT),
                    mode=AI_TITLE_RETITLE_MODE,
                )
            )

    return {
        "items": page_items,
        "total": total,
        "stats": compute_gallery_stats(items),
        "ai_titled_count": count_ai_titled_items(items),
        "requested_limit": int(limit),
        "before": before_id or None,
        "next_before": next_before,
        "has_more": has_more,
        "latest_message_id": latest_message_id(items),
        "synced_at": service.last_sync_at,
        "chat_id": CHAT_ID,
        "webapp": context,
        "sync_error": service.last_sync_error,
        "session_mode": service.session_mode,
    }


@app.get("/api/media/recent")
async def api_media_recent(
    limit: str = Query("120"),
    refresh: bool = Query(False),
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)

    try:
        parsed_limit = parse_limit_value(limit, default=120)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid limit '{limit}': {exc}") from exc

    if parsed_limit is None:
        limit_value = 120
    else:
        limit_value = max(1, min(int(parsed_limit), 500))

    sync_error: Optional[str] = None
    if refresh or not service.media_index:
        try:
            items = await service.sync_group_media(limit=limit_value, force_redownload=False)
        except HTTPException as exc:
            items = service.media_index
            sync_error = str(exc.detail)
    else:
        items = service.media_index

    response_items = apply_limit(items, limit_value)

    if AI_TITLE_ENABLED and response_items:
        for entry in response_items:
            try:
                msg_id = int(entry.get("message_id", 0))
            except (TypeError, ValueError):
                continue
            if msg_id <= 0:
                continue
            if str(entry.get("ai_title", "")).strip():
                continue
            service._enqueue_ai_title(msg_id)

        if not service._ai_title_lock.locked():
            # Kick off a small background run so the UI sees titles appear quickly.
            asyncio.create_task(
                service.generate_missing_ai_titles(
                    batch_size=min(6, max(1, AI_TITLE_BATCH_SIZE)),
                    recent_limit=max(limit_value, AI_TITLE_RECENT_SCAN_LIMIT),
                    mode=AI_TITLE_RETITLE_MODE,
                )
            )

    return {
        "items": response_items,
        "total": len(items),
        "stats": compute_gallery_stats(items),
        "ai_titled_count": count_ai_titled_items(items),
        "requested_limit": limit_value,
        "latest_message_id": latest_message_id(items),
        "synced_at": service.last_sync_at,
        "chat_id": CHAT_ID,
        "webapp": context,
        "sync_error": sync_error,
        "session_mode": service.session_mode,
    }


@app.post("/api/sync")
async def api_sync(
    limit: str = Query("all"),
    force_redownload: bool = Query(False),
    response_limit: str = Query("240"),
    wait_seconds: int = Query(SYNC_API_MAX_WAIT_SECONDS, ge=3, le=600),
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)
    try:
        limit_value = parse_limit_value(limit, default=None)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid limit '{limit}': {exc}") from exc

    try:
        response_limit_value = parse_limit_value(response_limit, default=240)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid response_limit '{response_limit}': {exc}") from exc

    timed_out = False
    sync_started = False
    sync_error: Optional[str] = None
    sync_notice: Optional[str] = None

    async def _do_sync() -> List[Dict[str, Any]]:
        return await service.sync_group_media(limit=limit_value, force_redownload=force_redownload)

    # Avoid hanging the Mini App UI: wait a bit, then continue syncing in background.
    try:
        sync_started = True
        items = await asyncio.wait_for(_do_sync(), timeout=int(wait_seconds))
    except TimeoutError:
        timed_out = True
        items = service.media_index
        sync_notice = f"Sync is running in background (waited {int(wait_seconds)}s)."
        if not service._background_sync_task or service._background_sync_task.done():
            service._background_sync_task = asyncio.create_task(_do_sync())
    except HTTPException as exc:
        items = service.media_index
        sync_error = str(exc.detail)
    except Exception as exc:
        items = service.media_index
        sync_error = str(exc)

    response_items = apply_limit(items, response_limit_value)

    return {
        "items": response_items,
        "total": len(items),
        "stats": compute_gallery_stats(items),
        "ai_titled_count": count_ai_titled_items(items),
        "requested_limit": "all" if limit_value is None else limit_value,
        "response_limit": "all" if response_limit_value is None else response_limit_value,
        "sync_started": sync_started,
        "timed_out": timed_out,
        "wait_seconds": int(wait_seconds),
        "next_before": int(response_items[-1].get("message_id", 0)) if response_items else None,
        "has_more": (len(items) > int(response_limit_value)) if response_limit_value is not None else False,
        "latest_message_id": latest_message_id(items),
        "synced_at": service.last_sync_at,
        "chat_id": CHAT_ID,
        "webapp": context,
        "sync_error": sync_error,
        "sync_notice": sync_notice,
        "session_mode": service.session_mode,
    }


@app.post("/api/ai-titles")
async def api_ai_titles(
    batch_size: int = Query(AI_TITLE_BATCH_SIZE, ge=1, le=AI_TITLE_BATCH_SIZE_MAX),
    recent_limit: int = Query(AI_TITLE_RECENT_SCAN_LIMIT, ge=0, le=50000),
    mode: str = Query(AI_TITLE_RETITLE_MODE),
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)
    mode_norm = (mode or "missing").strip().lower() or "missing"
    if mode_norm not in {"missing", "fallback", "style", "force"}:
        raise HTTPException(status_code=422, detail=f"Invalid mode '{mode}'; use missing,fallback,style,force")
    timed_out = False
    try:
        generated = await asyncio.wait_for(
            service.generate_missing_ai_titles(batch_size=batch_size, recent_limit=recent_limit, mode=mode_norm),
            timeout=AI_TITLE_API_MAX_WAIT_SECONDS,
        )
    except TimeoutError:
        generated = 0
        timed_out = True
        # Keep generation running in background so manual trigger never blocks callers.
        asyncio.create_task(
            service.generate_missing_ai_titles(batch_size=batch_size, recent_limit=recent_limit, mode=mode_norm)
        )
    return {
        "ok": True,
        "generated": generated,
        "timed_out": timed_out,
        "max_wait_seconds": AI_TITLE_API_MAX_WAIT_SECONDS,
        "ai_titled_count": count_ai_titled_items(service.media_index),
        "requested_batch": batch_size,
        "recent_limit": recent_limit,
        "mode": mode_norm,
        "cached_items": len(service.media_index),
        "latest_message_id": latest_message_id(service.media_index),
        "synced_at": service.last_sync_at,
        "webapp": context,
    }


@app.get("/api/health")
async def api_health() -> Dict[str, Any]:
    return {
        "ok": True,
        "started": service._started,
        "cached_items": len(service.media_index),
        "synced_at": service.last_sync_at,
        "strict_twa_verify": STRICT_TWA_VERIFY,
        "session_mode": service.session_mode,
        "last_sync_error": service.last_sync_error,
        "live_sync_enabled": LIVE_SYNC_ENABLED,
        "live_sync_seconds": LIVE_SYNC_SECONDS,
        "live_sync_limit": LIVE_SYNC_LIMIT,
        "ai_titles_enabled": AI_TITLE_ENABLED,
        "ai_title_provider": AI_TITLE_PROVIDER,
        "ai_title_model": AI_TITLE_MODEL,
        "ai_title_fallback_models": AI_TITLE_FALLBACK_MODELS,
        "ai_title_text_model": AI_TITLE_TEXT_MODEL,
        "ai_title_text_fallback_models": AI_TITLE_TEXT_FALLBACK_MODELS,
        "ai_title_style": AI_TITLE_STYLE,
        "ai_title_polish_titles": AI_TITLE_POLISH_ENABLED,
        "ai_title_timeout_seconds": AI_TITLE_TIMEOUT_SECONDS,
        "ai_title_per_item_timeout_seconds": AI_TITLE_PER_ITEM_TIMEOUT_SECONDS,
        "ai_title_batch_size": AI_TITLE_BATCH_SIZE,
        "ai_title_batch_size_max": AI_TITLE_BATCH_SIZE_MAX,
        "ai_title_recent_scan_limit": AI_TITLE_RECENT_SCAN_LIMIT,
        "ai_title_poll_seconds": AI_TITLE_POLL_SECONDS,
        "ai_title_retitle_mode": AI_TITLE_RETITLE_MODE,
        "ai_title_image_priority": AI_TITLE_IMAGE_PRIORITY,
        "ai_title_max_image_side": AI_TITLE_MAX_IMAGE_SIDE,
        "ai_title_image_quality": AI_TITLE_IMAGE_QUALITY,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")

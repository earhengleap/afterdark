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
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import URL
from starlette.responses import RedirectResponse, Response
from pyrogram import Client
from pyrogram.errors import RPCError
try:
    from PIL import Image
except Exception:
    Image = None


class CachedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            ext = path.lower().split(".")[-1] if "." in path else ""
            if ext in ("jpg", "jpeg", "png", "gif", "webp", "mp4", "webm", "mov"):
                response.headers["Cache-Control"] = "public, max-age=2592000, immutable"
            elif ext in ("css", "js"):
                # Short cache for CSS/JS so tunnel users get fresh files
                response.headers["Cache-Control"] = "public, max-age=60, must-revalidate"
            else:
                response.headers["Cache-Control"] = "public, max-age=3600"
        return response

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
DEFAULT_SYNC_LIMIT = None  # Sync ALL media by default
STRICT_TWA_VERIFY = os.getenv("TWA_VERIFY_STRICT", "0") == "1"
SYNC_TIMEOUT_SECONDS = max(10, int(os.getenv("TWA_SYNC_TIMEOUT_SECONDS", "90")))
DOWNLOAD_TIMEOUT_SECONDS = max(10, int(os.getenv("TWA_DOWNLOAD_TIMEOUT_SECONDS", "180")))
SERVICE_START_TIMEOUT_SECONDS = max(5, int(os.getenv("TWA_SERVICE_START_TIMEOUT_SECONDS", "20")))
try:
    SYNC_API_MAX_WAIT_SECONDS = max(3, int(os.getenv("TWA_SYNC_API_MAX_WAIT_SECONDS", "18").strip() or "18"))
except ValueError:
    SYNC_API_MAX_WAIT_SECONDS = 18
EAGER_DOWNLOAD_MEDIA = os.getenv("TWA_EAGER_DOWNLOAD_MEDIA", "0").strip() == "1"
CDN_ONLY_MODE = os.getenv("TWA_CDN_ONLY", "1").strip().lower() in {"1", "true", "yes", "on"}  # Default: ON
CDN_CLEANUP = os.getenv("TWA_CDN_CLEANUP", "0").strip().lower() in {"1", "true", "yes", "on"}
EAGER_VIDEO_THUMBS = os.getenv("TWA_EAGER_VIDEO_THUMBS", "1").strip().lower() not in {"0", "off", "false", "disabled", "no"}
EAGER_IMAGE_THUMBS = os.getenv("TWA_EAGER_IMAGE_THUMBS", "1").strip().lower() not in {"0", "off", "false", "disabled", "no"}
PARALLEL_THUMB_DOWNLOADS = max(1, min(5, int(os.getenv("TWA_PARALLEL_THUMBS", "3").strip() or "3")))
LIVE_SYNC_ENABLED = os.getenv("TWA_LIVE_SYNC", "1").strip().lower() not in {"0", "off", "false", "disabled", "no"}
try:
    LIVE_SYNC_SECONDS = max(3, int(os.getenv("TWA_LIVE_SYNC_SECONDS", "5").strip() or "5"))
except ValueError:
    LIVE_SYNC_SECONDS = 5
# Live sync - sync all new messages (no limit) 
LIVE_SYNC_LIMIT = None  # Sync ALL new messages
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
    AI_TITLE_TIMEOUT_SECONDS = max(20, int(os.getenv("TWA_AI_TIMEOUT_SECONDS", "120").strip() or "120"))
except ValueError:
    AI_TITLE_TIMEOUT_SECONDS = 120
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
    AI_TITLE_BATCH_SIZE = max(1, min(int(os.getenv("TWA_AI_BATCH_SIZE", "5").strip() or "5"), AI_TITLE_BATCH_SIZE_MAX))
except ValueError:
    AI_TITLE_BATCH_SIZE = 5
try:
    # 0 means scan full cached index (backfill titles for older media).
    _scan_raw = int(os.getenv("TWA_AI_RECENT_SCAN_LIMIT", "0").strip() or "0")
    AI_TITLE_RECENT_SCAN_LIMIT = 0 if _scan_raw <= 0 else _scan_raw
except ValueError:
    AI_TITLE_RECENT_SCAN_LIMIT = 0
try:
    AI_TITLE_POLL_SECONDS = max(5, int(os.getenv("TWA_AI_POLL_SECONDS", "8").strip() or "8"))
except ValueError:
    AI_TITLE_POLL_SECONDS = 8
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

# Suppress verbose Pyrogram rate limit messages
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("pyrogram.session.session").setLevel(logging.WARNING)

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

# In-memory store for async AI chat tasks (tunnel-friendly polling)
# {task_id: {"status": "pending"|"done"|"error", "reply": str, "model": str, "error": str}}
_chat_tasks: Dict[str, Dict[str, Any]] = {}


def latest_message_id(items: List[Dict[str, Any]]) -> int:
    if not items:
        return 0
    try:
        return int(items[0].get("message_id", 0))
    except (TypeError, ValueError, AttributeError):
        return 0


DEFAULT_MEDIA_TITLE_RE = re.compile(r"^(video|image|media)(?:\s*(?:#\s*)?\d+)?$", flags=re.IGNORECASE)


def is_default_media_title(value: str) -> bool:
    title = " ".join(str(value or "").strip().split())
    if not title:
        return False
    return bool(DEFAULT_MEDIA_TITLE_RE.fullmatch(title))


def count_ai_titled_items(items: List[Dict[str, Any]]) -> int:
    return sum(
        1
        for item in items
        if (
            str(item.get("ai_title", "")).strip()
            and not is_default_media_title(str(item.get("ai_title", "")))
        )
    )

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
        self._thumb_locks: Dict[int, asyncio.Lock] = {}
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

            # Register realtime message handler for instant media detection
            try:
                self._register_realtime_handler()
                logger.info("[REALTIME] Message handler registered successfully")
            except Exception as e:
                logger.warning(f"[REALTIME] Could not register handler (non-fatal): {e}")

    async def stop(self) -> None:
        if self._started:
            await self.client.stop()
            self._started = False
        if self._session_clone_name and SESSION_CLONE_CLEANUP:
            self._cleanup_session_artifacts(self._session_clone_name)
            self._session_clone_name = None

    def _register_realtime_handler(self) -> None:
        """Register a Pyrogram handler that fires instantly when new media arrives in the source group."""
        from pyrogram import filters
        from pyrogram.handlers import MessageHandler

        async def _on_new_media(client: Any, message: Any) -> None:
            """Called instantly when a new message with media is posted in the source group."""
            try:
                media_tuple = self._extract_media(message)
                if not media_tuple:
                    return

                media_kind, media_obj, mime_type, ext = media_tuple
                message_id = message.id

                # Skip if already in index
                existing_ids = {int(x.get("message_id", 0)) for x in self.media_index}
                if message_id in existing_ids:
                    return

                local_name = f"{message_id}_{media_kind}{ext}"

                msg_date = message.date
                if msg_date and msg_date.tzinfo is None:
                    msg_date = msg_date.replace(tzinfo=timezone.utc)

                # Get CDN URL if available
                cdn_url: Optional[str] = None
                if CDN_ONLY_MODE:
                    try:
                        cdn_url = await self._get_telegram_cdn_url(message, media_kind)
                    except Exception:
                        pass

                # Build URL
                if cdn_url:
                    item_url = cdn_url
                else:
                    item_url = f"/api/file/{message_id}"

                # Build thumb URL
                if media_kind == "image":
                    thumb_url = cdn_url or item_url
                else:
                    thumb_obj = self._pick_best_thumb(media_obj)
                    if thumb_obj:
                        thumb_url = f"/api/thumb/{message_id}"
                    else:
                        thumb_url = "/assets/video-placeholder.svg"

                media_size = getattr(media_obj, "file_size", None) or 0

                new_item: Dict[str, Any] = {
                    "message_id": message_id,
                    "media_kind": media_kind,
                    "mime_type": mime_type or "",
                    "file_name": local_name,
                    "url": item_url,
                    "cdn_url": cdn_url or "",
                    "thumb_url": thumb_url,
                    "size": media_size,
                    "date": msg_date.isoformat() if msg_date else "",
                    "caption": str(message.caption or ""),
                    "is_cached": False,
                    "ai_title": "",
                    "ai_description": "",
                    "duration": getattr(media_obj, "duration", None) or 0,
                    "width": getattr(media_obj, "width", None) or 0,
                    "height": getattr(media_obj, "height", None) or 0,
                }

                # Add to index (newest first)
                self.media_index.insert(0, new_item)
                logger.info(f"[REALTIME] New {media_kind} detected: message_id={message_id}")

                # Queue AI title generation
                self._enqueue_ai_title(message_id)

                # Try to get thumbnail in background
                try:
                    if media_kind == "video":
                        thumb = await self._ensure_video_thumb(message, media_obj, message_id)
                        if thumb and thumb.exists():
                            new_item["thumb_url"] = f"/media/{thumb.name}"
                    elif media_kind == "image":
                        thumb = await self._ensure_image_thumb(message, media_obj, message_id)
                        if thumb and thumb.exists():
                            new_item["thumb_url"] = f"/media/{thumb.name}"
                except Exception as e:
                    logger.debug(f"[REALTIME] Thumb error for {message_id}: {e}")

                # Persist index to disk so it survives restarts
                self._save_index()

            except Exception as e:
                logger.warning(f"[REALTIME] Error processing new message: {e}")

        # Filter: only messages in the source group that contain media
        media_filter = (
            filters.chat(int(CHAT_ID))
            & (filters.photo | filters.video | filters.document | filters.animation)
        )

        self.client.add_handler(MessageHandler(_on_new_media, media_filter))

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
                        else (
                            f"/media/{self._image_thumb_file_name(message_id)}"
                            if (media_kind == "image" and self._image_thumb_path(message_id).exists())
                            else (f"/media/{local_path.name}" if media_kind == "image" else f"/assets/video-placeholder.svg")
                        )
                    ),
                    "mime_type": mime_type,
                    "size": int(stat.st_size),
                    "is_cached": True,
                    "width": None,
                    "height": None,
                    "duration": None,
                    "caption": "",
                    "ai_title": "",
                    "ai_description": "",
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

    async def fetch_cdn_urls_for_all(self) -> None:
        """Fetch CDN URLs for all existing items that don't have them (for CDN mode)."""
        if not CDN_ONLY_MODE:
            return
            
        items_needing_urls = []
        for item in self.media_index:
            msg_id = int(item.get("message_id", 0))
            url = item.get("url", "")
            cdn_url = item.get("cdn_url", "")
            
            # Skip if already has CDN URL
            if cdn_url and cdn_url.startswith("https://"):
                continue
            # Skip if URL is already a direct CDN URL
            if url and url.startswith("https://"):
                continue
                
            items_needing_urls.append(item)
        
        if not items_needing_urls:
            logger.info("[CDN] All items already have CDN URLs")
            return
            
        logger.info(f"[CDN] Fetching CDN URLs for {len(items_needing_urls)} items...")
        
        # Process in batches to avoid rate limits
        batch_size = 50
        for i in range(0, len(items_needing_urls), batch_size):
            batch = items_needing_urls[i:i+batch_size]
            logger.info(f"[CDN] Processing batch {i//batch_size + 1}/{(len(items_needing_urls) + batch_size - 1)//batch_size}")
            
            for item in batch:
                msg_id = int(item.get("message_id", 0))
                media_kind = item.get("media_kind", "")
                
                try:
                    message = await self.client.get_messages(CHAT_ID, msg_id)
                    if message:
                        cdn_url = await self._get_telegram_cdn_url(message, media_kind)
                        if cdn_url:
                            item["cdn_url"] = cdn_url
                            item["url"] = cdn_url
                            logger.debug(f"[CDN] Got URL for {msg_id}")
                except Exception as e:
                    logger.warning(f"[CDN] Failed to get CDN for {msg_id}: {e}")
                
                # Rate limit
                await asyncio.sleep(0.1)
            
            # Save progress
            self._save_index()
            # Rate limit between batches
            await asyncio.sleep(1)
        
        logger.info(f"[CDN] Completed fetching CDN URLs for {len(items_needing_urls)} items")

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
            description = str(entry.get("ai_description", "")).strip()
            if not title and not description:
                continue

            # Old placeholders ("Video #123") should never be treated as final AI output.
            if title and is_default_media_title(title):
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
                # Continue to blocked-term checks for description.
                title = ""

            blocked = False
            if title and self._contains_blocked_title_terms(title):
                blocked = True
            if description and self._contains_blocked_title_terms(description):
                blocked = True

            if not blocked:
                continue

            # Remove unsafe AI fields and re-enqueue for re-analysis.
            entry["ai_title"] = ""
            entry["ai_description"] = ""
            entry["ai_title_style"] = ""
            entry["ai_title_model"] = ""
            entry["ai_title_generated_at"] = None
            entry["ai_title_is_fallback"] = False
            entry["ai_description_model"] = ""
            entry["ai_description_generated_at"] = None
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
                if incoming_title and (
                    self._contains_blocked_title_terms(incoming_title)
                    or is_default_media_title(incoming_title)
                ):
                    merged_item["ai_title"] = ""
                    merged_item["ai_title_style"] = ""
                    merged_item["ai_title_model"] = ""
                    merged_item["ai_title_generated_at"] = None
                    merged_item["ai_title_is_fallback"] = False

                incoming_description = str(merged_item.get("ai_description", "")).strip()
                if incoming_description and self._contains_blocked_title_terms(incoming_description):
                    merged_item["ai_description"] = ""
                    merged_item["ai_description_model"] = ""
                    merged_item["ai_description_generated_at"] = None

                if not str(merged_item.get("ai_title", "")).strip():
                    old_ai_title = str(old_item.get("ai_title", "")).strip()
                    if (
                        old_ai_title
                        and not self._contains_blocked_title_terms(old_ai_title)
                        and not is_default_media_title(old_ai_title)
                    ):
                        merged_item["ai_title"] = old_ai_title

                if not str(merged_item.get("ai_description", "")).strip():
                    old_ai_desc = str(old_item.get("ai_description", "")).strip()
                    if old_ai_desc and not self._contains_blocked_title_terms(old_ai_desc):
                        merged_item["ai_description"] = old_ai_desc
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

    @staticmethod
    def _image_thumb_file_name(message_id: int) -> str:
        return f"{message_id}_image_thumb.jpg"

    def _image_thumb_path(self, message_id: int) -> Path:
        return self.cache_dir / self._image_thumb_file_name(message_id)

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
            try:
                downloaded_path.replace(thumb_path)
            except OSError:
                return downloaded_path
        
        await self._optimize_thumbnail(thumb_path if thumb_path.exists() else downloaded_path)
        return thumb_path if thumb_path.exists() else downloaded_path

    async def _optimize_thumbnail(self, thumb_path: Path) -> None:
        if not thumb_path or not thumb_path.exists():
            return
        if Image is None:
            return
        try:
            with Image.open(thumb_path) as img:
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")
                width, height = img.size
                max_size = 400
                if width > max_size or height > max_size:
                    scale = max_size / max(width, height)
                    new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
                    img = img.resize(new_size, Image.Resampling.LANCZOS)
                output = io.BytesIO()
                img.save(output, format="JPEG", quality=75, optimize=True)
                output.seek(0)
                thumb_path.write_bytes(output.getvalue())
        except Exception:
            pass

    async def _generate_video_thumb_ffmpeg(self, video_path: Path, thumb_path: Path, message_id: int) -> Optional[Path]:
        """Generate video thumbnail using ffmpeg as fallback when no embedded thumb exists."""
        if not video_path.exists():
            logger.warning(f"[THUMB] Video file not found for ffmpeg: {video_path}")
            return None
        
        # Check file is valid (not temp, not empty)
        if video_path.name.endswith(".temp") or video_path.stat().st_size < 1000:
            logger.warning(f"[THUMB] Video file is incomplete/temp: {video_path}")
            return None
        
        if not self.ffmpeg_bin:
            logger.warning(f"[THUMB] ffmpeg not available for video {message_id}")
            return None
        
        try:
            # Try with seeking first
            cmd = [
                self.ffmpeg_bin,
                "-y",
                "-i", str(video_path),
                "-ss", "00:00:01",
                "-vframes", "1",
                "-vf", "scale=400:400:force_original_aspect_ratio=decrease,pad=400:400:(ow-iw)/2:(oh-ih)/2:black",
                "-q:v", "2",
                str(thumb_path),
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), 
                timeout=30
            )
            
            # If first attempt failed, try without seeking
            if process.returncode != 0 or not thumb_path.exists():
                cmd_no_seek = [
                    self.ffmpeg_bin,
                    "-y",
                    "-i", str(video_path),
                    "-vframes", "1",
                    "-vf", "scale=400:400:force_original_aspect_ratio=decrease",
                    "-q:v", "2",
                    str(thumb_path),
                ]
                process2 = await asyncio.create_subprocess_exec(
                    *cmd_no_seek,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(process2.communicate(), timeout=30)
            
            if thumb_path.exists() and thumb_path.stat().st_size > 0:
                logger.info(f"[THUMB] Generated ffmpeg thumb for video {message_id}")
                await self._optimize_thumbnail(thumb_path)
                return thumb_path
            else:
                logger.warning(f"[THUMB] ffmpeg failed for video {message_id}")
                return None
        except asyncio.TimeoutError:
            logger.warning(f"[THUMB] ffmpeg timeout for video {message_id}")
            return None
        except Exception as e:
            logger.warning(f"[THUMB] ffmpeg error for video {message_id}: {e}")
            return None

    def _find_video_file(self, message_id: int) -> Optional[Path]:
        """Find any video file in cache for this message_id (any extension, ignoring temp files)."""
        # Try common video extensions
        extensions = [".mp4", ".mov", ".avi", ".mkv", ".webm"]
        for ext in extensions:
            video_path = self.cache_dir / f"{message_id}_video{ext}"
            if video_path.exists():
                # Make sure it's not a temp file
                if not video_path.name.endswith(".temp") and video_path.stat().st_size > 1000:
                    return video_path
        
        # Also try pattern matching for any file starting with message_id_video (but not temp)
        try:
            for f in self.cache_dir.iterdir():
                if f.is_file() and f.name.startswith(f"{message_id}_video") and not f.name.endswith(".temp"):
                    if f.stat().st_size > 1000:  # Make sure file is complete (at least 1KB)
                        return f
        except Exception:
            pass
        
        return None

    async def _get_video_thumb_with_ffmpeg_fallback(self, message: Any, message_id: int) -> Optional[Path]:
        """Get video thumbnail - tries embedded thumb first, then falls back to ffmpeg."""
        thumb_path = self._thumb_path(message_id)
        if thumb_path.exists():
            return thumb_path
        
        media_tuple = self._extract_media(message)
        if not media_tuple:
            # Try to find cached video file
            cached_video = self._find_video_file(message_id)
            if cached_video:
                return await self._generate_video_thumb_ffmpeg(cached_video, thumb_path, message_id)
            return None
        
        media_kind, media_obj, _, ext = media_tuple
        
        # Try embedded thumbnail first
        thumb_obj = self._pick_best_thumb(media_obj)
        if thumb_obj:
            try:
                downloaded = await asyncio.wait_for(
                    self.client.download_media(thumb_obj, file_name=str(thumb_path)),
                    timeout=min(30, DOWNLOAD_TIMEOUT_SECONDS),
                )
                if downloaded and Path(downloaded).exists():
                    await self._optimize_thumbnail(thumb_path if thumb_path.exists() else Path(downloaded))
                    if thumb_path.exists():
                        return thumb_path
            except Exception as e:
                logger.debug(f"[THUMB] No embedded thumb for video {message_id}: {e}")
        
        # Try to find cached video file first
        cached_video = self._find_video_file(message_id)
        if cached_video:
            result = await self._generate_video_thumb_ffmpeg(cached_video, thumb_path, message_id)
            if result:
                return result
        
        # Download video if not cached
        try:
            video_name = f"{message_id}_video{ext}"
            video_path = self.cache_dir / video_name
            downloaded = await asyncio.wait_for(
                self.client.download_media(message, file_name=str(video_path)),
                timeout=DOWNLOAD_TIMEOUT_SECONDS,
            )
            if downloaded:
                video_path = Path(downloaded)
        except Exception as e:
            logger.warning(f"[THUMB] Failed to download video {message_id}: {e}")
            return None
        
        if video_path.exists():
            return await self._generate_video_thumb_ffmpeg(video_path, thumb_path, message_id)
        
        return None

    def _find_image_file(self, message_id: int) -> Optional[Path]:
        """Find any image file in cache for this message_id (any extension)."""
        extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
        for ext in extensions:
            img_path = self.cache_dir / f"{message_id}_image{ext}"
            if img_path.exists():
                return img_path
        
        # Also try pattern matching for any file starting with message_id_image
        for f in self.cache_dir.iterdir():
            if f.is_file() and f.name.startswith(f"{message_id}_image"):
                return f
        
        return None

    async def _download_thumbs_parallel(self, items: List[Dict[str, Any]], messages_map: Dict[int, Any]) -> None:
        logger.info(f"[THUMB] Starting parallel thumbnail download for {len(items)} items")
        
        # Deduplicate items by message_id to avoid duplicate downloads
        seen_ids: set[int] = set()
        unique_items: List[Dict[str, Any]] = []
        for item in items:
            msg_id = int(item.get("message_id", 0))
            if msg_id and msg_id not in seen_ids:
                seen_ids.add(msg_id)
                unique_items.append(item)
        items = unique_items
        
        async def download_single_thumb(item: Dict[str, Any]) -> bool:
            message_id = int(item.get("message_id", 0))
            media_kind = str(item.get("media_kind", ""))
            
            # Get or create per-item lock to prevent concurrent downloads of same item
            if message_id not in self._thumb_locks:
                self._thumb_locks[message_id] = asyncio.Lock()
            item_lock = self._thumb_locks[message_id]
            
            async with item_lock:
                # Check again after acquiring lock - another task might have just finished
                if media_kind == "video":
                    thumb_path = self._thumb_path(message_id)
                    if thumb_path.exists():
                        return True
                elif media_kind == "image":
                    thumb_path = self._image_thumb_path(message_id)
                    if thumb_path.exists():
                        return True
                
                message = messages_map.get(message_id)
                
                try:
                    if media_kind == "video":
                        # Try to get from message if available
                        if message:
                            downloaded_thumb = await self._get_video_thumb_with_ffmpeg_fallback(message, message_id)
                            if downloaded_thumb and downloaded_thumb.exists():
                                for idx, i in enumerate(self.media_index):
                                    if int(i.get("message_id", 0)) == message_id:
                                        self.media_index[idx]["thumb_url"] = f"/media/{downloaded_thumb.name}"
                                        break
                                return True
                        
                        # Try to find cached video file
                        cached_video = self._find_video_file(message_id)
                        if cached_video:
                            downloaded_thumb = await self._generate_video_thumb_ffmpeg(cached_video, thumb_path, message_id)
                            if downloaded_thumb and downloaded_thumb.exists():
                                for idx, i in enumerate(self.media_index):
                                    if int(i.get("message_id", 0)) == message_id:
                                        self.media_index[idx]["thumb_url"] = f"/media/{downloaded_thumb.name}"
                                        break
                                return True
                        
                        logger.warning(f"[THUMB] Could not generate thumb for video {message_id}")
                        
                    elif media_kind == "image":
                        thumb_path = self._image_thumb_path(message_id)
                        
                        # First try to find cached original image
                        cached_image = self._find_image_file(message_id)
                        if cached_image and cached_image.exists():
                            try:
                                await self._optimize_thumbnail(cached_image)
                                if cached_image.exists():
                                    import shutil
                                    try:
                                        shutil.copy2(cached_image, thumb_path)
                                    except Exception:
                                        pass
                                    if thumb_path.exists():
                                        for idx, i in enumerate(self.media_index):
                                            if int(i.get("message_id", 0)) == message_id:
                                                self.media_index[idx]["thumb_url"] = f"/media/{thumb_path.name}"
                                                break
                                        return True
                            except Exception as e:
                                logger.warning(f"[THUMB] Failed to optimize cached image {message_id}: {e}")
                        
                        # Download from Telegram if not cached
                        if message:
                            media_tuple = self._extract_media(message)
                            if media_tuple:
                                _, media_obj, _, _ = media_tuple
                                try:
                                    await self.client.download_media(media_obj, file_name=str(thumb_path))
                                    await self._optimize_thumbnail(thumb_path)
                                    if thumb_path.exists():
                                        for idx, i in enumerate(self.media_index):
                                            if int(i.get("message_id", 0)) == message_id:
                                                self.media_index[idx]["thumb_url"] = f"/media/{thumb_path.name}"
                                                break
                                        return True
                                except Exception as e:
                                    logger.warning(f"[THUMB] Failed to download image thumb {message_id}: {e}")
                except Exception as e:
                    logger.warning(f"[THUMB] Error processing thumb for {message_id}: {e}")
                return False

        semaphore = asyncio.Semaphore(PARALLEL_THUMB_DOWNLOADS)
        
        async def limited_download(item: Dict[str, Any]) -> None:
            async with semaphore:
                await download_single_thumb(item)
        
        tasks = [limited_download(item) for item in items]
        await asyncio.gather(*tasks, return_exceptions=True)
        self._save_index()
        logger.info(f"[THUMB] Parallel thumbnail download completed")

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
    def _sanitize_ai_description(value: str, max_chars: int = 900) -> str:
        cleaned = " ".join((value or "").replace("\r", " ").replace("\n", " ").split()).strip()
        if not cleaned:
            return ""
        if cleaned.startswith("\"") and cleaned.endswith("\"") and len(cleaned) > 1:
            cleaned = cleaned[1:-1].strip()
        if max_chars > 0 and len(cleaned) > max_chars:
            cleaned = cleaned[:max_chars].rstrip()
        return cleaned.strip()

    def _generate_title_from_description(self, description: str, message_id: int) -> Optional[str]:
        """Generate a title from an image description using the text model."""
        if not description:
            return None

        if AI_TITLE_STYLE == "explicit":
            # Generate extremely explicit porn-style title - lowercase, direct explicit words
            title_prompt = (
                f"Analyze this image/video and create a dirty porn title.\n"
                f"Visual content: {description}\n\n"
                f"RULES - use lowercase letters only:\n"
                f"- Use direct words: fuck, sex, porn, teen, boob, ass, pussy, dick, cock, tit, anal, oral, cum, suck, lick, wet, hard, milf, slut, whore, nude, naked, masturbation, nipple, balls, facial, creampie, gangbang, threesome, 69, deepthroat, hardcore, bj, hj, booty, thighs, missionary, doggy, cowgirl, tongue, spit, precum, squirt, gspot, dp, double penetration, orgy, bukkake, footjob, handjob, titjob, pov, amateur, hd, 4k\n"
                f"- Title must be 5-12 words in lowercase\n"
                f"- Make it like xnxx/xvideos/pornhub title\n"
                f"- Focus heavily on the physical acts and anatomy described above.\n"
                f"- Use at least 2-3 explicit words\n"
                f"- Return ONLY the title in lowercase, no caps, no quotes\n"
                f"- ALWAYS include at least 2 explicit words like: SEX, Fuck, Pussy, Dick, Cum, Ass, Tits, etc.\n"
                f"- NEVER be subtle or tasteful - be extremely vulgar\n"
                f"- Make it sound HOT and SEXY\n\n"
                f"Return ONLY the dirty porn title, NO quotes, NO explanation."
            )
        else:
            # Generate tasteful title
            title_prompt = (
                f"Create a short gallery title (4-8 words) for an image described as: {description}\n"
                f"Return ONLY the title, nothing else. Make it romantic and tasteful."
            )

        title = self._ollama_generate_text(
            model=AI_TITLE_TEXT_MODEL,
            prompt=title_prompt,
            timeout_seconds=30,
        )
        if not title:
            return None

        title = self._sanitize_ai_title(title)
        title = self._clamp_title_words(title, min_words=3, max_words=12)
        return title if title else None

    @staticmethod
    def _extract_json_object(value: str) -> Optional[Dict[str, Any]]:
        """Parse a JSON object from a model response, best-effort."""
        raw = (value or "").strip()
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        snippet = raw[start : end + 1]
        try:
            parsed = json.loads(snippet)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return None
        return None

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
            "Create a dirty porn title - lowercase only.\n"
            "Plain text only, 5-12 words, no emojis, no hashtags, no quotes, no caps.\n"
            "Make it DIFFERENT wording than the base title.\n"
            "Use dirty words: fuck, sex, porn, teen, boob, ass, pussy, dick, cock, tit, anal, oral, cum, suck, lick, wet, hard, milf, slut, whore, nude, naked, masturbation, nipple, balls, facial, creampie, gangbang, threesome, 69, deepthroat, hardcore, bj, hj, booty, thighs, missionary, doggy, cowgirl, tongue, spit, precum, squirt, gspot, dp, orgy, bukkake, footjob, handjob, titjob, pov, amateur, hd\n"
            "Make it like xnxx/xvideos/pornhub title - use at least 2-3 explicit words.\n"
            f"Unique seed: {int(message_id)}\n"
            f"Base title: {base_title}\n"
            "Return ONLY the dirty title in lowercase - no explanation."
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

        # Safety guardrails: never allow titles that imply minors or non-consent
        always_blocked_terms = (
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
        )
        if any(term in lowered for term in always_blocked_terms):
            return True

        # Block explicit anatomy words unless user explicitly opts into explicit mode.
        tasteful_only_terms = (
            " penis ",
            " vagina ",
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
                "dirty nude fucking with hard cock and pussy",
                "hot naked cock pumping wet pussy",
                "horny nude sex with cock and pussy",
                "hard cock pounding wet pussy",
                "naked fucking: cock and wet pussy",
                "raw nude sex: hard cock, wet pussy",
                "sloppy nude fucking with cock and pussy",
                "hot nude sex with tits and hard cock",
            )
            image_templates = (
                "nude tits and wet pussy close-up",
                "hot naked body, tits out, wet pussy",
                "horny nude babe showing tits and pussy",
                "naked tits, juicy pussy, horny pose",
                "dirty nude boobs and wet pussy shot",
                "nude body with tits and pussy on display",
                "wet pussy and tits, horny nude selfie",
                "hot naked tits and pussy closeup",
            )

            templates = video_templates if media_kind == "video" else image_templates
            idx = abs(safe_seed) % len(templates)
            return templates[idx]
        return "hot adult video moment" if media_kind == "video" else "hot adult moment"

    @staticmethod
    def _is_fallback_ai_title(value: str) -> bool:
        title = (value or "").strip().lower()
        if not title:
            return False
        fallback_titles = {
            "hot adult video moment",
            "Hot adult video moment",
            "hot adult moment",
            "Hot adult moment",
            "Explicit adult video clip",
            "explicit adult video clip",
            "Explicit adult moment",
            "explicit adult moment",
            "hot nude cock and pussy tease",
            "Hot nude cock and pussy tease",
            "hot nude tits and pussy tease",
            "Hot nude tits and pussy tease",
        }
        return title in fallback_titles

    @staticmethod
    def _ai_title_needs_generation(entry: Dict[str, Any], mode: str) -> bool:
        """Return True if this entry should be (re)analyzed according to retitle mode."""
        current_title = str(entry.get("ai_title", "")).strip()
        current_description = str(entry.get("ai_description", "")).strip()
        if current_title and is_default_media_title(current_title):
            return True
        if not current_title:
            return True
        if not current_description:
            return True
        # If a previously-generated title contains blocked terms, always retitle.
        if TelegramGalleryService._contains_blocked_title_terms(current_title):
            return True
        if TelegramGalleryService._contains_blocked_title_terms(current_description):
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
            "REWRITE into EXTREME porn-site style title - NO LIMITS. "
            "Plain text only, 5-12 words, no emojis, no hashtags, no quotes. "
            "Focus heavily on the physical acts and anatomy described.\n"
            "Use EXTREME dirty words: fuck, cum, pussy, dick, cock, ass, anal, tit, boob, MILF, teen, wet, hard, oral, suck, lick, balls, cumshot, facial, creampie, gangbang, threesome, 69, deepthroat, hardcore, slut, bj, hj, etc. "
            "For videos, include action verbs: fuck, suck, lick, ride, pound, thrust, cream, etc. "
            "Make it like xvideos/xnxx/pornhub premium titles. "
            "Be extremely vulgar and sexually explicit. "
            "Add spicy adjectives: hot, dirty, horny, naughty, juicy, throbbing, filthy, kinky, raw, wet, sloppy, creamy, deep, hard, busty, etc.\n"
            f"Media kind: {media_kind}\n"
            f"Unique seed: {int(message_id)}\n"
            f"Original title: {base_title}\n"
        )
        if caption:
            prompt += f"Caption context: {caption[:220]}\n"
        prompt += "Return only the dirty rewritten title."

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

    def _ollama_analyze_image_path(
        self,
        image_path: Path,
        media_kind: str,
        caption: str,
        message_id: int,
    ) -> Optional[Tuple[str, str, str]]:
        """Analyze an image (or extracted video frame) and return (title, description, model)."""
        if not image_path.exists():
            logger.debug(f"Image path does not exist: {image_path}")
            return None

        image_bytes = self._prepare_ai_image_bytes(image_path)
        if not image_bytes:
            logger.debug(f"Failed to prepare image bytes for: {image_path}")
            return None

        # User requested analysis driven by the media itself. Captions are accepted but not used by default.
        _ = caption

        prompt_suffix = ""
        if media_kind == "video":
            prompt_suffix = " The image is a preview frame from a video."

        prompt = (
            "Analyze this image and output ONLY valid JSON.\n"
            'Keys: "title", "description".\n'
            'title: 4-10 words, plain text, no emojis, no hashtags, no quotes.\n'
            "description: 1-3 sentences describing what is visible.\n"
            f"Unique seed: {int(message_id)}.\n"
            "Return JSON only."
            f"{prompt_suffix}"
        ).strip()

        encoded_image = base64.b64encode(image_bytes).decode("ascii")
        models_to_try = [AI_TITLE_MODEL] + list(AI_TITLE_FALLBACK_MODELS)

        for model_name in models_to_try:
            if not model_name:
                continue

            try:
                describe_prompt = (
                    "Focus entirely on the people in this image. "
                    "Ignore the background, lighting, and scenery completely. "
                    "Describe their specific physical actions, poses, interactions, and any visible anatomy in 1-2 short sentences."
                )
                if media_kind == "video":
                    describe_prompt = (
                        "Focus entirely on the people in this video frame. "
                        "Ignore the background, lighting, and scenery completely. "
                        "Describe their specific physical actions, poses, interactions, and any visible anatomy in 1-2 short sentences."
                    )

                payload = {
                    "model": model_name,
                    "prompt": describe_prompt,
                    "images": [encoded_image],
                    "stream": False,
                    "options": {"temperature": 0.3, "num_predict": 100},
                }

                data = json.dumps(payload).encode("utf-8")
                request = urllib.request.Request(
                    AI_TITLE_OLLAMA_URL,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )

                with urllib.request.urlopen(request, timeout=AI_TITLE_TIMEOUT_SECONDS) as response:
                    body = response.read().decode("utf-8", errors="ignore")
                parsed = json.loads(body)
                if parsed.get("error"):
                    continue

                description = self._sanitize_ai_vision_text(str(parsed.get("response", "")), max_chars=500)
                if not description or self._looks_like_refusal_text(description):
                    continue

                # Skip if description is too short or looks like a prompt fragment
                if len(description) < 15:
                    continue
                # Skip if description contains non-ASCII Thai/other garbage (likely model hallucination)
                if any(ord(c) > 127 and not c.isascii() for c in description[:50]):
                    continue

                title = self._generate_title_from_description(description, message_id)
                if not title:
                    continue

                # Skip if title looks like a prompt fragment
                if "1-3 sentences" in title.lower() or "describe" in title.lower():
                    continue

                if self._contains_blocked_title_terms(title) or self._contains_blocked_title_terms(description):
                    continue

                return title, description, model_name
            except Exception as e:
                logger.debug(f"Ollama API error: {e}")
                continue

        logger.debug(f"All models failed for message_id={message_id}")
        return None

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
                    "Create one concise gallery title for this image. "
                    "Output plain text only, 4 to 10 words, no emojis, no hashtags. "
                    "Use romantic, tasteful wording."
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
        
        await self._optimize_thumbnail(thumb_path if thumb_path.exists() else downloaded_path)
        return thumb_path if thumb_path.exists() else downloaded_path

    async def _ensure_image_thumb(self, message: Any, media_obj: Any, message_id: int) -> Optional[Path]:
        thumb_path = self._image_thumb_path(message_id)
        if thumb_path.exists():
            return thumb_path
        
        if not media_obj:
            return None
        
        try:
            downloaded = await asyncio.wait_for(
                self.client.download_media(media_obj, file_name=str(thumb_path)),
                timeout=min(30, DOWNLOAD_TIMEOUT_SECONDS),
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
        
        await self._optimize_thumbnail(thumb_path if thumb_path.exists() else downloaded_path)
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
            logger.debug(f"No local image for {message_id}, trying to download thumb...")
            thumb_image = await self._ensure_image_thumb_for_ai(media_obj, message_id)
            if thumb_image and thumb_image.exists():
                return thumb_image
            # Full downloads can be slow; only fall back to caching the full image if we couldn't get a thumb.
            logger.debug(f"No thumb for {message_id}, trying full image download...")
            cached_image = await self._ensure_image_cached_for_ai(item, message)
            if cached_image and cached_image.exists():
                return cached_image
            logger.debug(f"Failed to get any image for {message_id}")
            return None

        if media_kind == "video":
            thumb_path = self._thumb_path(message_id)
            if thumb_path.exists():
                return thumb_path

            logger.debug(f"No video thumb for {message_id}, trying to download...")
            downloaded_thumb = await self._ensure_video_thumb(message, media_obj, message_id)
            if downloaded_thumb and downloaded_thumb.exists():
                return downloaded_thumb

            local_video = self.cache_dir / str(item.get("file_name", ""))
            if not local_video.exists():
                logger.debug(f"No local video for {message_id}, downloading...")
                downloaded_video = await self._ensure_video_cached_for_ai(item, message)
                if downloaded_video:
                    local_video = downloaded_video
            if local_video.exists():
                return await asyncio.to_thread(self._extract_video_frame, local_video, message_id)
            
            logger.debug(f"Failed to get video frame for {message_id}")

        return None

    async def _generate_ai_title_for_item(
        self,
        item: Dict[str, Any],
        mode: str = "missing",
        message: Optional[Any] = None,
        media_tuple: Optional[Tuple[str, Any, str, str]] = None,
    ) -> Optional[str]:
        if not self._ai_generation_ready():
            logger.debug(f"AI generation not ready for {item.get('message_id')}")
            return None
        if not self._ai_title_needs_generation(item, mode):
            logger.debug(f"AI title not needed for {item.get('message_id')}")
            return None

        message_id = int(item.get("message_id", 0))
        if message_id <= 0:
            return None

        if message is None:
            try:
                message = await self.client.get_messages(CHAT_ID, message_id)
            except Exception as e:
                logger.debug(f"Failed to get message {message_id}: {e}")
                return None

        if media_tuple is None:
            media_tuple = self._extract_media(message)
        if not media_tuple:
            logger.debug(f"No media found for {message_id}")
            return None

        media_kind, media_obj, _, _ = media_tuple
        source_image = await self._resolve_ai_source_image(item, message, media_obj)
        if not source_image:
            logger.debug(f"No source image for {message_id} (media_kind={media_kind})")
            return None

        caption_text = str(item.get("caption") or message.caption or "").strip()
        result: Optional[Tuple[str, str, str]]
        if AI_TITLE_PER_ITEM_TIMEOUT_SECONDS > 0:
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        self._ollama_analyze_image_path,
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
                self._ollama_analyze_image_path,
                source_image,
                media_kind,
                caption_text,
                message_id,
            )

        # If we only had a low-res Telegram thumb for an image and analysis failed,
        # download the full image once and retry for better analysis.
        if not result and media_kind == "image" and source_image.name.endswith("_image_ai_thumb.jpg"):
            full_image = await self._ensure_image_cached_for_ai(item, message)
            if full_image and full_image.exists():
                try:
                    result = await asyncio.to_thread(
                        self._ollama_analyze_image_path,
                        full_image,
                        media_kind,
                        caption_text,
                        message_id,
                    )
                except Exception:
                    result = None

        if not result:
            logger.debug(f"No result from AI analysis for {message_id}")
            return None
        title, description, used_model = result
        if not title:
            return None

        # Metadata for future re-titling decisions.
        item["ai_title_style"] = AI_TITLE_STYLE
        item["ai_title_model"] = used_model
        item["ai_title_generated_at"] = datetime.now(timezone.utc).isoformat()
        item["ai_title_is_fallback"] = False
        item["ai_description"] = description
        item["ai_description_model"] = used_model
        item["ai_description_generated_at"] = datetime.now(timezone.utc).isoformat()
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

            def _candidate_key(entry: Dict[str, Any]) -> tuple[int, int, int, int]:
                # Prioritize: missing title -> fallback/default title -> other re-titles.
                title = str(entry.get("ai_title", "") or "").strip()
                if not title:
                    title_state = 0
                else:
                    is_fallback = bool(entry.get("ai_title_is_fallback"))
                    is_default = is_default_media_title(title)
                    title_state = 1 if (is_fallback or is_default or self._is_fallback_ai_title(title)) else 2

                # No caption + no AI title usually shows raw filename (e.g. ".mp4/.jpg"); prioritize those.
                caption = str(entry.get("caption", "") or "").strip()
                has_caption = 1 if caption else 0
                cached = 0 if bool(entry.get("is_cached")) else 1
                try:
                    size = int(entry.get("size") or 0)
                except (TypeError, ValueError):
                    size = 0
                return (title_state, has_caption, cached, size)

            if AI_TITLE_IMAGE_PRIORITY:
                image_candidates = [x for x in candidates if str(x.get("media_kind", "")) == "image"]
                non_image_candidates = [x for x in candidates if str(x.get("media_kind", "")) != "image"]
                image_candidates.sort(key=_candidate_key)
                non_image_candidates.sort(key=_candidate_key)
                candidates = image_candidates + non_image_candidates
            else:
                candidates.sort(key=_candidate_key)

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
                        "ai_description",
                        "ai_description_model",
                        "ai_description_generated_at",
                        "ai_title_style",
                        "ai_title_model",
                        "ai_title_generated_at",
                        "ai_title_is_fallback",
                    ):
                        value = item.get(field)
                        if value not in (None, ""):
                            current[field] = value

                    current["ai_title"] = self._sanitize_ai_title(title)
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

    async def process_all_untitled_media_fully(
        self,
        max_items: Optional[int] = None,
        per_item_timeout: int = 120,
    ) -> Dict[str, Any]:
        """
        Process ALL untitled media items synchronously with infinite retry.
        This will keep retrying until EVERY item has an AI-generated title.
        Also processes items with default titles like "Video #123".
        
        Args:
            max_items: Optional limit on items to process (None = all)
            per_item_timeout: Timeout per item in seconds (default 120s)
            
        Returns:
            Dict with processing status and counts
        """
        if not self._started:
            await self.start()
        
        if not self.media_index:
            return {
                "status": "complete",
                "total": 0,
                "processed": 0,
                "remaining": 0,
            }
        
        # Get all items without AI titles OR with default titles like "Video #123"
        untitled_items = [
            item for item in self.media_index
            if not str(item.get("ai_title", "")).strip() 
            or is_default_media_title(str(item.get("ai_title", "")))
        ]
        
        if max_items:
            untitled_items = untitled_items[:max_items]
        
        total = len(untitled_items)
        processed = 0
        failed = 0
        
        logger.info(f"Starting full AI processing for {total} items (infinite retry)...")
        
        for idx, item in enumerate(untitled_items):
            message_id = int(item.get("message_id", 0))
            logger.info(f"Processing item {idx + 1}/{total}: message_id={message_id}")
            
            # Limited retry loop - give up after 10 attempts per item
            retry_count = 0
            max_retries = 10  # Give up after 10 tries per item
            retry_delay = 2  # Start with 2 seconds
            max_delay = 30   # Cap at 30 seconds
            
            while retry_count < max_retries:
                try:
                    # Check if AI generation is ready
                    if not self._ai_generation_ready():
                        logger.warning(f"AI generation not ready, waiting {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 1.5, max_delay)
                        continue
                    
                    # Try to generate title
                    title = await self._generate_ai_title_for_item(item, mode="missing")
                    
                    if title:
                        # Success! Update the item
                        async with self._lock:
                            # Find and update the item in media_index
                            for idx2, media_item in enumerate(self.media_index):
                                if int(media_item.get("message_id", 0)) == message_id:
                                    # Carry over the generated fields
                                    for field in (
                                        "ai_title", "ai_description", "ai_title_style",
                                        "ai_title_model", "ai_title_generated_at",
                                        "ai_title_is_fallback", "ai_description_model",
                                        "ai_description_generated_at",
                                    ):
                                        if field in item:
                                            media_item[field] = item[field]
                                    break
                            
                            # Save after each success
                            self._save_index()
                        
                        logger.info(f"âœ“ Generated title for message_id={message_id}: {title[:50]}...")
                        processed += 1
                        break  # Success! Move to next item
                    else:
                        # AI returned no title, retry
                        retry_count += 1
                        logger.warning(f"No title generated for {message_id}, retry {retry_count} in {retry_delay}s...")
                        await asyncio.sleep(retry_delay)
                        retry_delay = min(retry_delay * 1.5, max_delay)
                        
                except Exception as e:
                    retry_count += 1
                    logger.warning(f"Error generating title for {message_id}: {e}, retry {retry_count} in {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, max_delay)
            
            if retry_count >= max_retries:
                # Give up on this item after max retries
                logger.warning(f"Giving up on message_id={message_id} after {max_retries} attempts")
                failed += 1
                continue
        
        # Final save
        async with self._lock:
            self._save_index()
        
        remaining = total - processed - failed
        
        logger.info(f"AI processing complete: {processed} processed, {failed} failed, {remaining} remaining")
        
        return {
            "status": "complete" if remaining == 0 else "partial",
            "total": total,
            "processed": processed,
            "failed": failed,
            "remaining": remaining,
        }

    @staticmethod
    def _guess_extension(file_name: str, mime_type: str, fallback: str) -> str:
        ext = Path(file_name or "").suffix.lower()
        if ext:
            return ext
        guessed = mimetypes.guess_extension(mime_type or "")
        if guessed:
            return guessed.lower()
        return fallback

    async def _get_telegram_cdn_url(self, message: Any, media_kind: str) -> Optional[str]:
        """Get Telegram CDN URL for direct media access (no local download needed)."""
        try:
            if media_kind == "video" and message.video:
                file_id = message.video.file_id
            elif media_kind == "image":
                if message.photo:
                    file_id = message.photo[-1].file_id if message.photo else None
                elif message.document:
                    file_id = message.document.file_id
                else:
                    return None
            else:
                return None
            
            if not file_id:
                return None
                
            file_ref = getattr(message, 'file', None)
            if not file_ref:
                return None
                
            # Get file info which includes CDN URL
            try:
                file = await self.client.get_file(file_id)
            except Exception:
                return None
                
            # Check if CDN URL is available
            if hasattr(file, 'cdn_url') and file.cdn_url:
                return file.cdn_url
            elif hasattr(file, 'file_path') and file.file_path:
                # Build URL from file_path as fallback
                return f"https://cdn1.telegram.org/file/{file.file_path}"
                
        except Exception as e:
            logger.debug(f"[CDN] Failed to get CDN URL: {e}")
        return None

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

    async def sync_group_media(self, limit: Optional[int], force_redownload: bool = False, process_ai_realtime: bool = True) -> List[Dict[str, Any]]:
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
            messages_map: Dict[int, Any] = {}
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

                    msg_date = message.date
                    if msg_date and msg_date.tzinfo is None:
                        msg_date = msg_date.replace(tzinfo=timezone.utc)

                    # Get Telegram CDN URL for direct access (no local download needed)
                    cdn_url: Optional[str] = None
                    
                    # Check if existing item has CDN URL
                    existing_for_cdn = existing_items_by_id.get(int(message.id))
                    if existing_for_cdn and existing_for_cdn.get("cdn_url"):
                        cdn_url = existing_for_cdn.get("cdn_url")
                    
                    # If no existing CDN URL and CDN mode enabled, try to get new one
                    if not cdn_url and CDN_ONLY_MODE:
                        try:
                            cdn_url = await self._get_telegram_cdn_url(message, media_kind)
                            if cdn_url:
                                logger.info(f"[CDN] Got CDN URL for message {message.id}")
                        except Exception as e:
                            logger.warning(f"[CDN] Failed to get CDN URL for {message.id}: {e}")

                    # Use CDN URL if available, otherwise use local cache or API
                    if cdn_url:
                        item_url = cdn_url
                    elif is_cached:
                        item_url = f"/media/{local_name}"
                    else:
                        item_url = f"/api/file/{message.id}"

                    media_size = getattr(media_obj, "file_size", None)
                    if media_size is None:
                        media_size = local_path.stat().st_size if local_path.exists() else 0
                    existing_item = existing_items_by_id.get(int(message.id), {})
                    is_new_item = int(message.id) not in existing_items_by_id
                    existing_ai_title = str(existing_item.get("ai_title", "")).strip()
                    if existing_ai_title and is_default_media_title(existing_ai_title):
                        existing_ai_title = ""
                    if existing_ai_title and self._contains_blocked_title_terms(existing_ai_title):
                        existing_ai_title = ""
                    existing_ai_description = str(existing_item.get("ai_description", "")).strip()
                    if existing_ai_description and self._contains_blocked_title_terms(existing_ai_description):
                        existing_ai_description = ""

                    thumb_url: Optional[str]
                    if media_kind == "image":
                        cached_img_thumb = self._image_thumb_path(message.id)
                        if cached_img_thumb.exists():
                            thumb_url = f"/media/{cached_img_thumb.name}"
                        elif cdn_url:
                            thumb_url = cdn_url  # Use CDN for image thumb
                        else:
                            thumb_url = item_url
                    else:
                        cached_thumb = self._thumb_url_if_cached(message.id)
                        if cached_thumb:
                            thumb_url = cached_thumb
                        elif self._pick_best_thumb(media_obj):
                            thumb_url = f"/api/thumb/{message.id}"
                        else:
                            thumb_url = "/assets/video-placeholder.svg"

                    # Immediately generate thumbnail if not exists (for both images and videos)
                    if media_kind == "image":
                        img_thumb_path = self._image_thumb_path(message.id)
                        if not img_thumb_path.exists() and local_path.exists():
                            try:
                                import shutil
                                shutil.copy2(local_path, img_thumb_path)
                                await self._optimize_thumbnail(img_thumb_path)
                                if img_thumb_path.exists():
                                    thumb_url = f"/media/{img_thumb_path.name}"
                            except Exception as e:
                                logger.warning(f"[THUMB] Failed to create image thumb for {message.id}: {e}")
                                thumb_url = item_url  # Fallback to full image
                    elif media_kind == "video":
                        video_thumb_path = self._thumb_path(message.id)
                        if not video_thumb_path.exists():
                            # Try to generate from cached video
                            cached_video = self._find_video_file(message.id)
                            if cached_video:
                                try:
                                    await self._generate_video_thumb_ffmpeg(cached_video, video_thumb_path, message.id)
                                    if video_thumb_path.exists():
                                        thumb_url = f"/media/{video_thumb_path.name}"
                                except Exception as e:
                                    logger.warning(f"[THUMB] Failed to create video thumb for {message.id}: {e}")
                                    thumb_url = "/assets/video-placeholder.svg"

                    item = {
                        "message_id": message.id,
                        "media_kind": media_kind,
                        "file_name": local_name,
                        "url": item_url,
                        "cdn_url": cdn_url or "",
                        "thumb_url": thumb_url,
                        "mime_type": mime_type,
                        "size": int(media_size or 0),
                        "is_cached": is_cached,
                        "width": getattr(media_obj, "width", None),
                        "height": getattr(media_obj, "height", None),
                        "duration": getattr(media_obj, "duration", None),
                        "caption": (message.caption or "").strip(),
                        "ai_title": existing_ai_title,
                        "ai_description": existing_ai_description,
                        "ai_title_style": str(existing_item.get("ai_title_style", "")).strip(),
                        "ai_title_model": str(existing_item.get("ai_title_model", "")).strip(),
                        "ai_title_generated_at": existing_item.get("ai_title_generated_at"),
                        "ai_title_is_fallback": bool(existing_item.get("ai_title_is_fallback")),
                        "ai_description_model": str(existing_item.get("ai_description_model", "")).strip(),
                        "ai_description_generated_at": existing_item.get("ai_description_generated_at"),
                        "date": (msg_date or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
                    }
                    messages_map[message.id] = message
                    
                    if process_ai_realtime and self._ai_title_needs_generation(item, mode="missing"):
                        self._enqueue_ai_title(int(message.id))

                    items.append(item)

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
                # Always merge to preserve existing items not in the new batch
                if self.media_index:
                    self.media_index = self._merge_partial_items(items)
                else:
                    self.media_index = items
                self.last_sync_limit = max(self.last_sync_limit, int(limit))
                # Partial sync never guarantees full coverage unless we've done a full sync
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

            # Download thumbnails in parallel in background - process ALL items
            items_needing_thumbs = [
                item for item in self.media_index
                if (item.get("media_kind") == "video" and not self._thumb_path(int(item["message_id"])).exists())
                or (item.get("media_kind") == "image" and not self._image_thumb_path(int(item["message_id"])).exists())
            ]
            if items_needing_thumbs and messages_map:
                # Process up to 200 thumbnails at a time
                asyncio.create_task(self._download_thumbs_parallel(items_needing_thumbs[:200], messages_map))

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
        
        # Cleanup old cache files if CDN mode with cleanup is enabled
        if CDN_ONLY_MODE and CDN_CLEANUP:
            logger.info("[STARTUP] CDN Only Mode - Cleaning up old cache files...")
            try:
                cleaned = 0
                for f in service.cache_dir.iterdir():
                    if f.is_file() and f.suffix.lower() in {'.mp4', '.jpg', '.jpeg', '.png', '.gif'}:
                        try:
                            f.unlink()
                            cleaned += 1
                        except Exception:
                            pass
                logger.info(f"[STARTUP] Cleaned up {cleaned} cached media files")
            except Exception as e:
                logger.warning(f"[STARTUP] Failed to cleanup cache: {e}")
        
        try:
            startup_limit = parse_limit_value(startup_raw, default=None)
        except ValueError:
            startup_limit = DEFAULT_SYNC_LIMIT
        try:
            # First sync all media
            await service.sync_group_media(limit=startup_limit, force_redownload=False, process_ai_realtime=True)
            
            # Then process ALL remaining items without AI titles (including existing ones)
            logger.info("[STARTUP] Processing all existing items without AI titles...")
            await service.process_all_untitled_media_fully(max_items=None, per_item_timeout=120)
            logger.info("[STARTUP] All AI titles processed!")
            
            # In CDN mode, fetch CDN URLs for existing items that don't have them
            if CDN_ONLY_MODE:
                logger.info("[STARTUP] Fetching CDN URLs for existing items...")
                await service.fetch_cdn_urls_for_all()
                logger.info("[STARTUP] CDN URL fetch complete!")
        except HTTPException:
            pass
        except Exception as e:
            logger.error(f"[STARTUP] Error during sync/AI processing: {e}")

    async def run_live_sync() -> None:
        if not LIVE_SYNC_ENABLED:
            return

        # Let startup sync warm cache first, then keep recent messages updated.
        await asyncio.sleep(3)
        while True:
            try:
                # Enable real-time AI title generation for new messages
                await service.sync_group_media(limit=LIVE_SYNC_LIMIT, force_redownload=False, process_ai_realtime=True)
            except HTTPException:
                pass
            except Exception:
                pass
            await asyncio.sleep(LIVE_SYNC_SECONDS)

    async def run_thumbnail_worker() -> None:
        """Background worker to continuously generate thumbnails for all items."""
        await asyncio.sleep(5)  # Wait for startup to complete
        
        while True:
            try:
                if not service._started or not service.media_index:
                    await asyncio.sleep(10)
                    continue
                
                # Find items needing thumbnails
                items_needing_thumbs = []
                for item in service.media_index:
                    msg_id = int(item.get("message_id", 0))
                    media_kind = str(item.get("media_kind", ""))
                    
                    if media_kind == "video":
                        thumb_path = service._thumb_path(msg_id)
                        if not thumb_path.exists():
                            items_needing_thumbs.append(item)
                    elif media_kind == "image":
                        thumb_path = service._image_thumb_path(msg_id)
                        if not thumb_path.exists():
                            items_needing_thumbs.append(item)
                
                if items_needing_thumbs:
                    # Process up to 100 at a time
                    items_to_process = items_needing_thumbs[:100]
                    
                    # Get messages for these items
                    messages_map: Dict[int, Any] = {}
                    for item in items_to_process:
                        msg_id = int(item.get("message_id", 0))
                        if msg_id not in messages_map:
                            try:
                                message = await service.client.get_messages(CHAT_ID, msg_id)
                                messages_map[msg_id] = message
                            except Exception:
                                pass
                    
                    if messages_map:
                        await service._download_thumbs_parallel(items_to_process, messages_map)
                    
                    await asyncio.sleep(2)  # Short sleep between batches
                else:
                    # All thumbnails generated, sleep longer
                    await asyncio.sleep(30)
                    
            except Exception:
                await asyncio.sleep(10)

    async def run_ai_title_worker() -> None:
        if not AI_TITLE_ENABLED:
            return

        # Wait a bit so cache and live sync can warm first.
        await asyncio.sleep(6)
        
        consecutive_empty = 0
        while True:
            try:
                # Prefer quick, real-time titling for newly fetched media.
                queue_len = len(service._ai_queue)  # noqa: SLF001 - internal queue for real-time prioritization
                batch = AI_TITLE_BATCH_SIZE
                
                # Dynamic batch sizing based on queue length
                if queue_len > 0:
                    # Process more items when queue is growing
                    batch = max(batch, min(20, max(4, queue_len)))
                    # If queue is large, process faster
                    if queue_len > 10:
                        batch = min(25, queue_len)
                
                generated = await service.generate_missing_ai_titles(
                    batch_size=batch, 
                    recent_limit=AI_TITLE_RECENT_SCAN_LIMIT, 
                    mode=AI_TITLE_RETITLE_MODE
                )
                
                # Adaptive polling: if we generated titles, keep going fast
                if generated > 0:
                    consecutive_empty = 0
                    # Short sleep if we made progress and queue still has items
                    if len(service._ai_queue) > 0:
                        await asyncio.sleep(2)
                        continue
                else:
                    consecutive_empty += 1
                    
            except Exception:
                pass
            
            # Adaptive sleep: shorter when queue is building up
            queue_len = len(service._ai_queue)
            if queue_len > 20:
                sleep_time = 3  # Very fast when lots queued
            elif queue_len > 5:
                sleep_time = 5  # Fast when some queued
            elif consecutive_empty > 5:
                sleep_time = AI_TITLE_POLL_SECONDS  # Normal when idle
            else:
                sleep_time = 8  # Moderate when active but empty
                
            await asyncio.sleep(sleep_time)

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
        thumbnail_task = asyncio.create_task(run_thumbnail_worker())
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
        if thumbnail_task and not thumbnail_task.done():
            thumbnail_task.cancel()
            with suppress(asyncio.CancelledError):
                await thumbnail_task
        await service.stop()


app = FastAPI(
    title="Telegram Mini App Gallery", 
    version="3.2.0", 
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS: allow all origins (required for serveo tunnel and other cross-origin access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/media", CachedStaticFiles(directory=str(service.cache_dir)), name="media")
app.mount("/assets", CachedStaticFiles(directory=str(WEB_DIR)), name="assets")



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


def cached_file_response(path: Path, media_type: str = "auto") -> FileResponse:
    ext = path.suffix.lower().lstrip(".")
    if media_type == "auto":
        if ext in ("jpg", "jpeg", "png", "gif", "webp"):
            media_type = "image/jpeg"
        elif ext in ("mp4", "webm", "mov"):
            media_type = "video/mp4"
        elif ext == "svg":
            media_type = "image/svg+xml"
    response = FileResponse(path, media_type=media_type)
    if ext in ("jpg", "jpeg", "png", "gif", "webp", "mp4", "webm", "mov"):
        response.headers["Cache-Control"] = "public, max-age=2592000, immutable"
        try:
            mtime = int(path.stat().st_mtime)
            response.headers["ETag"] = f'"{mtime}-{path.name}"'
        except OSError:
            pass
    else:
        response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.get("/")
async def index() -> FileResponse:
    response = FileResponse(WEB_DIR / "public" / "index.html")
    response.headers["Cache-Control"] = "no-cache"
    return response


app.mount("/css", CachedStaticFiles(directory=str(WEB_DIR / "public" / "css")), name="css")
app.mount("/js", CachedStaticFiles(directory=str(WEB_DIR / "public" / "js")), name="js")
app.mount("/assets", CachedStaticFiles(directory=str(WEB_DIR / "public" / "assets")), name="assets")

# We no longer need individual @app.get("/style.css") handles 
# since app.mount handles the entire directories automatically.

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
        return cached_file_response(local_path)

    async with service._lock:
        if local_path.exists():
            item["is_cached"] = True
            item["url"] = f"/media/{local_path.name}"
            return cached_file_response(local_path)

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

    return cached_file_response(local_path)


@app.get("/api/cdn/{message_id}")
async def api_cdn_file(message_id: int) -> Response:
    """Redirect to Telegram CDN for direct media access (no local cache needed)."""
    try:
        if not service._started:
            await asyncio.wait_for(service.start(), timeout=SERVICE_START_TIMEOUT_SECONDS)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Gallery session not ready")

    item = next((x for x in service.media_index if int(x.get("message_id", 0)) == message_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Media item not found")

    # Check if we already have a CDN URL stored
    existing_cdn_url = item.get("cdn_url")
    if existing_cdn_url:
        return RedirectResponse(url=existing_cdn_url, status_code=302)

    # Try to get CDN URL from Telegram
    try:
        message = await service.client.get_messages(CHAT_ID, message_id)
        media_kind = item.get("media_kind", "")
        
        cdn_url = await service._get_telegram_cdn_url(message, media_kind)
        if cdn_url:
            # Cache the CDN URL for future use
            item["cdn_url"] = cdn_url
            service._save_index()
            return RedirectResponse(url=cdn_url, status_code=302)
    except Exception as e:
        logger.warning(f"[CDN] Failed to get CDN URL for {message_id}: {e}")

    raise HTTPException(status_code=404, detail="CDN URL not available")


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
        local_path = service.cache_dir / str(item.get("file_name", ""))
        if local_path.exists():
            return cached_file_response(local_path)
        raise HTTPException(status_code=404, detail="Thumbnail not required for this media kind")

    thumb_path = service._thumb_path(message_id)
    if thumb_path.exists():
        item["thumb_url"] = f"/media/{thumb_path.name}"
        return cached_file_response(thumb_path)

    async with service._lock:
        if thumb_path.exists():
            item["thumb_url"] = f"/media/{thumb_path.name}"
            return cached_file_response(thumb_path)

        message = await service.client.get_messages(CHAT_ID, message_id)
        media_tuple = service._extract_media(message)
        if not media_tuple:
            raise HTTPException(status_code=404, detail="Message has no downloadable media")

        media_kind, media_obj, _, _ = media_tuple
        if media_kind != "video":
            raise HTTPException(status_code=404, detail="Video thumbnail not available")

        downloaded_thumb = await service._get_video_thumb_with_ffmpeg_fallback(message, message_id)
        if not downloaded_thumb or not downloaded_thumb.exists():
            item["thumb_url"] = "/assets/video-placeholder.svg"
            service._save_index()
            return cached_file_response(WEB_DIR / "video-placeholder.svg")

        item["thumb_url"] = f"/media/{downloaded_thumb.name}"
        service._save_index()
        return cached_file_response(downloaded_thumb)


@app.get("/api/thumb/{message_id}/image")
async def api_image_thumb(message_id: int) -> FileResponse:
    item = next((x for x in service.media_index if int(x.get("message_id", 0)) == message_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Media item not found")

    img_thumb_path = service._image_thumb_path(message_id)
    if img_thumb_path.exists():
        return cached_file_response(img_thumb_path)

    if str(item.get("media_kind", "")) == "image":
        local_path = service.cache_dir / str(item.get("file_name", ""))
        if local_path.exists():
            return cached_file_response(local_path)

    raise HTTPException(status_code=404, detail="Image thumbnail not available")


@app.get("/api/media")
async def api_media(
    limit: str = Query("all"),
    offset: int = Query(0, ge=0),
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
    
    # Use cached media index instead of auto-syncing
    # Only sync if explicitly requested with refresh=True
    if refresh:
        try:
            items = await service.sync_group_media(limit=limit_value, force_redownload=False, process_ai_realtime=True)
        except HTTPException as exc:
            items = service.media_index
            sync_error = str(exc.detail)
        except Exception as e:
            items = service.media_index
            sync_error = str(e)
    else:
        items = service.media_index

    # Get total from cached index BEFORE applying offset
    total_items = len(service.media_index)

    # Apply offset before applying limit
    if offset > 0 and offset < len(items):
        items = items[offset:]

    response_items = apply_limit(items, limit_value)

    effective_sync_error = sync_error or service.last_sync_error
    if items and not refresh:
        # Avoid noisy warnings for normal reads when cached media is available.
        effective_sync_error = None

    return {
        "items": response_items,
        "total": total_items,
        "stats": compute_gallery_stats(service.media_index),
        "ai_titled_count": count_ai_titled_items(service.media_index),
        "requested_limit": "all" if limit_value is None else limit_value,
        "latest_message_id": latest_message_id(service.media_index),
        "synced_at": service.last_sync_at,
        "chat_id": CHAT_ID,
        "webapp": context,
        "sync_error": effective_sync_error,
        "session_mode": service.session_mode,
    }


@app.get("/api/media/page")
async def api_media_page(
    limit: int = Query(24, ge=1, le=2000),
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
            if str(entry.get("ai_title", "")).strip() and str(entry.get("ai_description", "")).strip():
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
            if str(entry.get("ai_title", "")).strip() and str(entry.get("ai_description", "")).strip():
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
@app.get("/api/sync")
async def api_sync(
    limit: str = Query("all"),
    force_redownload: bool = Query(False),
    response_limit: str = Query("240"),
    wait_seconds: int = Query(SYNC_API_MAX_WAIT_SECONDS, ge=3, le=600),
    process_ai: bool = Query(True, description="Generate AI titles in real-time during sync"),
    ai_max_items: Optional[int] = Query(None),
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
    ai_processing_result: Optional[Dict[str, Any]] = None

    async def _do_sync() -> List[Dict[str, Any]]:
        return await service.sync_group_media(limit=limit_value, force_redownload=force_redownload, process_ai_realtime=process_ai)

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

    # Keep /api/sync responsive: queue/trigger bounded AI work instead of blocking on full pass.
    if process_ai and AI_TITLE_ENABLED:
        ai_scan_limit = AI_TITLE_RECENT_SCAN_LIMIT or len(service.media_index)
        if ai_max_items is not None and ai_max_items > 0:
            ai_scan_limit = min(ai_scan_limit, int(ai_max_items)) if ai_scan_limit > 0 else int(ai_max_items)
        ai_scan_limit = max(1, ai_scan_limit)
        ai_batch = min(AI_TITLE_BATCH_SIZE_MAX, max(AI_TITLE_BATCH_SIZE, min(ai_scan_limit, 24)))

        ai_processing_result = {
            "status": "queued",
            "batch_size": ai_batch,
            "recent_limit": ai_scan_limit,
        }
        if not service._ai_title_lock.locked():
            asyncio.create_task(
                service.generate_missing_ai_titles(
                    batch_size=ai_batch,
                    recent_limit=ai_scan_limit,
                    mode=AI_TITLE_RETITLE_MODE,
                )
            )

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
        "ai_processing": ai_processing_result,
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
        "stats": compute_gallery_stats(service.media_index),
        "latest_message_id": latest_message_id(service.media_index),
        "synced_at": service.last_sync_at,
        "webapp": context,
    }


@app.post("/api/ai-titles/process")
async def api_ai_titles_process(
    max_items: Optional[int] = Query(None, description="Maximum items to process (default: all)"),
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    """
    Process ALL untitled media with AI - with infinite retry until complete.
    
    This endpoint will:
    1. Find all media items without AI titles
    2. Process each one with RETRY UNTIL SUCCESS
    3. Save after each successful generation
    4. Return when ALL items have titles
    
    Use this to ensure 100% of your media has AI-generated titles.
    """
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)
    
    if not AI_TITLE_ENABLED:
        return {
            "ok": False,
            "error": "AI titles are disabled. Set TWA_AI_TITLES=1 to enable.",
            "status": "disabled",
        }
    
    logger.info(f"Starting full AI title processing (max_items={max_items})...")
    
    try:
        result = await service.process_all_untitled_media_fully(
            max_items=max_items,
            per_item_timeout=120,
        )
        
        return {
            "ok": True,
            "status": result.get("status", "unknown"),
            "total": result.get("total", 0),
            "processed": result.get("processed", 0),
            "failed": result.get("failed", 0),
            "remaining": result.get("remaining", 0),
            "ai_titled_count": count_ai_titled_items(service.media_index),
            "cached_items": len(service.media_index),
            "stats": compute_gallery_stats(service.media_index),
            "latest_message_id": latest_message_id(service.media_index),
            "synced_at": service.last_sync_at,
            "webapp": context,
        }
        
    except Exception as e:
        logger.error(f"AI title processing failed: {e}")
        return {
            "ok": False,
            "error": str(e),
            "status": "error",
            "ai_titled_count": count_ai_titled_items(service.media_index),
        }


@app.post("/api/ai-titles/process-all")
async def api_ai_titles_process_all(
    max_items: int = Query(0, ge=0, description="Max items (0=all)"),
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    """
    Process ALL existing media items without AI titles - with infinite retry.
    
    This works WITHOUT needing to sync first - it processes items already in the index.
    Use this to generate titles for existing "Video #123" items.
    
    Set max_items=0 to process ALL items.
    """
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)
    
    if not AI_TITLE_ENABLED:
        return {
            "ok": False,
            "error": "AI titles are disabled. Set TWA_AI_TITLES=1 to enable.",
            "status": "disabled",
        }
    
    # Get current count of untitled items
    untitled_count = sum(
        1 for item in service.media_index 
        if not str(item.get("ai_title", "")).strip()
    )
    
    # 0 = all items
    max_items_to_use = None if max_items == 0 else max_items
    
    logger.info(f"[PROCESS-ALL] Starting AI title processing for {untitled_count} existing items...")
    
    try:
        result = await service.process_all_untitled_media_fully(
            max_items=max_items_to_use,
            per_item_timeout=120,
        )
        
        return {
            "ok": True,
            "status": result.get("status", "unknown"),
            "total_items_in_index": len(service.media_index),
            "total_untitled_before": untitled_count,
            "processed": result.get("processed", 0),
            "failed": result.get("failed", 0),
            "remaining": result.get("remaining", 0),
            "ai_titled_count": count_ai_titled_items(service.media_index),
            "webapp": context,
        }
        
    except Exception as e:
        logger.error(f"[PROCESS-ALL] AI title processing failed: {e}")
        return {
            "ok": False,
            "error": str(e),
            "status": "error",
            "ai_titled_count": count_ai_titled_items(service.media_index),
        }


@app.post("/api/chat")
async def api_chat(
    request: Request,
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    """Start an AI chat task. Returns task_id immediately — poll /api/chat/result/{id} for result."""
    try:
        resolve_webapp_context(init_data=init_data, user_agent=user_agent)
    except Exception:
        pass

    try:
        body = await request.json()
        user_message = str(body.get("message", "")).strip()
    except Exception:
        return {"ok": False, "error": "Invalid request body"}

    if not user_message:
        return {"ok": False, "error": "Empty message"}

    # Build gallery context safely
    try:
        total_items = len(service.media_index)
        stats = compute_gallery_stats(service.media_index)
        ai_titled = count_ai_titled_items(service.media_index)
        untitled = sum(1 for x in service.media_index if not str(x.get("ai_title", "")).strip())
        recent_media_lines = []
        for item in service.media_index[:50]:
            try:
                title = item.get("ai_title") or item.get("caption") or ""
                desc = item.get("ai_description", "")
                kind = item.get("media_kind", "?")
                mid = item.get("message_id", "?")
                line = f"  #{mid}: [{kind}] \"{title}\""
                if desc:
                    line += f" — {desc[:60]}"
                recent_media_lines.append(line)
            except Exception:
                continue
        recent_text = "\n".join(recent_media_lines) if recent_media_lines else "  No items yet."
    except Exception:
        total_items = 0; stats = {}; ai_titled = 0; untitled = 0; recent_text = ""

    system_prompt = f"""You are the friendly and powerful "Vault Assistant" — the built-in AI for this private Telegram Bot and Web Gallery. 
You are currently chatting directly with the Admin through the Telegram chat interface!

Be extremely welcoming, conversational, and helpful. Always use emojis to make your responses lively and fun.

WHAT THE TELEGRAM BOT CAN DO:
- The user can paste single or multiple X (Twitter) Video/Image URLs natively into the chat, and you will instantly download them in the highest quality.
- The user can enable "Bulk Mode" to queue up dozens of URLs at once, saving time.

WHAT THE COMPANION WEBSITE CAN DO: 
- Browse {total_items} media items in a clean masonry grid.
- Filter by All/Videos/Images, sort by Newest/Oldest/Largest/Smallest.
- Search by AI-generated titles or descriptions.
- Click cards to open the full media viewer.
- The website auto-detects new media downloaded by the Telegram Bot!

GALLERY LIVE STATS: 
{total_items} total items | {stats.get('videos', 0)} videos | {stats.get('images', 0)} images | {stats.get('total_size_mb', 0):.0f} MB
AI Titles: {ai_titled} | Untitled: {untitled} | Last sync: {service.last_sync_at or 'never'}

RECENTLY ADDED 50 ITEMS:
{recent_text}

GUIDELINES: 
- Acknowledge that you are inside the Telegram bot when relevant!
- If asked about stats, use the 'GALLERY LIVE STATS' above. 
- If asked about recent downloads or "what do we have", use the 'RECENTLY ADDED' list above.
- Ensure your responses are formatted nicely for Telegram (bold text with **, code blocks with `). Keep answers to 2-4 sentences max."""

    # Generate a task ID and start background task immediately
    task_id = base64.b64encode(os.urandom(12)).decode().replace("=", "").replace("/", "_").replace("+", "-")
    _chat_tasks[task_id] = {"status": "pending"}

    text_model = AI_TITLE_TEXT_MODEL
    ollama_base = AI_TITLE_OLLAMA_URL.replace("/api/generate", "")

    async def _run_ollama():
        import http.client, urllib.parse
        parsed_url = urllib.parse.urlparse(f"{ollama_base}/api/generate")
        host = parsed_url.hostname or "localhost"
        port = parsed_url.port or 11434
        path = parsed_url.path or "/api/generate"
        models_to_try = [text_model] + list(AI_TITLE_TEXT_FALLBACK_MODELS)

        for model in models_to_try:
            try:
                payload = json.dumps({
                    "model": model,
                    "prompt": user_message,
                    "system": system_prompt,
                    "stream": True,
                    "options": {
                        "temperature": 0.8, 
                        "num_ctx": 2048
                    }
                }).encode("utf-8")

                def _do_stream():
                    import urllib.request, urllib.error
                    req = urllib.request.Request(
                        f"{ollama_base}/api/generate",
                        data=payload,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    tokens = []
                    try:
                        with urllib.request.urlopen(req, timeout=120) as response:
                            for raw_line in response:
                                line = raw_line.decode('utf-8', errors='ignore').strip()
                                if not line:
                                    continue
                                try:
                                    chunk = json.loads(line)
                                    tok = chunk.get("response", "")
                                    if tok:
                                        tokens.append(tok)
                                        # STREAMING FIX: Publish safely
                                        if task_id in _chat_tasks:
                                            _chat_tasks[task_id]["partial_reply"] = "".join(tokens).strip()

                                    if chunk.get("done"):
                                        break
                                except json.JSONDecodeError:
                                    continue
                            return "".join(tokens).strip() or None
                    except Exception as e:
                        logger.error(f"[CHAT] urllib stream error: {e}")
                        return None
                        
                loop = asyncio.get_event_loop()
                reply = await loop.run_in_executor(None, _do_stream)
                if reply:
                    _chat_tasks[task_id] = {"status": "done", "reply": reply, "model": model}
                    return
            except Exception as e:
                logger.warning(f"[CHAT] Model {model} error: {e}")
                continue

        _chat_tasks[task_id] = {"status": "error", "error": f"AI offline — ensure Ollama is running with '{text_model}'."}

    # Fire off background task and return task_id immediately (no waiting!)
    asyncio.ensure_future(_run_ollama())
    return {"ok": True, "task_id": task_id, "status": "pending"}


@app.get("/api/chat/result/{task_id}")
async def api_chat_result(task_id: str) -> JSONResponse:
    """Poll for AI chat result. Returns status: pending | done | error."""
    task = _chat_tasks.get(task_id)
    if not task:
        return JSONResponse({"ok": False, "error": "Task not found or expired"})
    if task["status"] == "pending":
        # STREAMING FIX: Return the partial text being generated so far
        reply_so_far = task.get("partial_reply", "")
        return JSONResponse({"ok": True, "status": "pending", "reply": reply_so_far})
    if task["status"] == "done":
        # Clean up after reading
        _chat_tasks.pop(task_id, None)
        return JSONResponse({"ok": True, "status": task["status"], "reply": task.get("reply", ""), "model": task.get("model", "")})
    if task["status"] == "error":
        _chat_tasks.pop(task_id, None)
        return JSONResponse({"ok": False, "error": task.get("error", "Unknown error")})
    # This line should ideally not be reached if all statuses are handled
    return JSONResponse({"ok": True, "status": "unknown"})


@app.post("/api/ai-titles/fix-defaults")
async def api_fix_default_titles(
    max_items: int = Query(0, ge=0, description="Max items (0=all)"),
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    """
    Fix ALL items with default titles like "Video #123" by generating proper AI titles.
    This specifically targets items that have default/generic titles.
    """
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)
    
    if not AI_TITLE_ENABLED:
        return {
            "ok": False,
            "error": "AI titles are disabled. Set TWA_AI_TITLES=1 to enable.",
            "status": "disabled",
        }
    
    # Find all items with default titles
    default_titled_items = [
        item for item in service.media_index
        if is_default_media_title(str(item.get("ai_title", "")))
    ]
    
    count_before = len(default_titled_items)
    
    if max_items > 0:
        default_titled_items = default_titled_items[:max_items]
    
    logger.info(f"[FIX-DEFAULTS] Processing {len(default_titled_items)} items with default titles...")
    
    # Enqueue all for processing
    for item in default_titled_items:
        msg_id = int(item.get("message_id", 0))
        if msg_id > 0:
            service._enqueue_ai_title(msg_id)
    
    # Process them with force mode
    try:
        result = await service.generate_missing_ai_titles(
            batch_size=min(25, len(default_titled_items)),
            recent_limit=0,
            mode="force",
        )
        
        # Count remaining
        remaining = sum(
            1 for item in service.media_index
            if is_default_media_title(str(item.get("ai_title", "")))
        )
        
        return {
            "ok": True,
            "status": "processed",
            "total_default_titles_before": count_before,
            "processed": len(default_titled_items),
            "remaining_default_titles": remaining,
            "generated_this_run": result,
            "ai_titled_count": count_ai_titled_items(service.media_index),
            "webapp": context,
        }
    except Exception as e:
        logger.error(f"[FIX-DEFAULTS] Failed: {e}")
        return {
            "ok": False,
            "error": str(e),
            "status": "error",
            "total_default_titles_before": count_before,
            "ai_titled_count": count_ai_titled_items(service.media_index),
        }


@app.post("/api/ai-titles/regenerate-all")
async def api_regenerate_all_ai_titles(
    max_items: int = Query(0, ge=0, description="Max items (0=all)"),
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    """
    Force regenerate ALL AI titles with EXPLICIT PORN STYLE.
    This will override all existing titles with new explicit xxx-style titles.
    Use this to regenerate all titles with maximum explicitness.
    """
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)
    
    if not AI_TITLE_ENABLED:
        return {
            "ok": False,
            "error": "AI titles are disabled. Set TWA_AI_TITLES=1 to enable.",
            "status": "disabled",
        }
    
    # Get all items that have any AI title (to regenerate them all)
    all_items = list(service.media_index)
    
    if max_items > 0:
        all_items = all_items[:max_items]
    
    logger.info(f"[REGENERATE-ALL] Regenerating AI titles for {len(all_items)} items with EXPLICIT mode...")
    
    # Clear any existing titles and enqueue for regeneration
    for item in all_items:
        msg_id = int(item.get("message_id", 0))
        if msg_id > 0:
            # Clear existing title to force regeneration
            item["ai_title"] = ""
            item["ai_description"] = ""
            service._enqueue_ai_title(msg_id)
    
    service._save_index()
    
    # Process with force mode to regenerate all
    try:
        result = await service.generate_missing_ai_titles(
            batch_size=min(30, len(all_items)),
            recent_limit=0,
            mode="force",
        )
        
        # Count items with AI titles now
        ai_titled = sum(
            1 for item in service.media_index
            if str(item.get("ai_title", "")).strip() and not is_default_media_title(str(item.get("ai_title", "")))
        )
        
        return {
            "ok": True,
            "status": "regenerated",
            "total_processed": len(all_items),
            "generated": result,
            "ai_titled_count": ai_titled,
            "message": f"Regenerated {result} explicit titles",
            "webapp": context,
        }
    except Exception as e:
        logger.error(f"[REGENERATE-ALL] Failed: {e}")
        return {
            "ok": False,
            "error": str(e),
            "status": "error",
        }


@app.get("/api/media/{message_id}/ai-status")
async def api_media_ai_status(
    message_id: int,
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    """Get AI title/description generation status for a specific media item."""
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)
    
    async with service._lock:
        item = next(
            (x for x in service.media_index if int(x.get("message_id", 0)) == message_id),
            None,
        )
    
    if not item:
        raise HTTPException(status_code=404, detail=f"Media item {message_id} not found")
    
    raw_title = str(item.get("ai_title", "")).strip()
    has_title = bool(raw_title) and not is_default_media_title(raw_title)
    has_description = bool(str(item.get("ai_description", "")).strip())
    is_queued = message_id in service._ai_queue_ids
    
    # If missing AI content and not queued, enqueue it
    if AI_TITLE_ENABLED and not (has_title and has_description) and not is_queued:
        service._enqueue_ai_title(message_id)
        is_queued = True
        # Trigger immediate processing
        if not service._ai_title_lock.locked():
            asyncio.create_task(
                service.generate_missing_ai_titles(
                    batch_size=min(3, AI_TITLE_BATCH_SIZE),
                    recent_limit=50,
                    mode="missing",
                )
            )
    
    return {
        "ok": True,
        "message_id": message_id,
        "has_ai_title": has_title,
        "has_ai_description": has_description,
        "ai_title": "" if is_default_media_title(raw_title) else raw_title,
        "ai_description": item.get("ai_description", ""),
        "ai_title_model": item.get("ai_title_model", ""),
        "ai_description_model": item.get("ai_description_model", ""),
        "ai_title_generated_at": item.get("ai_title_generated_at"),
        "ai_description_generated_at": item.get("ai_description_generated_at"),
        "is_queued": is_queued,
        "queue_position": list(service._ai_queue).index(message_id) if is_queued and message_id in service._ai_queue else None,
        "queue_length": len(service._ai_queue),
        "webapp": context,
    }


@app.post("/api/thumbnails/fix-all")
async def api_fix_all_thumbnails(
    limit: int = Query(100, ge=1, le=500, description="Max thumbnails to fix"),
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    """Fix thumbnails for all items in media index - regenerate missing/broken thumbnails."""
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)
    
    if not service._started:
        try:
            await asyncio.wait_for(service.start(), timeout=SERVICE_START_TIMEOUT_SECONDS)
        except TimeoutError:
            return {"ok": False, "error": "Service not ready", "webapp": context}
    
    fixed = 0
    failed = 0
    items_checked = []
    
    # Find items with missing or broken thumbnails
    for item in service.media_index[:limit]:
        msg_id = int(item.get("message_id", 0))
        media_kind = str(item.get("media_kind", ""))
        
        if media_kind == "video":
            thumb_path = service._thumb_path(msg_id)
            if not thumb_path.exists():
                # Try to find cached video and generate thumb
                cached_video = service._find_video_file(msg_id)
                if cached_video:
                    try:
                        await service._generate_video_thumb_ffmpeg(cached_video, thumb_path, msg_id)
                        if thumb_path.exists():
                            item["thumb_url"] = f"/media/{thumb_path.name}"
                            fixed += 1
                        else:
                            failed += 1
                            item["thumb_url"] = "/assets/video-placeholder.svg"
                    except Exception as e:
                        failed += 1
                        item["thumb_url"] = "/assets/video-placeholder.svg"
                else:
                    failed += 1
            items_checked.append(msg_id)
                
        elif media_kind == "image":
            thumb_path = service._image_thumb_path(msg_id)
            if not thumb_path.exists():
                # Try to find cached image
                cached_image = service._find_image_file(msg_id)
                if cached_image and cached_image.exists():
                    try:
                        import shutil
                        shutil.copy2(cached_image, thumb_path)
                        await service._optimize_thumbnail(thumb_path)
                        if thumb_path.exists():
                            item["thumb_url"] = f"/media/{thumb_path.name}"
                            fixed += 1
                        else:
                            failed += 1
                    except Exception:
                        failed += 1
                        # Use original as fallback
                        item["thumb_url"] = item.get("url", "")
                else:
                    failed += 1
            items_checked.append(msg_id)
    
    service._save_index()
    
    return {
        "ok": True,
        "fixed": fixed,
        "failed": failed,
        "checked": len(items_checked),
        "message": f"Fixed {fixed} thumbnails, {failed} failed",
        "webapp": context,
    }


@app.post("/api/media/{message_id}/generate-ai")
async def api_generate_ai_for_item(
    message_id: int,
    priority: bool = Query(True),
    mode: str = Query("force", description="Generation mode: missing, fallback, style, force"),
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    """Force immediate AI title/description generation for a specific item."""
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)
    
    if not AI_TITLE_ENABLED:
        raise HTTPException(status_code=503, detail="AI titles are disabled")
    
    # Validate mode
    if mode not in {"missing", "fallback", "style", "force"}:
        mode = "force"
    
    async with service._lock:
        item = next(
            (x for x in service.media_index if int(x.get("message_id", 0)) == message_id),
            None,
        )
    
    if not item:
        raise HTTPException(status_code=404, detail=f"Media item {message_id} not found")
    
    # Remove from queue if already there (will be re-added at front)
    if message_id in service._ai_queue_ids:
        service._ai_queue_ids.discard(message_id)
        with suppress(ValueError):
            service._ai_queue.remove(message_id)
    
    # Add to front of queue for priority processing
    service._ai_queue.appendleft(message_id)
    service._ai_queue_ids.add(message_id)
    
    # Generate immediately
    try:
        title = await asyncio.wait_for(
            service._generate_ai_title_for_item(item, mode=mode),
            timeout=30,
        )
        
        # Save to index if title was generated
        if title:
            async with service._lock:
                current = next(
                    (x for x in service.media_index if int(x.get("message_id", 0)) == message_id),
                    None,
                )
                if current:
                    current["ai_title"] = title
                    current["ai_title_model"] = item.get("ai_title_model", "")
                    current["ai_title_generated_at"] = item.get("ai_title_generated_at")
                    current["ai_description"] = item.get("ai_description", "")
                    current["ai_description_model"] = item.get("ai_description_model", "")
                    current["ai_description_generated_at"] = item.get("ai_description_generated_at")
                    service._save_index()
        
        return {
            "ok": True,
            "message_id": message_id,
            "generated": title is not None,
            "ai_title": title,
            "ai_description": item.get("ai_description", ""),
            "webapp": context,
        }
    except asyncio.TimeoutError:
        return {
            "ok": True,
            "message_id": message_id,
            "generated": False,
            "queued": True,
            "message": "AI generation is taking longer than expected, queued for background processing",
            "webapp": context,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {e}")


@app.post("/api/thumbnails/regenerate")
async def api_regenerate_thumbnails(
    limit: int = Query(0, ge=0, le=5000, description="Max thumbnails (0=all)"),
    force: bool = Query(False, description="Force regenerate even if exists"),
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    """Regenerate missing thumbnails for ALL videos and images using ffmpeg."""
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)
    
    if not service._started:
        try:
            await asyncio.wait_for(service.start(), timeout=SERVICE_START_TIMEOUT_SECONDS)
        except TimeoutError as exc:
            raise HTTPException(status_code=504, detail="Service not ready") from exc
    
    items_needing_thumbs = []
    for item in service.media_index:
        msg_id = int(item.get("message_id", 0))
        media_kind = str(item.get("media_kind", ""))
        
        if media_kind == "video":
            thumb_path = service._thumb_path(msg_id)
            if force or not thumb_path.exists():
                items_needing_thumbs.append(item)
        elif media_kind == "image":
            thumb_path = service._image_thumb_path(msg_id)
            if force or not thumb_path.exists():
                items_needing_thumbs.append(item)
    
    # 0 = all items
    if limit > 0:
        items_needing_thumbs = items_needing_thumbs[:limit]
    
    if not items_needing_thumbs:
        return {
            "ok": True,
            "message": "No thumbnails needed",
            "processed": 0,
            "webapp": context,
        }
    
    logger.info(f"[THUMB] Regenerating {len(items_needing_thumbs)} thumbnails...")
    
    messages_map: Dict[int, Any] = {}
    for item in items_needing_thumbs:
        msg_id = int(item.get("message_id", 0))
        if msg_id not in messages_map:
            try:
                message = await service.client.get_messages(CHAT_ID, msg_id)
                messages_map[msg_id] = message
            except Exception as e:
                logger.warning(f"[THUMB] Failed to fetch message {msg_id}: {e}")
    
    await service._download_thumbs_parallel(items_needing_thumbs, messages_map)
    
    generated = 0
    for item in items_needing_thumbs:
        msg_id = int(item.get("message_id", 0))
        media_kind = str(item.get("media_kind", ""))
        
        if media_kind == "video":
            thumb_path = service._thumb_path(msg_id)
            if thumb_path.exists():
                generated += 1
        elif media_kind == "image":
            thumb_path = service._image_thumb_path(msg_id)
            if thumb_path.exists():
                generated += 1
    
    return {
        "ok": True,
        "processed": len(items_needing_thumbs),
        "generated": generated,
        "message": f"Generated {generated}/{len(items_needing_thumbs)} thumbnails",
        "webapp": context,
    }


@app.get("/api/health")
async def api_health() -> Dict[str, Any]:
    stats = compute_gallery_stats(service.media_index)
    
    # Count CDN vs local URLs
    cdn_count = 0
    local_count = 0
    for item in service.media_index:
        url = item.get("url", "")
        if url and url.startswith("https://cdn"):
            cdn_count += 1
        elif url and url.startswith("/media/"):
            local_count += 1
    
    thumb_stats = {"videos": 0, "images": 0, "total": 0}
    for item in service.media_index:
        msg_id = int(item.get("message_id", 0))
        media_kind = str(item.get("media_kind", ""))
        if media_kind == "video":
            if service._thumb_path(msg_id).exists():
                thumb_stats["videos"] += 1
        elif media_kind == "image":
            if service._image_thumb_path(msg_id).exists():
                thumb_stats["images"] += 1
    thumb_stats["total"] = thumb_stats["videos"] + thumb_stats["images"]
    
    return {
        "ok": True,
        "started": service._started,
        "cached_items": len(service.media_index),
        "synced_at": service.last_sync_at,
        "stats": stats,
        "cdn_mode": CDN_ONLY_MODE,
        "cdn_urls": cdn_count,
        "local_urls": local_count,
        "thumb_stats": thumb_stats,
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
        "ai_queue_length": len(service._ai_queue),
        "ai_titled_count": count_ai_titled_items(service.media_index),
    }


@app.post("/api/reset-cache")
async def api_reset_cache(
    clear_thumbnails: bool = Query(True, description="Clear thumbnail cache"),
    clear_media: bool = Query(False, description="Clear media files"),
    clear_index: bool = Query(False, description="Clear media index"),
    resync: bool = Query(True, description="Resync after reset"),
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    """Reset cache and optionally resync from Telegram."""
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)
    
    results = {"ok": True, "actions": []}
    
    if clear_thumbnails:
        count = 0
        for f in service.cache_dir.iterdir():
            if f.is_file() and ("_thumb.jpg" in f.name or "_image_thumb.jpg" in f.name):
                try:
                    f.unlink()
                    count += 1
                except Exception:
                    pass
        results["actions"].append(f"Cleared {count} thumbnails")
    
    if clear_media:
        count = 0
        for f in service.cache_dir.iterdir():
            if f.is_file() and ("_video" in f.name or "_image" in f.name):
                try:
                    f.unlink()
                    count += 1
                except Exception:
                    pass
        results["actions"].append(f"Cleared {count} media files")
    
    if clear_index:
        try:
            service.index_path.unlink(missing_ok=True)
            service.media_index = []
            results["actions"].append("Cleared media index")
        except Exception as e:
            results["actions"].append(f"Failed to clear index: {e}")
    
    results["media_index_count"] = len(service.media_index)
    
    if resync and not clear_index:
        try:
            await service.sync_group_media(limit=200, force_redownload=False, process_ai_realtime=True)
            results["actions"].append("Synced 200 items from Telegram")
        except Exception as e:
            results["actions"].append(f"Sync failed: {e}")
    
    results["webapp"] = context
    return results


@app.get("/view/{message_id}", include_in_schema=False)
async def serve_view_page(message_id: int):
    view_path = WEB_DIR / "public" / "view.html"
    if not view_path.exists():
        return Response("view.html not found", status_code=404)
    return FileResponse(view_path, headers={"Cache-Control": "no-cache"})


@app.get("/api/media/{message_id}")
async def get_single_media(
    message_id: int,
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)
    
    item = next((x for x in service.media_index if int(x.get("message_id", 0)) == message_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Media item not found")
        
    return {
        "ok": True,
        "item": item,
        "webapp": context,
    }


# ============================================
# Visitor Tracking
# ============================================

VISITORS_LOG = WEB_DIR / "media_cache" / "visitors.json"
_visitors_lock = asyncio.Lock()


def _parse_device(ua: str) -> Dict[str, str]:
    """Very lightweight User-Agent parser — no deps needed."""
    ua_lower = ua.lower()

    # OS
    if "android" in ua_lower:
        os_name = "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower:
        os_name = "iOS"
    elif "windows" in ua_lower:
        os_name = "Windows"
    elif "mac os" in ua_lower or "macintosh" in ua_lower:
        os_name = "macOS"
    elif "linux" in ua_lower:
        os_name = "Linux"
    else:
        os_name = "Unknown OS"

    # Browser
    if "edg/" in ua_lower or "edge/" in ua_lower:
        browser = "Edge"
    elif "chrome/" in ua_lower and "chromium" not in ua_lower:
        browser = "Chrome"
    elif "firefox/" in ua_lower:
        browser = "Firefox"
    elif "safari/" in ua_lower and "chrome" not in ua_lower:
        browser = "Safari"
    elif "opera" in ua_lower or "opr/" in ua_lower:
        browser = "Opera"
    else:
        browser = "Other"

    # Device type
    if any(x in ua_lower for x in ("mobile", "android", "iphone")):
        device_type = "Mobile"
    elif any(x in ua_lower for x in ("ipad", "tablet")):
        device_type = "Tablet"
    else:
        device_type = "Desktop"

    return {"os": os_name, "browser": browser, "device_type": device_type}


def _get_client_ip(request: Request) -> str:
    """Get real client IP even behind proxies / the serveo tunnel."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip", "")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


async def _geolocate(ip: str) -> Dict[str, str]:
    """Fetch geolocation from ip-api.com (free, no API key needed)."""
    if ip in ("127.0.0.1", "::1", "unknown", "localhost") or ip.startswith("192.168.") or ip.startswith("10."):
        return {"country": "Local", "city": "Local", "isp": "Local Network"}
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,country,regionName,city,isp,org"
        import urllib.request as _ur
        req = _ur.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        loop = asyncio.get_event_loop()
        body = await loop.run_in_executor(
            None, lambda: _ur.urlopen(req, timeout=5).read().decode()
        )
        data = json.loads(body)
        if data.get("status") == "success":
            return {
                "country": data.get("country", "?"),
                "region": data.get("regionName", ""),
                "city": data.get("city", "?"),
                "isp": data.get("isp") or data.get("org") or "?",
            }
    except Exception:
        pass
    return {"country": "?", "city": "?", "isp": "?"}


def _load_visitors() -> List[Dict]:
    try:
        if VISITORS_LOG.exists():
            return json.loads(VISITORS_LOG.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save_visitors(visitors: List[Dict]) -> None:
    try:
        VISITORS_LOG.parent.mkdir(parents=True, exist_ok=True)
        VISITORS_LOG.write_text(json.dumps(visitors, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[VISITORS] Could not save log: {e}")


@app.post("/api/track")
async def api_track(request: Request) -> Dict[str, Any]:
    """Log a page visit — IP, geolocation, device, referrer, Telegram user."""
    try:
        body = await request.json()
    except Exception:
        body = {}

    ip = _get_client_ip(request)
    ua = request.headers.get("user-agent", "")
    referrer = body.get("referrer") or request.headers.get("referer", "")
    page = body.get("page", "/")
    tg_user_id = body.get("tg_user_id")
    tg_username = body.get("tg_username")

    # Geo + device in parallel-ish
    geo = await _geolocate(ip)
    device = _parse_device(ua)

    entry: Dict[str, Any] = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "ip": ip,
        "country": geo.get("country", "?"),
        "region": geo.get("region", ""),
        "city": geo.get("city", "?"),
        "isp": geo.get("isp", "?"),
        "device_type": device["device_type"],
        "os": device["os"],
        "browser": device["browser"],
        "referrer": referrer[:200] if referrer else "Direct",
        "page": page,
        "ua": ua[:300],
    }
    if tg_user_id:
        entry["tg_user_id"] = tg_user_id
    if tg_username:
        entry["tg_username"] = tg_username

    logger.info(f"[VISITOR] {ip} | {geo.get('country')} {geo.get('city')} | {device['device_type']} {device['browser']} | ref={referrer or 'direct'}")

    async with _visitors_lock:
        visitors = _load_visitors()
        visitors.insert(0, entry)
        visitors = visitors[:5000]  # Keep max 5000 entries
        _save_visitors(visitors)

    return {"ok": True}


@app.get("/api/visitors")
async def api_visitors(
    limit: int = Query(100, ge=1, le=1000),
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    """Return visitor log (newest first)."""
    async with _visitors_lock:
        visitors = _load_visitors()

    total = len(visitors)
    sliced = visitors[:limit]

    # Summary stats
    countries: Dict[str, int] = {}
    devices: Dict[str, int] = {}
    browsers: Dict[str, int] = {}
    for v in visitors:
        c = v.get("country", "?")
        countries[c] = countries.get(c, 0) + 1
        d = v.get("device_type", "?")
        devices[d] = devices.get(d, 0) + 1
        b = v.get("browser", "?")
        browsers[b] = browsers.get(b, 0) + 1

    top_countries = sorted(countries.items(), key=lambda x: -x[1])[:10]
    top_devices = sorted(devices.items(), key=lambda x: -x[1])[:5]
    top_browsers = sorted(browsers.items(), key=lambda x: -x[1])[:5]

    return {
        "ok": True,
        "total": total,
        "visitors": sliced,
        "stats": {
            "top_countries": [{"country": k, "count": v} for k, v in top_countries],
            "devices": [{"type": k, "count": v} for k, v in top_devices],
            "browsers": [{"browser": k, "count": v} for k, v in top_browsers],
        },
    }


if __name__ == "__main__":
    if CDN_ONLY_MODE:
        print(f"CDN MODE ENABLED - Media will stream from Telegram CDN")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")


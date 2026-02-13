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
from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import mimetypes
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pyrogram import Client
from pyrogram.errors import RPCError

WEB_DIR = Path(__file__).resolve().parent
ROOT_DIR = WEB_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import API_HASH, API_ID, BOT_TOKEN, BOT_USERNAME, CHAT_ID  # noqa: E402

PORT = 5000
DEFAULT_SYNC_LIMIT = 250
MAX_SYNC_LIMIT = 2000
STRICT_TWA_VERIFY = os.getenv("TWA_VERIFY_STRICT", "0") == "1"

GALLERY_AUTH_MODE = os.getenv("TELEGRAM_GALLERY_AUTH", "auto").strip().lower()
if GALLERY_AUTH_MODE not in {"auto", "bot", "user"}:
    GALLERY_AUTH_MODE = "auto"

GALLERY_USER_SESSION = os.getenv("TELEGRAM_GALLERY_SESSION", "twa_user")


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
        self.media_index: List[Dict[str, Any]] = []
        self.last_sync_error: Optional[str] = None
        self._lock = asyncio.Lock()
        self._started = False

        self.session_mode = self._resolve_session_mode()
        self.client = self._build_client(self.session_mode)

    def _resolve_session_mode(self) -> str:
        if GALLERY_AUTH_MODE in {"bot", "user"}:
            return GALLERY_AUTH_MODE

        user_session_path = self.cache_dir / f"{GALLERY_USER_SESSION}.session"
        if user_session_path.exists():
            return "user"

        return "bot"

    def _build_client(self, mode: str) -> Client:
        if mode == "user":
            return Client(
                name=GALLERY_USER_SESSION,
                api_id=API_ID,
                api_hash=API_HASH,
                workdir=str(self.cache_dir),
            )

        return Client(
            name="web_gallery_session",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workdir=str(self.cache_dir),
        )

    async def start(self) -> None:
        if not self._started:
            await self.client.start()
            self._started = True
            self._load_index()

    async def stop(self) -> None:
        if self._started:
            await self.client.stop()
            self._started = False

    def _load_index(self) -> None:
        if not self.index_path.exists():
            return
        try:
            payload = json.loads(self.index_path.read_text(encoding="utf-8"))
            self.media_index = payload.get("items", [])
            self.last_sync_at = payload.get("synced_at")
            self.last_sync_limit = int(payload.get("limit", 0))
            self.last_sync_error = payload.get("last_error")
        except (ValueError, OSError):
            self.media_index = []

    def _save_index(self) -> None:
        payload = {
            "synced_at": self.last_sync_at,
            "limit": self.last_sync_limit,
            "items": self.media_index,
            "last_error": self.last_sync_error,
            "session_mode": self.session_mode,
        }
        self.index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

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

    async def sync_group_media(self, limit: int, force_redownload: bool = False) -> List[Dict[str, Any]]:
        limit = max(1, min(limit, MAX_SYNC_LIMIT))

        async with self._lock:
            if not self._started:
                await self.start()

            items: List[Dict[str, Any]] = []

            try:
                async for message in self.client.get_chat_history(CHAT_ID, limit=limit):
                    media_tuple = self._extract_media(message)
                    if not media_tuple:
                        continue

                    media_kind, media_obj, mime_type, ext = media_tuple
                    local_name = f"{message.id}_{media_kind}{ext}"
                    local_path = self.cache_dir / local_name

                    if force_redownload and local_path.exists():
                        local_path.unlink(missing_ok=True)

                    if not local_path.exists():
                        downloaded_path = await self.client.download_media(message, file_name=str(local_path))
                        if not downloaded_path:
                            continue
                        local_path = Path(downloaded_path)
                        local_name = local_path.name

                    msg_date = message.date
                    if msg_date and msg_date.tzinfo is None:
                        msg_date = msg_date.replace(tzinfo=timezone.utc)

                    item = {
                        "message_id": message.id,
                        "media_kind": media_kind,
                        "file_name": local_name,
                        "url": f"/media/{local_name}",
                        "mime_type": mime_type,
                        "size": int(getattr(media_obj, "file_size", local_path.stat().st_size) or 0),
                        "width": getattr(media_obj, "width", None),
                        "height": getattr(media_obj, "height", None),
                        "duration": getattr(media_obj, "duration", None),
                        "caption": (message.caption or "").strip(),
                        "date": (msg_date or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
                    }
                    items.append(item)

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

            items.sort(key=lambda item: item["message_id"], reverse=True)

            self.media_index = items
            self.last_sync_limit = limit
            self.last_sync_at = datetime.now(timezone.utc).isoformat()
            self.last_sync_error = None
            self._save_index()

            return self.media_index


service = TelegramGalleryService(cache_dir=WEB_DIR / "media_cache")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await service.start()
        try:
            await service.sync_group_media(limit=DEFAULT_SYNC_LIMIT, force_redownload=False)
        except HTTPException:
            # Keep web server alive even when Telegram sync fails.
            pass
    except Exception as exc:
        # Keep app booting so UI and health endpoint stay reachable.
        service.last_sync_error = f"Startup sync unavailable: {exc}"
    try:
        yield
    finally:
        await service.stop()


app = FastAPI(title="Telegram Mini App Gallery", version="3.1.0", lifespan=lifespan)

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


@app.get("/api/media")
async def api_media(
    limit: int = Query(DEFAULT_SYNC_LIMIT, ge=1, le=MAX_SYNC_LIMIT),
    refresh: bool = Query(False),
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)

    sync_error: Optional[str] = None
    needs_sync = refresh or not service.media_index or service.last_sync_limit < limit

    if needs_sync:
        try:
            items = await service.sync_group_media(limit=limit, force_redownload=False)
        except HTTPException as exc:
            items = service.media_index
            sync_error = str(exc.detail)
    else:
        items = service.media_index

    return {
        "items": items[:limit],
        "total": len(items),
        "synced_at": service.last_sync_at,
        "chat_id": CHAT_ID,
        "webapp": context,
        "sync_error": sync_error or service.last_sync_error,
        "session_mode": service.session_mode,
    }


@app.post("/api/sync")
async def api_sync(
    limit: int = Query(DEFAULT_SYNC_LIMIT, ge=1, le=MAX_SYNC_LIMIT),
    force_redownload: bool = Query(False),
    init_data: Optional[str] = Header(default=None, alias="X-Telegram-Init-Data"),
    user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
) -> Dict[str, Any]:
    context = resolve_webapp_context(init_data=init_data, user_agent=user_agent)

    try:
        items = await service.sync_group_media(limit=limit, force_redownload=force_redownload)
        sync_error = None
    except HTTPException as exc:
        items = service.media_index
        sync_error = str(exc.detail)

    return {
        "items": items[:limit],
        "total": len(items),
        "synced_at": service.last_sync_at,
        "chat_id": CHAT_ID,
        "webapp": context,
        "sync_error": sync_error,
        "session_mode": service.session_mode,
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
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")

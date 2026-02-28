import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("AfterDark")


class VideyUploader:
    """Upload local video files to Videy and return CDN links."""

    DEFAULT_UPLOAD_ENDPOINT = "https://videy.co/api/upload"
    DEFAULT_TIMEOUT_SECONDS = 120

    @staticmethod
    def _is_enabled() -> bool:
        return os.getenv("VIDEY_UPLOAD_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}

    @staticmethod
    def _upload_endpoint() -> str:
        return os.getenv("VIDEY_UPLOAD_ENDPOINT", VideyUploader.DEFAULT_UPLOAD_ENDPOINT).strip()

    @staticmethod
    def _timeout_seconds() -> int:
        raw = os.getenv("VIDEY_UPLOAD_TIMEOUT", str(VideyUploader.DEFAULT_TIMEOUT_SECONDS)).strip()
        try:
            return max(10, int(raw))
        except Exception:
            return VideyUploader.DEFAULT_TIMEOUT_SECONDS

    @staticmethod
    def _normalize_cdn_url(upload_response_text: str) -> Optional[str]:
        value = (upload_response_text or "").strip()
        if not value:
            return None

        # API can return either an id or a full URL.
        if value.startswith("http://") or value.startswith("https://"):
            return value

        if re.fullmatch(r"[A-Za-z0-9_-]+", value):
            return f"https://cdn.videy.co/{value}.mp4"

        return None

    @staticmethod
    def _upload_sync(video_path: str) -> Optional[str]:
        endpoint = VideyUploader._upload_endpoint()
        timeout = VideyUploader._timeout_seconds()

        try:
            with open(video_path, "rb") as fh:
                files = {"file": (Path(video_path).name, fh, "video/mp4")}
                response = requests.post(endpoint, files=files, timeout=timeout)

            response.raise_for_status()

            # Prefer plain text id/url; fall back to common JSON shapes.
            cdn_url = VideyUploader._normalize_cdn_url(response.text)
            if cdn_url:
                return cdn_url

            try:
                data = response.json()
            except Exception:
                data = {}

            for key in ("url", "cdn_url", "link", "id"):
                if key in data:
                    cdn_url = VideyUploader._normalize_cdn_url(str(data[key]))
                    if cdn_url:
                        return cdn_url
        except Exception as exc:
            logger.warning(f"Videy upload failed for {video_path}: {exc}")
            return None

        logger.warning(f"Videy upload returned unrecognized response for {video_path}")
        return None

    @staticmethod
    async def upload_video(video_path: str) -> Optional[str]:
        if not VideyUploader._is_enabled():
            return None
        if not video_path or not os.path.exists(video_path):
            return None
        return await asyncio.to_thread(VideyUploader._upload_sync, video_path)


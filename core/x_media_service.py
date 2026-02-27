import asyncio
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional


class XMediaService:
    """Extract media post URLs from an X/Twitter user media timeline."""

    STATUS_RE = re.compile(r"(?:https?://)?(?:x\.com|twitter\.com)/[^/\s]+/status/(\d+)", re.IGNORECASE)
    IMAGE_EXT_RE = re.compile(r"\.(jpg|jpeg|png|webp|gif)(?:\?|$)", re.IGNORECASE)

    @staticmethod
    def _iter_values(node: Any):
        if isinstance(node, dict):
            for value in node.values():
                yield from XMediaService._iter_values(value)
        elif isinstance(node, list):
            for value in node:
                yield from XMediaService._iter_values(value)
        else:
            yield node

    @staticmethod
    def _extract_status_id(entry: Any) -> Optional[str]:
        if isinstance(entry, str):
            match = XMediaService.STATUS_RE.search(entry) or re.search(r"/status/(\d+)", entry)
            return match.group(1) if match else None

        if isinstance(entry, list):
            return None

        if not isinstance(entry, dict):
            return None

        # Common explicit fields first.
        for key in ("tweet_id", "tweetId", "tweet_id_str"):
            value = entry.get(key)
            if isinstance(value, (int, str)) and str(value).isdigit():
                return str(value)

        # Fallback: scan shallow string values for a /status/<id> pattern.
        for value in entry.values():
            if not isinstance(value, str):
                continue
            match = XMediaService.STATUS_RE.search(value) or re.search(r"/status/(\d+)", value)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _collect_status_ids(node: Any, out: List[str], seen: set) -> None:
        status_id = XMediaService._extract_status_id(node)
        if status_id and status_id not in seen:
            seen.add(status_id)
            out.append(status_id)

        if isinstance(node, dict):
            for value in node.values():
                XMediaService._collect_status_ids(value, out, seen)
        elif isinstance(node, list):
            for value in node:
                XMediaService._collect_status_ids(value, out, seen)

    @staticmethod
    def _classify_media_url(url: str) -> str:
        text = (url or "").lower()
        if ".mp4" in text or ".m3u8" in text or "video.twimg.com" in text:
            return "video"
        if XMediaService.IMAGE_EXT_RE.search(text):
            return "image"
        if "pbs.twimg.com/media/" in text:
            return "image"
        return "unknown"

    @staticmethod
    def _extract_from_payload(username: str, payload: Any, limit: Optional[int]) -> Dict[str, Any]:
        status_ids: List[str] = []
        seen_ids = set()
        image_count = 0
        video_count = 0
        unknown_count = 0

        # Try event stream shape first: [ [2, metadata], [3, media_url, ...], ... ]
        if isinstance(payload, list) and payload and isinstance(payload[0], list):
            current_status_id: Optional[str] = None
            include_current = False

            for event in payload:
                if not isinstance(event, list) or not event:
                    continue

                event_type = event[0]
                if event_type == 2 and len(event) > 1:
                    sid = XMediaService._extract_status_id(event[1])
                    if sid and sid.isdigit() and len(sid) >= 18 and sid not in seen_ids:
                        if limit and len(status_ids) >= limit:
                            current_status_id = None
                            include_current = False
                            continue
                        seen_ids.add(sid)
                        status_ids.append(sid)
                        current_status_id = sid
                        include_current = True
                    else:
                        current_status_id = None
                        include_current = False
                elif event_type == 3 and include_current:
                    media_url = None
                    # gallery-dl commonly emits [3, "<url>", {...}]
                    if len(event) > 1 and isinstance(event[1], str):
                        media_url = event[1]
                    elif len(event) > 2 and isinstance(event[2], str):
                        media_url = event[2]
                    if media_url:
                        kind = XMediaService._classify_media_url(media_url)
                        if kind == "image":
                            image_count += 1
                        elif kind == "video":
                            video_count += 1
                        else:
                            unknown_count += 1

            return {
                "post_urls": [f"https://x.com/{username}/status/{sid}" for sid in status_ids],
                "image_count": image_count,
                "video_count": video_count,
                "unknown_count": unknown_count,
            }

        # Generic fallback: recursive status extraction only.
        XMediaService._collect_status_ids(payload, status_ids, seen_ids)
        status_ids = [sid for sid in status_ids if sid.isdigit() and len(sid) >= 18]
        if limit:
            status_ids = status_ids[:limit]
        return {
            "post_urls": [f"https://x.com/{username}/status/{sid}" for sid in status_ids],
            "image_count": 0,
            "video_count": 0,
            "unknown_count": 0,
        }

    @staticmethod
    async def fetch_media_data(
        username: str,
        limit: Optional[int] = None,
        cookies_file: str = "config/twitter_cookies.txt",
    ) -> Dict[str, Any]:
        username = (username or "").strip().lstrip("@")
        if not username:
            return {"post_urls": [], "image_count": 0, "video_count": 0, "unknown_count": 0}

        target_url = f"https://x.com/{username}/media"
        cmd = [
            sys.executable,
            "-m",
            "gallery_dl",
            "--ignore-config",
            "--dump-json",
            "--quiet",
            target_url,
        ]

        if cookies_file and os.path.exists(cookies_file) and os.path.getsize(cookies_file) > 0:
            cmd.extend(["--cookies", cookies_file])

        completed = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )

        output = (completed.stdout or "").strip()
        if not output:
            return {"post_urls": [], "image_count": 0, "video_count": 0, "unknown_count": 0}

        try:
            payload = json.loads(output)
            return XMediaService._extract_from_payload(username, payload, limit)
        except json.JSONDecodeError:
            # If not a single JSON blob, parse line by line and merge.
            merged_urls: List[str] = []
            seen = set()
            for raw_line in output.splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                partial = XMediaService._extract_from_payload(username, payload, None)
                for url in partial["post_urls"]:
                    if url not in seen:
                        seen.add(url)
                        merged_urls.append(url)
            if limit:
                merged_urls = merged_urls[:limit]
            return {"post_urls": merged_urls, "image_count": 0, "video_count": 0, "unknown_count": 0}

    @staticmethod
    async def fetch_media_post_urls(
        username: str,
        limit: Optional[int] = None,
        cookies_file: str = "config/twitter_cookies.txt",
    ) -> List[str]:
        data = await XMediaService.fetch_media_data(username=username, limit=limit, cookies_file=cookies_file)
        return data.get("post_urls", [])

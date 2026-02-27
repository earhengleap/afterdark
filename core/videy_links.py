from __future__ import annotations

from datetime import datetime
import re
from typing import List

from models.enums import user_downloads
from core.database import history_db


VIDEY_URL_PATTERN = re.compile(r"https?://(?:cdn\.)?videy\.co/[^\s<>\"`]+", re.IGNORECASE)


def _extract_videy_links(text: str) -> List[str]:
    if not text:
        return []
    return list(dict.fromkeys(VIDEY_URL_PATTERN.findall(str(text))))


def _is_videy_link(link: str) -> bool:
    if not link:
        return False
    return bool(VIDEY_URL_PATTERN.match(str(link).strip()))


def add_videy_link(user_id: int, link: str, source_url: str = "") -> None:
    if not user_id or not link:
        return
    if not _is_videy_link(link):
        return
    key = f"{user_id}_videy_links"

    record = {
        "link": str(link).strip(),
        "source": str(source_url or "").strip(),
        "ts": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }
    user_downloads.append_list_item(key, record)


def _sync_videy_links_from_history(user_id: int) -> None:
    """
    Merge historical Videy URLs from download history into persistent Videy links.
    Keeps only Videy URLs in the store.
    """
    if not user_id:
        return

    key = f"{user_id}_videy_links"
    existing = user_downloads.get(key, [])
    if not isinstance(existing, list):
        existing = []

    # Keep valid Videy links only (and normalize legacy shapes).
    filtered_existing = []
    seen = set()
    for item in existing:
        if isinstance(item, dict):
            link = str(item.get("link", "")).strip()
            if _is_videy_link(link):
                if link not in seen:
                    filtered_existing.append(
                        {
                            "link": link,
                            "source": str(item.get("source", "")).strip(),
                            "ts": str(item.get("ts", "")).strip() or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )
                    seen.add(link)
        elif isinstance(item, str):
            link = item.strip()
            if _is_videy_link(link) and link not in seen:
                filtered_existing.append(
                    {
                        "link": link,
                        "source": "",
                        "ts": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )
                seen.add(link)

    # Backfill from download history table.
    try:
        all_history = history_db.get_all_user_history(user_id)
    except Exception:
        all_history = []

    for entry in all_history:
        for link in _extract_videy_links(str(entry.get("url", ""))):
            if link in seen:
                continue
            ts = entry.get("timestamp")
            ts_str = (
                ts.strftime("%Y-%m-%d %H:%M:%S")
                if hasattr(ts, "strftime")
                else datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            )
            filtered_existing.append(
                {
                    "link": link,
                    "source": str(entry.get("url", "")).strip(),
                    "ts": ts_str,
                }
            )
            seen.add(link)

    user_downloads[key] = filtered_existing


def get_videy_links(user_id: int) -> List[dict]:
    _sync_videy_links_from_history(user_id)
    key = f"{user_id}_videy_links"
    items = user_downloads.get(key, [])
    if not isinstance(items, list):
        return []
    cleaned = []
    for item in items:
        if isinstance(item, dict) and _is_videy_link(str(item.get("link", "")).strip()):
            cleaned.append(item)
    return cleaned

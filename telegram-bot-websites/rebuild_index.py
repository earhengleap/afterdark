#!/usr/bin/env python3
"""
Rebuild media_index.json from existing cached files.
Run this when the server can't connect to Telegram but you have cached media.
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime, timezone

CACHE_DIR = Path(__file__).parent / "media_cache"
INDEX_PATH = CACHE_DIR / "media_index.json"


def get_media_kind(filename: str) -> str:
    lower_name = filename.lower()
    if lower_name.endswith(".mp4") or lower_name.endswith(".webm") or lower_name.endswith(".mov"):
        return "video"
    if "_video" in filename:
        return "video"
    return "image"


def get_message_id(filename: str) -> int:
    match = re.match(r"^(\d+)_", filename)
    if match:
        return int(match.group(1))
    return 0


def get_file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except:
        return 0


def find_thumb_for_video(message_id: int, files: list) -> str:
    thumb_name = f"{message_id}_thumb.jpg"
    frame_name = f"{message_id}_frame.jpg"
    for f in files:
        if f == thumb_name or f == frame_name:
            return f"/media/{f}"
    return "/assets/video-placeholder.svg"


def find_thumb_for_image(message_id: int, files: list) -> str:
    thumb_name = f"{message_id}_image_thumb.jpg"
    ai_thumb_name = f"{message_id}_image_ai_thumb.jpg"
    for f in files:
        if f == thumb_name or f == ai_thumb_name:
            return f"/media/{f}"
    return ""


def is_main_media_file(filename: str, media_kind: str) -> bool:
    lower_name = filename.lower()
    if "_thumb" in lower_name or "_frame" in lower_name or "_ai_thumb" in lower_name:
        return False
    if media_kind == "video":
        return lower_name.endswith(".mp4") or lower_name.endswith(".webm") or lower_name.endswith(".mov")
    return lower_name.endswith(".jpg") or lower_name.endswith(".jpeg") or lower_name.endswith(".png")


def main():
    if not CACHE_DIR.exists():
        print(f"Cache directory not found: {CACHE_DIR}")
        return
    
    files = os.listdir(CACHE_DIR)
    print(f"Found {len(files)} files in cache")
    
    media_files = {}
    
    for filename in files:
        path = CACHE_DIR / filename
        if not path.is_file():
            continue
        
        message_id = get_message_id(filename)
        if message_id == 0:
            continue
        
        file_kind = get_media_kind(filename)
        
        if message_id not in media_files:
            media_files[message_id] = {
                "message_id": message_id,
                "media_kind": "image",
                "file_name": "",
                "url": "",
                "thumb_url": "",
                "mime_type": "image/jpeg",
                "size": 0,
                "is_cached": True,
                "caption": "",
                "ai_title": "",
                "ai_description": "",
                "date": datetime.now(timezone.utc).isoformat(),
                "_has_video": False,
                "_has_image": False,
            }
        
        entry = media_files[message_id]
        
        if file_kind == "video":
            entry["_has_video"] = True
            if is_main_media_file(filename, file_kind):
                entry["media_kind"] = "video"
                entry["file_name"] = filename
                entry["url"] = f"/media/{filename}"
                entry["mime_type"] = "video/mp4"
                entry["size"] = max(entry.get("size", 0), get_file_size(path))
                entry["thumb_url"] = find_thumb_for_video(message_id, files)
        else:
            entry["_has_image"] = True
            if is_main_media_file(filename, file_kind):
                if not entry["_has_video"]:
                    entry["media_kind"] = "image"
                    entry["file_name"] = filename
                    entry["url"] = f"/media/{filename}"
                    entry["size"] = max(entry.get("size", 0), get_file_size(path))
                    img_thumb = find_thumb_for_image(message_id, files)
                    entry["thumb_url"] = img_thumb if img_thumb else f"/media/{filename}"
    
    for entry in media_files.values():
        entry.pop("_has_video", None)
        entry.pop("_has_image", None)
    
    items = sorted(media_files.values(), key=lambda x: x["message_id"], reverse=True)
    
    videos = sum(1 for i in items if i["media_kind"] == "video")
    images = len(items) - videos
    total_size = sum(i.get("size", 0) for i in items)
    
    payload = {
        "items": items,
        "version": 1,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    
    INDEX_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print(f"\nRebuilt index:")
    print(f"  Total: {len(items)} items")
    print(f"  Videos: {videos}")
    print(f"  Images: {images}")
    print(f"  Size: {total_size / (1024*1024):.1f} MB")
    print(f"\nSaved to: {INDEX_PATH}")


if __name__ == "__main__":
    main()

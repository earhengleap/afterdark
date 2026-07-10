import json
import os
from pathlib import Path

index_path = Path("dashboard/media_cache/media_index.json")
if index_path.exists():
    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        items = data.get("items", [])
        print(f"Total items in index: {len(items)}")
        if items:
            print(f"First item: {items[0]['message_id']}")
else:
    print("Index file not found")

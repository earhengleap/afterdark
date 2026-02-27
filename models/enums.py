"""
Constants and enums
"""

import pickle
from pathlib import Path
from threading import RLock


class PersistentDict(dict):
    """Dictionary that persists mutations to disk."""

    def __init__(self, file_path: Path):
        super().__init__()
        self._file_path = Path(file_path)
        self._lock = RLock()
        self._load()

    def _load(self) -> None:
        with self._lock:
            try:
                if not self._file_path.exists():
                    return
                with self._file_path.open("rb") as f:
                    data = pickle.load(f)
                if isinstance(data, dict):
                    super().update(data)
            except Exception:
                # Ignore corrupted state and continue with empty cache.
                pass

    def _save(self) -> None:
        with self._lock:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._file_path.with_suffix(self._file_path.suffix + ".tmp")
            with tmp_path.open("wb") as f:
                pickle.dump(dict(self), f, protocol=pickle.HIGHEST_PROTOCOL)
            tmp_path.replace(self._file_path)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._save()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._save()

    def clear(self):
        super().clear()
        self._save()

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)
        self._save()

    def pop(self, key, default=None):
        if key in self:
            value = super().pop(key)
            self._save()
            return value
        return default

    def popitem(self):
        item = super().popitem()
        self._save()
        return item

    def setdefault(self, key, default=None):
        if key in self:
            return self[key]
        super().__setitem__(key, default)
        self._save()
        return default

    def append_list_item(self, key, item):
        """Atomically append an item to a list value and persist."""
        with self._lock:
            existing = super().get(key, [])
            if not isinstance(existing, list):
                existing = []
            existing.append(item)
            super().__setitem__(key, existing)
            self._save()


# Global state dictionaries (persisted where needed)
user_downloads = PersistentDict(Path("data/runtime/user_downloads.pkl"))
user_selections = {}
upload_progress = {}

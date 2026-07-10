"""
In-memory state stores for the bot session.

user_downloads  — ephemeral mapping of keys → file paths / lists.
                  Previously a PersistentDict backed by pickle that wrote to
                  disk on *every* assignment, causing hidden I/O overhead and
                  growing unboundedly.  It's now a plain dict with a lightweight
                  TTL eviction layer so stale entries (paths that no longer
                  exist on disk) are automatically purged.

user_selections — transient UI selection state (no persistence needed).
upload_progress — transient upload progress state (no persistence needed).
"""

import time
import threading
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("AfterDark.State")


class TTLDict:
    """
    A thread-safe dict with per-key TTL expiry.

    • Entries expire silently after `default_ttl` seconds.
    • An optional background reaper thread prunes stale keys every
      `reap_interval` seconds so memory doesn't grow forever.
    • The public API is dict-compatible (get / __setitem__ / __getitem__ /
      __delitem__ / __contains__) so existing call-sites need zero changes.
    """

    def __init__(self, default_ttl: int = 3600, reap_interval: int = 300):
        self._store: dict[str, tuple[Any, float]] = {}  # key → (value, expires_at)
        self._lock = threading.Lock()
        self._default_ttl = default_ttl
        self._reap_interval = reap_interval
        self._start_reaper()

    # ── internal ──────────────────────────────────────────────────────────────

    def _expires_at(self, ttl: Optional[int] = None) -> float:
        return time.monotonic() + (ttl if ttl is not None else self._default_ttl)

    def _is_alive(self, expires_at: float) -> bool:
        return time.monotonic() < expires_at

    def _start_reaper(self) -> None:
        t = threading.Thread(target=self._reap_loop, daemon=True, name="TTLDict-reaper")
        t.start()

    def _reap_loop(self) -> None:
        while True:
            time.sleep(self._reap_interval)
            self._reap()

    def _reap(self) -> None:
        now = time.monotonic()
        with self._lock:
            dead = [k for k, (_, exp) in self._store.items() if now >= exp]
            for k in dead:
                del self._store[k]
        if dead:
            logger.debug(f"TTLDict: reaped {len(dead)} expired key(s)")

    # ── dict-compatible public API ────────────────────────────────────────────

    def set(self, key: Any, value: Any, ttl: Optional[int] = None) -> None:
        """Store *value* under *key* with an optional custom TTL (seconds)."""
        str_key = str(key)
        with self._lock:
            self._store[str_key] = (value, self._expires_at(ttl))

    def get(self, key: Any, default: Any = None) -> Any:
        str_key = str(key)
        with self._lock:
            entry = self._store.get(str_key)
            if entry is None:
                return default
            value, expires_at = entry
            if not self._is_alive(expires_at):
                del self._store[str_key]
                return default
            return value

    def __setitem__(self, key: Any, value: Any) -> None:
        self.set(key, value)

    def __getitem__(self, key: Any) -> Any:
        str_key = str(key)
        with self._lock:
            entry = self._store.get(str_key)
            if entry is None:
                raise KeyError(key)
            value, expires_at = entry
            if not self._is_alive(expires_at):
                del self._store[str_key]
                raise KeyError(key)
            return value

    def __delitem__(self, key: Any) -> None:
        str_key = str(key)
        with self._lock:
            if str_key in self._store:
                del self._store[str_key]

    def __contains__(self, key: Any) -> bool:
        return self.get(key) is not None

    def pop(self, key: Any, default: Any = None) -> Any:
        str_key = str(key)
        with self._lock:
            entry = self._store.pop(str_key, None)
            if entry is None:
                return default
            value, expires_at = entry
            if not self._is_alive(expires_at):
                return default
            return value

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        now = time.monotonic()
        with self._lock:
            return sum(1 for _, (_, exp) in self._store.items() if now < exp)

    def stats(self) -> dict:
        """Return live / expired counts for diagnostics."""
        now = time.monotonic()
        with self._lock:
            alive = sum(1 for _, (_, exp) in self._store.items() if now < exp)
            total = len(self._store)
        return {"alive": alive, "expired": total - alive, "total_stored": total}

    def append_list_item(self, key: Any, item: Any, ttl: Optional[int] = None) -> None:
        """Atomically append *item* to the list stored at *key*.

        If the key does not exist (or has expired), a new list ``[item]`` is
        created.  The TTL is refreshed on every append so the list stays alive
        as long as it keeps receiving items.
        """
        str_key = str(key)
        with self._lock:
            entry = self._store.get(str_key)
            if entry is not None:
                current, exp = entry
                if time.monotonic() < exp and isinstance(current, list):
                    current.append(item)
                    # Refresh the TTL so active lists don't expire mid-use
                    self._store[str_key] = (current, self._expires_at(ttl))
                    return
            # Key missing, expired, or value wasn't a list — start fresh
            self._store[str_key] = ([item], self._expires_at(ttl))

    def get_list(self, key: Any, default: Optional[list] = None) -> list:
        """Return the list stored at *key*, or *default* (empty list) if absent."""
        value = self.get(key, default)
        if isinstance(value, list):
            return value
        return [] if default is None else default


# ── Global state stores ───────────────────────────────────────────────────────

# File-path / list store: keys expire after 2 hours of inactivity.
# 2 h is plenty of time for the user to hit "Upload" after a download.
user_downloads: TTLDict = TTLDict(default_ttl=7200, reap_interval=300)

# Transient UI state — plain dicts, no TTL needed
user_selections: dict = {}
upload_progress: dict = {}

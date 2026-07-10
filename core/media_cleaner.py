"""
MediaCleaner — disk cleanup service for AfterDark.

Provides:
  • scan_media_folders()  — walk media dirs and report file counts / sizes
  • delete_old_files()    — remove files older than N days, returns (count, bytes)
  • get_disk_report()     — human-readable storage summary for /cleanup command
  • start_auto_cleanup()  — background asyncio task for periodic purges
"""

import os
import asyncio
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger("AfterDark.MediaCleaner")


# ── Config ────────────────────────────────────────────────────────────────────

# Folders that contain downloaded media (relative to project root)
MEDIA_ROOTS = [
    Path("media/videos"),
    Path("media/images"),
]

# Files younger than this are never touched during auto-cleanup
AUTO_CLEANUP_MIN_AGE_DAYS: int = int(os.getenv("CLEANUP_MIN_AGE_DAYS", "7"))

# How often the background task runs (seconds)
AUTO_CLEANUP_INTERVAL_SECONDS: int = int(os.getenv("CLEANUP_INTERVAL_HOURS", "6")) * 3600

# Extensions that count as media files (others are skipped)
MEDIA_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv",
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
}


# ── Data types ────────────────────────────────────────────────────────────────

class FolderStat(NamedTuple):
    path: Path
    file_count: int
    total_bytes: int

    @property
    def total_mb(self) -> float:
        return self.total_bytes / (1024 * 1024)

    @property
    def total_gb(self) -> float:
        return self.total_bytes / (1024 * 1024 * 1024)


class CleanupResult(NamedTuple):
    deleted_files: int
    freed_bytes: int
    errors: int

    @property
    def freed_mb(self) -> float:
        return self.freed_bytes / (1024 * 1024)


# ── Core functions ────────────────────────────────────────────────────────────

def scan_media_folders(roots: list[Path] | None = None) -> list[FolderStat]:
    """
    Walk each media root and return per-folder statistics.
    Only counts files with recognised media extensions.
    """
    roots = roots or MEDIA_ROOTS
    results: list[FolderStat] = []

    for root in roots:
        if not root.exists():
            continue
        file_count = 0
        total_bytes = 0
        for entry in root.rglob("*"):
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in MEDIA_EXTENSIONS:
                continue
            try:
                total_bytes += entry.stat().st_size
                file_count += 1
            except OSError:
                pass
        results.append(FolderStat(path=root, file_count=file_count, total_bytes=total_bytes))

    return results


def delete_old_files(
    min_age_days: int = AUTO_CLEANUP_MIN_AGE_DAYS,
    roots: list[Path] | None = None,
    dry_run: bool = False,
) -> CleanupResult:
    """
    Delete media files older than *min_age_days* days.

    Args:
        min_age_days: Files newer than this are kept.
        roots: Folders to search (defaults to MEDIA_ROOTS).
        dry_run: If True, only log what *would* be deleted; don't actually remove.

    Returns:
        CleanupResult with counts of deleted files and freed bytes.
    """
    roots = roots or MEDIA_ROOTS
    cutoff = datetime.now() - timedelta(days=min_age_days)
    deleted = 0
    freed = 0
    errors = 0

    for root in roots:
        if not root.exists():
            continue
        for entry in root.rglob("*"):
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in MEDIA_EXTENSIONS:
                continue
            try:
                mtime = datetime.fromtimestamp(entry.stat().st_mtime)
                if mtime >= cutoff:
                    continue  # file is recent, keep it
                size = entry.stat().st_size
                if dry_run:
                    logger.info(f"[DRY RUN] Would delete: {entry} ({size / 1024:.1f} KB)")
                else:
                    entry.unlink()
                    logger.debug(f"Deleted old media: {entry} ({size / 1024:.1f} KB)")
                deleted += 1
                freed += size
            except OSError as e:
                logger.warning(f"Could not process {entry}: {e}")
                errors += 1

    if not dry_run:
        # Remove now-empty subdirectories (but not the roots themselves)
        for root in roots:
            if not root.exists():
                continue
            for dirpath in sorted(root.rglob("*"), reverse=True):
                if dirpath.is_dir() and dirpath != root:
                    try:
                        dirpath.rmdir()  # only succeeds if empty
                    except OSError:
                        pass

    if deleted > 0:
        action = "Would free" if dry_run else "Freed"
        logger.info(f"MediaCleaner: {deleted} file(s) processed. {action} {freed / (1024*1024):.2f} MB.")

    return CleanupResult(deleted_files=deleted, freed_bytes=freed, errors=errors)


def get_disk_report() -> str:
    """
    Build a human-readable storage report for the /cleanup Telegram command.
    Includes per-folder breakdown plus system disk usage.
    """
    folder_stats = scan_media_folders()

    if not folder_stats:
        media_section = "  📂 No media folders found yet.\n"
    else:
        lines = []
        for stat in folder_stats:
            if stat.total_mb >= 1024:
                size_str = f"{stat.total_gb:.2f} GB"
            else:
                size_str = f"{stat.total_mb:.1f} MB"
            lines.append(f"  📂 `{stat.path}` — {stat.file_count} files · {size_str}")
        media_section = "\n".join(lines) + "\n"

    total_bytes = sum(s.total_bytes for s in folder_stats)
    total_files = sum(s.file_count for s in folder_stats)
    if total_bytes >= 1024 ** 3:
        total_str = f"{total_bytes / (1024**3):.2f} GB"
    else:
        total_str = f"{total_bytes / (1024**2):.1f} MB"

    # System disk info for the drive that holds the project
    try:
        project_root = Path(".").resolve()
        usage = shutil.disk_usage(project_root)
        disk_pct = (usage.used / usage.total) * 100
        disk_free_gb = usage.free / (1024 ** 3)
        disk_total_gb = usage.total / (1024 ** 3)
        disk_section = (
            f"\n💽 **System Disk** (`{project_root.anchor}`)\n"
            f"  Used: {disk_pct:.1f}% · Free: {disk_free_gb:.1f} GB / {disk_total_gb:.1f} GB"
        )
    except Exception:
        disk_section = ""

    age_days = AUTO_CLEANUP_MIN_AGE_DAYS
    return (
        f"🗂️ **Media Storage Report**\n\n"
        f"{media_section}\n"
        f"📊 **Total:** {total_files} files · {total_str}\n"
        f"{disk_section}\n\n"
        f"♻️ Auto-cleanup removes files older than **{age_days} days**.\n"
        f"Use the buttons below to act."
    )


# ── Background auto-cleanup task ──────────────────────────────────────────────

async def start_auto_cleanup(interval_seconds: int | None = None) -> None:
    """
    Background asyncio task: periodically delete files older than
    AUTO_CLEANUP_MIN_AGE_DAYS days.  Runs every AUTO_CLEANUP_INTERVAL_SECONDS
    (default 6 hours) to keep disk usage in check without manual intervention.
    """
    interval = interval_seconds or AUTO_CLEANUP_INTERVAL_SECONDS
    logger.info(
        f"Auto-cleanup task started "
        f"(interval: {interval // 3600}h, min age: {AUTO_CLEANUP_MIN_AGE_DAYS}d)"
    )

    # Initial delay — don't run immediately on startup
    await asyncio.sleep(min(interval, 3600))

    while True:
        try:
            result = await asyncio.to_thread(
                delete_old_files, AUTO_CLEANUP_MIN_AGE_DAYS
            )
            if result.deleted_files > 0:
                logger.info(
                    f"Auto-cleanup: removed {result.deleted_files} file(s), "
                    f"freed {result.freed_mb:.1f} MB"
                    + (f", {result.errors} error(s)" if result.errors else "")
                )
        except asyncio.CancelledError:
            logger.info("Auto-cleanup task cancelled.")
            break
        except Exception as e:
            logger.error(f"Auto-cleanup error: {e}", exc_info=True)

        await asyncio.sleep(interval)

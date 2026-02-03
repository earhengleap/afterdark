"""
Download log management - FIXED VERSION
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional

from config.paths import LOG_FILE, DOWNLOAD_FOLDER
from core.file_manager import FileManager

class LogManager:
    """Handles download log operations - FIXED VERSION"""

    @staticmethod
    def load(sync: bool = False) -> List[Dict]:
        """
        Load log from file
        Args:
            sync: Whether to sync with folder (default: False to prevent auto-sync)
        """
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    log_data = json.loads(content) if content else []

                    # Only sync if explicitly requested
                    if sync:
                        return LogManager.sync_with_folder(log_data)
                    return log_data
            except Exception:
                return []
        return []

    @staticmethod
    def save(log_data: List[Dict]) -> None:
        """Save log to file"""
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def sync_with_folder(log_data: Optional[List[Dict]] = None) -> List[Dict]:
        """
        Sync log entries with actual files in folder
        Args:
            log_data: Existing log data (will load if not provided)
        Returns: Synced log data
        """
        # Load log if not provided
        if log_data is None:
            log_data = LogManager.load(sync=False)

        # Don't proceed if no log data
        if not log_data:
            return []

        # Get actual files in download folder
        actual_files = set()
        if os.path.exists(DOWNLOAD_FOLDER):
            for filename in os.listdir(DOWNLOAD_FOLDER):
                filepath = os.path.join(DOWNLOAD_FOLDER, filename)
                if os.path.isfile(filepath) and filename.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                    actual_files.add(filename)

        # Create new synced log
        synced_log = []
        files_to_remove = []

        for entry in log_data:
            filename = entry.get('filename', '')
            filepath = os.path.join(DOWNLOAD_FOLDER, filename)

            # Check if file exists
            if os.path.exists(filepath) and filename in actual_files:
                # Update filesize if available
                try:
                    entry['filesize'] = os.path.getsize(filepath)
                except Exception:
                    pass
                synced_log.append(entry)
            else:
                # Mark for removal (but don't print here)
                files_to_remove.append(filename)

        # Save if changes were made
        if len(synced_log) != len(log_data):
            LogManager.save(synced_log)
            # Only print summary, not every single file
            if files_to_remove:
                print(f"📊 Log sync: Removed {len(files_to_remove)} entries, {len(synced_log)} entries remain")

        return synced_log

    @staticmethod
    def add_entry(video_info: Dict, filename: str, url: str) -> None:
        """Add download entry to log - WITH PROPER SEQUENTIAL NUMBERING"""
        log = LogManager.load()  # Don't sync here
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)

        if not os.path.exists(filepath):
            print(f"⚠️ Warning: File not found, not adding to log: {filepath}")
            return

        # Check for duplicates
        if any(entry.get('filename') == filename for entry in log):
            print(f"ℹ️ File already in log: {filename}")
            return

        # Get the next number from the LOG, not from folder
        next_number = LogManager._get_next_log_number(log)

        try:
            actual_filesize = os.path.getsize(filepath)
        except Exception as e:
            print(f"⚠️ Error getting file size: {e}")
            actual_filesize = 0

        duration = video_info.get('duration') or video_info.get('duration_seconds') or 0

        log_entry = {
            'number': next_number,  # Use sequential log number
            'filename': filename,
            'url': url,
            'title': video_info.get('title', 'Unknown'),
            'uploader': video_info.get('uploader', 'Unknown'),
            'username': video_info.get('uploader_id', 'Unknown'),
            'upload_date': video_info.get('upload_date', 'Unknown'),
            'duration': duration,
            'filesize': actual_filesize,
            'download_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        log.append(log_entry)
        LogManager.save(log)
        print(f"✅ Added to log (#{next_number}): {filename} ({actual_filesize / (1024 * 1024):.2f} MB)")

    @staticmethod
    def _get_next_log_number(log_data: List[Dict]) -> int:
        """Get next sequential number from log entries"""
        if not log_data:
            return 1

        # Find the highest number in the log
        max_number = 0
        for entry in log_data:
            number = entry.get('number', 0)
            if isinstance(number, (int, float)):
                max_number = max(max_number, int(number))

        return max_number + 1

    @staticmethod
    def get_stats() -> Dict:
        """Get statistics with optional sync"""
        # Only sync when explicitly checking stats
        synced_log = LogManager.sync_with_folder()
        total_videos = FileManager.get_total_videos()

        return {
            'log_entries': len(synced_log),
            'actual_videos': total_videos,
            'synced': len(synced_log) == total_videos,
            'log_data': synced_log
        }

    @staticmethod
    def cleanup_old_entries(days_old: int = 30) -> None:
        """
        Clean up old log entries
        Args:
            days_old: Remove entries older than this many days
        """
        log = LogManager.load(sync=False)
        if not log:
            return

        cutoff_date = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
        cleaned_log = []
        removed_count = 0

        for entry in log:
            try:
                # Parse download date
                download_date_str = entry.get('download_date', '')
                if download_date_str:
                    download_date = datetime.strptime(download_date_str, '%Y-%m-%d %H:%M:%S')
                    if download_date.timestamp() > cutoff_date:
                        cleaned_log.append(entry)
                    else:
                        removed_count += 1
                else:
                    # Keep entries without date
                    cleaned_log.append(entry)
            except Exception:
                # Keep entries with invalid date format
                cleaned_log.append(entry)

        if removed_count > 0:
            LogManager.save(cleaned_log)
            print(f"🗑️ Cleaned up {removed_count} entries older than {days_old} days")

    @staticmethod
    def force_sync() -> None:
        """Force sync with folder and show detailed info"""
        print("🔄 Forcing log sync with folder...")
        LogManager.sync_with_folder()
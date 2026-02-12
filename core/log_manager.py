"""
Download log management - FIXED VERSION
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional

from config.paths import LOG_FILE, DOWNLOAD_FOLDER
from core.file_manager import FileManager
from core.logger import setup_logger

logger = setup_logger("LogManager")

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
        Sync log entries - UPDATED: Never removes entries, only updates metadata
        """
        if log_data is None:
            log_data = LogManager.load(sync=False)
            
        if not log_data:
            return []
            
        # Update file sizes if file exists, but NEVER remove entries
        updates_made = False
        for entry in log_data:
            filename = entry.get('filename', '')
            filepath = os.path.join(DOWNLOAD_FOLDER, filename)
            
            if os.path.exists(filepath):
                try:
                    current_size = os.path.getsize(filepath)
                    if entry.get('filesize') != current_size:
                        entry['filesize'] = current_size
                        updates_made = True
                except Exception:
                    pass
                    
        if updates_made:
            LogManager.save(log_data)
            
        return log_data

    @staticmethod
    def add_entry(video_info: Dict, filename: str, url: str) -> None:
        """Add download entry to log - WITH PROPER SEQUENTIAL NUMBERING"""
        log = LogManager.load()  # Don't sync here
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)

        if not os.path.exists(filepath):
            logger.warning(f"File not found, not adding to log: {filepath}")
            return

        # Check for duplicates
        if any(entry.get('filename') == filename for entry in log):
            logger.info(f"File already in log: {filename}")
            return

        # Get the next number from the LOG, not from folder
        next_number = LogManager._get_next_log_number(log)

        try:
            actual_filesize = os.path.getsize(filepath)
        except Exception as e:
            logger.warning(f"Error getting file size: {e}")
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
        logger.info(f"Added to log (#{next_number}): {filename} ({actual_filesize / (1024 * 1024):.2f} MB)")

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
        Clean up old log entries - DISABLED to preserve full history
        """
        # logger.info("Log cleanup is disabled to prevent history loss")
        return

    @staticmethod
    def force_sync() -> None:
        """Force sync with folder and show detailed info"""
        logger.info("Forcing log sync with folder...")
        LogManager.sync_with_folder()
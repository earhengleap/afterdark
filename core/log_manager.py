"""
Download log management
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Optional

from config.paths import LOG_FILE, DOWNLOAD_FOLDER
from core.file_manager import FileManager

class LogManager:
    """Handles download log operations"""
    
    @staticmethod
    def load() -> List[Dict]:
        """Load log from file"""
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    return json.loads(content) if content else []
            except Exception:
                return []
        return []
    
    @staticmethod
    def save(log_data: List[Dict]) -> None:
        """Save log to file"""
        with open(LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def sync_with_folder() -> List[Dict]:
        """Sync log entries with actual files in folder"""
        log = LogManager.load()
        if not log:
            return []
        
        actual_files = set()
        if os.path.exists(DOWNLOAD_FOLDER):
            for filename in os.listdir(DOWNLOAD_FOLDER):
                filepath = os.path.join(DOWNLOAD_FOLDER, filename)
                if os.path.isfile(filepath) and filename.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                    actual_files.add(filename)
        
        synced_log = []
        for entry in log:
            filename = entry.get('filename', '')
            filepath = os.path.join(DOWNLOAD_FOLDER, filename)
            
            if os.path.exists(filepath) and filename in actual_files:
                try:
                    entry['filesize'] = os.path.getsize(filepath)
                except Exception:
                    pass
                synced_log.append(entry)
            else:
                print(f"🗑️ Removed log entry for deleted file: {filename}")
        
        if len(synced_log) != len(log):
            LogManager.save(synced_log)
            print(f"✅ Log synced: {len(log)} → {len(synced_log)} entries")
        
        return synced_log
    
    @staticmethod
    def add_entry(video_info: Dict, filename: str, url: str) -> None:
        """Add download entry to log"""
        log = LogManager.sync_with_folder()
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)
        
        if not os.path.exists(filepath):
            print(f"⚠️ Warning: File not found, not adding to log: {filepath}")
            return
        
        # Check for duplicates
        if any(entry.get('filename') == filename for entry in log):
            print(f"ℹ️ File already in log: {filename}")
            return
        
        try:
            actual_filesize = os.path.getsize(filepath)
        except Exception as e:
            print(f"⚠️ Error getting file size: {e}")
            actual_filesize = 0
        
        duration = video_info.get('duration') or video_info.get('duration_seconds') or 0
        
        log_entry = {
            'number': FileManager.get_next_number() - 1,
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
        print(f"✅ Added to log: {filename} ({actual_filesize / (1024*1024):.2f} MB)")
    
    @staticmethod
    def get_stats() -> Dict:
        """Get statistics synced with folder"""
        synced_log = LogManager.sync_with_folder()
        total_videos = FileManager.get_total_videos()
        
        return {
            'log_entries': len(synced_log),
            'actual_videos': total_videos,
            'synced': len(synced_log) == total_videos,
            'log_data': synced_log
        }
"""
SQLite database manager for download history
"""

import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from core.logger import setup_logger

logger = setup_logger("HistoryDB")


class HistoryDB:
    """Manage download history in SQLite database"""
    
    def __init__(self, db_path: str = 'data/history.db'):
        self.db_path = db_path
        self._ensure_data_directory()
        self.init_database()
    
    def _ensure_data_directory(self):
        """Create data directory if it doesn't exist"""
        data_dir = os.path.dirname(self.db_path)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir)
            logger.info(f"Created data directory: {data_dir}")
    
    def init_database(self):
        """Create tables and indexes if they don't exist"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create download_history table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS download_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    source_username TEXT,
                    filename TEXT,
                    status TEXT,
                    content_type TEXT,
                    file_size INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    error_message TEXT
                )
            ''')
            
            # Create download_queue table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS download_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create user_settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    PRIMARY KEY (user_id, key)
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_timestamp 
                ON download_history(user_id, timestamp DESC)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_username 
                ON download_history(user_id, source_username)
            ''')
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
    # ... (keep existing methods) ...

    # ==================== SETTINGS METHODS ====================
    
    def set_setting(self, user_id: int, key: str, value: str) -> bool:
        """Set a user setting"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_settings (user_id, key, value)
                VALUES (?, ?, ?)
            ''', (user_id, key, str(value)))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to set setting: {e}")
            return False
            
    def get_setting(self, user_id: int, key: str, default: str = None) -> str:
        """Get a user setting"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM user_settings WHERE user_id = ? AND key = ?', (user_id, key))
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else default
        except Exception as e:
            logger.error(f"Failed to get setting: {e}")
            return default

    # ==================== QUEUE METHODS ====================

    def add_to_queue(self, user_id: int, url: str) -> bool:
        """Add URL to user's download queue"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO download_queue (user_id, url)
                VALUES (?, ?)
            ''', (user_id, url))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to add to queue: {e}")
            return False
            
    def get_queue(self, user_id: int) -> List[str]:
        """Get all URLs in user's queue"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT url FROM download_queue WHERE user_id = ? ORDER BY timestamp ASC', (user_id,))
            rows = cursor.fetchall()
            conn.close()
            return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Failed to get queue: {e}")
            return []
            
    def clear_queue(self, user_id: int) -> bool:
        """Clear user's queue"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM download_queue WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to clear queue: {e}")
            return False
            
    def get_queue_count(self, user_id: int) -> int:
        """Get count of items in queue"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM download_queue WHERE user_id = ?', (user_id,))
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            logger.error(f"Failed to get queue count: {e}")
            return 0
    
    def add_entry(self, user_id: int, url: str, source_username: Optional[str],
                  filename: Optional[str], status: str, content_type: str,
                  file_size: int = 0, error_message: Optional[str] = None) -> bool:
        """
        Add a download history entry
        
        Args:
            user_id: Telegram user ID
            url: Download URL
            source_username: Source username (e.g., @elonmusk)
            filename: Downloaded filename
            status: 'success' or 'failed'
            content_type: 'video', 'image', or 'unknown'
            file_size: File size in bytes
            error_message: Error message if failed
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO download_history 
                (user_id, url, source_username, filename, status, content_type, file_size, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, url, source_username, filename, status, content_type, file_size, error_message))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Added history entry: user={user_id}, url={url[:50]}..., status={status}")
            return True
        except Exception as e:
            logger.error(f"Failed to add history entry: {e}")
            return False
    
    def get_user_history(self, user_id: int, limit: int = 10, offset: int = 0) -> List[Dict]:
        """
        Get paginated history for a user
        
        Args:
            user_id: Telegram user ID
            limit: Number of entries to retrieve
            offset: Offset for pagination
            
        Returns:
            List of history entries as dictionaries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM download_history
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
            ''', (user_id, limit, offset))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Convert to list of dictionaries
            entries = []
            for row in rows:
                entries.append({
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'url': row['url'],
                    'source_username': row['source_username'],
                    'filename': row['filename'],
                    'status': row['status'],
                    'content_type': row['content_type'],
                    'file_size': row['file_size'],
                    'timestamp': datetime.fromisoformat(row['timestamp']),
                    'error_message': row['error_message']
                })
            
            return entries
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return []
    
    def get_all_user_history(self, user_id: int) -> List[Dict]:
        """
        Get ALL history for a user (for export)
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            List of all history entries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM download_history
                WHERE user_id = ?
                ORDER BY timestamp DESC
            ''', (user_id,))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Convert to list of dictionaries
            entries = []
            for row in rows:
                entries.append({
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'url': row['url'],
                    'source_username': row['source_username'],
                    'filename': row['filename'],
                    'status': row['status'],
                    'content_type': row['content_type'],
                    'file_size': row['file_size'],
                    'timestamp': datetime.fromisoformat(row['timestamp']),
                    'error_message': row['error_message']
                })
            
            return entries
        except Exception as e:
            logger.error(f"Failed to get all history: {e}")
            return []
    
    def get_total_count(self, user_id: int) -> int:
        """
        Get total number of entries for a user
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            Total count of history entries
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COUNT(*) FROM download_history
                WHERE user_id = ?
            ''', (user_id,))
            
            count = cursor.fetchone()[0]
            conn.close()
            
            return count
        except Exception as e:
            logger.error(f"Failed to get count: {e}")
            return 0
    
    def clear_user_history(self, user_id: int) -> bool:
        """
        Clear all history for a user
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                DELETE FROM download_history
                WHERE user_id = ?
            ''', (user_id,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            logger.info(f"Cleared {deleted_count} history entries for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")
            return False


# Global database instance
history_db = HistoryDB()

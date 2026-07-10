"""
SQLite database manager for download history
"""

import sqlite3
import os
from contextlib import contextmanager
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

    @contextmanager
    def _get_conn(self):
        """
        Context-manager that yields a connection and guarantees it is
        closed (and committed on success / rolled-back on error) even if
        an exception is raised mid-operation.

        WAL mode is applied once per connection so concurrent readers
        don't block the writer on an async event-loop.
        """
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")  # Wait up to 5 s on lock
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_database(self):
        """Create tables and indexes if they don't exist"""
        try:
            with self._get_conn() as conn:
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

                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS group_sync_state (
                        chat_id INTEGER PRIMARY KEY,
                        last_message_id INTEGER NOT NULL DEFAULT 0,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

                # Create indexes for better performance
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_user_timestamp
                    ON download_history(user_id, timestamp DESC)
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_filename
                    ON download_history(filename)
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_user_username
                    ON download_history(user_id, source_username)
                ''')

                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_history_url
                    ON download_history(user_id, url, timestamp DESC)
                ''')

            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")

    # ==================== SYNC METHODS ====================

    def get_sync_state(self, chat_id: int) -> int:
        """Get the last processed message ID for a chat"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT last_message_id FROM group_sync_state WHERE chat_id = ?",
                    (chat_id,)
                )
                row = cursor.fetchone()
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"Error getting sync state for {chat_id}: {e}")
            return 0

    def update_sync_state(self, chat_id: int, message_id: int):
        """Update the last processed message ID for a chat"""
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO group_sync_state (chat_id, last_message_id, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(chat_id) DO UPDATE SET
                        last_message_id = MAX(last_message_id, excluded.last_message_id),
                        updated_at = CURRENT_TIMESTAMP
                ''', (chat_id, message_id))
        except Exception as e:
            logger.error(f"Error updating sync state for {chat_id}: {e}")

    # ==================== SETTINGS METHODS ====================

    def set_setting(self, user_id: int, key: str, value: str) -> bool:
        """Set a user setting"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    'INSERT OR REPLACE INTO user_settings (user_id, key, value) VALUES (?, ?, ?)',
                    (user_id, key, str(value))
                )
            return True
        except Exception as e:
            logger.error(f"Failed to set setting: {e}")
            return False

    def get_setting(self, user_id: int, key: str, default: str = None) -> str:
        """Get a user setting"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    'SELECT value FROM user_settings WHERE user_id = ? AND key = ?',
                    (user_id, key)
                )
                result = cursor.fetchone()
            return result[0] if result else default
        except Exception as e:
            logger.error(f"Failed to get setting: {e}")
            return default

    # ==================== QUEUE METHODS ====================

    def add_to_queue(self, user_id: int, url: str) -> bool:
        """Add URL to user's download queue"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    'INSERT INTO download_queue (user_id, url) VALUES (?, ?)',
                    (user_id, url)
                )
            return True
        except Exception as e:
            logger.error(f"Failed to add to queue: {e}")
            return False

    def get_queue(self, user_id: int) -> List[str]:
        """Get all URLs in user's queue"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    'SELECT url FROM download_queue WHERE user_id = ? ORDER BY timestamp ASC',
                    (user_id,)
                )
                rows = cursor.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Failed to get queue: {e}")
            return []

    def clear_queue(self, user_id: int) -> bool:
        """Clear user's queue"""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    'DELETE FROM download_queue WHERE user_id = ?',
                    (user_id,)
                )
            return True
        except Exception as e:
            logger.error(f"Failed to clear queue: {e}")
            return False

    def get_queue_count(self, user_id: int) -> int:
        """Get count of items in queue"""
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    'SELECT COUNT(*) FROM download_queue WHERE user_id = ?',
                    (user_id,)
                )
                count = cursor.fetchone()[0]
            return count
        except Exception as e:
            logger.error(f"Failed to get queue count: {e}")
            return 0

    # ==================== HISTORY METHODS ====================

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
            with self._get_conn() as conn:
                conn.execute(
                    '''INSERT INTO download_history
                       (user_id, url, source_username, filename, status, content_type, file_size, error_message)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (user_id, url, source_username, filename, status, content_type, file_size, error_message)
                )
            logger.debug(f"Added history entry: user={user_id}, url={url[:50]}..., status={status}")
            return True
        except Exception as e:
            logger.error(f"Failed to add history entry: {e}")
            return False

    def is_recent_duplicate(self, user_id: int, url: str, within_seconds: int = 300) -> bool:
        """
        Check if the same URL was already downloaded successfully by this user
        within the given time window.  Use this to avoid redundant re-downloads.

        Args:
            user_id: Telegram user ID
            url: Download URL to check
            within_seconds: Look-back window in seconds (default 5 minutes)

        Returns:
            True if a successful download exists in the window, False otherwise
        """
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    '''SELECT COUNT(*) FROM download_history
                       WHERE user_id = ?
                         AND url = ?
                         AND status = 'success'
                         AND timestamp >= datetime('now', ? || ' seconds')''',
                    (user_id, url, f"-{within_seconds}")
                )
                count = cursor.fetchone()[0]
            return count > 0
        except Exception as e:
            logger.error(f"Failed to check duplicate: {e}")
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
            with self._get_conn() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    '''SELECT * FROM download_history
                       WHERE user_id = ?
                       ORDER BY timestamp DESC
                       LIMIT ? OFFSET ?''',
                    (user_id, limit, offset)
                )
                rows = cursor.fetchall()

            return [
                {
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'url': row['url'],
                    'source_username': row['source_username'],
                    'filename': row['filename'],
                    'status': row['status'],
                    'content_type': row['content_type'],
                    'file_size': row['file_size'],
                    'timestamp': datetime.fromisoformat(row['timestamp']),
                    'error_message': row['error_message'],
                }
                for row in rows
            ]
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
            with self._get_conn() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    '''SELECT * FROM download_history
                       WHERE user_id = ?
                       ORDER BY timestamp DESC''',
                    (user_id,)
                )
                rows = cursor.fetchall()

            return [
                {
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'url': row['url'],
                    'source_username': row['source_username'],
                    'filename': row['filename'],
                    'status': row['status'],
                    'content_type': row['content_type'],
                    'file_size': row['file_size'],
                    'timestamp': datetime.fromisoformat(row['timestamp']),
                    'error_message': row['error_message'],
                }
                for row in rows
            ]
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
            with self._get_conn() as conn:
                cursor = conn.execute(
                    'SELECT COUNT(*) FROM download_history WHERE user_id = ?',
                    (user_id,)
                )
                count = cursor.fetchone()[0]
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
            with self._get_conn() as conn:
                cursor = conn.execute(
                    'DELETE FROM download_history WHERE user_id = ?',
                    (user_id,)
                )
                deleted_count = cursor.rowcount
            logger.info(f"Cleared {deleted_count} history entries for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")
            return False


# Global database instance
history_db = HistoryDB()

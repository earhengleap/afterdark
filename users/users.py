"""
User Activity Manager
Handles user logging and history management asynchronously.
"""

import logging
from core.database import history_db

# Configure logging
logger = logging.getLogger("AfterDark.Users")

class UserManager:
    """
    Manages user logs and activity history by delegating to SQLite HistoryDB.
    """
    
    @classmethod
    async def log_action(cls, user_id: int, username: str, url: str, 
                        status: str, content_type: str = "unknown") -> None:
        """
        Log a user action (download, error, etc).
        
        Args:
            user_id: Telegram User ID
            username: User's username or first name
            url: The URL processed
            status: Status of action ('success', 'failed', 'invalid_input')
            content_type: Type of content ('video', 'image', 'unknown')
        """
        # Save to SQLite HistoryDB directly
        history_db.add_entry(
            user_id=user_id,
            url=url,
            source_username=username,
            filename=None,
            status=status,
            content_type=content_type
        )

        # Professional Logging
        cls._log_to_console(username, url, status, content_type)

    @staticmethod
    def _log_to_console(username: str, url: str, status: str, content_type: str):
        """Internal method to log formatted messages to console/logger"""
        short_url = url[:50] + "..." if len(url) > 50 else url
        
        if status == "success":
            if content_type == "video":
                logger.info(f"✅ Video downloaded for {username}: {short_url}")
            elif content_type == "image":
                logger.info(f"✅ Images downloaded for {username}: {short_url}")
            else:
                logger.info(f"✅ Content downloaded for {username}: {short_url}")
                
        elif status == "invalid_input":
            # Demoted to info/debug to reduce noise
            logger.info(f"⚠️ Invalid input from {username}: {url[:20]}...")
            
        else:
            # Only ignore known "no video" errors if status is failed
            if "No video could be found" not in url and "Unsupported URL" not in url:
                logger.warning(f"❌ Download failed for {username}: {short_url}")

# For backward compatibility
async def log_user_action(user_id: int, username: str, url: str, status: str, content_type: str = "unknown"):
    await UserManager.log_action(user_id, username, url, status, content_type)

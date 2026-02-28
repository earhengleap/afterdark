"""
User Activity Manager
Handles user logging and history management asynchronously.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import aiofiles

# Configure logging
logger = logging.getLogger("AfterDark.Users")

class UserManager:
    """
    Manages user logs and activity history asynchronously.
    """
    
    USERS_FOLDER = Path("users")
    
    @classmethod
    def ensure_directory(cls):
        """Ensure users directory exists"""
        cls.USERS_FOLDER.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _get_user_file(cls, user_id: int) -> Path:
        """Get path to user's log file"""
        return cls.USERS_FOLDER / f"{user_id}.json"

    @classmethod
    async def load_user_log(cls, user_id: int) -> List[Dict[str, Any]]:
        """
        Load user's history log asynchronously.
        Returns empty list if file doesn't exist or is invalid.
        """
        cls.ensure_directory()
        user_file = cls._get_user_file(user_id)
        
        if not user_file.exists():
            return []
            
        try:
            async with aiofiles.open(user_file, mode='r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content)
        except json.JSONDecodeError:
            logger.error(f"Corrupted log file for user {user_id}")
            return []
        except Exception as e:
            logger.error(f"Error loading log for user {user_id}: {e}")
            return []

    @classmethod
    async def save_user_log(cls, user_id: int, log_data: List[Dict[str, Any]]) -> None:
        """Save user's history log asynchronously"""
        cls.ensure_directory()
        user_file = cls._get_user_file(user_id)
        
        try:
            async with aiofiles.open(user_file, mode='w', encoding='utf-8') as f:
                await f.write(json.dumps(log_data, indent=2, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Error saving log for user {user_id}: {e}")

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
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        log_entry = {
            "username": username,
            "url": url,
            "status": status,
            "content_type": content_type,
            "timestamp": timestamp
        }

        # Load, append, save
        history = await cls.load_user_log(user_id)
        history.append(log_entry)
        
        # Save full history - Never truncate
        await cls.save_user_log(user_id, history)

        
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

# For backward compatibility (optional, but good for transition)
async def log_user_action(user_id: int, username: str, url: str, status: str, content_type: str = "unknown"):
    await UserManager.log_action(user_id, username, url, status, content_type)

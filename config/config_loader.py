import os
import sys
from dataclasses import dataclass
from typing import Optional

@dataclass
class BotConfig:
    bot_token: str
    api_id: int
    api_hash: str
    chat_id: int
    twitter_cookies: Optional[str] = None
    neon_database_url: Optional[str] = None
    uploadthing_token: Optional[str] = None
    uploadthing_app_id: Optional[str] = None
    ffmpeg_path: Optional[str] = None
    bot_username: str = "Vuploads_bot"
    web_app_url: str = "http://localhost:5000"
    notify_usernames: str = ""
    session_string: Optional[str] = None

    @classmethod
    def load(cls) -> 'BotConfig':
        """Load configuration prioritizing config/config.py, then environment variables"""
        
        # Load local config.py if it exists
        local_config = None
        try:
            sys.path.append(os.getcwd())
            import config.config as local_cfg
            local_config = local_cfg
        except ImportError:
            pass

        def get_val(key, default=None):
            if local_config and hasattr(local_config, key):
                return getattr(local_config, key)
            return os.environ.get(key, default)

        # Basic credentials
        bot_token = get_val("BOT_TOKEN", "")
        api_id = int(get_val("API_ID", 0))
        api_hash = get_val("API_HASH", "")
        chat_id = int(get_val("CHAT_ID", 0))

        # Validate critical configs
        missing = []
        if not bot_token: missing.append("BOT_TOKEN")
        if not api_id: missing.append("API_ID")
        if not api_hash: missing.append("API_HASH")
        
        if missing:
            print(f"CRITICAL ERROR: Missing configuration for: {', '.join(missing)}")
            print("Please ensure config/config.py has these values.")
            sys.exit(1)
            
        return cls(
            bot_token=bot_token,
            api_id=api_id,
            api_hash=api_hash,
            chat_id=chat_id,
            twitter_cookies=get_val("TWITTER_COOKIES"),
            neon_database_url=get_val("NEON_DATABASE_URL"),
            uploadthing_token=get_val("UPLOADTHING_TOKEN"),
            uploadthing_app_id=get_val("UPLOADTHING_APP_ID"),
            ffmpeg_path=get_val("FFMPEG_PATH"),
            bot_username=get_val("BOT_USERNAME", "Vuploads_bot"),
            web_app_url=get_val("WEB_APP_URL", "http://localhost:5000"),
            notify_usernames=get_val("NOTIFY_USERNAMES", ""),
            session_string=get_val("SESSION_STRING")
        )

# Create a singleton instance
config_instance = BotConfig.load()

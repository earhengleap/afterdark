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

    @classmethod
    def load(cls) -> 'BotConfig':
        """Load configuration from environment variables or config files"""
        
        # Try importing from local config.py first
        try:
            # We use dynamic import to avoid hard dependency at top level
            sys.path.append(os.getcwd())
            import config.config as local_config
            
            return cls(
                bot_token=getattr(local_config, "BOT_TOKEN", os.environ.get("BOT_TOKEN", "")),
                api_id=int(getattr(local_config, "API_ID", os.environ.get("API_ID", 0))),
                api_hash=getattr(local_config, "API_HASH", os.environ.get("API_HASH", "")),
                chat_id=int(getattr(local_config, "CHAT_ID", os.environ.get("CHAT_ID", 0)))
            )
        except ImportError:
            pass # Fallback to environment variables
            
        except ValueError as e:
            print(f"Error parsing configuration values: {e}")
            sys.exit(1)

        # Fallback to pure environment variables
        bot_token = os.environ.get("BOT_TOKEN", "")
        api_id_str = os.environ.get("API_ID", "0")
        api_hash = os.environ.get("API_HASH", "")
        chat_id_str = os.environ.get("CHAT_ID", "0")
        
        # Validate critical configs
        missing = []
        if not bot_token: missing.append("BOT_TOKEN")
        if not api_id_str or api_id_str == "0": missing.append("API_ID")
        if not api_hash: missing.append("API_HASH")
        
        if missing:
            print(f"CRITICAL ERROR: Missing configuration for: {', '.join(missing)}")
            print("Please ensure config/config.py exists or environment variables are set.")
            sys.exit(1)
            
        return cls(
            bot_token=bot_token,
            api_id=int(api_id_str),
            api_hash=api_hash,
            chat_id=int(chat_id_str)
        )

# Create a singleton instance
config_instance = BotConfig.load()

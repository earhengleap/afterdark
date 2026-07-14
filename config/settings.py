import os
import tempfile
from .config_loader import config_instance

# ==================== BOT CONFIGURATION ====================
BOT_TOKEN = config_instance.bot_token
API_ID = config_instance.api_id
API_HASH = config_instance.api_hash
CHAT_ID = config_instance.chat_id
SESSION_STRING = config_instance.session_string

# ==================== BOT METADATA ====================

BOT_VERSION = "1.1.0"
BOT_NAME = "AfterDark"
VERSION_DATE = "February 2026"

CHANGELOG = {
    "1.1.0": [
        "Enhanced bulk download capabilities",
        "Bulk Content Hub for advanced link processing",
        "Social community integration",
        "Performance optimizations for bulk downloads"
    ],
    "1.0.1": [
        "Enhanced logging system",
        "Robust configuration validation",
        "Graceful shutdown handling",
        "Improved error tracking"
    ],
    "1.0.0": [
        "Initial release",
        "Single video download support",
        "Bulk video download (multiple URLs)",
        "Bulk upload to Telegram groups",
        "Video selection interface with pagination",
        "Upload progress tracking with ETA",
        "Download statistics",
        "Dynamic log sync with video folder",
        "Auto file size detection"
    ]
}

# ==================== COOKIE CONFIGURATION ====================

# Cookie file handling
cookies_content = config_instance.twitter_cookies
if cookies_content:
    tmp_cookies_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix=".txt")
    tmp_cookies_file.write(cookies_content)
    tmp_cookies_file.close()
    COOKIE_FILE = tmp_cookies_file.name
    IMAGES_DIR = 'media/images'
else:
    COOKIE_FILE = 'config/twitter_cookies.txt'

def _resolve_ffmpeg_path() -> str:
    """
    Resolve the ffmpeg binary path.
    Priority:
      1. FFMPEG_PATH from config/config.py
      2. 'ffmpeg' on PATH (Linux / Docker / any OS)
      3. Windows default install location
    """
    import shutil
    # Try config/config.py first
    if config_instance.ffmpeg_path:
        return config_instance.ffmpeg_path
        
    # Check if ffmpeg is on the system PATH
    on_path = shutil.which("ffmpeg")
    if on_path:
        return on_path
        
    # Fallback: Windows default install
    return r"C:\ffmpeg\bin\ffmpeg.exe"


FFMPEG_PATH = _resolve_ffmpeg_path()

# ==================== BOT USERNAME ====================
# Bot username for deep linking (without @)
BOT_USERNAME = config_instance.bot_username

# ==================== WEB APP URL ====================
# Dashboard/webapp URL for tracking
WEB_APP_URL = config_instance.web_app_url


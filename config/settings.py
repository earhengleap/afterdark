import os
import tempfile
from .config_loader import config_instance

# Force user session auth mode so dashboard can read full group history
os.environ["TELEGRAM_GALLERY_AUTH"] = "user"

# ==================== BOT CONFIGURATION ====================
BOT_TOKEN = config_instance.bot_token
API_ID = config_instance.api_id
API_HASH = config_instance.api_hash
CHAT_ID = config_instance.chat_id

# ==================== BOT METADATA ====================

BOT_VERSION = "1.1.0"
BOT_NAME = "X Video Downloader Pro"
VERSION_DATE = "February 2026"

CHANGELOG = {
    "1.1.0": [
        "Premium UI upgrade with dashboard layout",
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
cookies_content = os.environ.get("TWITTER_COOKIES")
if cookies_content:
    tmp_cookies_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix=".txt")
    tmp_cookies_file.write(cookies_content)
    tmp_cookies_file.close()
    COOKIE_FILE = tmp_cookies_file.name
    IMAGES_DIR = 'media/images'
else:
    COOKIE_FILE = 'config/twitter_cookies.txt'

FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"

# ==================== BOT USERNAME ====================
# Bot username for deep linking (without @)
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Vuploads_bot")

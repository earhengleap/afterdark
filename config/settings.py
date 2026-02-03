"""
Configuration settings and constants
"""

import os
import tempfile

# Import from local config.py in the same directory
try:
    from .config import BOT_TOKEN, API_ID, API_HASH, CHAT_ID
except ImportError:
    # Fallback if config.py is not found
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
    API_ID = int(os.environ.get("API_ID", 0))
    API_HASH = os.environ.get("API_HASH", "")
    CHAT_ID = int(os.environ.get("CHAT_ID", 0))

# ==================== BOT METADATA ====================

BOT_VERSION = "1.0.0"
BOT_NAME = "X Video Downloader Bot"
VERSION_DATE = "October 2024"

CHANGELOG = {
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
else:
    COOKIE_FILE = 'config/twitter_cookies.txt'

FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
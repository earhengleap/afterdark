import os

# All credentials are loaded from environment variables/Replit Secrets.
# Never hardcode tokens or keys here — see replit.md for how config is wired up.

# Bot token (from BotFather)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Private group chat ID
CHAT_ID = int(os.environ.get("CHAT_ID", "0") or "0")

# Pyrogram API credentials
API_ID = int(os.environ.get("API_ID", "0") or "0")
API_HASH = os.environ.get("API_HASH", "")

# Telegram User Session String (for the website to read history)
# To get this, you can run a session generator script.
SESSION_STRING = os.environ.get("SESSION_STRING", "")

# Cookie file path
COOKIE_FILE = 'config/twitter_cookies.txt'
FFMPEG_PATH = os.environ.get("FFMPEG_PATH", "")

# Paths
DOWNLOAD_FOLDER = "media/videos"
DATA_FOLDER = "data"
LOG_FILE = "data/download_log.log"
UPLOAD_LOG_FILE = "data/upload_history.log"
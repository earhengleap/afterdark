# twitter_download/x_telegram.py

"""
X Video Downloader Bot - Clean Architecture Implementation
Version: 1.0.0
"""

import os
import time
from datetime import datetime

from pyrogram import Client

# Configuration imports
from config.settings import BOT_TOKEN, API_ID, API_HASH, BOT_VERSION, BOT_NAME, VERSION_DATE
from config.paths import setup_directories

# Core functionality imports
from core.downloader import VideoDownloader
from core.image_downloader import ImageDownloader # ADD THIS IMPORT
from core.uploader import VideoUploader
from core.image_uploader import ImageUploader
from core.file_manager import FileManager
from core.log_manager import LogManager
from core.progress_tracker import ProgressTracker

# Models imports
from models.data_models import VideoInfo, DownloadResult
from models.enums import user_downloads, user_selections, upload_progress

# Utilities imports
from utils.formatters import Formatter
from utils.url_extractor import URLExtractor
from utils.video_processor import VideoProcessor
from utils.upload_logger import UploadLogger

# UI imports
from ui.keyboards import Keyboards
from ui.messages import Messages
from ui.languages import language_manager

# Handler imports
from handlers.command_handlers import setup_command_handlers
from handlers.callback_handlers import setup_callback_handlers

# User management
from users.users import log_user_action

# ==================== PYROGRAM CLIENT ====================

app = Client(
    "x_video_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ==================== SETUP HANDLERS ====================

# Handlers are now setup inside __main__ for cleaner logging

def print_banner():
    """Print a professional banner on startup"""
    width = 60
    border = "━" * width
    print(f"\n\033[1;36m┏{border}┓\033[0m")
    print(f"\033[1;36m┃\033[0m \033[1;33m{BOT_NAME.center(width-2)}\033[0m \033[1;36m┃\033[0m")
    print(f"\033[1;36m┃\033[0m \033[1;32m{'Production Ready • Stable Version'.center(width-2)}\033[0m \033[1;36m┃\033[0m")
    print(f"\033[1;36m┣{border}┫\033[0m")
    print(f"\033[1;36m┃\033[0m \033[1;37m📦 Version: {BOT_VERSION.ljust(width-14)}\033[0m \033[1;36m┃\033[0m")
    print(f"\033[1;36m┃\033[0m \033[1;37m📅 Release: {VERSION_DATE.ljust(width-14)}\033[0m \033[1;36m┃\033[0m")
    print(f"\033[1;36m┃\033[0m \033[1;37m🛡️ System:   {os.name.upper().ljust(width-14)}\033[0m \033[1;36m┃\033[0m")
    print(f"\033[1;36m┃\033[0m \033[1;37m🕒 Startup: {datetime.now().strftime('%Y-%m-%d %H:%M:%S').ljust(width-14)}\033[0m \033[1;36m┃\033[0m")
    print(f"\033[1;36m┗{border}┛\033[0m")

def log_info(message):
    print(f"\033[1;34m[INFO]\033[0m \033[1;37m{datetime.now().strftime('%H:%M:%S')}\033[0m | {message}")

def log_success(message):
    print(f"\033[1;32m[OK]\033[0m   \033[1;37m{datetime.now().strftime('%H:%M:%S')}\033[0m | {message}")

def log_warning(message):
    print(f"\033[1;33m[WARN]\033[0m \033[1;37m{datetime.now().strftime('%H:%M:%S')}\033[0m | {message}")

def log_error(message):
    print(f"\033[1;31m[ERROR]\033[0m\033[1;37m{datetime.now().strftime('%H:%M:%S')}\033[0m | {message}")

if __name__ == "__main__":
    print_banner()
    log_info("Initializing system directories...")
    setup_directories()
    
    log_info("Setting up handlers...")
    setup_command_handlers(app)
    setup_callback_handlers(app)
    
    log_info("Connecting to Telegram API...")
    
    try:
        log_success(f"Bot '{BOT_NAME}' is now LIVE and listening for events")
        app.run()
    except KeyboardInterrupt:
        print("")
        log_warning("Bot stopped by user interrupt")
    except Exception as e:
        log_error(f"Critical system failure: {e}")
    finally:
        log_info("Graceful shutdown sequence complete")
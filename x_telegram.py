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
from core.uploader import VideoUploader
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

# Setup command handlers
setup_command_handlers(app)

# Setup callback handlers  
setup_callback_handlers(app)

# ==================== MAIN ====================

if __name__ == "__main__":
    print("="*50)
    print(f"🤖 {BOT_NAME}")
    print(f"📦 Version: {BOT_VERSION}")
    print(f"📅 Release: {VERSION_DATE}")
    print("="*50)
    print("✅ Bot is starting...")
    print("⏳ Connecting to Telegram...")
    
    try:
        app.run()
    except KeyboardInterrupt:
        print("\n⚠️ Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot crashed: {e}")
    finally:
        print("👋 Bot shutdown complete")
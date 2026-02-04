# x_telegram.py

"""
X Video Downloader Bot - Clean Architecture Implementation
Version: 1.0.1
"""

import os
import time
import sys
import signal
import asyncio
import logging
from datetime import datetime

from pyrogram import Client, idle
from pyrogram.errors import ApiIdInvalid, AuthKeyInvalid

# Configuration imports
from config.settings import BOT_TOKEN, API_ID, API_HASH, BOT_VERSION, BOT_NAME, VERSION_DATE
from config.paths import setup_directories

# Core functionality imports
from core.logger import setup_logger

# Handler imports
from handlers.command_handlers import setup_command_handlers
from handlers.callback_handlers import setup_callback_handlers

# Initialize Logger
logger = setup_logger()

# ==================== PYROGRAM CLIENT ====================

app = Client(
    "x_video_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# ==================== SHUTDOWN HANDLER ====================

async def shutdown(signal_name, loop):
    """Graceful shutdown handler"""
    logger.info(f"Received signal {signal_name}: Initiating graceful shutdown...")
    
    # Perform cleanup tasks here (close DB connections, save buffers, etc.)
    logger.info("Cleaning up resources...")
    
    try:
        await app.stop()
        logger.info("Telegram client stopped successfully")
    except Exception as e:
        logger.warning(f"Error stopping client: {e}")
        
    # Cancel all running tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    
    logger.info(f"Cancelled {len(tasks)} pending tasks")
    logger.info("Goodbye! 👋")
    loop.stop()

def handle_exception(loop, context):
    msg = context.get("exception", context["message"])
    logger.error(f"Unhandled exception: {msg}")

# ==================== MAIN ENTRY POINT ====================

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

async def main():
    print_banner()
    logger.info("Initializing system directories...")
    setup_directories()
    
    logger.info("Setting up handlers...")
    setup_command_handlers(app)
    setup_callback_handlers(app)
    
    logger.info("Connecting to Telegram API...")
    
    try:
        await app.start()
        me = await app.get_me()
        logger.info(f"Bot '{me.first_name}' (@{me.username}) is now LIVE")
        logger.info("Press Ctrl+C to stop")
        
        # Keep the bot running
        await idle()
        
    except (ApiIdInvalid, AuthKeyInvalid):
        logger.critical("Invalid API_ID, API_HASH, or BOT_TOKEN. Please check your configuration.")
    except Exception as e:
        logger.critical(f"Critical system failure: {e}", exc_info=True)
    finally:
        try:
            if app.is_connected:
                await app.stop()
        except:
            pass
        logger.info("Bot execution ended")

if __name__ == "__main__":
    # Setup signal handlers
    loop = asyncio.get_event_loop()
    
    # Windows doesn't support adding signal handlers to the loop easily for SIGINT/SIGTERM in some versions
    # but we can try basic signal handling. 
    # For better cross-platform support, we just rely on KeyboardInterrupt for local dev, 
    # but for production on Linux, add_signal_handler is better.
    
    if os.name != 'nt':
        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(shutdown(s.name, loop)))
    
    loop.set_exception_handler(handle_exception)

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.warning("Bot stopped by user interrupt (KeyboardInterrupt)")
    finally:
        logger.info("System shutdown complete")
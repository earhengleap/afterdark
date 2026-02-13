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
from pyrogram.types import BotCommand
from pyrogram.errors import ApiIdInvalid, AuthKeyInvalid

# Configuration imports
from config.settings import BOT_TOKEN, API_ID, API_HASH, BOT_VERSION, BOT_NAME, VERSION_DATE
from config.paths import setup_directories

# Core functionality imports
from core.logger import setup_logger
from core.metrics import metrics, get_metrics
from core.config_validator import validate_configuration
from core.health_monitor import start_health_monitor, get_health_monitor

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
    """Enhanced graceful shutdown handler with timeout and cleanup"""
    logger.info(f"Received signal {signal_name}: Initiating graceful shutdown...")
    
    # Set shutdown timeout
    shutdown_timeout = 30
    
    try:
        # Stop accepting new requests
        logger.info("Stopping bot client...")
        await asyncio.wait_for(app.stop(), timeout=10)
        logger.info("✓ Telegram client stopped successfully")
    except asyncio.TimeoutError:
        logger.error("⏱️ Timeout while stopping client - forcing shutdown")
    except Exception as e:
        logger.warning(f"⚠️ Error stopping client: {e}")
    
    # Cancel all running tasks gracefully
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if tasks:
        logger.info(f"Cancelling {len(tasks)} pending tasks...")
        
        for task in tasks:
            task.cancel()
        
        # Wait for tasks to complete cancellation
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=10
            )
            logger.info("✓ All tasks cancelled successfully")
        except asyncio.TimeoutError:
            logger.warning("⏱️ Some tasks did not cancel in time")
    
    # Log final metrics
    logger.info("📊 Final metrics:")
    logger.info(f"\n{metrics.get_summary()}")
    
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
    """Main bot entry point with enhanced error handling and monitoring"""
    print_banner()
    
    # Step 1: Validate configuration
    logger.info("Validating configuration...")
    try:
        validate_configuration(raise_on_error=True)
        logger.info("✓ Configuration validated successfully")
    except ValueError as e:
        logger.critical(f"Configuration validation failed: {e}")
        return
    
    # Step 2: Setup directories
    logger.info("Initializing system directories...")
    setup_directories()
    logger.info("✓ Directories initialized")
    
    # Step 3: Setup handlers
    logger.info("Setting up command and callback handlers...")
    setup_command_handlers(app)
    setup_callback_handlers(app)
    logger.info("✓ Handlers configured")
    
    # Step 4: Start bot with retry logic
    logger.info("Connecting to Telegram API...")
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            await app.start()
            me = await app.get_me()
            
            # Set bot commands for autocomplete
            await app.set_bot_commands([
                BotCommand("start", "Start the bot"),
                BotCommand("help", "Get help instructions"),
                BotCommand("stats", "View download statistics"),
                BotCommand("version", "Check bot version"),
                BotCommand("health", "System health status")
            ])
            
            logger.info(f"✅ Bot '{me.first_name}' (@{me.username}) is now LIVE!")
            logger.info(f"🆔 Bot ID: {me.id}")
            logger.info(f"📅 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("⌨️ Press Ctrl+C to stop")
            
            # Step 5: Start health monitoring
            logger.info("Starting health monitor...")
            asyncio.create_task(start_health_monitor(app, interval=300))
            
            # Step 6: Log initial metrics
            logger.info("📊 Metrics tracking enabled")
            
            # Keep the bot running
            await idle()
            break
            
        except (ApiIdInvalid, AuthKeyInvalid) as e:
            logger.critical("❌ Invalid API_ID, API_HASH, or BOT_TOKEN")
            logger.critical("Please check your .env configuration file")
            return
            
        except ConnectionError as e:
            retry_count += 1
            if retry_count < max_retries:
                wait_time = 2 ** retry_count
                logger.warning(
                    f"⚠️ Connection failed (attempt {retry_count}/{max_retries}). "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                logger.critical(f"❌ Failed to connect after {max_retries} attempts")
                return
                
        except Exception as e:
            logger.critical(f"❌ Critical system failure: {e}", exc_info=True)
            metrics.increment_errors("critical_startup_error")
            return
            
    # Cleanup on exit
    try:
        if app.is_connected:
            logger.info("Disconnecting bot...")
            await app.stop()
            logger.info("✓ Bot disconnected")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
    finally:
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
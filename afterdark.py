# afterdark.py

"""
X Video Downloader Bot - Clean Architecture Implementation
Version: 1.0.1
"""

import os
import time
import sys
import signal
import asyncio
import platform
from datetime import datetime

from pyrogram import Client, idle
from pyrogram.types import BotCommand
from pyrogram.errors import ApiIdInvalid, AuthKeyInvalid, FloodWait

# Configuration imports
from config.settings import BOT_TOKEN, API_ID, API_HASH, BOT_VERSION, BOT_NAME, VERSION_DATE, CHAT_ID
from config.paths import setup_directories

# Core functionality imports
from core.logger import setup_logger
from core.metrics import metrics, get_metrics
from core.config_validator import validate_configuration
from core.health_monitor import start_health_monitor, get_health_monitor
from core.database import history_db

# Handler imports
from handlers.command_handlers import setup_command_handlers
from handlers.callback_handlers import setup_callback_handlers
from handlers.media_sync_handler import setup_media_sync_handlers, handle_group_media

# Initialize Logger
logger = setup_logger()

# ==================== SINGLE INSTANCE LOCK ====================

def _get_running_pid() -> int:
    """Get current process PID"""
    return os.getpid()

def _is_process_running(pid: int) -> bool:
    """Check if a process with given PID is running"""
    if os.name == 'nt':
        try:
            import subprocess
            result = subprocess.run(
                ['tasklist', '/FI', f'PID eq {pid}'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return str(pid) in result.stdout
        except:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

def _check_single_instance() -> bool:
    """Ensure only one instance of the bot runs at a time"""
    pid_file = os.path.join(os.getcwd(), "data", "afterdark.pid")
    os.makedirs(os.path.dirname(pid_file), exist_ok=True)
    
    current_pid = _get_running_pid()
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    system_info = platform.system()
    
    # Check for existing PID
    existing_pid = None
    if os.path.exists(pid_file):
        try:
            with open(pid_file, 'r') as f:
                existing_pid = int(f.read().strip())
        except:
            existing_pid = None
    
    # Check if existing process is still running
    if existing_pid and existing_pid != current_pid:
        if _is_process_running(existing_pid):
            logger.error("=" * 60)
            logger.error("  [MULTIPLE INSTANCE DETECTED]")
            logger.error("=" * 60)
            logger.error(f"  Current PID:    {current_pid}")
            logger.error(f"  Running PID:    {existing_pid}")
            logger.error(f"  System:         {system_info}")
            logger.error(f"  Time:            {current_time}")
            logger.info("-" * 60)
            logger.error("  Another instance of AfterDark is already running!")
            logger.error("  Please stop the existing instance first:")
            logger.error(f"     Windows: Taskkill //PID {existing_pid} //F")
            logger.error(f"     Linux:   kill -9 {existing_pid}")
            logger.error("=" * 60)
            return False
        else:
            logger.warning(f"Stale PID file found (PID: {existing_pid}), cleaning up...")
            try:
                os.remove(pid_file)
            except:
                pass
    
    # Acquire lock by writing current PID
    lock_file = os.path.join(os.getcwd(), "data", "afterdark.lock")
    try:
        with open(pid_file, 'w') as f:
            f.write(str(current_pid))
        with open(lock_file, 'w') as f:
            f.write(str(current_pid))
        
        return True
        
    except Exception as e:
        logger.critical("=" * 60)
        logger.critical("  [FAILED TO ACQUIRE LOCK]")
        logger.critical("=" * 60)
        logger.critical(f"  Error: {e}")
        logger.critical("  Please check file permissions")
        logger.critical("=" * 60)
        return False




# ==================== PYROGRAM CLIENT ====================


def _build_bot_client() -> Client:
    # --- Smart Session Logic ---
    # Default to file-based sessions on local/Windows to prevent FloodWait during restarts.
    is_local = os.name == 'nt' or os.getenv("IS_LOCAL", "0") == "1"
    session_in_memory_default = "0" if is_local else "1"
    
    session_name = os.getenv("BOT_SESSION_NAME", "afterdark_bot").strip() or "afterdark_bot"
    session_in_memory = os.getenv("BOT_SESSION_IN_MEMORY", session_in_memory_default).strip().lower() in {"1", "true", "yes", "on"}
    session_workdir = os.getenv("BOT_SESSION_WORKDIR", "data").strip()
    
    if not os.path.exists(session_workdir):
        os.makedirs(session_workdir, exist_ok=True)

    client_kwargs = {
        "api_id": API_ID,
        "api_hash": API_HASH,
        "bot_token": BOT_TOKEN,
        "in_memory": session_in_memory,
        "workdir": session_workdir,
    }

    if session_in_memory:
        logger.info("Using in-memory bot session (BOT_SESSION_IN_MEMORY=1).")
    else:
        logger.info(f"Using file-based bot session '{session_name}' in '{session_workdir}/'.")

    return Client(session_name, **client_kwargs)


app = _build_bot_client()

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
        logger.error("â±ï¸ Timeout while stopping client - forcing shutdown")
    except Exception as e:
        logger.warning(f"âš ï¸ Error stopping client: {e}")
    
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
            logger.warning("â±ï¸ Some tasks did not cancel in time")
    
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
    """Print a professional startup rectangle with runtime metadata."""
    import sys

    if (sys.stdout.encoding or "").lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    width = 84
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pid = os.getpid()
    system = platform.system()
    workdir = os.getcwd()

    def _line(text: str) -> str:
        return f"| {text:<{width - 4}} |"

    try:
        top = "+" + ("=" * (width - 2)) + "+"
        sep = "|" + ("-" * (width - 2)) + "|"
        print(f"\n\033[1;36m{top}\033[0m")
        print(f"\033[1;36m{_line('AfterDark'.center(width - 4))}\033[0m")
        print(f"\033[1;36m{_line('Production Ready - Stable Build'.center(width - 4))}\033[0m")
        print(f"\033[1;36m{sep}\033[0m")
        print(f"\033[1;37m{_line(f'Bot Name : {BOT_NAME}')}\033[0m")
        print(f"\033[1;37m{_line(f'Version  : {BOT_VERSION}')}\033[0m")
        print(f"\033[1;37m{_line(f'Release  : {VERSION_DATE}')}\033[0m")
        print(f"\033[1;37m{_line(f'PID      : {pid}')}\033[0m")
        print(f"\033[1;37m{_line(f'System   : {system}')}\033[0m")
        print(f"\033[1;37m{_line(f'Started  : {now}')}\033[0m")
        print(f"\033[1;37m{_line(f'Workdir  : {workdir}')}\033[0m")
        print(f"\033[1;36m{top}\033[0m")
    except UnicodeEncodeError:
        print("\n+===============================+")
        print("|           AfterDark          |")
        print("|-------------------------------|")
        print(f"| Version : {BOT_VERSION:<20} |")
        print(f"| Started : {now:<20} |")
        print("+===============================+\n")

async def sync_group_history(client: Client):
    """
    Skipped: Bot only handles real-time link processing to avoid method restrictions.
    """
    logger.info("ℹ️ History sync skipped (bot-only mode).")


async def main():
    """Main bot entry point with enhanced error handling and monitoring"""
    print_banner()
    if not _check_single_instance():
        return

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
    setup_media_sync_handlers(app)
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
                BotCommand("videy", "View your Videy CDN links"),
                BotCommand("version", "Check bot version"),
                BotCommand("health", "System health status"),
                BotCommand("cleanup", "View & manage disk storage"),
                BotCommand("chat", "Chat with the AI Assistant"),
                BotCommand("get_following", "Scrape a Twitter user's following list"),
                BotCommand("x_media", "Download media from an X username"),
                BotCommand("redgifs_media", "Download all gifs from a RedGifs username")
            ])
            
            logger.info(f"✅ Bot '{me.first_name}' (@{me.username}) is now LIVE!")
            logger.info(f"🆔 Bot ID: {me.id}")
            logger.info(f"📅 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info("⌨️ Press Ctrl+C to stop")
            
            # Start Group History Sync in background
            asyncio.create_task(sync_group_history(app))

            # Step 5: Start health monitoring
            logger.info("Starting health monitor...")
            asyncio.create_task(start_health_monitor(app, interval=300))

            # Start periodic media auto-cleanup
            from core.media_cleaner import start_auto_cleanup
            asyncio.create_task(start_auto_cleanup())
            logger.info("Auto-cleanup task scheduled")
            
            # Step 6: Log initial metrics
            logger.info("📊 Metrics tracking enabled")
            
            # Keep the bot running
            await idle()
            break
            
        except (ApiIdInvalid, AuthKeyInvalid) as e:
            logger.critical("âŒ Invalid API_ID, API_HASH, or BOT_TOKEN")
            logger.critical("Please check your .env configuration file")
            return
            
        except ConnectionError as e:
            retry_count += 1
            if retry_count < max_retries:
                wait_time = 2 ** retry_count
                logger.warning(
                    f"âš ï¸ Connection failed (attempt {retry_count}/{max_retries}). "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                logger.critical(f"âŒ Failed to connect after {max_retries} attempts")
                return
                
        except FloodWait as e:
            logger.warning(f"⚠️ Telegram FloodWait: Must wait {e.value} seconds before retrying...")
            await asyncio.sleep(e.value)
            continue
        except Exception as e:
            if "database is locked" in str(e).lower():
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count
                    logger.warning(
                        f"Pyrogram session database is locked (attempt {retry_count}/{max_retries}). "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                logger.critical(
                    "Failed to start bot because session database remained locked. "
                    "If another bot instance is running, stop it and retry. "
                    "Tip: keep BOT_SESSION_IN_MEMORY=1 to avoid file lock issues."
                )
                return
            logger.critical(f"Critical system failure: {e}", exc_info=True)
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
    
    def handle_exception(loop, context):
        msg = context.get("exception", context["message"])
        logger.error(f"Caught exception: {msg}")
        
    async def shutdown(signal_name, loop):
        logger.info(f"Received exit signal {signal_name}...")
        try:
            if app.is_connected:
                logger.info("Disconnecting bot...")
                await app.stop()
                logger.info("✓ Bot disconnected")
        except Exception as e:
            logger.error(f"Error during shutdown disconnect: {e}")
        finally:
            _stop_aux_processes()
            
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
        loop.stop()

    if os.name != 'nt':
        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(
                s, lambda s=s: asyncio.create_task(shutdown(s.name, loop)))
    
    loop.set_exception_handler(handle_exception)

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.warning("\nBot stopped by user interrupt (KeyboardInterrupt)")
        # On Windows or when signal handlers don't catch it first, ensure cleanup runs
        try:
            if loop.is_running():
                # If loop is still running, schedule shutdown
                loop.create_task(shutdown("SIGINT", loop))
            else:
                # If loop stopped, run shutdown explicitly
                loop.run_until_complete(shutdown("SIGINT", loop))
        except Exception as e:
            logger.critical(f"Error executing emergency shutdown: {e}")
            _stop_aux_processes()
    finally:
        logger.info("System shutdown complete")




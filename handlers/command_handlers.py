import os
import re
import asyncio
import logging
import time
import json
import urllib.request
import urllib.parse
from pathlib import Path
from pyrogram import Client, filters
from pyrogram.types import Message, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from datetime import datetime

from config.settings import BOT_VERSION, VERSION_DATE, BOT_NAME, BOT_TOKEN
from core.log_manager import LogManager
from core.file_manager import FileManager
from core.metrics import metrics
from utils.url_extractor import URLExtractor
from core.downloader import VideoDownloader
from core.image_downloader import ImageDownloader
from core.database import history_db
from core.uploader import safe_edit_text
from core.videy_uploader import VideyUploader
from core.videy_links import add_videy_link, get_videy_links
from utils.video_processor import VideoProcessor
from utils.videy_formatter import format_videy_message
from handlers.ai_handler import AIHandler
from resources.messages import Messages
from resources.keyboards import Keyboards
from users.users import log_user_action

from core.get_following_service import get_following_list, parse_cookies

# Get logger
logger = logging.getLogger("XVideoBot")

async def get_remote_file_size(url: str) -> float:
    """Get remote file size in MB via HEAD request"""
    try:
        req = urllib.request.Request(url, method='HEAD')
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
        response = await asyncio.to_thread(urllib.request.urlopen, req, timeout=5)
        size_bytes = int(response.headers.get('Content-Length', 0))
        return size_bytes / (1024 * 1024)
    except Exception as e:
        logger.warning(f"Failed to get remote file size for {url}: {e}")
        return 0.0

async def send_direct_video_to_user(video_url: str, message: Message, user_id: int, username: str, app: Client):
    """Send a video directly from a URL to the user without downloading"""
    logger.info(f"Sending direct video from {video_url} to user {user_id}...")
    
    file_name = video_url.split('/')[-1] if '/' in video_url else "video.mp4"
    file_size_mb = await get_remote_file_size(video_url)
    formatted_url = format_url_for_display(video_url)
    if "videy.co" in (video_url or "").lower():
        add_videy_link(user_id, video_url, video_url)
    
    caption = (
        f"🎬 **Direct Download Successful**\n\n"
        f"🔗 **Source:** {formatted_url}\n"
        f"📁 **File:** `{file_name}`\n"
        f"💾 **Estimated Size:** {file_size_mb:.2f} MB\n"
        f"📥 **Requested by:** {username}\n"
        f"🕒 **Time:** {datetime.now().strftime('%H:%M:%S')}\n\n"
        f"✅ X Video Downloader Bot"
    )
    
    status_msg = await message.reply_text(
        f"📤 **Sending video directly...**\n\n"
        f"🔗 `{video_url[:50]}...`\n"
        f"⏳ Telegram is processing the URL, please wait..."
    )
    
    try:
        await app.send_video(
            chat_id=message.chat.id,
            video=video_url,
            supports_streaming=True,
            caption=caption
        )
        
        # Track successful video send
        metrics.increment_videos(1)
        # We estimate bytes for metrics
        metrics.download_completed(success=True, bytes_downloaded=int(file_size_mb * 1024 * 1024))
        
        logger.info(f"Sent direct video to user {user_id}: {file_name}")
        await status_msg.delete()
        
    except Exception as e:
        logger.error(f"Error sending direct video: {e}")
        await safe_edit_text(
            status_msg,
            f"❌ **Error Sending Direct Video**\n\n"
            f"🔗 **URL:** `{video_url}`\n"
            f"⚠️ **Error:** {str(e)[:100]}\n\n"
            f"Telegram server might have rejected the direct link."
        )


def _read_cached_twa_public_url() -> str | None:
    custom_path = os.getenv("TWA_PUBLIC_URL_FILE", "").strip()
    if custom_path:
        target = Path(custom_path).expanduser()
    else:
        target = Path(__file__).resolve().parent.parent / "data" / "twa_public_url.txt"

    try:
        if not target.exists():
            return None
        url = target.read_text(encoding="utf-8", errors="ignore").strip()
    except Exception:
        return None

    if url.startswith("https://"):
        return url.rstrip("/") + "/"
    return None


def _is_twa_public_url_healthy(url: str) -> bool:
    normalized = url.strip().rstrip("/")
    if not normalized.startswith("https://"):
        return False

    health_url = normalized + "/api/health"
    try:
        with urllib.request.urlopen(health_url, timeout=8) as response:
            if response.status != 200:
                return False
            body = json.loads(response.read().decode("utf-8"))
        return bool(body.get("ok"))
    except Exception:
        return False


def _discover_twa_public_url() -> str | None:
    explicit_url = os.getenv("TWA_PUBLIC_URL", "").strip()
    if explicit_url.startswith("https://"):
        if _is_twa_public_url_healthy(explicit_url):
            return explicit_url.rstrip("/") + "/"
        logger.warning(f"Ignoring unhealthy explicit TWA_PUBLIC_URL: {explicit_url[:50]}...")

    cached_url = _read_cached_twa_public_url()
    if cached_url:
        if _is_twa_public_url_healthy(cached_url):
            return cached_url
        logger.warning(f"Ignoring unhealthy cached TWA_PUBLIC_URL: {cached_url[:50]}...")

    return None


def _set_chat_menu_button(chat_id: int, web_app_url: str, text: str = "Open Vault") -> None:
    menu_button = {
        "type": "web_app",
        "text": text,
        "web_app": {"url": web_app_url.rstrip("/") + "/"},
    }
    payload = urllib.parse.urlencode(
        {
            "chat_id": str(chat_id),
            "menu_button": json.dumps(menu_button),
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setChatMenuButton",
        data=payload,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=8) as response:
        body = json.loads(response.read().decode("utf-8"))

    if not body.get("ok"):
        raise RuntimeError(f"setChatMenuButton failed: {body}")


async def _refresh_menu_for_chat(chat_id: int) -> None:
    if not str(chat_id).strip():
        return

    web_app_url = await asyncio.to_thread(_discover_twa_public_url)
    if not web_app_url:
        return

    try:
        await asyncio.to_thread(_set_chat_menu_button, chat_id, web_app_url)
        logger.info(f"Mini App menu refreshed for chat {chat_id}: {web_app_url}")
    except Exception as exc:
        logger.warning(f"Mini App menu refresh failed for chat {chat_id}: {exc}")


def _mini_app_inline_keyboard(web_app_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Open Vault (Mini App)",
                    web_app=WebAppInfo(url=web_app_url.rstrip("/") + "/"),
                )
            ]
        ]
    )

def get_version_info() -> str:
    """Get formatted version information"""
    from config.settings import CHANGELOG
    
    features = CHANGELOG.get(BOT_VERSION, [])
    features_text = "\n".join([f"• {feature}" for feature in features])
    
    return f"""🎬 **{BOT_NAME}**

📦 **Version:** {BOT_VERSION}
📅 **Release Date:** {VERSION_DATE}

**Features in this version:**
{features_text}

━━━━━━━━━━━━━━━━━━━━
*Stable Release • Production Ready*"""

def extract_x_username_and_url(url: str) -> tuple:
    """Extract X/Twitter username and profile URL from post URL"""
    try:
        patterns = [
            r'(?:https?://)?(?:x\.com|twitter\.com)/([a-zA-Z0-9_]+)(?:/status/\d+)?',
            r'(?:https?://)?(?:x\.com|twitter\.com)/([a-zA-Z0-9_]+)/?$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                username = match.group(1)
                profile_url = f"https://x.com/{username}"
                return f"@{username}", profile_url
        
        return "Unknown User", url
    except Exception:
        return "Unknown User", url

def format_url_for_display(url: str) -> str:
    """Format URL in code blocks for easy copying"""
    return f"```\n{url}\n```"

def build_status_callback(status_msg: Message, title: str):
    """Build a throttled async status callback for dynamic progress updates."""
    state = {"last_ts": 0.0, "last_pct": -1, "tick": 0}
    spinner = ["⠋", "⠙", "⠸", "⠴", "⠦", "⠇"]

    async def _callback(percent: int, stage: str):
        now = time.time()
        # Throttle frequent updates to avoid Telegram flood limits.
        if percent < 100 and state["last_pct"] == percent and (now - state["last_ts"]) < 1.0:
            return
        if percent < 100 and (now - state["last_ts"]) < 0.8:
            return
        state["tick"] += 1

        clamped = max(0, min(100, int(percent)))
        filled = int((clamped / 100) * 12)
        bar = ("█" * filled) + ("░" * (12 - filled))
        spin = spinner[state["tick"] % len(spinner)] if clamped < 100 else "✓"
        text = (
            f"{title}\n\n"
            f"🔄 **Status:** {spin} Working...\n"
            f"🧩 **Step:** {stage}\n"
            f"📊 **Progress:** `{bar}` **{clamped}%**\n"
            "⏳ Please wait, your files are being prepared."
        )
        try:
            await status_msg.edit_text(text, disable_web_page_preview=True)
            state["last_ts"] = now
            state["last_pct"] = clamped
        except Exception:
            pass

    return _callback

async def send_videos_to_user(video_paths: list, message: Message, user_id: int, x_username: str, url: str, username: str, app: Client):
    """Send multiple videos to user with proper formatting"""
    from models.enums import user_downloads
    
    total_videos = len(video_paths)
    formatted_url = format_url_for_display(url)
    bulk_videy_links = []
    
    logger.info(f"Sending {total_videos} video(s) to user {user_id}...")
    
    for idx, video_path in enumerate(video_paths, 1):
        try:
            if not os.path.exists(video_path):
                logger.warning(f"Video file not found: {video_path}")
                continue
            
            file_size = os.path.getsize(video_path) / (1024 * 1024)
            file_name = os.path.basename(video_path)
            
            try:
                width, height = VideoProcessor.get_resolution(video_path)
                resolution_text = f"{width}x{height}" if width and height else "Unknown"
            except:
                width, height = 720, 1280
                resolution_text = "Unknown"
            
            # Store video path for upload functionality
            video_key = f"{user_id}_v_{idx}"
            user_downloads[video_key] = video_path
            
            # Create caption based on whether it's multiple videos or single
            if total_videos > 1:
                caption = (
                    f"🎬 **Video {idx}/{total_videos}**\n\n"
                    f"👤 **X User:** {x_username}\n"
                    f"🔗 **Source:** {formatted_url}\n"
                    f"📁 **File:** `{file_name}`\n"
                    f"📏 **Resolution:** {resolution_text}\n"
                    f"💾 **Size:** {file_size:.2f} MB\n"
                    f"📥 **Downloaded by:** {username}\n"
                    f"🕒 **Time:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                    f"✅ X Video Downloader Bot"
                )
            else:
                caption = (
                    f"🎬 **Download Successful**\n\n"
                    f"👤 **X User:** {x_username}\n"
                    f"🔗 **Source:** {formatted_url}\n"
                    f"📁 **File:** `{file_name}`\n"
                    f"📏 **Resolution:** {resolution_text}\n"
                    f"💾 **Size:** {file_size:.2f} MB\n"
                    f"📥 **Downloaded by:** {username}\n"
                    f"🕒 **Time:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                    f"✅ X Video Downloader Bot"
                )
            videy_cdn_url = await VideyUploader.upload_video(video_path)
            if videy_cdn_url:
                add_videy_link(user_id, videy_cdn_url, url)
                if total_videos == 1:
                    caption += f"\n\nCDN: `{videy_cdn_url}`"
                else:
                    bulk_videy_links.append(videy_cdn_url)
                logger.info(f"Videy CDN link created for user {user_id}: {videy_cdn_url}")
            else:
                logger.info(f"Videy CDN link not created for {file_name}")

            # Generate thumbnail for better UX
            from utils.video_processor import VideoProcessor
            thumb_path = await VideoProcessor.generate_thumbnail(video_path)
            
            try:
                sent_msg = await app.send_video(
                    chat_id=message.chat.id,
                    video=video_path,
                    thumb=thumb_path,
                    width=width,
                    height=height,
                    supports_streaming=True,
                    caption=caption,
                    reply_markup=Keyboards.single_video_upload(video_key)
                )
            finally:
                if thumb_path and os.path.exists(thumb_path):
                    try:
                        os.remove(thumb_path)
                    except Exception as e:
                        logger.debug(f"Failed to cleanup thumbnail: {e}")
            
            # Track successful video send
            file_size_bytes = os.path.getsize(video_path)
            metrics.increment_videos(1)
            metrics.download_completed(success=True, bytes_downloaded=file_size_bytes)
            # Start auto-upload timer ONLY for single video
            # For bulk, we'll do it on the summary message
            if total_videos == 1:
                from core.auto_scheduler import AutoScheduler
                await AutoScheduler.start_timer(
                    client=app,
                    message=sent_msg,
                    user_id=user_id,
                    content_type="video_single",
                    content_path=video_path,
                    duration=120
                )
            
            logger.info(f"Sent video {idx}/{total_videos}: {file_name}")
            
        except Exception as e:
            logger.error(f"Error sending video {idx}/{total_videos}: {e}")
            await message.reply_text(
                f"❌ **Error Sending Video {idx}/{total_videos}**\n\n"
                f"📁 **File:** `{os.path.basename(video_path)}`\n"
                f"⚠️ **Error:** {str(e)[:100]}\n\n"
                f"The video was downloaded but couldn't be sent."
            )

    if total_videos > 1 and bulk_videy_links:
        unique_links = list(dict.fromkeys(bulk_videy_links))
        lines = [f"{i}. `{link}`" for i, link in enumerate(unique_links, 1)]
        header = "🔗 **Bulk Videy Links**\n\n"
        max_len = 3800
        current = header

        for line in lines:
            entry = line + "\n"
            if len(current) + len(entry) > max_len:
                await message.reply_text(current, disable_web_page_preview=False)
                current = header + entry
            else:
                current += entry

        if current.strip():
            await message.reply_text(current, disable_web_page_preview=False)

async def process_shared_url(client: Client, message: Message, url: str, user_id: int, username: str):
    """
    Process URL shared via deep link and auto-download content
    
    Args:
        client: Pyrogram client
        message: Message object
        url: The X/Twitter URL to download
        user_id: User ID
        username: Username
    """
    try:
        # Try video download first
        status_msg = await message.reply_text(
            f"📥 **Downloading Video...**\n\n"
            f"🔗 Source: `{url[:50]}...`\n"
            f"⏳ This may take a moment..."
        )
        
        # Extract X Username for caption
        x_username, profile_url = extract_x_username_and_url(url)
        
        video_paths, video_info = await VideoDownloader.download_with_progress(
            url=url,
            status_msg=status_msg,
            index=1,
            total=1,
        )
        
        if video_paths and len(video_paths) > 0:
            # Send videos to user
            await safe_edit_text(status_msg, f"📤 **Sending {len(video_paths)} video(s)...**")
            
            # Use existing send function which handles formatting and buttons
            try:
                await send_videos_to_user(video_paths, message, user_id, x_username, url, username, client)
            except Exception as e:
                logger.error(f"Error sending video: {e}")
                await safe_edit_text(status_msg, f"❌ Error sending video: {str(e)[:100]}")
                return
            
            await status_msg.delete()
            return
        
        # Try image download
        await safe_edit_text(status_msg, "🖼️ **Trying image download...**")
        image_cb = build_status_callback(status_msg, "🖼️ Downloading Images")
        image_paths, image_info = await ImageDownloader.download(
            url,
            message,
            status_callback=image_cb,
            index=1,
            total=1,
        )
        
        if image_paths and len(image_paths) > 0:
            await safe_edit_text(status_msg, f"📤 **Sending {len(image_paths)} image(s)...**")
            
            # Send images as media group
            media_group = [InputMediaPhoto(img) for img in image_paths[:10]]
            await client.send_media_group(message.chat.id, media_group)
            
            await safe_edit_text(
                status_msg,
                f"✅ **Download Complete!**\n\n"
                f"📥 {len(image_paths)} image(s) sent successfully!"
            )
            return
        
        # No content found
        await safe_edit_text(
            status_msg,
            f"❌ **No Media Found**\n\n"
            f"The URL doesn't contain any downloadable videos or images.\n\n"
            f"Please try a different X post."
        )
        
    except Exception as e:
        logger.error(f"Error processing shared URL: {e}")
        await message.reply_text(
            f"❌ **Download Failed**\n\n"
            f"Error: {str(e)[:100]}\n\n"
            f"Please try again or use a different URL."
        )

def setup_command_handlers(app: Client):
    """Setup all command handlers"""
    
    @app.on_message(filters.private & filters.command("start"))
    async def start_handler(client: Client, message: Message) -> None:
        """Handle /start command with deep link support"""
        user_id = message.from_user.id
        user_name = message.from_user.first_name

        # Refresh per-chat Mini App URL to prevent stale tunnel links.
        await _refresh_menu_for_chat(user_id)
        
        # Track metrics
        metrics.increment_commands("start")
        metrics.add_user(user_id)
        
        # Check for deep link parameter
        if len(message.command) > 1:
            param = message.command[1]
            
            # Import deep link helper
            from utils.deep_link import DeepLinkHelper
            
            # Try to decode URL from deep link
            decoded_url = DeepLinkHelper.decode_url(param)
            
            if decoded_url:
                # Check for bulk mode
                from core.database import history_db
                is_bulk_mode = history_db.get_setting(user_id, "bulk_mode", "0") == "1"
                
                if is_bulk_mode:
                    history_db.add_to_queue(user_id, decoded_url)
                    queue_count = history_db.get_queue_count(user_id)
                    
                    await message.reply_text(
                        f"📦 **Added to Bulk Queue**\n\n"
                        f"🔗 Source: `{decoded_url[:50]}...`\n"
                        f"📊 **Queue Size:** {queue_count}\n\n"
                        f"__Link saved for later processing.__",
                        reply_markup=Keyboards.bulk_queue_menu(queue_count, True)
                    )
                    return

                # Auto-download from shared X link
                await message.reply_text(
                    f"🎯 **Auto-Download Started!**\n\n"
                    f"✨ Received from X Share!\n"
                    f"🔗 Processing: `{decoded_url[:50]}...`\n\n"
                    f"⏳ Please wait..."
                )
                
                # Process the URL automatically
                await process_shared_url(client, message, decoded_url, user_id, message.from_user.username or user_name)
                return
        
        # Normal start message
        keyboard = Keyboards.main_menu()
        welcome_text = Messages.welcome(user_name, user_id=user_id)
        version_footer = f"\n\n📦 **Version {BOT_VERSION}** • {VERSION_DATE}"
        await message.reply_text(welcome_text + version_footer, reply_markup=keyboard)

        # Fallback launcher: helps when Telegram still caches an old menu button URL.
        web_app_url = await asyncio.to_thread(_discover_twa_public_url)
        if web_app_url:
            try:
                await message.reply_text(
                    "Open the Mini App directly:",
                    reply_markup=_mini_app_inline_keyboard(web_app_url),
                )
            except Exception as exc:
                logger.warning(f"Mini App direct button send failed for chat {user_id}: {exc}")

    @app.on_message(filters.private & filters.command("help"))
    async def help_handler(client: Client, message: Message) -> None:
        """Handle /help command"""
        metrics.increment_commands("help")
        
        text = Messages.help_text()
        keyboard = Keyboards.back_to_main()
        await message.reply_text(text, reply_markup=keyboard)

    @app.on_message(filters.private & filters.command(["videy", "links"]))
    async def videy_links_handler(client: Client, message: Message) -> None:
        """Handle /videy command - read-only list of user's generated Videy links."""
        user_id = message.from_user.id
        metrics.increment_commands("videy")
        links = get_videy_links(user_id)

        if not links:
            await message.reply_text(
                "🔗 **Videy Links**\n\nNo links found yet.\n\nDownload a video first, then run `/videy`.",
                disable_web_page_preview=False,
            )
            return

        links = list(reversed(links))
        per_page = 10
        page = 1
        total_count = len(links)
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        page_entries = links[:per_page]
        text = format_videy_message(page_entries, page, total_pages, total_count)
        keyboard = Keyboards.videy_pagination(page, total_pages)
        await message.reply_text(text, reply_markup=keyboard, disable_web_page_preview=False)

    @app.on_message(filters.private & filters.command(["stats", "stat"]))
    async def stats_handler(client: Client, message: Message) -> None:
        """Handle /stats command - Enhanced with bot metrics"""
        metrics.increment_commands("stats")
        
        stats_info = LogManager.get_stats()
        log = stats_info['log_data']
        
        sync_status = ""
        if not stats_info['synced']:
            sync_status = f"\n\n⚠️ Log entries: {stats_info['log_entries']} | Folder videos: {stats_info['actual_videos']}"
        
        # Add bot metrics
        bot_metrics = f"\n\n{metrics.get_summary()}"
        
        text = Messages.stats_text(log) + sync_status + bot_metrics
        keyboard = Keyboards.back_to_main()
        await message.reply_text(text, reply_markup=keyboard)

    @app.on_message(filters.private & filters.command(["version", "ver"]))
    async def version_handler(client: Client, message: Message) -> None:
        """Handle /version command"""
        metrics.increment_commands("version")
        
        version_text = get_version_info()
        keyboard = Keyboards.back_to_main()
        await message.reply_text(version_text, reply_markup=keyboard)
    
    @app.on_message(filters.private & filters.command(["health", "status"]))
    async def health_handler(client: Client, message: Message) -> None:
        """Handle /health command - Show bot health and system metrics"""
        metrics.increment_commands("health")
        
        from core.health_monitor import get_health_monitor
        
        # Create health monitor and check health
        health_monitor = get_health_monitor(app)
        health_data = await health_monitor.check_health()
        
        # Get health summary
        summary = health_monitor.get_health_summary()
        
        # Just show health summary without rate limits
        text = summary
        keyboard = Keyboards.back_to_main()
        await message.reply_text(text, reply_markup=keyboard)

    @app.on_message(filters.private & filters.command("get_following"))
    async def get_following_handler(client: Client, message: Message) -> None:
        """Handle /get_following command"""
        if len(message.command) < 2:
            await message.reply_text("⚠️ Please provide a username. Usage: `/get_following elonmusk`")
            return
            
        username = message.command[1].strip().replace("@", "")
        
        cookies_file = "config/twitter_cookies.txt"
        if not os.path.exists(cookies_file):
            await message.reply_text("❌ System error: Cookie file missing. Cannot authenticate with Twitter.")
            return

        status_msg = await message.reply_text(f"🔍 **Starting scrape for @{username}...**\n\n⏳ Initializing...")
        
        try:
            cookies = parse_cookies(cookies_file)
            if not cookies.get('auth_token') or not cookies.get('ct0'):
                await status_msg.edit_text("❌ Authentication Error: Cookies are invalid or expired.")
                return

            def update_progress(msg: str):
                # Only update occasionally to avoid flood wait, or just log it
                # We'll rely on the background thread printing to console for detailed logs
                pass

            # Run synchronous scraping in a thread pool
            following_list = await asyncio.to_thread(
                get_following_list, 
                username, 
                cookies, 
                True, # resume mode
                update_progress
            )
            
            if following_list is None:
                await status_msg.edit_text(f"❌ Failed to get following list for @{username}. They might be suspended, private, or the cookies are expired.")
                return
                
            await status_msg.edit_text(f"✅ Scraping completed for @{username}. Found {len(following_list)} users. Preparing files...")

            txt_file = f"{username}_following.txt"
            json_file = f"{username}_following.json"
            
            # Send the files to the user
            docs_to_send = []
            if os.path.exists(txt_file):
                docs_to_send.append(txt_file)
            if os.path.exists(json_file):
                docs_to_send.append(json_file)
                
            for doc in docs_to_send:
                await message.reply_document(document=doc, caption=f"📑 Result for @{username}")
                # Optional: Delete the file after sending
                # try:
                #    os.remove(doc)
                # except Exception:
                #    pass
                
            # Clear state file if it exists
            state_file = f"{username}_state.json"
            if os.path.exists(state_file):
                try:
                    os.remove(state_file)
                except:
                    pass
                
        except Exception as e:
            logger.error(f"Scrape error: {e}")
            await status_msg.edit_text(f"❌ An error occurred during scraping: {str(e)[:100]}")

    @app.on_message(filters.command(["chat", "ai", "ask"]) & filters.private)
    async def chat_handler(client: Client, message: Message) -> None:
        """Handle explicit AI chat commands"""
        # Remove the command part (e.g. "/chat ")
        text = message.text.split(" ", 1)
        if len(text) < 2 or not text[1].strip():
            await message.reply_text("Please provide a message. Example: `/chat What can you do?`")
            return
            
        user_prompt = text[1].strip()
        await AIHandler.process_chat(client, message, user_prompt)

    @app.on_message(filters.private & filters.text)
    async def text_handler(client: Client, message: Message) -> None:
        """Handle text messages (URLs) - NOW SUPPORTS MULTIPLE VIDEOS PER URL"""
        text = message.text.strip()
        username = message.from_user.username or message.from_user.first_name
        user_id = message.from_user.id
        
        # Track user
        metrics.add_user(user_id)
        metrics.increment_commands("download_request")

        urls = URLExtractor.extract(text)
        
        if not urls:
            # If there are no URLs, assume the user is trying to chat with the AI natively
            await AIHandler.process_chat(client, message, text)
            return
            
        # Check for Bulk Mode (Global Setting)
        from core.database import history_db
        is_bulk_mode = history_db.get_setting(user_id, "bulk_mode", "0") == "1"
        
        if is_bulk_mode:
            # Add all extracted URLs to queue
            for url in urls:
                history_db.add_to_queue(user_id, url)
                
            queue_count = history_db.get_queue_count(user_id)
            
            await message.reply_text(
                f"📦 **Added to Bulk Queue**\n\n"
                f"📊 **Added:** {len(urls)} links\n"
                f"🔢 **Total in Queue:** {queue_count}\n\n"
                f"__Links saved. Use /bulk_queue or menu to process.__",
                reply_markup=Keyboards.bulk_queue_menu(queue_count, True)
            )
            return
        
        # Bulk download (multiple URLs in one message)
        if len(urls) > 1:
            # Track download attempt
            metrics.increment_downloads()
            
            detection_msg = await message.reply_text(
                f"🔍 **Bulk URL Detection**\n\n"
                f"📊 **Detected {len(urls)} URLs**\n"
                f"👤 **Requested by:** {username}\n"
                f"🕒 **Time:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"⏳ Starting bulk download process..."
            )
            
            await VideoDownloader.download_multiple(urls, message, user_id, detection_msg)
            return
        
        # Single URL download - NOW HANDLES MULTIPLE VIDEOS FROM ONE URL
        url = urls[0]
        x_username, profile_url = extract_x_username_and_url(url)
        formatted_url = format_url_for_display(url)
        
        # Create clickable username link
        if x_username != "Unknown User":
            clickable_username = f"[{x_username}]({profile_url})"
        else:
            clickable_username = "Unknown User"
        
        # Initial analysis message
        status_msg = await message.reply_text(
            f"🔍 **URL Analysis Started**\n\n"
            f"👤 **X User:** {clickable_username}\n"
            f"🔗 **URL:** {formatted_url}\n"
            f"📥 **Requested by:** {username}\n"
            f"🕒 **Start Time:** {datetime.now().strftime('%H:%M:%S')}\n"
            f"📅 **Date:** {datetime.now().strftime('%Y-%m-%d')}\n\n"
            f"⏳ Analyzing content type...",
            disable_web_page_preview=False
        )
        
        # Check user intent
        user_intent = "auto"
        if hasattr(message, 'reply_to_message') and message.reply_to_message:
            reply_text = message.reply_to_message.text or ""
            if "Download Video" in reply_text:
                user_intent = "video"
            elif "Download Images" in reply_text:
                user_intent = "images"
        
        if "x.com" in url or "twitter.com" in url:
            if user_intent == "video" or user_intent == "auto":
                # Check for cdn.videy.co links in tweet text first
                videy_url = URLExtractor.get_videy_link_from_x_tweet(url)
                
                download_url = url
                video_source = "X"
                source_check_msg = ""
                
                if videy_url:
                    download_url = videy_url
                    video_source = "Videy (cDNA)"
                    source_check_msg = f"\n🔗 **Videy Link:** Found in tweet caption"
                    logger.info(f"Found videy link in tweet: {videy_url}")
                
                # Try video download first (supports multiple videos)
                await safe_edit_text(
                    status_msg,
                    f"🎬 **Video Download Started**\n\n"
                    f"👤 **X User:** {clickable_username}\n"
                    f"🔗 **URL:** {formatted_url}\n"
                    f"📥 **Requested by:** {username}\n"
                    f"🕒 **Time:** {datetime.now().strftime('%H:%M:%S')}\n"
                    f"{source_check_msg}\n\n"
                    f"⏳ Checking for video content...",
                    disable_web_page_preview=False
                )
                
                # FIXED: download() now returns a LIST of video paths
                video_paths, video_info = await VideoDownloader.download_with_progress(
                    url=download_url,
                    status_msg=status_msg,
                    index=1,
                    total=1,
                )
                
                # FIXED: Check if video_paths is a list and has items
                if video_paths and isinstance(video_paths, list) and len(video_paths) > 0:
                    # Video download successful - HANDLE MULTIPLE VIDEOS
                    total_videos = len(video_paths)
                    total_size = sum(os.path.getsize(vp) for vp in video_paths if os.path.exists(vp)) / (1024 * 1024)
                    
                    source_note = f"\n📍 **Source:** {video_source}" if video_source != "X" else ""
                    
                    await safe_edit_text(
                        status_msg,
                        f"✅ **Video Download Complete**\n\n"
                        f"👤 **X User:** {clickable_username}\n"
                        f"🔗 **URL:** {formatted_url}\n"
                        f"🎬 **Videos Found:** {total_videos}\n"
                        f"💾 **Total Size:** {total_size:.2f} MB\n"
                        f"📥 **Downloaded by:** {username}\n"
                        f"🕒 **Completed:** {datetime.now().strftime('%H:%M:%S')}\n"
                        f"{source_note}\n\n"
                        f"📤 Sending {total_videos} video(s) to you...",
                        disable_web_page_preview=False
                    )
                    
                    await status_msg.delete()
                    
                    # Send all videos
                    await send_videos_to_user(video_paths, message, user_id, x_username, url, username, app)
                    
                    # Send summary message after all videos (if multiple)
                    if total_videos > 1:
                        from models.enums import user_downloads
                        user_downloads[f"{user_id}_bulk_videos"] = video_paths
                        
                        summary_msg = await message.reply_text(
                            f"✅ **All Videos Sent Successfully**\n\n"
                            f"👤 **X User:** {clickable_username}\n"
                            f"🔗 **Source:** {formatted_url}\n"
                            f"🎬 **Total Videos:** {total_videos}\n"
                            f"💾 **Total Size:** {total_size:.2f} MB\n"
                            f"📥 **Downloaded by:** {username}\n\n"
                            f"What would you like to do next?",
                            reply_markup=Keyboards.bulk_download_complete_mixed(user_id, video_paths, []),
                            disable_web_page_preview=False
                        )
                        
                        from core.auto_scheduler import AutoScheduler
                        await AutoScheduler.start_timer(
                            client=app,
                            message=summary_msg,
                            user_id=user_id,
                            content_type="video_bulk",
                            content_path=video_paths,
                            duration=120
                        )
                    
                    source_info = f" (via {video_source})" if video_source != "X" else ""
                    await log_user_action(user_id, username, url, "success", f"video({total_videos}){source_info}")
                    logger.info(f"Successfully sent {total_videos} video(s) from: {url}{source_info}")
                    
                elif user_intent == "auto":
                    # Video not found, try images (only in auto mode)
                    await safe_edit_text(
                        status_msg,
                        f"🖼️ **No Video Found - Checking Images**\n\n"
                        f"👤 **X User:** {clickable_username}\n"
                        f"🔗 **URL:** {formatted_url}\n"
                        f"📥 **Requested by:** {username}\n"
                        f"⚠️ **Status:** No video content found\n"
                        f"🕒 **Time:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"⏳ Searching for images...",
                        disable_web_page_preview=False
                    )
                    image_cb = build_status_callback(status_msg, "🖼️ Downloading Images")
                    image_paths, image_info = await ImageDownloader.download(
                        url,
                        message,
                        status_callback=image_cb,
                        index=1,
                        total=1,
                    )
                    
                    if image_paths and len(image_paths) > 0:
                        # Image download successful
                        try:
                            from models.enums import user_downloads
                            user_downloads[user_id] = image_paths
                            
                            total_size = sum(os.path.getsize(img) for img in image_paths) / (1024 * 1024)
                            
                            await safe_edit_text(
                                status_msg,
                                f"✅ **Images Download Complete**\n\n"
                                f"👤 **X User:** {clickable_username}\n"
                                f"🔗 **URL:** {formatted_url}\n"
                                f"🖼️ **Total Images:** {len(image_paths)}\n"
                                f"💾 **Total Size:** {total_size:.2f} MB\n"
                                f"📥 **Downloaded by:** {username}\n"
                                f"🕒 **Completed:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                                f"📤 Sending images to you...",
                                disable_web_page_preview=False
                            )
                            
                            await status_msg.delete()
                            
                            # Send images in groups of 10
                            await ImageDownloader.send_images_to_user(image_paths, message, user_id)
                            
                            try:
                                sent_msg = await message.reply_text(
                                    f"✅ **Images Download Successful**\n\n"
                                    f"👤 **X User:** {clickable_username}\n"
                                    f"🔗 **Source:** {formatted_url}\n"
                                    f"🖼️ **Images Found:** {len(image_paths)}\n"
                                    f"💾 **Total Size:** {total_size:.2f} MB\n"
                                    f"📥 **Downloaded by:** {username}\n\n"
                                    f"What would you like to do next?",
                                    reply_markup=Keyboards.image_actions_with_upload(user_id),
                                    disable_web_page_preview=False
                                )
                                from core.auto_scheduler import AutoScheduler
                                await AutoScheduler.start_timer(
                                    client=app,
                                    message=sent_msg,
                                    user_id=user_id,
                                    content_type="image_bulk",
                                    content_path=image_paths,
                                    duration=120
                                )
                                await log_user_action(user_id, username, url, "success", "image")
                                logger.info(f"Image download successful for {url} - Sent {len(image_paths)} images")
                            except Exception as e:
                                logger.error(f"Error post-image download menu: {e}")
                                
                        except Exception as e:
                            logger.error(f"Error handling images: {e}")
                            await message.reply_text("❌ An error occurred while processing the images.")
                    else:
                        # Nothing found
                        await safe_edit_text(
                            status_msg,
                            f"❌ **No Media Found**\n\n"
                            f"👤 **X User:** {clickable_username}\n"
                            f"🔗 **URL:** {formatted_url}\n"
                            f"📥 **Requested by:** {username}\n\n"
                            f"The URL doesn't contain any downloadable videos or images.\n\n"
                            f"Please make sure the content is not private restricted or a text-only post.",
                            disable_web_page_preview=False
                        )
                        await log_user_action(user_id, username, url, "failed", "no_media")
            elif user_intent == "images":
                # User explicitly requested images only
                await safe_edit_text(
                    status_msg,
                    f"🖼️ **Image Download Started**\n\n"
                    f"👤 **X User:** {clickable_username}\n"
                    f"🔗 **URL:** {formatted_url}\n"
                    f"📥 **Requested by:** {username}\n"
                    f"🕒 **Time:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                    f"⏳ Searching for images...",
                    disable_web_page_preview=False
                )
                image_cb = build_status_callback(status_msg, "🖼️ Downloading Images")
                image_paths, image_info = await ImageDownloader.download(
                    url,
                    message,
                    status_callback=image_cb,
                    index=1,
                    total=1,
                )
                
                if image_paths and len(image_paths) > 0:
                    try:
                        from models.enums import user_downloads
                        user_downloads[user_id] = image_paths
                        
                        total_size = sum(os.path.getsize(img) for img in image_paths) / (1024 * 1024)
                        
                        await safe_edit_text(
                            status_msg,
                            f"✅ **Images Download Complete**\n\n"
                            f"👤 **X User:** {clickable_username}\n"
                            f"🔗 **URL:** {formatted_url}\n"
                            f"🖼️ **Total Images:** {len(image_paths)}\n"
                            f"💾 **Total Size:** {total_size:.2f} MB\n"
                            f"📥 **Downloaded by:** {username}\n"
                            f"🕒 **Completed:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                            f"📤 Sending images to you...",
                            disable_web_page_preview=False
                        )
                        
                        await status_msg.delete()
                        
                        # Send images in groups of 10
                        await ImageDownloader.send_images_to_user(image_paths, message, user_id)
                        
                        try:
                            sent_msg = await message.reply_text(
                                f"✅ **Images Download Successful**\n\n"
                                f"👤 **X User:** {clickable_username}\n"
                                f"🔗 **Source:** {formatted_url}\n"
                                f"🖼️ **Images Found:** {len(image_paths)}\n"
                                f"💾 **Total Size:** {total_size:.2f} MB\n"
                                f"📥 **Downloaded by:** {username}\n\n"
                                f"What would you like to do next?",
                                reply_markup=Keyboards.image_actions_with_upload(user_id),
                                disable_web_page_preview=False
                            )
                            from core.auto_scheduler import AutoScheduler
                            await AutoScheduler.start_timer(
                                client=app,
                                message=sent_msg,
                                user_id=user_id,
                                content_type="image_bulk",
                                content_path=image_paths,
                                duration=120
                            )
                            await log_user_action(user_id, username, url, "success", "image")
                        except Exception as e:
                            logger.error(f"Error post-image download menu: {e}")
                    except Exception as e:
                        logger.error(f"Error handling images: {e}")
                        await message.reply_text("❌ An error occurred while processing the images.")
                else:
                    await safe_edit_text(
                        status_msg,
                        f"❌ **No Images Found**\n\n"
                        f"👤 **X User:** {clickable_username}\n"
                        f"🔗 **URL:** {formatted_url}\n"
                        f"📥 **Requested by:** {username}\n\n"
                        f"Could not find any downloadable images in this post.",
                        disable_web_page_preview=False
                    )
                    await log_user_action(user_id, username, url, "failed", "no_images")
        elif "videy.co" in url:
            # Direct video download bypass
            await status_msg.delete()
            await send_direct_video_to_user(url, message, user_id, username, app)
            await log_user_action(user_id, username, url, "success", "direct_video")
        
        elif user_intent == "images":
            # User explicitly wants images
            await safe_edit_text(
                status_msg,
                f"🖼️ **Image Download Requested**\n\n"
                f"👤 **X User:** {clickable_username}\n"
                f"🔗 **URL:** {formatted_url}\n"
                f"📥 **Requested by:** {username}\n"
                f"🕒 **Time:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"⏳ Checking for image content...",
                disable_web_page_preview=False
            )
            image_cb = build_status_callback(status_msg, "🖼️ Downloading Images")
            image_paths, image_info = await ImageDownloader.download(
                url,
                message,
                status_callback=image_cb,
                index=1,
                total=1,
            )
            
            if image_paths and len(image_paths) > 0:
                try:
                    from models.enums import user_downloads
                    user_downloads[user_id] = image_paths
                    
                    total_size = sum(os.path.getsize(img) for img in image_paths) / (1024 * 1024)
                    
                    await safe_edit_text(
                        status_msg,
                        f"✅ **Images Download Complete**\n\n"
                        f"👤 **X User:** {clickable_username}\n"
                        f"🔗 **URL:** {formatted_url}\n"
                        f"🖼️ **Total Images:** {len(image_paths)}\n"
                        f"💾 **Total Size:** {total_size:.2f} MB\n"
                        f"📥 **Downloaded by:** {username}\n"
                        f"🕒 **Completed:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"📤 Sending images to you...",
                        disable_web_page_preview=False
                    )
                    
                    await status_msg.delete()
                    
                    # Send images individually to avoid Pyrogram media group bug
                    for img_path in image_paths:
                        try:
                            if os.path.exists(img_path):
                                await app.send_photo(chat_id=message.chat.id, photo=img_path)
                                await asyncio.sleep(0.5)
                        except Exception as e:
                            logger.error(f"Error sending image: {e}")
                    
                    try:
                        sent_msg = await message.reply_text(
                            f"✅ **Images Download Successful**\n\n"
                            f"👤 **X User:** {clickable_username}\n"
                            f"🔗 **Source:** {formatted_url}\n"
                            f"🖼️ **Images Found:** {len(image_paths)}\n"
                            f"💾 **Total Size:** {total_size:.2f} MB\n"
                            f"📥 **Downloaded by:** {username}\n\n"
                            f"What would you like to do next?",
                            reply_markup=Keyboards.image_actions_with_upload(user_id),
                            disable_web_page_preview=False
                        )
                        from core.auto_scheduler import AutoScheduler
                        await AutoScheduler.start_timer(
                            client=app,
                            message=sent_msg,
                            user_id=user_id,
                            content_type="image_bulk",
                            content_path=image_paths,
                            duration=120
                        )
                        await log_user_action(user_id, username, url, "success", "image")
                    except Exception as e:
                        logger.error(f"Error sending confirmation message: {e}")
                    
                except Exception as e:
                    try:
                        await safe_edit_text(
                            status_msg,
                            f"❌ **Image Send Failed**\n\n"
                            f"⚠️ **Error:** {str(e)[:100]}",
                            disable_web_page_preview=False
                        )
                    except:
                        pass
                    await log_user_action(user_id, username, url, "failed", "image")
            else:
                # Try video as fallback
                await safe_edit_text(
                    status_msg,
                    f"🎬 **No Images Found - Checking Video**\n\n"
                    f"👤 **X User:** {clickable_username}\n"
                    f"🔗 **URL:** {formatted_url}\n\n"
                    f"⏳ Searching for video...",
                    disable_web_page_preview=False
                )
                video_paths, video_info = await VideoDownloader.download_with_progress(
                    url=url,
                    status_msg=status_msg,
                    index=1,
                    total=1,
                )
                
                if video_paths and isinstance(video_paths, list) and len(video_paths) > 0:
                    total_videos = len(video_paths)
                    total_size = sum(os.path.getsize(vp) for vp in video_paths if os.path.exists(vp)) / (1024 * 1024)
                    
                    await safe_edit_text(
                        status_msg,
                        f"✅ **Video Found Instead**\n\n"
                        f"🎬 **Videos:** {total_videos}\n"
                        f"💾 **Size:** {total_size:.2f} MB\n\n"
                        f"📤 Sending video(s)...",
                        disable_web_page_preview=False
                    )
                    
                    await status_msg.delete()
                    await send_videos_to_user(video_paths, message, user_id, x_username, url, username, app)
                    await log_user_action(user_id, username, url, "success", "video")
                else:
                    await safe_edit_text(
                        status_msg,
                        f"❌ **No Media Found**\n\n"
                        f"⚠️ No images or videos found at this URL.",
                        disable_web_page_preview=False
                    )
                    await log_user_action(user_id, username, url, "failed", "unknown")
        else:
            # Non-X/Twitter URL
            await safe_edit_text(
                status_msg,
                f"🎬 **Video Download Started**\n\n"
                f"🔗 **URL:** {formatted_url}\n"
                f"📥 **Requested by:** {username}\n"
                f"⏳ Processing...",
                disable_web_page_preview=False
            )
            
            video_paths, video_info = await VideoDownloader.download_with_progress(
                url=url,
                status_msg=status_msg,
                index=1,
                total=1,
            )
            
            if video_paths and isinstance(video_paths, list) and len(video_paths) > 0:
                await status_msg.delete()
                await send_videos_to_user(video_paths, message, user_id, x_username, url, username, app)
                await log_user_action(user_id, username, url, "success", "video")
            else:
                await safe_edit_text(
                    status_msg,
                    f"❌ **Download Failed**\n\n"
                    f"🔗 **URL:** {formatted_url}\n"
                    f"⚠️ Could not download video from this URL.",
                    disable_web_page_preview=False
                )
                await log_user_action(user_id, username, url, "failed", "unknown")




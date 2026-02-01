"""
Command handlers for the bot - FIXED TO SUPPORT MULTIPLE VIDEOS PER URL
"""
import os
import re
from pyrogram import Client, filters
from pyrogram.types import Message, InputMediaPhoto
from datetime import datetime

from config.settings import BOT_VERSION, VERSION_DATE, BOT_NAME
from core.log_manager import LogManager
from core.file_manager import FileManager
from utils.url_extractor import URLExtractor
from core.downloader import VideoDownloader
from core.image_downloader import ImageDownloader
from utils.video_processor import VideoProcessor
from ui.messages import Messages
from ui.keyboards import Keyboards
from users.users import log_user_action

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

async def send_videos_to_user(video_paths: list, message: Message, user_id: int, x_username: str, url: str, username: str, app: Client):
    """Send multiple videos to user with proper formatting"""
    from models.enums import user_downloads
    
    total_videos = len(video_paths)
    formatted_url = format_url_for_display(url)
    
    print(f"📤 Sending {total_videos} video(s) to user...")
    
    for idx, video_path in enumerate(video_paths, 1):
        try:
            if not os.path.exists(video_path):
                print(f"⚠️ Video file not found: {video_path}")
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
            
            await app.send_video(
                chat_id=message.chat.id,
                video=video_path,
                width=width,
                height=height,
                supports_streaming=True,
                caption=caption,
                reply_markup=Keyboards.single_video_upload(video_key)
            )
            
            print(f"✅ Sent video {idx}/{total_videos}: {file_name}")
            
        except Exception as e:
            print(f"❌ Error sending video {idx}/{total_videos}: {e}")
            await message.reply_text(
                f"❌ **Error Sending Video {idx}/{total_videos}**\n\n"
                f"📁 **File:** `{os.path.basename(video_path)}`\n"
                f"⚠️ **Error:** {str(e)[:100]}\n\n"
                f"The video was downloaded but couldn't be sent."
            )

def setup_command_handlers(app: Client):
    """Setup all command handlers"""
    
    @app.on_message(filters.private & filters.command("start"))
    async def start_handler(client: Client, message: Message) -> None:
        """Handle /start command"""
        user_name = message.from_user.first_name
        keyboard = Keyboards.main_menu()
        welcome_text = Messages.welcome(user_name)
        version_footer = f"\n\n📦 **Version {BOT_VERSION}** • {VERSION_DATE}"
        await message.reply_text(welcome_text + version_footer, reply_markup=keyboard)

    @app.on_message(filters.private & filters.command("help"))
    async def help_handler(client: Client, message: Message) -> None:
        """Handle /help command"""
        text = Messages.help_text()
        keyboard = Keyboards.back_to_main()
        await message.reply_text(text, reply_markup=keyboard)

    @app.on_message(filters.private & filters.command("stats"))
    async def stats_handler(client: Client, message: Message) -> None:
        """Handle /stats command"""
        stats_info = LogManager.get_stats()
        log = stats_info['log_data']
        
        sync_status = ""
        if not stats_info['synced']:
            sync_status = f"\n\n⚠️ Log entries: {stats_info['log_entries']} | Folder videos: {stats_info['actual_videos']}"
        
        text = Messages.stats_text(log) + sync_status
        keyboard = Keyboards.back_to_main()
        await message.reply_text(text, reply_markup=keyboard)

    @app.on_message(filters.private & filters.command("version"))
    async def version_handler(client: Client, message: Message) -> None:
        """Handle /version command"""
        version_text = get_version_info()
        keyboard = Keyboards.back_to_main()
        await message.reply_text(version_text, reply_markup=keyboard)

    @app.on_message(filters.private & filters.text)
    async def text_handler(client: Client, message: Message) -> None:
        """Handle text messages (URLs) - NOW SUPPORTS MULTIPLE VIDEOS PER URL"""
        text = message.text.strip()
        username = message.from_user.username or message.from_user.first_name
        user_id = message.from_user.id

        urls = URLExtractor.extract(text)
        
        if not urls:
            await message.reply_text(
                "❌ Please send valid URL(s).\n\n"
                "You can send:\n"
                "• Single URL\n"
                "• Multiple URLs separated by spaces, pipes (|), or newlines\n\n"
                "Or use the menu buttons for specific actions."
            )
            log_user_action(user_id, username, text, "failed", "unknown")
            return
        
        # Bulk download (multiple URLs)
        if len(urls) > 1:
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
                # Try video download first (supports multiple videos)
                await status_msg.edit_text(
                    f"🎬 **Video Download Started**\n\n"
                    f"👤 **X User:** {clickable_username}\n"
                    f"🔗 **URL:** {formatted_url}\n"
                    f"📥 **Requested by:** {username}\n"
                    f"🕒 **Time:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                    f"⏳ Checking for video content...",
                    disable_web_page_preview=False
                )
                
                # FIXED: download() now returns a LIST of video paths
                video_paths, video_info = VideoDownloader.download(url, message)
                
                # FIXED: Check if video_paths is a list and has items
                if video_paths and isinstance(video_paths, list) and len(video_paths) > 0:
                    # Video download successful - HANDLE MULTIPLE VIDEOS
                    total_videos = len(video_paths)
                    total_size = sum(os.path.getsize(vp) for vp in video_paths if os.path.exists(vp)) / (1024 * 1024)
                    
                    await status_msg.edit_text(
                        f"✅ **Video Download Complete**\n\n"
                        f"👤 **X User:** {clickable_username}\n"
                        f"🔗 **URL:** {formatted_url}\n"
                        f"🎬 **Videos Found:** {total_videos}\n"
                        f"💾 **Total Size:** {total_size:.2f} MB\n"
                        f"📥 **Downloaded by:** {username}\n"
                        f"🕒 **Completed:** {datetime.now().strftime('%H:%M:%S')}\n\n"
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
                        
                        await message.reply_text(
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
                    
                    log_user_action(user_id, username, url, "success", f"video({total_videos})")
                    print(f"✅ Successfully sent {total_videos} video(s) from: {url}")
                    
                elif user_intent == "auto":
                    # Video not found, try images (only in auto mode)
                    await status_msg.edit_text(
                        f"🖼️ **No Video Found - Checking Images**\n\n"
                        f"👤 **X User:** {clickable_username}\n"
                        f"🔗 **URL:** {formatted_url}\n"
                        f"📥 **Requested by:** {username}\n"
                        f"⚠️ **Status:** No video content found\n"
                        f"🕒 **Time:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"⏳ Searching for images...",
                        disable_web_page_preview=False
                    )
                    image_paths, image_info = await ImageDownloader.download(url, message)
                    
                    if image_paths and len(image_paths) > 0:
                        # Image download successful
                        try:
                            from models.enums import user_downloads
                            user_downloads[user_id] = image_paths
                            
                            total_size = sum(os.path.getsize(img) for img in image_paths) / (1024 * 1024)
                            
                            await status_msg.edit_text(
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
                                        await asyncio.sleep(0.5) # Avoid flood wait
                                except Exception as e:
                                    print(f"❌ Error sending image: {e}")
                            
                            try:
                                await message.reply_text(
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
                                log_user_action(user_id, username, url, "success", "image")
                                print(f"✅ Image download successful for {url} - Sent {len(image_paths)} images")
                            except Exception as e:
                                print(f"❌ Error sending confirmation message: {e}")
                            
                        except Exception as e:
                            print(f"❌ Error sending images: {e}")
                            try:
                                await status_msg.edit_text(
                                    f"❌ **Image Send Failed**\n\n"
                                    f"👤 **X User:** {clickable_username}\n"
                                    f"🔗 **URL:** {formatted_url}\n"
                                    f"🖼️ **Images Downloaded:** {len(image_paths)}\n"
                                    f"⚠️ **Error:** {str(e)[:100]}\n\n"
                                    f"Images downloaded but couldn't be sent.",
                                    disable_web_page_preview=False
                                )
                            except:
                                pass
                            log_user_action(user_id, username, url, "failed", "image")
                    else:
                        # Both video and image failed
                        await status_msg.edit_text(
                            f"❌ **Download Failed**\n\n"
                            f"👤 **X User:** {clickable_username}\n"
                            f"🔗 **URL:** {formatted_url}\n"
                            f"📥 **Requested by:** {username}\n"
                            f"🕒 **Time:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                            f"⚠️ No video or image content found.\n\n"
                            f"**Possible reasons:**\n"
                            f"• Tweet is private/deleted\n"
                            f"• URL doesn't contain media\n"
                            f"• Content is restricted",
                            disable_web_page_preview=False
                        )
                        log_user_action(user_id, username, url, "failed", "unknown")
                else:
                    # Video explicitly requested but not found
                    await status_msg.edit_text(
                        f"❌ **No Video Found**\n\n"
                        f"👤 **X User:** {clickable_username}\n"
                        f"🔗 **URL:** {formatted_url}\n"
                        f"📥 **Requested by:** {username}\n"
                        f"🕒 **Time:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"⚠️ No video content found at this URL.",
                        disable_web_page_preview=False
                    )
                    log_user_action(user_id, username, url, "failed", "video")
            
            elif user_intent == "images":
                # User explicitly wants images
                await status_msg.edit_text(
                    f"🖼️ **Image Download Requested**\n\n"
                    f"👤 **X User:** {clickable_username}\n"
                    f"🔗 **URL:** {formatted_url}\n"
                    f"📥 **Requested by:** {username}\n"
                    f"🕒 **Time:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                    f"⏳ Checking for image content...",
                    disable_web_page_preview=False
                )
                image_paths, image_info = await ImageDownloader.download(url, message)
                
                if image_paths and len(image_paths) > 0:
                    try:
                        from models.enums import user_downloads
                        user_downloads[user_id] = image_paths
                        
                        total_size = sum(os.path.getsize(img) for img in image_paths) / (1024 * 1024)
                        
                        await status_msg.edit_text(
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
                                print(f"❌ Error sending image: {e}")
                        
                        try:
                            await message.reply_text(
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
                            log_user_action(user_id, username, url, "success", "image")
                        except Exception as e:
                            print(f"❌ Error sending confirmation message: {e}")
                        
                    except Exception as e:
                        try:
                            await status_msg.edit_text(
                                f"❌ **Image Send Failed**\n\n"
                                f"⚠️ **Error:** {str(e)[:100]}",
                                disable_web_page_preview=False
                            )
                        except:
                            pass
                        log_user_action(user_id, username, url, "failed", "image")
                else:
                    # Try video as fallback
                    await status_msg.edit_text(
                        f"🎬 **No Images Found - Checking Video**\n\n"
                        f"👤 **X User:** {clickable_username}\n"
                        f"🔗 **URL:** {formatted_url}\n\n"
                        f"⏳ Searching for video...",
                        disable_web_page_preview=False
                    )
                    video_paths, video_info = VideoDownloader.download(url, message)
                    
                    if video_paths and isinstance(video_paths, list) and len(video_paths) > 0:
                        total_videos = len(video_paths)
                        total_size = sum(os.path.getsize(vp) for vp in video_paths if os.path.exists(vp)) / (1024 * 1024)
                        
                        await status_msg.edit_text(
                            f"✅ **Video Found Instead**\n\n"
                            f"🎬 **Videos:** {total_videos}\n"
                            f"💾 **Size:** {total_size:.2f} MB\n\n"
                            f"📤 Sending video(s)...",
                            disable_web_page_preview=False
                        )
                        
                        await status_msg.delete()
                        await send_videos_to_user(video_paths, message, user_id, x_username, url, username, app)
                        log_user_action(user_id, username, url, "success", "video")
                    else:
                        await status_msg.edit_text(
                            f"❌ **No Media Found**\n\n"
                            f"⚠️ No images or videos found at this URL.",
                            disable_web_page_preview=False
                        )
                        log_user_action(user_id, username, url, "failed", "unknown")
        else:
            # Non-X/Twitter URL
            await status_msg.edit_text(
                f"🎬 **Video Download Started**\n\n"
                f"🔗 **URL:** {formatted_url}\n"
                f"📥 **Requested by:** {username}\n"
                f"⏳ Processing...",
                disable_web_page_preview=False
            )
            
            video_paths, video_info = VideoDownloader.download(url, message)
            
            if video_paths and isinstance(video_paths, list) and len(video_paths) > 0:
                await status_msg.delete()
                await send_videos_to_user(video_paths, message, user_id, x_username, url, username, app)
                log_user_action(user_id, username, url, "success", "video")
            else:
                await status_msg.edit_text(
                    f"❌ **Download Failed**\n\n"
                    f"🔗 **URL:** {formatted_url}\n"
                    f"⚠️ Could not download video from this URL.",
                    disable_web_page_preview=False
                )
                log_user_action(user_id, username, url, "failed", "unknown")

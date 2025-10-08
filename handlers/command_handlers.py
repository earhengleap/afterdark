"""
Command handlers for the bot
"""
import os
from pyrogram import Client, filters
from pyrogram.types import Message

from config.settings import BOT_VERSION, VERSION_DATE, BOT_NAME
from core.log_manager import LogManager
from core.file_manager import FileManager
from utils.url_extractor import URLExtractor
from core.downloader import VideoDownloader
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

def setup_command_handlers(app: Client):
    """Setup all command handlers"""
    
    @app.on_message(filters.private & filters.command("start"))
    def start_handler(client: Client, message: Message) -> None:
        """Handle /start command"""
        user_name = message.from_user.first_name
        keyboard = Keyboards.main_menu()
        welcome_text = Messages.welcome(user_name)
        version_footer = f"\n\n📦 **Version {BOT_VERSION}** • {VERSION_DATE}"
        message.reply_text(welcome_text + version_footer, reply_markup=keyboard)

    @app.on_message(filters.private & filters.command("help"))
    def help_handler(client: Client, message: Message) -> None:
        """Handle /help command"""
        text = Messages.help_text()
        keyboard = Keyboards.back_to_main()
        message.reply_text(text, reply_markup=keyboard)

    @app.on_message(filters.private & filters.command("stats"))
    def stats_handler(client: Client, message: Message) -> None:
        """Handle /stats command"""
        stats_info = LogManager.get_stats()
        log = stats_info['log_data']
        
        sync_status = ""
        if not stats_info['synced']:
            sync_status = f"\n\n⚠️ Log entries: {stats_info['log_entries']} | Folder videos: {stats_info['actual_videos']}"
        
        text = Messages.stats_text(log) + sync_status
        keyboard = Keyboards.back_to_main()
        message.reply_text(text, reply_markup=keyboard)

    @app.on_message(filters.private & filters.command("version"))
    def version_handler(client: Client, message: Message) -> None:
        """Handle /version command"""
        version_text = get_version_info()
        keyboard = Keyboards.back_to_main()
        message.reply_text(version_text, reply_markup=keyboard)

    @app.on_message(filters.private & filters.text)
    def text_handler(client: Client, message: Message) -> None:
        """Handle text messages (URLs)"""
        text = message.text.strip()
        username = message.from_user.username or message.from_user.first_name
        user_id = message.from_user.id

        urls = URLExtractor.extract(text)
        
        if not urls:
            message.reply_text(
                "❌ Please send valid URL(s).\n\n"
                "You can send:\n"
                "• Single URL\n"
                "• Multiple URLs separated by spaces, pipes (|), or newlines"
            )
            log_user_action(user_id, username, text, "failed")
            return
        
        # Bulk download
        if len(urls) > 1:
            detection_msg = message.reply_text(
                f"🔍 **Detected {len(urls)} URLs**\n\n"
                f"Starting bulk download..."
            )
            VideoDownloader.download_multiple(urls, message, user_id, detection_msg)
            return
        
        # Single download
        url = urls[0]
        status_msg = message.reply_text(Messages.downloading(url))
        video_path, info = VideoDownloader.download(url, message)

        if not video_path or not os.path.exists(video_path):
            status_msg.edit_text(Messages.download_failed())
            log_user_action(user_id, username, url, "failed")
            return

        status_msg.edit_text(Messages.uploading())
        width, height = VideoProcessor.get_resolution(video_path)

        try:
            file_size = os.path.getsize(video_path) / (1024 * 1024)
            resolution_text = f"{width}x{height}" if width and height else "Unknown"

            from models.enums import user_downloads
            user_downloads[user_id] = video_path

            app.send_video(
                chat_id=message.chat.id,
                video=video_path,
                width=width if width else 720,
                height=height if height else 1280,
                supports_streaming=True,
                caption=(
                    Messages.video_caption(os.path.basename(video_path)) +
                    f"\n\n📏 Resolution: {resolution_text}\n💾 Size: {file_size:.2f} MB"
                ),
                reply_markup=Keyboards.video_actions_with_upload(user_id)
            )

            status_msg.delete()
            log_user_action(user_id, username, url, "success")
            print(f"✅ Sent video {video_path} | Resolution: {resolution_text}, Size: {file_size:.2f} MB")

        except Exception as e:
            status_msg.edit_text(Messages.upload_failed(str(e)))
            log_user_action(user_id, username, url, "failed")
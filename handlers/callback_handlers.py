"""
Callback query handlers for the bot
"""
import os

from pyrogram import Client
from pyrogram.types import CallbackQuery, Message

from core.file_manager import FileManager
from core.uploader import VideoUploader
from ui.messages import Messages
from ui.keyboards import Keyboards
from ui.languages import language_manager
from models.enums import user_downloads, user_selections
from utils.formatters import Formatter

def get_text(user_id: int, key: str) -> str:
    """Helper function to get localized text"""
    return language_manager.get_text(user_id, key)

def setup_callback_handlers(app: Client):
    """Setup all callback handlers"""
    
    @app.on_callback_query()
    def callback_handler(client: Client, callback_query: CallbackQuery) -> None:
        """Handle callback queries"""
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        # Navigation callbacks
        if data == "download":
            keyboard = Keyboards.cancel_button()
            callback_query.message.edit_text(Messages.download_prompt(), reply_markup=keyboard)
        
        elif data == "about":
            keyboard = Keyboards.back_to_main()
            callback_query.message.edit_text(Messages.about_text(), reply_markup=keyboard)
        
        elif data == "help":
            keyboard = Keyboards.back_to_main()
            callback_query.message.edit_text(Messages.help_text(), reply_markup=keyboard)
        
        elif data == "stats":
            from core.log_manager import LogManager
            stats_info = LogManager.get_stats()
            log = stats_info['log_data']
            sync_status = ""
            if not stats_info['synced']:
                sync_status = f"\n\n⚠️ Log entries: {stats_info['log_entries']} | Folder videos: {stats_info['actual_videos']}"
            keyboard = Keyboards.back_to_main()
            callback_query.message.edit_text(Messages.stats_text(log) + sync_status, reply_markup=keyboard)
        
        elif data == "settings":
            keyboard = Keyboards.settings_menu()
            callback_query.message.edit_text(Messages.settings_text(), reply_markup=keyboard)
        
        elif data == "main_menu":
            keyboard = Keyboards.main_menu()
            user_name = callback_query.from_user.first_name
            callback_query.message.edit_text(Messages.welcome(user_name), reply_markup=keyboard)
        
        elif data == "cancel":
            keyboard = Keyboards.main_menu()
            callback_query.message.edit_text(Messages.action_cancelled(), reply_markup=keyboard)
        
        elif data == "version":
            from handlers.command_handlers import get_version_info
            keyboard = Keyboards.back_to_main()
            callback_query.message.edit_text(get_version_info(), reply_markup=keyboard)
        
        # Bulk upload callbacks
        elif data == "bulk_upload":
            videos = FileManager.get_all_videos()
            if not videos:
                callback_query.answer("❌ No videos found in download folder!", show_alert=True)
                return
            
            video_dicts = [{'filename': v.filename, 'filepath': v.filepath, 'size': v.size_mb} for v in videos]
            user_downloads[f"{user_id}_videos"] = video_dicts
            if user_id not in user_selections:
                user_selections[user_id] = set()
            
            current_page = user_downloads.get(f"{user_id}_page", 0)
            keyboard = Keyboards.video_list_keyboard(video_dicts, user_selections.get(user_id, set()), page=current_page)
            callback_query.message.edit_text(Messages.bulk_upload_prompt(len(videos)), reply_markup=keyboard)
        
        elif data.startswith("sel_") and data != "sel_all":
            try:
                video_idx = int(data.replace("sel_", ""))
            except ValueError:
                callback_query.answer("❌ Invalid selection", show_alert=True)
                return
            
            if user_id not in user_selections:
                user_selections[user_id] = set()
            
            if video_idx in user_selections[user_id]:
                user_selections[user_id].remove(video_idx)
                callback_query.answer("❌ Deselected")
            else:
                user_selections[user_id].add(video_idx)
                callback_query.answer("✅ Selected")
            
            videos = user_downloads.get(f"{user_id}_videos", [])
            current_page = user_downloads.get(f"{user_id}_page", 0)
            keyboard = Keyboards.video_list_keyboard(videos, user_selections[user_id], page=current_page)
            
            try:
                callback_query.message.edit_reply_markup(reply_markup=keyboard)
            except Exception:
                pass
        
        elif data == "sel_all":
            videos = user_downloads.get(f"{user_id}_videos", [])
            user_selections[user_id] = set(range(len(videos)))
            keyboard = Keyboards.video_list_keyboard(videos, user_selections[user_id], page=0)
            callback_query.message.edit_reply_markup(reply_markup=keyboard)
            callback_query.answer(f"✅ Selected all {len(videos)} videos")
        
        elif data == "desel_all":
            videos = user_downloads.get(f"{user_id}_videos", [])
            user_selections[user_id] = set()
            keyboard = Keyboards.video_list_keyboard(videos, user_selections[user_id], page=0)
            callback_query.message.edit_reply_markup(reply_markup=keyboard)
            callback_query.answer("❌ Deselected all videos")
        
        elif data.startswith("pg_"):
            try:
                page = int(data.replace("pg_", ""))
            except ValueError:
                return
            
            videos = user_downloads.get(f"{user_id}_videos", [])
            keyboard = Keyboards.video_list_keyboard(videos, user_selections.get(user_id, set()), page=page)
            
            try:
                callback_query.message.edit_reply_markup(reply_markup=keyboard)
                callback_query.answer(f"📄 Page {page + 1}")
            except Exception:
                pass
        
        elif data == "confirm_upload":
            if user_id not in user_selections or not user_selections[user_id]:
                callback_query.answer("❌ No videos selected!", show_alert=True)
                return
            
            videos = user_downloads.get(f"{user_id}_videos", [])
            selected_files = [videos[idx]['filepath'] for idx in user_selections[user_id] if idx < len(videos)]
            
            if not selected_files:
                callback_query.answer("❌ No valid videos selected!", show_alert=True)
                return
            
            callback_query.answer("📤 Starting upload...")
            VideoUploader.upload_multiple(selected_files, callback_query.message, user_id)
            
            user_selections[user_id] = set()
            if f"{user_id}_videos" in user_downloads:
                del user_downloads[f"{user_id}_videos"]
        
        # Upload callbacks
        elif data.startswith("upload_to_group_"):
            video_path = user_downloads.get(user_id)
            
            if not video_path or not os.path.exists(video_path):
                callback_query.answer("❌ Video file not found. Please download again.", show_alert=True)
                return
            
            callback_query.answer("📤 Uploading to group...", show_alert=False)
            
            video_name = os.path.basename(video_path)
            file_size = os.path.getsize(video_path)
            status_msg = callback_query.message.reply_text(
                f"📤 **Starting Upload**\n\n"
                f"📁 File: `{video_name[:35]}...`\n"
                f"💾 Size: {Formatter.size(file_size)}\n\n"
                f"⏳ Preparing..."
            )
            
            # Pass the client from callback_query
            success, message = VideoUploader.upload_to_group(
                video_path, user_id, status_msg, client=callback_query.message._client
            )
            
            if success:
                status_msg.edit_text(
                    "✅ **Video Uploaded to Group Successfully!**\n\n"
                    f"📁 File: `{video_name}`\n"
                    f"💾 Size: {Formatter.size(file_size)}\n\n"
                    "The video has been shared with the group.\n\n"
                    "Want to download another video?",
                    reply_markup=Keyboards.back_to_main()
                )
            else:
                status_msg.edit_text(
                    f"❌ **Upload Failed**\n\n"
                    f"Error: {message}\n\n"
                    "Please try again later.",
                    reply_markup=Keyboards.back_to_main()
                )

        elif data == "upload_bulk_downloaded":
            downloaded_paths = user_downloads.get(f"{user_id}_bulk_downloaded", [])
            
            if not downloaded_paths:
                callback_query.answer("❌ No downloaded videos found!", show_alert=True)
                return
            
            callback_query.answer("📤 Starting bulk upload...")
            VideoUploader.upload_multiple(downloaded_paths, callback_query.message, user_id)

        elif data.startswith("upload_single_"):
            video_key = data.replace("upload_single_", "")
            video_path = user_downloads.get(video_key)
            
            if not video_path or not os.path.exists(video_path):
                callback_query.answer("❌ Video file not found.", show_alert=True)
                return
            
            callback_query.answer("📤 Uploading to group...", show_alert=False)
            
            video_name = os.path.basename(video_path)
            file_size = os.path.getsize(video_path)
            status_msg = callback_query.message.reply_text(
                f"📤 **Starting Upload**\n\n"
                f"📁 File: `{video_name[:35]}...`\n"
                f"💾 Size: {Formatter.size(file_size)}\n\n"
                f"⏳ Preparing..."
            )
            
            # Pass the client from callback_query
            success, message = VideoUploader.upload_to_group(
                video_path, user_id, status_msg, client=callback_query.message._client
            )
            
            if success:
                status_msg.edit_text(
                    "✅ **Video Uploaded Successfully!**\n\n"
                    f"📁 File: `{video_name}`\n"
                    f"💾 Size: {Formatter.size(file_size)}",
                    reply_markup=Keyboards.back_to_main()
                )
                try:
                    callback_query.message.edit_reply_markup(reply_markup=None)
                except Exception:
                    pass
            else:
                status_msg.edit_text(
                    f"❌ **Upload Failed**\n\n"
                    f"Error: {message}",
                    reply_markup=Keyboards.back_to_main()
                )
        
        elif data == "upload_bulk_downloaded":
            downloaded_paths = user_downloads.get(f"{user_id}_bulk_downloaded", [])
            
            if not downloaded_paths:
                callback_query.answer("❌ No downloaded videos found!", show_alert=True)
                return
            
            callback_query.answer("📤 Starting bulk upload...")
            VideoUploader.upload_multiple(downloaded_paths, callback_query.message, user_id)
            
            if f"{user_id}_bulk_downloaded" in user_downloads:
                del user_downloads[f"{user_id}_bulk_downloaded"]
        
        elif data.startswith("upload_single_"):
            video_key = data.replace("upload_single_", "")
            video_path = user_downloads.get(video_key)
            
            if not video_path or not os.path.exists(video_path):
                callback_query.answer("❌ Video file not found.", show_alert=True)
                return
            
            callback_query.answer("📤 Uploading to group...", show_alert=False)
            
            video_name = os.path.basename(video_path)
            file_size = os.path.getsize(video_path)
            status_msg = callback_query.message.reply_text(
                f"📤 **Starting Upload**\n\n"
                f"📁 File: `{video_name[:35]}...`\n"
                f"💾 Size: {Formatter.size(file_size)}\n\n"
                f"⏳ Preparing..."
            )
            
            success, message = VideoUploader.upload_to_group(video_path, user_id, status_msg)
            
            if success:
                status_msg.edit_text(
                    "✅ **Video Uploaded Successfully!**\n\n"
                    f"📁 File: `{video_name}`\n"
                    f"💾 Size: {Formatter.size(file_size)}",
                    reply_markup=Keyboards.back_to_main()
                )
                try:
                    callback_query.message.edit_reply_markup(reply_markup=None)
                except Exception:
                    pass
            else:
                status_msg.edit_text(
                    f"❌ **Upload Failed**\n\n"
                    f"Error: {message}",
                    reply_markup=Keyboards.back_to_main()
                )
        
        # Language settings
        elif data == "settings_language":
            keyboard = language_manager.get_language_keyboard()
            current_lang = language_manager.get_user_language(user_id)
            lang_name = language_manager.LANGUAGES.get(current_lang, '🇬🇧 English')
            
            callback_query.message.edit_text(
                f"🌐 **{get_text(user_id, 'select_language')}**\n\n"
                f"📍 {get_text(user_id, 'current_language')}: {lang_name}\n\n"
                f"Choose your preferred language from the options below:",
                reply_markup=keyboard
            )
        
        elif data.startswith("lang_"):
            lang_code = data.replace("lang_", "")
            
            if language_manager.set_user_language(user_id, lang_code):
                lang_name = language_manager.LANGUAGES[lang_code]
                callback_query.answer(f"✅ {lang_name}", show_alert=False)
                
                callback_query.message.edit_text(
                    f"✅ **{get_text(user_id, 'language_changed')}**\n\n"
                    f"🌐 {get_text(user_id, 'current_language')}: {lang_name}\n\n"
                    f"{get_text(user_id, 'what_next')}",
                    reply_markup=Keyboards.back_to_main()
                )
            else:
                callback_query.answer("❌ Invalid language", show_alert=True)
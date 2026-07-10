"""
Callback query handlers for the bot
"""
import os
import time
import asyncio
from datetime import datetime

from pyrogram import Client
from pyrogram.types import CallbackQuery, Message
import logging
from pyrogram.errors import MessageNotModified

# Get logger
logger = logging.getLogger("AfterDark")

from core.file_manager import FileManager
from core.uploader import VideoUploader
from core.image_downloader import ImageDownloader
from resources.messages import Messages
from resources.keyboards import Keyboards
from resources.languages import language_manager
from models.enums import user_downloads, user_selections
from core.formatting.formatters import Formatter
from core.image_uploader import ImageUploader
from core.videy_links import get_videy_links
from core.formatting.videy_formatter import format_videy_message, format_videy_export_message
from core.export.videy_exporter import export_videy_to_csv, export_videy_to_text

def get_text(user_id: int, key: str, default: str = None) -> str:
    """Helper function to get localized text"""
    return language_manager.translate(user_id, key, default)



def _fallback_video_paths() -> list:
    """Fallback video paths from filesystem, newest first."""
    videos = FileManager.get_all_videos()
    videos.sort(key=lambda x: os.path.getmtime(x.filepath), reverse=True)
    return [v.filepath for v in videos if os.path.exists(v.filepath)]


def _fallback_image_paths() -> list:
    """Fallback image paths from filesystem, newest first."""
    images = FileManager.get_all_images()
    images.sort(key=lambda x: os.path.getmtime(x.filepath), reverse=True)
    return [i.filepath for i in images if os.path.exists(i.filepath)]

def setup_callback_handlers(app: Client):
    """Setup all callback handlers"""
    
    @app.on_callback_query()
    async def callback_handler(client: Client, callback_query: CallbackQuery) -> None:
        """Handle callback queries"""
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        # Navigation callbacks
        if data == "download":
            keyboard = Keyboards.cancel_button(user_id=user_id)
            await callback_query.message.edit_text(Messages.download_prompt(), reply_markup=keyboard)
        
        elif data == "download_images":
            keyboard = Keyboards.cancel_button(user_id=user_id)
            await callback_query.message.edit_text(Messages.image_download_prompt(), reply_markup=keyboard)
        
        elif data == "about":
            keyboard = Keyboards.back_to_main(user_id=user_id)
            await callback_query.message.edit_text(Messages.about_text(), reply_markup=keyboard)
        
        elif data == "help":
            help_text = Messages.help_text()
            await callback_query.message.edit_text(help_text, reply_markup=Keyboards.back_to_main(user_id=user_id))
        
        elif data == "bulk_content":
            await callback_query.message.edit_text(
                Messages.bulk_content_prompt(),
                reply_markup=Keyboards.back_to_main(user_id=user_id)
            )
        
        # ==================== BULK QUEUE HANDLERS ====================
        elif data == "bulk_queue":
            from core.database import history_db
            
            queue_count = history_db.get_queue_count(user_id)
            is_bulk_mode = history_db.get_setting(user_id, "bulk_mode", "0") == "1"
            
            await callback_query.message.edit_text(
                f"?? **Bulk Download Queue**\n\n"
                f"?? **Items in Queue:** {queue_count}\n"
                f"?? **Bulk Mode:** {'? Enabled' if is_bulk_mode else '? Disabled'}\n\n"
                f"__Enable Bulk Mode to queue up links instead of downloading immediately.__",
                reply_markup=Keyboards.bulk_queue_menu(queue_count, is_bulk_mode, user_id=user_id)
            )
            
        elif data.startswith("toggle_bulk:"):
            from core.database import history_db
            action = data.split(":")[1]
            new_value = "1" if action == "enable" else "0"
            
            history_db.set_setting(user_id, "bulk_mode", new_value)
            
            # Refresh menu
            queue_count = history_db.get_queue_count(user_id)
            is_bulk_mode = new_value == "1"
            
            await callback_query.message.edit_text(
                f"?? **Bulk Download Queue**\n\n"
                f"?? **Items in Queue:** {queue_count}\n"
                f"?? **Bulk Mode:** {'? Enabled' if is_bulk_mode else '? Disabled'}\n\n"
                f"__Enable Bulk Mode to queue up links instead of downloading immediately.__",
                reply_markup=Keyboards.bulk_queue_menu(queue_count, is_bulk_mode, user_id=user_id)
            )
            
        elif data == "process_queue":
            from core.database import history_db
            from core.downloader import VideoDownloader
            
            urls = history_db.get_queue(user_id)
            if not urls:
                await callback_query.answer("? Queue is empty!", show_alert=True)
                return
            
            # Clear queue immediately to prevent double processing
            history_db.clear_queue(user_id)
            
            await callback_query.answer(f"?? Processing {len(urls)} links...")
            
            status_msg = await callback_query.message.edit_text(
                f"?? **Processing Bulk Queue**\n\n"
                f"?? **Links:** {len(urls)}\n"
                f"? Starting download process...",
                reply_markup=None
            )
            
            # Use existing bulk download logic
            await VideoDownloader.download_multiple(urls, callback_query.message, user_id, status_msg)
            
        elif data == "clear_queue":
            from core.database import history_db
            
            history_db.clear_queue(user_id)
            await callback_query.answer("? Queue cleared!")
            
            # Refresh menu
            is_bulk_mode = history_db.get_setting(user_id, "bulk_mode", "0") == "1"
            await callback_query.message.edit_text(
                f"?? **Bulk Download Queue**\n\n"
                f"?? **Items in Queue:** 0\n"
                f"?? **Bulk Mode:** {'? Enabled' if is_bulk_mode else '? Disabled'}\n\n"
                f"__Queue cleared successfully.__",
                reply_markup=Keyboards.bulk_queue_menu(0, is_bulk_mode, user_id=user_id)
            )
        
        elif data == "get_share_link":
            from config.settings import BOT_USERNAME, BOT_NAME
            from core.parsing.deep_link import DeepLinkHelper
            
            share_link = DeepLinkHelper.generate_share_link(BOT_USERNAME)
            
            await callback_query.message.edit_text(
                f"?? **Share to Bot**\n\n"
                f"Share an X video to this bot without copying the link!\n\n"
                f"**Method 1: Mobile Share**\n"
                f"1. Tap Share on any X post\n"
                f"2. Select Telegram\n"
                f"3. Select **{BOT_NAME}** (@{BOT_USERNAME})\n"
                f"4. Video downloads instantly!\n\n"
                f"**Method 2: Deep Link**\n"
                f"Add this link to your X bio:\n"
                f"`{share_link}`\n\n"
                f"Anyone who clicks it can send you videos!",
                reply_markup=Keyboards.back_to_main(user_id=user_id)
            )

        elif data == "socials":
            await callback_query.message.edit_text(
                "?? **Community & Socials**\n\n"
                "Stay updated and get support from our community:\n\n"
                "?? **Channel:** @XDownloaderPro_News\n"
                "?? **Support Group:** @XDownloaderPro_Support\n"
                "??? **Developer:** @DevMoonlight\n\n"
                "Feel free to report bugs or suggest features!",
                reply_markup=Keyboards.back_to_main(user_id=user_id)
            )
        
        elif data == "stats":
            from core.log_manager import LogManager
            stats_info = LogManager.get_stats()
            log = stats_info['log_data']
            sync_status = ""
            if not stats_info['synced']:
                sync_status = f"\n\n?? Log entries: {stats_info['log_entries']} | Folder videos: {stats_info['actual_videos']}"
            keyboard = Keyboards.back_to_main(user_id=user_id)
            await callback_query.message.edit_text(Messages.stats_text(log) + sync_status, reply_markup=keyboard)

        elif data == "videy_links" or data.startswith("videy:"):
            effective_data = "videy:1" if data == "videy_links" else data
            parts = effective_data.split(":")
            action = parts[1] if len(parts) > 1 else "1"
            links = get_videy_links(user_id)
            if not links:
                await callback_query.message.edit_text(
                    "?? **Videy Links**\n\nNo links found yet.\n\nDownload a video first, then use this menu again.",
                    reply_markup=Keyboards.back_to_main(user_id=user_id),
                    disable_web_page_preview=False,
                )
                return

            links = list(reversed(links))
            if action == "export":
                keyboard = Keyboards.videy_export_format_selection(user_id=user_id)
                await callback_query.message.edit_text(
                    format_videy_export_message(len(links)),
                    reply_markup=keyboard
                )
                return

            try:
                page = int(action)
            except ValueError:
                page = 1

            per_page = 10
            total_count = len(links)
            total_pages = max(1, (total_count + per_page - 1) // per_page)
            page = max(1, min(page, total_pages))
            offset = (page - 1) * per_page
            page_entries = links[offset:offset + per_page]

            text = format_videy_message(page_entries, page, total_pages, total_count)
            keyboard = Keyboards.videy_pagination(page, total_pages, user_id=user_id)
            await callback_query.message.edit_text(
                text,
                reply_markup=keyboard,
                disable_web_page_preview=False
            )
            await callback_query.answer(f"?? Page {page}/{total_pages}")
        
        elif data.startswith("videy_export:"):
            links = get_videy_links(user_id)
            if not links:
                await callback_query.answer("No Videy links to export!", show_alert=True)
                return

            links = list(reversed(links))
            format_type = data.split(":")[1]
            await callback_query.answer("?? Generating Videy export...")

            if format_type == "csv":
                file_data = export_videy_to_csv(links)
                filename = f"videy_links_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                caption = f"?? **Videy Links (CSV)**\n\n{len(links)} total links"
            else:
                file_data = export_videy_to_text(links)
                filename = f"videy_links_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                caption = f"?? **Videy Links (Text)**\n\n{len(links)} total links"

            await callback_query.message.reply_document(
                document=file_data,
                file_name=filename,
                caption=caption
            )

            try:
                await callback_query.message.delete()
            except Exception:
                pass

            await callback_query.answer("? Videy links exported!")
        
        elif data == "settings_notifications":
            from core.database import history_db
            current = history_db.get_setting(user_id, "tunnel_notifications", "1")
            is_enabled = str(current).strip().lower() in {"1", "true", "yes", "on"}
            new_enabled = not is_enabled
            history_db.set_setting(user_id, "tunnel_notifications", "1" if new_enabled else "0")

            keyboard = Keyboards.settings_menu(new_enabled, user_id=user_id)
            status_text = "ON" if new_enabled else "OFF"
            await callback_query.message.edit_text(
                Messages.settings_text() + f"\n\nTunnel notifications: **{status_text}**",
                reply_markup=keyboard
            )
            await callback_query.answer(f"Notifications {status_text}")

        elif data == "settings":
            from core.database import history_db
            current = history_db.get_setting(user_id, "tunnel_notifications", "1")
            is_enabled = str(current).strip().lower() in {"1", "true", "yes", "on"}
            keyboard = Keyboards.settings_menu(is_enabled, user_id=user_id)
            status_text = "ON" if is_enabled else "OFF"
            await callback_query.message.edit_text(
                Messages.settings_text() + f"\n\nTunnel notifications: **{status_text}**",
                reply_markup=keyboard
            )
        


        elif data == "settings_language":
            from resources.languages import language_manager
            from pyrogram.errors import MessageNotModified
            
            keyboard = language_manager.get_language_keyboard(user_id=user_id)
            current_lang_name = language_manager.LANGUAGES.get(language_manager.get_user_language(user_id), 'English')
            lang_header = get_text(user_id, 'select_language', 'Select Your Language')
            
            try:
                await callback_query.message.edit_text(
                    Messages.settings_text(user_id=user_id) + f"\n\n🌐 **{lang_header}**\n_Current: {current_lang_name}_",
                    reply_markup=keyboard
                )
            except MessageNotModified:
                pass
            await callback_query.answer()
            
        elif data.startswith("lang_"):
            from core.database import history_db
            from resources.languages import language_manager
            from pyrogram.errors import MessageNotModified
            
            new_lang = data[5:]  # strip 'lang_' prefix
            old_lang = language_manager.get_user_language(user_id)
            
            if new_lang in language_manager.LANGUAGES:
                language_manager.set_user_language(user_id, new_lang)
                lang_name = language_manager.LANGUAGES[new_lang]
                changed_text = get_text(user_id, 'language_changed', 'Language changed successfully! ✅')
                await callback_query.answer(f"{changed_text} ({lang_name})", show_alert=(new_lang != old_lang))
            else:
                await callback_query.answer("Unknown language.", show_alert=True)
                return
            
            # Rebuild the keyboard and message in the NEW language
            keyboard = language_manager.get_language_keyboard(user_id=user_id)
            lang_header = get_text(user_id, 'select_language', 'Select Your Language')
            current_lang_name = language_manager.LANGUAGES.get(new_lang, 'English')
            
            try:
                await callback_query.message.edit_text(
                    Messages.settings_text(user_id=user_id) + f"\n\n🌐 **{lang_header}**\n_Current: {current_lang_name}_",
                    reply_markup=keyboard
                )
            except MessageNotModified:
                # Same language re-selected; just update the markup to keep checkmark fresh
                try:
                    await callback_query.message.edit_reply_markup(reply_markup=keyboard)
                except Exception:
                    pass

        elif data == "settings_theme":
            from core.database import history_db
            current_theme = history_db.get_setting(user_id, "bot_theme", "default")
            keyboard = Keyboards.theme_selection_menu(current_theme, user_id=user_id)
            
            await callback_query.message.edit_text(
                Messages.settings_text(user_id=user_id) + "\n\n🎨 **Choose a Theme:**",
                reply_markup=keyboard
            )
            
        elif data.startswith("set_theme:"):
            from core.database import history_db
            from resources.themes import theme_manager
            
            new_theme = data.split(":")[1]
            if new_theme in theme_manager.THEMES:
                history_db.set_setting(user_id, "bot_theme", new_theme)
                await callback_query.answer(f"✅ Theme changed to {theme_manager.THEMES[new_theme]['name']}!")
            
            # Rehydrate with new theme immediately
            current_theme = history_db.get_setting(user_id, "bot_theme", "default")
            keyboard = Keyboards.theme_selection_menu(current_theme, user_id=user_id)
            
            try:
                await callback_query.message.edit_text(
                    Messages.settings_text(user_id=user_id) + "\n\n🎨 **Choose a Theme:**",
                    reply_markup=keyboard
                )
            except Exception:
                pass

        elif data == "main_menu":
            keyboard = Keyboards.main_menu(user_id=user_id)
            user_name = callback_query.from_user.first_name
            try:
                await callback_query.message.edit_text(Messages.welcome(user_name, user_id=user_id), reply_markup=keyboard)
            except MessageNotModified:
                pass
            await callback_query.answer()
        
        elif data == "cancel":
            keyboard = Keyboards.main_menu(user_id=user_id)
            try:
                await callback_query.message.edit_text(Messages.action_cancelled(), reply_markup=keyboard)
            except MessageNotModified:
                pass
            await callback_query.answer()
        
        elif data == "version":
            from handlers.command_handlers import get_version_info
            keyboard = Keyboards.back_to_main(user_id=user_id)
            await callback_query.message.edit_text(get_version_info(), reply_markup=keyboard)
        
        # Bulk upload callbacks
        elif data == "bulk_upload":
            videos = FileManager.get_all_videos()
            if not videos:
                await callback_query.answer("? No videos found in download folder!", show_alert=True)
                return
            
            video_dicts = [{'filename': v.filename, 'filepath': v.filepath, 'size': v.size_mb} for v in videos]
            user_downloads[f"{user_id}_videos"] = video_dicts
            if user_id not in user_selections:
                user_selections[user_id] = set()
            
            current_page = user_downloads.get(f"{user_id}_page", 0)
            keyboard = Keyboards.video_list_keyboard(video_dicts, user_selections.get(user_id, set()), page=current_page, user_id=user_id)
            await callback_query.message.edit_text(Messages.bulk_upload_prompt(len(videos)), reply_markup=keyboard)
        
        elif data == "bulk_upload_images":
            images = FileManager.get_all_images()
            if not images:
                await callback_query.answer("? No images found in download folder!", show_alert=True)
                return
            
            image_dicts = [{'filename': img.filename, 'filepath': img.filepath, 'size': img.size_mb} for img in images]
            user_downloads[f"{user_id}_images"] = image_dicts
            if user_id not in user_selections:
                user_selections[user_id] = set()
            
            current_page = user_downloads.get(f"{user_id}_image_page", 0)
            keyboard = Keyboards.image_list_keyboard(image_dicts, user_selections.get(user_id, set()), page=current_page, user_id=user_id)
            await callback_query.message.edit_text(Messages.bulk_image_upload_prompt(len(images)), reply_markup=keyboard)
        
        elif data.startswith("sel_") and data != "sel_all":
            try:
                video_idx = int(data.replace("sel_", ""))
            except ValueError:
                await callback_query.answer("? Invalid selection", show_alert=True)
                return
            
            if user_id not in user_selections:
                user_selections[user_id] = set()
            
            if video_idx in user_selections[user_id]:
                user_selections[user_id].remove(video_idx)
                await callback_query.answer("? Deselected")
            else:
                user_selections[user_id].add(video_idx)
                await callback_query.answer("? Selected")
            
            videos = user_downloads.get(f"{user_id}_videos", [])
            current_page = user_downloads.get(f"{user_id}_page", 0)
            keyboard = Keyboards.video_list_keyboard(videos, user_selections[user_id], page=current_page, user_id=user_id)
            
            try:
                await callback_query.message.edit_reply_markup(reply_markup=keyboard)
            except Exception:
                pass
        
        elif data.startswith("img_sel_") and data != "img_sel_all":
            try:
                image_idx = int(data.replace("img_sel_", ""))
            except ValueError:
                await callback_query.answer("? Invalid selection", show_alert=True)
                return
            
            if user_id not in user_selections:
                user_selections[user_id] = set()
            
            if image_idx in user_selections[user_id]:
                user_selections[user_id].remove(image_idx)
                await callback_query.answer("? Deselected")
            else:
                user_selections[user_id].add(image_idx)
                await callback_query.answer("? Selected")
            
            images = user_downloads.get(f"{user_id}_images", [])
            current_page = user_downloads.get(f"{user_id}_image_page", 0)
            keyboard = Keyboards.image_list_keyboard(images, user_selections[user_id], page=current_page, user_id=user_id)
            
            try:
                await callback_query.message.edit_reply_markup(reply_markup=keyboard)
            except Exception:
                pass
        
        elif data == "sel_all":
            videos = user_downloads.get(f"{user_id}_videos", [])
            user_selections[user_id] = set(range(len(videos)))
            keyboard = Keyboards.video_list_keyboard(videos, user_selections[user_id], page=0, user_id=user_id)
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
            await callback_query.answer(f"? Selected all {len(videos)} videos")
        
        elif data == "img_sel_all":
            images = user_downloads.get(f"{user_id}_images", [])
            user_selections[user_id] = set(range(len(images)))
            keyboard = Keyboards.image_list_keyboard(images, user_selections[user_id], page=0, user_id=user_id)
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
            await callback_query.answer(f"? Selected all {len(images)} images")
        
        elif data == "desel_all":
            videos = user_downloads.get(f"{user_id}_videos", [])
            user_selections[user_id] = set()
            keyboard = Keyboards.video_list_keyboard(videos, user_selections[user_id], page=0, user_id=user_id)
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
            await callback_query.answer("? Deselected all videos")
        
        elif data == "img_desel_all":
            images = user_downloads.get(f"{user_id}_images", [])
            user_selections[user_id] = set()
            keyboard = Keyboards.image_list_keyboard(images, user_selections[user_id], page=0, user_id=user_id)
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
            await callback_query.answer("? Deselected all images")
        
        elif data.startswith("pg_"):
            try:
                page = int(data.replace("pg_", ""))
            except ValueError:
                return
            
            videos = user_downloads.get(f"{user_id}_videos", [])
            keyboard = Keyboards.video_list_keyboard(videos, user_selections.get(user_id, set()), page=page, user_id=user_id)
            
            try:
                await callback_query.message.edit_reply_markup(reply_markup=keyboard)
                await callback_query.answer(f"?? Page {page + 1}")
            except Exception:
                pass
        
        elif data.startswith("img_pg_"):
            try:
                page = int(data.replace("img_pg_", ""))
            except ValueError:
                return
            
            images = user_downloads.get(f"{user_id}_images", [])
            keyboard = Keyboards.image_list_keyboard(images, user_selections.get(user_id, set()), page=page, user_id=user_id)
            
            try:
                await callback_query.message.edit_reply_markup(reply_markup=keyboard)
                await callback_query.answer(f"?? Page {page + 1}")
            except Exception:
                pass
        
        elif data == "confirm_upload":
            if user_id not in user_selections or not user_selections[user_id]:
                await callback_query.answer("? No videos selected!", show_alert=True)
                return
            
            videos = user_downloads.get(f"{user_id}_videos", [])
            selected_files = [videos[idx]['filepath'] for idx in user_selections[user_id] if idx < len(videos)]
            
            if not selected_files:
                await callback_query.answer("? No valid videos selected!", show_alert=True)
                return
            
            await callback_query.answer("?? Starting upload...")
            await VideoUploader.upload_multiple(selected_files, callback_query.message, user_id)
            
            user_selections[user_id] = set()
            if f"{user_id}_videos" in user_downloads:
                del user_downloads[f"{user_id}_videos"]
        
        elif data == "confirm_image_upload":
            if user_id not in user_selections or not user_selections[user_id]:
                await callback_query.answer("? No images selected!", show_alert=True)
                return
            
            images = user_downloads.get(f"{user_id}_images", [])
            selected_files = [images[idx]['filepath'] for idx in user_selections[user_id] if idx < len(images)]
            
            if not selected_files:
                await callback_query.answer("? No valid images selected!", show_alert=True)
                return
            
            await callback_query.answer("?? Starting image upload...")
            await ImageUploader.upload_multiple_images(selected_files, callback_query.message, user_id)
            
            user_selections[user_id] = set()
            if f"{user_id}_images" in user_downloads:
                del user_downloads[f"{user_id}_images"]
        
        # Upload callbacks - UPDATED TO SUPPORT MULTIPLE VIDEOS PER URL
        elif data.startswith("upload_to_group_"):
            # Cancel auto-upload if pending
            from core.auto_scheduler import AutoScheduler
            await AutoScheduler.cancel_task(user_id, "video_single")
            await AutoScheduler.cancel_task(user_id, "video_bulk")
            
            # Handle both single video and multiple videos
            video_path = user_downloads.get(user_id)
            if not video_path:
                fallback_videos = _fallback_video_paths()
                if fallback_videos:
                    # Recover after bot restart when memory state is empty.
                    video_path = fallback_videos[0]
                    logger.info(f"Recovered single video upload for user {user_id} from disk")
            
            # Check if it's a single video path or multiple videos
            if isinstance(video_path, list) and len(video_path) > 0:
                # Multiple videos from single URL
                await callback_query.answer(f"?? Uploading {len(video_path)} videos to group...", show_alert=False)
                
                status_msg = await callback_query.message.reply_text(
                    f"?? **Starting Bulk Upload**\n\n"
                    f"?? Videos: {len(video_path)} files\n\n"
                    f"? Preparing..."
                )
                
                # Upload all videos from this URL
                await VideoUploader.upload_multiple(video_path, status_msg, user_id)
                
            elif video_path and os.path.exists(video_path):
                # Single video (original behavior)
                await callback_query.answer("?? Uploading to group...", show_alert=False)
                
                video_name = os.path.basename(video_path)
                file_size = os.path.getsize(video_path)
                status_msg = await callback_query.message.reply_text(
                    f"?? **Starting Upload**\n\n"
                    f"?? File: `{video_name[:35]}...`\n"
                    f"?? Size: {Formatter.size(file_size)}\n\n"
                    f"? Preparing..."
                )
                
                # Pass the client from callback_query
                success, message = await VideoUploader.upload_to_group(
                    video_path, user_id, status_msg, client=callback_query.message._client
                )
                
                if success:
                    await status_msg.edit_text(
                        "? **Video Uploaded to Group Successfully!**\n\n"
                        f"?? File: `{video_name}`\n"
                        f"?? Size: {Formatter.size(file_size)}\n\n"
                        "The video has been shared with the group.\n\n"
                        "Want to download another video?",
                        reply_markup=Keyboards.back_to_main(user_id=user_id)
                    )
                else:
                    await status_msg.edit_text(
                        f"? **Upload Failed**\n\n"
                        f"Error: {message}\n\n"
                        "Please try again later.",
                        reply_markup=Keyboards.back_to_main(user_id=user_id)
                    )
            else:
                await callback_query.answer("? Video file not found. Please download again.", show_alert=True)

        elif data.startswith("upload_images_to_group_"):
            # Cancel auto-upload if pending
            from core.auto_scheduler import AutoScheduler
            await AutoScheduler.cancel_task(user_id, "image_bulk")
            
            image_paths = user_downloads.get(user_id, [])
            if not image_paths:
                # Recover after restart: use latest image files.
                image_paths = _fallback_image_paths()[:20]
            
            if not image_paths or (isinstance(image_paths, str) and not os.path.exists(image_paths)):
                await callback_query.answer("? Image files not found. Please download again.", show_alert=True)
                return
            
            await callback_query.answer("?? Uploading images to group...", show_alert=False)
            
            if isinstance(image_paths, str):
                image_paths = [image_paths]
            
            status_msg = await callback_query.message.reply_text(
                f"?? **Starting Image Upload**\n\n"
                f"??? Files: {len(image_paths)} images\n\n"
                f"? Preparing..."
            )
            
            success, message = await ImageUploader.upload_images_to_group(
                image_paths, user_id, status_msg, client=callback_query.message._client
            )
            
            if success:
                await status_msg.edit_text(
                    "? **Images Uploaded to Group Successfully!**\n\n"
                    f"??? Uploaded: {len(image_paths)} images\n\n"
                    "The images have been shared with the group.\n\n"
                    "Want to download more images?",
                    reply_markup=Keyboards.back_to_main(user_id=user_id)
                )
            else:
                await status_msg.edit_text(
                    f"? **Upload Failed**\n\n"
                    f"Error: {message}\n\n"
                    "Please try again later.",
                    reply_markup=Keyboards.back_to_main(user_id=user_id)
                )

        elif data == "upload_bulk_downloaded" or data == "upload_bulk_videos_downloaded":
            # Cancel auto-upload if pending
            from core.auto_scheduler import AutoScheduler
            await AutoScheduler.cancel_task(user_id, "video_bulk")
            
            # Handle multiple videos from bulk downloads
            downloaded_paths = user_downloads.get(f"{user_id}_bulk_downloaded", [])
            
            # Also check for multiple videos from single URL
            if not downloaded_paths:
                downloaded_paths = user_downloads.get(f"{user_id}_bulk_videos", [])

            # Restart recovery fallback
            if not downloaded_paths:
                downloaded_paths = _fallback_video_paths()
            
            if not downloaded_paths:
                await callback_query.answer("? No downloaded videos found!", show_alert=True)
                return
            
            await callback_query.answer(f"?? Starting bulk upload of {len(downloaded_paths)} videos...")
            await VideoUploader.upload_multiple(downloaded_paths, callback_query.message, user_id)

        elif data == "upload_bulk_images_downloaded":
            # Cancel auto-upload if pending
            from core.auto_scheduler import AutoScheduler
            await AutoScheduler.cancel_task(user_id, "image_bulk")
            
            # Try multiple possible keys for bulk images
            downloaded_paths = None
            
            # Try the main bulk images key
            downloaded_paths = user_downloads.get(f"{user_id}_bulk_images_downloaded")
            
            # If not found, try the mixed content key
            if not downloaded_paths:
                downloaded_paths = user_downloads.get(f"{user_id}_bulk_downloaded_images")
            
            # If still not found, try the all content key and filter images
            if not downloaded_paths:
                all_paths = user_downloads.get(f"{user_id}_bulk_downloaded_all", [])
                if all_paths:
                    # Filter only image files
                    downloaded_paths = [path for path in all_paths if path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]

            # Restart recovery fallback
            if not downloaded_paths:
                downloaded_paths = _fallback_image_paths()
            
            if not downloaded_paths:
                await callback_query.answer("? No downloaded images found!", show_alert=True)
                return
            
            logger.info(f"Found {len(downloaded_paths)} images for bulk upload")
            await callback_query.answer("?? Starting bulk image upload...")
            await ImageUploader.upload_multiple_images(downloaded_paths, callback_query.message, user_id)

        elif data == "upload_bulk_all_downloaded":
            # Cancel ALL potential auto-uploads
            from core.auto_scheduler import AutoScheduler
            await AutoScheduler.cancel_task(user_id, "video_bulk")
            await AutoScheduler.cancel_task(user_id, "image_bulk")
            await AutoScheduler.cancel_task(user_id, "mixed_bulk")
            
            # Get both videos and images from multiple sources
            video_paths = user_downloads.get(f"{user_id}_bulk_downloaded_videos", [])
            image_paths = user_downloads.get(f"{user_id}_bulk_downloaded_images", [])
            
            # Also check for multiple videos from single URL bulk storage
            if not video_paths:
                video_paths = user_downloads.get(f"{user_id}_bulk_videos", [])
            
            # If not found in separate keys, try the combined key
            if not video_paths and not image_paths:
                all_paths = user_downloads.get(f"{user_id}_bulk_downloaded_all", [])
                if all_paths:
                    # Separate videos and images
                    video_paths = [path for path in all_paths if path.lower().endswith(('.mp4', '.mkv', '.avi', '.mov'))]
                    image_paths = [path for path in all_paths if path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
            
            all_paths = video_paths + image_paths

            # Restart recovery fallback from disk
            if not all_paths:
                video_paths = _fallback_video_paths()
                image_paths = _fallback_image_paths()
                all_paths = video_paths + image_paths
            
            if not all_paths:
                await callback_query.answer("? No downloaded content found!", show_alert=True)
                return
            
            logger.info(f"Found {len(video_paths)} videos and {len(image_paths)} images for bulk upload")
            await callback_query.answer(f"?? Starting bulk upload of {len(all_paths)} files...")
            
            # Upload videos first, then images
            if video_paths:
                await VideoUploader.upload_multiple(video_paths, callback_query.message, user_id)
            
            if image_paths:
                # Small delay between video and image upload
                await asyncio.sleep(2)
                await ImageUploader.upload_multiple_images(image_paths, callback_query.message, user_id)

        # UPDATED: Single video upload - now handles multiple videos from single URL
        elif data.startswith("upload_single_"):
            video_key = data.replace("upload_single_", "")
            video_path = user_downloads.get(video_key)
            
            # Cancel auto-upload if pending (specifically single video key or bulk)
            from core.auto_scheduler import AutoScheduler
            if video_key == f"{user_id}_bulk_videos":
                await AutoScheduler.cancel_task(user_id, "video_bulk")
            else:
                await AutoScheduler.cancel_task(user_id, "video_single")
            
            # Check if this is a bulk videos key
            if video_key == f"{user_id}_bulk_videos":
                # Handle multiple videos from single URL
                video_paths = user_downloads.get(video_key, [])
                if not video_paths:
                    # Recover bulk list after restart.
                    video_paths = _fallback_video_paths()
                if video_paths and len(video_paths) > 0:
                    await callback_query.answer(f"?? Uploading {len(video_paths)} videos to group...", show_alert=False)
                    status_msg = await callback_query.message.reply_text(
                        f"?? **Starting Bulk Upload**\n\n"
                        f"?? Videos: {len(video_paths)} files\n\n"
                        f"? Preparing..."
                    )
                    await VideoUploader.upload_multiple(video_paths, status_msg, user_id)
                    return
            if not video_path:
                fallback_videos = _fallback_video_paths()
                if fallback_videos:
                    video_path = fallback_videos[0]
            if video_path and os.path.exists(video_path):
                # Single video upload (original behavior)
                await callback_query.answer("?? Uploading to group...", show_alert=False)
                
                video_name = os.path.basename(video_path)
                file_size = os.path.getsize(video_path)
                status_msg = await callback_query.message.reply_text(
                    f"?? **Starting Upload**\n\n"
                    f"?? File: `{video_name[:35]}...`\n"
                    f"?? Size: {Formatter.size(file_size)}\n\n"
                    f"? Preparing..."
                )
                
                # Pass the client from callback_query
                success, message = await VideoUploader.upload_to_group(
                    video_path, user_id, status_msg, client=callback_query.message._client
                )
                
                if success:
                    await status_msg.edit_text(
                        "? **Video Uploaded Successfully!**\n\n"
                        f"?? File: `{video_name}`\n"
                        f"?? Size: {Formatter.size(file_size)}",
                        reply_markup=Keyboards.back_to_main(user_id=user_id)
                    )
                    try:
                        await callback_query.message.edit_reply_markup(reply_markup=None)
                    except Exception:
                        pass
                else:
                    await status_msg.edit_text(
                        f"? **Upload Failed**\n\n"
                        f"Error: {message}",
                        reply_markup=Keyboards.back_to_main(user_id=user_id)
                    )
            else:
                await callback_query.answer("? Video file not found.", show_alert=True)
        
        elif data.startswith("upload_single_image_"):
            image_key = data.replace("upload_single_image_", "")
            image_path = user_downloads.get(image_key)
            if (not image_path or not os.path.exists(image_path)):
                fallback_images = _fallback_image_paths()
                if fallback_images:
                    image_path = fallback_images[0]
            
            if not image_path or not os.path.exists(image_path):
                await callback_query.answer("? Image file not found.", show_alert=True)
                return
            
            await callback_query.answer("?? Uploading to group...", show_alert=False)
            
            image_name = os.path.basename(image_path)
            file_size = os.path.getsize(image_path)
            status_msg = await callback_query.message.reply_text(
                f"?? **Starting Image Upload**\n\n"
                f"??? File: `{image_name[:35]}...`\n"
                f"?? Size: {Formatter.size(file_size)}\n\n"
                f"? Preparing..."
            )
            
            success, message = await ImageUploader.upload_single_image_to_group(
                image_path, user_id, status_msg, client=callback_query.message._client
            )
            
            if success:
                await status_msg.edit_text(
                    "? **Image Uploaded Successfully!**\n\n"
                    f"??? File: `{image_name}`\n"
                    f"?? Size: {Formatter.size(file_size)}",
                    reply_markup=Keyboards.back_to_main(user_id=user_id)
                )
            else:
                await status_msg.edit_text(
                    f"? **Upload Failed**\n\n"
                    f"Error: {message}",
                    reply_markup=Keyboards.back_to_main(user_id=user_id)
                )
        
        elif data.startswith("history:"):
            from core.database import history_db
            from core.formatting.history_formatter import format_history_message, format_export_message, format_clear_confirmation
            
            parts = data.split(":")
            
            if len(parts) == 3 and parts[1] == "clear" and parts[2] == "confirm":
                # Clear history confirmation
                total_count = history_db.get_total_count(user_id)
                if history_db.clear_user_history(user_id):
                    await callback_query.answer("? History cleared!", show_alert=True)
                    keyboard = Keyboards.main_menu(user_id=user_id)
                    await callback_query.message.edit_text(
                        f"??? **History Cleared**\n\n"
                        f"Successfully deleted {total_count} entries.\n\n"
                        f"Your download history is now empty.",
                        reply_markup=keyboard
                    )
                    logger.info(f"User {user_id} cleared {total_count} history entries")
                else:
                    await callback_query.answer("? Failed to clear history", show_alert=True)
            
            elif parts[1] == "clear":
                # Show clear confirmation
                total_count = history_db.get_total_count(user_id)
                if total_count == 0:
                    await callback_query.answer("No history to clear!", show_alert=True)
                    return
                
                keyboard = Keyboards.clear_history_confirmation(user_id=user_id)
                await callback_query.message.edit_text(
                    format_clear_confirmation(total_count),
                    reply_markup=keyboard
                )
            
            elif parts[1] == "export":
                # Export history
                all_history = history_db.get_all_user_history(user_id)
                
                if not all_history:
                    await callback_query.answer("No history to export!", show_alert=True)
                    return
                
                keyboard = Keyboards.export_format_selection(user_id=user_id)
                await callback_query.message.edit_text(
                    format_export_message(len(all_history)),
                    reply_markup=keyboard
                )
            
            else:
                # View history (pagination)
                try:
                    page = int(parts[1])
                except (ValueError, IndexError):
                    page = 1
                
                # Get history from database
                per_page = 10
                offset = (page - 1) * per_page
                history = history_db.get_user_history(user_id, limit=per_page, offset=offset)
                total_count = history_db.get_total_count(user_id)
                total_pages = max(1, (total_count + per_page - 1) // per_page)
                
                # Format message
                message = format_history_message(history, page, total_pages, total_count)
                
                # Send with pagination keyboard
                keyboard = Keyboards.history_pagination(page, total_pages, user_id=user_id)
                await callback_query.message.edit_text(
                    message,
                    reply_markup=keyboard,
                    disable_web_page_preview=True
                )
                
                await callback_query.answer(f"?? Page {page}/{total_pages}")
        
        # Export format selection
        elif data.startswith("export:"):
            from core.database import history_db
            from core.export.history_exporter import export_to_csv, export_to_text
            
            format_type = data.split(":")[1]
            
            # Get all history
            all_history = history_db.get_all_user_history(user_id)
            
            if not all_history:
                await callback_query.answer("No history to export!", show_alert=True)
                return
            
            # Show processing message
            await callback_query.answer("?? Generating export file...")
            
            # Generate file
            if format_type == 'csv':
                file_data = export_to_csv(all_history)
                filename = f"download_history_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                caption = f"?? **Download History (CSV)**\n\n{len(all_history)} total entries"
            else:  # txt
                file_data = export_to_text(all_history)
                filename = f"download_history_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                caption = f"?? **Download History (Text)**\n\n{len(all_history)} total entries"
            
            # Send file
            await callback_query.message.reply_document(
                document=file_data,
                file_name=filename,
                caption=caption
            )
            
            # Delete the export selection message
            try:
                await callback_query.message.delete()
            except Exception:
                pass
            
            await callback_query.answer("? History exported!")
            logger.info(f"User {user_id} exported {len(all_history)} history entries as {format_type}")

        # ── Storage / Cleanup callbacks ────────────────────────────────────────
        elif data.startswith("cleanup:"):
            from core.media_cleaner import (
                get_disk_report, delete_old_files, AUTO_CLEANUP_MIN_AGE_DAYS
            )

            action = data.split(":", 1)[1]

            if action == "scan":
                await callback_query.answer("🔍 Scanning...")
                report = await asyncio.to_thread(get_disk_report)
                try:
                    await callback_query.message.edit_text(
                        report,
                        reply_markup=Keyboards.cleanup_menu(user_id, AUTO_CLEANUP_MIN_AGE_DAYS),
                        disable_web_page_preview=True,
                    )
                except MessageNotModified:
                    pass

            elif action == "confirm":
                await callback_query.answer()
                await callback_query.message.edit_text(
                    f"⚠️ **Confirm Cleanup**\n\n"
                    f"This will permanently delete all downloaded media files "
                    f"older than **{AUTO_CLEANUP_MIN_AGE_DAYS} days** from "
                    f"`media/videos` and `media/images`.\n\n"
                    f"Files currently in use will **not** be touched.\n\n"
                    f"Are you sure?",
                    reply_markup=Keyboards.cleanup_confirm(user_id, AUTO_CLEANUP_MIN_AGE_DAYS),
                )

            elif action == "delete":
                await callback_query.answer("♻️ Cleaning up...")
                try:
                    result = await asyncio.to_thread(
                        delete_old_files, AUTO_CLEANUP_MIN_AGE_DAYS
                    )
                    if result.deleted_files == 0:
                        status = "✅ **Nothing to clean!**\n\nNo files older than " \
                                 f"{AUTO_CLEANUP_MIN_AGE_DAYS} days were found."
                    else:
                        err_note = f"\n⚠️ {result.errors} error(s) skipped." if result.errors else ""
                        status = (
                            f"✅ **Cleanup Complete!**\n\n"
                            f"🗑️ Deleted: **{result.deleted_files}** file(s)\n"
                            f"💾 Freed: **{result.freed_mb:.1f} MB**"
                            f"{err_note}"
                        )
                    logger.info(
                        f"User {user_id} triggered cleanup: "
                        f"{result.deleted_files} files, {result.freed_mb:.1f} MB freed"
                    )
                    # Show updated report after deletion
                    report = await asyncio.to_thread(get_disk_report)
                    await callback_query.message.edit_text(
                        status + "\n\n" + report,
                        reply_markup=Keyboards.cleanup_menu(user_id, AUTO_CLEANUP_MIN_AGE_DAYS),
                        disable_web_page_preview=True,
                    )
                except Exception as e:
                    logger.error(f"Cleanup callback error: {e}")
                    await callback_query.message.edit_text(
                        f"❌ Cleanup failed: {e}",
                        reply_markup=Keyboards.back_to_main(user_id=user_id),
                    )





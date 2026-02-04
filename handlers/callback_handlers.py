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

# Get logger
logger = logging.getLogger("XVideoBot")

from core.file_manager import FileManager
from core.uploader import VideoUploader
from core.image_downloader import ImageDownloader
from ui.messages import Messages
from ui.keyboards import Keyboards
from ui.languages import language_manager
from models.enums import user_downloads, user_selections
from utils.formatters import Formatter
from core.image_uploader import ImageUploader

def get_text(user_id: int, key: str) -> str:
    """Helper function to get localized text"""
    return language_manager.get_text(user_id, key)

def setup_callback_handlers(app: Client):
    """Setup all callback handlers"""
    
    @app.on_callback_query()
    async def callback_handler(client: Client, callback_query: CallbackQuery) -> None:
        """Handle callback queries"""
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        # Navigation callbacks
        if data == "download":
            keyboard = Keyboards.cancel_button()
            await callback_query.message.edit_text(Messages.download_prompt(), reply_markup=keyboard)
        
        elif data == "download_images":
            keyboard = Keyboards.cancel_button()
            await callback_query.message.edit_text(Messages.image_download_prompt(), reply_markup=keyboard)
        
        elif data == "about":
            keyboard = Keyboards.back_to_main()
            await callback_query.message.edit_text(Messages.about_text(), reply_markup=keyboard)
        
        elif data == "help":
            keyboard = Keyboards.back_to_main()
            await callback_query.message.edit_text(Messages.help_text(), reply_markup=keyboard)
        
        elif data == "stats":
            from core.log_manager import LogManager
            stats_info = LogManager.get_stats()
            log = stats_info['log_data']
            sync_status = ""
            if not stats_info['synced']:
                sync_status = f"\n\n⚠️ Log entries: {stats_info['log_entries']} | Folder videos: {stats_info['actual_videos']}"
            keyboard = Keyboards.back_to_main()
            await callback_query.message.edit_text(Messages.stats_text(log) + sync_status, reply_markup=keyboard)
        
        elif data == "settings":
            keyboard = Keyboards.settings_menu()
            await callback_query.message.edit_text(Messages.settings_text(), reply_markup=keyboard)
        
        elif data == "main_menu":
            keyboard = Keyboards.main_menu()
            user_name = callback_query.from_user.first_name
            await callback_query.message.edit_text(Messages.welcome(user_name, user_id=user_id), reply_markup=keyboard)
        
        elif data == "cancel":
            keyboard = Keyboards.main_menu()
            await callback_query.message.edit_text(Messages.action_cancelled(), reply_markup=keyboard)
        
        elif data == "version":
            from handlers.command_handlers import get_version_info
            keyboard = Keyboards.back_to_main()
            await callback_query.message.edit_text(get_version_info(), reply_markup=keyboard)
        
        # Bulk upload callbacks
        elif data == "bulk_upload":
            videos = FileManager.get_all_videos()
            if not videos:
                await callback_query.answer("❌ No videos found in download folder!", show_alert=True)
                return
            
            video_dicts = [{'filename': v.filename, 'filepath': v.filepath, 'size': v.size_mb} for v in videos]
            user_downloads[f"{user_id}_videos"] = video_dicts
            if user_id not in user_selections:
                user_selections[user_id] = set()
            
            current_page = user_downloads.get(f"{user_id}_page", 0)
            keyboard = Keyboards.video_list_keyboard(video_dicts, user_selections.get(user_id, set()), page=current_page)
            await callback_query.message.edit_text(Messages.bulk_upload_prompt(len(videos)), reply_markup=keyboard)
        
        elif data == "bulk_upload_images":
            images = FileManager.get_all_images()
            if not images:
                await callback_query.answer("❌ No images found in download folder!", show_alert=True)
                return
            
            image_dicts = [{'filename': img.filename, 'filepath': img.filepath, 'size': img.size_mb} for img in images]
            user_downloads[f"{user_id}_images"] = image_dicts
            if user_id not in user_selections:
                user_selections[user_id] = set()
            
            current_page = user_downloads.get(f"{user_id}_image_page", 0)
            keyboard = Keyboards.image_list_keyboard(image_dicts, user_selections.get(user_id, set()), page=current_page)
            await callback_query.message.edit_text(Messages.bulk_image_upload_prompt(len(images)), reply_markup=keyboard)
        
        elif data.startswith("sel_") and data != "sel_all":
            try:
                video_idx = int(data.replace("sel_", ""))
            except ValueError:
                await callback_query.answer("❌ Invalid selection", show_alert=True)
                return
            
            if user_id not in user_selections:
                user_selections[user_id] = set()
            
            if video_idx in user_selections[user_id]:
                user_selections[user_id].remove(video_idx)
                await callback_query.answer("❌ Deselected")
            else:
                user_selections[user_id].add(video_idx)
                await callback_query.answer("✅ Selected")
            
            videos = user_downloads.get(f"{user_id}_videos", [])
            current_page = user_downloads.get(f"{user_id}_page", 0)
            keyboard = Keyboards.video_list_keyboard(videos, user_selections[user_id], page=current_page)
            
            try:
                await callback_query.message.edit_reply_markup(reply_markup=keyboard)
            except Exception:
                pass
        
        elif data.startswith("img_sel_") and data != "img_sel_all":
            try:
                image_idx = int(data.replace("img_sel_", ""))
            except ValueError:
                await callback_query.answer("❌ Invalid selection", show_alert=True)
                return
            
            if user_id not in user_selections:
                user_selections[user_id] = set()
            
            if image_idx in user_selections[user_id]:
                user_selections[user_id].remove(image_idx)
                await callback_query.answer("❌ Deselected")
            else:
                user_selections[user_id].add(image_idx)
                await callback_query.answer("✅ Selected")
            
            images = user_downloads.get(f"{user_id}_images", [])
            current_page = user_downloads.get(f"{user_id}_image_page", 0)
            keyboard = Keyboards.image_list_keyboard(images, user_selections[user_id], page=current_page)
            
            try:
                await callback_query.message.edit_reply_markup(reply_markup=keyboard)
            except Exception:
                pass
        
        elif data == "sel_all":
            videos = user_downloads.get(f"{user_id}_videos", [])
            user_selections[user_id] = set(range(len(videos)))
            keyboard = Keyboards.video_list_keyboard(videos, user_selections[user_id], page=0)
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
            await callback_query.answer(f"✅ Selected all {len(videos)} videos")
        
        elif data == "img_sel_all":
            images = user_downloads.get(f"{user_id}_images", [])
            user_selections[user_id] = set(range(len(images)))
            keyboard = Keyboards.image_list_keyboard(images, user_selections[user_id], page=0)
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
            await callback_query.answer(f"✅ Selected all {len(images)} images")
        
        elif data == "desel_all":
            videos = user_downloads.get(f"{user_id}_videos", [])
            user_selections[user_id] = set()
            keyboard = Keyboards.video_list_keyboard(videos, user_selections[user_id], page=0)
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
            await callback_query.answer("❌ Deselected all videos")
        
        elif data == "img_desel_all":
            images = user_downloads.get(f"{user_id}_images", [])
            user_selections[user_id] = set()
            keyboard = Keyboards.image_list_keyboard(images, user_selections[user_id], page=0)
            await callback_query.message.edit_reply_markup(reply_markup=keyboard)
            await callback_query.answer("❌ Deselected all images")
        
        elif data.startswith("pg_"):
            try:
                page = int(data.replace("pg_", ""))
            except ValueError:
                return
            
            videos = user_downloads.get(f"{user_id}_videos", [])
            keyboard = Keyboards.video_list_keyboard(videos, user_selections.get(user_id, set()), page=page)
            
            try:
                await callback_query.message.edit_reply_markup(reply_markup=keyboard)
                await callback_query.answer(f"📄 Page {page + 1}")
            except Exception:
                pass
        
        elif data.startswith("img_pg_"):
            try:
                page = int(data.replace("img_pg_", ""))
            except ValueError:
                return
            
            images = user_downloads.get(f"{user_id}_images", [])
            keyboard = Keyboards.image_list_keyboard(images, user_selections.get(user_id, set()), page=page)
            
            try:
                await callback_query.message.edit_reply_markup(reply_markup=keyboard)
                await callback_query.answer(f"📄 Page {page + 1}")
            except Exception:
                pass
        
        elif data == "confirm_upload":
            if user_id not in user_selections or not user_selections[user_id]:
                await callback_query.answer("❌ No videos selected!", show_alert=True)
                return
            
            videos = user_downloads.get(f"{user_id}_videos", [])
            selected_files = [videos[idx]['filepath'] for idx in user_selections[user_id] if idx < len(videos)]
            
            if not selected_files:
                await callback_query.answer("❌ No valid videos selected!", show_alert=True)
                return
            
            await callback_query.answer("📤 Starting upload...")
            await VideoUploader.upload_multiple(selected_files, callback_query.message, user_id)
            
            user_selections[user_id] = set()
            if f"{user_id}_videos" in user_downloads:
                del user_downloads[f"{user_id}_videos"]
        
        elif data == "confirm_image_upload":
            if user_id not in user_selections or not user_selections[user_id]:
                await callback_query.answer("❌ No images selected!", show_alert=True)
                return
            
            images = user_downloads.get(f"{user_id}_images", [])
            selected_files = [images[idx]['filepath'] for idx in user_selections[user_id] if idx < len(images)]
            
            if not selected_files:
                await callback_query.answer("❌ No valid images selected!", show_alert=True)
                return
            
            await callback_query.answer("📤 Starting image upload...")
            await ImageUploader.upload_multiple_images(selected_files, callback_query.message, user_id)
            
            user_selections[user_id] = set()
            if f"{user_id}_images" in user_downloads:
                del user_downloads[f"{user_id}_images"]
        
        # Upload callbacks - UPDATED TO SUPPORT MULTIPLE VIDEOS PER URL
        elif data.startswith("upload_to_group_"):
            # Cancel auto-upload if pending
            from core.auto_scheduler import AutoScheduler
            AutoScheduler.cancel_task(user_id, "video_single")
            AutoScheduler.cancel_task(user_id, "video_bulk")
            
            # Handle both single video and multiple videos
            video_path = user_downloads.get(user_id)
            
            # Check if it's a single video path or multiple videos
            if isinstance(video_path, list) and len(video_path) > 0:
                # Multiple videos from single URL
                await callback_query.answer(f"📤 Uploading {len(video_path)} videos to group...", show_alert=False)
                
                status_msg = await callback_query.message.reply_text(
                    f"📤 **Starting Bulk Upload**\n\n"
                    f"🎬 Videos: {len(video_path)} files\n\n"
                    f"⏳ Preparing..."
                )
                
                # Upload all videos from this URL
                await VideoUploader.upload_multiple(video_path, status_msg, user_id)
                
            elif video_path and os.path.exists(video_path):
                # Single video (original behavior)
                await callback_query.answer("📤 Uploading to group...", show_alert=False)
                
                video_name = os.path.basename(video_path)
                file_size = os.path.getsize(video_path)
                status_msg = await callback_query.message.reply_text(
                    f"📤 **Starting Upload**\n\n"
                    f"📁 File: `{video_name[:35]}...`\n"
                    f"💾 Size: {Formatter.size(file_size)}\n\n"
                    f"⏳ Preparing..."
                )
                
                # Pass the client from callback_query
                success, message = await VideoUploader.upload_to_group(
                    video_path, user_id, status_msg, client=callback_query.message._client
                )
                
                if success:
                    await status_msg.edit_text(
                        "✅ **Video Uploaded to Group Successfully!**\n\n"
                        f"📁 File: `{video_name}`\n"
                        f"💾 Size: {Formatter.size(file_size)}\n\n"
                        "The video has been shared with the group.\n\n"
                        "Want to download another video?",
                        reply_markup=Keyboards.back_to_main()
                    )
                else:
                    await status_msg.edit_text(
                        f"❌ **Upload Failed**\n\n"
                        f"Error: {message}\n\n"
                        "Please try again later.",
                        reply_markup=Keyboards.back_to_main()
                    )
            else:
                await callback_query.answer("❌ Video file not found. Please download again.", show_alert=True)

        elif data.startswith("upload_images_to_group_"):
            # Cancel auto-upload if pending
            from core.auto_scheduler import AutoScheduler
            AutoScheduler.cancel_task(user_id, "image_bulk")
            
            image_paths = user_downloads.get(user_id, [])
            
            if not image_paths or (isinstance(image_paths, str) and not os.path.exists(image_paths)):
                await callback_query.answer("❌ Image files not found. Please download again.", show_alert=True)
                return
            
            await callback_query.answer("📤 Uploading images to group...", show_alert=False)
            
            if isinstance(image_paths, str):
                image_paths = [image_paths]
            
            status_msg = await callback_query.message.reply_text(
                f"📤 **Starting Image Upload**\n\n"
                f"🖼️ Files: {len(image_paths)} images\n\n"
                f"⏳ Preparing..."
            )
            
            success, message = await ImageUploader.upload_images_to_group(
                image_paths, user_id, status_msg, client=callback_query.message._client
            )
            
            if success:
                await status_msg.edit_text(
                    "✅ **Images Uploaded to Group Successfully!**\n\n"
                    f"🖼️ Uploaded: {len(image_paths)} images\n\n"
                    "The images have been shared with the group.\n\n"
                    "Want to download more images?",
                    reply_markup=Keyboards.back_to_main()
                )
            else:
                await status_msg.edit_text(
                    f"❌ **Upload Failed**\n\n"
                    f"Error: {message}\n\n"
                    "Please try again later.",
                    reply_markup=Keyboards.back_to_main()
                )

        elif data == "upload_bulk_downloaded" or data == "upload_bulk_videos_downloaded":
            # Cancel auto-upload if pending
            from core.auto_scheduler import AutoScheduler
            AutoScheduler.cancel_task(user_id, "video_bulk")
            
            # Handle multiple videos from bulk downloads
            downloaded_paths = user_downloads.get(f"{user_id}_bulk_downloaded", [])
            
            # Also check for multiple videos from single URL
            if not downloaded_paths:
                downloaded_paths = user_downloads.get(f"{user_id}_bulk_videos", [])
            
            if not downloaded_paths:
                await callback_query.answer("❌ No downloaded videos found!", show_alert=True)
                return
            
            await callback_query.answer(f"📤 Starting bulk upload of {len(downloaded_paths)} videos...")
            await VideoUploader.upload_multiple(downloaded_paths, callback_query.message, user_id)

        elif data == "upload_bulk_images_downloaded":
            # Cancel auto-upload if pending
            from core.auto_scheduler import AutoScheduler
            AutoScheduler.cancel_task(user_id, "image_bulk")
            
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
            
            if not downloaded_paths:
                await callback_query.answer("❌ No downloaded images found!", show_alert=True)
                return
            
            logger.info(f"Found {len(downloaded_paths)} images for bulk upload")
            await callback_query.answer("📤 Starting bulk image upload...")
            await ImageUploader.upload_multiple_images(downloaded_paths, callback_query.message, user_id)

        elif data == "upload_bulk_all_downloaded":
            # Cancel ALL potential auto-uploads
            from core.auto_scheduler import AutoScheduler
            AutoScheduler.cancel_task(user_id, "video_bulk")
            AutoScheduler.cancel_task(user_id, "image_bulk")
            AutoScheduler.cancel_task(user_id, "mixed_bulk")
            
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
            
            if not all_paths:
                await callback_query.answer("❌ No downloaded content found!", show_alert=True)
                return
            
            logger.info(f"Found {len(video_paths)} videos and {len(image_paths)} images for bulk upload")
            await callback_query.answer(f"📤 Starting bulk upload of {len(all_paths)} files...")
            
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
                AutoScheduler.cancel_task(user_id, "video_bulk")
            else:
                AutoScheduler.cancel_task(user_id, "video_single")
            
            # Check if this is a bulk videos key
            if video_key == f"{user_id}_bulk_videos":
                # Handle multiple videos from single URL
                video_paths = user_downloads.get(video_key, [])
                if video_paths and len(video_paths) > 0:
                    await callback_query.answer(f"📤 Uploading {len(video_paths)} videos to group...", show_alert=False)
                    status_msg = await callback_query.message.reply_text(
                        f"📤 **Starting Bulk Upload**\n\n"
                        f"🎬 Videos: {len(video_paths)} files\n\n"
                        f"⏳ Preparing..."
                    )
                    await VideoUploader.upload_multiple(video_paths, status_msg, user_id)
                    return
            elif video_path and os.path.exists(video_path):
                # Single video upload (original behavior)
                await callback_query.answer("📤 Uploading to group...", show_alert=False)
                
                video_name = os.path.basename(video_path)
                file_size = os.path.getsize(video_path)
                status_msg = await callback_query.message.reply_text(
                    f"📤 **Starting Upload**\n\n"
                    f"📁 File: `{video_name[:35]}...`\n"
                    f"💾 Size: {Formatter.size(file_size)}\n\n"
                    f"⏳ Preparing..."
                )
                
                # Pass the client from callback_query
                success, message = await VideoUploader.upload_to_group(
                    video_path, user_id, status_msg, client=callback_query.message._client
                )
                
                if success:
                    await status_msg.edit_text(
                        "✅ **Video Uploaded Successfully!**\n\n"
                        f"📁 File: `{video_name}`\n"
                        f"💾 Size: {Formatter.size(file_size)}",
                        reply_markup=Keyboards.back_to_main()
                    )
                    try:
                        await callback_query.message.edit_reply_markup(reply_markup=None)
                    except Exception:
                        pass
                else:
                    await status_msg.edit_text(
                        f"❌ **Upload Failed**\n\n"
                        f"Error: {message}",
                        reply_markup=Keyboards.back_to_main()
                    )
            else:
                await callback_query.answer("❌ Video file not found.", show_alert=True)
        
        elif data.startswith("upload_single_image_"):
            image_key = data.replace("upload_single_image_", "")
            image_path = user_downloads.get(image_key)
            
            if not image_path or not os.path.exists(image_path):
                await callback_query.answer("❌ Image file not found.", show_alert=True)
                return
            
            await callback_query.answer("📤 Uploading to group...", show_alert=False)
            
            image_name = os.path.basename(image_path)
            file_size = os.path.getsize(image_path)
            status_msg = await callback_query.message.reply_text(
                f"📤 **Starting Image Upload**\n\n"
                f"🖼️ File: `{image_name[:35]}...`\n"
                f"💾 Size: {Formatter.size(file_size)}\n\n"
                f"⏳ Preparing..."
            )
            
            success, message = await ImageUploader.upload_single_image_to_group(
                image_path, user_id, status_msg, client=callback_query.message._client
            )
            
            if success:
                await status_msg.edit_text(
                    "✅ **Image Uploaded Successfully!**\n\n"
                    f"🖼️ File: `{image_name}`\n"
                    f"💾 Size: {Formatter.size(file_size)}",
                    reply_markup=Keyboards.back_to_main()
                )
            else:
                await status_msg.edit_text(
                    f"❌ **Upload Failed**\n\n"
                    f"Error: {message}",
                    reply_markup=Keyboards.back_to_main()
                )
        
        elif data.startswith("history:"):
            from core.database import history_db
            from utils.history_formatter import format_history_message, format_export_message, format_clear_confirmation
            
            parts = data.split(":")
            
            if len(parts) == 3 and parts[1] == "clear" and parts[2] == "confirm":
                # Clear history confirmation
                total_count = history_db.get_total_count(user_id)
                if history_db.clear_user_history(user_id):
                    await callback_query.answer("✅ History cleared!", show_alert=True)
                    keyboard = Keyboards.main_menu()
                    await callback_query.message.edit_text(
                        f"🗑️ **History Cleared**\n\n"
                        f"Successfully deleted {total_count} entries.\n\n"
                        f"Your download history is now empty.",
                        reply_markup=keyboard
                    )
                    logger.info(f"User {user_id} cleared {total_count} history entries")
                else:
                    await callback_query.answer("❌ Failed to clear history", show_alert=True)
            
            elif parts[1] == "clear":
                # Show clear confirmation
                total_count = history_db.get_total_count(user_id)
                if total_count == 0:
                    await callback_query.answer("No history to clear!", show_alert=True)
                    return
                
                keyboard = Keyboards.clear_history_confirmation()
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
                
                keyboard = Keyboards.export_format_selection()
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
                keyboard = Keyboards.history_pagination(page, total_pages)
                await callback_query.message.edit_text(
                    message,
                    reply_markup=keyboard,
                    disable_web_page_preview=True
                )
                
                await callback_query.answer(f"📜 Page {page}/{total_pages}")
        
        # Export format selection
        elif data.startswith("export:"):
            from core.database import history_db
            from utils.history_exporter import export_to_csv, export_to_text
            
            format_type = data.split(":")[1]
            
            # Get all history
            all_history = history_db.get_all_user_history(user_id)
            
            if not all_history:
                await callback_query.answer("No history to export!", show_alert=True)
                return
            
            # Show processing message
            await callback_query.answer("📊 Generating export file...")
            
            # Generate file
            if format_type == 'csv':
                file_data = export_to_csv(all_history)
                filename = f"download_history_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                caption = f"📊 **Download History (CSV)**\n\n{len(all_history)} total entries"
            else:  # txt
                file_data = export_to_text(all_history)
                filename = f"download_history_{user_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                caption = f"📄 **Download History (Text)**\n\n{len(all_history)} total entries"
            
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
            
            await callback_query.answer("✅ History exported!")
            logger.info(f"User {user_id} exported {len(all_history)} history entries as {format_type}")


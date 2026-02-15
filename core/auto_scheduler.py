import asyncio
import time
from typing import Union, List, Optional, Any
from pyrogram import Client
from pyrogram.types import Message
from core.uploader import VideoUploader
from core.image_uploader import ImageUploader
from core.uploader import safe_edit_text
from ui.keyboards import Keyboards

class AutoScheduler:
    """
    Manages auto-upload timers and tasks.
    Singleton-like usage.
    """
    _tasks = {}  # Stores current tasks: {user_id_type_id: asyncio.Task}

    @staticmethod
    def get_task_key(user_id: int, type_id: str) -> str:
        return f"{user_id}_{type_id}"

    @staticmethod
    async def start_timer(
        client: Client,
        message: Message,
        user_id: int,
        content_type: str,  # "video_single", "video_bulk", "image_bulk"
        content_path: Union[str, List[str]],
        duration: int = 120
    ):
        """
        Starts a countdown timer for auto-upload.
        """
        task_key = AutoScheduler.get_task_key(user_id, content_type)
        
        # Cancel existing task if any
        if task_key in AutoScheduler._tasks:
            AutoScheduler._tasks[task_key].cancel()

        # Create new task
        task = asyncio.create_task(
            AutoScheduler._countdown_and_upload(
                client, message, user_id, content_type, content_path, duration, task_key
            )
        )
        AutoScheduler._tasks[task_key] = task

    @staticmethod
    def cancel_task(user_id: int, content_type: str):
        """
        Cancels a pending auto-upload task.
        """
        task_key = AutoScheduler.get_task_key(user_id, content_type)
        if task_key in AutoScheduler._tasks:
            task = AutoScheduler._tasks[task_key]
            if not task.done():
                task.cancel()
            del AutoScheduler._tasks[task_key]
            return True
        return False

    @staticmethod
    async def _countdown_and_upload(
        client: Client,
        message: Message,
        user_id: int,
        content_type: str,
        content_path: Union[str, List[str]],
        duration: int,
        task_key: str
    ):
        """
        The internal loop handling countdown and triggering upload.
        """
        original_caption = message.caption or message.text or ""
        target_chat_id = message.chat.id
        # Remove any existing clean signature if it exists to avoid duplication issues
        # (Though we usually just append)

        end_time = time.time() + duration
        last_update_time = time.time()

        try:
            from pyrogram.errors import FloodWait, MessageNotModified
            
            # Adaptive update intervals to prevent FloodWait
            # > 30s remaining: Update every 5s
            # < 30s remaining: Update every 3s
            # < 10s remaining: Update every 2s
            
            while time.time() < end_time:
                remaining = int(end_time - time.time())
                
                # Determine safe update interval
                if remaining > 30:
                    update_interval = 5
                elif remaining > 10:
                    update_interval = 3
                else:
                    update_interval = 2
                
                if time.time() - last_update_time >= update_interval:
                    mins, secs = divmod(remaining, 60)
                    timer_text = f"\n\n⏳ **Auto-sending to Group in {mins}:{secs:02d}**"
                    
                    try:
                        # Determine content to update (caption vs text)
                        if message.caption:
                            # Append to original caption (most robust method)
                            await message.edit_caption(
                                caption=original_caption + timer_text,
                                reply_markup=message.reply_markup
                            )
                        else:
                            await message.edit_text(
                                text=original_caption + timer_text,
                                reply_markup=message.reply_markup,
                                disable_web_page_preview=True
                            )
                        last_update_time = time.time()
                        
                    except FloodWait as e:
                        # CRITICAL: Respect Telegram's wait request
                        print(f"⚠️ Timer FloodWait: Pausing updates for {e.value}s")
                        await asyncio.sleep(e.value)
                        last_update_time = time.time() # Reset to avoid instant retry
                    except MessageNotModified:
                        pass
                    except Exception as e:
                        # print(f"Timer update error: {e}")
                        pass
                        
                await asyncio.sleep(1) # Check cancellation every second

            # Time is up!
            # Notify user
            try:
                if message.caption:
                    await message.edit_caption(
                        caption=original_caption + "\n\n🚀 **Auto-sending now...**",
                        reply_markup=message.reply_markup
                    )
                else:
                    await message.edit_text(
                        text=original_caption + "\n\n🚀 **Auto-sending now...**",
                        reply_markup=message.reply_markup,
                        disable_web_page_preview=True
                    )
            except:
                pass

            # Trigger Upload
            if content_type == "video_single":
                # status_msg=message might overwrite the video message, better send a new small status msg?
                # Or re-use. VideoUploader updates the status_msg.
                # If we pass 'message', VideoUploader might try to edit it. 
                # If 'message' is the video itself, we can't 'edit' it into a text status easily if type differs.
                # VideoUploader expects a text message to edit usually. 
                
                # So we should send a new status message "Auto uploading..."
                status_msg = await client.send_message(
                    chat_id=target_chat_id,
                    text="🚀 **Auto-upload triggered...**"
                )
                
                # Check upload result and update status accordingly
                success, result_msg = await VideoUploader.upload_to_group(content_path, user_id, status_msg, client)
                
                if success:
                    # Construct success message info (like file name/size if available)
                    # For simplicity, we just show success. 
                    # If we wanted details, we'd need to re-fetch/pass them or let VideoUploader helper do it.
                    # VideoUploader.upload_to_group returns (True, "Upload successful") but doesn't edit status to final state.
                    
                    filename = content_path.split("/")[-1] if "/" in content_path else content_path
                    try:
                        import os
                        from utils.formatters import Formatter
                        file_size = os.path.getsize(content_path)
                        size_text = Formatter.size(file_size)
                    except:
                        size_text = "Unknown"
                        
                    await safe_edit_text(
                        status_msg,
                        "✅ **Video Uploaded Successfully!**\n\n"
                        f"📁 File: `{filename}`\n"
                        f"💾 Size: {size_text}\n\n"
                        "The video has been shared with the group.",
                        reply_markup=Keyboards.back_to_main()
                    )
                else:
                    await safe_edit_text(
                        status_msg,
                        f"❌ **Upload Failed**\n\n"
                        f"Error: {result_msg}",
                        reply_markup=Keyboards.back_to_main()
                    )

            elif content_type == "video_bulk":
                status_msg = await client.send_message(
                    chat_id=target_chat_id,
                    text="🚀 **Bulk Auto-upload triggered...**"
                )
                await VideoUploader.upload_multiple(content_path, status_msg, user_id)

            elif content_type == "image_bulk":
                status_msg = await client.send_message(
                    chat_id=target_chat_id,
                    text="🚀 **Image Auto-upload triggered...**"
                )
                await ImageUploader.upload_multiple_images(content_path, status_msg, user_id)

            elif content_type == "mixed_bulk":
                # content_path is expected to be a dict or tuple containing lists: {'videos': [], 'images': []}
                # But start_timer args type hint say Union[str, List[str]]. 
                # We can pass a list of ALL paths, but we need to distinguish them.
                # Or pass a dict. The type hint in start_timer is just a hint, python is dynamic.
                
                status_msg = await client.send_message(
                    chat_id=target_chat_id,
                    text="🚀 **Mixed Content Auto-upload triggered...**"
                )
                
                video_paths = content_path.get('videos', [])
                image_paths = content_path.get('images', [])
                
                if video_paths:
                    await VideoUploader.upload_multiple(video_paths, status_msg, user_id)
                
                if image_paths:
                    if video_paths:
                        await asyncio.sleep(2)
                    await ImageUploader.upload_multiple_images(image_paths, status_msg, user_id)

        except asyncio.CancelledError:
            # Clean up the timer text if cancelled?
            # User clicked upload manually, so that flow handles UI updates.
            pass
        except Exception as e:
            print(f"Auto-upload scheduler error: {e}")
        finally:
            # Remove from task list
            if task_key in AutoScheduler._tasks:
                del AutoScheduler._tasks[task_key]

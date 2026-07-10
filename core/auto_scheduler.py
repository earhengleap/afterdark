import asyncio
import logging
import time
from typing import Union, List, Optional, Any, Dict
from pyrogram import Client
from pyrogram.types import Message
from core.uploader import VideoUploader
from core.image_uploader import ImageUploader
from core.uploader import safe_edit_text
from resources.keyboards import Keyboards

logger = logging.getLogger("AfterDark.AutoScheduler")


class AutoScheduler:
    """
    Manages auto-upload timers and tasks.

    Class-level _tasks has been replaced with a module-level dict protected
    by an asyncio.Lock so concurrent coroutines cannot corrupt it.
    """

    # Module-level task registry: {task_key: asyncio.Task}
    _tasks: Dict[str, asyncio.Task] = {}
    _lock: asyncio.Lock = asyncio.Lock()

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
        Any previously running timer for the same user+type is cancelled first.
        """
        task_key = AutoScheduler.get_task_key(user_id, content_type)

        async with AutoScheduler._lock:
            existing = AutoScheduler._tasks.get(task_key)
            if existing and not existing.done():
                existing.cancel()

            task = asyncio.create_task(
                AutoScheduler._countdown_and_upload(
                    client, message, user_id, content_type, content_path, duration, task_key
                )
            )
            AutoScheduler._tasks[task_key] = task

    @staticmethod
    async def cancel_task(user_id: int, content_type: str) -> bool:
        """
        Cancels a pending auto-upload task.
        Returns True if a task was found and cancelled.
        """
        task_key = AutoScheduler.get_task_key(user_id, content_type)
        async with AutoScheduler._lock:
            task = AutoScheduler._tasks.get(task_key)
            if task:
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

        end_time = time.time() + duration
        last_update_time = time.time()

        try:
            from pyrogram.errors import FloodWait, MessageNotModified

            # Adaptive update intervals to prevent FloodWait:
            # > 30s remaining: update every 5 s
            # < 30s remaining: update every 3 s
            # < 10s remaining: update every 2 s

            while time.time() < end_time:
                remaining = int(end_time - time.time())

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
                        if message.caption:
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
                        logger.warning(f"Timer FloodWait: pausing updates for {e.value}s")
                        await asyncio.sleep(e.value)
                        last_update_time = time.time()
                    except MessageNotModified:
                        pass
                    except Exception:
                        pass

                await asyncio.sleep(1)  # Check cancellation every second

            # Time is up — notify user
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
            except Exception:
                pass

            # Trigger Upload
            if content_type == "video_single":
                status_msg = await client.send_message(
                    chat_id=target_chat_id,
                    text="🚀 **Auto-upload triggered...**"
                )

                success, result_msg = await VideoUploader.upload_to_group(content_path, user_id, status_msg, client)

                if success:
                    filename = content_path.split("/")[-1] if "/" in content_path else content_path
                    try:
                        import os
                        from core.formatting.formatters import Formatter
                        file_size = os.path.getsize(content_path)
                        size_text = Formatter.size(file_size)
                    except Exception:
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
                        f"❌ **Upload Failed**\n\nError: {result_msg}",
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
                # content_path is a dict: {'videos': [...], 'images': [...]}
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
            # User clicked upload manually — that flow handles UI updates.
            pass
        except Exception as e:
            logger.error(f"Auto-upload scheduler error: {e}", exc_info=True)
        finally:
            # Remove from task registry under lock
            async with AutoScheduler._lock:
                AutoScheduler._tasks.pop(task_key, None)

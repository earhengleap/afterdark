"""
Video upload functionality.
"""

import asyncio
import os
import time
from typing import List, Optional, Tuple

from pyrogram import Client
from pyrogram.errors import FloodWait, MessageIdInvalid, MessageNotModified
from pyrogram.types import Message

from config.settings import CHAT_ID
from core.logger import setup_logger
from core.progress_tracker import ProgressTracker
from utils.formatters import Formatter
from utils.upload_logger import UploadLogger
from utils.video_processor import VideoProcessor

logger = setup_logger("VideoUploader")


async def safe_edit_text(status_msg: Message, text: str, **kwargs) -> None:
    max_retries = 2
    retry_count = 0

    while True:
        try:
            await status_msg.edit_text(text, **kwargs)
            return
        except MessageNotModified:
            return
        except MessageIdInvalid:
            # Message was deleted/invalid, nothing to edit.
            return
        except FloodWait as e:
            retry_count += 1
            if retry_count >= max_retries:
                return
            await asyncio.sleep(e.value + 1)
            continue
        except Exception:
            return


class VideoUploader:
    """Handle video uploads to Telegram."""

    @staticmethod
    async def upload_to_group(
        video_path: str,
        user_id: int,
        status_msg: Optional[Message] = None,
        client: Optional[Client] = None,
    ) -> Tuple[bool, str]:
        """Upload video to Telegram group with retry logic."""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                if not os.path.exists(video_path):
                    return False, "File not found"

                file_size = os.path.getsize(video_path)
                width, height, fps, duration = VideoProcessor.get_dimensions(video_path)
                video_name = os.path.basename(video_path)
                progress_key = f"{user_id}_{video_name}"
                start_time = time.time()

                upload_type = "video"

                # Use the provided client or import app as fallback.
                if client is None:
                    from x_telegram import app as upload_client
                else:
                    upload_client = client

                if width is None or height is None:
                    upload_type = "document"
                    await upload_client.send_document(
                        chat_id=CHAT_ID,
                        document=video_path,
                        progress=ProgressTracker.callback,
                        progress_args=(progress_key, status_msg, video_name, start_time),
                    )
                else:
                    await upload_client.send_video(
                        chat_id=CHAT_ID,
                        video=video_path,
                        width=width,
                        height=height,
                        supports_streaming=True,
                        progress=ProgressTracker.callback,
                        progress_args=(progress_key, status_msg, video_name, start_time),
                    )

                from models.enums import upload_progress

                if progress_key in upload_progress:
                    del upload_progress[progress_key]

                UploadLogger.log(video_path, file_size, width, height, fps, duration, upload_type)
                return True, "Upload successful"

            except FloodWait as e:
                wait_time = e.value
                retry_count += 1

                logger.warning(
                    f"FLOOD_WAIT: Need to wait {wait_time} seconds (Attempt {retry_count}/{max_retries})"
                )

                if status_msg:
                    try:
                        await safe_edit_text(
                            status_msg,
                            f"Rate Limit Hit\n\n"
                            f"Telegram requires a {wait_time}s cooldown.\n\n"
                            f"Waiting {wait_time} seconds...\n"
                            f"Attempt {retry_count}/{max_retries}\n\n"
                            f"Please be patient, upload will resume automatically.",
                        )
                    except Exception:
                        pass

                await asyncio.sleep(wait_time + 1)

                if status_msg:
                    try:
                        await safe_edit_text(
                            status_msg,
                            f"Resuming Upload\n\n"
                            f"File: `{video_name[:35]}...`\n"
                            f"Size: {Formatter.size(file_size)}\n\n"
                            "Retrying upload...",
                        )
                    except Exception:
                        pass

                continue

            except Exception as e:
                logger.error(f"Upload to group failed: {e}")
                return False, str(e)

        return False, f"Failed after {max_retries} attempts due to rate limiting"

    @staticmethod
    async def upload_multiple(video_paths: List[str], message: Message, user_id: int) -> None:
        """Upload multiple videos with progress tracking."""
        total = len(video_paths)
        success_count = 0
        failed_count = 0

        status_msg = await message.reply_text(
            f"Bulk Upload Started\n\n"
            f"Total Files: {total}\n"
            f"Status: Preparing files...\n"
            "--------------------"
        )

        overall_start = time.time()

        for idx, video_path in enumerate(video_paths, 1):
            try:
                video_name = os.path.basename(video_path)
                remaining = total - (idx - 1)

                await safe_edit_text(
                    status_msg,
                    f"Bulk Upload in Progress\n\n"
                    f"File: {idx}/{total}\n"
                    f"Success: {success_count}\n"
                    f"Failed: {failed_count}\n"
                    f"Remaining: {remaining}\n"
                    "--------------------\n"
                    f"Current: `{video_name[:30]}...`",
                )

                # Pass the client from the message context.
                success, msg = await VideoUploader.upload_to_group(
                    video_path, user_id, status_msg, client=message._client
                )

                if success:
                    success_count += 1
                    logger.info(f"Uploaded {idx}/{total}: {video_name}")
                else:
                    failed_count += 1
                    logger.error(f"Failed {idx}/{total}: {video_name} - {msg}")

                if idx < total:
                    await asyncio.sleep(3)

            except Exception as e:
                logger.error(f"Error uploading {video_path}: {e}")
                failed_count += 1

        total_time = time.time() - overall_start

        from ui.keyboards import Keyboards

        await safe_edit_text(
            status_msg,
            f"Bulk Upload Complete\n\n"
            "Summary:\n"
            f"- Total: {total} videos\n"
            f"- Uploaded: {success_count}\n"
            f"- Failed: {failed_count}\n"
            f"- Time: {Formatter.duration(total_time)}\n\n"
            "All selected videos have been sent to the group.",
            reply_markup=Keyboards.back_to_main(),
        )

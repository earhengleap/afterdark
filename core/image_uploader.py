"""
Image upload functionality for Telegram
"""

import os
import time
import asyncio
from typing import List, Tuple, Optional

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from config.settings import CHAT_ID
from utils.formatters import Formatter
from models.enums import user_downloads
from core.logger import setup_logger
from core.uploader import safe_edit_text

logger = setup_logger("ImageUploader")

class ImageUploader:
    """Handle image uploads to Telegram"""
    
    @staticmethod
    async def upload_images_to_group(image_paths: List[str], user_id: int,
                             status_msg: Optional[Message] = None,
                             client: Optional[Client] = None) -> Tuple[bool, str]:
        """Upload images to Telegram group with retry logic - NO CAPTIONS, NO GROUPING"""
        max_retries = 3
        retry_count = 0
        
        if not image_paths:
            return False, "No images provided"
        
        while retry_count < max_retries:
            try:
                # Use the provided client or import app as fallback
                if client is None:
                    from x_telegram import app as upload_client
                else:
                    upload_client = client
                
                total_uploaded = 0
                
                # Send images INDIVIDUALLY (no grouping)
                for idx, img_path in enumerate(image_paths):
                    if not os.path.exists(img_path):
                        logger.warning(f"Image file not found: {img_path}")
                        continue
                    
                    # Send single photo WITHOUT caption
                    await upload_client.send_photo(
                        chat_id=CHAT_ID,
                        photo=img_path
                        # No caption parameter
                    )
                    total_uploaded += 1
                    
                    # Update progress every 5 images
                    if status_msg and (idx + 1) % 5 == 0:
                        await safe_edit_text(
                            status_msg,
                            f"📤 **Uploading Images to Group**\n\n"
                            f"🖼️ Progress: {idx + 1}/{len(image_paths)}\n"
                            f"✅ Uploaded: {total_uploaded} images\n\n"
                            f"⏳ Continuing..."
                        )
                    
                    # Small delay between images to avoid rate limits
                    await asyncio.sleep(1)
                
                return True, f"Successfully uploaded {total_uploaded} images"

            except FloodWait as e:
                wait_time = e.value
                retry_count += 1
                
                logger.warning(f"FLOOD_WAIT: Need to wait {wait_time} seconds (Attempt {retry_count}/{max_retries})")
                
                if status_msg:
                    try:
                        await safe_edit_text(
                            status_msg,
                            f"⏸️ **Rate Limit Hit**\n\n"
                            f"Telegram requires a {wait_time}s cooldown.\n\n"
                            f"⏳ Waiting {wait_time} seconds...\n"
                            f"📊 Attempt {retry_count}/{max_retries}\n\n"
                            f"Please be patient, upload will resume automatically."
                        )
                    except Exception:
                        pass
                
                await asyncio.sleep(wait_time + 1)
                
                if status_msg:
                    try:
                        await safe_edit_text(
                            status_msg,
                            f"📤 **Resuming Image Upload**\n\n"
                            f"🖼️ Remaining: {len(image_paths) - total_uploaded} images\n\n"
                            f"⏳ Retrying upload..."
                        )
                    except Exception:
                        pass
                
                continue

            except Exception as e:
                logger.error(f"Image upload to group failed: {e}")
                return False, str(e)
        
        return False, f"Failed after {max_retries} attempts due to rate limiting"
    
    @staticmethod
    async def upload_single_image_to_group(image_path: str, user_id: int, status_msg: Optional[Message] = None,
                           client: Optional[Client] = None) -> Tuple[bool, str]:
        """Upload single image to Telegram group - NO CAPTION"""
        if not os.path.exists(image_path):
            return False, "Image file not found"
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Use the provided client or import app as fallback
                if client is None:
                    from x_telegram import app as upload_client
                else:
                    upload_client = client
                
                # Send single photo WITHOUT caption
                await upload_client.send_photo(
                    chat_id=CHAT_ID,
                    photo=image_path
                    # No caption parameter
                )
                
                return True, "Image uploaded successfully"
                
            except FloodWait as e:
                wait_time = e.value
                retry_count += 1
                
                logger.warning(f"FLOOD_WAIT: Need to wait {wait_time} seconds (Attempt {retry_count}/{max_retries})")
                
                if status_msg:
                    try:
                        await safe_edit_text(
                            status_msg,
                            f"⏸️ **Rate Limit Hit**\n\n"
                            f"Telegram requires a {wait_time}s cooldown.\n\n"
                            f"⏳ Waiting {wait_time} seconds...\n"
                            f"📊 Attempt {retry_count}/{max_retries}"
                        )
                    except Exception:
                        pass
                
                await asyncio.sleep(wait_time + 1)
                
                if status_msg:
                    try:
                        await safe_edit_text(status_msg, "📤 **Resuming Upload...**")
                    except Exception:
                        pass
                
                continue

            except Exception as e:
                logger.error(f"Single image upload failed: {e}")
                return False, str(e)
        
        return False, f"Failed after {max_retries} attempts due to rate limiting"
    
    @staticmethod
    async def upload_multiple_images(image_paths: List[str], message: Message, user_id: int) -> None:
        """Upload multiple images with progress tracking - NO CAPTIONS, NO GROUPING"""
        total = len(image_paths)
        success_count = 0
        failed_count = 0
        
        status_msg = await message.reply_text(
            f"📤 **Starting Bulk Image Upload**\n\n"
            f"Total images: {total}\n"
            f"Preparing upload..."
        )
        
        overall_start = time.time()
        
        # Upload images individually
        success, msg = await ImageUploader.upload_images_to_group(
            image_paths, user_id, status_msg, client=message._client
        )
        
        if success:
            success_count = total
            logger.info(f"Uploaded all {total} images individually")
        else:
            failed_count = total
            logger.error(f"Failed to upload images: {msg}")
        
        total_time = time.time() - overall_start
        
        from ui.keyboards import Keyboards
        await safe_edit_text(
            status_msg,
            f"✅ **Bulk Image Upload Complete!**\n\n"
            f"📊 **Summary:**\n"
            f"• Total: {total} images\n"
            f"• ✅ Uploaded: {success_count}\n"
            f"• ❌ Failed: {failed_count}\n"
            f"• ⏱️ Time: {Formatter.duration(total_time)}\n\n"
            f"All selected images have been sent to the group individually.",
            reply_markup=Keyboards.back_to_main()
        )

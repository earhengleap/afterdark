import logging
import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import Message
from config.settings import CHAT_ID
from config.paths import get_platform_folder, apply_sequence_prefix
from core.database import history_db
from core.parsing.url_extractor import URLExtractor
from core.downloader import VideoDownloader
from core.image_downloader import ImageDownloader

logger = logging.getLogger("AfterDark.Sync")

async def handle_group_media(client: Client, message: Message):
    """Detect links in group messages and download them"""
    chat_id = message.chat.id
    message_id = message.id
    user_id = message.from_user.id if message.from_user else chat_id
    username = message.from_user.username if message.from_user else "Unknown"

    try:
        # 1. Handle links in text/caption
        text = message.text or message.caption
        if text:
            urls = URLExtractor.extract_urls(text)
            for url in urls:
                # Trigger background download for links found in the group
                logger.info(f"🔗 Group link detected: {url}")
                asyncio.create_task(process_group_link(client, message, url))

    except Exception as e:
        logger.error(f"Error in handle_group_media processing: {e}")

async def process_group_link(client: Client, message: Message, url: str):
    """Background task to download media from a link found in the group"""
    try:
        user_id = message.from_user.id if message.from_user else message.chat.id
        username = message.from_user.username if message.from_user else "Unknown"
        
        # Call the existing downloader logic
        # Note: We pass None for status_msg to download silently in the background
        await VideoDownloader.download(
            url=url,
            message=message,
            user_id=user_id,
            username=username,
            app=client
        )
    except Exception as e:
        logger.error(f"Failed to process group link {url}: {e}")

def setup_media_sync_handlers(app: Client):
    """Register real-time group media sync handlers"""
    
    # If CHAT_ID is configured, only listen to that chat
    target_chat = int(CHAT_ID) if CHAT_ID else None
    
    @app.on_message(filters.group | filters.channel)
    async def media_sync_handler(client: Client, message: Message):
        # Filter by CHAT_ID if set
        if target_chat and message.chat.id != target_chat:
            return
            
        # Process media regardless of sender in the target chat
        await handle_group_media(client, message)


    logger.info("✓ Media Sync Handlers registered")

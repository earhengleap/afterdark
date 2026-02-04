"""
Progress tracking for downloads and uploads
"""

import time
import asyncio
from typing import Dict, Optional

from pyrogram.types import Message

from utils.formatters import Formatter
from models.enums import upload_progress
from core.logger import setup_logger

logger = setup_logger("ProgressTracker")


class ProgressTracker:
    """Track and display download and upload progress"""
    
    def __init__(self):
        self.last_update = {}
        self.update_interval = 1.5  # Update every 1.5 seconds
        
    def should_update(self, key: str) -> bool:
        """Check if enough time has passed to update the message"""
        current_time = time.time()
        last = self.last_update.get(key, 0)
        if current_time - last >= self.update_interval:
            self.last_update[key] = current_time
            return True
        return False
    
    async def update_download_progress(
        self,
        status_msg: Message,
        downloaded: float,
        total: float,
        speed: float,
        filename: str,
        index: int = 1,
        total_count: int = 1,
        url: str = ""
    ) -> None:
        """
        Update download progress message
        
        Args:
            status_msg: Message to update
            downloaded: Bytes downloaded
            total: Total bytes
            speed: Download speed in bytes/second
            filename: File being downloaded
            index: Current file index
            total_count: Total number of files
            url: Source URL
        """
        progress_key = f"download_{id(status_msg)}"
        
        if not self.should_update(progress_key):
            return
            
        try:
            percentage = (downloaded / total * 100) if total > 0 else 0
            progress_bar = Formatter.progress_bar(percentage)
            
            # Calculate ETA
            eta = 0
            if speed > 0 and total > downloaded:
                remaining = total - downloaded
                eta = remaining / speed
            
            # Format URL for display
            url_display = url.replace('https://', '').replace('http://', '')
            if len(url_display) > 35:
                url_display = url_display[:32] + '...'
            
            progress_text = (
                f"📥 **Downloading** ({index}/{total_count})\n\n"
                f"🔗 **Source:** `{url_display}`\n"
                f"📄 **File:** `{filename[:30]}{'...' if len(filename) > 30 else ''}`\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 **Progress:** {percentage:.1f}%\n"
                f"`{progress_bar}`\n\n"
                f"💾 **Size:** {Formatter.size(downloaded)} / {Formatter.size(total)}\n"
            )
            
            if speed > 0:
                speed_mb = speed / (1024 * 1024)
                progress_text += f"⚡ **Speed:** {speed_mb:.2f} MB/s\n"
            
            if eta > 0:
                progress_text += f"⏱️ **ETA:** {Formatter.eta(eta)}\n"
            
            progress_text += "━━━━━━━━━━━━━━━━━━━━"
            
            await status_msg.edit_text(progress_text)
            logger.debug(f"Download progress: {percentage:.1f}% - {Formatter.size(downloaded)}/{Formatter.size(total)}")
        except Exception as e:
            logger.debug(f"Progress update error: {e}")
    
    @staticmethod
    async def callback(current: int, total: int, progress_key: str, status_msg: Message, 
                 video_name: str, start_time: float) -> None:
        """Progress callback for upload with ETA"""
        try:
            percentage = (current / total) * 100
            elapsed_time = time.time() - start_time
            
            if current > 0:
                speed = current / elapsed_time
                remaining_bytes = total - current
                eta = remaining_bytes / speed if speed > 0 else 0
            else:
                speed = 0
                eta = 0
            
            upload_progress[progress_key] = {
                'current': current,
                'total': total,
                'percentage': percentage,
                'speed': speed,
                'eta': eta
            }
            
            if not hasattr(ProgressTracker.callback, 'last_update'):
                ProgressTracker.callback.last_update = {}
            
            last_update = ProgressTracker.callback.last_update.get(progress_key, 0)
            if elapsed_time - last_update >= 1.5:
                ProgressTracker.callback.last_update[progress_key] = elapsed_time
                
                progress_bar = Formatter.progress_bar(percentage)
                speed_mb = speed / (1024 * 1024)
                
                status_text = (
                    f"📤 **Uploading to Telegram**\n\n"
                    f"📹 **File:** `{video_name[:30]}{'...' if len(video_name) > 30 else ''}`\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 **Progress:** {percentage:.1f}%\n"
                    f"`{progress_bar}`\n\n"
                    f"⚡ **Speed:** {speed_mb:.2f} MB/s\n"
                    f"💾 **Size:** {Formatter.size(current)} / {Formatter.size(total)}\n"
                    f"⏱️ **ETA:** {Formatter.eta(eta)}\n"
                    f"━━━━━━━━━━━━━━━━━━━━"
                )
                
                try:
                    await status_msg.edit_text(status_text)
                    logger.debug(f"Upload progress: {percentage:.1f}%")
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Upload progress callback error: {e}")


# Global tracker instance
download_tracker = ProgressTracker()


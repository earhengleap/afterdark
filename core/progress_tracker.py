"""
Progress tracking for uploads
"""

import time
from typing import Dict, Optional

from pyrogram.types import Message

from utils.formatters import Formatter
from models.enums import upload_progress

class ProgressTracker:
    """Track and display upload progress"""
    
    @staticmethod
    def callback(current: int, total: int, progress_key: str, status_msg: Message, 
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
            if elapsed_time - last_update >= 2:
                ProgressTracker.callback.last_update[progress_key] = elapsed_time
                
                progress_bar = Formatter.progress_bar(percentage)
                speed_mb = speed / (1024 * 1024)
                
                status_text = (
                    f"📤 **Uploading to Group**\n\n"
                    f"📁 **File:** `{video_name[:35]}...`\n\n"
                    f"**Progress:** {percentage:.1f}%\n"
                    f"`{progress_bar}`\n\n"
                    f"📊 **Size:** {Formatter.size(current)} / {Formatter.size(total)}\n"
                    f"⚡ **Speed:** {speed_mb:.2f} MB/s\n"
                    f"⏱️ **ETA:** {Formatter.eta(eta)}\n"
                )
                
                try:
                    status_msg.edit_text(status_text)
                except Exception:
                    pass
        except Exception as e:
            print(f"Progress callback error: {e}")
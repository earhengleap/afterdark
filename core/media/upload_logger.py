"""
Upload logging utilities
"""

import os
from datetime import datetime
from typing import Optional

from core.formatting.formatters import Formatter

class UploadLogger:
    """Log upload activities"""
    
    @staticmethod
    def log(video_path: str, file_size: float, width: Optional[int], 
            height: Optional[int], fps: Optional[int], duration: Optional[float], 
            upload_type: str) -> None:
        """Log video upload info to file"""
        from config.paths import UPLOAD_LOG_FILE
        
        video_name = os.path.basename(video_path)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        log_lines = [
            "="*80,
            f"📤 Upload Timestamp : {timestamp}",
            f"📁 File Name        : {video_name}",
            f"💾 File Size        : {file_size / (1024*1024):.2f} MB",
            f"📄 Upload Type      : {upload_type}"
        ]

        if width and height:
            log_lines.extend([
                f"📺 Resolution       : {width}x{height}",
                f"🎬 FPS             : {fps}",
                f"⏱️  Duration        : {Formatter.duration(duration)}"
            ])

        log_lines.append("="*80 + "\n")

        with open(UPLOAD_LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n".join(log_lines))
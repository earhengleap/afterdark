"""
Data models and classes
"""

from typing import Optional

class VideoInfo:
    """Data class for video information"""
    def __init__(self, filepath: str, filename: str, size_mb: float):
        self.filepath = filepath
        self.filename = filename
        self.size_mb = size_mb

class DownloadResult:
    """Data class for download results"""
    def __init__(self, url: str, status: str, filename: Optional[str] = None, 
                 size: float = 0, error: Optional[str] = None):
        self.url = url
        self.status = status
        self.filename = filename
        self.size = size
        self.error = error
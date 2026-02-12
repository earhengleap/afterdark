"""
Bot Metrics Tracking - Monitor performance and usage
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
import threading
import json
import logging

logger = logging.getLogger("XVideoBot.Metrics")


@dataclass
class BotMetrics:
    """Track bot performance and usage metrics"""
    
    start_time: datetime = field(default_factory=datetime.now)
    total_commands: int = 0
    total_downloads: int = 0
    total_videos_downloaded: int = 0
    total_images_downloaded: int = 0
    total_errors: int = 0
    active_downloads: int = 0
    successful_downloads: int = 0
    failed_downloads: int = 0
    total_bytes_downloaded: int = 0
    unique_users: set = field(default_factory=set)
    command_counts: Dict[str, int] = field(default_factory=dict)
    error_counts: Dict[str, int] = field(default_factory=dict)
    
    # Thread safety
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def increment_commands(self, command: str = "unknown"):
        """Increment total command count and track specific command"""
        with self._lock:
            self.total_commands += 1
            self.command_counts[command] = self.command_counts.get(command, 0) + 1
    
    def increment_downloads(self):
        """Increment total download attempts"""
        with self._lock:
            self.total_downloads += 1
    
    def increment_videos(self, count: int = 1):
        """Increment video download count"""
        with self._lock:
            self.total_videos_downloaded += count
    
    def increment_images(self, count: int = 1):
        """Increment image download count"""
        with self._lock:
            self.total_images_downloaded += count
    
    def increment_errors(self, error_type: str = "general"):
        """Increment error count and track error types"""
        with self._lock:
            self.total_errors += 1
            self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
    
    def download_started(self):
        """Mark a download as started"""
        with self._lock:
            self.active_downloads += 1
    
    def download_completed(self, success: bool = True, bytes_downloaded: int = 0):
        """Mark a download as completed"""
        with self._lock:
            self.active_downloads = max(0, self.active_downloads - 1)
            if success:
                self.successful_downloads += 1
                self.total_bytes_downloaded += bytes_downloaded
            else:
                self.failed_downloads += 1
    
    def add_user(self, user_id: int):
        """Track unique user"""
        with self._lock:
            self.unique_users.add(user_id)
    
    def get_uptime(self) -> float:
        """Get bot uptime in seconds"""
        return (datetime.now() - self.start_time).total_seconds()
    
    def get_uptime_formatted(self) -> str:
        """Get formatted uptime string"""
        uptime = self.get_uptime()
        days = int(uptime // 86400)
        hours = int((uptime % 86400) // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    def get_success_rate(self) -> float:
        """Calculate download success rate"""
        total = self.successful_downloads + self.failed_downloads
        if total == 0:
            return 0.0
        return (self.successful_downloads / total) * 100
    
    def as_dict(self) -> dict:
        """Export metrics as dictionary"""
        with self._lock:
            return {
                "uptime_seconds": self.get_uptime(),
                "uptime_formatted": self.get_uptime_formatted(),
                "start_time": self.start_time.isoformat(),
                "total_commands": self.total_commands,
                "total_downloads": self.total_downloads,
                "total_videos_downloaded": self.total_videos_downloaded,
                "total_images_downloaded": self.total_images_downloaded,
                "successful_downloads": self.successful_downloads,
                "failed_downloads": self.failed_downloads,
                "success_rate": f"{self.get_success_rate():.2f}%",
                "total_errors": self.total_errors,
                "active_downloads": self.active_downloads,
                "total_bytes_downloaded": self.total_bytes_downloaded,
                "total_bytes_downloaded_mb": f"{self.total_bytes_downloaded / (1024*1024):.2f} MB",
                "unique_users": len(self.unique_users),
                "top_commands": dict(sorted(self.command_counts.items(), key=lambda x: x[1], reverse=True)[:5]),
                "error_types": dict(sorted(self.error_counts.items(), key=lambda x: x[1], reverse=True)[:5])
            }
    
    def as_json(self) -> str:
        """Export metrics as JSON string"""
        return json.dumps(self.as_dict(), indent=2)
    
    def get_summary(self) -> str:
        """Get human-readable summary"""
        with self._lock:
            return (
                f"📊 **Bot Metrics Summary**\n\n"
                f"⏱️ Uptime: {self.get_uptime_formatted()}\n"
                f"👥 Unique Users: {len(self.unique_users)}\n"
                f"📥 Total Downloads: {self.total_downloads}\n"
                f"🎥 Videos: {self.total_videos_downloaded} | 🖼️ Images: {self.total_images_downloaded}\n"
                f"✅ Success: {self.successful_downloads} | ❌ Failed: {self.failed_downloads}\n"
                f"📈 Success Rate: {self.get_success_rate():.2f}%\n"
                f"⚡ Active Downloads: {self.active_downloads}\n"
                f"💾 Data Downloaded: {self.total_bytes_downloaded / (1024*1024):.2f} MB\n"
                f"⚠️ Total Errors: {self.total_errors}"
            )
    
    def reset(self):
        """Reset all metrics (except start time)"""
        with self._lock:
            self.total_commands = 0
            self.total_downloads = 0
            self.total_videos_downloaded = 0
            self.total_images_downloaded = 0
            self.total_errors = 0
            self.active_downloads = 0
            self.successful_downloads = 0
            self.failed_downloads = 0
            self.total_bytes_downloaded = 0
            self.unique_users.clear()
            self.command_counts.clear()
            self.error_counts.clear()
            logger.info("Metrics reset successfully")


# Global metrics instance
metrics = BotMetrics()


def get_metrics() -> BotMetrics:
    """Get the global metrics instance"""
    return metrics

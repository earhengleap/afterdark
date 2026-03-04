"""
Formatting utilities for display
"""

class Formatter:
    """Formatting utilities for display"""
    
    @staticmethod
    def duration(seconds: float) -> str:
        """Format duration dynamically"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            sec = int(seconds % 60)
            return f"{minutes}m {sec}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            sec = int(seconds % 60)
            return f"{hours}h {minutes}m {sec}s"
    
    @staticmethod
    def size(bytes_size: float) -> str:
        """Format file size"""
        mb = bytes_size / (1024 * 1024)
        if mb < 1024:
            return f"{mb:.2f} MB"
        else:
            gb = mb / 1024
            return f"{gb:.2f} GB"
    
    @staticmethod
    def eta(seconds: float) -> str:
        """Format ETA time"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            sec = int(seconds % 60)
            return f"{minutes}m {sec}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    @staticmethod
    def progress_bar(percentage: float) -> str:
        """Generate visual progress bar"""
        filled = int(percentage / 10)
        empty = 10 - filled
        return "█" * filled + "░" * empty
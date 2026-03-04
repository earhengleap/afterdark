"""
File management operations
"""

import os
import re
from typing import List

from models.data_models import VideoInfo
from config.paths import DOWNLOAD_FOLDER, IMAGES_FOLDER, apply_sequence_prefix


class FileManager:
    """Handles file operations and naming"""

    @staticmethod
    def rename_with_number(original_path: str) -> str:
        """Add sequential 'NN-' number prefix to filename within its folder.
        Delegates to the central apply_sequence_prefix() from paths.py so the
        logic is consistent everywhere."""
        return apply_sequence_prefix(original_path)

    @staticmethod
    def get_all_videos() -> List[VideoInfo]:
        """Recursively get all video files from all platform subfolders."""
        try:
            videos = []
            for root, dirs, files in os.walk(DOWNLOAD_FOLDER):
                for filename in files:
                    if filename.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm')):
                        filepath = os.path.join(root, filename)
                        size_mb = os.path.getsize(filepath) / (1024 * 1024)
                        # Show relative sub-path in filename for clarity
                        rel = os.path.relpath(filepath, DOWNLOAD_FOLDER)
                        videos.append(VideoInfo(filepath, rel, size_mb))
            videos.sort(key=lambda x: x.filename)
            return videos
        except Exception as e:
            print(f"Error getting videos: {e}")
            return []

    @staticmethod
    def get_all_images() -> List[VideoInfo]:
        """Recursively get all image files from all platform subfolders."""
        try:
            images = []
            if os.path.exists(IMAGES_FOLDER):
                for root, dirs, files in os.walk(IMAGES_FOLDER):
                    for filename in files:
                        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                            filepath = os.path.join(root, filename)
                            size_mb = os.path.getsize(filepath) / (1024 * 1024)
                            rel = os.path.relpath(filepath, IMAGES_FOLDER)
                            images.append(VideoInfo(filepath, rel, size_mb))
            images.sort(key=lambda x: x.filename)
            return images
        except Exception as e:
            print(f"Error getting images: {e}")
            return []

    @staticmethod
    def get_total_videos() -> int:
        """Count total video files"""
        return len(FileManager.get_all_videos())

    @staticmethod
    def get_total_images() -> int:
        """Count total image files"""
        return len(FileManager.get_all_images())

    @staticmethod
    def get_next_number() -> int:
        """Get next sequential number across the whole videos folder (legacy helper)."""
        all_videos = FileManager.get_all_videos()
        numbers = []
        for v in all_videos:
            m = re.match(r'^(\d+)-', os.path.basename(v.filepath))
            if m:
                try:
                    numbers.append(int(m.group(1)))
                except ValueError:
                    pass
        return max(numbers) + 1 if numbers else 1
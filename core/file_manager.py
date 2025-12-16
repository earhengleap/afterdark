"""
File management operations
"""

import os
import re
from typing import List

from models.data_models import VideoInfo
from config.paths import DOWNLOAD_FOLDER, IMAGES_FOLDER  # UPDATED: Import IMAGES_FOLDER

class FileManager:
    """Handles file operations and naming"""
    
    @staticmethod
    def get_next_number() -> int:
        """Get next sequential number for file naming"""
        files = os.listdir(DOWNLOAD_FOLDER)
        numbers = [int(m.group(1)) for f in files if (m := re.match(r'^(\d+)-', f))]
        return max(numbers) + 1 if numbers else 1
    
    @staticmethod
    def rename_with_number(original_path: str) -> str:
        """Add sequential number prefix to filename"""
        if not os.path.exists(original_path):
            return original_path
        
        directory = os.path.dirname(original_path)
        filename = os.path.basename(original_path)
        
        if re.match(r'^\d+-', filename):
            return original_path
        
        next_num = FileManager.get_next_number()
        new_filename = f"{next_num:02d}-{filename}"
        new_path = os.path.join(directory, new_filename)
        
        # Check if target already exists
        if os.path.exists(new_path):
            return original_path
            
        os.rename(original_path, new_path)
        return new_path
    
    @staticmethod
    def get_all_videos() -> List[VideoInfo]:
        """Get all video files from download folder"""
        try:
            videos = []
            for filename in os.listdir(DOWNLOAD_FOLDER):
                filepath = os.path.join(DOWNLOAD_FOLDER, filename)
                if os.path.isfile(filepath) and filename.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                    size_mb = os.path.getsize(filepath) / (1024 * 1024)
                    videos.append(VideoInfo(filepath, filename, size_mb))
            videos.sort(key=lambda x: x.filename)
            return videos
        except Exception as e:
            print(f"Error getting videos: {e}")
            return []
    
    @staticmethod
    def get_all_images() -> List[VideoInfo]:
        """Get all image files from images folder"""
        try:
            images = []
            # Use IMAGES_FOLDER instead of videos/images
            if os.path.exists(IMAGES_FOLDER):
                for root, dirs, files in os.walk(IMAGES_FOLDER):
                    for filename in files:
                        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                            filepath = os.path.join(root, filename)
                            size_mb = os.path.getsize(filepath) / (1024 * 1024)
                            images.append(VideoInfo(filepath, filename, size_mb))
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
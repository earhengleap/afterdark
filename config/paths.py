"""
Path management and directory setup
"""

import os

# ==================== PATH CONSTANTS ====================

DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "media", "videos")
IMAGES_FOLDER = os.path.join(os.getcwd(), "media", "images") 
THUMBNAILS_FOLDER = os.path.join(os.getcwd(), "media", "thumbnails")
DATA_FOLDER = os.path.join(os.getcwd(), "data")
LOG_FILE = os.path.join(DATA_FOLDER, "download_log.log")
UPLOAD_LOG_FILE = os.path.join(DATA_FOLDER, "upload_history.log")

# ==================== DIRECTORY SETUP ====================

def setup_directories():
    """Ensure required directories exist"""
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    os.makedirs(IMAGES_FOLDER, exist_ok=True)  
    os.makedirs(DATA_FOLDER, exist_ok=True)

# Initialize directories on import
setup_directories()
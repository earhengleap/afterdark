"""
Path management and directory setup
"""

import os
import re

# ==================== BASE PATH CONSTANTS ====================

DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "media", "videos")
IMAGES_FOLDER = os.path.join(os.getcwd(), "media", "images")
THUMBNAILS_FOLDER = os.path.join(os.getcwd(), "media", "thumbnails")
DATA_FOLDER = os.path.join(os.getcwd(), "data")
LOG_FILE = os.path.join(DATA_FOLDER, "download_log.log")
UPLOAD_LOG_FILE = os.path.join(DATA_FOLDER, "upload_history.log")

# ==================== PLATFORM FOLDER MAP ====================
# Maps a platform key -> subfolder name
# Add new platforms here and everywhere else will stay in sync.

PLATFORM_FOLDER_NAMES = {
    "X":        "X",
    "Reddit":   "Reddit",
    "RedGifs":  "RedGifs",
    "91Porn":   "91Porn",
    "Papalah":  "Papalah",
    "BadNews":  "Bad.news",
    "Videy":    "Videy",
    "Generic":  "Other",   # yt-dlp fallback for any unsupported site
}


def get_platform_folder(platform: str, media_type: str = "video") -> str:
    """
    Return (and create) the correct subfolder for a given platform and media type.

    Args:
        platform: one of the keys in PLATFORM_FOLDER_NAMES (e.g. "X", "Reddit")
        media_type: "video" or "image"

    Returns:
        Absolute path to the platform subfolder (already created on disk).

    Examples:
        get_platform_folder("X", "video")   → .../media/videos/X/
        get_platform_folder("Reddit", "image") → .../media/images/Reddit/
    """
    folder_name = PLATFORM_FOLDER_NAMES.get(platform, platform)
    base = DOWNLOAD_FOLDER if media_type == "video" else IMAGES_FOLDER
    folder = os.path.join(base, folder_name)
    os.makedirs(folder, exist_ok=True)
    return folder


def get_x_user_folder(username: str, media_type: str = "video") -> str:
    """
    Return (and create) a per-username subfolder inside the X platform folder.

    Args:
        username: X/Twitter username (with or without leading @)
        media_type: "video" or "image"

    Returns:
        Absolute path to media/videos/X/@username/ or media/images/X/@username/

    Examples:
        get_x_user_folder("elonmusk", "video") → .../media/videos/X/@elonmusk/
        get_x_user_folder("@nasa",    "image") → .../media/images/X/@nasa/
    """
    # Strip @ if present, then re-add for consistency
    clean = username.lstrip("@").strip() if username else "unknown"
    # Sanitize for filesystem (remove characters unsafe on Windows/Mac/Linux)
    clean = re.sub(r'[<>:"/\\|?*]', '_', clean)
    folder_name = f"@{clean}"
    x_base = get_platform_folder("X", media_type)
    folder = os.path.join(x_base, folder_name)
    os.makedirs(folder, exist_ok=True)
    return folder




def get_next_sequence_number(folder: str) -> int:
    """
    Scan *folder* for files prefixed with 'NN-' and return the next integer.
    Thread-safe enough for sequential single-user bots.
    """
    if not os.path.isdir(folder):
        return 1
    numbers = []
    for f in os.listdir(folder):
        m = re.match(r'^(\d+)-', f)
        if m:
            try:
                numbers.append(int(m.group(1)))
            except ValueError:
                pass
    return max(numbers) + 1 if numbers else 1


def apply_sequence_prefix(file_path: str) -> str:
    """
    Rename *file_path* in-place to add a sequential 'NN-' prefix if one is not
    already present.  Returns the final path (which may differ from *file_path*).
    """
    if not os.path.exists(file_path):
        return file_path

    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)

    # Already numbered – leave it alone
    if re.match(r'^\d+-', filename):
        return file_path

    next_num = get_next_sequence_number(directory)
    new_filename = f"{next_num:02d}-{filename}"
    new_path = os.path.join(directory, new_filename)

    # Avoid collisions
    counter = next_num
    while os.path.exists(new_path):
        counter += 1
        new_path = os.path.join(directory, f"{counter:02d}-{filename}")

    try:
        os.rename(file_path, new_path)
        return new_path
    except OSError:
        return file_path


# ==================== DIRECTORY SETUP ====================

def setup_directories():
    """Ensure base required directories exist"""
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    os.makedirs(IMAGES_FOLDER, exist_ok=True)
    os.makedirs(DATA_FOLDER, exist_ok=True)
    # Pre-create platform subfolders for videos and images
    for platform in PLATFORM_FOLDER_NAMES:
        get_platform_folder(platform, "video")
        get_platform_folder(platform, "image")


# Initialize directories on import
setup_directories()
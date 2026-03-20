"""
Image download functionality for X (Twitter) - ENHANCED FIX with URL normalization
"""

import os
import re
import subprocess
import sys
import time
import json
import tempfile
import asyncio
from typing import List, Tuple, Optional, Dict
from urllib.parse import urlparse, parse_qs
import requests

from pyrogram.types import Message, InputMediaPhoto

from config.settings import COOKIE_FILE
from config.paths import DOWNLOAD_FOLDER, IMAGES_FOLDER, get_platform_folder, get_x_user_folder, apply_sequence_prefix
from models.data_models import DownloadResult
from core.file_manager import FileManager
from core.log_manager import LogManager
from core.formatting.formatters import Formatter
from models.enums import user_downloads
from resources.keyboards import Keyboards
from core.logger import setup_logger
from core.database import history_db
from core.parsing.url_parser import extract_twitter_username

logger = setup_logger("ImageDownloader")

class ImageDownloader:
    """Handle image downloads from X (Twitter) using gallery-dl - ENHANCED FIX"""

    @staticmethod
    async def _notify_status(status_callback, percent: int, stage: str) -> None:
        if not status_callback:
            return
        try:
            result = status_callback(percent, stage)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            pass
    
    @staticmethod
    def normalize_twitter_url(url: str) -> str:
        """
        Normalize Twitter/X URLs to their cleanest form.
        Removes query parameters and ensures consistent format.
        """
        # Remove query parameters/fragments that can interfere.
        url = url.split('#', 1)[0].split('?', 1)[0].rstrip('/')

        # Canonicalize all Twitter/X hosts to x.com so cookie domains match.
        url = re.sub(r'(?i)://(?:www\.|mobile\.)?twitter\.com/', '://x.com/', url, count=1)
        url = re.sub(r'(?i)://(?:www\.|mobile\.)?x\.com/', '://x.com/', url, count=1)
        
        logger.debug(f"URL normalized: {url}")
        return url
    
    @staticmethod
    async def download(
        url: str,
        message: Optional[Message] = None,
        status_callback=None,
        index: int = 1,
        total: int = 1
    ) -> Tuple[Optional[List[str]], Optional[Dict]]:
        """Download images from X URL - ENHANCED FIX with URL normalization"""
        try:
            await ImageDownloader._notify_status(
                status_callback, 5, f"📌 Link {index}/{total} - Preparing image scan"
            )

            # NORMALIZE URL FIRST - This is critical!
            original_url = url
            url = ImageDownloader.normalize_twitter_url(url)
            logger.debug(f"Cleaned URL: {original_url} -> {url}")
            await ImageDownloader._notify_status(
                status_callback, 12, f"🔗 Link {index}/{total} - Link checked"
            )
            
            # Use the X platform per-user images subfolder
            x_username = extract_twitter_username(url)
            if x_username:
                download_folder = get_x_user_folder(x_username, "image")
                logger.debug(f"X image folder: {download_folder}")
            else:
                download_folder = get_platform_folder("X", "image")
            
            # Get list of existing files BEFORE download
            existing_files = set()
            for root, dirs, files in os.walk(download_folder):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                        full_path = os.path.join(root, file)
                        existing_files.add(full_path)
            
            logger.debug(f"Existing image files before download: {len(existing_files)}")
            
            # First, check if cookies file exists and is valid
            if not os.path.exists(COOKIE_FILE):
                logger.warning(f"Cookie file not found: {COOKIE_FILE}")
            else:
                # Check if cookies file is not empty
                if os.path.getsize(COOKIE_FILE) == 0:
                    logger.warning("Cookie file is empty")
            
            # Run the single robust gallery-dl execution
            logger.debug("Executing gallery-dl download process")
            await ImageDownloader._notify_status(
                status_callback, 50, f"🛰️ Link {index}/{total} - Downloading media"
            )
            downloaded_files = await ImageDownloader._run_gallery_dl(
                url, download_folder, existing_files, status_callback, index, total
            )

            # Fallback for cases where gallery-dl fails to resolve X images.
            if not downloaded_files and ("x.com/" in url or "twitter.com/" in url):
                logger.info("gallery-dl returned no images; trying fxtwitter fallback")
                downloaded_files = await ImageDownloader._run_fxtwitter_fallback(
                    url, download_folder, status_callback, index, total
                )
            
            if downloaded_files:
                logger.info(f"Download success: Retrieved {len(downloaded_files)} images")
                await ImageDownloader._notify_status(
                    status_callback, 100, f"✅ Link {index}/{total} - Downloaded {len(downloaded_files)} image(s)"
                )
                info = {
                    'title': f"X Images - {len(downloaded_files)} files",
                    'uploader': 'X (Twitter)',
                    'upload_date': time.strftime('%Y%m%d')
                }
                return downloaded_files, info
            
            logger.warning("Download failed - no images found")
            await ImageDownloader._notify_status(
                status_callback, 100, f"⚠️ Link {index}/{total} - No images found"
            )
            return None, None
                
        except Exception as e:
            logger.error(f"Image download error: {e}", exc_info=True)
            await ImageDownloader._notify_status(
                status_callback, 100, f"❌ Link {index}/{total} - Image download failed"
            )
            return None, None
    
    @staticmethod
    async def _run_gallery_dl(url: str, download_folder: str, existing_files: set, status_callback=None, index=1, total=1) -> Optional[List[str]]:
        """Run gallery-dl with real-time progress parsing."""
        try:
            config_content = {
                "extractor": {
                    "twitter": {
                        "syndication": True,
                        "api": "syndication",
                        "videos": False,
                        "retweets": True,
                        "quoted": True
                    }
                },
                "downloader": {
                    "retries": 5,
                    "timeout": 45.0,
                    "rate": "2M",
                    "part": False,
                    "mtime": True
                },
                "output": {
                    "mode": "terminal"
                }
            }
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as config_file:
                json.dump(config_content, config_file, indent=2)
                config_path = config_file.name
            
            try:
                cmd = [
                    sys.executable,
                    "-m", "gallery_dl",
                    "--config", config_path,
                    "-d", download_folder,
                    "--no-part",
                    url
                ]
                
                if os.path.exists(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 0:
                    cmd.extend(["--cookies", COOKIE_FILE])
                
                logger.debug(f"Executing gallery-dl for {url}")
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                found_images = []
                # Read stdout line by line for real-time progress
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    
                    line_str = line.decode().strip()
                    if line_str:
                        # gallery-dl usually prints the image URL or Path
                        if any(ext in line_str.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                            found_images.append(line_str)
                            if status_callback:
                                await ImageDownloader._notify_status(
                                    status_callback, 
                                    min(50 + len(found_images) * 5, 95), 
                                    f"🛰️ Link {index}/{total} - Found {len(found_images)} images..."
                                )
                
                await process.wait()
                
                # Detect the actual new files on disk
                new_files = ImageDownloader._get_new_files(download_folder, existing_files)
                return new_files
                
            finally:
                try:
                    os.unlink(config_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error in gallery-dl execution: {e}")
            return None
    
    @staticmethod
    def _parse_gallery_dl_output(output: str, download_folder: str) -> Optional[List[str]]:
        """Parse gallery-dl output to extract downloaded file paths"""
        try:
            downloaded_files = []
            lines = output.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Clean prefix if it exists (gallery-dl sometimes prefixes with '# ')
                if line.startswith('#'):
                    file_path = line[1:].strip()
                else:
                    file_path = line
                    
                # Only check if the path looks like it belongs to our download folder or a valid image
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                        new_path = ImageDownloader._safe_rename_with_number(file_path)
                        if new_path:
                            downloaded_files.append(new_path)
                        else:
                            downloaded_files.append(file_path)
            
            if downloaded_files:
                return downloaded_files
            return None
        except Exception as e:
            logger.error(f"Error parsing gallery-dl output: {e}")
            return None
    
    @staticmethod
    def _get_new_files(download_folder: str, existing_files: set) -> Optional[List[str]]:
        """Get only newly downloaded files"""
        downloaded_files = []
        for root, dirs, files in os.walk(download_folder):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                    file_path = os.path.join(root, file)
                    if file_path not in existing_files:
                        new_path = ImageDownloader._safe_rename_with_number(file_path)
                        if new_path:
                            downloaded_files.append(new_path)
                        else:
                            downloaded_files.append(file_path)
        return downloaded_files if downloaded_files else None

    @staticmethod
    async def _run_fxtwitter_fallback(
        url: str,
        download_folder: str,
        status_callback=None,
        index: int = 1,
        total: int = 1,
    ) -> Optional[List[str]]:
        """Download X images via fxtwitter API when gallery-dl returns no files."""
        try:
            status_match = re.search(r"/status/(\d+)", url)
            if not status_match:
                return None

            tweet_id = status_match.group(1)
            api_url = f"https://api.fxtwitter.com/status/{tweet_id}"
            response = await asyncio.to_thread(requests.get, api_url, timeout=15)
            if response.status_code != 200:
                logger.warning(f"fxtwitter fallback failed ({response.status_code}) for {url}")
                return None

            payload = response.json()
            tweet = payload.get("tweet", {}) if isinstance(payload, dict) else {}
            media = tweet.get("media", {}) if isinstance(tweet, dict) else {}
            all_media = media.get("all", []) if isinstance(media, dict) else []

            image_urls = []
            for item in all_media:
                if not isinstance(item, dict):
                    continue
                if str(item.get("type", "")).lower() != "photo":
                    continue
                image_url = item.get("url")
                if image_url:
                    image_urls.append(image_url)

            if not image_urls:
                return None

            os.makedirs(download_folder, exist_ok=True)
            downloaded_files = []

            for i, image_url in enumerate(image_urls, 1):
                if status_callback:
                    await ImageDownloader._notify_status(
                        status_callback,
                        min(60 + i * 10, 95),
                        f"Fallback image {i}/{len(image_urls)}",
                    )

                parsed = urlparse(image_url)
                ext = os.path.splitext(parsed.path)[1].lower() or ".jpg"
                if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
                    ext = ".jpg"

                base_name = f"x_{tweet_id}_{i}{ext}"
                target_path = os.path.join(download_folder, base_name)
                suffix = 1
                while os.path.exists(target_path):
                    target_path = os.path.join(download_folder, f"x_{tweet_id}_{i}_{suffix}{ext}")
                    suffix += 1

                img_response = await asyncio.to_thread(requests.get, image_url, timeout=20)
                if img_response.status_code != 200 or not img_response.content:
                    logger.warning(f"fxtwitter image fetch failed ({img_response.status_code}) for {image_url}")
                    continue

                with open(target_path, "wb") as f:
                    f.write(img_response.content)

                final_path = ImageDownloader._safe_rename_with_number(target_path) or target_path
                downloaded_files.append(final_path)

            return downloaded_files if downloaded_files else None
        except Exception as e:
            logger.warning(f"fxtwitter fallback failed for {url}: {e}")
            return None

    @staticmethod
    async def send_images_to_user(image_paths: List[str], message: Message, user_id: int) -> None:
        """Send images to user with proper handling"""
        for i in range(0, len(image_paths), 10):
            batch = image_paths[i:i + 10]
            media_group = [InputMediaPhoto(media=img_path) for img_path in batch]
            try:
                await message.reply_media_group(media=media_group)
            except Exception as e:
                logger.error(f"Error sending image group: {e}")

    @staticmethod
    def _safe_rename_with_number(original_path: str) -> Optional[str]:
        """Safely rename file with a unique short hash prefix"""
        if not os.path.exists(original_path):
            return original_path
        directory = os.path.dirname(original_path)
        filename = os.path.basename(original_path)
        
        # Prevent re-prefixing if a previous scan already renamed the file with a hash pattern.
        # We look for a '-' separator and check if the prefix looks like a short hash (alphanumeric).
        prefix, sep, _rest = filename.partition("-")
        if sep == "-" and prefix.isalnum() and len(prefix) >= 6:
            return original_path
            
        try:
            import uuid
            # Use an 8-character UUID hex string for uniqueness
            short_hash = uuid.uuid4().hex[:8]
            new_filename = f"{short_hash}-{filename}"
            new_path = os.path.join(directory, new_filename)
            
            # Unlikely collision, but check just in case
            if os.path.exists(new_path):
                # Fallback to current timestamp + hash
                new_filename = f"{int(time.time())}-{short_hash}-{filename}"
                new_path = os.path.join(directory, new_filename)
                
            os.rename(original_path, new_path)
            return new_path
        except OSError:
            return original_path

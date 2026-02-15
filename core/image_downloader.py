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

from pyrogram.types import Message, InputMediaPhoto

from config.settings import COOKIE_FILE
from config.paths import DOWNLOAD_FOLDER, IMAGES_FOLDER
from models.data_models import DownloadResult
from core.file_manager import FileManager
from core.log_manager import LogManager
from utils.formatters import Formatter
from models.enums import user_downloads
from ui.keyboards import Keyboards
from core.logger import setup_logger
from core.database import history_db
from utils.url_parser import extract_twitter_username

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
        # Remove query parameters that can interfere
        url = url.split('?')[0]
        
        # Replace x.com with twitter.com for better compatibility
        url = url.replace('x.com', 'twitter.com')
        
        # Ensure URL ends cleanly (no trailing slashes or fragments)
        url = url.rstrip('/').split('#')[0]
        
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
            
            # Use separate images folder (not inside videos)
            download_folder = IMAGES_FOLDER
            
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
            
            # Try Method 1: Syndication API first (most reliable for public tweets)
            logger.debug("Attempting Method 1: Syndication API")
            await ImageDownloader._notify_status(
                status_callback, 25, f"🛰️ Link {index}/{total} - Trying method 1/4"
            )
            downloaded_files = await ImageDownloader._try_syndication_method(url, download_folder, existing_files)
            
            if downloaded_files:
                logger.info(f"Method 1 success: Downloaded {len(downloaded_files)} images")
                await ImageDownloader._notify_status(
                    status_callback, 100, f"✅ Link {index}/{total} - Downloaded {len(downloaded_files)} image(s)"
                )
                info = {
                    'title': f"X Images - {len(downloaded_files)} files",
                    'uploader': 'X (Twitter)',
                    'upload_date': time.strftime('%Y%m%d')
                }
                return downloaded_files, info
            
            # Try Method 2: With detailed config
            print("🔄 Method 1 failed, trying Method 2 (detailed config)...")
            await ImageDownloader._notify_status(
                status_callback, 45, f"🔄 Link {index}/{total} - Trying method 2/4"
            )
            downloaded_files = await ImageDownloader._try_config_method(url, download_folder, existing_files)
            
            if downloaded_files:
                logger.info(f"Method 2 success: Downloaded {len(downloaded_files)} images")
                await ImageDownloader._notify_status(
                    status_callback, 100, f"✅ Link {index}/{total} - Downloaded {len(downloaded_files)} image(s)"
                )
                info = {
                    'title': f"X Images - {len(downloaded_files)} files",
                    'uploader': 'X (Twitter)',
                    'upload_date': time.strftime('%Y%m%d')
                }
                return downloaded_files, info
            
            # Try Method 3: Simple fallback
            print("🔄 Method 2 failed, trying Method 3 (simple method)...")
            await ImageDownloader._notify_status(
                status_callback, 65, f"🔄 Link {index}/{total} - Trying method 3/4"
            )
            downloaded_files = await ImageDownloader._try_simple_method(url, download_folder, existing_files)
            
            if downloaded_files:
                logger.info(f"Method 3 success: Downloaded {len(downloaded_files)} images")
                await ImageDownloader._notify_status(
                    status_callback, 100, f"✅ Link {index}/{total} - Downloaded {len(downloaded_files)} image(s)"
                )
                info = {
                    'title': f"X Images - {len(downloaded_files)} files",
                    'uploader': 'X (Twitter)',
                    'upload_date': time.strftime('%Y%m%d')
                }
                return downloaded_files, info
            
            # Try Method 4: Direct API method with aggressive settings
            print("🔄 Method 3 failed, trying Method 4 (aggressive mode)...")
            await ImageDownloader._notify_status(
                status_callback, 85, f"🔄 Link {index}/{total} - Trying method 4/4"
            )
            downloaded_files = await ImageDownloader._try_aggressive_method(url, download_folder, existing_files)
            
            if downloaded_files:
                logger.info(f"Method 4 success: Downloaded {len(downloaded_files)} images")
                await ImageDownloader._notify_status(
                    status_callback, 100, f"✅ Link {index}/{total} - Downloaded {len(downloaded_files)} image(s)"
                )
                info = {
                    'title': f"X Images - {len(downloaded_files)} files",
                    'uploader': 'X (Twitter)',
                    'upload_date': time.strftime('%Y%m%d')
                }
                return downloaded_files, info
            
            logger.warning("All download methods failed - no images found")
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
    async def _try_syndication_method(url: str, download_folder: str, existing_files: set) -> Optional[List[str]]:
        """Try download using Twitter syndication API (works without authentication)"""
        try:
            config_content = {
                "extractor": {
                    "twitter": {
                        "syndication": True,
                        "api": None,
                        "include": "media",
                        "videos": False,
                        "retweets": True,
                        "quoted": True,
                        "text-tweets": False
                    }
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
                
                logger.debug(f"Method 1 (Syndication): Downloading from syndication API")
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    logger.debug(f"Method 1 exit code: {process.returncode}")
                
                await asyncio.sleep(0.5)
                
                # Try normal file detection first
                new_files = ImageDownloader._get_new_files(download_folder, existing_files)
                
                # If that fails, try parsing output
                if not new_files and stdout:
                    new_files = ImageDownloader._parse_gallery_dl_output(stdout.decode(), download_folder)
                
                return new_files
                
            finally:
                try:
                    os.unlink(config_path)
                except:
                    pass
                    
        except Exception as e:
            logger.debug(f"Method 1 error: {e}")
            return None
    
    @staticmethod
    async def _try_config_method(url: str, download_folder: str, existing_files: set) -> Optional[List[str]]:
        """Try download with detailed configuration"""
        try:
            config_content = {
                "extractor": {
                    "twitter": {
                        "include": "media",
                        "retweets": True,
                        "replies": False,
                        "quoted": True,
                        "cards": False,
                        "conversations": False,
                        "unique": True,
                        "videos": False,
                        "twitpic": False,
                        "text-tweets": False,
                        "syndication": True,
                        "users": "user,author"
                    },
                    "base-directory": download_folder
                },
                "downloader": {
                    "part": False,
                    "mtime": True,
                    "rate": "1M",
                    "retries": 5,
                    "timeout": 60.0
                },
                "output": {
                    "mode": "terminal",
                    "logfile": None,
                    "unsupportedfile": None
                },
                "filename": "{category}_{tweet_id}_{num}.{extension}"
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
                    url
                ]
                
                if os.path.exists(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 0:
                    cmd.extend(["--cookies", COOKIE_FILE])
                
                logger.debug(f"Method 2 (Config): Downloading with detailed config")
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    logger.debug(f"Method 2 exit code: {process.returncode}")
                
                await asyncio.sleep(0.5)
                
                # Try normal file detection first
                new_files = ImageDownloader._get_new_files(download_folder, existing_files)
                
                # If that fails, try parsing output
                if not new_files and stdout:
                    new_files = ImageDownloader._parse_gallery_dl_output(stdout.decode(), download_folder)
                
                return new_files
                
            finally:
                try:
                    os.unlink(config_path)
                except:
                    pass
                    
        except Exception as e:
            logger.debug(f"Method 2 error: {e}")
            return None
    
    @staticmethod
    async def _try_simple_method(url: str, download_folder: str, existing_files: set) -> Optional[List[str]]:
        """Try simple download without config"""
        try:
            cmd = [
                sys.executable,
                "-m", "gallery_dl",
                "-d", download_folder,
                "--no-part",
                url
            ]
            
            if os.path.exists(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 0:
                cmd.extend(["--cookies", COOKIE_FILE])
            
            logger.debug(f"Method 3 (Simple): Downloading with simple method")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.debug(f"Method 3 exit code: {process.returncode}")
            
            await asyncio.sleep(0.5)
            
            # Try normal file detection first
            new_files = ImageDownloader._get_new_files(download_folder, existing_files)
            
            # If that fails, try parsing output
            if not new_files and stdout:
                new_files = ImageDownloader._parse_gallery_dl_output(stdout.decode(), download_folder)
            
            return new_files
            
        except Exception as e:
            logger.debug(f"Method 3 error: {e}")
            return None
    
    @staticmethod
    async def _try_aggressive_method(url: str, download_folder: str, existing_files: set) -> Optional[List[str]]:
        """Try aggressive download with all options enabled"""
        try:
            config_content = {
                "extractor": {
                    "twitter": {
                        "syndication": True,
                        "api": "syndication",
                        "include": "media,timeline",
                        "videos": False,
                        "retweets": True,
                        "quoted": True,
                        "replies": True,
                        "cards": True,
                        "text-tweets": False,
                        "conversations": True
                    }
                },
                "downloader": {
                    "retries": 10,
                    "timeout": 90.0,
                    "part": False
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
                    "-v",
                    url
                ]
                
                if os.path.exists(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 0:
                    cmd.extend(["--cookies", COOKIE_FILE])
                
                logger.debug(f"Method 4 (Aggressive): Downloading with aggressive config")
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    logger.debug(f"Method 4 exit code: {process.returncode}")
                
                await asyncio.sleep(0.5)
                
                # Try normal file detection first
                new_files = ImageDownloader._get_new_files(download_folder, existing_files)
                
                # If that fails, try parsing output
                if not new_files and stdout:
                    new_files = ImageDownloader._parse_gallery_dl_output(stdout.decode(), download_folder)
                
                return new_files
                
            finally:
                try:
                    os.unlink(config_path)
                except:
                    pass
                    
        except Exception as e:
            logger.debug(f"Method 4 error: {e}")
            return None
    
    @staticmethod
    def _parse_gallery_dl_output(output: str, download_folder: str) -> Optional[List[str]]:
        """Parse gallery-dl output to extract downloaded file paths"""
        try:
            downloaded_files = []
            lines = output.split('\n')
            
            for line in lines:
                if line.strip().startswith('#'):
                    file_path = line.strip()[1:].strip()
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
        """Safely rename file with number prefix"""
        if not os.path.exists(original_path):
            return original_path
        directory = os.path.dirname(original_path)
        filename = os.path.basename(original_path)
        # Prevent double-prefixing when a previous scan already renamed the file.
        # Accept any leading digits + "-" prefix (e.g. "01-", "24-", "100-").
        prefix, sep, _rest = filename.partition("-")
        if sep == "-" and prefix.isdigit():
            return original_path
        try:
            next_num = ImageDownloader._get_next_image_number()
            new_filename = f"{next_num:02d}-{filename}"
            new_path = os.path.join(directory, new_filename)
            if os.path.exists(new_path):
                return original_path
            os.rename(original_path, new_path)
            return new_path
        except OSError:
            return original_path

    @staticmethod
    def _get_next_image_number() -> int:
        """Get next sequential number for image file naming"""
        try:
            files = []
            for root, dirs, filenames in os.walk(IMAGES_FOLDER):
                for filename in filenames:
                    if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                        files.append(filename)
            numbers = []
            for f in files:
                if f[:2].isdigit() and f[2] == '-':
                    numbers.append(int(f[:2]))
            return max(numbers) + 1 if numbers else 1
        except Exception:
            return 1

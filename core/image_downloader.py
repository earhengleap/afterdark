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

class ImageDownloader:
    """Handle image downloads from X (Twitter) using gallery-dl - ENHANCED FIX"""
    
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
        
        print(f"🔧 Normalized URL: {url}")
        return url
    
    @staticmethod
    def ensure_gallery_dl():
        """Ensure gallery-dl is installed and updated"""
        try:
            import gallery_dl  # noqa
            print("✅ gallery-dl is available")
            # Try to update gallery-dl for latest Twitter support
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "gallery-dl"], 
                             capture_output=True, timeout=30)
                print("✅ gallery-dl updated to latest version")
            except:
                pass
        except ImportError:
            print("📦 Installing gallery-dl...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "gallery-dl"])
    
    @staticmethod
    def download(url: str, message: Optional[Message] = None) -> Tuple[Optional[List[str]], Optional[Dict]]:
        """Download images from X URL - ENHANCED FIX with URL normalization"""
        try:
            ImageDownloader.ensure_gallery_dl()
            
            # NORMALIZE URL FIRST - This is critical!
            original_url = url
            url = ImageDownloader.normalize_twitter_url(url)
            print(f"📎 Original URL: {original_url}")
            print(f"✨ Clean URL: {url}")
            
            # Use separate images folder (not inside videos)
            download_folder = IMAGES_FOLDER
            
            # Get list of existing files BEFORE download
            existing_files = set()
            for root, dirs, files in os.walk(download_folder):
                for file in files:
                    if file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                        full_path = os.path.join(root, file)
                        existing_files.add(full_path)
            
            print(f"📊 Existing files before download: {len(existing_files)}")
            
            # First, check if cookies file exists and is valid
            if not os.path.exists(COOKIE_FILE):
                print(f"⚠️ Cookie file '{COOKIE_FILE}' not found - downloads may fail for some tweets")
                print(f"💡 To fix: Export your Twitter cookies using a browser extension")
            else:
                # Check if cookies file is not empty
                if os.path.getsize(COOKIE_FILE) == 0:
                    print(f"⚠️ Cookie file is empty - authentication may fail")
            
            # Try Method 1: Syndication API first (most reliable for public tweets)
            print("🔄 Method 1: Trying syndication API (best for public tweets)...")
            downloaded_files = ImageDownloader._try_syndication_method(url, download_folder, existing_files)
            
            if downloaded_files:
                print(f"✅ Method 1 succeeded: Downloaded {len(downloaded_files)} images")
                info = {
                    'title': f"X Images - {len(downloaded_files)} files",
                    'uploader': 'X (Twitter)',
                    'upload_date': time.strftime('%Y%m%d')
                }
                return downloaded_files, info
            
            # Try Method 2: With detailed config
            print("🔄 Method 1 failed, trying Method 2 (detailed config)...")
            downloaded_files = ImageDownloader._try_config_method(url, download_folder, existing_files)
            
            if downloaded_files:
                print(f"✅ Method 2 succeeded: Downloaded {len(downloaded_files)} images")
                info = {
                    'title': f"X Images - {len(downloaded_files)} files",
                    'uploader': 'X (Twitter)',
                    'upload_date': time.strftime('%Y%m%d')
                }
                return downloaded_files, info
            
            # Try Method 3: Simple fallback
            print("🔄 Method 2 failed, trying Method 3 (simple method)...")
            downloaded_files = ImageDownloader._try_simple_method(url, download_folder, existing_files)
            
            if downloaded_files:
                print(f"✅ Method 3 succeeded: Downloaded {len(downloaded_files)} images")
                info = {
                    'title': f"X Images - {len(downloaded_files)} files",
                    'uploader': 'X (Twitter)',
                    'upload_date': time.strftime('%Y%m%d')
                }
                return downloaded_files, info
            
            # Try Method 4: Direct API method with aggressive settings
            print("🔄 Method 3 failed, trying Method 4 (aggressive mode)...")
            downloaded_files = ImageDownloader._try_aggressive_method(url, download_folder, existing_files)
            
            if downloaded_files:
                print(f"✅ Method 4 succeeded: Downloaded {len(downloaded_files)} images")
                info = {
                    'title': f"X Images - {len(downloaded_files)} files",
                    'uploader': 'X (Twitter)',
                    'upload_date': time.strftime('%Y%m%d')
                }
                return downloaded_files, info
            
            print("❌ All download methods failed - no images found")
            print("💡 This could mean:")
            print("   1. The tweet has no images (only text or video)")
            print("   2. The images require authentication")
            print("   3. Gallery-dl needs to be updated")
            return None, None
                
        except Exception as e:
            print(f"❌ Unexpected error in image download: {e}")
            import traceback
            traceback.print_exc()
            if message:
                print(f"❌ Image download failed for {url}: {e}")
            return None, None
    
    @staticmethod
    def _try_syndication_method(url: str, download_folder: str, existing_files: set) -> Optional[List[str]]:
        """Try download using Twitter syndication API (works without authentication)"""
        try:
            # Force syndication API which doesn't require authentication
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
                
                print(f"🖼️ Method 1 (Syndication): Downloading from: {url}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
                if result.returncode != 0:
                    print(f"⚠️ Method 1 exit code: {result.returncode}")
                    if result.stderr:
                        print(f"📝 stderr: {result.stderr[:500]}")
                    if result.stdout:
                        print(f"📝 stdout: {result.stdout[:500]}")
                
                time.sleep(0.5)
                
                # Try normal file detection first
                new_files = ImageDownloader._get_new_files(download_folder, existing_files)
                
                # If that fails, try parsing output
                if not new_files and result.stdout:
                    new_files = ImageDownloader._parse_gallery_dl_output(result.stdout, download_folder)
                
                return new_files
                
            finally:
                try:
                    os.unlink(config_path)
                except:
                    pass
                    
        except Exception as e:
            print(f"❌ Method 1 error: {e}")
            return None
    
    @staticmethod
    def _try_config_method(url: str, download_folder: str, existing_files: set) -> Optional[List[str]]:
        """Try download with detailed configuration"""
        try:
            # Create a comprehensive config file for gallery-dl
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
            
            # Write config to temporary file
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
                
                # Add cookies if available
                if os.path.exists(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 0:
                    cmd.extend(["--cookies", COOKIE_FILE])
                
                print(f"🖼️ Method 2 (Config): Downloading from: {url}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
                # Debug output
                if result.returncode != 0:
                    print(f"⚠️ Method 2 exit code: {result.returncode}")
                    if result.stderr:
                        print(f"📝 stderr: {result.stderr[:500]}")
                
                time.sleep(0.5)
                
                # Try normal file detection first
                new_files = ImageDownloader._get_new_files(download_folder, existing_files)
                
                # If that fails, try parsing output
                if not new_files and result.stdout:
                    new_files = ImageDownloader._parse_gallery_dl_output(result.stdout, download_folder)
                
                return new_files
                
            finally:
                try:
                    os.unlink(config_path)
                except:
                    pass
                    
        except Exception as e:
            print(f"❌ Method 2 error: {e}")
            return None
    
    @staticmethod
    def _try_simple_method(url: str, download_folder: str, existing_files: set) -> Optional[List[str]]:
        """Try simple download without config"""
        try:
            cmd = [
                sys.executable,
                "-m", "gallery_dl",
                "-d", download_folder,
                "--no-part",
                url
            ]
            
            # Add cookies if available
            if os.path.exists(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 0:
                cmd.extend(["--cookies", COOKIE_FILE])
            
            print(f"🖼️ Method 3 (Simple): Downloading from: {url}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                print(f"⚠️ Method 3 exit code: {result.returncode}")
                if result.stderr:
                    print(f"📝 stderr: {result.stderr[:300]}")
            
            time.sleep(0.5)
            
            # Try normal file detection first
            new_files = ImageDownloader._get_new_files(download_folder, existing_files)
            
            # If that fails, try parsing output
            if not new_files and result.stdout:
                new_files = ImageDownloader._parse_gallery_dl_output(result.stdout, download_folder)
            
            return new_files
            
        except Exception as e:
            print(f"❌ Method 3 error: {e}")
            return None
    
    @staticmethod
    def _try_aggressive_method(url: str, download_folder: str, existing_files: set) -> Optional[List[str]]:
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
                    "-v",  # Verbose mode
                    url
                ]
                
                # Add cookies if available
                if os.path.exists(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 0:
                    cmd.extend(["--cookies", COOKIE_FILE])
                
                print(f"🖼️ Method 4 (Aggressive): Downloading from: {url}")
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=150)
                
                if result.returncode != 0:
                    print(f"⚠️ Method 4 exit code: {result.returncode}")
                    if result.stderr:
                        print(f"📝 stderr: {result.stderr[:500]}")
                if result.stdout:
                    print(f"📝 stdout preview: {result.stdout[:800]}")
                
                # Small delay to ensure file system sync
                time.sleep(0.5)
                
                # Try to get files normally first
                new_files = ImageDownloader._get_new_files(download_folder, existing_files)
                
                # If that fails, try parsing the output
                if not new_files and result.stdout:
                    print("🔍 Attempting to parse gallery-dl output for file paths...")
                    new_files = ImageDownloader._parse_gallery_dl_output(result.stdout, download_folder)
                
                return new_files
                
            finally:
                try:
                    os.unlink(config_path)
                except:
                    pass
                    
        except Exception as e:
            print(f"❌ Method 4 error: {e}")
            return None
    
    @staticmethod
    def _parse_gallery_dl_output(output: str, download_folder: str) -> Optional[List[str]]:
        """Parse gallery-dl output to extract downloaded file paths"""
        try:
            downloaded_files = []
            lines = output.split('\n')
            
            for line in lines:
                # Look for lines that start with # (these are downloaded files in gallery-dl output)
                if line.strip().startswith('#'):
                    # Extract the file path
                    file_path = line.strip()[1:].strip()
                    
                    # Check if file exists
                    if os.path.exists(file_path) and os.path.isfile(file_path):
                        # Check if it's an image
                        if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                            print(f"✅ Parsed file from output: {file_path}")
                            
                            # Rename with number prefix
                            new_path = ImageDownloader._safe_rename_with_number(file_path)
                            if new_path:
                                downloaded_files.append(new_path)
                            else:
                                downloaded_files.append(file_path)
            
            if downloaded_files:
                print(f"✨ Parsed {len(downloaded_files)} files from gallery-dl output")
                return downloaded_files
            
            return None
            
        except Exception as e:
            print(f"❌ Error parsing gallery-dl output: {e}")
            return None
    
    @staticmethod
    def _get_new_files(download_folder: str, existing_files: set) -> Optional[List[str]]:
        """Get only newly downloaded files"""
        downloaded_files = []
        
        print(f"🔍 Scanning for new files in: {download_folder}")
        print(f"📊 Existing files count: {len(existing_files)}")
        
        for root, dirs, files in os.walk(download_folder):
            for file in files:
                if file.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                    file_path = os.path.join(root, file)
                    
                    # Debug: Show found file
                    print(f"📁 Found image file: {file_path}")
                    
                    # Only include files that weren't there before download
                    if file_path not in existing_files:
                        print(f"✨ NEW file detected: {file}")
                        
                        # Rename with number prefix using safe method
                        new_path = ImageDownloader._safe_rename_with_number(file_path)
                        if new_path:
                            downloaded_files.append(new_path)
                            print(f"✅ Added to download list: {new_path}")
                        else:
                            downloaded_files.append(file_path)
                            print(f"✅ Added to download list: {file_path}")
                    else:
                        print(f"⏭️ Skipping existing file: {file}")
        
        print(f"📦 Total new files found: {len(downloaded_files)}")
        return downloaded_files if downloaded_files else None
    
    @staticmethod
    def _download_fallback(url: str, download_folder: str, existing_files: set, message: Optional[Message] = None) -> Tuple[Optional[List[str]], Optional[Dict]]:
        """Legacy fallback method - kept for compatibility"""
        downloaded_files = ImageDownloader._try_simple_method(url, download_folder, existing_files)
        
        if downloaded_files:
            info = {
                'title': f"X Images - {len(downloaded_files)} files",
                'uploader': 'X (Twitter)',
                'upload_date': time.strftime('%Y%m%d')
            }
            return downloaded_files, info
        
        return None, None
    
    @staticmethod
    def _safe_rename_with_number(original_path: str) -> Optional[str]:
        """Safely rename file with number prefix, handling file exists errors"""
        if not os.path.exists(original_path):
            return original_path
        
        directory = os.path.dirname(original_path)
        filename = os.path.basename(original_path)
        
        # Check if already has number prefix
        if filename[:3].isdigit() and filename[3] == '-':
            return original_path
        
        try:
            # Get next number for images specifically
            next_num = ImageDownloader._get_next_image_number()
            new_filename = f"{next_num:02d}-{filename}"
            new_path = os.path.join(directory, new_filename)
            
            # Check if target file already exists
            if os.path.exists(new_path):
                print(f"⚠️ File already exists, using original: {new_path}")
                return original_path
            
            os.rename(original_path, new_path)
            return new_path
        except OSError as e:
            print(f"⚠️ Could not rename file {filename}: {e}")
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
                # Extract number from filename like "01-filename.jpg"
                if f[:2].isdigit() and f[2] == '-':
                    try:
                        numbers.append(int(f[:2]))
                    except ValueError:
                        pass
            
            return max(numbers) + 1 if numbers else 1
        except Exception as e:
            print(f"Error getting next image number: {e}")
            return 1
    
    @staticmethod
    def download_multiple(urls: List[str], message: Message, user_id: int,
                         detection_msg: Optional[Message] = None) -> None:
        """Download multiple images with progress tracking"""
        total = len(urls)
        success_count = 0
        failed_count = 0
        downloaded_paths = []
        url_results = []
        
        print(f"🔄 Starting bulk image download for {total} URLs")
        
        if detection_msg:
            status_msg = detection_msg
            status_msg.edit_text(
                f"🖼️ **Starting Bulk Image Download**\n\n"
                f"Total URLs: {total}\n"
                f"Preparing downloads..."
            )
        else:
            status_msg = message.reply_text(
                f"🖼️ **Starting Bulk Image Download**\n\n"
                f"Total URLs: {total}\n"
                f"Preparing downloads..."
            )
        
        overall_start = time.time()
        
        # Download phase
        for idx, url in enumerate(urls, 1):
            try:
                status_msg.edit_text(
                    f"🖼️ **Bulk Image Download Progress**\n\n"
                    f"**URL {idx}/{total}**\n"
                    f"✅ Downloaded: {success_count}\n"
                    f"❌ Failed: {failed_count}\n\n"
                    f"🔗 Current URL:\n`{url[:50]}...`\n\n"
                    f"⏳ Downloading images..."
                )
                
                image_paths, info = ImageDownloader.download(url, message)
                
                if image_paths and len(image_paths) > 0:
                    success_count += 1
                    downloaded_paths.extend(image_paths)
                    
                    for img_path in image_paths:
                        url_results.append(DownloadResult(
                            url=url,
                            status='success',
                            filename=os.path.basename(img_path),
                            size=os.path.getsize(img_path) / (1024 * 1024)
                        ))
                    
                    print(f"✅ Downloaded {idx}/{total}: {len(image_paths)} NEW images from {url}")
                    
                    status_msg.edit_text(
                        f"🖼️ **Bulk Image Download Progress**\n\n"
                        f"**URL {idx}/{total}**\n"
                        f"✅ Downloaded: {success_count}\n"
                        f"❌ Failed: {failed_count}\n\n"
                        f"✅ **Success:** {len(image_paths)} NEW images from URL\n\n"
                        f"⏳ Continuing..."
                    )
                    time.sleep(0.5)
                else:
                    failed_count += 1
                    url_results.append(DownloadResult(
                        url=url,
                        status='failed',
                        error='Download failed - No images found or invalid URL'
                    ))
                    print(f"❌ Failed to download images from {idx}/{total}: {url}")
                    
            except Exception as e:
                error_msg = ImageDownloader._parse_error(str(e))
                failed_count += 1
                url_results.append(DownloadResult(
                    url=url,
                    status='failed',
                    error=error_msg
                ))
                print(f"❌ Error downloading images from {idx}/{total}: {error_msg}")
        
        total_time = time.time() - overall_start
        
        # Store images in multiple keys for different access methods
        user_downloads[f"{user_id}_bulk_images_downloaded"] = downloaded_paths
        user_downloads[f"{user_id}_bulk_downloaded_images"] = downloaded_paths
        
        print(f"📊 Bulk image download completed: {success_count} success, {failed_count} failed")
        print(f"📁 Downloaded NEW images: {len(downloaded_paths)}")
        print(f"🔑 Stored images under keys: {user_id}_bulk_images_downloaded and {user_id}_bulk_downloaded_images")
        
        try:
            status_msg.delete()
        except Exception:
            pass
        
        # Send ONLY newly downloaded images to user
        print(f"🔄 Sending {len(downloaded_paths)} NEW images to user...")
        ImageDownloader._send_downloaded_images(downloaded_paths, message, user_id)
        
        # Send summary
        ImageDownloader._send_summary(url_results, success_count, failed_count,
                                    total, total_time, message, user_id, downloaded_paths)
    
    @staticmethod
    def _parse_error(error_msg: str) -> str:
        """Parse and simplify error messages"""
        if "No images could be found" in error_msg or "No images" in error_msg:
            return "No images found in this tweet"
        elif "private" in error_msg.lower():
            return "Tweet is private or restricted"
        elif "deleted" in error_msg.lower():
            return "Tweet has been deleted"
        elif "unavailable" in error_msg.lower():
            return "Images are unavailable"
        elif "login required" in error_msg.lower():
            return "Login required - may need cookies"
        elif "suspended" in error_msg.lower():
            return "Account suspended or content removed"
        else:
            return error_msg[:100] if len(error_msg) > 100 else error_msg
    
    @staticmethod
    def _send_downloaded_images(downloaded_paths: List[str], message: Message, user_id: int) -> None:
        """Send ONLY newly downloaded images to user - NO CAPTIONS"""
        if not downloaded_paths:
            print("❌ No new images to send")
            return
        
        print(f"🔄 Preparing to send {len(downloaded_paths)} newly downloaded images...")
        
        # Store all images in a list for bulk upload
        user_downloads[f"{user_id}_bulk_images_downloaded"] = downloaded_paths
        print(f"📁 Stored {len(downloaded_paths)} images for bulk upload under key: {user_id}_bulk_images_downloaded")
        
        # Send images INDIVIDUALLY (no grouping) to user
        for idx, img_path in enumerate(downloaded_paths):
            try:
                if not os.path.exists(img_path):
                    print(f"⚠️ Image file not found: {img_path}")
                    continue
                
                image_name = os.path.basename(img_path)
                
                # Create SHORT unique key for each image (to avoid callback data limit)
                img_key = f"{user_id}_img_{idx}"
                user_downloads[img_key] = img_path
                
                print(f"📁 Stored single image {image_name} under key: {img_key}")
                
                # Send individual photo WITHOUT caption
                message.reply_photo(
                    photo=img_path,
                    reply_markup=Keyboards.single_image_upload(img_key)
                )
                print(f"✅ Sent individual image {idx+1}/{len(downloaded_paths)}: {image_name}")
                
            except Exception as e:
                print(f"❌ Error sending individual image {img_path}: {e}")
        
        # Send success message with upload button
        message.reply_text(
            f"✅ **Successfully Downloaded {len(downloaded_paths)} Images**\n\n"
            f"All newly downloaded images have been sent above.\n\n"
            f"What would you like to do next?",
            reply_markup=Keyboards.bulk_image_download_complete(user_id, downloaded_paths)
        )
        print(f"✅ Success message sent for {len(downloaded_paths)} images")
    
    @staticmethod
    def _send_summary(url_results: List[DownloadResult], success_count: int, 
                     failed_count: int, total: int, total_time: float, 
                     message: Message, user_id: int, downloaded_paths: List[str]) -> None:
        """Send download summary with results"""
        from ui.keyboards import Keyboards
        
        MAX_MESSAGE_LENGTH = 4000
        
        success_results = [r for r in url_results if r.status == 'success']
        failed_results = [r for r in url_results if r.status == 'failed']
        
        total_images = len(downloaded_paths)
        
        summary_text = ""
        
        if success_results:
            summary_text += "✅ **Successfully Downloaded:**\n\n"
            urls_added = 0
            for idx, result in enumerate(success_results, 1):
                url_entry = f"{idx}. `{result.filename[:40]}...`\n"
                url_entry += f"   💾 {result.size:.2f} MB\n\n"
                
                if len(summary_text + url_entry) > MAX_MESSAGE_LENGTH - 1500:
                    remaining = len(success_results) - urls_added
                    summary_text += f"... and {remaining} more successful download(s)\n\n"
                    break
                else:
                    summary_text += url_entry
                    urls_added += 1
        
        if failed_results:
            summary_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            summary_text += "❌ **Failed Downloads:**\n\n"
            
            failed_added = 0
            for idx, result in enumerate(failed_results, 1):
                failed_entry = f"{idx}. ```\n{result.url}\n```\n"
                if result.error:
                    failed_entry += f"   ⚠️ {result.error}\n\n"
                else:
                    failed_entry += f"   ⚠️ Download failed\n\n"
                
                if len(summary_text + failed_entry) > MAX_MESSAGE_LENGTH - 500:
                    remaining = len(failed_results) - failed_added
                    summary_text += f"... and {remaining} more failed URL(s)\n\n"
                    break
                else:
                    summary_text += failed_entry
                    failed_added += 1
        
        summary_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        summary_text += "🖼️ **Bulk Image Download Complete!**\n\n"
        summary_text += (
            f"📊 **Summary:**\n"
            f"• Total URLs: {total}\n"
            f"• ✅ Downloaded: {success_count}\n"
            f"• ❌ Failed: {failed_count}\n"
            f"• 🖼️ Total NEW Images: {total_images}\n"
            f"• ⏱️ Time: {Formatter.duration(total_time)}\n\n"
        )
        
        if success_count > 0:
            summary_text += f"📁 {total_images} NEW image(s) saved and sent to you.\n\n"
            if failed_count > 0:
                summary_text += "💡 **Tip:** You can copy the failed URLs above and retry them.\n\n"
            summary_text += "What would you like to do next?"
            keyboard = Keyboards.bulk_image_download_complete(user_id, downloaded_paths)
        else:
            summary_text += "No NEW images were downloaded successfully.\n\n"
            summary_text += "💡 **Tip:** Check if the URLs contain images and are publicly accessible."
            keyboard = Keyboards.back_to_main()
        
        message.reply_text(summary_text, reply_markup=keyboard, disable_web_page_preview=True)
    
    @staticmethod
    def send_images_to_user(image_paths: List[str], message: Message, user_id: int) -> None:
        """Send images to user individually - NO CAPTIONS (for use by VideoDownloader)"""
        if not image_paths:
            return
        
        print(f"🔄 Sending {len(image_paths)} images to user individually...")
        
        # Send images INDIVIDUALLY to user
        for idx, img_path in enumerate(image_paths):
            try:
                if not os.path.exists(img_path):
                    print(f"⚠️ Image file not found: {img_path}")
                    continue
                
                image_name = os.path.basename(img_path)
                
                # Create SHORT unique key for each image (to avoid callback data limit)
                img_key = f"{user_id}_bulk_img_{idx}"
                user_downloads[img_key] = img_path
                
                print(f"📁 Stored bulk image {image_name} under key: {img_key}")
                
                # Send individual photo WITHOUT caption
                message.reply_photo(
                    photo=img_path,
                    reply_markup=Keyboards.single_image_upload(img_key)
                )
                print(f"✅ Sent individual image {idx+1}/{len(image_paths)}: {image_name}")
                
            except Exception as e:
                print(f"❌ Error sending individual image {img_path}: {e}")
    
    @staticmethod
    def diagnose_url(url: str) -> None:
        """Diagnose why a specific URL might not be working"""
        print(f"🔍 Diagnosing URL: {url}")
        
        # Normalize URL first
        normalized_url = ImageDownloader.normalize_twitter_url(url)
        print(f"✨ Normalized URL: {normalized_url}")
        
        # Check if it's a valid Twitter/X URL
        if not any(domain in url for domain in ['x.com', 'twitter.com']):
            print("❌ Not a Twitter/X URL")
            return
        
        # Try to get basic info about the tweet
        try:
            import requests
            response = requests.head(normalized_url, timeout=10, allow_redirects=True)
            print(f"📡 HTTP Status: {response.status_code}")
            
            if response.status_code == 404:
                print("❌ Tweet not found (404) - may be deleted")
            elif response.status_code == 403:
                print("❌ Access forbidden (403) - may be private or restricted")
            elif response.status_code == 200:
                print("✅ URL is accessible")
            elif response.status_code == 429:
                print("⚠️ Rate limited (429) - too many requests")
            else:
                print(f"⚠️ Unexpected status: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Could not access URL: {e}")
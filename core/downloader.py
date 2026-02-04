"""
Video download functionality - SUPPORTS MULTIPLE VIDEOS PER URL
"""

import os
import time
import asyncio
from typing import List, Tuple, Optional, Dict

import yt_dlp
from pyrogram.types import Message

from config.settings import COOKIE_FILE, FFMPEG_PATH
from config.paths import DOWNLOAD_FOLDER
from models.data_models import DownloadResult, VideoInfo
from core.file_manager import FileManager
from core.log_manager import LogManager
from core.image_downloader import ImageDownloader
from utils.formatters import Formatter
from utils.video_processor import VideoProcessor
from models.enums import user_downloads
from ui.keyboards import Keyboards
from core.logger import setup_logger
from core.progress_tracker import download_tracker, ProgressTracker
from utils.media_info import MediaInfo
from core.database import history_db
from utils.url_parser import extract_twitter_username

logger = setup_logger("VideoDownloader")

class VideoDownloader:
    """Handle video downloads from X (Twitter) - SUPPORTS MULTIPLE VIDEOS PER URL"""
    
    # Class variable to store progress state
    _progress_data = {}
    
    @staticmethod
    def download(url: str, message: Optional[Message] = None, status_msg: Optional[Message] = None, 
                 index: int = 1, total: int = 1) -> Tuple[Optional[List[str]], Optional[Dict]]:
        """
        Download video(s) from URL - SUPPORTS MULTIPLE VIDEOS
        Returns: (list_of_video_paths, info_dict) or (None, None)
        """
        
        # Define quality profiles to try in order
        quality_profiles = [
            {
                'name': 'High Quality',
                'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]/best',
                'merge_output_format': 'mp4',
            },
            {
                'name': 'Standard Quality',
                'format': 'best[ext=mp4]/best',
                'merge_output_format': 'mp4',
            },
            {
                'name': 'Any Available',
                'format': 'best',
                'merge_output_format': 'mp4',
            }
        ]
        
        for profile in quality_profiles:
            try:
                # Progress hook for yt-dlp
                def progress_hook(d):
                    if status_msg and d['status'] == 'downloading':
                        try:
                            downloaded = d.get('downloaded_bytes', 0)
                            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                            speed = d.get('speed', 0) or 0
                            filename = d.get('filename', 'video.mp4')
                            if '/' in filename:
                                filename = filename.split('/')[-1]
                            elif '\\' in filename:
                                filename = filename.split('\\')[-1]
                            
                            # Store for async update
                            VideoDownloader._progress_data['downloaded'] = downloaded
                            VideoDownloader._progress_data['total'] = total_bytes
                            VideoDownloader._progress_data['speed'] = speed
                            VideoDownloader._progress_data['filename'] = filename
                        except Exception:
                            pass
                
                ydl_opts = {
                    'cookiefile': COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
                    'format': profile['format'],
                    'merge_output_format': profile['merge_output_format'],
                    'ffmpeg_location': FFMPEG_PATH,
                    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s_%(autonumber)s.%(ext)s'),
                    'noplaylist': False,  # Changed to False to allow multiple videos
                    'quiet': True,
                    'no_warnings': True,
                    'no_color': True,
                    'extract_flat': False,
                    'ignoreerrors': False,
                    'progress_hooks': [progress_hook] if status_msg else [],
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    downloaded_files = []
                    
                    # Check if this is a playlist/multiple videos
                    if 'entries' in info:
                        # Multiple videos found
                        logger.info(f"Found {len(info['entries'])} videos in tweet")
                        for entry in info['entries']:
                            if entry and 'requested_downloads' in entry:
                                for download in entry['requested_downloads']:
                                    if 'filepath' in download:
                                        downloaded_file = download['filepath']
                                        if os.path.exists(downloaded_file):
                                            new_path = FileManager.rename_with_number(downloaded_file)
                                            downloaded_files.append(new_path)
                                            LogManager.add_entry(entry, os.path.basename(new_path), url)
                    else:
                        # Single video
                        if 'requested_downloads' in info:
                            downloaded_file = info['requested_downloads'][0]['filepath']
                        else:
                            title = info.get('title', 'video')
                            downloaded_file = os.path.join(DOWNLOAD_FOLDER, f"{title}.mp4")
                        
                        if downloaded_file and os.path.exists(downloaded_file):
                            new_path = FileManager.rename_with_number(downloaded_file)
                            downloaded_files.append(new_path)
                            LogManager.add_entry(info, os.path.basename(new_path), url)
                    
                    if downloaded_files:
                        logger.info(f"Downloaded {len(downloaded_files)} video(s) using {profile['name']}")
                        return downloaded_files, info
                    
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                
                # Check if it's actually a "no video" error (not a quality issue)
                if "No video could be found" in error_msg or "Unsupported URL" in error_msg:
                    # This is not a video, don't try other profiles
                    return None, None
                
                # Otherwise it's a quality/format issue, try next profile
                logger.warning(f"{profile['name']} failed, trying next profile")
                continue
                
            except Exception as e:
                error_msg = str(e)
                
                # Check if it's a "no video" error
                if "No video could be found" in error_msg or "Unsupported URL" in error_msg:
                    return None, None
                
                # Try next profile for other errors
                logger.warning(f"{profile['name']} error: {e}, trying next profile")
                continue
        
        # All profiles failed
        return None, None
    
    @staticmethod
    async def download_multiple(urls: List[str], message: Message, user_id: int,
                        detection_msg: Optional[Message] = None) -> None:
        """Download multiple videos with progress tracking - NOW HANDLES BOTH VIDEOS AND IMAGES"""
        total = len(urls)
        video_success_count = 0
        image_success_count = 0
        failed_count = 0
        downloaded_video_paths = []
        downloaded_image_paths = []
        url_results = []
        
        logger.info(f"Starting bulk download: {total} URLs (videos and images)")
        
        initial_text = (
            f"📥 **Bulk Download Started**\n\n"
            f"🔢 **Total URLs:** {total}\n"
            f"⚙️ **Status:** Initializing...\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
        
        if detection_msg:
            status_msg = detection_msg
            await status_msg.edit_text(initial_text)
        else:
            status_msg = await message.reply_text(initial_text)
        
        overall_start = time.time()
        
        # Download phase - try both video and image for each URL
        for idx, url in enumerate(urls, 1):
            try:
                processed = idx - 1
                remaining = total - processed
                
                # Format URL for display
                url_display = url.replace('https://', '').replace('http://', '')
                if len(url_display) > 40:
                    url_display = url_display[:37] + '...'
                
                await status_msg.edit_text(
                    f"📥 **Analyzing URL** ({idx}/{total})\n\n"
                    f"🔗 **Source:** `{url_display}`\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"📊 **Statistics:**\n"
                    f"• 🎬 Videos: {video_success_count}\n"
                    f"• 📸 Images: {image_success_count}\n"
                    f"• ❌ Failed: {failed_count}\n"
                    f"• ⏳ Remaining: {remaining}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"⚙️ Processing..."
                )
                
                # Try video download first with progress tracking
                video_paths, video_info = VideoDownloader.download(url, message, status_msg, idx, total)
                
                if video_paths and len(video_paths) > 0:
                    video_success_count += 1
                    downloaded_video_paths.extend(video_paths)
                    
                    # Track each video in history
                    source_username = extract_twitter_username(url)
                    for video_path in video_paths:
                        file_size = os.path.getsize(video_path)
                        filename = os.path.basename(video_path)
                        
                        # Add to history
                        history_db.add_entry(
                            user_id=user_id,
                            url=url,
                            source_username=source_username,
                            filename=filename,
                            status='success',
                            content_type='video',
                            file_size=file_size
                        )
                        
                        url_results.append(DownloadResult(
                            url=url,
                            status='success',
                            filename=filename,
                            size=file_size / (1024 * 1024),
                            content_type='video'
                        ))
                    
                    logger.info(f"Downloaded {len(video_paths)} video(s) from URL {idx}/{total}")
                    
                    # Show success message briefly
                    success_msg = (
                        f"✅ **Downloaded** ({idx}/{total})\n\n"
                        f"📹 Found {len(video_paths)} video(s)\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"📊 **Statistics:**\n"
                        f"• 🎬 Videos: {video_success_count}\n"
                        f"• 📸 Images: {image_success_count}\n"
                        f"• ❌ Failed: {failed_count}\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"⏳ Continuing..."
                    )
                    await status_msg.edit_text(success_msg)
                    await asyncio.sleep(0.5)
                else:
                    # Video download failed, try image download
                    logger.debug(f"No video found, attempting image download for URL {idx}/{total}")
                    image_paths, image_info = await ImageDownloader.download(url, message)
                    
                    if image_paths and len(image_paths) > 0:
                        image_success_count += 1
                        downloaded_image_paths.extend(image_paths)
                        
                        # Track image download in history
                        source_username = extract_twitter_username(url)
                        total_size = sum(os.path.getsize(img) for img in image_paths if os.path.exists(img))
                        
                        # Add to history
                        history_db.add_entry(
                            user_id=user_id,
                            url=url,
                            source_username=source_username,
                            filename=f"{len(image_paths)} images",
                            status='success',
                            content_type='image',
                            file_size=total_size
                        )
                        
                        for img_path in image_paths:
                            url_results.append(DownloadResult(
                                url=url,
                                status='success',
                                filename=os.path.basename(img_path),
                                size=os.path.getsize(img_path) / (1024 * 1024),
                                content_type='image'
                            ))
                        
                        logger.info(f"Downloaded {len(image_paths)} image(s) from URL {idx}/{total}")
                        
                        await status_msg.edit_text(
                            f"📥 **Bulk Download Progress**\n\n"
                            f"**URL {idx}/{total}**\n"
                            f"🎬 Videos: {video_success_count}\n"
                            f"🖼️ Images: {image_success_count}\n"
                            f"❌ Failed: {failed_count}\n\n"
                            f"✅ **Image Success:** {len(image_paths)} images from URL\n\n"
                            f"⏳ Continuing..."
                        )
                        await asyncio.sleep(0.5)
                    else:
                        # Both video and image download failed
                        failed_count += 1
                        url_results.append(DownloadResult(
                            url=url,
                            status='failed',
                            error='Download failed - No video or images found',
                            content_type='unknown'
                        ))
                        logger.warning(f"Failed to download from URL {idx}/{total}")
                        
            except Exception as e:
                error_msg = VideoDownloader._parse_error(str(e))
                failed_count += 1
                
                # Track failed download in history
                source_username = extract_twitter_username(url)
                history_db.add_entry(
                    user_id=user_id,
                    url=url,
                    source_username=source_username,
                    filename=None,
                    status='failed',
                    content_type='unknown',
                    file_size=0,
                    error_message=error_msg
                )
                
                url_results.append(DownloadResult(
                    url=url,
                    status='failed',
                    error=error_msg,
                    content_type='unknown'
                ))
                logger.error(f"Error downloading URL {idx}/{total}: {error_msg}")
        
        total_time = time.time() - overall_start
        total_success = video_success_count + image_success_count
        
        # Store both videos and images for bulk upload
        user_downloads[f"{user_id}_bulk_downloaded_videos"] = downloaded_video_paths
        user_downloads[f"{user_id}_bulk_downloaded_images"] = downloaded_image_paths
        user_downloads[f"{user_id}_bulk_downloaded_all"] = downloaded_video_paths + downloaded_image_paths
        
        logger.info(f"Bulk download complete: {total_success} success ({video_success_count} videos, {image_success_count} images), {failed_count} failed")
        logger.info(f"Downloaded {len(downloaded_video_paths)} video files, {len(downloaded_image_paths)} image files")
        
        try:
            await status_msg.delete()
        except Exception:
            pass
        
        # Send downloaded content to user
        if downloaded_video_paths or downloaded_image_paths:
            logger.info(f"Sending {len(downloaded_video_paths)} videos and {len(downloaded_image_paths)} images to user")
            await VideoDownloader._send_downloaded_content(downloaded_video_paths, downloaded_image_paths, message, user_id)
        
        # Send summary
        await VideoDownloader._send_summary(url_results, video_success_count, image_success_count, 
                                    failed_count, total, total_time, message, user_id, 
                                    downloaded_video_paths, downloaded_image_paths)
    
    @staticmethod
    async def _send_downloaded_content(video_paths: List[str], image_paths: List[str], 
                               message: Message, user_id: int) -> None:
        """Send downloaded videos and images to user"""
        # Send videos with progress tracking
        for idx, video_path in enumerate(video_paths):
            try:
                video_name = os.path.basename(video_path)
                file_size = os.path.getsize(video_path)
                
                # Create enhanced caption with detailed info
                caption = MediaInfo.create_caption(video_path, include_filename=True)
                
                # Use short key for videos
                video_key = f"{user_id}_v_{idx}"
                user_downloads[video_key] = video_path
                
                # Create upload status message
                upload_msg = await message.reply_text(
                    f"📤 **Preparing upload**\n\n"
                    f"📹 {video_name[:30]}{'...' if len(video_name) > 30 else ''}\n"
                    f"💾 Size: {file_size / (1024 * 1024):.1f} MB\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"⏳ Starting upload..."
                )
                
                # Get resolution for video
                width, height = VideoProcessor.get_resolution(video_path)
                
                # Track upload start time for progress
                start_time = time.time()
                progress_key = f"upload_{user_id}_{idx}"
                
                # Send video with upload progress
                await message.reply_video(
                    video=video_path,
                    width=width if width else 720,
                    height=height if height else 1280,
                    supports_streaming=True,
                    caption=caption,
                    reply_markup=Keyboards.single_video_upload(video_key),
                    progress=ProgressTracker.callback,
                    progress_args=(progress_key, upload_msg, video_name, start_time)
                )
                
                # Delete upload status message
                try:
                    await upload_msg.delete()
                except Exception:
                    pass
                
                logger.info(f"Sent video [{idx+1}/{len(video_paths)}]: {video_name} ({file_size / (1024 * 1024):.2f} MB)")
                
            except Exception as e:
                logger.error(f"Failed to send video {os.path.basename(video_path)}: {e}")
        
        # Send images individually to avoid Pyrogram media group bug
        if image_paths:
            logger.info(f"Sending {len(image_paths)} images individually")
            for img_path in image_paths:
                try:
                    if os.path.exists(img_path):
                        await message.reply_photo(photo=img_path)
                        await asyncio.sleep(0.5) # Avoid flood wait
                except Exception as e:
                    logger.error(f"Failed to send image {os.path.basename(img_path)}: {e}")
    
    @staticmethod
    async def _send_summary(url_results: List[DownloadResult], video_success_count: int, 
                     image_success_count: int, failed_count: int, total: int, 
                     total_time: float, message: Message, user_id: int, 
                     video_paths: List[str], image_paths: List[str]) -> None:
        """Send download summary with results"""
        from ui.keyboards import Keyboards
        
        MAX_MESSAGE_LENGTH = 4000
        
        success_results = [r for r in url_results if r.status == 'success']
        failed_results = [r for r in url_results if r.status == 'failed']
        
        video_results = [r for r in success_results if getattr(r, 'content_type', '') == 'video']
        image_results = [r for r in success_results if getattr(r, 'content_type', '') == 'image']
        
        summary_text = ""
        
        if video_results:
            summary_text += "🎬 **Successfully Downloaded Videos:**\n\n"
            for idx, result in enumerate(video_results, 1):
                url_entry = f"{idx}. `{result.filename[:40]}...`\n"
                url_entry += f"   💾 {result.size:.2f} MB\n\n"
                
                if len(summary_text + url_entry) > MAX_MESSAGE_LENGTH - 2000:
                    remaining = len(video_results) - idx + 1
                    summary_text += f"... and {remaining} more video(s)\n\n"
                    break
                summary_text += url_entry
        
        if image_results:
            summary_text += "🖼️ **Successfully Downloaded Images:**\n\n"
            images_shown = 0
            for idx, result in enumerate(image_results, 1):
                url_entry = f"{idx}. `{result.filename[:40]}...`\n"
                url_entry += f"   💾 {result.size:.2f} MB\n\n"
                
                if len(summary_text + url_entry) > MAX_MESSAGE_LENGTH - 1500:
                    remaining = len(image_results) - images_shown
                    summary_text += f"... and {remaining} more image(s)\n\n"
                    break
                summary_text += url_entry
                images_shown += 1
        
        if failed_results:
            summary_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
            summary_text += "❌ **Failed Downloads:**\n\n"
            
            failed_shown = 0
            for idx, result in enumerate(failed_results, 1):
                failed_entry = f"{idx}. ```\n{result.url}\n```\n"
                if result.error:
                    failed_entry += f"   ⚠️ {result.error}\n\n"
                else:
                    failed_entry += f"   ⚠️ Download failed\n\n"
                
                if len(summary_text + failed_entry) > MAX_MESSAGE_LENGTH - 500:
                    remaining = len(failed_results) - failed_shown
                    summary_text += f"... and {remaining} more failed URL(s)\n\n"
                    break
                summary_text += failed_entry
                failed_shown += 1
        
        summary_text += "━━━━━━━━━━━━━━━━━━━━\n\n"
        summary_text += "📦 **Bulk Download Complete!**\n\n"
        summary_text += (
            f"📊 **Summary:**\n"
            f"• Total URLs: {total}\n"
            f"• 🎬 Videos: {video_success_count} URLs ({len(video_paths)} files)\n"
            f"• 🖼️ Images: {image_success_count} URLs ({len(image_paths)} files)\n"
            f"• ❌ Failed: {failed_count}\n"
            f"• ⏱️ Time: {Formatter.duration(total_time)}\n\n"
        )
        
        total_success = video_success_count + image_success_count
        total_files = len(video_paths) + len(image_paths)
        
        if total_success > 0:
            summary_text += f"📁 {total_files} file(s) downloaded from {total_success} URL(s) and sent to you.\n\n"
            if failed_count > 0:
                summary_text += "💡 **Tip:** You can copy the failed URLs above and retry them.\n\n"
            summary_text += "What would you like to do next?"
            keyboard = Keyboards.bulk_download_complete_mixed(user_id, video_paths, image_paths)
        else:
            summary_text += "No videos or images were downloaded successfully.\n\n"
            summary_text += "💡 **Tip:** Check if the URLs contain videos/images and are publicly accessible."
            keyboard = Keyboards.back_to_main()
        
        sent_msg = await message.reply_text(summary_text, reply_markup=keyboard, disable_web_page_preview=True)
        
        # Start Auto-Upload Timer if there is success content
        if total_success > 0:
            from core.auto_scheduler import AutoScheduler
            
            # Determine content type and payload
            content_type = ""
            content_path = None
            
            if video_paths and image_paths:
                content_type = "mixed_bulk"
                content_path = {'videos': video_paths, 'images': image_paths}
            elif video_paths:
                content_type = "video_bulk"
                content_path = video_paths
            elif image_paths:
                content_type = "image_bulk"
                content_path = image_paths
            
            if content_type:
                # Use the client from the message
                app = message._client
                await AutoScheduler.start_timer(
                    client=app,
                    message=sent_msg,
                    user_id=user_id,
                    content_type=content_type,
                    content_path=content_path,
                    duration=120
                )
    
    @staticmethod
    def _parse_error(error_msg: str) -> str:
        """Parse and simplify error messages"""
        if "No video could be found" in error_msg:
            return "No video found in this tweet"
        elif "private" in error_msg.lower():
            return "Tweet is private or restricted"
        elif "deleted" in error_msg.lower():
            return "Tweet has been deleted"
        elif "unavailable" in error_msg.lower():
            return "Content is unavailable"
        elif "Unsupported URL" in error_msg:
            return "Unsupported URL format"
        else:
            return error_msg[:100] if len(error_msg) > 100 else error_msg

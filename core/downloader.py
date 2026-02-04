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

class VideoDownloader:
    """Handle video downloads from X (Twitter) - SUPPORTS MULTIPLE VIDEOS PER URL"""
    
    @staticmethod
    def download(url: str, message: Optional[Message] = None) -> Tuple[Optional[List[str]], Optional[Dict]]:
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
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    downloaded_files = []
                    
                    # Check if this is a playlist/multiple videos
                    if 'entries' in info:
                        # Multiple videos found
                        print(f"📹 Found {len(info['entries'])} videos in this tweet")
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
                        print(f"✅ Downloaded {len(downloaded_files)} video(s) with {profile['name']}")
                        return downloaded_files, info
                    
            except yt_dlp.utils.DownloadError as e:
                error_msg = str(e)
                
                # Check if it's actually a "no video" error (not a quality issue)
                if "No video could be found" in error_msg or "Unsupported URL" in error_msg:
                    # This is not a video, don't try other profiles
                    return None, None
                
                # Otherwise it's a quality/format issue, try next profile
                print(f"⚠️ {profile['name']} failed, trying next profile...")
                continue
                
            except Exception as e:
                error_msg = str(e)
                
                # Check if it's a "no video" error
                if "No video could be found" in error_msg or "Unsupported URL" in error_msg:
                    return None, None
                
                # Try next profile for other errors
                print(f"⚠️ {profile['name']} error: {e}, trying next profile...")
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
        
        print(f"🔄 Starting bulk download for {total} URLs (videos and images)")
        
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
                
                await status_msg.edit_text(
                    f"📥 **Bulk Download in Progress**\n\n"
                    f"🔄 **Processing:** {idx}/{total}\n"
                    f"🎬 **Videos:** {video_success_count}\n"
                    f"📸 **Images:** {image_success_count}\n"
                    f"❌ **Failed:** {failed_count}\n"
                    f"⏳ **Remaining:** {remaining}\n"
                    f"━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔗 **Current:** `{url[:40]}...`"
                )
                
                # Try video download first
                video_paths, video_info = VideoDownloader.download(url, message)
                
                if video_paths and len(video_paths) > 0:
                    video_success_count += 1
                    downloaded_video_paths.extend(video_paths)
                    
                    for video_path in video_paths:
                        url_results.append(DownloadResult(
                            url=url,
                            status='success',
                            filename=os.path.basename(video_path),
                            size=os.path.getsize(video_path) / (1024 * 1024),
                            content_type='video'
                        ))
                    
                    print(f"✅ Downloaded {len(video_paths)} video(s) from {idx}/{total}: {url}")
                    
                    await status_msg.edit_text(
                        f"📥 **Bulk Download Progress**\n\n"
                        f"**URL {idx}/{total}**\n"
                        f"🎬 Videos: {video_success_count}\n"
                        f"🖼️ Images: {image_success_count}\n"
                        f"❌ Failed: {failed_count}\n\n"
                        f"✅ **Video Success:** {len(video_paths)} video(s) from URL\n\n"
                        f"⏳ Continuing..."
                    )
                    await asyncio.sleep(0.5)
                else:
                    # Video download failed, try image download
                    print(f"🖼️ No video found, trying image download for {url}")
                    image_paths, image_info = await ImageDownloader.download(url, message)
                    
                    if image_paths and len(image_paths) > 0:
                        image_success_count += 1
                        downloaded_image_paths.extend(image_paths)
                        
                        for img_path in image_paths:
                            url_results.append(DownloadResult(
                                url=url,
                                status='success',
                                filename=os.path.basename(img_path),
                                size=os.path.getsize(img_path) / (1024 * 1024),
                                content_type='image'
                            ))
                        
                        print(f"✅ Downloaded {len(image_paths)} images from {idx}/{total}: {url}")
                        
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
                        print(f"❌ Failed to download from {idx}/{total}: {url}")
                        
            except Exception as e:
                error_msg = VideoDownloader._parse_error(str(e))
                failed_count += 1
                url_results.append(DownloadResult(
                    url=url,
                    status='failed',
                    error=error_msg,
                    content_type='unknown'
                ))
                print(f"❌ Error downloading {idx}/{total}: {error_msg}")
        
        total_time = time.time() - overall_start
        total_success = video_success_count + image_success_count
        
        # Store both videos and images for bulk upload
        user_downloads[f"{user_id}_bulk_downloaded_videos"] = downloaded_video_paths
        user_downloads[f"{user_id}_bulk_downloaded_images"] = downloaded_image_paths
        user_downloads[f"{user_id}_bulk_downloaded_all"] = downloaded_video_paths + downloaded_image_paths
        
        print(f"📊 Bulk download completed: {total_success} success ({video_success_count} videos, {image_success_count} images), {failed_count} failed")
        print(f"📁 Total downloaded videos: {len(downloaded_video_paths)}")
        print(f"📁 Total downloaded images: {len(downloaded_image_paths)}")
        
        try:
            await status_msg.delete()
        except Exception:
            pass
        
        # Send downloaded content to user
        if downloaded_video_paths or downloaded_image_paths:
            print(f"🔄 Sending {len(downloaded_video_paths)} videos and {len(downloaded_image_paths)} images to user...")
            await VideoDownloader._send_downloaded_content(downloaded_video_paths, downloaded_image_paths, message, user_id)
        
        # Send summary
        await VideoDownloader._send_summary(url_results, video_success_count, image_success_count, 
                                    failed_count, total, total_time, message, user_id, 
                                    downloaded_video_paths, downloaded_image_paths)
    
    @staticmethod
    async def _send_downloaded_content(video_paths: List[str], image_paths: List[str], 
                               message: Message, user_id: int) -> None:
        """Send downloaded videos and images to user"""
        # Send videos
        for idx, video_path in enumerate(video_paths):
            try:
                width, height = VideoProcessor.get_resolution(video_path)
                file_size = os.path.getsize(video_path) / (1024 * 1024)
                video_name = os.path.basename(video_path)
                
                # Use short key for videos too
                video_key = f"{user_id}_v_{idx}"
                user_downloads[video_key] = video_path
                
                await message.reply_video(
                    video=video_path,
                    width=width if width else 720,
                    height=height if height else 1280,
                    supports_streaming=True,
                    caption=f"🎬 {video_name}\n💾 Size: {file_size:.2f} MB",
                    reply_markup=Keyboards.single_video_upload(video_key)
                )
                print(f"✅ Sent video {idx+1}/{len(video_paths)}: {video_name}")
                
            except Exception as e:
                print(f"❌ Error sending video {video_path}: {e}")
        
        # Send images individually to avoid Pyrogram media group bug
        if image_paths:
            print(f"🔄 Sending {len(image_paths)} images to user individually...")
            for img_path in image_paths:
                try:
                    if os.path.exists(img_path):
                        await message.reply_photo(photo=img_path)
                        await asyncio.sleep(0.5) # Avoid flood wait
                except Exception as e:
                    print(f"❌ Error sending image {img_path}: {e}")
    
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

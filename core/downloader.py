"""
Video download functionality
"""

import os
import time
from typing import List, Tuple, Optional, Dict

import yt_dlp
from pyrogram.types import Message

from config.settings import COOKIE_FILE, FFMPEG_PATH
from config.paths import DOWNLOAD_FOLDER
from models.data_models import DownloadResult, VideoInfo
from core.file_manager import FileManager
from core.log_manager import LogManager
from utils.formatters import Formatter
from utils.video_processor import VideoProcessor
from models.enums import user_downloads
from ui.keyboards import Keyboards

class VideoDownloader:
    """Handle video downloads from X (Twitter)"""
    
    @staticmethod
    def download(url: str, message: Optional[Message] = None) -> Tuple[Optional[str], Optional[Dict]]:
        """Download single video from URL"""
        try:
            ydl_opts = {
                'cookiefile': COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
                'format': 'bestvideo+bestaudio/best',
                'merge_output_format': 'mp4',
                'ffmpeg_location': FFMPEG_PATH,
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
                'noplaylist': True,
                'quiet': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                if 'requested_downloads' in info:
                    downloaded_file = info['requested_downloads'][0]['filepath']
                else:
                    title = info.get('title', 'video')
                    downloaded_file = os.path.join(DOWNLOAD_FOLDER, f"{title}.mp4")

                if downloaded_file and os.path.exists(downloaded_file):
                    new_path = FileManager.rename_with_number(downloaded_file)
                    LogManager.add_entry(info, os.path.basename(new_path), url)
                    return new_path, info
                
                return None, None
        except Exception as e:
            if message:
                print(f"❌ Download failed for {url}: {e}")
            return None, None
    
    @staticmethod
    def download_multiple(urls: List[str], message: Message, user_id: int,
                        detection_msg: Optional[Message] = None) -> None:
        """Download multiple videos with progress tracking"""
        total = len(urls)
        success_count = 0
        failed_count = 0
        downloaded_paths = []
        url_results = []
        
        print(f"🔄 Starting bulk download for {total} URLs")
        
        if detection_msg:
            status_msg = detection_msg
            status_msg.edit_text(
                f"📥 **Starting Bulk Download**\n\n"
                f"Total URLs: {total}\n"
                f"Preparing downloads..."
            )
        else:
            status_msg = message.reply_text(
                f"📥 **Starting Bulk Download**\n\n"
                f"Total URLs: {total}\n"
                f"Preparing downloads..."
            )
        
        overall_start = time.time()
        
        # Download phase
        for idx, url in enumerate(urls, 1):
            try:
                status_msg.edit_text(
                    f"📥 **Bulk Download Progress**\n\n"
                    f"**Video {idx}/{total}**\n"
                    f"✅ Downloaded: {success_count}\n"
                    f"❌ Failed: {failed_count}\n\n"
                    f"🔗 Current URL:\n`{url[:50]}...`\n\n"
                    f"⏳ Downloading..."
                )
                
                video_path, info = VideoDownloader.download(url, message)
                
                if video_path and os.path.exists(video_path):
                    success_count += 1
                    downloaded_paths.append(video_path)
                    url_results.append(DownloadResult(
                        url=url,
                        status='success',
                        filename=os.path.basename(video_path),
                        size=os.path.getsize(video_path) / (1024 * 1024)
                    ))
                    
                    print(f"✅ Downloaded {idx}/{total}: {os.path.basename(video_path)}")
                    
                    status_msg.edit_text(
                        f"📥 **Bulk Download Progress**\n\n"
                        f"**Video {idx}/{total}**\n"
                        f"✅ Downloaded: {success_count}\n"
                        f"❌ Failed: {failed_count}\n\n"
                        f"✅ **Success:** `{os.path.basename(video_path)[:40]}...`\n\n"
                        f"⏳ Continuing..."
                    )
                    time.sleep(0.5)
                else:
                    failed_count += 1
                    url_results.append(DownloadResult(
                        url=url,
                        status='failed',
                        error='Download failed - No video found or invalid URL'
                    ))
                    print(f"❌ Failed to download {idx}/{total}: {url}")
                    
            except Exception as e:
                error_msg = VideoDownloader._parse_error(str(e))
                failed_count += 1
                url_results.append(DownloadResult(
                    url=url,
                    status='failed',
                    error=error_msg
                ))
                print(f"❌ Error downloading {idx}/{total}: {error_msg}")
        
        total_time = time.time() - overall_start
        user_downloads[f"{user_id}_bulk_downloaded"] = downloaded_paths
        
        print(f"📊 Bulk download completed: {success_count} success, {failed_count} failed")
        print(f"📁 Downloaded paths: {downloaded_paths}")
        
        try:
            status_msg.delete()
        except Exception:
            pass
        
        # Send videos to user
        print(f"🔄 Sending {len(downloaded_paths)} videos to user...")
        VideoDownloader._send_downloaded_videos(downloaded_paths, message, user_id)
        
        # Send summary
        VideoDownloader._send_summary(url_results, success_count, failed_count,
                                    total, total_time, message, user_id, downloaded_paths)
    
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
            return "Video is unavailable"
        else:
            return error_msg[:100] if len(error_msg) > 100 else error_msg
    
    @staticmethod
    def _send_downloaded_videos(downloaded_paths: List[str], message: Message, user_id: int) -> None:
        """Send downloaded videos to user"""
        if not downloaded_paths:
            return
        
        for idx, video_path in enumerate(downloaded_paths):
            try:
                width, height = VideoProcessor.get_resolution(video_path)
                file_size = os.path.getsize(video_path) / (1024 * 1024)
                video_name = os.path.basename(video_path)
                
                video_key = f"{user_id}_bulk_{idx}"
                user_downloads[video_key] = video_path
                
                # Use message.reply_video to send video back to user
                message.reply_video(
                    video=video_path,
                    width=width if width else 720,
                    height=height if height else 1280,
                    supports_streaming=True,
                    caption=f"✅ {video_name}\n💾 Size: {file_size:.2f} MB",
                    reply_markup=Keyboards.single_video_upload(video_key)
                )
                print(f"✅ Sent bulk video {idx+1}/{len(downloaded_paths)}: {video_name}")
                
            except Exception as e:
                print(f"❌ Error sending bulk video {video_path}: {e}")
    
    @staticmethod
    def _send_summary(url_results: List[DownloadResult], success_count: int, 
                     failed_count: int, total: int, total_time: float, 
                     message: Message, user_id: int, downloaded_paths: List[str]) -> None:
        """Send download summary with results"""
        from ui.keyboards import Keyboards
        
        MAX_MESSAGE_LENGTH = 4000
        
        success_results = [r for r in url_results if r.status == 'success']
        failed_results = [r for r in url_results if r.status == 'failed']
        
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
        summary_text += "🎬 **Bulk Download Complete!**\n\n"
        summary_text += (
            f"📊 **Summary:**\n"
            f"• Total URLs: {total}\n"
            f"• ✅ Downloaded: {success_count}\n"
            f"• ❌ Failed: {failed_count}\n"
            f"• ⏱️ Time: {Formatter.duration(total_time)}\n\n"
        )
        
        if success_count > 0:
            summary_text += f"📁 {success_count} video(s) saved and sent to you.\n\n"
            if failed_count > 0:
                summary_text += "💡 **Tip:** You can copy the failed URLs above and retry them.\n\n"
            summary_text += "What would you like to do next?"
            keyboard = Keyboards.bulk_download_complete(user_id, downloaded_paths)
        else:
            summary_text += "No videos were downloaded successfully.\n\n"
            summary_text += "💡 **Tip:** Check if the URLs contain videos and are publicly accessible."
            keyboard = Keyboards.back_to_main()
        
        message.reply_text(summary_text, reply_markup=keyboard, disable_web_page_preview=True)
"""
Video download functionality - SUPPORTS MULTIPLE VIDEOS PER URL
"""

import os
import time
import asyncio
import contextlib
from typing import List, Tuple, Optional, Dict

import yt_dlp
from pyrogram.types import Message

from config.settings import COOKIE_FILE, FFMPEG_PATH
from config.paths import DOWNLOAD_FOLDER
from models.data_models import DownloadResult, VideoInfo
from core.file_manager import FileManager
from core.log_manager import LogManager
from core.image_downloader import ImageDownloader
from core.formatting.formatters import Formatter
from core.media.video_processor import VideoProcessor
from models.enums import user_downloads
from resources.keyboards import Keyboards
from core.logger import setup_logger
from core.progress_tracker import download_tracker, ProgressTracker
from core.media.media_info import MediaInfo
from core.database import history_db
from core.videy_uploader import VideyUploader
from core.videy_links import add_videy_link
from core.parsing.url_parser import extract_twitter_username
from core.bad_news_service import BadNewsService
from core.papalah_service import PapalahService

logger = setup_logger("VideoDownloader")

class VideoDownloader:
    """Handle video downloads from X (Twitter) - SUPPORTS MULTIPLE VIDEOS PER URL"""

    @staticmethod
    def _format_bytes(num_bytes: int) -> str:
        if not num_bytes:
            return "0 B"
        value = float(num_bytes)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if value < 1024.0:
                return f"{value:.1f} {unit}"
            value /= 1024.0
        return f"{value:.1f} PB"

    @staticmethod
    def _format_speed(speed: float) -> str:
        if not speed:
            return "0 B/s"
        return f"{VideoDownloader._format_bytes(int(speed))}/s"

    @staticmethod
    def _progress_bar(percent: int, width: int = 15) -> str:
        percent = max(0, min(100, int(percent)))
        filled = int((percent / 100) * width)
        # Using a more premium looking bar
        return "▰" * filled + "▱" * (width - filled)

    @staticmethod
    def _pretty_phase(phase: str) -> str:
        phase_text = (phase or "").lower()
        if "selecting format" in phase_text:
            return f"🔎 Selecting best quality"
        if "downloading" in phase_text:
            return "📥 Downloading media file"
        if "finalizing" in phase_text:
            return "🛠️ Finalizing file"
        if "analyzing" in phase_text:
            return "🔍 Analyzing link"
        return f"⚙️ {phase}" if phase else "⚙️ Processing"

    @staticmethod
    async def _video_progress_poller(
        status_msg: Message,
        progress_state: Dict,
        index: int,
        total: int
    ) -> None:
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        spin_idx = 0
        last_text = ""

        while not progress_state.get("done", False):
            downloaded = int(progress_state.get("downloaded", 0) or 0)
            total_bytes = int(progress_state.get("total", 0) or 0)
            speed = float(progress_state.get("speed", 0) or 0.0)
            filename = progress_state.get("filename", "video")
            phase = progress_state.get("phase", "Preparing download")
            started_at = float(progress_state.get("started_at", time.time()))
            elapsed = max(0.1, time.time() - started_at)

            eta_text = "estimating..."
            if total_bytes > 0 and speed > 0:
                remaining = total_bytes - downloaded
                eta_seconds = remaining / speed
                if eta_seconds > 0:
                    eta_text = Formatter.duration(eta_seconds)
                else:
                    eta_text = "finishing..."

            if total_bytes > 0:
                pct = min(99, int((downloaded / total_bytes) * 100))
                size_line = (
                    f"{VideoDownloader._format_bytes(downloaded)} / "
                    f"{VideoDownloader._format_bytes(total_bytes)}"
                )
            else:
                pct = 0
                size_line = f"{VideoDownloader._format_bytes(downloaded)} / estimating..."

            text = (
                "🎬 **Downloading Your Media**\n\n"
                f"🔄 **Status:** {spinner[spin_idx % len(spinner)]} In Progress\n"
                f"📌 **Item:** `{index}/{total}`\n"
                f"🧩 **Stage:** {VideoDownloader._pretty_phase(phase)}\n"
                f"📄 **File:** `{os.path.basename(str(filename))[:50]}...`\n"
                f"📊 **Progress:** `{VideoDownloader._progress_bar(pct)}` **{pct}%**\n"
                f"💾 **Size:** {size_line}\n"
                f"⚡ **Speed:** `{VideoDownloader._format_speed(speed)}`\n"
                f"⏳ **ETA:** `{eta_text}`\n"
                f"⏱️ **Elapsed:** {Formatter.duration(elapsed)}"
            )
            spin_idx += 1

            if text != last_text:
                try:
                    await status_msg.edit_text(text, disable_web_page_preview=True)
                    last_text = text
                except Exception:
                    pass

            await asyncio.sleep(0.8)

        # Emit a final "downloaded" state for this URL before sender phase.
        final_text = (
            "✅ **Download Complete**\n\n"
            f"📌 **Item:** `{index}/{total}`\n"
            "📤 **Next:** Preparing files to send to you..."
        )
        try:
            await status_msg.edit_text(final_text, disable_web_page_preview=True)
        except Exception:
            pass

    @staticmethod
    async def download_with_progress(
        url: str,
        status_msg: Optional[Message] = None,
        index: int = 1,
        total: int = 1,
        user_id: int = 0,
        item_progress_callback: Optional[callable] = None
    ) -> Tuple[Optional[List[str]], Optional[Dict]]:
        """Unified download handler with a progress poller UI"""
        progress_state = {
            "downloaded": 0, "total": 0, "speed": 0.0,
            "filename": "video", "phase": "Analyzing...", "done": False, "started_at": time.time()
        }

        # Handle item progress callback for bulk
        def wrapped_callback(p):
            if item_progress_callback:
                item_progress_callback(p)

        # 1. Start the UI poller background task if status_msg is provided
        poller_task = None
        if status_msg:
            poller_task = asyncio.create_task(
                VideoDownloader._video_progress_poller(status_msg, progress_state, index, total)
            )

        # 2. Start the actual download
        try:
            paths, info = await VideoDownloader.download(
                url=url,
                index=index,
                total=total,
                progress_state=progress_state,
                user_id=user_id,
                item_progress_callback=wrapped_callback
            )
            return paths, info
        finally:
            progress_state["done"] = True
            if poller_task:
                with contextlib.suppress(Exception):
                    await poller_task
    
    @staticmethod
    async def download(url: str, message: Optional[Message] = None, status_msg: Optional[Message] = None,
                 index: int = 1, total: int = 1, progress_state: Optional[Dict] = None, user_id: int = 0,
                 item_progress_callback: Optional[callable] = None) -> Tuple[Optional[List[str]], Optional[Dict]]:
        """
        Download video(s) from URL - SUPPORTS MULTIPLE VIDEOS
        Returns: (list_of_video_paths, info_dict) or (None, None)
        """
        
        # 1. Custom Progress Callback for Services
        def service_progress_callback(d):
            if progress_state is not None:
                progress_state['downloaded'] = d.get('downloaded_bytes', 0)
                progress_state['total'] = d.get('total_bytes', 0)
                progress_state['speed'] = d.get('speed', 0.0)
                progress_state['filename'] = d.get('filename', 'video.mp4')
                progress_state['phase'] = 'Downloading media'
            if item_progress_callback:
                item_progress_callback(d)

        # 2. Check for RedGifs
        if "redgifs.com/watch/" in url.lower():
            if progress_state is not None: progress_state["phase"] = "Analyzing RedGifs..."
            from core.redgifs_media_service import RedGifsMediaService
            # RedGifs downloader doesn't support progress callback yet, but we'll add it if needed
            paths, ctype, info = await RedGifsMediaService.download_media(url, user_id)
            return paths, info

        # 3. Check for bad.news
        if "bad.news/t/" in url.lower():
            if progress_state is not None: progress_state["phase"] = "Analyzing BadNews mirror..."
            paths, ctype, info = await BadNewsService.download_media(url, user_id, service_progress_callback)
            return paths, info

        # 4. Check for Papalah
        if "papalah.com" in url.lower():
            if progress_state is not None: progress_state["phase"] = "Analyzing Papalah mirror..."
            paths, ctype, info = await PapalahService.download_media(url, user_id, service_progress_callback)
            return paths, info

        # 5. Check for Reddit
        from core.reddit_service import RedditService
        if RedditService.is_reddit_url(url):
            if progress_state is not None: progress_state["phase"] = "Analyzing Reddit..."
            paths, ctype, info = await RedditService.download_reddit_media(url, user_id)
            # Reddit service currently handles both video and image depending on the post type.
            return paths, info

        # 6. Check for 91porn
        from core.porn91_service import Porn91Service
        if Porn91Service.is_91porn_url(url):
            if progress_state is not None: progress_state["phase"] = "Analyzing 91porn (Cloudflare bypass)..."
            paths, ctype, info = await Porn91Service.download_media(url, user_id, service_progress_callback)
            return paths, info

        # 5. Default YT-DLP Quality profiles
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
                if progress_state is not None:
                    progress_state["phase"] = f"Selecting format ({profile['name']})"

                # Use a per-job token in filename template to avoid collisions across concurrent tasks.
                job_token = f"{index}_{int(time.time() * 1000)}_{os.getpid()}"

                # Progress hook for yt-dlp
                def progress_hook(d):
                    if (status_msg or progress_state) and d['status'] == 'downloading':
                        try:
                            downloaded = d.get('downloaded_bytes', 0)
                            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                            speed = d.get('speed', 0) or 0
                            filename = d.get('filename', 'video.mp4')
                            if '/' in filename:
                                filename = filename.split('/')[-1]
                            elif '\\' in filename:
                                filename = filename.split('\\')[-1]
                            
                            if progress_state is not None:
                                progress_state['downloaded'] = downloaded
                                progress_state['total'] = total_bytes
                                progress_state['speed'] = speed
                                progress_state['filename'] = filename
                                progress_state['phase'] = 'Downloading media'
                            if item_progress_callback:
                                item_progress_callback({
                                    'status': 'downloading',
                                    'downloaded_bytes': downloaded,
                                    'total_bytes': total_bytes,
                                    'speed': speed,
                                    'filename': filename
                                })
                        except Exception:
                            pass
                    elif progress_state is not None and d.get('status') == 'finished':
                        try:
                            progress_state['phase'] = 'Finalizing file'
                            progress_state['downloaded'] = d.get('downloaded_bytes', progress_state.get('downloaded', 0))
                            progress_state['total'] = d.get('total_bytes', progress_state.get('total', 0))
                        except Exception:
                            pass
                
                ydl_opts = {
                    'cookiefile': COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
                    'format': profile['format'],
                    'merge_output_format': profile['merge_output_format'],
                    'ffmpeg_location': FFMPEG_PATH,
                    'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'%(title).120B_{job_token}_%(autonumber)s.%(ext)s'),
                    'noplaylist': False,  # Changed to False to allow multiple videos
                    'quiet': True,
                    'no_warnings': True,
                    'no_color': True,
                    'extract_flat': False,
                    # Continue when one playlist entry is unsupported (e.g. external links in tweet cards).
                    'ignoreerrors': True,
                    # Disable resume/range continuation to prevent HTTP 416 on unstable servers.
                    'continuedl': False,
                    # Avoid .part rename race/lock issues on Windows.
                    'nopart': True,
                    # Make retries explicit at extractor/downloader layer.
                    'retries': 3,
                    'fragment_retries': 3,
                    'progress_hooks': [progress_hook] if (status_msg or progress_state is not None) else [],
                }
                
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(url, download=True)
                            if info is None:
                                # With ignoreerrors=True yt-dlp can return None for unsupported/non-video entries.
                                logger.info(f"No downloadable video info for URL: {url}")
                                continue
                            
                            downloaded_files = []
                            
                            # Check if this is a playlist/multiple videos
                            if isinstance(info, dict) and 'entries' in info:
                                # Multiple videos found
                                logger.info(f"Found {len(info['entries'])} videos in tweet")
                                for entry in info['entries']:
                                    if entry and isinstance(entry, dict) and 'requested_downloads' in entry:
                                        for download in (entry.get('requested_downloads') or []):
                                            if 'filepath' in download:
                                                downloaded_file = download['filepath']
                                                if os.path.exists(downloaded_file):
                                                    new_path = FileManager.rename_with_number(downloaded_file)
                                                    downloaded_files.append(new_path)
                                                    LogManager.add_entry(entry, os.path.basename(new_path), url)
                            else:
                                # Single video
                                if isinstance(info, dict) and (info.get('requested_downloads') or []):
                                    downloaded_file = (info.get('requested_downloads') or [])[0].get('filepath')
                                else:
                                    title = info.get('title', 'video') if isinstance(info, dict) else 'video'
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
                        if "No video could be found" in error_msg or "Unsupported URL" in error_msg:
                            raise e # Let outer catch handle this, don't retry
                        if attempt < max_retries - 1:
                            logger.warning(f"yt-dlp network error: {e}, retrying {attempt + 1}/{max_retries} in 2s...")
                            time.sleep(2)
                            continue
                        raise e
                    
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
        """Download multiple videos concurrently with progress tracking - NOW HANDLES BOTH VIDEOS AND IMAGES"""
        total = len(urls)
        
        logger.info(f"Starting async bulk download: {total} URLs (videos and images)")
        
        initial_text = (
            "📦 **Bulk Download Started**\n\n"
            f"🔢 **Total Links:** {total}\n"
            "⚙️ **Status:** Preparing your download queue\n"
            f"📊 **Progress:** `{VideoDownloader._progress_bar(0)}` **0%**"
        )
        
        if detection_msg:
            status_msg = detection_msg
            await status_msg.edit_text(initial_text)
        else:
            status_msg = await message.reply_text(initial_text)
        
        overall_start = time.time()
        
        # Central state for UI updates
        state = {
            "processed": 0,
            "video_success_count": 0,
            "image_success_count": 0,
            "failed_count": 0,
            "url_progress": {url: "Waiting" for url in urls},
            "done": False
        }
        
        downloaded_video_paths = []
        downloaded_image_paths = []
        video_source_map: Dict[str, str] = {}
        url_results = []

        # UI Updater Task
        async def ui_updater():
            last_text = ""
            while not state["done"]:
                processed_pct = int((state["processed"] / total) * 100) if total > 0 else 0
                
                # Show up to 3 active URL statuses
                active_statuses = []
                for url, phase in state["url_progress"].items():
                    if phase not in ["Waiting", "Done", "Failed"]:
                        short_url = url.replace('https://', '').replace('http://', '')[:25] + '...'
                        active_statuses.append(f"• {short_url}: {phase}")
                        if len(active_statuses) >= 3:
                            break
                
                active_text = "\n".join(active_statuses) if active_statuses else "Finalizing..."
                
                text = (
                    "📦 **Bulk Download In Progress (Concurrent)**\n\n"
                    f"🏃 **Active Downloads:**\n{active_text}\n\n"
                    f"📊 **Overall Progress:** `{VideoDownloader._progress_bar(processed_pct)}` **{processed_pct}%**\n\n"
                    "📈 **Live Summary**\n"
                    f"🎬 Videos completed: {state['video_success_count']}\n"
                    f"🖼️ Images completed: {state['image_success_count']}\n"
                    f"❌ Failed: {state['failed_count']}\n"
                    f"⏳ Remaining: {total - state['processed']}"
                )
                
                if text != last_text:
                    try:
                        await status_msg.edit_text(text)
                        last_text = text
                    except Exception:
                        pass
                
                await asyncio.sleep(1.0)  # Polling interval for bulk

        ui_task = asyncio.create_task(ui_updater())

        # Worker for a single URL
        # Worker for a single URL
        async def process_url(url: str, idx: int):
            try:
                # 1. Update overall status for this URL
                state["url_progress"][url] = "Preparing..."
                
                # 2. Extract videy link if applicable (optimization for X)
                from core.parsing.url_extractor import URLExtractor
                download_url = url
                if "x.com" in url or "twitter.com" in url:
                    videy_url = URLExtractor.get_videy_link_from_x_tweet(url)
                    if videy_url:
                        download_url = videy_url
                        logger.info(f"Bulk download: Found videy link in tweet: {videy_url}")

                # 3. Define a granular progress state for this specific URL
                # This could be used by UI updater to show current item details
                item_progress: Dict = {
                    "downloaded": 0, "total": 0, "speed": 0.0,
                    "filename": "video", "phase": "Starting", "done": False, "started_at": time.time()
                }

                # Helper to update both item and overall state
                def internal_callback(p):
                    item_progress["downloaded"] = p.get("downloaded_bytes", 0)
                    item_progress["total"] = p.get("total_bytes", 0)
                    item_progress["speed"] = p.get("speed", 0.0)
                    item_progress["phase"] = p.get("status", "downloading")
                    # Update overall state for the UI polling
                    pct = int((item_progress["downloaded"] / item_progress["total"] * 100)) if item_progress["total"] > 0 else 0
                    state["url_progress"][url] = f"Downloading ({pct}%)"

                # 4. Use unified download_with_progress (silent mode for bulk)
                state["url_progress"][url] = "Analyzing..."
                video_paths, video_info = await VideoDownloader.download_with_progress(
                    url=download_url,
                    status_msg=None, # Silent UI
                    index=idx,
                    total=total,
                    user_id=user_id,
                    item_progress_callback=internal_callback
                )
                
                if video_paths and len(video_paths) > 0:
                    actual_videos = []
                    actual_images = []
                    for vp in video_paths:
                        if vp.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                            actual_images.append(vp)
                        else:
                            actual_videos.append(vp)
                            
                    if actual_videos:
                        state["video_success_count"] += 1
                        downloaded_video_paths.extend(actual_videos)
                        for vp in actual_videos:
                            video_source_map[vp] = url
                            file_size = os.path.getsize(vp)
                            filename = os.path.basename(vp)
                            # Add to history
                            from core.parsing.url_parser import extract_twitter_username
                            source_username = extract_twitter_username(url) if "twitter" in url or "x.com" in url else "Bulk User"
                            history_db.add_entry(
                                user_id=user_id, url=url, source_username=source_username,
                                filename=filename, status='success', content_type='video', file_size=file_size
                            )
                            url_results.append(DownloadResult(url=url, status='success', filename=filename, size=file_size / (1024 * 1024), content_type='video'))
                            
                    if actual_images:
                        state["image_success_count"] += 1
                        downloaded_image_paths.extend(actual_images)
                        for ip in actual_images:
                            file_size = os.path.getsize(ip)
                            filename = os.path.basename(ip)
                            url_results.append(DownloadResult(url=url, status='success', filename=filename, size=file_size / (1024 * 1024), content_type='image'))
                            
                    state["url_progress"][url] = "Done"
                else:
                    # Check if it was images (Reddit/X only)
                    from core.reddit_service import RedditService
                    if RedditService.is_reddit_url(url) or "x.com" in url or "twitter.com" in url:
                        state["url_progress"][url] = "Checking images..."
                        image_paths, image_info = await ImageDownloader.download(
                            url, message=None, status_callback=None, index=idx, total=total
                        )
                        if image_paths:
                            state["image_success_count"] += 1
                            downloaded_image_paths.extend(image_paths)
                            state["url_progress"][url] = "Done"
                            return
                    
                    state["failed_count"] += 1
                    url_results.append(DownloadResult(url=url, status='failed', error='No media found', content_type='video'))
                    state["url_progress"][url] = "Failed"
            except Exception as e:
                logger.error(f"Error processing {url} in bulk: {e}")
                state["failed_count"] += 1
                state["url_progress"][url] = "Error"
                url_results.append(DownloadResult(url=url, status='failed', error=str(e), content_type='unknown'))
            finally:
                state["processed"] += 1

        # Execute all tasks concurrently
        tasks = [process_url(url, idx) for idx, url in enumerate(urls, 1)]
        await asyncio.gather(*tasks)
        
        # Stop UI updater
        state["done"] = True
        with contextlib.suppress(Exception):
            await ui_task
        
        total_time = time.time() - overall_start
        total_success = state["video_success_count"] + state["image_success_count"]
        
        # Store both videos and images for bulk upload
        user_downloads[f"{user_id}_bulk_downloaded_videos"] = downloaded_video_paths
        user_downloads[f"{user_id}_bulk_downloaded_images"] = downloaded_image_paths
        user_downloads[f"{user_id}_bulk_downloaded_all"] = downloaded_video_paths + downloaded_image_paths
        
        logger.info(f"Bulk download complete: {total_success} success ({state['video_success_count']} videos, {state['image_success_count']} images), {state['failed_count']} failed")
        logger.info(f"Downloaded {len(downloaded_video_paths)} video files, {len(downloaded_image_paths)} image files")
        
        try:
            await status_msg.delete()
        except Exception:
            pass
        
        # Send downloaded content to user
        if downloaded_video_paths or downloaded_image_paths:
            logger.info(f"Sending {len(downloaded_video_paths)} videos and {len(downloaded_image_paths)} images to user")
            await VideoDownloader._send_downloaded_content(
                downloaded_video_paths,
                downloaded_image_paths,
                message,
                user_id,
                video_source_map=video_source_map,
            )
        
        # Send summary
        await VideoDownloader._send_summary(url_results, state["video_success_count"], state["image_success_count"], 
                                    state["failed_count"], total, total_time, message, user_id, 
                                    downloaded_video_paths, downloaded_image_paths)
    
    @staticmethod
    async def _send_downloaded_content(
        video_paths: List[str],
        image_paths: List[str],
        message: Message,
        user_id: int,
        video_source_map: Optional[Dict[str, str]] = None,
    ) -> None:
        """Send downloaded videos and images to user"""
        bulk_videy_links: List[str] = []
        video_source_map = video_source_map or {}
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

                videy_cdn_url = await VideyUploader.upload_video(video_path)
                if videy_cdn_url:
                    add_videy_link(user_id, videy_cdn_url, video_source_map.get(video_path, ""))
                    bulk_videy_links.append(videy_cdn_url)
                    logger.info(f"Videy CDN link created in bulk flow for {video_name}: {videy_cdn_url}")

                # Send video with upload progress
                await message.reply_video(
                    video=video_path,
                    width=width if width else 720,
                    height=height if height else 1280,
                    supports_streaming=True,
                    caption=caption,
                    reply_markup=Keyboards.single_video_upload(video_key, user_id=user_id),
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

        if bulk_videy_links:
            unique_links = list(dict.fromkeys(bulk_videy_links))
            lines = [f"{i}. `{link}`" for i, link in enumerate(unique_links, 1)]
            header = "🔗 **Bulk Videy Links**\n\n"
            max_len = 3800
            current = header

            for line in lines:
                entry = line + "\n"
                if len(current) + len(entry) > max_len:
                    await message.reply_text(current, disable_web_page_preview=False)
                    current = header + entry
                else:
                    current += entry

            if current.strip():
                await message.reply_text(current, disable_web_page_preview=False)
        
        # Send images INDIVIDUALLY per user request (Parity with Reddit flow)
        if image_paths:
            logger.info(f"Sending {len(image_paths)} images individually")
            for i, img_path in enumerate(image_paths, 1):
                try:
                    if os.path.exists(img_path):
                        await message.reply_photo(
                            photo=img_path,
                            caption=f"🖼️ Bulk Image {i}/{len(image_paths)}"
                        )
                        await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Error sending bulk image: {e}")
    
    @staticmethod
    async def _send_summary(url_results: List[DownloadResult], video_success_count: int, 
                     image_success_count: int, failed_count: int, total: int, 
                     total_time: float, message: Message, user_id: int, 
                     video_paths: List[str], image_paths: List[str]) -> None:
        """Send download summary with results"""
        from resources.keyboards import Keyboards
        
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
            summary_text += "💡 **Tip:** Check if the link exists in the dashboard/media_cache folder and are publicly accessible."
            keyboard = Keyboards.back_to_main(user_id=user_id)
        
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




import asyncio
import logging
import requests
import re
import os
import time
from typing import List, Dict, Optional, Tuple
import uuid

from core.logger import setup_logger
from config.paths import get_platform_folder

logger = setup_logger("BadNewsService")

class BadNewsService:
    """Service to handle video extraction from bad.news links"""
    
    _headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    @staticmethod
    async def get_media_info(url: str) -> Dict:
        """Extract video metadata from a bad.news link"""
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(url, headers=BadNewsService._headers, timeout=15)
            )
            
            if response.status_code != 200:
                logger.error(f"BadNews API error ({response.status_code}) for {url}")
                return {"urls": [], "error": f"Page error {response.status_code}"}
                
            html = response.text
            
            # Extract OG metadata where possible
            og_title_matches = re.findall(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']|<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']', html)
            og_title = [t for tup in og_title_matches for t in tup if t]
            title = og_title[0] if og_title else "BadNews Video"
            
            # The bad.news pages often lack og:video and the main video is Twitter HLS (m3u8) while the footer is full of related MP4s. 
            # If we just grab any mp4, we grab the wrong video. We must target the main video ID.
            
            # 1. Try to find the poster image ID (which is the Twitter media ID)
            # Example: https://pbs.twimg.com/amplify_video_thumb/2027259064053563392/img/...
            twitter_id_matches = re.findall(r'pbs\.twimg\.com/(?:amplify_video_thumb|ext_tw_video_thumb|media(?:_thumb)?)/(\d+)', html)
            
            og_video = []
            
            if twitter_id_matches:
                vid_id = twitter_id_matches[0]
                # Construct the HLS URL for this specific video ID to ensure we don't grab a related video
                # Note: bad.news uses JS to construct this, but we can usually rely on the amplify/ext_tw pattern
                
                # Check if the page itself contains the exact m3u8 for this ID
                m3u8_matches = re.findall(rf'https://video\.twimg\.com/[^"\']*?/{vid_id}/[^"\']*?\.m3u8', html)
                if m3u8_matches:
                    og_video = [m3u8_matches[0]]
                else:
                    # If we found the ID but not the direct m3u8 string, we can look for any HLS links first
                    any_m3u8 = re.findall(r'https://video\.twimg\.com/[^\s"\'<>]+\.m3u8', html)
                    if any_m3u8:
                        og_video = [any_m3u8[0]]
            
            # 2. If no Twitter ID found, look for ANY m3u8 link (bad.news uses HLS for the main player)
            if not og_video:
                any_m3u8 = re.findall(r'https://video\.twimg\.com/[^\s"\'<>]+\.m3u8', html)
                if any_m3u8:
                    og_video = [any_m3u8[0]]

            # 3. Fallback: try standard video source tags
            if not og_video:
                source_src = re.findall(r'<video[^>]*>.*?<source[^>]+src=["\']([^"\']+)["\']', html, re.DOTALL | re.IGNORECASE)
                if source_src:
                    og_video = [source_src[0]]

            # 4. Fallback: video tag src attribute
            if not og_video:
                video_src = re.findall(r'<video[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE)
                if video_src:
                    og_video = [video_src[0]]
            
            # 5. Last resort fallback (WARNING: on bad.news this often grabs a related video from the footer)
            if not og_video:
                twimg_links = re.findall(r'https://video\.twimg\.com/[^\s"\']+\.mp4', html)
                if twimg_links:
                    og_video = [twimg_links[0]]
            
            if not og_video:
                return {"urls": [], "error": "No main video found on page"}
                
            return {
                "urls": [og_video[0]],
                "title": title,
                "author": "BadNews",
                "source": "BadNews"
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch BadNews media for {url}: {e}")
            return {"urls": [], "error": str(e)}

    @staticmethod
    async def download_media(url: str, user_id: int, progress_callback=None) -> Tuple[List[str], str, Dict]:
        """Download video from bad.news with progress reporting"""
        info = await BadNewsService.get_media_info(url)
        if not info.get("urls"):
            return [], "unknown", {"error": info.get("error", "Failed to extract video")}

        video_url = info["urls"][0]
        loop = asyncio.get_event_loop()
        
        try:
            filename = f"badnews_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}.mp4"
            file_path = os.path.join(get_platform_folder("BadNews", "video"), filename)
            
            # Check if this is an HLS (m3u8) stream
            if video_url.endswith('.m3u8'):
                logger.info(f"Downloading HLS stream via yt-dlp: {video_url}")
                import yt_dlp
                ydl_opts = {
                    'outtmpl': file_path,
                    'format': 'bestvideo+bestaudio/best',
                    'merge_output_format': 'mp4',
                    'quiet': True,
                    'no_warnings': True,
                }
                
                # Optional: wrap the yt-dlp hook to provide progress updates
                def ytdlp_hook(d):
                    if progress_callback and d['status'] == 'downloading':
                        try:
                            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                            downloaded = d.get('downloaded_bytes', 0)
                            speed = d.get('speed', 0)
                            progress_callback({
                                "status": "downloading",
                                "downloaded_bytes": downloaded,
                                "total_bytes": total,
                                "speed": speed,
                                "filename": filename
                            })
                        except Exception:
                            pass
                            
                ydl_opts['progress_hooks'] = [ytdlp_hook]
                
                def download_hls():
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([video_url])
                        
                await loop.run_in_executor(None, download_hls)
                
                # Verify that yt-dlp succeeded
                if not os.path.exists(file_path):
                    return [], "unknown", {"error": "yt-dlp failed to download the HLS stream"}
                    
            else:
                # Use chunked standard download for mp4 links
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.get(video_url, headers=BadNewsService._headers, stream=True, timeout=30)
                )
                
                if response.status_code == 200:
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    start_time = time.time()
                    
                    with open(file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if progress_callback and total_size > 0:
                                    elapsed = time.time() - start_time
                                    speed = downloaded / elapsed if elapsed > 0 else 0
                                    progress_callback({
                                        "status": "downloading",
                                        "downloaded_bytes": downloaded,
                                        "total_bytes": total_size,
                                        "speed": speed,
                                        "filename": filename
                                    })
                else:
                    return [], "unknown", {"error": f"Download failed ({response.status_code})"}

            metadata = {
                "author": info.get("author", "BadNews"),
                "subreddit": "BadNews",
                "title": info.get("title", "Video"),
                "is_video": True,
                "source_url": url
            }
            return [file_path], "video", metadata
            
        except Exception as e:
            logger.error(f"Failed to download BadNews video {url}: {e}")
            return [], "unknown", {"error": str(e)}

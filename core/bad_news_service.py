import asyncio
import logging
import requests
import re
import os
import time
from typing import List, Dict, Optional, Tuple
import uuid

from core.logger import setup_logger
from config.paths import DOWNLOAD_FOLDER

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
            
            # Extract OG metadata
            og_video = re.findall(r'<meta property="og:video" content="([^"]+)"', html)
            og_title = re.findall(r'<meta property="og:title" content="([^"]+)"', html)
            
            if not og_video:
                # Fallback: search for any twimg mp4 links
                twimg_links = re.findall(r'https://video\.twimg\.com/[^\s"\']+\.mp4', html)
                if twimg_links:
                    og_video = [twimg_links[0]]
            
            if not og_video:
                return {"urls": [], "error": "No video found on page"}
                
            video_url = og_video[0]
            title = og_title[0] if og_title else "BadNews Video"
            
            return {
                "urls": [video_url],
                "title": title,
                "author": "BadNews Mirror",
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
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            
            # Use chunked download for progress feedback
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
                                # Report to progress_state
                                progress_callback({
                                    "status": "downloading",
                                    "downloaded_bytes": downloaded,
                                    "total_bytes": total_size,
                                    "speed": speed,
                                    "filename": filename
                                })

                metadata = {
                    "author": info.get("author", "BadNews"),
                    "subreddit": "BadNews",
                    "title": info.get("title", "Video"),
                    "is_video": True,
                    "source_url": url
                }
                return [file_path], "video", metadata
            
            return [], "unknown", {"error": f"Download failed ({response.status_code})"}
        except Exception as e:
            logger.error(f"Failed to download BadNews video {url}: {e}")
            return [], "unknown", {"error": str(e)}

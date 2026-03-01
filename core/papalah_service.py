import asyncio
import logging
import requests
import re
import os
import time
from typing import List, Dict, Optional, Tuple

from core.logger import setup_logger
from config.paths import DOWNLOAD_FOLDER

logger = setup_logger("PapalahService")

from urllib.parse import unquote

class PapalahService:
    """Service to handle video extraction from papalah.com links"""
    
    _headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.papalah.com/'
    }

    @staticmethod
    async def get_media_info(url: str) -> Dict:
        """Extract video metadata and direct URL from a papalah.com link"""
        loop = asyncio.get_event_loop()
        try:
            # 1. Fetch the page
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(url, headers=PapalahService._headers, timeout=15)
            )
            
            if response.status_code != 200:
                logger.error(f"Papalah API error ({response.status_code}) for {url}")
                return {"urls": [], "error": f"Page error {response.status_code}"}
                
            html = response.text
            
            # 2. Extract Title from OG tags or HTML
            og_title = re.findall(r'<meta property="og:title" content="([^"]+)"', html)
            title = og_title[0] if og_title else "Papalah Video"
            
            # 3. De-obfuscate direct MP4 URL
            # The site uses dynamic variable names and a reordering loop
            segments_match = re.search(r'const _[a-z0-9]+ = (\["[^\]]+"\]);', html)
            mapping_match = re.search(r'const _[a-z0-9]+ = (\[[0-9, ]+\]);', html)
            replace_match = re.search(r"\.replace\('([^']+)', ''\)", html)

            video_url = None
            if segments_match and mapping_match:
                segments = eval(segments_match.group(1))
                mapping = eval(mapping_match.group(1))
                
                # Reconstruct string by indexing into segments based on mapping's values
                reconstructed = ""
                for i in range(len(mapping)):
                    try:
                        target_idx = mapping.index(i)
                        reconstructed += segments[target_idx]
                    except (ValueError, IndexError):
                        continue
                
                video_url = unquote(reconstructed)
                if replace_match:
                    suffix = replace_match.group(1)
                    video_url = video_url.replace(suffix, '')
                
                # Suffix fallback: strip .mp4_xxxx
                video_url = re.sub(r'\.mp4_[a-z0-9]+$', '.mp4', video_url)
            
            if not video_url:
                # Fallback to direct search if obfuscation logic changes
                mp4_urls = re.findall(r'(https?://[^\s"\']+media\.[^\s"\']+\.mp4)', html)
                if mp4_urls:
                    video_url = mp4_urls[0]
            
            if not video_url:
                return {"urls": [], "error": "No direct video link found on page"}
                
            return {
                "urls": [video_url],
                "title": title,
                "author": "Papalah User",
                "source": "Papalah"
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch Papalah media for {url}: {e}")
            return {"urls": [], "error": str(e)}

    @staticmethod
    async def download_media(url: str, user_id: int, progress_callback=None) -> Tuple[List[str], str, Dict]:
        """Download video from papalah with progress reporting"""
        info = await PapalahService.get_media_info(url)
        if not info.get("urls"):
            return [], "unknown", {"error": info.get("error", "Failed to extract video")}

        video_url = info["urls"][0]
        loop = asyncio.get_event_loop()
        
        try:
            filename = f"papalah_{user_id}_{int(time.time())}.mp4"
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            
            # Use chunked download for progress feedback
            # CRITICAL: Must use Referer header for Papalah downloads
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(video_url, headers=PapalahService._headers, stream=True, timeout=60)
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
                    "author": info.get("author", "Papalah"),
                    "subreddit": "Papalah",
                    "title": info.get("title", "Video"),
                    "is_video": True,
                    "source_url": url
                }
                return [file_path], "video", metadata
            
            return [], "unknown", {"error": f"Download failed ({response.status_code})"}
        except Exception as e:
            logger.error(f"Failed to download Papalah video {url}: {e}")
            return [], "unknown", {"error": str(e)}

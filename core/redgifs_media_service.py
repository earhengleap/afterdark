import asyncio
import logging
import requests
import re
import os
import time
from typing import List, Dict, Optional, Tuple

from core.logger import setup_logger
from config.paths import DOWNLOAD_FOLDER

logger = setup_logger("RedGifsMediaService")

class RedGifsMediaService:
    """Service to handle RedGifs user profiles and direct media downloads"""
    
    _headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    @staticmethod
    async def _get_token() -> Optional[str]:
        """Fetch a temporary OAuth token from RedGifs"""
        try:
            auth_url = "https://api.redgifs.com/v2/auth/temporary"
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(auth_url, headers=RedGifsMediaService._headers, timeout=10)
            )
            if response.status_code == 200:
                return response.json().get('token')
            return None
        except Exception as e:
            logger.error(f"Failed to get RedGifs token: {e}")
            return None

    @staticmethod
    async def get_user_stats(username: str) -> Dict:
        """Fetch total counts for gifs and images for a user"""
        token = await RedGifsMediaService._get_token()
        if not token:
            return {"gifs": 0, "images": 0, "error": "Auth failed"}

        headers = RedGifsMediaService._headers.copy()
        headers['Authorization'] = f"Bearer {token}"
        
        loop = asyncio.get_event_loop()
        stats = {"gifs": 0, "images": 0}
        
        try:
            # 1. Get GIF count
            url_gif = f"https://api.redgifs.com/v2/users/{username}/search?count=1&type=gif"
            resp_gif = await loop.run_in_executor(
                None,
                lambda: requests.get(url_gif, headers=headers, timeout=10)
            )
            if resp_gif.status_code == 200:
                stats["gifs"] = resp_gif.json().get('total', 0)
            elif resp_gif.status_code == 404:
                return {"gifs": 0, "images": 0, "error": "User not found"}
                
            # 2. Get Image count
            url_img = f"https://api.redgifs.com/v2/users/{username}/search?count=1&type=image"
            resp_img = await loop.run_in_executor(
                None,
                lambda: requests.get(url_img, headers=headers, timeout=10)
            )
            if resp_img.status_code == 200:
                stats["images"] = resp_img.json().get('total', 0)
            
            return stats
        except Exception as e:
            logger.error(f"Failed to fetch RedGifs stats for {username}: {e}")
            return {"gifs": 0, "images": 0, "error": str(e)}

    @staticmethod
    async def get_direct_url(url: str) -> Optional[str]:
        """Resolve a RedGifs watch URL to a direct MP4 link"""
        try:
            match = re.search(r'redgifs\.com/watch/([a-z0-9-]+)', url, re.IGNORECASE)
            if not match: return None
            
            gif_id = match.group(1)
            
            token = await RedGifsMediaService._get_token()
            if not token: return None
            
            loop = asyncio.get_event_loop()
            api_url = f"https://api.redgifs.com/v2/gifs/{gif_id}"
            headers = RedGifsMediaService._headers.copy()
            headers['Authorization'] = f"Bearer {token}"
            
            api_response = await loop.run_in_executor(
                None,
                lambda: requests.get(api_url, headers=headers, timeout=30)
            )
            
            if api_response.status_code == 200:
                data = api_response.json()
                gif_data = data.get('gif', {})
                urls = gif_data.get('urls', {})
                return urls.get('hd') or urls.get('sd')
            
            return None
        except Exception as e:
            logger.error(f"RedGifs direct URL extraction failed for {url}: {e}")
            return None

    @staticmethod
    async def fetch_user_media(username: str, limit: Optional[int] = None) -> Dict:
        """Fetch all GIF URLs from a user profile"""
        token = await RedGifsMediaService._get_token()
        if not token:
            return {"post_urls": [], "video_count": 0, "error": "Auth failed"}

        headers = RedGifsMediaService._headers.copy()
        headers['Authorization'] = f"Bearer {token}"
        
        all_gifs = []
        page = 1
        total_found = 0
        
        loop = asyncio.get_event_loop()
        
        try:
            while True:
                count = min(100, limit) if limit else 100
                api_url = f"https://api.redgifs.com/v2/users/{username}/search?count={count}&page={page}"
                
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.get(api_url, headers=headers, timeout=15)
                )
                
                if response.status_code == 404:
                    return {"post_urls": [], "video_count": 0, "error": "User not found"}
                if response.status_code != 200:
                    logger.error(f"RedGifs API error ({response.status_code}) for user {username}")
                    return {"post_urls": [], "video_count": 0, "error": f"API Error {response.status_code}"}
                    
                data = response.json()
                gifs = data.get('gifs', [])
                if not gifs:
                    break
                    
                for gif in gifs:
                    gif_id = gif.get('id')
                    if gif_id:
                        all_gifs.append(f"https://www.redgifs.com/watch/{gif_id.lower()}")
                
                total_found = data.get('total', len(all_gifs))
                if limit and len(all_gifs) >= limit:
                    all_gifs = all_gifs[:limit]
                    break
                    
                if len(all_gifs) >= total_found or page >= data.get('pages', 1):
                    break
                    
                page += 1
                await asyncio.sleep(0.5)

            return {
                "post_urls": all_gifs,
                "video_count": len(all_gifs),
                "image_count": 0,
                "username": username
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch RedGifs media for {username}: {e}")
            return {"post_urls": all_gifs, "video_count": len(all_gifs), "error": str(e)}

    @staticmethod
    async def download_media(url: str, user_id: int) -> Tuple[List[str], str, Dict]:
        """Download a single RedGifs video"""
        direct_url = await RedGifsMediaService.get_direct_url(url)
        if not direct_url:
            return [], "unknown", {"error": "Failed to resolve direct URL"}

        loop = asyncio.get_event_loop()
        try:
            filename = f"redgifs_{user_id}_{int(time.time())}.mp4"
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(direct_url, headers=RedGifsMediaService._headers, timeout=20)
            )
            
            if response.status_code == 200:
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                info = {
                    "author": "RedGifs User",
                    "subreddit": "RedGifs",
                    "title": os.path.basename(url),
                    "is_video": True
                }
                return [file_path], "video", info
            
            return [], "unknown", {"error": f"Download failed ({response.status_code})"}
        except Exception as e:
            logger.error(f"Failed to download RedGifs {url}: {e}")
            return [], "unknown", {"error": str(e)}

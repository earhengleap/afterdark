import os
import re
import time
import json
import asyncio
import logging
import requests
from typing import List, Tuple, Optional, Dict
from urllib.parse import urlparse

from config.paths import IMAGES_FOLDER, DOWNLOAD_FOLDER
from core.logger import setup_logger
from core.file_manager import FileManager

logger = setup_logger("RedditService")

class RedditService:
    """Service to handle high-resolution media downloads from Reddit using JSON API"""
    
    _headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    @staticmethod
    def is_reddit_url(url: str) -> bool:
        """Check if the URL is a Reddit URL"""
        return bool(re.search(r'(?:reddit\.com|redd\.it)', url, re.IGNORECASE))

    @staticmethod
    async def get_media_info(url: str) -> Dict:
        """Extract direct media URLs and metadata from a Reddit post using JSON API"""
        try:
            # 1. Follow redirects for short links (/s/ or redd.it)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: requests.get(url, headers=RedditService._headers, allow_redirects=True, timeout=10)
            )
            
            real_url = response.url
            if '.json' not in real_url:
                json_url = real_url.split('?')[0].rstrip('/') + '.json'
            else:
                json_url = real_url
            
            # 2. Fetch JSON data
            json_response = await loop.run_in_executor(
                None,
                lambda: requests.get(json_url, headers=RedditService._headers, timeout=10)
            )
            
            if json_response.status_code != 200:
                logger.error(f"Failed to fetch Reddit JSON ({json_response.status_code}): {json_url}")
                return {"urls": [], "author": "Unknown", "subreddit": "Unknown", "title": ""}

            data = json_response.json()
            if not isinstance(data, list) or not data[0]['data']['children']:
                return {"urls": [], "author": "Unknown", "subreddit": "Unknown", "title": ""}
                
            post_data = data[0]['data']['children'][0]['data']
            media_urls = []

            # A. Image Gallery
            if post_data.get('is_gallery'):
                metadata = post_data.get('media_metadata', {})
                gallery_items = post_data.get('gallery_data', {}).get('items', [])
                for item in gallery_items:
                    media_id = item['media_id']
                    if media_id in metadata:
                        s = metadata[media_id]['s']
                        link = s.get('u') or s.get('gif')
                        if link:
                            media_urls.append(link.replace('&amp;', '&'))

            # B. Native Reddit Video
            elif post_data.get('is_video'):
                video_url = post_data.get('media', {}).get('reddit_video', {}).get('fallback_url')
                if video_url:
                    media_urls.append(video_url.split('?')[0])

            # C. Single Image / Gif
            else:
                raw_url = post_data.get('url', '')
                if any(raw_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.gifv']):
                    if raw_url.endswith('.gifv'):
                        media_urls.append(raw_url.replace('.gifv', '.mp4'))
                    else:
                        media_urls.append(raw_url)
                elif post_data.get('post_hint') == 'image' or post_data.get('post_hint') == 'rich:video':
                    media_urls.append(raw_url)
                
                # Check previews as fallback for some videos/gifs handled via external providers
                if not media_urls and 'preview' in post_data:
                    images = post_data['preview'].get('images', [])
                    if images:
                        # Check for variants like mp4
                        variants = images[0].get('variants', {})
                        if 'mp4' in variants:
                            media_urls.append(variants['mp4']['source']['url'].replace('&amp;', '&'))
                        elif 'gif' in variants:
                            media_urls.append(variants['gif']['source']['url'].replace('&amp;', '&'))
                        else:
                            media_urls.append(images[0]['source']['url'].replace('&amp;', '&'))

            return {
                "urls": media_urls,
                "author": post_data.get('author', 'Unknown'),
                "subreddit": post_data.get('subreddit', 'Unknown'),
                "title": post_data.get('title', ''),
                "upvotes": post_data.get('ups', 0),
                "is_video": post_data.get('is_video', False) or any('redgifs.com' in u or 'gfycat.com' in u or u.endswith('.mp4') for u in media_urls)
            }

        except Exception as e:
            logger.error(f"Error extracting Reddit media info: {e}")
            return {"urls": [], "author": "Unknown", "subreddit": "Unknown", "title": "", "is_video": False}

    @staticmethod
    async def _get_redgifs_url(url: str) -> Optional[str]:
        """Attempt to get direct mp4 link from a RedGifs URL using their temporary OAuth API"""
        try:
            # Extract ID: https://www.redgifs.com/watch/[ID]
            match = re.search(r'redgifs\.com/watch/([a-z0-9-]+)', url, re.IGNORECASE)
            if not match: return None
            
            gif_id = match.group(1)
            
            loop = asyncio.get_event_loop()
            
            # 1. Get temporary token
            auth_url = "https://api.redgifs.com/v2/auth/temporary"
            auth_response = await loop.run_in_executor(
                None,
                lambda: requests.get(auth_url, headers=RedditService._headers, timeout=10)
            )
            
            if auth_response.status_code != 200:
                logger.warning(f"Failed to get RedGifs temporary token: {auth_response.status_code}")
                return None
                
            token = auth_response.json().get('token')
            if not token: return None
            
            # 2. Use token to get media info
            api_url = f"https://api.redgifs.com/v2/gifs/{gif_id}"
            headers = RedditService._headers.copy()
            headers['Authorization'] = f"Bearer {token}"
            
            api_response = await loop.run_in_executor(
                None,
                lambda: requests.get(api_url, headers=headers, timeout=10)
            )
            
            if api_response.status_code == 200:
                data = api_response.json()
                gif_data = data.get('gif', {})
                urls = gif_data.get('urls', {})
                # Prefer HD, fallback to SD
                return urls.get('hd') or urls.get('sd')
            
            return None
        except Exception as e:
            logger.error(f"RedGifs extraction failed for {url}: {e}")
            return None

    @staticmethod
    async def download_reddit_media(url: str, user_id: int) -> Tuple[List[str], str, Dict]:
        """Download Reddit media and return list of paths, content type, and metadata"""
        info = await RedditService.get_media_info(url)
        media_urls = info.get("urls", [])
        
        if not media_urls:
            return [], "unknown", info

        downloaded_paths = []
        is_video = info.get("is_video", False)
        content_type = "video" if is_video else "image"
        target_folder = DOWNLOAD_FOLDER if is_video else IMAGES_FOLDER

        loop = asyncio.get_event_loop()
        for idx, m_url in enumerate(media_urls):
            try:
                # Specialized handling for RedGifs in the download loop
                active_url = m_url
                if 'redgifs.com/watch/' in m_url:
                    direct_url = await RedditService._get_redgifs_url(m_url)
                    if direct_url:
                        active_url = direct_url
                        logger.info(f"Resolved RedGifs to: {active_url}")
                
                ext = '.jpg'
                if '.png' in active_url.lower(): ext = '.png'
                elif '.gif' in active_url.lower(): ext = '.gif'
                elif '.mp4' in active_url.lower() or 'video' in active_url.lower() or 'redgifs' in m_url.lower(): ext = '.mp4'
                
                filename = f"reddit_{user_id}_{int(time.time())}_{idx}{ext}"
                file_path = os.path.join(target_folder, filename)
                
                response = await loop.run_in_executor(
                    None,
                    lambda: requests.get(active_url, headers=RedditService._headers, timeout=20)
                )
                
                if response.status_code == 200:
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    
                    # Rename for uniqueness if needed
                    from core.image_downloader import ImageDownloader
                    final_path = ImageDownloader._safe_rename_with_number(file_path) if not is_video else file_path
                    downloaded_paths.append(final_path)
            except Exception as e:
                logger.error(f"Failed to download Reddit item {m_url}: {e}")

        return downloaded_paths, content_type, info

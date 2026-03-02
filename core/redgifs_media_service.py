import asyncio
import logging
import re
import os
import time
import uuid
import random
import requests
from typing import List, Dict, Optional, Tuple
import yt_dlp

from core.logger import setup_logger
from config.paths import DOWNLOAD_FOLDER

logger = setup_logger("RedGifsMediaService")

class RedGifsMediaService:
    """Service to handle RedGifs user profiles and direct media downloads"""
    
    _headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Origin': 'https://www.redgifs.com',
        'Referer': 'https://www.redgifs.com/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'Connection': 'keep-alive'
    }
    
    _token: Optional[str] = None
    _token_expires: float = 0
    _token_lock = asyncio.Lock()
    _download_semaphore = asyncio.Semaphore(1) # Sequential downloads to avoid CDN resets
    _session = None
    _retry_statuses = {429, 500, 502, 503, 504, 520, 521, 522, 524}

    @classmethod
    def _get_session(cls):
        """Lazy initializer for a shared requests session"""
        if cls._session is None:
            cls._session = requests.Session()
            cls._session.trust_env = False
            cls._session.headers.update(cls._headers)
        return cls._session

    @staticmethod
    async def _safe_request(
        url: str,
        headers: Optional[Dict] = None,
        method: str = "GET",
        timeout: int = 20,
        retries: int = 5,
        use_session: bool = True,
    ) -> Optional[requests.Response]:
        """Perform a request with retries and jittered backoff."""
        loop = asyncio.get_event_loop()
        session = RedGifsMediaService._get_session() if use_session else None

        req_headers = headers if headers is not None else RedGifsMediaService._headers

        for attempt in range(retries):
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: (
                        session.request(method, url, headers=req_headers, timeout=timeout)
                        if session is not None
                        else RedGifsMediaService._request_without_env(method, url, req_headers, timeout)
                    ),
                )

                if response.status_code == 200:
                    return response

                if response.status_code in RedGifsMediaService._retry_statuses and attempt < retries - 1:
                    wait_time = (2 ** (attempt + 1)) + random.uniform(0.5, 2.0)
                    logger.warning(
                        f"HTTP {response.status_code} for {url} (attempt {attempt+1}/{retries}). "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue

                return response

            except (
                requests.exceptions.ConnectionError,
                ConnectionResetError,
                requests.exceptions.Timeout,
                requests.exceptions.SSLError,
            ) as e:
                if attempt == retries - 1:
                    logger.error(f"Request failed after {retries} attempts for {url}: {e}")
                    return None
                
                wait_time = (2 ** (attempt + 1)) + random.uniform(0.5, 2.0)
                logger.warning(f"Connection issue for {url} (attempt {attempt+1}/{retries}). Retrying in {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"Unexpected error for {url}: {e}")
                return None
        return None

    @staticmethod
    def _request_without_env(method: str, url: str, headers: Dict, timeout: int) -> requests.Response:
        """Issue a request without inheriting system proxy settings."""
        with requests.Session() as temp_session:
            temp_session.trust_env = False
            return temp_session.request(method, url, headers=headers, timeout=timeout)

    @staticmethod
    def _extract_gif_id(url: str) -> Optional[str]:
        """Extract RedGifs clip id from known URL shapes."""
        patterns = [
            r"redgifs\.com/watch/([a-z0-9-]+)",
            r"redgifs\.com/ifr/([a-z0-9-]+)",
            r"redgifs\.com/([a-z0-9-]+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    @staticmethod
    async def _get_direct_url_from_watch_page(url: str) -> Optional[str]:
        """Fallback: scrape direct MP4 URL from watch page HTML when API is blocked."""
        html_headers = {
            "User-Agent": RedGifsMediaService._headers["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.redgifs.com/",
            "Connection": "close",
        }
        resp = await RedGifsMediaService._safe_request(
            url,
            headers=html_headers,
            timeout=25,
            retries=3,
            use_session=False,
        )
        if not resp or resp.status_code != 200:
            return None

        html = resp.text or ""
        patterns = [
            r"https://media\.redgifs\.com/[A-Za-z0-9_-]+\.mp4",
            r"https://v3\.redgifs\.com/[A-Za-z0-9_-]+\.mp4",
            r"https:\\/\\/media\.redgifs\.com\\/[A-Za-z0-9_-]+\.mp4",
            r"https:\\/\\/v3\.redgifs\.com\\/[A-Za-z0-9_-]+\.mp4",
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(0).replace("\\/", "/")
        return None

    @staticmethod
    def _build_direct_url_candidates(gif_id: str) -> List[str]:
        """Build likely direct media URL variants from gif id."""
        base_hosts = ["media.redgifs.com", "v3.redgifs.com"]
        slug = gif_id.strip()
        slug_no_dash = slug.replace("-", "")
        hyphen_title = "".join(part.capitalize() for part in slug.split("-") if part)
        candidates = [slug, slug_no_dash, slug.capitalize(), slug_no_dash.capitalize(), hyphen_title]

        seen = set()
        urls: List[str] = []
        for host in base_hosts:
            for name in candidates:
                if not name:
                    continue
                for scheme in ("https", "http"):
                    u = f"{scheme}://{host}/{name}.mp4"
                    if u not in seen:
                        seen.add(u)
                        urls.append(u)
        return urls

    @staticmethod
    async def _download_direct_file(direct_url: str, file_path: str) -> bool:
        """Try downloading direct media URL with host fallback and strict headers."""
        host_variants = [direct_url]
        if "media.redgifs.com" in direct_url:
            host_variants.append(direct_url.replace("media.redgifs.com", "v3.redgifs.com"))
        elif "v3.redgifs.com" in direct_url:
            host_variants.append(direct_url.replace("v3.redgifs.com", "media.redgifs.com"))

        media_headers = {
            "User-Agent": RedGifsMediaService._headers["User-Agent"],
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Referer": "https://www.redgifs.com/",
            "Connection": "close",
        }

        for candidate_url in host_variants:
            response = await RedGifsMediaService._safe_request(
                candidate_url,
                media_headers,
                timeout=45,
                retries=4,
                use_session=False,
            )
            if not response or response.status_code not in (200, 206):
                status = response.status_code if response else "Unknown"
                logger.warning(f"RedGifs media candidate failed ({status}): {candidate_url}")
                continue

            try:
                with open(file_path, "wb") as f:
                    f.write(response.content)
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    return True
            except Exception as e:
                logger.warning(f"Failed to write RedGifs media file from {candidate_url}: {e}")
        return False

    @staticmethod
    async def _get_token() -> Optional[str]:
        """Fetch a temporary OAuth token from RedGifs (cached)"""
        async with RedGifsMediaService._token_lock:
            if RedGifsMediaService._token and time.time() < RedGifsMediaService._token_expires:
                return RedGifsMediaService._token
                
            auth_url = "https://api.redgifs.com/v2/auth/temporary"
            response = await RedGifsMediaService._safe_request(auth_url)
            
            if response and response.status_code == 200:
                data = response.json()
                RedGifsMediaService._token = data.get('token')
                RedGifsMediaService._token_expires = time.time() + 3000 
                return RedGifsMediaService._token
            return None

    @staticmethod
    async def get_user_stats(username: str) -> Dict:
        """Fetch total counts for gifs and images for a user"""
        token = await RedGifsMediaService._get_token()
        if not token:
            return {"gifs": 0, "images": 0, "error": "Auth failed"}

        headers = RedGifsMediaService._headers.copy()
        headers['Authorization'] = f"Bearer {token}"
        
        stats = {"gifs": 0, "images": 0}
        
        try:
            url_gif = f"https://api.redgifs.com/v2/users/{username}/search?count=1&type=g"
            resp_gif = await RedGifsMediaService._safe_request(url_gif, headers)
            
            if resp_gif and resp_gif.status_code == 200:
                stats["gifs"] = resp_gif.json().get('total', 0)
            elif resp_gif and resp_gif.status_code == 404:
                return {"gifs": 0, "images": 0, "error": "User not found"}
                
            url_img = f"https://api.redgifs.com/v2/users/{username}/search?count=1&type=i"
            resp_img = await RedGifsMediaService._safe_request(url_img, headers)
            
            if resp_img and resp_img.status_code == 200:
                stats["images"] = resp_img.json().get('total', 0)
            
            return stats
        except Exception as e:
            logger.error(f"Failed to fetch RedGifs stats for {username}: {e}")
            return {"gifs": 0, "images": 0, "error": str(e)}

    @staticmethod
    async def get_direct_url(url: str) -> Optional[str]:
        """Resolve a RedGifs watch URL to a direct MP4 link"""
        try:
            gif_id = RedGifsMediaService._extract_gif_id(url)
            if not gif_id:
                return None
            
            token = await RedGifsMediaService._get_token()
            if token:
                api_url = f"https://api.redgifs.com/v2/gifs/{gif_id}"
                headers = RedGifsMediaService._headers.copy()
                headers["Authorization"] = f"Bearer {token}"

                api_response = await RedGifsMediaService._safe_request(api_url, headers, timeout=30)
                if api_response and api_response.status_code == 200:
                    data = api_response.json()
                    gif_data = data.get("gif", {})
                    urls = gif_data.get("urls", {})
                    direct_url = urls.get("hd") or urls.get("sd")
                    if direct_url:
                        return direct_url

            # API blocked/failed fallback.
            watch_url = f"https://www.redgifs.com/watch/{gif_id}"
            watch_url_direct = await RedGifsMediaService._get_direct_url_from_watch_page(watch_url)
            if watch_url_direct:
                return watch_url_direct

            # Last-resort guess when API + page extraction are blocked.
            guesses = RedGifsMediaService._build_direct_url_candidates(gif_id)
            return guesses[0] if guesses else None
        except Exception as e:
            logger.error(f"RedGifs direct URL extraction failed for {url}: {e}")
            return None

    @staticmethod
    async def fetch_user_media(username: str, limit: Optional[int] = None, order: str = "recent") -> Dict:
        """Fetch all GIF URLs from a user profile"""
        token = await RedGifsMediaService._get_token()
        if not token:
            return {"post_urls": [], "video_count": 0, "error": "Auth failed"}

        headers = RedGifsMediaService._headers.copy()
        headers['Authorization'] = f"Bearer {token}"
        
        all_gifs = []
        page = 1
        
        try:
            while True:
                count = 100 
                if limit and limit < 100:
                    count = limit
                
                api_url = f"https://api.redgifs.com/v2/users/{username}/search?count={count}&page={page}&order={order}&type=g"
                response = await RedGifsMediaService._safe_request(api_url, headers)
                
                if response and response.status_code == 404:
                    return {"post_urls": [], "video_count": 0, "error": "User not found"}
                if not response or response.status_code != 200:
                    status = response.status_code if response else "Unknown"
                    return {"post_urls": [], "video_count": 0, "error": f"API Error {status}"}
                    
                data = response.json()
                gifs = data.get('gifs', [])
                if not gifs: break
                    
                for gif in gifs:
                    gif_id = gif.get('id')
                    if gif_id:
                        all_gifs.append(f"https://www.redgifs.com/watch/{gif_id.lower()}")
                
                total_found = data.get('total', len(all_gifs))
                if limit and len(all_gifs) >= limit: break
                if len(all_gifs) >= total_found or page >= data.get('pages', 1): break
                    
                page += 1
                await asyncio.sleep(1.0)

            return {"post_urls": all_gifs, "video_count": len(all_gifs), "image_count": 0, "username": username}
        except Exception as e:
            logger.error(f"Failed to fetch RedGifs media for {username}: {e}")
            return {"post_urls": all_gifs, "video_count": len(all_gifs), "error": str(e)}

    @staticmethod
    async def download_media(url: str, user_id: int) -> Tuple[List[str], str, Dict]:
        """Download a single RedGifs video sequentially"""
        async with RedGifsMediaService._download_semaphore:
            direct_url = await RedGifsMediaService.get_direct_url(url)
            if not direct_url:
                gif_id = RedGifsMediaService._extract_gif_id(url)
                if gif_id:
                    filename = f"redgifs_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}.mp4"
                    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
                    if await RedGifsMediaService._download_direct_file(
                        RedGifsMediaService._build_direct_url_candidates(gif_id)[0],
                        file_path,
                    ):
                        info = {"author": "RedGifs User", "subreddit": "RedGifs", "title": os.path.basename(url), "is_video": True}
                        return [file_path], "video", info
                return await RedGifsMediaService._download_with_ytdlp(url, user_id)

            try:
                filename = f"redgifs_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}.mp4"
                file_path = os.path.join(DOWNLOAD_FOLDER, filename)

                if await RedGifsMediaService._download_direct_file(direct_url, file_path):
                    info = {"author": "RedGifs User", "subreddit": "RedGifs", "title": os.path.basename(url), "is_video": True}
                    return [file_path], "video", info

                gif_id = RedGifsMediaService._extract_gif_id(url)
                if gif_id:
                    for candidate in RedGifsMediaService._build_direct_url_candidates(gif_id):
                        if await RedGifsMediaService._download_direct_file(candidate, file_path):
                            info = {"author": "RedGifs User", "subreddit": "RedGifs", "title": os.path.basename(url), "is_video": True}
                            return [file_path], "video", info

                logger.warning(f"Direct RedGifs CDN download failed for {url}, trying yt-dlp fallback")
                return await RedGifsMediaService._download_with_ytdlp(url, user_id)
            except Exception as e:
                logger.error(f"Failed to download RedGifs {url} via direct CDN: {e}")
                return await RedGifsMediaService._download_with_ytdlp(url, user_id)

    @staticmethod
    async def _download_with_ytdlp(url: str, user_id: int) -> Tuple[List[str], str, Dict]:
        """Fallback downloader when direct CDN access fails."""
        loop = asyncio.get_event_loop()

        def _run_ytdlp() -> Tuple[List[str], str, Dict]:
            outtmpl = os.path.join(
                DOWNLOAD_FOLDER,
                f"redgifs_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}.%(ext)s",
            )
            ydl_opts = {
                "format": "best[ext=mp4]/best",
                "outtmpl": outtmpl,
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "retries": 3,
                "fragment_retries": 3,
                "continuedl": False,
                "nopart": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    return [], "unknown", {"error": "yt-dlp returned no media info"}

                file_path = None
                requested = info.get("requested_downloads") if isinstance(info, dict) else None
                if requested and isinstance(requested, list):
                    file_path = requested[0].get("filepath")
                if not file_path and isinstance(info, dict):
                    file_path = ydl.prepare_filename(info)

                if not file_path or not os.path.exists(file_path):
                    return [], "unknown", {"error": "yt-dlp download produced no file"}

                media_info = {
                    "author": "RedGifs User",
                    "subreddit": "RedGifs",
                    "title": os.path.basename(url),
                    "is_video": True,
                }
                return [file_path], "video", media_info

        try:
            return await loop.run_in_executor(None, _run_ytdlp)
        except Exception as e:
            logger.error(f"yt-dlp fallback failed for RedGifs {url}: {e}")
            return [], "unknown", {"error": f"Both direct and yt-dlp downloads failed: {e}"}

import asyncio
import logging
import re
import os
import time
import subprocess
from typing import List, Dict, Optional, Tuple

from core.logger import setup_logger
from config.paths import get_platform_folder

logger = setup_logger("Porna91Service")

class Porna91Service:
    """Service to handle video extraction from 91porna.com using Playwright."""

    _user_agent = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )

    _CHROMIUM_ARGS = [
        '--disable-blink-features=AutomationControlled',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-setuid-sandbox',
        '--ignore-certificate-errors',
        '--disable-web-security',
    ]

    @staticmethod
    def is_91porna_url(url: str) -> bool:
        """Check if URL belongs to 91porna"""
        return bool(re.search(r'(91porna\.com)', url, re.IGNORECASE))

    @staticmethod
    async def _extract_m3u8_url(url: str) -> Tuple[Optional[str], Optional[Dict[str, str]]]:
        """Load the page in headless Chromium to bypass Cloudflare and intercept the M3U8 API"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("playwright not installed.")
            return None, None

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=True,
                        args=Porna91Service._CHROMIUM_ARGS,
                    )
                    context = await browser.new_context(
                        user_agent=Porna91Service._user_agent,
                        extra_http_headers={
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        },
                    )
                    page = await context.new_page()

                    await page.add_init_script(
                        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                    )

                    m3u8_url: Optional[str] = None

                    async def handle_request(request):
                        nonlocal m3u8_url
                        # We are looking for the master playlist or a 720p stream
                        if "m3u8" in request.url and m3u8_url is None:
                            logger.info(f"Intercepted HLS Playlist: {request.url}")
                            # Prefer a specific resolution stream if multiple fire
                            if "720p" in str(request.url) or "1080p" in str(request.url) or "480p" in str(request.url):
                                m3u8_url = request.url
                            else:
                                m3u8_url = request.url

                    page.on("request", handle_request)

                    try:
                        logger.info(f"Navigating to 91porna (Attempt {attempt}): {url}")
                        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)

                        # Wait for the page/Cloudflare to settle and the player to initialize and fetch the playlist
                        await page.wait_for_timeout(8000)

                        # Extract Cloudflare passing cookies
                        cookies = await context.cookies()
                        cookie_dict = {c['name']: c['value'] for c in cookies}

                        if m3u8_url:
                            logger.info(f"Extracted 91porna video src: {m3u8_url}")
                            return m3u8_url, cookie_dict
                        else:
                            logger.warning("No m3u8 network request was intercepted.")

                    except Exception as e:
                        logger.warning(f"Page load issue (attempt {attempt}/{max_retries}): {e}")
                    finally:
                        await browser.close()

            except Exception as e:
                logger.warning(f"Playwright attempt {attempt} failed: {e}")

            if attempt < max_retries:
                await asyncio.sleep(attempt * 5)

        return None, None
        
    @staticmethod
    async def get_media_info(url: str) -> Dict:
        """Extract the direct video URL and metadata from a 91porna link."""
        m3u8_url, cookies = await Porna91Service._extract_m3u8_url(url)

        if not m3u8_url:
            logger.error(f"Could not extract video URL for {url}")
            return {"urls": [], "error": "No video source found or blocked by Cloudflare."}

        title = "91porna_video"
        m = re.search(r'video_key=([a-zA-Z0-9]+)', url)
        if m:
            title = f"91porna_{m.group(1)}"

        return {
            "urls": [m3u8_url],
            "title": title,
            "author": "91Porna",
            "source": "91Porna",
            "cookies": cookies,
            "referer": url
        }

    @staticmethod
    async def download_media(
        url: str, user_id: int, progress_callback=None
    ) -> Tuple[List[str], str, Dict]:
        """Download a 91porna video using ffmpeg and extracted Cloudflare cookies."""
        info = await Porna91Service.get_media_info(url)
        if not info.get("urls"):
            return [], "unknown", {"error": info.get("error", "Failed to extract video")}

        video_url = info["urls"][0]
        cookies = info.get("cookies", {})
        referer = info.get("referer", "https://91porna.com/")
        
        filename = f"{info['title']}_{user_id}_{int(time.time())}.mp4"
        file_path = os.path.join(get_platform_folder("91Porna", "video"), filename)

        loop = asyncio.get_event_loop()

        def _download():
            headers = f"User-Agent: {Porna91Service._user_agent}\r\nReferer: {referer}\r\n"
            
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            if cookie_str:
                headers += f"Cookie: {cookie_str}\r\n"

            logger.info(f"Starting FFMPEG HLS download for 91porna: {video_url}")
            
            command = [
                "ffmpeg",
                "-y",
                "-headers", headers,
                "-i", video_url,
                "-c", "copy",
                "-bsf:a", "aac_adtstoasc",
                file_path
            ]
            
            try:
                proc = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=600 # 10 minute timeout
                )
                logger.debug(f"FFMPEG output: {proc.stderr.decode('utf-8', errors='ignore')}")
            except subprocess.CalledProcessError as e:
                logger.error(f"FFMPEG download failed: {e.stderr.decode('utf-8', errors='ignore')}")
                raise Exception(f"FFMPEG download failed. Return code: {e.returncode}")
            except subprocess.TimeoutExpired:
                logger.error("FFMPEG download timed out")
                raise Exception("FFMPEG download timed out after 10 minutes")

        try:
            if progress_callback:
                progress_callback({"status": "downloading", "filename": filename})
                
            await loop.run_in_executor(None, _download)
            logger.info(f"Successfully downloaded 91porna video to {file_path}")
        except Exception as e:
            logger.error(f"Download failed for 91porna url {url}: {e}")
            return [], "unknown", {"error": str(e)}

        if not os.path.exists(file_path):
            return [], "unknown", {"error": "File not found after download"}

        if progress_callback:
            progress_callback({"status": "done", "filename": filename})

        metadata = {
            "author": info.get("author", "91Porna"),
            "subreddit": "91Porna",
            "title": info.get("title", "91porna Video"),
            "is_video": True,
            "source_url": url,
        }
        return [file_path], "video", metadata

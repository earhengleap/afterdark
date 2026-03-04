import asyncio
import logging
import re
import os
import time
import subprocess
from typing import List, Dict, Optional, Tuple

from core.logger import setup_logger
from config.paths import get_platform_folder

logger = setup_logger("Porny91Service")

class Porny91Service:
    """Service to handle video extraction from 91porny.com using Playwright."""

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
    def is_91porny_url(url: str) -> bool:
        """Check if URL belongs to 91porny"""
        return bool(re.search(r'(91porny\.com)', url, re.IGNORECASE))

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
                        args=Porny91Service._CHROMIUM_ARGS,
                    )
                    context = await browser.new_context(
                        user_agent=Porny91Service._user_agent,
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
                        # Intercept any m3u8 playlist links fire from the player
                        if "m3u8" in request.url and m3u8_url is None:
                            logger.info(f"Intercepted HLS Playlist: {request.url}")
                            m3u8_url = request.url

                    page.on("request", handle_request)

                    try:
                        logger.info(f"Navigating to 91porny (Attempt {attempt}): {url}")
                        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)

                        # Wait for the page/Cloudflare to settle and player initialization
                        await page.wait_for_timeout(8000)

                        # Fallback: Scrape from DOM if network interception missed it
                        if not m3u8_url:
                            m3u8_url = await page.evaluate('''() => {
                                const player = document.querySelector('#video-play_html5_api');
                                if (player) {
                                    return player.getAttribute('src') || player.querySelector('source')?.getAttribute('src');
                                }
                                return null;
                            }''')

                        # Extract Cloudflare passing cookies
                        cookies = await context.cookies()
                        cookie_dict = {c['name']: c['value'] for c in cookies}

                        if m3u8_url:
                            logger.info(f"Extracted 91porny video src: {m3u8_url}")
                            return m3u8_url, cookie_dict
                        else:
                            logger.warning("No m3u8 source could be identified.")

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
        """Extract the direct video URL and metadata from a 91porny link."""
        m3u8_url, cookies = await Porny91Service._extract_m3u8_url(url)

        if not m3u8_url:
            logger.error(f"Could not extract video URL for {url}")
            return {"urls": [], "error": "No video source found or blocked by Cloudflare."}

        title = "91porny_video"
        # Extract ID from URL like /video/view/51e2493673d16465ee04
        m = re.search(r'view/([a-zA-Z0-9]+)', url)
        if m:
            title = f"91porny_{m.group(1)}"

        return {
            "urls": [m3u8_url],
            "title": title,
            "author": "91Porny",
            "source": "91Porny",
            "cookies": cookies,
            "referer": url
        }

    @staticmethod
    async def download_media(
        url: str, user_id: int, progress_callback=None
    ) -> Tuple[List[str], str, Dict]:
        """Download a 91porny video using ffmpeg and extracted Cloudflare cookies."""
        info = await Porny91Service.get_media_info(url)
        if not info.get("urls"):
            return [], "unknown", {"error": info.get("error", "Failed to extract video")}

        video_url = info["urls"][0]
        cookies = info.get("cookies", {})
        referer = info.get("referer", "https://91porny.com/")
        
        filename = f"{info['title']}_{user_id}_{int(time.time())}.mp4"
        file_path = os.path.join(get_platform_folder("91Porny", "video"), filename)

        loop = asyncio.get_event_loop()

        def _download():
            headers = f"User-Agent: {Porny91Service._user_agent}\r\nReferer: {referer}\r\n"
            
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            if cookie_str:
                headers += f"Cookie: {cookie_str}\r\n"

            logger.info(f"Starting FFMPEG HLS download for 91porny: {video_url}")
            
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
                    timeout=900 # 15 minute timeout for longer videos
                )
            except subprocess.CalledProcessError as e:
                logger.error(f"FFMPEG download failed: {e.stderr.decode('utf-8', errors='ignore')}")
                raise Exception(f"FFMPEG download failed. Code: {e.returncode}")

        try:
            if progress_callback:
                progress_callback({"status": "downloading", "filename": filename})
                
            await loop.run_in_executor(None, _download)
            logger.info(f"Successfully downloaded 91porny video to {file_path}")
        except Exception as e:
            logger.error(f"Download failed for 91porny url {url}: {e}")
            return [], "unknown", {"error": str(e)}

        if not os.path.exists(file_path):
            return [], "unknown", {"error": "File not found after download"}

        if progress_callback:
            progress_callback({"status": "done", "filename": filename})

        metadata = {
            "author": info.get("author", "91Porny"),
            "subreddit": "91Porny",
            "title": info.get("title", "91Porny Video"),
            "is_video": True,
            "source_url": url,
        }
        return [file_path], "video", metadata

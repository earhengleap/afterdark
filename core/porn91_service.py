import asyncio
import logging
import re
import os
import time
import requests
import uuid
from typing import List, Dict, Optional, Tuple

from core.logger import setup_logger
from config.paths import DOWNLOAD_FOLDER

logger = setup_logger("Porn91Service")

class Porn91Service:
    """Service to handle video extraction from 91porn.com using Playwright."""

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
    def is_91porn_url(url: str) -> bool:
        """Check if URL belongs to 91porn or its common mirrors"""
        return bool(re.search(r'(91porn\.com|91p52\.com|91p\.com|91\.[a-zA-Z0-9]+\.xyz)', url, re.IGNORECASE))

    @staticmethod
    async def _extract_video_url(url: str) -> Tuple[Optional[str], Optional[Dict[str, str]]]:
        """Load the page in headless Chromium to bypass Cloudflare and extract MP4 + Cookies"""
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
                        args=Porn91Service._CHROMIUM_ARGS,
                    )
                    context = await browser.new_context(
                        user_agent=Porn91Service._user_agent,
                        extra_http_headers={
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        },
                    )
                    page = await context.new_page()

                    await page.add_init_script(
                        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                    )

                    try:
                        logger.info(f"Navigating to 91porn (Attempt {attempt}): {url}")
                        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)

                        # Wait for page/Cloudflare to settle
                        await page.wait_for_timeout(3000)

                        # Extract video source
                        video_src = None
                        # 1. Search for ev.php embed link in the main page DOM
                        # The embed link bypasses the ~9 minute guest truncation limit
                        html = await page.content()
                        m_embed = re.search(r'(https?://[^\'"\s<>]*(?:ev|embed)\.php\?VID=[a-zA-Z0-9]+)', html)
                        
                        embed_url = m_embed.group(1) if m_embed else None
                        logger.info(f"DEBUG: Scraped embed_url from main page regex: {embed_url}")
                        if embed_url:
                            logger.info(f"Found 91porn embed link, following to bypass limits: {embed_url}")
                            try:
                                logger.info("Setting referer and navigating to embed")
                                await page.set_extra_http_headers({'Referer': 'https://91porn.com/'})
                                await page.goto(embed_url, wait_until="networkidle", timeout=25_000)
                                await page.wait_for_selector('#player_one_html5_api', timeout=10000)
                                await page.wait_for_timeout(2000)
                                
                                video_src = await page.evaluate('''() => {
                                    const mainPlayer = document.querySelector('#player_one_html5_api');
                                    if (mainPlayer) {
                                        const src = mainPlayer.querySelector('source');
                                        if (src && src.getAttribute('src')) return src.getAttribute('src');
                                        if (mainPlayer.getAttribute('src')) return mainPlayer.getAttribute('src');
                                    }
                                    return null;
                                }''')
                                logger.info(f"DEBUG: Evaluated JS Result: {video_src[:50] if video_src else 'None'}")
                                if video_src:
                                    logger.info(f"Successfully extracted CDN string from DOM: {video_src[:30]}...")
                                else:
                                    logger.warning("DOM extraction returned null video_src")
                            except Exception as e:
                                logger.warning(f"Failed to extract from embed url DOM: {e}")
                        else:
                            logger.info(f"DEBUG: No embed_url found on {url}")
                        
                        # 2. If no embed found (or extraction failed for embed), fallback to the truncated main player
                        if not video_src:
                            logger.info("Falling back to extracting from main player")
                            # Look back at original page
                            await page.goto(url, wait_until="domcontentloaded")
                            html = await page.content()
                            
                            # Existing fallback extraction logic
                            m = re.search(r'(https?://[^\'"\s<>]+\.rsc\.cdn77\.org/mp43/[^\'"\s<>]+)', html)
                            if m:
                                video_src = m.group(1)
                            else:
                                # further fallback via javascript extract...
                                video_src = await page.evaluate('''() => {
                                    const mainPlayer = document.querySelector('#player_one_html5_api');
                                    if (mainPlayer) {
                                        const src = mainPlayer.querySelector('source');
                                        if (src && src.getAttribute('src')) return src.getAttribute('src');
                                        if (mainPlayer.getAttribute('src')) return mainPlayer.getAttribute('src');
                                    }
                                    return null;
                                }''')
                        
                        # Extract Cloudflare passing cookies
                        cookies = await context.cookies()
                        cookie_dict = {c['name']: c['value'] for c in cookies}

                        if video_src:
                            logger.info(f"Extracted 91porn video src: {video_src}")
                            return video_src, cookie_dict

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
        """Extract the direct video URL and metadata from a 91porn link."""
        video_url, cookies = await Porn91Service._extract_video_url(url)

        if not video_url:
            logger.error(f"Could not extract video URL for {url}")
            return {"urls": [], "error": "No video source found or blocked by Cloudflare."}

        # Grab title directly from the page using Playwright earlier, but as a fallback:
        title = "91porn_video"
        m = re.search(r'viewkey=([a-zA-Z0-9]+)', url)
        if m:
            title = f"91porn_{m.group(1)}"
        else:
            m2 = re.search(r'VID=([a-zA-Z0-9]+)', url)
            if m2:
                title = f"91porn_embed_{m2.group(1)}"

        return {
            "urls": [video_url],
            "title": title,
            "author": "91Porn",
            "source": "91Porn",
            "cookies": cookies,  # IMPORTANT: Pass cookies down for the downloader!
            "referer": url
        }

    @staticmethod
    async def download_media(
        url: str, user_id: int, progress_callback=None
    ) -> Tuple[List[str], str, Dict]:
        """Download a 91porn video using extracted Cloudflare cookies."""
        info = await Porn91Service.get_media_info(url)
        if not info.get("urls"):
            return [], "unknown", {"error": info.get("error", "Failed to extract video")}

        video_url = info["urls"][0]
        cookies = info.get("cookies", {})
        referer = info.get("referer", "https://91porn.com/")
        
        filename = f"{info['title']}_{user_id}_{int(time.time())}.mp4"
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)

        loop = asyncio.get_event_loop()

        def _download():
            headers = {
                'User-Agent': Porn91Service._user_agent,
                'Referer': referer,
                'Accept': '*/*'
            }
            
            # Format cookies for requests
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            if cookie_str:
                headers['Cookie'] = cookie_str

            logger.info(f"Starting native request to 91porn CDN: {video_url}")
            resp = requests.get(
                video_url,
                headers=headers,
                stream=True,
                timeout=60,
            )
            resp.raise_for_status()

            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0
            start_time = time.time()

            with open(file_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
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
                                "filename": filename,
                            })

        try:
            if progress_callback:
                progress_callback({"status": "downloading", "filename": filename})
            await loop.run_in_executor(None, _download)
            logger.info(f"Successfully downloaded 91porn video to {file_path}")
        except Exception as e:
            logger.error(f"Download failed for 91porn url {url}: {e}")
            return [], "unknown", {"error": str(e)}

        if not os.path.exists(file_path):
            return [], "unknown", {"error": "File not found after download"}

        if progress_callback:
            progress_callback({"status": "done", "filename": filename})

        metadata = {
            "author": info.get("author", "91Porn"),
            "subreddit": "91Porn",
            "title": info.get("title", "91Porn Video"),
            "is_video": True,
            "source_url": url,
        }
        return [file_path], "video", metadata

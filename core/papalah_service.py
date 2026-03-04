import asyncio
import logging
import re
import os
import time
import sys
import requests
import uuid
from typing import List, Dict, Optional, Tuple

from core.logger import setup_logger
from config.paths import get_platform_folder

logger = setup_logger("PapalahService")


class PapalahService:
    """Service to handle video extraction from papalah.com using Playwright.

    The actual video is a direct MP4 hosted on media.aiailah.com and is stored
    in the VideoJS player's options_.sources — NOT in HLS/m3u8 streams.
    The m3u8 network requests on the page are all from advertisements.
    """

    _user_agent = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    )

    _headers = {
        'User-Agent': _user_agent,
        'Referer': 'https://www.papalah.com/',
    }

    # JS snippet: reads direct src from VideoJS player options or <source> tag
    _JS_GET_SRC = """() => {
        // Method 1: VideoJS player options (most reliable)
        if (window.videojs && window.videojs.players) {
            for (const id in window.videojs.players) {
                const player = window.videojs.players[id];
                const sources = (player.options_ && player.options_.sources) || [];
                for (const s of sources) {
                    if (s.src && (s.src.includes('.mp4') || s.src.includes('.m3u8'))) {
                        return s.src;
                    }
                }
                const cur = player.currentSrc && player.currentSrc();
                if (cur && (cur.includes('.mp4') || cur.includes('.m3u8'))) {
                    return cur;
                }
            }
        }

        // Method 2: <source> element inside <video>
        const src = document.querySelector('video source[src]');
        if (src) return src.getAttribute('src');

        // Method 3: src attribute on the <video> element itself
        const vid = document.querySelector('video[src]');
        if (vid) return vid.getAttribute('src');

        return null;
    }"""

    # Stealth Chromium args to reduce bot-detection and connection resets
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
    def _html_fallback(url: str) -> Optional[str]:
        """Try to extract the video URL from raw HTML using requests + regex.
        Used when the headless browser is blocked/reset by the server."""
        try:
            resp = requests.get(url, headers=PapalahService._headers, timeout=20)
            if not resp.ok:
                return None
            html = resp.text
            patterns = [
                r'"src"\s*:\s*"(https?://[^"]+\.mp4[^"]*)"',
                r"'src'\s*:\s*'(https?://[^']+\.mp4[^']*)'",
                r'file\s*:\s*["\']?(https?://[^"\'>\s]+\.mp4[^"\'>\s]*)',
                r'(https?://[^"\'>\s]+media\.aiailah\.com[^"\'>\s]+\.mp4[^"\'>\s]*)',
                r'(https?://[^"\'>\s]+\.m3u8[^"\'>\s]*)',
            ]
            for pat in patterns:
                m = re.search(pat, html, re.IGNORECASE)
                if m:
                    video_url = m.group(1).replace('\\/', '/')
                    logger.info(f"HTML fallback found video URL: {video_url}")
                    return video_url
        except Exception as e:
            logger.warning(f"HTML fallback failed: {e}")
        return None

    @staticmethod
    async def _extract_video_url(url: str) -> Optional[str]:
        """Load the page in a headless Chromium browser and extract the video
        URL from the VideoJS player.  Retries up to 3 times on connection
        errors; falls back to HTML regex parsing if all attempts fail."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error(
                "playwright not installed. "
                "Run: pip install playwright && playwright install chromium"
            )
            return None

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(
                        headless=True,
                        args=PapalahService._CHROMIUM_ARGS,
                    )
                    context = await browser.new_context(
                        user_agent=PapalahService._user_agent,
                        extra_http_headers={
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Accept': (
                                'text/html,application/xhtml+xml,'
                                'application/xml;q=0.9,*/*;q=0.8'
                            ),
                        },
                    )
                    page = await context.new_page()

                    # Hide the webdriver flag to reduce bot detection
                    await page.add_init_script(
                        "Object.defineProperty(navigator, 'webdriver', "
                        "{get: () => undefined})"
                    )

                    video_src = None
                    try:
                        await page.goto(
                            url, wait_until="domcontentloaded", timeout=45_000
                        )

                        # Wait for VideoJS to initialise (<2 s normally)
                        try:
                            await page.wait_for_function(
                                "() => window.videojs && "
                                "Object.keys(window.videojs.players).length > 0",
                                timeout=10_000,
                            )
                        except Exception:
                            pass  # VideoJS may not be present; carry on

                        video_src = await page.evaluate(PapalahService._JS_GET_SRC)

                        if video_src:
                            logger.info(f"Extracted video src from player: {video_src}")
                        else:
                            logger.warning(
                                "VideoJS found but no src yet; waiting 3s then retrying eval..."
                            )
                            await page.wait_for_timeout(3_000)
                            video_src = await page.evaluate(PapalahService._JS_GET_SRC)

                    except Exception as e:
                        logger.warning(
                            f"Page load issue (attempt {attempt}/{max_retries}): {e}; "
                            "attempting JS eval on partial page..."
                        )
                        try:
                            video_src = await page.evaluate(PapalahService._JS_GET_SRC)
                        except Exception:
                            pass
                    finally:
                        await browser.close()

                    if video_src:
                        return video_src

            except Exception as e:
                logger.warning(f"Playwright attempt {attempt}/{max_retries} failed: {e}")

            if attempt < max_retries:
                wait_secs = attempt * 5
                logger.info(f"Retrying in {wait_secs}s... (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait_secs)

        # All Playwright attempts exhausted — try plain HTTP + regex
        logger.info("All Playwright attempts failed; trying HTML regex fallback...")
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, PapalahService._html_fallback, url)

    @staticmethod
    async def _get_page_title(url: str) -> str:
        """Fetch the og:title from the raw HTML (no JS needed)."""
        try:
            resp = requests.get(url, headers=PapalahService._headers, timeout=10)
            if resp.ok:
                m = re.search(r'<meta property="og:title" content="([^"]+)"', resp.text)
                if m:
                    return m.group(1)
        except Exception:
            pass
        return "Papalah Video"

    @staticmethod
    async def get_media_info(url: str) -> Dict:
        """Extract the direct video URL and metadata from a papalah.com link."""
        title_task = asyncio.ensure_future(PapalahService._get_page_title(url))
        src_task   = asyncio.ensure_future(PapalahService._extract_video_url(url))

        title, video_url = await asyncio.gather(title_task, src_task)

        if not video_url:
            logger.error(f"Could not extract video URL for {url}")
            return {"urls": [], "error": "No video source found on page."}

        return {
            "urls":   [video_url],
            "title":  title,
            "author": "Papalah User",
            "source": "Papalah",
        }

    @staticmethod
    async def scrape_user_media(username: str, limit: Optional[int] = None) -> Dict:
        """Fetch all video page URLs from a Papalah user's profile."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("playwright not installed.")
            return {"post_urls": [], "video_count": 0, "error": "Playwright missing"}

        all_video_urls = set()
        current_page = 1
        has_next_page = True
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=PapalahService._CHROMIUM_ARGS
            )
            context = await browser.new_context(
                user_agent=PapalahService._user_agent,
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                }
            )
            page = await context.new_page()
            
            # Hide webdriver execution
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            
            try:
                while has_next_page:
                    url = f"https://www.papalah.com/v/{username}"
                    if current_page > 1:
                        url += f"?page={current_page}"
                        
                    logger.info(f"Papalah bulk: Crawling profile page {current_page} - {url}")
                    
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                        await page.wait_for_timeout(3000) # Give DOM time to settle
                        html_content = await page.content()
                    except Exception as e:
                        logger.warning(f"Failed to load page {current_page} for {username}: {e}")
                        break
                        
                    # Find video paths: format is /v/USER_ID/VIDEO_NAME
                    # Avoid capturing the root user path /v/USER_ID or /v/USER_ID/
                    pat_str = r'href=[\'\"]?(/v/' + re.escape(username) + r'/[^\'\" >/?]+)[\'\"]?'
                    matches = re.findall(pat_str, html_content)
                    
                    page_urls = set()
                    for match in matches:
                        # Ensure we don't just grab the profile link itself
                        if match.strip('/') == f"v/{username}":
                            continue
                        full_url = "https://www.papalah.com" + match
                        page_urls.add(full_url)
                        all_video_urls.add(full_url)
                        
                    if limit and len(all_video_urls) >= limit:
                        # Cut off if we reached the cap
                        all_video_urls = set(list(all_video_urls)[:limit])
                        break
                        
                    # Check if there is a 'next page' button or if no new URLs were found
                    if not page_urls:
                        break
                        
                    # Basic pagination logic snippet: Look for hrefs matching ?page={current_page + 1}
                    next_page_str = f"?page={current_page + 1}"
                    if next_page_str not in html_content:
                        has_next_page = False
                    else:
                        current_page += 1
                        await asyncio.sleep(2) # Be polite
                        
            finally:
                await browser.close()
                
        final_urls = list(all_video_urls)
        return {
            "post_urls": final_urls,
            "video_count": len(final_urls),
            "image_count": 0
        }


    @staticmethod
    async def download_media(
        url: str, user_id: int, progress_callback=None
    ) -> Tuple[List[str], str, Dict]:
        """Download a Papalah video with chunked progress reporting."""
        info = await PapalahService.get_media_info(url)
        if not info.get("urls"):
            return [], "unknown", {"error": info.get("error", "Failed to extract video")}

        video_url = info["urls"][0]
        filename  = f"papalah_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}.mp4"
        file_path = os.path.join(get_platform_folder("Papalah", "video"), filename)

        loop = asyncio.get_event_loop()

        def _download():
            resp = requests.get(
                video_url,
                headers=PapalahService._headers,
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
                            speed   = downloaded / elapsed if elapsed > 0 else 0
                            progress_callback({
                                "status":           "downloading",
                                "downloaded_bytes": downloaded,
                                "total_bytes":      total_size,
                                "speed":            speed,
                                "filename":         filename,
                            })

        try:
            if progress_callback:
                progress_callback({"status": "downloading", "filename": filename})
            await loop.run_in_executor(None, _download)
        except Exception as e:
            logger.error(f"Download failed for {url}: {e}")
            return [], "unknown", {"error": str(e)}

        if not os.path.exists(file_path):
            return [], "unknown", {"error": "File not found after download"}

        if progress_callback:
            progress_callback({"status": "done", "filename": filename})

        metadata = {
            "author":     info.get("author", "Papalah User"),
            "subreddit":  "Papalah",
            "title":      info.get("title", "Video"),
            "is_video":   True,
            "source_url": url,
        }
        return [file_path], "video", metadata

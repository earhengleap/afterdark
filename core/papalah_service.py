import asyncio
import logging
import re
import os
import time
import sys
import requests
from typing import List, Dict, Optional, Tuple

from core.logger import setup_logger
from config.paths import DOWNLOAD_FOLDER

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
                // Read configured sources (set before any ad plays)
                const sources = (player.options_ && player.options_.sources) || [];
                for (const s of sources) {
                    if (s.src && (s.src.includes('.mp4') || s.src.includes('.m3u8'))) {
                        return s.src;
                    }
                }
                // Fallback to currentSrc if sources list is empty
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

    @staticmethod
    async def _extract_video_url(url: str) -> Optional[str]:
        """Load the page in a headless browser and read the video src from the
        VideoJS player API — this is the actual content URL, not an ad stream."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("playwright not installed. Run: pip install playwright && playwright install chromium")
            return None

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=PapalahService._user_agent)
            page = await context.new_page()
            video_src = None

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

                # Wait for the VideoJS player to initialise (usually < 2 s)
                await page.wait_for_function(
                    "() => window.videojs && Object.keys(window.videojs.players).length > 0",
                    timeout=10_000,
                )

                video_src = await page.evaluate(PapalahService._JS_GET_SRC)

                if video_src:
                    logger.info(f"Extracted video src from player: {video_src}")
                else:
                    logger.warning("VideoJS player found but no src detected; trying <video> tag wait...")
                    # Give DOM one more moment then retry
                    await page.wait_for_timeout(3_000)
                    video_src = await page.evaluate(PapalahService._JS_GET_SRC)

            except Exception as e:
                logger.warning(f"Page load issue: {e}; attempting JS eval anyway")
                try:
                    video_src = await page.evaluate(PapalahService._JS_GET_SRC)
                except Exception:
                    pass
            finally:
                await browser.close()

        return video_src

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
    async def download_media(url: str, user_id: int, progress_callback=None) -> Tuple[List[str], str, Dict]:
        """Download a Papalah video with chunked progress reporting."""
        info = await PapalahService.get_media_info(url)
        if not info.get("urls"):
            return [], "unknown", {"error": info.get("error", "Failed to extract video")}

        video_url = info["urls"][0]
        filename  = f"papalah_{user_id}_{int(time.time())}.mp4"
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)

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


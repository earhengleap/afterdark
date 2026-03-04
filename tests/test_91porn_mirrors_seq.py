import asyncio
import os
import re
import urllib.parse
from playwright.async_api import async_playwright

async def test_single_mirror(browser, url):
    print(f"\nMirror: {url}")
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    try:
        # Reduced timeout to avoid hanging the whole script
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)
        
        res = await page.evaluate('''() => {
            const title = document.title;
            const textarea = document.querySelector('#fm-video_link');
            const poster = document.querySelector('video')?.getAttribute('poster') || document.querySelector('.vjs-poster')?.style.backgroundImage;
            return {
                title: title,
                fm_vid: textarea ? textarea.value.match(/VID=([a-zA-Z0-9]+)/)?.[1] : null,
                poster: poster
            };
        }''')
        print(f"  Title: {res['title']}")
        print(f"  FM VID: {res['fm_vid']}")
        print(f"  Poster: {res['poster']}")
    except Exception as e:
        print(f"  Error: {e}")
    finally:
        await page.close()
        await context.close()

async def run_tests():
    viewkey = "7e0b07fe5a33a7bd9913"
    mirrors = [
        f"https://91porn.com/view_video.php?viewkey={viewkey}",
        f"https://www.91p52.com/view_video.php?viewkey={viewkey}",
        f"https://www.91p30.com/view_video.php?viewkey={viewkey}"
    ]
    
    async with async_playwright() as p:
        # Use a non-headless browser if possible or just stick to headful for better bypass
        browser = await p.chromium.launch(headless=True)
        for url in mirrors:
            await test_single_mirror(browser, url)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_tests())

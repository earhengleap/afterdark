import asyncio
from playwright.async_api import async_playwright
import re

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # ID is usually numeric, e.g., 102812
        url = "https://www.papalah.com/v/102812"
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        
        # Give it a moment to load
        await page.wait_for_timeout(3000)
        
        html = await page.content()
        patterns = [
            r'href=[\'\"]?(https?://(?:www\.)?papalah\.com/v/102812/[^\'\" >]+)',
            r'href=[\'\"]?(/v/102812/[^\'\" >]+)'
        ]
        
        links = []
        for pat in patterns:
            for match in re.findall(pat, html):
                if match.startswith('/'):
                    links.append('https://www.papalah.com' + match)
                else:
                    links.append(match)
                    
        unique_links = list(set(links))
        print(f"Found {len(unique_links)} videos")
        for l in unique_links[:5]:
            print(l)
            
        await browser.close()
        
asyncio.run(main())

import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        await page.goto("https://91porna.com/comic/index/detail?video_key=283079", wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(5000)
        html = await page.content()
        with open("d:\\test_91porna.html", "w", encoding="utf-8") as f:
            f.write(html)
        print("HTML saved to d:\\test_91porna.html")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())

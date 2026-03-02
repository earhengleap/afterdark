import asyncio
from playwright.async_api import async_playwright
import json

async def test_playwright_redgifs():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        print("Navigating to auth endpoint...")
        try:
            # We can just fetch the token using page.evaluate to run fetch() inside the browser context
            # to bypass the Python connection reset
            await page.goto("https://www.redgifs.com", wait_until="domcontentloaded", timeout=20000)
            token_json = await page.evaluate('''async () => {
                const resp = await fetch("https://api.redgifs.com/v2/auth/temporary");
                return await resp.json();
            }''')
            print("Token JSON:", token_json)
        except Exception as e:
            print("Error in Playwright:", e)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_playwright_redgifs())

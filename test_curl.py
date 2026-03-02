import asyncio
from curl_cffi.requests import AsyncSession

async def test():
    async with AsyncSession(impersonate="chrome110") as session:
        try:
            resp = await session.get("https://api.redgifs.com/v2/auth/temporary", headers={
                'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                'Origin': 'https://www.redgifs.com',
                'Referer': 'https://www.redgifs.com/'
            }, timeout=10)
            print("Status:", resp.status_code)
            print("JSON:", resp.json())
        except Exception as e:
            print("Failed:", e)

if __name__ == "__main__":
    asyncio.run(test())

import asyncio
import os
from core.bad_news_service import BadNewsService

async def test():
    url = 'https://bad.news/t/5986416'
    print('Testing get_media_info:')
    info = await BadNewsService.get_media_info(url)
    print("INFO:", info)
    print('\nTesting download_media:')
    res = await BadNewsService.download_media(url, 123)
    print("RES:", res)
    if res and res[0] and res[0][0]:
        print("Cleaning up:", res[0][0])
        try:
            os.remove(res[0][0])
        except:
            pass

if __name__ == '__main__':
    asyncio.run(test())

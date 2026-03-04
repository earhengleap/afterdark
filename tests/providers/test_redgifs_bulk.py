import asyncio
import os
import sys

# Ensure AfterDark imports work by adding it to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.redgifs_media_service import RedGifsMediaService

async def main():
    urls = [
        "https://www.redgifs.com/watch/bowedsleepynandine",
        "https://www.redgifs.com/watch/wellinformedwastefulkingbird" 
    ]
    
    direct_urls = []
    for u in urls:
        d = await RedGifsMediaService.get_direct_url(u)
        direct_urls.append(d)
        print(f"{u} -> {d}")
        
    tasks = [RedGifsMediaService.download_media(u, 123) for u in urls]
    results = await asyncio.gather(*tasks)
    print("\nDownload Results:")
    for r in results:
        print(r)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.porny91_service import Porny91Service

async def test_91porny_download():
    url = "https://91porny.com/video/view/51e2493673d16465ee04"
    user_id = 999
    
    print(f"Testing 91porny download for: {url}")
    
    def progress_callback(status):
        print(f"Progress: {status}")

    paths, media_type, metadata = await Porny91Service.download_media(url, user_id, progress_callback)
    
    if paths:
        print(f"SUCCESS: Downloaded to {paths[0]}")
        print(f"Metadata: {metadata}")
    else:
        print(f"FAILED: {metadata.get('error', 'Unknown error')}")

if __name__ == "__main__":
    asyncio.run(test_91porny_download())

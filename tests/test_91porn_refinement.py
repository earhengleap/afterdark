import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.porn91_service import Porn91Service

async def test_91porn_refinement():
    url = "https://91porn.com/view_video.php?viewkey=7e0b07fe5a33a7bd9913&c=pikt1"
    user_id = 111
    
    print(f"Testing refined 91porn extraction for: {url}")
    
    def progress_callback(status):
        print(f"Progress: {status}")

    # Test extraction only first
    video_url, cookies = await Porn91Service._extract_video_url(url)
    
    if video_url:
        print(f"SUCCESS: Extracted video source: {video_url[:80]}...")
        if cookies:
            print(f"Cookies extracted: {len(cookies)} keys")
        
        # Test full download process (without actual download if possible, or just run it)
        # paths, media_type, metadata = await Porn91Service.download_media(url, user_id, progress_callback)
    else:
        print("FAILED: Extraction returned None")

if __name__ == "__main__":
    asyncio.run(test_91porn_refinement())

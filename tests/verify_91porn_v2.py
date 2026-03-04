import asyncio
import sys
import os

sys.path.append(os.getcwd())

from core.porn91_service import Porn91Service

async def verify():
    url = "https://91porn.com/view_video.php?viewkey=7e0b07fe5a33a7bd9913&c=pikt1"
    print(f"Testing strencode2 extraction for: {url}\n")
    
    info = await Porn91Service.get_media_info(url)
    
    if info.get("urls"):
        print("\n[SUCCESS] Extracted video URL:")
        print(f"  {info['urls'][0]}")
        print(f"  Title: {info.get('title')}")
    else:
        print("\n[FAILED] Could not extract video info.")
        if "error" in info:
            print(f"Error: {info['error']}")

if __name__ == "__main__":
    asyncio.run(verify())

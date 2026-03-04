import asyncio
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

from core.porn91_service import Porn91Service

async def verify_91porn():
    url = "https://91porn.com/view_video.php?viewkey=7e0b07fe5a33a7bd9913&c=pikt1"
    print(f"Testing 91porn refinement for: {url}")
    
    # We call get_media_info which triggers _extract_video_url
    info = await Porn91Service.get_media_info(url)
    
    if info.get("urls"):
        print("\n[SUCCESS] Extracted video URLs:")
        for u in info["urls"]:
            print(f"- {u}")
        print(f"Title: {info.get('title')}")
        
        # Check if the extracted URL looks like a valid CDN link and not the ad one
        # If it contains the correct ID (from the embed), it's likely correct.
    else:
        print("\n[FAILED] Could not extract video info.")
        if "error" in info:
            print(f"Error: {info['error']}")

if __name__ == "__main__":
    asyncio.run(verify_91porn())

import asyncio
import os
import sys
from pyrogram import Client

# Add project root to path
sys.path.insert(0, os.getcwd())

from config.config import API_ID, API_HASH, CHAT_ID

async def test_sync():
    session_path = "dashboard/media_cache/twa_user"
    print(f"Testing session: {session_path}")
    
    app = Client("twa_user", api_id=API_ID, api_hash=API_HASH, workdir="dashboard/media_cache")
    
    try:
        await app.start()
        print("✅ Session started successfully")
        
        chat = await app.get_chat(CHAT_ID)
        print(f"✅ Successfully accessed chat: {chat.title} ({chat.id})")
        
        count = 0
        async for message in app.get_chat_history(CHAT_ID, limit=5):
            if message.media:
                count += 1
        print(f"✅ Found {count} media items in last 5 messages")
        
        await app.stop()
        print("✅ Test completed")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_sync())

import asyncio
from pyrogram import Client

async def main():
    print("--- AfterDark Session String Generator ---")
    api_id = input("Enter API ID: ")
    api_hash = input("Enter API Hash: ")
    
    async with Client(":memory:", api_id=int(api_id), api_hash=api_hash) as app:
        session_string = await app.export_session_string()
        print("\n" + "="*50)
        print("YOUR SESSION STRING (Keep this secret!):")
        print("="*50)
        print(session_string)
        print("="*50 + "\n")
        print("Copy the string above and paste it into config/config.py")

if __name__ == "__main__":
    asyncio.run(main())

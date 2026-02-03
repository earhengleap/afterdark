from telethon import TelegramClient
import asyncio
import os

api_id = 22268900
api_hash = '6764e4d6dd12108e82105f355c6309d8'
# session file name (Telethon will create a file with this name + ".session")
session_file = 'my_telegram_session'

client = TelegramClient(session_file, api_id, api_hash)

async def main():
    await client.start()  # will reuse session if it exists
    me = await client.get_me()
    print(f"Logged in as: {me.first_name} (@{me.username})\n")
    print("Your groups that you created:\n")

    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        # Only consider groups/supergroups
        if getattr(entity, 'megagroup', None) is not None or dialog.is_group:
            try:
                full_info = await client.get_entity(entity.id)
                # Check if you are the creator (for supergroups/channels)
                if hasattr(full_info, 'creator') and full_info.creator:
                    print(f"✅ Group title: {dialog.name!r}  —  ID: {entity.id}")
            except:
                # fallback for small groups
                participants = await client.get_participants(entity)
                for p in participants:
                    if p.id == me.id and getattr(p, 'is_creator', False):
                        print(f"✅ Group title: {dialog.name!r}  —  ID: {entity.id}")
                        break

asyncio.run(main())

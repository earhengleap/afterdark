from telethon import TelegramClient
import asyncio

API_ID = 22268900
API_HASH = "6764e4d6dd12108e82105f355c6309d8"
SESSION_NAME = "my_account.session"

OUTPUT_FILE = "channels_list.txt"

async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()

    lines = []
    print("✅ Listing your channels...")

    async for dialog in client.iter_dialogs():
        if dialog.is_channel:
            name = dialog.name
            cid = dialog.entity.id
            line = f"Name: {name} | ID: {cid}"
            lines.append(line)
            print(line)

    # Save to file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n✅ Saved channel list to: {OUTPUT_FILE}")
    print("👉 Use the ID (-100xxxxxxxxxx) for downloading media.")

if __name__ == "__main__":
    asyncio.run(main())

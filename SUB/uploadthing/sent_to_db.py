import os
import asyncio
from telethon import TelegramClient
from tqdm import tqdm
from supabase import create_client, Client

# ================== Telegram Credentials ==================
API_ID = 22268900
API_HASH = '6764e4d6dd12108e82105f355c6309d8'
CHAT_ID = -1001816303239  # Telegram Group ID

# ================== Supabase Credentials ==================
SUPABASE_URL = "https://gcxpxdatsxpfslxcxrel.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdjeHB4ZGF0c3hwZnNseGN4cmVsIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MDU0NDU3MSwiZXhwIjoyMDc2MTIwNTcxfQ.U_3yBye3XBdGKV4RGjHT33aCUoHtjE4676TQ0nyJeho"
BUCKET_NAME = "telegram_uploads"

# ================== Setup Supabase & Telegram Client ==================
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
client = TelegramClient('my_session', API_ID, API_HASH)

# ================== Log file for uploaded message IDs ==================
LOG_FILE = "uploaded.log"

def load_uploaded_ids():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r") as f:
            return set(line.strip() for line in f.readlines())
    return set()

def save_uploaded_id(msg_id):
    with open(LOG_FILE, "a") as f:
        f.write(f"{msg_id}\n")

# ================== Supabase File Check ==================
def file_exists_in_supabase(file_name):
    try:
        response = supabase.storage.from_(BUCKET_NAME).list()
        if not response or "error" in response:
            print(f"⚠️ Error listing Supabase bucket: {response}")
            return False
        for f in response:
            if f["name"] == file_name:
                return True
        return False
    except Exception as e:
        print(f"⚠️ Failed to check file existence: {e}")
        return False

# ================== Upload file to Supabase ==================
def upload_to_supabase(file_path):
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    print(f"⬆️ Uploading {file_name} ({file_size / (1024*1024):.2f} MB) to Supabase...")

    try:
        # Read file content
        with open(file_path, "rb") as f:
            file_content = f.read()

        # Upload with progress bar
        with tqdm(total=file_size, unit='B', unit_scale=True, desc="⬆️ Uploading") as pbar:
            res = supabase.storage.from_(BUCKET_NAME).upload(
                path=file_name,
                file=file_content,
                file_options={
                    "content-type": "video/mp4",
                    "upsert": "true"
                }
            )
            pbar.update(file_size)

        # Get public URL
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_name)
        print(f"✅ Upload successful: {public_url}")
        return public_url

    except Exception as e:
        print(f"❌ Upload failed: {str(e)}")
        return None

# ================== Download Telegram Media ==================
async def download_with_progress(message, file_name):
    total = message.file.size
    with tqdm(total=total, unit='B', unit_scale=True, desc="📥 Downloading") as pbar:
        def callback(current, total_bytes):
            pbar.n = current
            pbar.refresh()
        await message.download_media(file=file_name, progress_callback=callback)

# ================== Main Logic ==================
async def main():
    await client.start()
    uploaded_ids = load_uploaded_ids()

    print("🤖 Bot started — scanning videos from oldest to newest...")

    # Check Supabase connection
    try:
        buckets = supabase.storage.list_buckets()
        print(f"✅ Connected to Supabase. Buckets: {[b.name for b in buckets]}")
    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        return

    async for message in client.iter_messages(CHAT_ID, reverse=True):
        if not (message.video or message.document):
            continue

        msg_id = str(message.id)
        file_name = f"video_{msg_id}.mp4"

        # Skip if already uploaded
        if msg_id in uploaded_ids:
            continue

        # Check if already exists in Supabase
        if file_exists_in_supabase(file_name):
            print(f"⚠️ {file_name} already exists in Supabase. Skipping upload.")
            save_uploaded_id(msg_id)
            uploaded_ids.add(msg_id)
            continue

        print(f"\n🎥 Found new video [ID: {msg_id}] — downloading...")

        try:
            await download_with_progress(message, file_name)

            url = upload_to_supabase(file_name)
            if url:
                save_uploaded_id(msg_id)
                uploaded_ids.add(msg_id)
                print(f"✅ Uploaded successfully [ID: {msg_id}]")

                # Delete local file after upload
                if os.path.exists(file_name):
                    os.remove(file_name)
                    print(f"🗑️ Deleted local file: {file_name}")
            else:
                print(f"⚠️ Upload failed for [ID: {msg_id}], skipping...")

        except Exception as e:
            print(f"❌ Error processing [ID: {msg_id}]: {e}")
            continue

    print("🏁 All videos processed!")

# ================== Run Script ==================
if __name__ == "__main__":
    asyncio.run(main())

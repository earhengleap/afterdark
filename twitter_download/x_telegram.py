import os
import re
import json
from datetime import datetime
import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import subprocess
import tempfile

# --- CONFIG ---
from config import BOT_TOKEN, API_ID, API_HASH

# --- USERS ---
from users.users import log_user_action

# --- Folders ---
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "videos")
DATA_FOLDER = os.path.join(os.getcwd(), "data")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)

LOG_FILE = os.path.join(DATA_FOLDER, "download_log.log")

# --- COOKIES HANDLING ---
cookies_content = os.environ.get("TWITTER_COOKIES")
if cookies_content:
    tmp_cookies_file = tempfile.NamedTemporaryFile(delete=False, mode='w', suffix=".txt")
    tmp_cookies_file.write(cookies_content)
    tmp_cookies_file.close()
    COOKIE_FILE = tmp_cookies_file.name
else:
    COOKIE_FILE = 'config/twitter_cookies.txt'  # fallback local file

# --- FFMPEG ---
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"   # Adjust if needed

# --- Pyrogram Client ---
app = Client(
    "x_video_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- Helper Functions ---
def get_next_number():
    files = os.listdir(DOWNLOAD_FOLDER)
    numbers = [int(m.group(1)) for f in files if (m := re.match(r'^(\d+)-', f))]
    return max(numbers)+1 if numbers else 1

def rename_downloaded_file(original_path):
    if not os.path.exists(original_path):
        return original_path
    directory = os.path.dirname(original_path)
    filename = os.path.basename(original_path)
    if re.match(r'^\d+-', filename):
        return original_path
    next_num = get_next_number()
    new_filename = f"{next_num:02d}-{filename}"
    new_path = os.path.join(directory, new_filename)
    os.rename(original_path, new_path)
    return new_path

def load_log():
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                return json.loads(content) if content else []
        except:
            return []
    return []

def save_log(log_data):
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

def add_to_log(video_info, filename, url):
    log_entry = {
        'number': get_next_number()-1,
        'filename': filename,
        'url': url,
        'title': video_info.get('title', 'Unknown'),
        'uploader': video_info.get('uploader', 'Unknown'),
        'username': video_info.get('uploader_id', 'Unknown'),
        'upload_date': video_info.get('upload_date', 'Unknown'),
        'duration': video_info.get('duration', 0),
        'filesize': video_info.get('filesize', 0),
        'download_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    log = load_log()
    log.append(log_entry)
    save_log(log)

def get_video_resolution(path):
    """Get width and height using ffprobe."""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "json",
            path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        info = json.loads(result.stdout)
        width = info['streams'][0]['width']
        height = info['streams'][0]['height']
        return width, height
    except Exception as e:
        print(f"⚠️ Could not get resolution: {e}")
        return None, None

# --- Download Function ---
def download_x_video(url, message=None):
    downloaded_file = None
    try:
        ydl_opts = {
            'cookiefile': COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'ffmpeg_location': FFMPEG_PATH,
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if 'requested_downloads' in info:
                downloaded_file = info['requested_downloads'][0]['filepath']
            else:
                title = info.get('title', 'video')
                downloaded_file = os.path.join(DOWNLOAD_FOLDER, f"{title}.mp4")

            if downloaded_file and os.path.exists(downloaded_file):
                new_path = rename_downloaded_file(downloaded_file)
                add_to_log(info, os.path.basename(new_path), url)
                return new_path
            else:
                return None
    except Exception as e:
        if message:
            message.reply_text(f"❌ Download failed: {e}")
        print(f"❌ Download failed: {e}")
        return None

# --- Bot Handlers ---
@app.on_message(filters.private & filters.command("start"))
def start(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬇️ Download from X", callback_data="download")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings")]
    ])
    message.reply_text(
        "👋 Welcome to **X Video Downloader Bot**!\n\n"
        "Choose an option below:",
        reply_markup=keyboard
    )

@app.on_callback_query()
def handle_callback(client, callback_query):
    data = callback_query.data

    if data == "download":
        callback_query.message.edit_text(
            "⬇️ Please drop your X/Twitter video URL here..."
        )

    elif data == "about":
        callback_query.message.edit_text(
            "ℹ️ **About this bot**\n\n"
            "This bot allows you to download videos from **X (Twitter)** and send them directly in Telegram.\n"
            "Developed with ❤️ using Pyrogram + yt-dlp."
        )

    elif data == "help":
        callback_query.message.edit_text(
            "❓ **How to use:**\n\n"
            "1. Send me a valid X/Twitter video link.\n"
            "2. Wait a moment while I download it.\n"
            "3. I’ll send the video back to you directly.\n\n"
            "Example:\n`https://x.com/username/status/1234567890`"
        )

    elif data == "settings":
        callback_query.message.edit_text(
            "⚙️ Settings are not available yet. Coming soon!"
        )

@app.on_message(filters.private & filters.text)
def handle_url(client, message):
    url = message.text.strip()
    username = message.from_user.username or message.from_user.first_name
    user_id = message.from_user.id

    if not url.startswith("http"):
        message.reply_text("❌ Please send a valid URL.")
        log_user_action(user_id, username, url, "failed")
        return

    message.reply_text(f"⏳ Downloading video from: {url} ...")
    video_path = download_x_video(url, message)

    if not video_path or not os.path.exists(video_path):
        message.reply_text("❌ Failed to download video file.")
        log_user_action(user_id, username, url, "failed")
        return

    width, height = get_video_resolution(video_path)

    try:
        app.send_video(
            chat_id=message.chat.id,
            video=video_path,
            width=width if width else 720,
            height=height if height else 1280,
            supports_streaming=True
        )
        message.reply_text(f"✅ Video uploaded: {os.path.basename(video_path)}")
        log_user_action(user_id, username, url, "success")
    except Exception as e:
        message.reply_text(f"❌ Upload failed: {e}")
        log_user_action(user_id, username, url, "failed")

# --- Run Bot ---
if __name__ == "__main__":
    print("Bot is running...")
    app.run()

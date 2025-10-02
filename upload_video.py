import os
from pyrogram import Client
from config import BOT_TOKEN, CHAT_ID, API_ID, API_HASH
from datetime import datetime

# Create Pyrogram client using bot
app = Client(
    "video_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Path to store upload logs
LOG_FILE = "upload_history.log"

def format_duration(seconds):
    """Format duration dynamically based on video length."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        sec = int(seconds % 60)
        return f"{minutes}m {sec}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        sec = int(seconds % 60)
        return f"{hours}h {minutes}m {sec}s"

def get_video_dimensions(video_path):
    """Extract video width, height, FPS, and duration using OpenCV."""
    try:
        import cv2

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print("⚠️ Could not open video file")
            return None, None, None, None

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frame_count / fps if fps > 0 else 0

        cap.release()
        return width, height, fps, duration

    except ImportError:
        print("⚠️ OpenCV not installed. Install with: pip install opencv-python")
        return None, None, None, None
    except Exception as e:
        print(f"⚠️ Error reading video: {e}")
        return None, None, None, None

def log_upload(video_path, file_size, width, height, fps, duration, upload_type):
    """Log video upload info to file."""
    video_name = os.path.basename(video_path)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_lines = [
        "="*80,
        f"📤 Upload Timestamp : {timestamp}",
        f"📁 File Name        : {video_name}",
        f"💾 File Size        : {file_size / (1024*1024):.2f} MB",
        f"📄 Upload Type      : {upload_type}"
    ]

    if width and height:
        log_lines.extend([
            f"📺 Resolution       : {width}x{height}",
            f"🎬 FPS             : {fps}",
            f"⏱️  Duration        : {format_duration(duration)}"
        ])

    log_lines.append("="*80 + "\n")

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

def upload_video(video_path):
    """Upload video to Telegram group with Pyrogram."""
    if not os.path.exists(video_path):
        print(f"❌ File not found: {video_path}")
        return

    file_size = os.path.getsize(video_path)
    video_name = os.path.basename(video_path)

    print("=" * 60)
    print(f"📁 File: {video_name}")
    print(f"💾 Size: {file_size / (1024*1024):.2f} MB")

    width, height, fps, duration = get_video_dimensions(video_path)
    if width and height:
        print(f"📺 Resolution: {width}x{height}")
        print(f"🎬 FPS: {fps}")
        print(f"⏱️  Duration: {format_duration(duration)}")

    print("=" * 60)
    print()

    def progress_callback(current, total):
        percentage = (current / total) * 100
        bar_length = 40
        filled_length = int(bar_length * current // total)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        print(f"\r📤 Progress: [{bar}] {percentage:.1f}% ({current/1024/1024:.2f}/{total/1024/1024:.2f} MB)", end="", flush=True)

    upload_type = "video"

    with app:
        try:
            if width is None or height is None:
                print("⚠️ Could not detect video dimensions. Uploading as document...")
                upload_type = "document"

                app.send_document(
                    chat_id=CHAT_ID,
                    document=video_path,
                    progress=progress_callback
                )
            else:
                app.send_video(
                    chat_id=CHAT_ID,
                    video=video_path,
                    width=width,
                    height=height,
                    supports_streaming=True,
                    progress=progress_callback
                )

        except Exception as e:
            print(f"\n❌ Upload failed: {e}")
            return

    print("\n✅ Upload finished!\n")
    log_upload(video_path, file_size, width, height, fps, duration, upload_type)

if __name__ == "__main__":
    video_file = r"C:\Users\Xing\Desktop\Twitter\myvideo.mp4"
    upload_video(video_file)

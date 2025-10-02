import yt_dlp
import os
import re
import json
from datetime import datetime

# Create folders to store downloaded videos and data
DOWNLOAD_FOLDER = os.path.join(os.getcwd(), "videos")
DATA_FOLDER = os.path.join(os.getcwd(), "data")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)

# Path to log file in data folder
LOG_FILE = os.path.join(DATA_FOLDER, "download_log.log")

# Path to your FFmpeg binary (optional, only if not in PATH)
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"  # change if needed

def get_next_number():
    """Find the highest numbered video and return the next number"""
    if not os.path.exists(DOWNLOAD_FOLDER):
        return 1
    
    files = os.listdir(DOWNLOAD_FOLDER)
    numbers = []
    
    # Extract numbers from filenames that match pattern like "01-", "02-", etc.
    for file in files:
        match = re.match(r'^(\d+)-', file)
        if match:
            numbers.append(int(match.group(1)))
    
    # Return next number, or 1 if no numbered files exist
    return max(numbers) + 1 if numbers else 1

def load_log():
    """Load existing log file or create new one"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    return json.loads(content)
                return []
        except:
            return []
    return []

def save_log(log_data):
    """Save log data to file"""
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

def add_to_log(video_info, filename, url):
    """Add video information to log"""
    log_entry = {
        'number': get_next_number() - 1,  # Current number (already incremented)
        'filename': filename,
        'url': url,
        'title': video_info.get('title', 'Unknown'),
        'uploader': video_info.get('uploader', 'Unknown'),
        'uploader_id': video_info.get('uploader_id', 'Unknown'),  # Username/handle
        'username': video_info.get('uploader_id', 'Unknown'),  # X/Twitter username
        'upload_date': video_info.get('upload_date', 'Unknown'),
        'duration': video_info.get('duration', 0),
        'view_count': video_info.get('view_count', 0),
        'like_count': video_info.get('like_count', 0),
        'repost_count': video_info.get('repost_count', 0),
        'description': video_info.get('description', '')[:200],  # First 200 chars
        'resolution': f"{video_info.get('width', 0)}x{video_info.get('height', 0)}",
        'filesize': video_info.get('filesize', 0),
        'download_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    # Load existing log
    log = load_log()
    
    # Add new entry
    log.append(log_entry)
    
    # Save updated log
    save_log(log)
    
    print(f"📝 Added to log: {log_entry['title']} by @{log_entry['username']}")

def rename_downloaded_file(original_path):
    """Rename the downloaded file with sequential numbering"""
    if not os.path.exists(original_path):
        return
    
    # Get the directory and filename
    directory = os.path.dirname(original_path)
    filename = os.path.basename(original_path)
    
    # Check if file already has numbering pattern
    if re.match(r'^\d+-', filename):
        print(f"✅ File already numbered: {filename}")
        return original_path
    
    # Get next number and format it with leading zeros
    next_num = get_next_number()
    new_filename = f"{next_num:02d}-{filename}"
    new_path = os.path.join(directory, new_filename)
    
    # Rename the file
    os.rename(original_path, new_path)
    print(f"✅ Renamed to: {new_filename}")
    return new_path

# Options for yt-dlp
ydl_opts = {
    'cookiefile': 'config/twitter_cookies.txt',   # Use your exported cookies
    'format': 'bestvideo+bestaudio/best',  # Best video + audio
    'merge_output_format': 'mp4',          # Merge into mp4
    'ffmpeg_location': FFMPEG_PATH,        # Specify ffmpeg location
    'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),  # Save in videos folder
    'noplaylist': True,
    'quiet': False,
}

def download_x_video(url):
    print(f"⏳ Starting download from: {url}")
    downloaded_file = None
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info to get the filename
            info = ydl.extract_info(url, download=True)
            
            # Get the actual filename that was downloaded
            if 'requested_downloads' in info:
                downloaded_file = info['requested_downloads'][0]['filepath']
            else:
                # Fallback: construct filename from title
                title = info.get('title', 'video')
                downloaded_file = os.path.join(DOWNLOAD_FOLDER, f"{title}.mp4")
            
            print(f"✅ Download finished!")
            
            # Rename with sequential numbering
            if downloaded_file and os.path.exists(downloaded_file):
                new_path = rename_downloaded_file(downloaded_file)
                
                # Add to log
                final_filename = os.path.basename(new_path if new_path else downloaded_file)
                add_to_log(info, final_filename, url)
            
    except Exception as e:
        print(f"❌ Download failed: {e}")

if __name__ == "__main__":
    tweet_url = input("Enter X/Twitter URL: ").strip()
    if tweet_url:
        download_x_video(tweet_url)
    else:
        print("❌ Please enter a valid URL")
        
    #OLD
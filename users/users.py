import os
import json
from datetime import datetime

# Folder to store individual user logs
USERS_FOLDER = os.path.join(os.getcwd(), "users")
os.makedirs(USERS_FOLDER, exist_ok=True)

def get_user_file(user_id):
    """Return the path to a user's JSON log file."""
    return os.path.join(USERS_FOLDER, f"{user_id}.json")

def load_user_log(user_id):
    """Load user's log file, return empty list if not exist."""
    user_file = get_user_file(user_id)
    if os.path.exists(user_file):
        try:
            with open(user_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_user_log(user_id, log_data):
    """Save user's log to their file."""
    user_file = get_user_file(user_id)
    with open(user_file, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)

def log_user_action(user_id, username, url, status, content_type="unknown"):
    """
    Log an action for a user.
    - user_id: Telegram ID
    - username: Telegram username or full name
    - url: link input by user
    - status: "success" or "failed"
    - content_type: "video", "image", or "unknown"
    """
    log_entry = {
        "username": username,
        "url": url,
        "status": status,
        "content_type": content_type,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    log = load_user_log(user_id)
    log.append(log_entry)
    save_user_log(user_id, log)
    
    # Cleaner logging - only show essential info
    if status == "success":
        if content_type == "video":
            print(f"✅ Video downloaded from {url[:50]}...")
        elif content_type == "image":
            print(f"✅ Images downloaded from {url[:50]}...")
        else:
            print(f"✅ Content downloaded from {url[:50]}...")
    elif status == "invalid_input":
        print(f"⚠️ Invalid input from {username}: {url[:20]}...")
    else:
        # Don't log failed attempts for normal cases (no video in image URLs)
        if "No video could be found" not in str(url) and "Unsupported URL" not in str(url):
            print(f"❌ Download failed from {url[:50]}...")
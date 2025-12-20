"""
Web Uploader for Telegram
Handles uploading files from web interface to Telegram groups
"""

import os
import asyncio
import json
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

# Try to import pyrogram
try:
    from pyrogram import Client
    from pyrogram.errors import FloodWait
    PYROGRAM_AVAILABLE = True
except ImportError:
    print("Warning: Pyrogram not installed. Install with: pip install pyrogram")
    PYROGRAM_AVAILABLE = False

# Import from existing bot code
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config.settings import CHAT_ID, API_ID, API_HASH, BOT_TOKEN
    from utils.video_processor import VideoProcessor
    from utils.formatters import Formatter
    from config.paths import DOWNLOAD_FOLDER, IMAGES_FOLDER
except ImportError:
    # Default values for web interface
    CHAT_ID = -1001816303239  # Your group ID
    API_ID = 22268900
    API_HASH = "6764e4d6dd12108e82105f355c6309d8"
    BOT_TOKEN = "8396142955:AAHTFHGai_SNUAooPOzmyNG1Y-wp6G5IXNo"
    DOWNLOAD_FOLDER = "downloads/videos"
    IMAGES_FOLDER = "downloads/images"

class WebUploader:
    """Handle file uploads to Telegram from web interface"""
    
    def __init__(self):
        self.app = None
        self.is_connected = False
        self.session_file = "web_uploader.session"
        
    async def connect(self):
        """Connect to Telegram"""
        try:
            if not PYROGRAM_AVAILABLE:
                print("❌ Pyrogram not installed")
                return False
                
            # Create a minimal, clean client configuration
            # Using bot mode to avoid premium checks
            self.app = Client(
                name="bot_session",  # Simple name
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN,
                in_memory=False,  # Use file-based session
                workdir=Path(__file__).parent,
                sleep_threshold=30,
                no_updates=True,  # Don't handle updates
                takeout=False  # Disable takeout mode
            )
            
            # Start the client with minimal initialization
            await self.app.start()
            self.is_connected = True
            
            # Test connection
            try:
                me = await self.app.get_me()
                print(f"✅ Connected to Telegram as @{me.username}")
            except Exception as e:
                print(f"⚠️ Connected but get_me failed: {e}")
                
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect to Telegram: {e}")
            # Try to cleanup
            try:
                if self.app:
                    await self.app.stop()
            except:
                pass
            self.app = None
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from Telegram"""
        if self.app and self.is_connected:
            try:
                await self.app.stop()
                self.is_connected = False
                print("✅ Disconnected from Telegram")
            except Exception as e:
                print(f"❌ Error disconnecting: {e}")
    
    async def upload_file(self, filepath: str, caption: str = "") -> Dict[str, Any]:
        """Upload a single file to Telegram"""
        if not PYROGRAM_AVAILABLE:
            return {"success": False, "error": "Pyrogram not installed"}
            
        if not self.is_connected:
            if not await self.connect():
                return {"success": False, "error": "Failed to connect to Telegram"}
        
        try:
            if not os.path.exists(filepath):
                return {"success": False, "error": "File not found"}
            
            filename = os.path.basename(filepath)
            file_size = os.path.getsize(filepath)
            
            print(f"📤 Uploading: {filename} ({file_size / (1024*1024):.2f} MB)")
            
            # Determine file type
            is_video = filename.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm'))
            is_image = filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'))
            
            # Create a simple caption (max 1024 chars for Telegram)
            safe_caption = (caption or filename)[:1024]
            
            try:
                if is_video:
                    # Upload video with minimal parameters
                    message = await self.app.send_video(
                        chat_id=CHAT_ID,
                        video=filepath,
                        caption=safe_caption,
                        supports_streaming=True
                    )
                    print(f"✅ Video uploaded: {filename}")
                    
                elif is_image:
                    # Upload image
                    message = await self.app.send_photo(
                        chat_id=CHAT_ID,
                        photo=filepath,
                        caption=safe_caption
                    )
                    print(f"✅ Image uploaded: {filename}")
                    
                else:
                    # Upload as document
                    message = await self.app.send_document(
                        chat_id=CHAT_ID,
                        document=filepath,
                        caption=safe_caption
                    )
                    print(f"✅ Document uploaded: {filename}")
                    
            except Exception as upload_error:
                # If any upload method fails, try as document (most reliable)
                print(f"⚠️ Upload failed with primary method: {upload_error}")
                print(f"🔄 Trying as document...")
                try:
                    message = await self.app.send_document(
                        chat_id=CHAT_ID,
                        document=filepath,
                        caption=safe_caption
                    )
                    print(f"✅ Uploaded as document: {filename}")
                except Exception as doc_error:
                    print(f"❌ Document upload also failed: {doc_error}")
                    raise doc_error
            
            print(f"✅ Successfully uploaded: {filename}")
            
            return {
                "success": True,
                "filename": filename,
                "size_mb": file_size / (1024 * 1024),
                "type": "video" if is_video else "image" if is_image else "document",
                "message_id": message.id if hasattr(message, 'id') else None
            }
            
        except FloodWait as e:
            wait_time = e.value
            print(f"⚠️ Rate limited: waiting {wait_time} seconds")
            return {"success": False, "error": f"Rate limited: wait {wait_time}s", "wait_time": wait_time}
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Upload failed for {filepath}: {error_msg}")
            
            # Handle specific errors
            if "is_premium" in error_msg:
                error_msg = "Telegram API error. Try reconnecting."
            elif "File too large" in error_msg:
                error_msg = "File exceeds Telegram's size limit (max 2GB)."
            elif "invalid" in error_msg.lower():
                error_msg = "Invalid file format."
            
            return {"success": False, "error": error_msg}
    
    async def upload_multiple_files(self, filepaths: List[str]) -> Dict[str, Any]:
        """Upload multiple files to Telegram"""
        if not PYROGRAM_AVAILABLE:
            return {"success": False, "error": "Pyrogram not installed"}
            
        if not self.is_connected:
            if not await self.connect():
                return {"success": False, "error": "Failed to connect to Telegram"}
        
        results = []
        success_count = 0
        failed_count = 0
        total_size = 0
        
        print(f"📤 Starting batch upload of {len(filepaths)} files")
        
        for idx, filepath in enumerate(filepaths):
            try:
                print(f"📤 Uploading file {idx+1}/{len(filepaths)}: {os.path.basename(filepath)}")
                
                result = await self.upload_file(filepath)
                
                if result["success"]:
                    success_count += 1
                    total_size += result["size_mb"]
                    print(f"✅ Success: {result['filename']}")
                else:
                    failed_count += 1
                    print(f"❌ Failed: {result.get('error', 'Unknown error')}")
                
                results.append({
                    "filename": os.path.basename(filepath),
                    "success": result["success"],
                    "error": result.get("error"),
                    "size_mb": result.get("size_mb", 0),
                    "type": result.get("type", "unknown")
                })
                
                # Small delay between uploads to avoid rate limiting
                if idx < len(filepaths) - 1:
                    await asyncio.sleep(1)  # Reduced delay
                
            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                print(f"❌ Error uploading {filepath}: {error_msg}")
                results.append({
                    "filename": os.path.basename(filepath),
                    "success": False,
                    "error": error_msg
                })
        
        print(f"📊 Upload completed: {success_count} success, {failed_count} failed, total size: {total_size:.2f} MB")
        
        return {
            "success": success_count > 0,
            "total": len(filepaths),
            "success_count": success_count,
            "failed_count": failed_count,
            "total_size_mb": round(total_size, 2),
            "results": results
        }
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test Telegram connection"""
        try:
            if not PYROGRAM_AVAILABLE:
                return {"success": False, "error": "Pyrogram not installed"}
                
            if not self.is_connected:
                if not await self.connect():
                    return {"success": False, "error": "Failed to connect"}
            
            # Send a simple test message
            message = await self.app.send_message(
                chat_id=CHAT_ID,
                text="✅ Web Uploader Test - Connection Successful!"
            )
            
            return {
                "success": True,
                "message": "Connection test successful",
                "chat_id": CHAT_ID,
                "message_id": message.id if hasattr(message, 'id') else None
            }
            
        except Exception as e:
            error_msg = str(e)
            if "is_premium" in error_msg:
                error_msg = "Telegram API error. Check bot permissions and try reconnecting."
            return {"success": False, "error": error_msg}

# Global uploader instance
uploader = WebUploader()

async def upload_single_file(filepath: str, caption: str = "") -> Dict[str, Any]:
    """Upload single file helper"""
    return await uploader.upload_file(filepath, caption)

async def upload_multiple_files(filepaths: List[str]) -> Dict[str, Any]:
    """Upload multiple files helper"""
    return await uploader.upload_multiple_files(filepaths)

async def test_telegram_connection() -> Dict[str, Any]:
    """Test connection helper"""
    return await uploader.test_connection()

# Initialize on startup
async def initialize():
    """Initialize the uploader"""
    print("🔄 Initializing Telegram uploader...")
    try:
        await uploader.connect()
    except Exception as e:
        print(f"⚠️ Failed to initialize uploader: {e}")
        
async def initialize_uploader():
    """Initialize the uploader in background"""
    print("🔄 Initializing Telegram uploader...")
    try:
        await uploader.connect()
    except Exception as e:
        print(f"⚠️ Failed to initialize uploader: {e}")
        # Don't crash if Telegram connection fails
        


# Run initialization in background
# import asyncio
# try:
#     # Schedule initialization
#     asyncio.create_task(initialize())
# except:
#     # If no event loop, will initialize on first use
#     pass

#OLD
"""
X Video Downloader Web Interface
FastAPI backend for web-based X/Twitter downloader with Telegram upload
"""

import os
import asyncio
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

# Import your existing modules
import sys

# Private group chat ID
CHAT_ID = -1001816303239  

# Add parent directory to path to import existing modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from core.downloader import VideoDownloader
    from core.image_downloader import ImageDownloader
    from core.file_manager import FileManager
    from core.log_manager import LogManager
    from utils.url_extractor import URLExtractor
    from utils.formatters import Formatter
    from utils.video_processor import VideoProcessor
    from config.paths import DOWNLOAD_FOLDER, IMAGES_FOLDER, DATA_FOLDER
    from config.paths import setup_directories
    
    # Import web uploader
    from web_uploader import upload_single_file, upload_multiple_files, test_telegram_connection
    
except ImportError as e:
    print(f"Import error: {e}")
    print("Creating mock classes for development...")
    # Create mock classes for development
    class MockDownloader:
        @staticmethod
        def download(url, message=None):
            return [f"/downloads/video_{datetime.now().timestamp()}.mp4"], {}
    
    class MockImageDownloader:
        @staticmethod
        def download(url, message=None):
            return [f"/downloads/image_{datetime.now().timestamp()}.jpg"], {}
    
    VideoDownloader = MockDownloader
    ImageDownloader = MockImageDownloader
    
    class MockURLExtractor:
        @staticmethod
        def extract(text):
            # Simple URL extraction
            import re
            urls = re.findall(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\d\-_?=&.%#]*', text)
            return urls if urls else [text] if 'http' in text else []
    
    URLExtractor = MockURLExtractor
    
    class MockVideoProcessor:
        @staticmethod
        def get_resolution(filepath):
            return 1920, 1080
    
    VideoProcessor = MockVideoProcessor
    
    DOWNLOAD_FOLDER = "downloads/videos"
    IMAGES_FOLDER = "downloads/images"
    DATA_FOLDER = "downloads/data"
    
    # Mock upload functions for development
    async def upload_single_file(filepath: str, caption: str = ""):
        return {"success": True, "filename": os.path.basename(filepath), "size_mb": 10.5, "type": "video"}
    
    async def upload_multiple_files(filepaths: List[str]):
        return {
            "success": True,
            "total": len(filepaths),
            "success_count": len(filepaths),
            "failed_count": 0,
            "total_size_mb": len(filepaths) * 10.5,
            "results": [{"filename": os.path.basename(f), "success": True} for f in filepaths]
        }
    
    async def test_telegram_connection():
        return {"success": True, "message": "Test connection successful", "chat_id": -1000000000000}

# Setup directories
setup_directories()

# In-memory storage for tasks (in production, use Redis or database)
tasks: Dict[str, Any] = {}
active_connections: Dict[str, List[WebSocket]] = {}

def cleanup_old_tasks():
    """Remove tasks older than 24 hours"""
    current_time = datetime.now()
    to_delete = []
    
    for task_id, task in tasks.items():
        if task.get('start_time'):
            try:
                start_time = datetime.fromisoformat(task.get('start_time'))
                if (current_time - start_time).total_seconds() > 24 * 3600:  # 24 hours
                    to_delete.append(task_id)
            except:
                pass
    
    for task_id in to_delete:
        del tasks[task_id]

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI"""
    # Startup
    print("Starting up X Downloader Web...")
    
    # Create required directories
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    os.makedirs(IMAGES_FOLDER, exist_ok=True)
    os.makedirs(DATA_FOLDER, exist_ok=True)
    
    # Create template and static directories
    templates_dir.mkdir(exist_ok=True)
    static_dir.mkdir(exist_ok=True)
    
    # Don't initialize Telegram here - let it initialize on first use
    # This prevents startup errors
    
    yield
    
    # Shutdown
    print("Shutting down X Downloader Web...")
    cleanup_old_tasks()
    
    # Close all WebSocket connections
    for task_id, connections in list(active_connections.items()):
        for connection in connections:
            try:
                await connection.close()
            except:
                pass
        active_connections[task_id] = []

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="X Downloader Web",
    description="Web interface for downloading X/Twitter videos and images",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Templates
BASE_DIR = Path(__file__).parent
templates_dir = BASE_DIR / "templates"
static_dir = BASE_DIR / "static"

# Ensure template directory exists
templates_dir.mkdir(exist_ok=True)
static_dir.mkdir(exist_ok=True)

templates = Jinja2Templates(directory=str(templates_dir))

# Mount static files
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ==================== DATA MODELS ====================

class DownloadRequest(BaseModel):
    urls: List[str]
    content_type: str = "auto"  # auto, video, image
    quality: str = "best"  # best, high, medium

class UploadRequest(BaseModel):
    filenames: List[str]
    upload_mode: str = "mixed"  # mixed, videos_only, images_only
    delay: int = 2
    add_caption: bool = True

class SingleUploadRequest(BaseModel):
    filename: str
    caption: Optional[str] = None

class TaskStatus(BaseModel):
    task_id: str
    status: str  # pending, processing, completed, failed
    progress: float = 0.0
    total_urls: int = 0
    processed_urls: int = 0
    downloaded_files: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    total_size_mb: float = 0.0
    current_file: Optional[Dict[str, Any]] = None

class FileInfo(BaseModel):
    name: str
    path: str
    size_mb: float
    type: str
    created: str
    modified: str
    duration: Optional[float] = None
    resolution: Optional[str] = None

# ==================== API ROUTES ====================

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main page"""
    return templates.TemplateResponse("index.html", {"request": {}})

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    telegram_status = "disconnected"
    try:
        # Import here to avoid circular imports
        from web_uploader import uploader
        if uploader and uploader.is_connected:
            telegram_status = "connected"
    except:
        pass
    
    return {
        "status": "healthy",
        "version": "2.0.0",
        "telegram": telegram_status,
        "timestamp": datetime.now().isoformat(),
        "directories": {
            "downloads": DOWNLOAD_FOLDER,
            "images": IMAGES_FOLDER,
            "data": DATA_FOLDER
        }
    }

@app.post("/api/download/start")
async def start_download(request: DownloadRequest, background_tasks: BackgroundTasks):
    """Start a new download task"""
    # Validate URLs
    valid_urls = []
    for url in request.urls:
        extracted = URLExtractor.extract(url)
        if extracted:
            valid_urls.extend(extracted)
    
    if not valid_urls:
        raise HTTPException(status_code=400, detail="No valid URLs found")
    
    # Create task
    task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(tasks)}"
    task = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0.0,
        "total_urls": len(valid_urls),
        "processed_urls": 0,
        "downloaded_files": [],
        "errors": [],
        "start_time": datetime.now().isoformat(),
        "end_time": None,
        "total_size_mb": 0.0,
        "current_file": None
    }
    
    tasks[task_id] = task
    
    # Start background processing
    background_tasks.add_task(
        process_download_task,
        task_id,
        valid_urls,
        request.content_type,
        request.quality
    )
    
    return {
        "task_id": task_id,
        "message": f"Download started for {len(valid_urls)} URLs",
        "status_url": f"/api/tasks/{task_id}"
    }

@app.post("/api/upload/start")
async def start_upload(request: UploadRequest, background_tasks: BackgroundTasks):
    """Start uploading files to Telegram"""
    try:
        # Filter files based on upload mode
        filtered_files = []
        for filename in request.filenames:
            filepath = None
            
            # Search in both folders
            for folder in [DOWNLOAD_FOLDER, IMAGES_FOLDER]:
                test_path = os.path.join(folder, filename)
                if os.path.exists(test_path):
                    filepath = test_path
                    break
            
            if filepath:
                # Check if file matches upload mode
                is_video = filename.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm'))
                is_image = filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'))
                
                if request.upload_mode == "videos_only" and not is_video:
                    continue
                elif request.upload_mode == "images_only" and not is_image:
                    continue
                
                filtered_files.append(filepath)
        
        if not filtered_files:
            raise HTTPException(status_code=400, detail="No valid files found for upload")
        
        # Create upload task
        task_id = f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(tasks)}"
        
        task = {
            "task_id": task_id,
            "status": "pending",
            "progress": 0.0,
            "total_urls": len(filtered_files),  # Reuse field for files count
            "processed_urls": 0,
            "downloaded_files": [],
            "errors": [],
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "total_size_mb": 0.0,
            "current_file": None
        }
        
        tasks[task_id] = task
        
        # Start background upload
        background_tasks.add_task(
            process_upload_task,
            task_id,
            filtered_files,
            request.delay,
            request.add_caption
        )
        
        return {
            "task_id": task_id,
            "message": f"Upload started for {len(filtered_files)} files",
            "status_url": f"/api/tasks/{task_id}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload/single")
async def upload_single(request: SingleUploadRequest):
    """Upload a single file to Telegram"""
    try:
        filepath = None
        filename = request.filename
        original_filename = filename
        
        print(f"🔍 Searching for file: {filename}")
        
        # Search recursively in both folders
        search_folders = [DOWNLOAD_FOLDER, IMAGES_FOLDER]
        found_files = []
        
        for folder in search_folders:
            if os.path.exists(folder):
                print(f"🔍 Recursively searching in: {folder}")
                for root, dirs, files in os.walk(folder):
                    for file in files:
                        if file == filename or file.startswith(os.path.splitext(filename)[0]):
                            full_path = os.path.join(root, file)
                            found_files.append({
                                "path": full_path,
                                "name": file,
                                "folder": root
                            })
        
        print(f"✅ Found {len(found_files)} matching files")
        
        # Choose the best match
        if found_files:
            # Prioritize exact filename matches
            exact_matches = [f for f in found_files if f["name"] == filename]
            if exact_matches:
                filepath = exact_matches[0]["path"]
                filename = exact_matches[0]["name"]
                print(f"✅ Using exact match: {filepath}")
            else:
                # Use the first match
                filepath = found_files[0]["path"]
                filename = found_files[0]["name"]
                print(f"✅ Using partial match: {filepath}")
        
        if not filepath:
            print(f"❌ File not found: {original_filename}")
            
            # List all available files for debugging
            print("📂 Available files structure:")
            for folder in search_folders:
                if os.path.exists(folder):
                    print(f"\nIn {folder}:")
                    for root, dirs, files in os.walk(folder):
                        level = root.replace(folder, '').count(os.sep)
                        indent = ' ' * 2 * level
                        print(f"{indent}{os.path.basename(root)}/")
                        subindent = ' ' * 2 * (level + 1)
                        for file in files[:5]:  # Show first 5 files
                            print(f"{subindent}{file}")
                        if len(files) > 5:
                            print(f"{subindent}... and {len(files) - 5} more")
            
            raise HTTPException(status_code=404, detail=f"File not found: {original_filename}")
        
        # Upload the file
        print(f"📤 Attempting to upload: {filepath}")
        result = await upload_single_file(filepath, request.caption or "")
        
        if result["success"]:
            return {
                "success": True,
                "message": f"Uploaded {result['filename']}",
                "filename": result['filename'],
                "size_mb": result.get("size_mb", 0),
                "type": result.get("type", "unknown")
            }
        else:
            print(f"❌ Upload failed: {result.get('error')}")
            return {
                "success": False,
                "error": result.get("error", "Upload failed")
            }
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in upload_single: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload error: {str(e)}")

@app.get("/api/upload/debug-chat")
async def debug_chat_access():
    """Debug chat access - uses direct Telegram API calls"""
    import requests
    
    try:
        # First get bot info
        bot_token = "8396142955:AAHTFHGai_SNUAooPOzmyNG1Y-wp6G5IXNo"
        chat_id = "-1001816303239"
        
        # Get bot info
        bot_response = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe")
        bot_info = bot_response.json()
        
        # Get chat member info
        chat_response = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getChatMember",
            params={"chat_id": chat_id, "user_id": bot_info["result"]["id"]}
        )
        chat_info = chat_response.json()
        
        return {
            "success": True,
            "bot_info": bot_info,
            "chat_info": chat_info,
            "bot_token": bot_token[:10] + "..." + bot_token[-5:],  # Partial for security
            "chat_id": chat_id
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Check if bot token and chat ID are correct"
        }

@app.get("/api/upload/test-simple")
async def test_simple_upload():
    """Test simple upload with minimal Telegram API"""
    try:
        from web_uploader import upload_single_file
        
        # Test with a small file or create a test file
        test_files = []
        
        # Check for any existing files
        for folder in [DOWNLOAD_FOLDER, IMAGES_FOLDER]:
            if os.path.exists(folder):
                for root, dirs, files in os.walk(folder):
                    if files:
                        test_file = os.path.join(root, files[0])
                        test_files.append(test_file)
                        break
                if test_files:
                    break
        
        if not test_files:
            # Create a test file
            test_path = os.path.join(DATA_FOLDER, "test_upload.txt")
            with open(test_path, "w") as f:
                f.write("Test file for Telegram upload\n")
                f.write(f"Created at: {datetime.now().isoformat()}")
            test_files.append(test_path)
        
        # Try to upload the first test file
        result = await upload_single_file(test_files[0], "Test upload from X Downloader Web")
        
        return {
            "success": result["success"],
            "message": result.get("message", "Test completed"),
            "filename": result.get("filename"),
            "error": result.get("error")
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Test upload failed"
        }

@app.get("/api/upload/telegram-info")
async def get_telegram_info():
    """Get Telegram bot information"""
    try:
        from web_uploader import uploader
        
        if not uploader.is_connected:
            await uploader.connect()
        
        me = await uploader.app.get_me()
        bot_info = {
            "id": me.id,
            "username": me.username,
            "first_name": me.first_name,
            "is_bot": me.is_bot
        }
        
        # Try to get chat info
        try:
            chat = await uploader.app.get_chat(CHAT_ID)
            chat_info = {
                "id": chat.id,
                "title": getattr(chat, 'title', 'Private Chat'),
                "type": chat.type
            }
        except Exception as e:
            chat_info = {"error": str(e)}
        
        return {
            "success": True,
            "bot": bot_info,
            "chat": chat_info,
            "connected": uploader.is_connected
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "connected": False
        }
        


@app.get("/api/upload/test-connection")
async def test_upload_connection():
    """Test Telegram connection for uploads"""
    try:
        result = await test_telegram_connection()
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get task status"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return tasks[task_id]

@app.get("/api/tasks")
async def list_tasks(limit: int = 10):
    """List recent tasks"""
    task_list = list(tasks.values())
    task_list.sort(key=lambda x: x.get('start_time') or "", reverse=True)
    return task_list[:limit]

@app.get("/api/files")
async def list_files(file_type: Optional[str] = None, limit: int = 50):
    """List downloaded files"""
    files = []
    
    print(f"📁 Scanning for files in: {DOWNLOAD_FOLDER} and {IMAGES_FOLDER}")
    
    # Scan video folder
    if os.path.exists(DOWNLOAD_FOLDER):
        print(f"📁 Scanning videos in: {DOWNLOAD_FOLDER}")
        for filename in os.listdir(DOWNLOAD_FOLDER):
            if filename.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm')):
                filepath = os.path.join(DOWNLOAD_FOLDER, filename)
                if os.path.isfile(filepath):
                    stat = os.stat(filepath)
                    size_mb = stat.st_size / (1024 * 1024)
                    
                    files.append({
                        "name": filename,
                        "path": filepath,
                        "size_mb": round(size_mb, 2),
                        "type": "video",
                        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                    print(f"✅ Found video: {filename}")
    
    # Scan image folder
    if os.path.exists(IMAGES_FOLDER):
        print(f"📁 Scanning images in: {IMAGES_FOLDER}")
        for root, dirs, filenames in os.walk(IMAGES_FOLDER):
            for filename in filenames:
                if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp')):
                    filepath = os.path.join(root, filename)
                    if os.path.isfile(filepath):
                        stat = os.stat(filepath)
                        size_mb = stat.st_size / (1024 * 1024)
                        
                        files.append({
                            "name": filename,
                            "path": filepath,
                            "size_mb": round(size_mb, 2),
                            "type": "image",
                            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                        })
                        print(f"✅ Found image: {filename}")
    
    # Filter by type if specified
    if file_type in ["video", "image"]:
        files = [f for f in files if f["type"] == file_type]
    
    # Sort by modified time (newest first)
    files.sort(key=lambda x: x["modified"], reverse=True)
    
    print(f"📊 Total files found: {len(files)}")
    
    return files[:limit]

@app.get("/api/files/{filename}")
async def get_file_info(filename: str):
    """Get information about a specific file"""
    # Security check
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Search in both folders
    for folder in [DOWNLOAD_FOLDER, IMAGES_FOLDER]:
        filepath = os.path.join(folder, filename)
        if os.path.exists(filepath):
            stat = os.stat(filepath)
            size_mb = stat.st_size / (1024 * 1024)
            
            file_type = "video" if filename.lower().endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm')) else "image"
            
            info = {
                "name": filename,
                "path": filepath,
                "size_mb": round(size_mb, 2),
                "type": file_type,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "exists": True
            }
            
            if file_type == "video" and hasattr(VideoProcessor, 'get_resolution'):
                try:
                    width, height = VideoProcessor.get_resolution(filepath)
                    if width and height:
                        info["resolution"] = f"{width}x{height}"
                except:
                    pass
            
            return info
    
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download a file"""
    # Security check
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Search recursively in both folders
    for folder in [DOWNLOAD_FOLDER, IMAGES_FOLDER]:
        if os.path.exists(folder):
            for root, dirs, files in os.walk(folder):
                if filename in files:
                    filepath = os.path.join(root, filename)
                    print(f"✅ Found file for download: {filepath}")
                    return FileResponse(
                        path=filepath,
                        filename=filename,
                        media_type='application/octet-stream'
                    )
    
    print(f"❌ File not found for download: {filename}")
    raise HTTPException(status_code=404, detail="File not found")

@app.delete("/api/files/{filename}")
async def delete_file(filename: str):
    """Delete a downloaded file"""
    # Security check
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    deleted = False
    filepath_found = None
    
    # Try to delete from all subdirectories
    for folder in [DOWNLOAD_FOLDER, IMAGES_FOLDER]:
        if os.path.exists(folder):
            for root, dirs, files in os.walk(folder):
                if filename in files:
                    filepath = os.path.join(root, filename)
                    try:
                        os.remove(filepath)
                        deleted = True
                        filepath_found = filepath
                        print(f"✅ Deleted file: {filepath}")
                        break
                    except Exception as e:
                        print(f"❌ Error deleting {filepath}: {e}")
                        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")
            if deleted:
                break
    
    if not deleted:
        print(f"❌ File not found for deletion: {filename}")
        raise HTTPException(status_code=404, detail="File not found")
    
    return {
        "message": f"Deleted {filename}",
        "success": True,
        "path": filepath_found
    }

@app.get("/api/stats")
async def get_statistics():
    """Get download statistics"""
    try:
        from core.log_manager import LogManager
        stats = LogManager.get_stats()
        return {
            "total_downloads": stats.get('log_entries', 0),
            "total_videos": stats.get('actual_videos', 0),
            "synced": stats.get('synced', False),
            "log_data": stats.get('log_data', [])[:10]  # Last 10 entries
        }
    except:
        # Return mock stats if LogManager not available
        return {
            "total_downloads": 0,
            "total_videos": 0,
            "synced": True,
            "log_data": []
        }

@app.get("/api/system-info")
async def get_system_info():
    """Get system information"""
    try:
        import psutil
        import platform
        import time
        
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "uptime": psutil.boot_time()
        }
    except ImportError:
        import time
        import platform
        
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_percent": 10,
            "memory_percent": 50,
            "disk_usage": 60,
            "uptime": time.time() - 3600
        }

# WebSocket endpoints for real-time updates
@app.websocket("/ws/tasks/{task_id}")
async def websocket_task_endpoint(websocket: WebSocket, task_id: str):
    await websocket.accept()
    
    # Add connection to list
    if task_id not in active_connections:
        active_connections[task_id] = []
    active_connections[task_id].append(websocket)
    
    try:
        # Send initial status
        if task_id in tasks:
            await websocket.send_json(tasks[task_id])
        
        # Keep connection alive and send updates
        while True:
            # Just keep connection alive, updates are sent via notify_task_update
            await asyncio.sleep(10)
            await websocket.send_json({"type": "ping", "timestamp": datetime.now().isoformat()})
            
    except WebSocketDisconnect:
        # Remove connection
        if task_id in active_connections:
            if websocket in active_connections[task_id]:
                active_connections[task_id].remove(websocket)
            if not active_connections[task_id]:
                del active_connections[task_id]

# ==================== BACKGROUND TASKS ====================

async def process_download_task(task_id: str, urls: List[str], content_type: str, quality: str):
    """Process download in background"""
    if task_id not in tasks:
        return
    
    task = tasks[task_id]
    task["status"] = "processing"
    
    total_files = []
    total_size = 0.0
    
    for idx, url in enumerate(urls):
        try:
            # Update progress
            task["processed_urls"] = idx
            task["progress"] = (idx / len(urls)) * 100
            await notify_task_update(task_id)
            
            print(f"Processing URL {idx+1}/{len(urls)}: {url}")
            
            downloaded_files = []
            
            # Try video download first for auto or video mode
            if content_type in ["auto", "video"]:
                try:
                    video_paths, video_info = VideoDownloader.download(url)
                    if video_paths and isinstance(video_paths, list):
                        for vpath in video_paths:
                            if os.path.exists(vpath):
                                size_mb = os.path.getsize(vpath) / (1024 * 1024)
                                total_size += size_mb
                                
                                # Get video info
                                width, height = None, None
                                if hasattr(VideoProcessor, 'get_resolution'):
                                    try:
                                        width, height = VideoProcessor.get_resolution(vpath)
                                    except:
                                        pass
                                
                                resolution = f"{width}x{height}" if width and height else "Unknown"
                                
                                file_info = {
                                    "name": os.path.basename(vpath),
                                    "path": vpath,
                                    "size_mb": round(size_mb, 2),
                                    "type": "video",
                                    "resolution": resolution,
                                    "url": url
                                }
                                downloaded_files.append(file_info)
                                total_files.append(file_info)
                except Exception as e:
                    print(f"Video download failed for {url}: {e}")
                    if content_type == "video":  # Only add error if video was specifically requested
                        task["errors"].append({"url": url, "error": str(e)[:100]})
            
            # Try image download for auto or image mode
            if (content_type in ["auto", "image"]) and (not downloaded_files or content_type == "image"):
                try:
                    image_paths, image_info = ImageDownloader.download(url)
                    if image_paths and isinstance(image_paths, list):
                        for ipath in image_paths:
                            if os.path.exists(ipath):
                                size_mb = os.path.getsize(ipath) / (1024 * 1024)
                                total_size += size_mb
                                
                                file_info = {
                                    "name": os.path.basename(ipath),
                                    "path": ipath,
                                    "size_mb": round(size_mb, 2),
                                    "type": "image",
                                    "resolution": "Image",
                                    "url": url
                                }
                                downloaded_files.append(file_info)
                                total_files.append(file_info)
                except Exception as e:
                    print(f"Image download failed for {url}: {e}")
                    if content_type == "image":  # Only add error if image was specifically requested
                        task["errors"].append({"url": url, "error": str(e)[:100]})
            
            if not downloaded_files:
                task["errors"].append({"url": url, "error": "No content found"})
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"Error processing {url}: {e}")
            task["errors"].append({"url": url, "error": str(e)[:100]})
    
    # Update final status
    task["status"] = "completed"
    task["progress"] = 100
    task["processed_urls"] = len(urls)
    task["downloaded_files"] = total_files
    task["total_size_mb"] = round(total_size, 2)
    task["end_time"] = datetime.now().isoformat()
    
    await notify_task_update(task_id)
    print(f"Task {task_id} completed: {len(total_files)} files, {total_size:.2f} MB")

async def process_upload_task(task_id: str, filepaths: List[str], delay: int, add_caption: bool):
    """Process upload in background"""
    if task_id not in tasks:
        return
    
    task = tasks[task_id]
    task["status"] = "processing"
    
    try:
        # Upload files
        uploaded_files = []
        errors = []
        success_count = 0
        
        for idx, filepath in enumerate(filepaths):
            try:
                # Update progress
                task["processed_urls"] = idx
                task["progress"] = (idx / len(filepaths)) * 100
                task["current_file"] = {"name": os.path.basename(filepath), "progress": 0}
                await notify_task_update(task_id)
                
                # Upload the file
                result = await upload_single_file(filepath, f"Uploaded: {os.path.basename(filepath)}")
                
                if result["success"]:
                    success_count += 1
                    uploaded_files.append({
                        "name": os.path.basename(filepath),
                        "size_mb": result.get("size_mb", 0),
                        "type": result.get("type", "unknown")
                    })
                else:
                    errors.append({
                        "url": os.path.basename(filepath),
                        "error": result.get("error", "Unknown error")
                    })
                
                # Delay between uploads
                if idx < len(filepaths) - 1:
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                errors.append({
                    "url": os.path.basename(filepath),
                    "error": str(e)
                })
        
        # Update task status
        task["status"] = "completed" if success_count > 0 else "failed"
        task["processed_urls"] = len(filepaths)
        task["progress"] = 100
        task["current_file"] = None
        task["downloaded_files"] = uploaded_files
        task["errors"] = errors
        task["total_size_mb"] = sum(f["size_mb"] for f in uploaded_files)
        task["end_time"] = datetime.now().isoformat()
        
    except Exception as e:
        task["status"] = "failed"
        task["errors"] = [{"url": "Upload task", "error": str(e)}]
        task["end_time"] = datetime.now().isoformat()
    
    await notify_task_update(task_id)

async def notify_task_update(task_id: str):
    """Notify all WebSocket connections about task update"""
    if task_id in active_connections and task_id in tasks:
        for connection in active_connections[task_id]:
            try:
                await connection.send_json(tasks[task_id])
            except:
                # Remove broken connection
                if connection in active_connections[task_id]:
                    active_connections[task_id].remove(connection)

# ==================== MAIN ENTRY ====================

if __name__ == "__main__":
    uvicorn.run(
        "web_backend:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
    
    #OLD
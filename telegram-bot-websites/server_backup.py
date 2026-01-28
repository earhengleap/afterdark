#!/usr/bin/env python3
"""
Video Gallery Server
Serves videos from Telegram-Bot/videos folder
"""

import os
import json
import mimetypes
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, unquote
import sys

# Get the absolute path to the Telegram-Bot folder
TELEGRAM_BOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VIDEO_FOLDER = os.path.join(TELEGRAM_BOT_DIR, "videos")  # Absolute path to videos
PORT = 8080
API_PREFIX = "/api"
STATIC_FOLDER = os.path.dirname(__file__)  # Current directory

print("=" * 60)
print("🔍 Configuration:")
print(f"   Current directory: {os.getcwd()}")
print(f"   Script location: {__file__}")
print(f"   Telegram Bot dir: {TELEGRAM_BOT_DIR}")
print(f"   Video folder: {VIDEO_FOLDER}")
print(f"   Video folder exists: {os.path.exists(VIDEO_FOLDER)}")
print("=" * 60)

def is_video_file(filename):
    """Check if file is a video based on extension"""
    video_extensions = {
        '.mp4', '.mkv', '.avi', '.mov', '.webm', 
        '.flv', '.wmv', '.m4v', '.mpg', '.mpeg',
        '.3gp', '.ts', '.mts', '.m2ts'
    }
    filename_lower = filename.lower()
    return any(filename_lower.endswith(ext) for ext in video_extensions)

def scan_videos_directory():
    """Scan videos directory and return file info"""
    videos = []
    
    print(f"🔍 Scanning video folder: {VIDEO_FOLDER}")
    
    if not os.path.exists(VIDEO_FOLDER):
        print(f"❌ Video folder does not exist: {VIDEO_FOLDER}")
        return videos
    
    # List all files in directory
    try:
        files = os.listdir(VIDEO_FOLDER)
        print(f"📁 Found {len(files)} files in videos folder")
    except Exception as e:
        print(f"❌ Error listing directory: {e}")
        return videos
    
    video_count = 0
    for filename in files:
        filepath = os.path.join(VIDEO_FOLDER, filename)
        
        if os.path.isfile(filepath) and is_video_file(filename):
            try:
                stat = os.stat(filepath)
                
                # Get file modification time
                mtime = datetime.fromtimestamp(stat.st_mtime)
                
                # URL-encode filename for web access
                from urllib.parse import quote
                encoded_filename = quote(filename)
                
                video_info = {
                    "name": filename,
                    "encoded_name": encoded_filename,  # URL-encoded version
                    "path": f"/videos/{encoded_filename}",
                    "size": stat.st_size,
                    "modified": mtime.isoformat(),
                    "modified_display": mtime.strftime("%Y-%m-%d %H:%M:%S"),
                    "type": mimetypes.guess_type(filename)[0] or "video/mp4"
                }
                
                videos.append(video_info)
                video_count += 1
                
                if video_count <= 5:  # Show first 5 videos
                    print(f"   ✅ {filename[:50]}... ({stat.st_size / (1024*1024):.2f} MB)")
                
            except Exception as e:
                print(f"   ❌ Error reading {filename}: {e}")
    
    print(f"📊 Total videos found: {video_count}")
    if video_count > 5:
        print(f"   ... and {video_count - 5} more videos")
    
    # Sort by filename (numerical order for numbered files)
    def sort_key(x):
        name = x["name"]
        import re
        match = re.match(r'^(\d+)-', name)
        if match:
            return (int(match.group(1)), name)
        return (9999, name)  # Files without numbers go to end
    
    videos.sort(key=sort_key, reverse=True)  # Show newest first
    return videos

def generate_placeholder_thumbnail(filename):
    """Generate SVG placeholder for video thumbnail"""
    import hashlib
    
    # Create hash for consistent color
    hash_val = int(hashlib.md5(filename.encode()).hexdigest(), 16)
    hue = hash_val % 360
    
    # Clean filename for display
    display_name = filename[:25] + "..." if len(filename) > 25 else filename
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="400" height="225" viewBox="0 0 400 225">
        <defs>
            <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="hsl({hue}, 70%, 50%)"/>
                <stop offset="100%" stop-color="hsl({(hue + 30) % 360}, 70%, 30%)"/>
            </linearGradient>
        </defs>
        <rect width="400" height="225" fill="url(#bg)"/>
        <circle cx="200" cy="112" r="40" fill="rgba(255,255,255,0.2)"/>
        <path d="M180 97 L220 112 L180 127 Z" fill="white"/>
        <text x="200" y="165" text-anchor="middle" fill="white" 
              font-family="Arial, sans-serif" font-size="14" opacity="0.8">
            {display_name}
        </text>
    </svg>'''
    
    return svg

def find_video_file(encoded_filename):
    """Find video file by encoded filename - handles URL decoding and special characters"""
    # First try: URL-decode the filename
    decoded_filename = unquote(encoded_filename)
    
    # Try different possible file paths
    possible_paths = [
        os.path.join(VIDEO_FOLDER, decoded_filename),  # URL-decoded
        os.path.join(VIDEO_FOLDER, encoded_filename),  # URL-encoded (as sent)
    ]
    
    # Also try to match by cleaning up the filename
    import re
    cleaned_filename = re.sub(r'[^\w\s\-\.()\[\]{}@#&+!]', '_', decoded_filename)
    possible_paths.append(os.path.join(VIDEO_FOLDER, cleaned_filename))
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Last resort: search through all files
    try:
        for filename in os.listdir(VIDEO_FOLDER):
            filepath = os.path.join(VIDEO_FOLDER, filename)
            if os.path.isfile(filepath) and is_video_file(filename):
                # Compare cleaned versions
                cleaned1 = re.sub(r'[^\w\s\-\.]', '', decoded_filename.lower())
                cleaned2 = re.sub(r'[^\w\s\-\.]', '', filename.lower())
                if cleaned1 in cleaned2 or cleaned2 in cleaned1:
                    return filepath
                
                # Check if numbers match (for numbered files)
                match1 = re.search(r'^(\d+)-', decoded_filename)
                match2 = re.search(r'^(\d+)-', filename)
                if match1 and match2 and match1.group(1) == match2.group(1):
                    return filepath
    except Exception as e:
        print(f"Error searching for file: {e}")
    
    return None

class VideoGalleryHandler(BaseHTTPRequestHandler):
    """HTTP handler for video gallery with proper connection error handling"""
    
    def do_GET(self):
        """Handle GET requests"""
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            
            # API endpoints
            if path.startswith(f"{API_PREFIX}/videos"):
                self.handle_videos_api()
            elif path.startswith(f"{API_PREFIX}/thumbnail/"):
                self.handle_thumbnail_api(path)
            elif path.startswith(f"{API_PREFIX}/stats"):
                self.handle_stats_api()
            
            # Static files
            elif path == "/":
                self.serve_file("index.html")
            elif path.endswith((".css", ".js", ".html", ".ico")):
                filename = path[1:]  # Remove leading slash
                self.serve_file(filename)
            
            # Video files
            elif path.startswith("/videos/"):
                self.serve_video(path)
            
            # 404 for everything else
            else:
                print(f"404: {path}")
                self.send_error(404, f"File not found: {path}")
                
        except Exception as e:
            # Don't log connection errors as errors
            error_str = str(e)
            if "10053" not in error_str and "10054" not in error_str:
                print(f"❌ Error handling request: {e}")
                import traceback
                traceback.print_exc()
                try:
                    self.send_error(500, f"Internal server error: {str(e)}")
                except:
                    pass  # Connection already closed
            else:
                # Normal client disconnect before headers
                print(f"ℹ️  Client disconnected: {self.path}")
    
    def handle_videos_api(self):
        """Return list of videos in JSON format"""
        try:
            print("📋 API: Getting videos list...")
            videos = scan_videos_directory()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            
            response = json.dumps(videos, indent=2, default=str)
            self.wfile.write(response.encode('utf-8'))
            print(f"✅ API: Returned {len(videos)} videos")
            
        except Exception as e:
            print(f"❌ Error in videos API: {e}")
            import traceback
            traceback.print_exc()
            self.send_error(500, f"Error scanning videos: {str(e)}")
    
    def handle_thumbnail_api(self, path):
        """Generate or serve video thumbnail"""
        try:
            # Extract video filename from path
            encoded_filename = path.split("/thumbnail/")[-1]
            
            # Find the actual file
            video_path = find_video_file(encoded_filename)
            
            if not video_path:
                print(f"❌ Thumbnail: Video not found: {encoded_filename}")
                placeholder_svg = generate_placeholder_thumbnail(encoded_filename)
                self.send_response(200)
                self.send_header('Content-Type', 'image/svg+xml')
                self.send_header('Cache-Control', 'public, max-age=3600')
                self.end_headers()
                self.wfile.write(placeholder_svg.encode('utf-8'))
                return
            
            # Generate SVG placeholder
            filename = os.path.basename(video_path)
            placeholder_svg = generate_placeholder_thumbnail(filename)
            
            self.send_response(200)
            self.send_header('Content-Type', 'image/svg+xml')
            self.send_header('Cache-Control', 'public, max-age=3600')
            self.end_headers()
            
            self.wfile.write(placeholder_svg.encode('utf-8'))
            
        except Exception as e:
            print(f"❌ Error in thumbnail API: {e}")
            self.send_error(500, f"Error generating thumbnail: {str(e)}")
    
    def handle_stats_api(self):
        """Return server statistics"""
        try:
            videos = scan_videos_directory()
            total_size = sum(v["size"] for v in videos)
            
            stats = {
                "total_videos": len(videos),
                "total_size": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "last_updated": datetime.now().isoformat(),
                "server_info": {
                    "video_folder": VIDEO_FOLDER,
                    "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "videos_found": len(videos)
                }
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            response = json.dumps(stats, indent=2, default=str)
            self.wfile.write(response.encode('utf-8'))
            
        except Exception as e:
            print(f"❌ Error in stats API: {e}")
            self.send_error(500, f"Error getting stats: {str(e)}")
    
    def serve_file(self, filepath):
        """Serve static file"""
        try:
            full_path = os.path.join(STATIC_FOLDER, filepath)
            
            if not os.path.exists(full_path):
                print(f"❌ Static file not found: {filepath}")
                self.send_error(404, f"File not found: {filepath}")
                return
            
            # Determine MIME type
            mime_type, _ = mimetypes.guess_type(filepath)
            if not mime_type:
                if filepath.endswith(".js"):
                    mime_type = "application/javascript"
                elif filepath.endswith(".css"):
                    mime_type = "text/css"
                elif filepath.endswith(".html"):
                    mime_type = "text/html"
                elif filepath.endswith(".ico"):
                    mime_type = "image/x-icon"
                else:
                    mime_type = "application/octet-stream"
            
            with open(full_path, 'rb') as f:
                content = f.read()
            
            self.send_response(200)
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(content)
            
        except Exception as e:
            print(f"❌ Error serving file {filepath}: {e}")
            self.send_error(500, f"Error reading file: {str(e)}")
    
    def serve_video(self, path):
        """Serve video file with proper headers for streaming"""
        try:
            # Extract filename from path
            encoded_filename = path.split("/videos/")[-1]
            
            print(f"🎬 Serving video: {encoded_filename}")
            
            # Find the actual file
            video_path = find_video_file(encoded_filename)
            
            if not video_path:
                print(f"❌ Video not found: {encoded_filename}")
                self.send_error(404, f"Video not found: {encoded_filename}")
                return
            
            # Get file size
            file_size = os.path.getsize(video_path)
            
            # Get MIME type
            filename = os.path.basename(video_path)
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                mime_type = "video/mp4"
            
            # Check for Range header (video streaming)
            range_header = self.headers.get('Range')
            
            if range_header and range_header.startswith('bytes='):
                # Handle byte range requests
                self.serve_partial_video(video_path, range_header, file_size, mime_type)
            else:
                # Serve full video
                self.send_response(200)
                self.send_header('Content-Type', mime_type)
                self.send_header('Content-Length', str(file_size))
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Cache-Control', 'public, max-age=86400')
                self.end_headers()
                
                # Stream the video in chunks
                chunk_size = 1024 * 1024  # 1MB chunks
                try:
                    with open(video_path, 'rb') as f:
                        while True:
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                            try:
                                self.wfile.write(chunk)
                                self.wfile.flush()
                            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                                # Client disconnected - normal behavior
                                print(f"ℹ️  Client disconnected during video: {filename}")
                                break
                            except Exception as e:
                                print(f"⚠️  Error writing chunk: {e}")
                                break
                                
                except Exception as e:
                    print(f"❌ Error reading video file: {e}")
                    # Headers already sent, can't send error response
                    
        except Exception as e:
            # Don't log connection errors as errors
            error_str = str(e)
            if "10053" not in error_str and "10054" not in error_str:
                print(f"❌ Error serving video {path}: {e}")
                import traceback
                traceback.print_exc()
                try:
                    self.send_error(500, f"Error serving video: {str(e)}")
                except:
                    pass  # Connection already closed
            else:
                # Normal client disconnect
                print(f"ℹ️  Client disconnected before video headers: {path}")
    
    def serve_partial_video(self, filepath, range_header, file_size, mime_type):
        """Serve partial content for video streaming - with proper error handling"""
        try:
            # Parse range header
            range_spec = range_header[len('bytes='):]
            parts = range_spec.split('-')
            
            if len(parts) == 2:
                start_str, end_str = parts
                start = int(start_str) if start_str else 0
                end = int(end_str) if end_str else file_size - 1
            else:
                self.send_error(400, "Invalid range format")
                return
            
            if end >= file_size:
                end = file_size - 1
            
            if start > end or start < 0 or end >= file_size:
                self.send_error(416, "Requested Range Not Satisfiable")
                return
            
            content_length = end - start + 1
            
            self.send_response(206)  # Partial Content
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Length', str(content_length))
            self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Cache-Control', 'public, max-age=86400')
            self.end_headers()
            
            # Send requested chunk with proper error handling
            chunk_size = 1024 * 1024  # 1MB chunks
            try:
                with open(filepath, 'rb') as f:
                    f.seek(start)
                    remaining = content_length
                    
                    while remaining > 0:
                        chunk = f.read(min(chunk_size, remaining))
                        if not chunk:
                            break
                        try:
                            self.wfile.write(chunk)
                            self.wfile.flush()  # Ensure data is sent
                            remaining -= len(chunk)
                        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                            # Client disconnected - this is normal for video streaming
                            print(f"ℹ️  Client disconnected during streaming: {os.path.basename(filepath)}")
                            break
                        except Exception as e:
                            # Log other unexpected errors
                            print(f"⚠️  Unexpected error during streaming: {e}")
                            break
                            
            except FileNotFoundError:
                print(f"❌ Video file not found: {filepath}")
                # Don't send error response since headers already sent
                return
            except Exception as e:
                print(f"❌ Error reading video file: {e}")
                # Headers already sent, can't send error response
                
        except Exception as e:
            # Only log if it's not a connection-related error
            error_str = str(e)
            if "10053" not in error_str and "10054" not in error_str:
                print(f"❌ Error in serve_partial_video: {e}")
                import traceback
                traceback.print_exc()
                try:
                    self.send_error(500, f"Error serving video: {str(e)}")
                except:
                    pass
            else:
                # Normal client disconnect - minimal logging
                print(f"ℹ️  Client disconnected before partial video: {os.path.basename(filepath)}")
                # Try to send error, but ignore if connection is already closed
                try:
                    self.send_error(500, f"Error serving video: {str(e)}")
                except:
                    pass
    
    def log_message(self, format, *args):
        """Custom log format - suppress normal connection errors"""
        message = format % args
        
        # Skip logging for common client disconnects during video streaming
        if '500' in message and ('10053' in message or '10054' in message or 'An established connection' in message):
            # Don't log normal client disconnects as errors
            return
        
        if '404' in message or '500' in message:
            print(f"⚠️  {datetime.now().strftime('%H:%M:%S')} - {message}")
        elif '/api/' in message:
            # Reduced logging for API calls
            pass

def run_server():
    """Start the HTTP server"""
    # Check if video folder exists
    print("\n" + "=" * 60)
    print("🎬 VIDEO GALLERY SERVER")
    print("=" * 60)
    
    if not os.path.exists(VIDEO_FOLDER):
        print(f"❌ CRITICAL: Video folder not found!")
        print(f"   Expected: {VIDEO_FOLDER}")
        print(f"   Current dir: {os.getcwd()}")
        print("\n💡 SOLUTIONS:")
        print("   1. Make sure you're running from telegram-bot-websites/ folder")
        print("   2. Check that Telegram-Bot/videos folder exists")
        print("   3. Create symbolic link: mklink /D videos ..\\videos")
        return
    
    # Scan videos first
    print("\n🔍 Scanning for videos...")
    videos = scan_videos_directory()
    
    print(f"\n📊 SERVER STATUS:")
    print(f"   Port: {PORT}")
    print(f"   Video folder: {VIDEO_FOLDER}")
    print(f"   Videos found: {len(videos)}")
    print(f"   Web URL: http://localhost:{PORT}")
    
    if videos:
        print("\n📹 RECENT VIDEOS (last 10):")
        for i, video in enumerate(videos[:10], 1):
            size_mb = video['size'] / (1024 * 1024)
            name_display = video['name'][:40] + "..." if len(video['name']) > 40 else video['name']
            print(f"   {i:2d}. {name_display:43} ({size_mb:.1f} MB)")
        if len(videos) > 10:
            print(f"   ... and {len(videos) - 10} more videos")
    else:
        print("\n⚠️  No video files found!")
        print("   Supported formats: .mp4, .mkv, .avi, .mov, .webm, .flv, .wmv, .m4v")
        print(f"   Check folder: {VIDEO_FOLDER}")
    
    print("\n🚀 Starting server...")
    print("   Press Ctrl+C to stop")
    print("=" * 60 + "\n")
    
    # Initialize server
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, VideoGalleryHandler)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user.")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        httpd.server_close()

if __name__ == '__main__':
    # Add common MIME types
    mimetypes.add_type('video/mp4', '.mp4')
    mimetypes.add_type('video/x-matroska', '.mkv')
    mimetypes.add_type('video/x-msvideo', '.avi')
    mimetypes.add_type('video/quicktime', '.mov')
    mimetypes.add_type('video/webm', '.webm')
    mimetypes.add_type('video/x-flv', '.flv')
    mimetypes.add_type('video/x-ms-wmv', '.wmv')
    mimetypes.add_type('video/3gpp', '.3gp')
    mimetypes.add_type('video/mpeg', '.mpeg')
    mimetypes.add_type('video/mpeg', '.mpg')
    
    run_server()
"""
Video processing and metadata extraction
"""

import subprocess
import json
from typing import Tuple, Optional

class VideoProcessor:
    """Video processing and metadata extraction"""
    
    @staticmethod
    def get_dimensions(video_path: str) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[float]]:
        """Extract video dimensions and metadata using ffprobe"""
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,r_frame_rate,duration",
                "-of", "json",
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            info = json.loads(result.stdout)
            
            if 'streams' in info and info['streams']:
                stream = info['streams'][0]
                width = stream.get('width')
                height = stream.get('height')
                duration = float(stream.get('duration', 0))
                
                fps_str = stream.get('r_frame_rate', '0/1')
                if '/' in fps_str:
                    num, den = fps_str.split('/')
                    fps = int(num) / int(den) if int(den) != 0 else 0
                else:
                    fps = 0
                
                return width, height, int(fps), duration
            return None, None, None, None
        except Exception as e:
            print(f"⚠️ Error reading video: {e}")
            return None, None, None, None
    
    @staticmethod
    def get_resolution(path: str) -> Tuple[Optional[int], Optional[int]]:
        """Get width and height using ffprobe"""
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
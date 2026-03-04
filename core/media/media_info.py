"""
Media information extraction utilities
"""

import os
import subprocess
import json
from typing import Optional, Dict, Tuple
from core.logger import setup_logger

logger = setup_logger("MediaInfo")


class MediaInfo:
    """Extract detailed information from media files"""
    
    @staticmethod
    def get_video_info(file_path: str) -> Optional[Dict]:
        """
        Extract detailed video information using ffprobe
        
        Args:
            file_path: Path to video file
            
        Returns:
            Dictionary with video metadata or None
        """
        if not os.path.exists(file_path):
            return None
            
        try:
            # Try using ffprobe first (more accurate)
            from config.settings import FFMPEG_PATH
            ffprobe_path = FFMPEG_PATH.replace('ffmpeg.exe', 'ffprobe.exe') if 'ffmpeg.exe' in FFMPEG_PATH else 'ffprobe'
            
            cmd = [
                ffprobe_path,
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace', timeout=10)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return MediaInfo._parse_ffprobe_data(data, file_path)
        except Exception as e:
            logger.debug(f"ffprobe extraction failed: {e}")
        
        # Fallback to basic file info
        return MediaInfo._get_basic_info(file_path)
    
    @staticmethod
    def _parse_ffprobe_data(data: Dict, file_path: str) -> Dict:
        """Parse ffprobe JSON output"""
        info = {
            'filename': os.path.basename(file_path),
            'size': os.path.getsize(file_path),
            'format': None,
            'duration': None,
            'resolution': None,
            'width': None,
            'height': None,
            'codec': None,
            'bitrate': None,
            'fps': None
        }
        
        # Get format information
        if 'format' in data:
            fmt = data['format']
            info['format'] = fmt.get('format_name', '').upper()
            if 'duration' in fmt:
                try:
                    info['duration'] = float(fmt['duration'])
                except (ValueError, TypeError):
                    pass
            if 'bit_rate' in fmt:
                try:
                    info['bitrate'] = int(fmt['bit_rate'])
                except (ValueError, TypeError):
                    pass
        
        # Get video stream information
        if 'streams' in data:
            for stream in data['streams']:
                if stream.get('codec_type') == 'video':
                    info['width'] = stream.get('width')
                    info['height'] = stream.get('height')
                    if info['width'] and info['height']:
                        info['resolution'] = f"{info['width']}x{info['height']}"
                    
                    info['codec'] = stream.get('codec_name', '').upper()
                    
                    # Calculate FPS
                    if 'r_frame_rate' in stream:
                        try:
                            fps_str = stream['r_frame_rate']
                            if '/' in fps_str:
                                num, den = fps_str.split('/')
                                info['fps'] = round(float(num) / float(den), 2)
                        except (ValueError, ZeroDivisionError):
                            pass
                    break
        
        return info
    
    @staticmethod
    def _get_basic_info(file_path: str) -> Dict:
        """Get basic file information without ffprobe"""
        return {
            'filename': os.path.basename(file_path),
            'size': os.path.getsize(file_path),
            'format': os.path.splitext(file_path)[1].upper().replace('.', ''),
            'duration': None,
            'resolution': None,
            'width': None,
            'height': None,
            'codec': None,
            'bitrate': None,
            'fps': None
        }
    
    @staticmethod
    def format_duration(seconds: Optional[float]) -> str:
        """Format duration in seconds to human-readable format"""
        if seconds is None or seconds <= 0:
            return "Unknown"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"
    
    @staticmethod
    def format_quality(width: Optional[int], height: Optional[int]) -> str:
        """Get quality label from resolution"""
        if not height:
            return "Unknown"
        
        if height >= 2160:
            return "4K"
        elif height >= 1440:
            return "2K"
        elif height >= 1080:
            return "1080p (Full HD)"
        elif height >= 720:
            return "720p (HD)"
        elif height >= 480:
            return "480p (SD)"
        else:
            return f"{height}p"
    
    @staticmethod
    def format_bitrate(bitrate: Optional[int]) -> str:
        """Format bitrate to human-readable format"""
        if not bitrate:
            return "Unknown"
        
        # Convert to kbps or Mbps
        kbps = bitrate / 1000
        if kbps >= 1000:
            return f"{kbps/1000:.1f} Mbps"
        else:
            return f"{kbps:.0f} kbps"
    
    @staticmethod
    def create_caption(video_path: str, include_filename: bool = True) -> str:
        """
        Create a detailed caption for a video file
        
        Args:
            video_path: Path to video file
            include_filename: Whether to include filename in caption
            
        Returns:
            Formatted caption string
        """
        info = MediaInfo.get_video_info(video_path)
        if not info:
            return f"📹 {os.path.basename(video_path)}"
        
        caption_parts = []
        
        if include_filename:
            filename = info['filename']
            if len(filename) > 50:
                filename = filename[:47] + '...'
            caption_parts.append(f"📹 `{filename}`")
        
        # Quality and Resolution
        if info['width'] and info['height']:
            quality = MediaInfo.format_quality(info['width'], info['height'])
            caption_parts.append(f"🎬 {quality} ({info['resolution']})")
        
        # Duration
        if info['duration']:
            duration_str = MediaInfo.format_duration(info['duration'])
            caption_parts.append(f"⏱️ {duration_str}")
        
        # File size
        size_mb = info['size'] / (1024 * 1024)
        if size_mb >= 1024:
            caption_parts.append(f"💾 {size_mb/1024:.2f} GB")
        else:
            caption_parts.append(f"💾 {size_mb:.1f} MB")
        
        # Format/Codec
        if info['codec']:
            format_str = info['format'] if info['format'] else 'MP4'
            caption_parts.append(f"📦 {format_str} ({info['codec']})")
        elif info['format']:
            caption_parts.append(f"📦 {info['format']}")
        
        # FPS (optional, only if available)
        if info['fps'] and info['fps'] > 0:
            caption_parts.append(f"🎞️ {info['fps']} FPS")
        
        return "\n".join(caption_parts)

"""
X/Twitter Profile Media Scraper
Standalone script to fetch all videos and images from a specific profile
"""

import os
import re
import json
import time
import requests
import subprocess
import concurrent.futures
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from pathlib import Path
from urllib.parse import urlparse, unquote
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('profile_scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TwitterProfileScraper:
    """Scrape all videos and images from a Twitter/X profile"""
    
    def __init__(self, username: str):
        """
        Initialize scraper for a specific username
        
        Args:
            username: Twitter/X username without @ (e.g., 'ThaoAnh1010')
        """
        self.username = username.lstrip('@')
        self.base_url = f"https://x.com/{self.username}"
        self.nitter_url = f"https://nitter.net/{self.username}"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Create directories for downloads
        self.download_dir = Path(f"downloads/{self.username}")
        self.videos_dir = self.download_dir / "videos"
        self.images_dir = self.download_dir / "images"
        
        for directory in [self.download_dir, self.videos_dir, self.images_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized scraper for @{self.username}")
        logger.info(f"Download directory: {self.download_dir}")
    
    def scrape_profile_media(self, max_tweets: int = 100, use_nitter: bool = True) -> Dict[str, List[str]]:
        """
        Scrape all media URLs from profile
        
        Args:
            max_tweets: Maximum number of tweets to check
            use_nitter: Use nitter.net instead of x.com (recommended, no auth needed)
            
        Returns:
            Dictionary with 'video_urls' and 'image_urls' lists
        """
        logger.info(f"Starting to scrape media from @{self.username} (max: {max_tweets} tweets)")
        
        all_media_urls = {
            'video_urls': [],
            'image_urls': [],
            'tweet_urls': []
        }
        
        if use_nitter:
            media_urls = self._scrape_via_nitter(max_tweets)
        else:
            media_urls = self._scrape_via_twitter_api(max_tweets)
        
        if not media_urls['tweet_urls']:
            logger.warning("No tweet URLs found. Profile might be private or doesn't exist.")
            return all_media_urls
        
        # Process each tweet URL to extract media
        logger.info(f"Found {len(media_urls['tweet_urls'])} tweets. Extracting media...")
        
        for tweet_url in media_urls['tweet_urls']:
            try:
                tweet_media = self._extract_media_from_tweet(tweet_url)
                if tweet_media:
                    all_media_urls['video_urls'].extend(tweet_media.get('videos', []))
                    all_media_urls['image_urls'].extend(tweet_media.get('images', []))
                    
            except Exception as e:
                logger.error(f"Error processing tweet {tweet_url}: {e}")
                continue
        
        # Remove duplicates while preserving order
        all_media_urls['video_urls'] = list(dict.fromkeys(all_media_urls['video_urls']))
        all_media_urls['image_urls'] = list(dict.fromkeys(all_media_urls['image_urls']))
        
        logger.info(f"Scraping complete!")
        logger.info(f"Found {len(all_media_urls['video_urls'])} video URLs")
        logger.info(f"Found {len(all_media_urls['image_urls'])} image URLs")
        
        return all_media_urls
    
    def _scrape_via_nitter(self, max_tweets: int) -> Dict[str, List[str]]:
        """Scrape tweet URLs using nitter.net (no authentication needed)"""
        tweet_urls = []
        page = 1
        
        try:
            while len(tweet_urls) < max_tweets:
                # Try different nitter instances
                nitter_instances = [
                    f"https://nitter.net/{self.username}?page={page}",
                    f"https://nitter.it/{self.username}?page={page}",
                    f"https://nitter.unixfox.eu/{self.username}?page={page}"
                ]
                
                success = False
                for instance_url in nitter_instances:
                    try:
                        logger.info(f"Fetching page {page} from {instance_url}")
                        response = self.session.get(instance_url, timeout=30)
                        
                        if response.status_code == 200:
                            # Extract tweet links from HTML
                            tweet_patterns = [
                                r'href="/([^/]+)/status/(\d+)"',
                                r'https?://nitter[^/]+/[^/]+/status/\d+',
                                r'twitter\.com/[^/]+/status/\d+'
                            ]
                            
                            html_content = response.text
                            
                            # Method 1: Look for tweet links in href attributes
                            matches = re.findall(r'href="/([^/]+)/status/(\d+)"', html_content)
                            for username, tweet_id in matches:
                                tweet_url = f"https://x.com/{username}/status/{tweet_id}"
                                if tweet_url not in tweet_urls:
                                    tweet_urls.append(tweet_url)
                                    logger.debug(f"Found tweet: {tweet_url}")
                            
                            # Method 2: Look for full URLs
                            matches = re.findall(r'https?://(?:nitter\.(?:net|it)|twitter\.com)/[^/]+/status/\d+', html_content)
                            for url in matches:
                                # Convert nitter URLs to x.com URLs
                                if 'nitter' in url:
                                    url = url.replace('nitter.net', 'x.com').replace('nitter.it', 'x.com')
                                if url not in tweet_urls:
                                    tweet_urls.append(url)
                                    logger.debug(f"Found tweet: {url}")
                            
                            success = True
                            break
                            
                    except Exception as e:
                        logger.debug(f"Failed to fetch from {instance_url}: {e}")
                        continue
                
                if not success:
                    logger.warning(f"Could not fetch page {page}. Stopping.")
                    break
                
                # Check if we have enough tweets or reached the end
                if len(tweet_urls) >= max_tweets:
                    break
                
                # Check if we got new tweets on this page
                if page > 1 and len(tweet_urls) <= len(tweet_urls_before):
                    logger.info("No new tweets found on this page. Stopping.")
                    break
                
                tweet_urls_before = tweet_urls.copy()
                page += 1
                time.sleep(1)  # Rate limiting
                
        except Exception as e:
            logger.error(f"Error scraping via nitter: {e}")
        
        return {'tweet_urls': tweet_urls[:max_tweets]}
    
    def _scrape_via_twitter_api(self, max_tweets: int) -> Dict[str, List[str]]:
        """Alternative method using Twitter API (requires authentication)"""
        # This is a placeholder - you would need Twitter API credentials
        logger.warning("Twitter API method requires authentication. Using nitter instead.")
        return {'tweet_urls': []}
    
    def _extract_media_from_tweet(self, tweet_url: str) -> Dict[str, List[str]]:
        """
        Extract video and image URLs from a single tweet
        
        Returns:
            Dictionary with 'videos' and 'images' lists
        """
        tweet_media = {'videos': [], 'images': []}
        
        try:
            # Convert to nitter URL for easier parsing
            nitter_url = tweet_url.replace('x.com', 'nitter.net').replace('twitter.com', 'nitter.net')
            
            response = self.session.get(nitter_url, timeout=30)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch tweet: {tweet_url}")
                return tweet_media
            
            html_content = response.text
            
            # Extract video URLs
            video_patterns = [
                # MP4 videos
                r'(https?://[^"\'\s]+\.mp4(?:\?[^"\'\s]*)?)',
                # Video links in nitter
                r'data-url="(https?://[^"\']+video/[^"\']+)"',
                # Twitter video variants
                r'(https?://video\.twimg\.com/[^"\'\s]+)',
                # Extended video URLs
                r'(https?://[^"\'\s]*video/[^"\'\s]*\.mp4)',
            ]
            
            for pattern in video_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for video_url in matches:
                    # Clean and decode URL
                    video_url = unquote(video_url)
                    if video_url not in tweet_media['videos']:
                        tweet_media['videos'].append(video_url)
                        logger.debug(f"Found video URL: {video_url}")
            
            # Extract image URLs
            image_patterns = [
                # Twitter image URLs
                r'(https?://pbs\.twimg\.com/media/[^"\'\s]+\.(?:jpg|jpeg|png|webp))',
                # General image URLs in tweets
                r'(https?://[^"\'\s]+\.(?:jpg|jpeg|png|gif|webp|bmp)(?:\?[^"\'\s]*)?)',
                # Image links in nitter
                r'data-url="(https?://[^"\']+\.(?:jpg|jpeg|png|webp))"',
                # Extended image URLs
                r'<img[^>]+src="(https?://[^"\']+\.(?:jpg|jpeg|png|webp))"',
            ]
            
            for pattern in image_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for image_url in matches:
                    # Clean and decode URL
                    image_url = unquote(image_url)
                    if image_url not in tweet_media['images']:
                        tweet_media['images'].append(image_url)
                        logger.debug(f"Found image URL: {image_url}")
            
            # Try to extract from JSON-LD metadata
            json_ld_pattern = r'<script type="application/ld\+json">(.*?)</script>'
            json_matches = re.findall(json_ld_pattern, html_content, re.DOTALL)
            
            for json_str in json_matches:
                try:
                    data = json.loads(json_str)
                    # Look for video content
                    if isinstance(data, dict) and 'video' in data:
                        video_info = data.get('video', {})
                        if 'contentUrl' in video_info:
                            tweet_media['videos'].append(video_info['contentUrl'])
                    
                    # Look for image content
                    if isinstance(data, dict):
                        for key, value in data.items():
                            if isinstance(value, str) and value.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                                if value not in tweet_media['images']:
                                    tweet_media['images'].append(value)
                except:
                    pass
            
            logger.info(f"Extracted {len(tweet_media['videos'])} videos and {len(tweet_media['images'])} images from {tweet_url}")
            
        except Exception as e:
            logger.error(f"Error extracting media from {tweet_url}: {e}")
        
        return tweet_media
    
    def download_media(self, media_urls: Dict[str, List[str]], max_concurrent: int = 5) -> Dict[str, List[str]]:
        """
        Download all media files
        
        Args:
            media_urls: Dictionary with 'video_urls' and 'image_urls' lists
            max_concurrent: Maximum concurrent downloads
            
        Returns:
            Dictionary with paths to downloaded files
        """
        downloaded_files = {
            'videos': [],
            'images': []
        }
        
        total_media = len(media_urls['video_urls']) + len(media_urls['image_urls'])
        logger.info(f"Starting download of {total_media} media files")
        
        # Download videos
        if media_urls['video_urls']:
            logger.info(f"Downloading {len(media_urls['video_urls'])} videos...")
            video_files = self._download_batch(
                media_urls['video_urls'], 
                self.videos_dir, 
                ['mp4', 'mov', 'avi', 'mkv', 'webm'],
                max_concurrent
            )
            downloaded_files['videos'] = video_files
        
        # Download images
        if media_urls['image_urls']:
            logger.info(f"Downloading {len(media_urls['image_urls'])} images...")
            image_files = self._download_batch(
                media_urls['image_urls'],
                self.images_dir,
                ['jpg', 'jpeg', 'png', 'webp', 'gif', 'bmp'],
                max_concurrent
            )
            downloaded_files['images'] = image_files
        
        logger.info(f"Download complete: {len(downloaded_files['videos'])} videos, {len(downloaded_files['images'])} images")
        return downloaded_files
    
    def _download_batch(self, urls: List[str], save_dir: Path, 
                       allowed_extensions: List[str], max_concurrent: int) -> List[str]:
        """Download multiple files concurrently"""
        downloaded_files = []
        
        def download_single(url: str, idx: int) -> Optional[str]:
            """Download a single file"""
            try:
                # Generate filename from URL
                parsed_url = urlparse(url)
                filename = os.path.basename(parsed_url.path)
                
                if not filename:
                    # Create a filename based on URL hash and index
                    import hashlib
                    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
                    filename = f"media_{idx}_{url_hash}.mp4" if 'video' in url.lower() else f"media_{idx}_{url_hash}.jpg"
                
                # Ensure file extension is valid
                ext = filename.split('.')[-1].lower()
                if ext not in allowed_extensions:
                    # Determine extension from content type or URL
                    if any(video_ext in url.lower() for video_ext in ['video', 'mp4', 'mov']):
                        filename = f"{filename.split('.')[0]}.mp4"
                    else:
                        filename = f"{filename.split('.')[0]}.jpg"
                
                # Ensure unique filename
                counter = 1
                base_name = filename
                while (save_dir / filename).exists():
                    name, ext = os.path.splitext(base_name)
                    filename = f"{name}_{counter}{ext}"
                    counter += 1
                
                filepath = save_dir / filename
                
                # Download the file
                logger.info(f"Downloading {idx+1}/{len(urls)}: {filename}")
                
                response = self.session.get(url, stream=True, timeout=60)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                
                file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
                logger.info(f"Downloaded: {filename} ({file_size_mb:.2f} MB)")
                
                return str(filepath)
                
            except Exception as e:
                logger.error(f"Failed to download {url}: {e}")
                return None
        
        # Use ThreadPoolExecutor for concurrent downloads
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_url = {executor.submit(download_single, url, idx): url 
                           for idx, url in enumerate(urls)}
            
            for future in concurrent.futures.as_completed(future_to_url):
                result = future.result()
                if result:
                    downloaded_files.append(result)
        
        return downloaded_files
    
    def save_results(self, media_urls: Dict[str, List[str]], 
                    downloaded_files: Dict[str, List[str]]) -> None:
        """Save scraping results to JSON file"""
        results = {
            'username': self.username,
            'scraped_at': datetime.now().isoformat(),
            'media_urls': media_urls,
            'downloaded_files': downloaded_files,
            'statistics': {
                'total_video_urls': len(media_urls['video_urls']),
                'total_image_urls': len(media_urls['image_urls']),
                'videos_downloaded': len(downloaded_files['videos']),
                'images_downloaded': len(downloaded_files['images'])
            }
        }
        
        results_file = self.download_dir / f"{self.username}_results.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to: {results_file}")
    
    def generate_report(self) -> str:
        """Generate HTML report of downloaded media"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Twitter Media Scraper - @{self.username}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #1da1f2; color: white; padding: 20px; border-radius: 5px; }}
                .stats {{ background: #f5f8fa; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                .media-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }}
                .media-item {{ border: 1px solid #e1e8ed; border-radius: 5px; padding: 10px; }}
                .video {{ background: #e8f4f9; }}
                .image {{ background: #f9f0e8; }}
                .filename {{ font-weight: bold; margin-bottom: 10px; }}
                .preview {{ max-width: 100%; height: auto; }}
                video {{ max-width: 100%; height: auto; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Twitter Media Scraper</h1>
                <h2>@<a href="https://x.com/{self.username}" target="_blank">{self.username}</a></h2>
                <p>Scraped on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
        """
        
        # Count files
        video_files = list(self.videos_dir.glob("*"))
        image_files = list(self.images_dir.glob("*"))
        
        html_content += f"""
            <div class="stats">
                <h3>Statistics</h3>
                <p>Videos downloaded: {len(video_files)}</p>
                <p>Images downloaded: {len(image_files)}</p>
                <p>Total files: {len(video_files) + len(image_files)}</p>
            </div>
        """
        
        # Display videos
        if video_files:
            html_content += "<h3>Downloaded Videos</h3><div class='media-grid'>"
            for video_file in video_files[:50]:  # Limit to first 50
                rel_path = video_file.relative_to(self.download_dir)
                html_content += f"""
                    <div class="media-item video">
                        <div class="filename">{video_file.name}</div>
                        <video controls>
                            <source src="{rel_path}" type="video/mp4">
                            Your browser does not support the video tag.
                        </video>
                        <p>Size: {os.path.getsize(video_file) / (1024*1024):.2f} MB</p>
                    </div>
                """
            html_content += "</div>"
        
        # Display images
        if image_files:
            html_content += "<h3>Downloaded Images</h3><div class='media-grid'>"
            for image_file in image_files[:100]:  # Limit to first 100
                rel_path = image_file.relative_to(self.download_dir)
                html_content += f"""
                    <div class="media-item image">
                        <div class="filename">{image_file.name}</div>
                        <img src="{rel_path}" class="preview" loading="lazy">
                        <p>Size: {os.path.getsize(image_file) / (1024*1024):.2f} MB</p>
                    </div>
                """
            html_content += "</div>"
        
        html_content += """
        </body>
        </html>
        """
        
        report_file = self.download_dir / f"{self.username}_report.html"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML report generated: {report_file}")
        return str(report_file)


def main():
    """Main function to run the scraper"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape all videos and images from a Twitter/X profile')
    parser.add_argument('username', help='Twitter username (without @)')
    parser.add_argument('--max-tweets', type=int, default=50, help='Maximum tweets to check (default: 50)')
    parser.add_argument('--download', action='store_true', help='Download media files')
    parser.add_argument('--concurrent', type=int, default=3, help='Maximum concurrent downloads (default: 3)')
    parser.add_argument('--no-nitter', action='store_true', help='Do not use nitter.net (not recommended)')
    parser.add_argument('--report', action='store_true', help='Generate HTML report')
    
    args = parser.parse_args()
    
    # Create scraper instance
    scraper = TwitterProfileScraper(args.username)
    
    try:
        # Step 1: Scrape media URLs
        logger.info("=" * 60)
        logger.info(f"STARTING SCRAPING FOR @{args.username}")
        logger.info("=" * 60)
        
        media_urls = scraper.scrape_profile_media(
            max_tweets=args.max_tweets,
            use_nitter=not args.no_nitter
        )
        
        # Step 2: Download media if requested
        downloaded_files = {'videos': [], 'images': []}
        if args.download and (media_urls['video_urls'] or media_urls['image_urls']):
            downloaded_files = scraper.download_media(
                media_urls,
                max_concurrent=args.concurrent
            )
        
        # Step 3: Save results
        scraper.save_results(media_urls, downloaded_files)
        
        # Step 4: Generate report if requested
        if args.report:
            report_path = scraper.generate_report()
            logger.info(f"Open this file in browser to view report: {report_path}")
        
        # Summary
        logger.info("=" * 60)
        logger.info("SCRAPING COMPLETE!")
        logger.info(f"Username: @{args.username}")
        logger.info(f"Video URLs found: {len(media_urls['video_urls'])}")
        logger.info(f"Image URLs found: {len(media_urls['image_urls'])}")
        logger.info(f"Videos downloaded: {len(downloaded_files['videos'])}")
        logger.info(f"Images downloaded: {len(downloaded_files['images'])}")
        logger.info(f"Download directory: {scraper.download_dir}")
        logger.info("=" * 60)
        
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Example usage:
    # python profile_scraper.py ThaoAnh1010 --max-tweets 100 --download --report
    main()
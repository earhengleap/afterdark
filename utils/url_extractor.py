"""
URL extraction and validation utilities - FLEXIBLE VERSION
Handles URLs with no spaces, unlimited input, line breaks, and various formats
"""

import re
import requests
from typing import List, Optional

class URLExtractor:
    """Extract and validate URLs from text - SUPER FLEXIBLE"""
    
    @staticmethod
    def extract(text: str) -> List[str]:
        """
        Extract all URLs from text.
        """
        if not text:
            return []
            
        # Standard robust matching that also explicitly splits stuck-together "https://"
        url_pattern = re.compile(
            r"(?:https?://|www\.)[^\s<>]+?(?=(?:https?://|www\.|$|\s|<|>))", 
            re.IGNORECASE
        )
        found_urls = url_pattern.findall(text)
        
        # Clean up URLs
        cleaned_urls = []
        for url in found_urls:
            url = url.strip()
            
            # Remove trailing punctuation that's not part of the URL
            # Note: Do not remove valid URL chars (like closing parens if it opened one)
            url = re.sub(r'[,;:!?]+$', '', url)
            
            # If it's just 'www.', prepend 'http://'
            if url.lower().startswith('www.'):
                url = 'http://' + url
                
            if len(url) > 10 and '.' in url:
                cleaned_urls.append(url)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in cleaned_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls
    
    @staticmethod
    def extract_twitter_urls(text: str) -> List[str]:
        """
        Extract only Twitter/X URLs from text
        Handles URLs stuck together with no spaces
        """
        if not text:
            return []
        
        # Pattern specifically for Twitter/X URLs with lookahead
        twitter_pattern = re.compile(
            r'https?://(?:www\.)?(?:twitter\.com|x\.com)/[^\s]*?(?=https?://|$|\s)',
            re.IGNORECASE
        )
        
        found_urls = twitter_pattern.findall(text)
        
        # Clean up URLs
        cleaned_urls = []
        for url in found_urls:
            # Remove trailing punctuation
            url = re.sub(r'[,;.!?\)\]]+$', '', url)
            url = url.rstrip('"\'')
            
            # Remove any trailing 'https://' or 'http://'
            url = re.sub(r'https?://$', '', url)
            
            # Only include valid Twitter URLs
            if len(url) > 15:  # Minimum length for a Twitter URL
                cleaned_urls.append(url)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in cleaned_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls
    
    @staticmethod
    def split_concatenated_urls(text: str) -> List[str]:
        """
        Specifically handles URLs that are stuck together with no spaces
        
        Example:
        Input: "https://x.com/user1/status/123https://x.com/user2/status/456"
        Output: ['https://x.com/user1/status/123', 'https://x.com/user2/status/456']
        """
        if not text:
            return []
        
        # Split on 'https://' or 'http://' but keep it in the result
        parts = re.split(r'(https?://)', text)
        
        urls = []
        current_url = ""
        
        for part in parts:
            if part in ['https://', 'http://']:
                # If we have a current URL, save it
                if current_url and current_url.startswith(('http://', 'https://')):
                    urls.append(current_url.strip())
                # Start new URL
                current_url = part
            elif part:
                # Add to current URL
                current_url += part
        
        # Don't forget the last URL
        if current_url and current_url.startswith(('http://', 'https://')):
            urls.append(current_url.strip())
        
        # Clean URLs
        cleaned_urls = []
        for url in urls:
            # Remove trailing punctuation
            url = re.sub(r'[,;.!?\)\]]+$', '', url)
            url = url.rstrip('"\'')
            
            if len(url) > 10 and '.' in url:
                cleaned_urls.append(url)
        
        return cleaned_urls
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """
        Validate if a string is a proper URL
        """
        url_pattern = re.compile(
            r'^https?://'
            r'(?:[a-zA-Z0-9-]+\.)*'
            r'[a-zA-Z0-9-]+'
            r'\.[a-zA-Z]{2,}'
            r'(?::[0-9]+)?'
            r'(?:/.*)?$',
            re.IGNORECASE
        )
        return bool(url_pattern.match(url))
    
    @staticmethod
    def normalize_url(url: str) -> str:
        """
        Normalize Twitter/X URLs to a consistent format
        """
        # Convert twitter.com to x.com for consistency
        url = url.replace('twitter.com', 'x.com')
        
        # Remove tracking parameters
        url = re.sub(r'\?.*$', '', url)
        
        # Remove trailing slashes
        url = url.rstrip('/')
        
        return url
    
    @staticmethod
    def count_urls(text: str) -> int:
        """
        Count how many URLs are in the text
        """
        return len(URLExtractor.extract(text))
    
    @staticmethod
    def extract_with_line_breaks(text: str) -> List[str]:
        """
        Extract URLs from text with line breaks
        Each line can contain one or more URLs (even stuck together)
        
        Example input:
        https://x.com/user1/status/123
        https://x.com/user2/status/456https://x.com/user3/status/789
        https://x.com/user4/status/101
        """
        if not text:
            return []
        
        # Split by line breaks
        lines = text.split('\n')
        
        all_urls = []
        for line in lines:
            line = line.strip()
            if line:
                # Extract URLs from each line (handles concatenated URLs)
                urls = URLExtractor.extract(line)
                all_urls.extend(urls)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in all_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls

    @staticmethod
    def extract_videy_links(text: str) -> List[str]:
        """
        Extract cdn.videy.co links from text.
        """
        if not text:
            return []
        
        pattern = r'https?://cdn\.videy\.co/[^\s<>"]+'
        matches = re.findall(pattern, text)
        return list(dict.fromkeys(matches))

    @staticmethod
    def get_videy_link_from_x_tweet(x_url: str) -> Optional[str]:
        """
        Extract cdn.videy.co video link from X/Twitter tweet using fxtwitter API.
        Returns the videy URL if found, None otherwise.
        """
        try:
            tweet_id = x_url.split("/status/")[-1].split("?")[0]
            api_url = f"https://api.fxtwitter.com/status/{tweet_id}"
            
            response = requests.get(api_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                tweet_text = data.get("tweet", {}).get("text", "")
                videy_links = URLExtractor.extract_videy_links(tweet_text)
                return videy_links[0] if videy_links else None
        except Exception:
            pass
        return None
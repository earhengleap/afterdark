"""
URL extraction and validation utilities - FLEXIBLE VERSION
Handles URLs with no spaces, unlimited input, line breaks, and various formats
"""

import re
from typing import List

class URLExtractor:
    """Extract and validate URLs from text - SUPER FLEXIBLE"""
    
    @staticmethod
    def extract(text: str) -> List[str]:
        """
        Extract all URLs from text with maximum flexibility
        
        Features:
        - Handles URLs with NO SPACES between them
        - Supports line breaks (\n)
        - Removes trailing punctuation
        - Handles URLs with query parameters
        - No limit on number of URLs
        - Supports both x.com and twitter.com
        
        Example:
        Input: "https://x.com/user1/status/123https://x.com/user2/status/456"
        Output: ['https://x.com/user1/status/123', 'https://x.com/user2/status/456']
        """
        if not text:
            return []
        
        # Use regex pattern that finds ALL occurrences of URLs
        # This pattern matches URLs even when they're stuck together
        url_pattern = re.compile(
            r'https?://'  # http:// or https://
            r'(?:[a-zA-Z0-9-]+\.)*'  # subdomains (optional)
            r'[a-zA-Z0-9-]+'  # domain name
            r'\.[a-zA-Z]{2,}'  # TLD (.com, .net, etc)
            r'(?::[0-9]+)?'  # port (optional)
            r'(?:/[^\s]*?)?'  # path (optional, non-greedy)
            r'(?=https?://|\s|$)',  # Stop before next URL, whitespace, or end of string
            re.IGNORECASE
        )
        
        # Find all URLs using findall
        found_urls = url_pattern.findall(text)
        
        # If no URLs found with lookahead, try simpler pattern
        if not found_urls:
            # Fallback pattern for edge cases
            simple_pattern = re.compile(
                r'https?://[^\s]+',
                re.IGNORECASE
            )
            found_urls = simple_pattern.findall(text)
        
        # Clean up URLs
        cleaned_urls = []
        for url in found_urls:
            # Remove trailing punctuation that's not part of the URL
            url = re.sub(r'[,;.!?\)\]]+$', '', url)
            
            # Remove trailing quotes
            url = url.rstrip('"\'')
            
            # If URL ends with 'https://' (captured the start of next URL), remove it
            if url.endswith('https://') or url.endswith('http://'):
                url = re.sub(r'https?://$', '', url)
            
            # Validate that it's a reasonable URL
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
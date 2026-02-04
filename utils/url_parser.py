"""
URL parsing utilities for extracting information from social media URLs
"""

import re
from typing import Optional


def extract_twitter_username(url: str) -> Optional[str]:
    """
    Extract username from X/Twitter URL
    
    Args:
        url: Twitter or X URL
        
    Returns:
        Username with @ prefix, or None if not found
        
    Examples:
        >>> extract_twitter_username('https://twitter.com/elonmusk/status/123')
        '@elonmusk'
        >>> extract_twitter_username('https://x.com/username/status/456')
        '@username'
        >>> extract_twitter_username('https://x.com/user_name')
        '@user_name'
    """
    if not url:
        return None
    
    # Patterns to match Twitter/X URLs
    patterns = [
        r'(?:twitter\.com|x\.com)/([^/\?#]+)/status',  # With /status/
        r'(?:twitter\.com|x\.com)/([^/\?#]+)/?$',      # Direct profile
        r'(?:twitter\.com|x\.com)/([^/\?#]+)/.*'       # Any path after username
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            username = match.group(1)
            # Skip common paths that aren't usernames
            if username.lower() not in ['home', 'i', 'search', 'explore', 'notifications', 'messages', 'settings']:
                return f"@{username}" if not username.startswith('@') else username
    
    return None


def shorten_url(url: str, max_length: int = 50) -> str:
    """
    Shorten URL for display purposes
    
    Args:
        url: Full URL
        max_length: Maximum length of shortened URL
        
    Returns:
        Shortened URL with ellipsis if needed
    """
    if not url:
        return ""
    
    # Remove protocol
    display_url = url.replace('https://', '').replace('http://', '')
    
    # Truncate if too long
    if len(display_url) > max_length:
        return display_url[:max_length-3] + '...'
    
    return display_url

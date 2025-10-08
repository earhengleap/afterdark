"""
URL extraction and validation utilities
"""

import re
from typing import List

class URLExtractor:
    """Extract and validate URLs from text"""
    
    @staticmethod
    def extract(text: str) -> List[str]:
        """Extract all URLs from text"""
        text = text.replace('|', ' ')
        potential_urls = text.split()
        
        urls = []
        url_pattern = re.compile(r'https?://[^\s]+')
        
        for item in potential_urls:
            item = item.strip()
            if url_pattern.match(item):
                item = re.sub(r'[,;.!?\)\]]+$', '', item)
                urls.append(item)
        
        return urls
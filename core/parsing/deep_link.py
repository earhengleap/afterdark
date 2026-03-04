"""
Deep Link Helper Module
Handles URL encoding/decoding for Telegram deep linking
"""

import base64
from typing import Optional


class DeepLinkHelper:
    """Helper class for Telegram deep linking operations"""
    
    @staticmethod
    def encode_url(url: str) -> str:
        """
        Encode URL for deep link parameter
        
        Args:
            url: The URL to encode
            
        Returns:
            Encoded parameter string with 'dl_' prefix
        """
        encoded = base64.urlsafe_b64encode(url.encode()).decode()
        return f"dl_{encoded}"
    
    @staticmethod
    def decode_url(param: str) -> Optional[str]:
        """
        Decode URL from deep link parameter
        
        Args:
            param: The parameter from /start command
            
        Returns:
            Decoded URL or None if invalid
        """
        try:
            if param.startswith("dl_"):
                encoded = param[3:]
                return base64.urlsafe_b64decode(encoded).decode()
        except Exception:
            pass
        return None
    
    @staticmethod
    def generate_share_link(bot_username: str, url: Optional[str] = None) -> str:
        """
        Generate deep link for sharing
        
        Args:
            bot_username: The bot's username (without @)
            url: Optional URL to encode in the link
            
        Returns:
            Complete deep link URL
        """
        if url:
            param = DeepLinkHelper.encode_url(url)
            return f"https://t.me/{bot_username}?start={param}"
        else:
            return f"https://t.me/{bot_username}?start=share"

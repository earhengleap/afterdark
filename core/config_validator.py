"""
Configuration Validator - Validate environment and bot configuration
"""

import os
import logging
from typing import List, Tuple, Optional
from pathlib import Path

logger = logging.getLogger("AfterDark.ConfigValidator")


class ConfigValidator:
    """Validate bot configuration and environment"""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate_all(self) -> Tuple[bool, List[str], List[str]]:
        """
        Validate all configuration
        
        Returns:
            (is_valid, errors, warnings)
        """
        self.errors.clear()
        self.warnings.clear()
        
        self._validate_required_env_vars()
        self._validate_bot_credentials()
        self._validate_paths()
        self._validate_dependencies()
        
        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings
    
    def _validate_required_env_vars(self):
        """Check required environment variables"""
        from config.settings import BOT_TOKEN, API_ID, API_HASH
        
        if not BOT_TOKEN or BOT_TOKEN == "":
            self.errors.append("BOT_TOKEN is not set or empty")
        
        if not API_ID or API_ID == 0:
            self.errors.append("API_ID is not set or invalid")
        
        if not API_HASH or API_HASH == "":
            self.errors.append("API_HASH is not set or empty")
    
    def _validate_bot_credentials(self):
        """Validate bot credentials format"""
        from config.settings import BOT_TOKEN, API_ID, API_HASH
        
        # Validate BOT_TOKEN format (should be like 123456:ABC-DEF1234...)
        if BOT_TOKEN and ":" not in str(BOT_TOKEN):
            self.errors.append("BOT_TOKEN format appears invalid (should contain ':')")
        
        # Validate API_ID is numeric
        try:
            if API_ID:
                int(API_ID)
        except (ValueError, TypeError):
            self.errors.append("API_ID must be a valid integer")
        
        # Validate API_HASH is alphanumeric
        if API_HASH and not str(API_HASH).replace("_", "").isalnum():
            self.warnings.append("API_HASH contains unusual characters")
    
    def _validate_paths(self):
        """Validate required paths and directories"""
        from config.settings import COOKIE_FILE, FFMPEG_PATH
        
        # Check cookie file
        if COOKIE_FILE:
            cookie_path = Path(COOKIE_FILE)
            if not cookie_path.exists():
                self.warnings.append(f"Cookie file not found: {COOKIE_FILE}")
            elif not cookie_path.is_file():
                self.warnings.append(f"Cookie path is not a file: {COOKIE_FILE}")
        
        # Check FFmpeg (if specified)
        if FFMPEG_PATH:
            ffmpeg_path = Path(FFMPEG_PATH)
            if not ffmpeg_path.exists():
                self.warnings.append(
                    f"FFmpeg not found at: {FFMPEG_PATH}\n"
                    "Video processing may fail without FFmpeg"
                )
        
        # Check required directories will be created
        required_dirs = ['videos', 'images', 'logs', 'temp']
        for dir_name in required_dirs:
            dir_path = Path(dir_name)
            if not dir_path.exists():
                logger.debug(f"Directory will be created: {dir_name}")
    
    def _validate_dependencies(self):
        """Check if critical dependencies are installed"""
        critical_packages = [
            ('pyrogram', 'Pyrogram'),
            ('yt_dlp', 'yt-dlp'),
            ('asyncio', 'asyncio'),
        ]
        
        for module_name, display_name in critical_packages:
            try:
                __import__(module_name)
            except ImportError:
                self.errors.append(f"Critical dependency missing: {display_name}")
        
        # Check optional but recommended packages
        optional_packages = [
            ('psutil', 'psutil - for system monitoring'),
            ('aiofiles', 'aiofiles - for async file operations'),
        ]
        
        for module_name, display_name in optional_packages:
            try:
                __import__(module_name)
            except ImportError:
                self.warnings.append(f"Optional dependency missing: {display_name}")
    
    def print_validation_report(self, is_valid: bool, errors: List[str], warnings: List[str]):
        """Print a formatted validation report"""
        print("\n" + "=" * 60)
        
        if errors:
            print("\nâŒ ERRORS (must be fixed):")
            for i, error in enumerate(errors, 1):
                print(f"  {i}. {error}")
        
        if warnings:
            print("\nâš ï¸  WARNINGS (recommended to fix):")
            for i, warning in enumerate(warnings, 1):
                print(f"  {i}. {warning}")
        
        if is_valid and not warnings:
            print("\nâœ… Configuration is valid.")
        elif is_valid:
            print(f"\nâœ… Configuration is valid (with {len(warnings)} warnings)")
        else:
            print(f"\nâŒ Configuration is INVALID ({len(errors)} errors)")
        
        print("=" * 60 + "\n")


def validate_configuration(raise_on_error: bool = True) -> bool:
    """
    Validate bot configuration
    
    Args:
        raise_on_error: If True, raise ValueError on validation errors
    
    Returns:
        True if valid, False otherwise
    
    Raises:
        ValueError: If raise_on_error is True and validation fails
    """
    validator = ConfigValidator()
    is_valid, errors, warnings = validator.validate_all()
    
    # Log results
    if errors:
        for error in errors:
            logger.error(f"Configuration error: {error}")
    
    if warnings:
        for warning in warnings:
            logger.warning(f"Configuration warning: {warning}")
    
    if not is_valid and raise_on_error:
        error_msg = "\n".join([f"  - {e}" for e in errors])
        raise ValueError(f"Configuration validation failed:\n{error_msg}")
    
    return is_valid




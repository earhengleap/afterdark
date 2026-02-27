import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

os.makedirs("logs", exist_ok=True)

ENABLE_LOG_EMOJIS = False

class ProfessionalFormatter(logging.Formatter):
    """Logback/SLF4J style professional formatter"""
    
    COLORS = {
        'RESET': '\033[0m',
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    
    def __init__(self, use_color=True):
        super().__init__()
        self.use_color = use_color and sys.stdout.isatty()
    
    def format(self, record):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level = record.levelname
        name = record.name
        message = record.getMessage()
        
        if self.use_color:
            color = self.COLORS.get(level, self.COLORS['RESET'])
            reset = self.COLORS['RESET']
            formatted = f"{timestamp} | {color}{level:8s}{reset} | {name:20s} | {message}"
        else:
            formatted = f"{timestamp} | {level:8s} | {name:20s} | {message}"
        
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)
        
        return formatted


class FileFormatter(logging.Formatter):
    """File formatter with structured output"""
    
    def format(self, record):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level = record.levelname
        name = record.name
        message = record.getMessage()
        
        formatted = f"{timestamp} | {level:8s} | {name:20s} | {message}"
        
        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)
        
        return formatted


def setup_logger(name="XVideoBot", level=logging.INFO):
    """Setup and return a logger with console and file handlers"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if logger.handlers:
        return logger
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ProfessionalFormatter())
    logger.addHandler(console_handler)
    
    log_file = f"logs/bot_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(FileFormatter())
    logger.addHandler(file_handler)
    
    return logger

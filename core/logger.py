import logging
import sys
import os
import re
from logging.handlers import RotatingFileHandler
from datetime import datetime

os.makedirs("logs", exist_ok=True)

ENABLE_LOG_EMOJIS = False

class ColoredFormatter(logging.Formatter):
    """Custom formatter for colored console output"""
    
    GREY = "\x1b[38;20m"
    CYAN = "\x1b[36;20m"
    GREEN = "\x1b[32;20m"
    YELLOW = "\x1b[33;20m"
    RED = "\x1b[31;20m"
    BOLD_RED = "\x1b[31;1m"
    RESET = "\x1b[0m"
    
    BASE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s"
    DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
    LEVEL_COLORS = {
        logging.DEBUG: GREY,
        logging.INFO: GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: BOLD_RED,
    }

    def format(self, record):
        ts = datetime.fromtimestamp(record.created).strftime(self.DATE_FORMAT)
        level = f"{record.levelname:<8}"
        name = f"{record.name:<28}"
        msg = record.getMessage()
        level_color = self.LEVEL_COLORS.get(record.levelno, self.GREY)
        return (
            f"{self.GREY}{ts}{self.RESET} | "
            f"{level_color}{level}{self.RESET} | "
            f"{self.CYAN}{name}{self.RESET} | "
            f"{msg}"
        )


class PlainAlignedFormatter(logging.Formatter):
    """Aligned formatter for file logs without ANSI color codes."""

    ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    def format(self, record):
        text = super().format(record)
        return self.ANSI_RE.sub("", text)

def setup_logger(name="AfterDark", level=logging.INFO):
    """Setup and return a logger with console and file handlers"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if logger.handlers:
        return logger
    logger.propagate = False

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter())
    logger.addHandler(console_handler)

    log_file = f"logs/bot_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8'
    )
    file_handler.setFormatter(PlainAlignedFormatter())
    logger.addHandler(file_handler)

    return logger


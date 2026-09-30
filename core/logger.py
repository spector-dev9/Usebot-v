"""Logging configuration"""
import logging
import sys
from datetime import datetime
from Config.settings import Config

class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m", "INFO": "\033[32m", "WARNING": "\033[33m",
        "ERROR": "\033[31m", "CRITICAL": "\033[35m", "RESET": "\033[0m"
    }
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS["RESET"])
        original = record.levelname
        record.levelname = f"{color}{original}{self.COLORS['RESET']}"
        try:
            return super().format(record)
        finally:
            record.levelname = original

def setup_logger(name="Userbot"):
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO))
    if logger.handlers:
        return logger
    Config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(ColoredFormatter("%(levelname)s - %(message)s"))
    logfile = Config.LOGS_DIR / f"userbot_{datetime.now():%Y%m%d}.log"
    file_handler = logging.FileHandler(logfile, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger

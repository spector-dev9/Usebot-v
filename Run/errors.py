"""Error handling"""
import traceback
from datetime import datetime
from core.logger import setup_logger
logger = setup_logger(__name__)

class ErrorHandler:
    def __init__(self):
        self.error_log = []
        self.max_errors = 100
    def log_error(self, error, context=None):
        self.error_log.append({
            "timestamp": datetime.now(), "error": str(error),
            "type": type(error).__name__, "context": context,
            "traceback": traceback.format_exc()})
        if len(self.error_log) > self.max_errors:
            self.error_log.pop(0)
        logger.error(f"Error in {context}: {error}", exc_info=True)
    def get_recent_errors(self, count=10):
        return self.error_log[-count:]
    def clear_errors(self):
        self.error_log.clear()

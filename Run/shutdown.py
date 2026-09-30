"""Graceful shutdown handler"""
import signal
import sys
from core.logger import setup_logger
logger = setup_logger(__name__)

class ShutdownHandler:
    def __init__(self, runtime):
        self.runtime = runtime
        self.shutdown_initiated = False
    def setup_handlers(self):
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
    def _handle_signal(self, signum, frame):
        if not self.shutdown_initiated:
            self.shutdown_initiated = True
            logger.info(f"🛑 Received shutdown signal ({signum})")
            sys.exit(0)
    async def shutdown(self):
        try:
            await self.runtime.stop()
            await self.runtime.client.stop()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

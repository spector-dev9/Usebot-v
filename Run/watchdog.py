"""Watchdog"""
import asyncio
from core.logger import setup_logger
logger = setup_logger(__name__)

class Watchdog:
    def __init__(self, runtime):
        self.runtime = runtime
        self.running = False
        self.check_interval = 60
    async def start(self):
        self.running = True
        while self.running:
            await self._check()
            await asyncio.sleep(self.check_interval)
    async def _check(self):
        try:
            if not self.runtime.client.client.is_connected():
                await self.runtime.client.start()
        except Exception as e:
            logger.error(f"Watchdog check failed: {e}")
    def stop(self):
        self.running = False

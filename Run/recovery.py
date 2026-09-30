"""Recovery mechanisms"""
from core.logger import setup_logger
logger = setup_logger(__name__)

class Recovery:
    def __init__(self, runtime):
        self.runtime = runtime
    async def recover_from_disconnect(self):
        try:
            await self.runtime.client.client.connect()
            return True
        except Exception as e:
            logger.error(f"❌ Recovery failed: {e}")
            return False

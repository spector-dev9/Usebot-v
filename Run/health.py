"""Health monitoring"""
from datetime import datetime
from core.logger import setup_logger
logger = setup_logger(__name__)

class HealthMonitor:
    def __init__(self, runtime):
        self.runtime = runtime
        self.last_check = datetime.now()
        self.health_status = "healthy"
    async def check_health(self):
        try:
            if not self.runtime.client.client.is_connected():
                self.health_status = "disconnected"
                return False
            if self.runtime.state.status != "running":
                self.health_status = "not_running"
                return False
            self.health_status = "healthy"
            self.last_check = datetime.now()
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.health_status = "error"
            return False

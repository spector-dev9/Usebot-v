"""Main runtime controller"""
from core.logger import setup_logger
from .registry import PluginRegistry
from .state import BotState
logger = setup_logger(__name__)

class Runtime:
    def __init__(self, client):
        self.client = client
        self.state = BotState()
        self.registry = PluginRegistry(client)

    async def initialize(self):
        self.state.status = "initializing"
        modules, handlers = self.registry.load_all()
        self.client.plugin_registry = self.registry
        self.client.bot_state = self.state
        logger.info(f"✅ Runtime initialized with {modules} modules")
        return modules, handlers

    async def start(self):
        self.state.start()
        logger.info("▶️ Runtime started")

    async def stop(self):
        self.state.stop()
        logger.info("⏹ Runtime stopped")

    def get_status(self):
        return {"state": self.state.get_stats(), "registry": self.registry.get_stats()}

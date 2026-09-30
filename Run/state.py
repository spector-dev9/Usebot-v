"""Bot state management"""
from datetime import datetime

class BotState:
    def __init__(self):
        self.started_at = datetime.now()
        self.restart_count = 0
        self.command_count = 0
        self.error_count = 0
        self.status = "initializing"
        self._custom_data = {}

    def start(self):
        self.status = "running"
        self.started_at = datetime.now()
    def stop(self):
        self.status = "stopped"
    def increment_commands(self):
        self.command_count += 1
    def increment_errors(self):
        self.error_count += 1
    def get_uptime(self):
        return (datetime.now() - self.started_at).total_seconds()
    def set_data(self, key, value):
        self._custom_data[key] = value
    def get_data(self, key, default=None):
        return self._custom_data.get(key, default)
    def get_stats(self):
        return {"status": self.status, "uptime": self.get_uptime(),
                "commands": self.command_count, "errors": self.error_count,
                "restarts": self.restart_count, "started_at": self.started_at.isoformat()}

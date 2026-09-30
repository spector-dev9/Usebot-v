"""Module information storage"""
from datetime import datetime

class ModuleInfo:
    def __init__(self, name, path, category):
        self.name = name
        self.path = path
        self.category = category
        self.handlers = []
        self.enabled = True
        self.loaded_at = datetime.now()
        self.error_count = 0

    def add_handler(self, handler_name):
        self.handlers.append(handler_name)
    def disable(self):
        self.enabled = False
    def enable(self):
        self.enabled = True
    def __repr__(self):
        status = "enabled" if self.enabled else "disabled"
        return f"<Module {self.name} ({len(self.handlers)} handlers, {status})>"
    def to_dict(self):
        return {
            "name": self.name, "path": self.path, "category": self.category,
            "handlers": self.handlers, "enabled": self.enabled,
            "loaded_at": self.loaded_at.isoformat(), "error_count": self.error_count
        }

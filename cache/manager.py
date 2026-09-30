"""In-memory cache"""
from datetime import datetime, timedelta
class CacheManager:
    def __init__(self, default_ttl=3600):
        self.cache = {}
        self.default_ttl = default_ttl
    def set(self, key, value, ttl=None):
        self.cache[key] = {"value": value, "expires_at": datetime.now() + timedelta(seconds=ttl or self.default_ttl)}
    def get(self, key, default=None):
        if key not in self.cache: return default
        item = self.cache[key]
        if datetime.now() > item["expires_at"]:
            del self.cache[key]
            return default
        return item["value"]
    def delete(self, key): self.cache.pop(key, None)
    def clear(self): self.cache.clear()
    def cleanup_expired(self):
        now = datetime.now()
        for key in [k for k,v in self.cache.items() if now > v["expires_at"]]:
            del self.cache[key]

"""Formatters"""
from datetime import datetime
class Formatters:
    @staticmethod
    def format_size(bytes):
        for unit in ["B","KB","MB","GB","TB"]:
            if bytes < 1024.0: return f"{bytes:.2f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.2f} PB"
    @staticmethod
    def format_duration(seconds):
        if seconds < 1: return f"{seconds*1000:.0f}ms"
        if seconds < 60: return f"{seconds:.1f}s"
        if seconds < 3600: return f"{int(seconds//60)}m {int(seconds%60)}s"
        return f"{int(seconds//3600)}h {int((seconds%3600)//60)}m"
    @staticmethod
    def format_uptime(started_at):
        delta = datetime.now() - started_at
        days = delta.days
        hours, rem = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        parts = ([f"{days}d"] if days else []) + ([f"{hours}h"] if hours else []) + ([f"{minutes}m"] if minutes else [])
        if seconds or not parts: parts.append(f"{seconds}s")
        return " ".join(parts)
    @staticmethod
    def truncate(text, length=100, suffix="..."):
        return text if len(text) <= length else text[:length-len(suffix)] + suffix

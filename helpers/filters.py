"""Custom event filters"""
class Filters:
    @staticmethod
    def is_reply(event): return event.is_reply
    @staticmethod
    def has_media(event): return event.message.media is not None
    @staticmethod
    def is_private(event): return event.is_private
    @staticmethod
    def is_group(event): return event.is_group
    @staticmethod
    def is_channel(event): return event.is_channel
"""Helper utilities package."""
from .decorators import command, sudo_only

__all__ = ["command", "sudo_only"]
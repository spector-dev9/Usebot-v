"""Validation utilities"""
import re
class Validators:
    @staticmethod
    def is_valid_username(username):
        return bool(re.match(r"^[a-zA-Z0-9_]{5,32}$", username))
    @staticmethod
    def is_valid_user_id(user_id):
        return user_id.isdigit() and len(user_id) <= 10
    @staticmethod
    def is_valid_url(url):
        return bool(re.match(r"^https?://[^\s]+$", url))
    @staticmethod
    def extract_user_id(text):
        match = re.search(r"tg://user\?id=(\d+)", text)
        if match: return int(match.group(1))
        if text.isdigit(): return int(text)
        return None

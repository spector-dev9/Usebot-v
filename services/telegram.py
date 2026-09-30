"""Telegram service functions"""
from telethon import functions
class TelegramService:
    def __init__(self, client): self.client = client
    async def get_full_user(self, user_id):
        return await self.client(functions.users.GetFullUserRequest(user_id))
    async def get_chat_members_count(self, chat_id):
        chat = await self.client.get_entity(chat_id)
        full_chat = await self.client(functions.messages.GetFullChatRequest(chat))
        return full_chat.full_chat.participants_count

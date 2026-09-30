"""Decorators for command handlers and event listeners."""
import inspect
from functools import wraps
from Config.settings import Config
from core.logger import setup_logger
from helpers import animations
logger = setup_logger(__name__)
def command(pattern: str, description: str = "", category: str = None, action: str = "typing"):
    def decorator(func):
        @wraps(func)
        async def wrapper(event):
            try:
                if hasattr(event.client, "bot_state"): event.client.bot_state.increment_commands()
                async with animations.typing(event.client, event.chat_id, action): await func(event)
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                if hasattr(event.client, "bot_state"): event.client.bot_state.increment_errors()
                try:
                    from utils.messages import Messages
                    await event.reply(Messages.error(str(e)))
                except Exception: pass
        wrapper._is_handler = True; wrapper._raw_pattern = pattern
        wrapper._pattern = f"(?i)^\\{Config.CMD_PREFIX}{pattern}"
        wrapper._description = description; wrapper._command_name = pattern.split()[0] if pattern else pattern
        wrapper._docstring = inspect.getdoc(func) or ""; wrapper._category = category
        wrapper._sudo_only = getattr(func, "_sudo_only", False); return wrapper
    return decorator
def sudo_only(func):
    @wraps(func)
    async def wrapper(event):
        if Config.SUDO_USERS and event.sender_id not in Config.SUDO_USERS:
            await event.reply("⛔ **Access Denied** — sudo users only."); return
        await func(event)
    wrapper._sudo_only = True; return wrapper
def listener(event_builder):
    def decorator(func):
        @wraps(func)
        async def wrapper(event):
            try: await func(event)
            except Exception as e: logger.error(f"Error in listener {func.__name__}: {e}", exc_info=True)
        wrapper._is_listener = True; wrapper._event_builder = event_builder; wrapper._docstring = inspect.getdoc(func) or ""; return wrapper
    return decorator

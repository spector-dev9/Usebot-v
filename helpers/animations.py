"""Animations — typing / uploading / recording indicators for commands."""
import asyncio
from contextlib import asynccontextmanager
from core.logger import setup_logger
logger = setup_logger(__name__)
_state = {"enabled": True}
MIN_ACTION_TIME = 0.4
def enabled() -> bool: return _state["enabled"]
def set_enabled(value: bool) -> None: _state["enabled"] = bool(value)
@asynccontextmanager
async def typing(client, chat_id, action: str = "typing"):
    if not _state["enabled"]:
        yield; return
    try:
        async with client.action(chat_id, action): yield
    except Exception as e:
        logger.debug(f"action indicator failed: {e}"); yield
async def quick_typing(client, chat_id, seconds: float = MIN_ACTION_TIME):
    if not _state["enabled"]: return
    try:
        async with client.action(chat_id, "typing"): await asyncio.sleep(seconds)
    except Exception: pass

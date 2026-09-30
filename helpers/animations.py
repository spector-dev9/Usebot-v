"""Animations — typing indicators via a plain class context manager."""
import asyncio

from core.logger import setup_logger

logger = setup_logger(__name__)

_state = {"enabled": True}
MIN_ACTION_TIME = 0.4


def enabled() -> bool:
    return _state["enabled"]


def set_enabled(value: bool) -> None:
    _state["enabled"] = bool(value)


async def _keep_typing(client, chat_id, action: str):
    """Background loop — refreshes the action every 4 seconds."""
    while True:
        try:
            async with client.action(chat_id, action):
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.debug(f"keep_typing: {e}")
            await asyncio.sleep(1)


class _TypingCtx:
    """
    Plain async context manager.

    No @asynccontextmanager, no generator, no chance of
    'generator didn't stop after athrow()'.
    """

    __slots__ = ("client", "chat_id", "action", "task")

    def __init__(self, client, chat_id, action: str):
        self.client = client
        self.chat_id = chat_id
        self.action = action
        self.task = None

    async def __aenter__(self):
        if not _state["enabled"]:
            return self
        try:
            self.task = asyncio.create_task(
                _keep_typing(self.client, self.chat_id, self.action)
            )
        except Exception as e:
            logger.debug(f"typing start failed: {e}")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.task is not None:
            try:
                self.task.cancel()
                await self.task
            except BaseException:
                pass
            self.task = None
        # Always False → never suppress exceptions from the body
        return False


def typing(client, chat_id, action: str = "typing"):
    """
    Return a context manager that keeps the action indicator alive.

    Usage:
        async with typing(event.client, event.chat_id):
            await do_something()
    """
    return _TypingCtx(client, chat_id, action)


async def quick_typing(client, chat_id, seconds: float = MIN_ACTION_TIME):
    """Show typing for a fixed short delay."""
    if not _state["enabled"]:
        return
    try:
        async with client.action(chat_id, "typing"):
            await asyncio.sleep(seconds)
    except Exception:
        pass

#!/usr/bin/env python3
"""Telegram Userbot main entry point"""
import asyncio
import sys

from Config.settings import Config
from core.client import UserbotClient
from core.logger import setup_logger
from Run.runtime import Runtime
from Run.shutdown import ShutdownHandler
from database.migrations import run as run_migrations
from database.connection import dispose_engine

logger = setup_logger("Main")


async def main():
    print("""
    ╔══════════════════════════════════════╗
    ║     ZeroX Userbot v1.1.0          ║
    ║     Starting initialization...       ║
    ╚══════════════════════════════════════╝
    """)

    userbot = runtime = None
    try:
        logger.info("📋 Validating configuration...")
        Config.validate()

        logger.info("💾 Running DB migrations...")
        await run_migrations()

        logger.info("🔌 Creating Telegram client...")
        userbot = UserbotClient()

        logger.info("⚙️ Setting up runtime...")
        runtime = Runtime(userbot.client)
        ShutdownHandler(runtime).setup_handlers()

        logger.info("🔐 Authenticating...")
        await userbot.start()

        modules, handlers = await runtime.initialize()
        await runtime.start()

        logger.info(f"✅ Userbot started — modules: {modules}, handlers: {handlers}")
        await userbot.client.run_until_disconnected()

    except KeyboardInterrupt:
        logger.info("⏹ Stopped by user")
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        logger.critical(f"💥 Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if runtime:
            await runtime.stop()
        if userbot:
            await userbot.stop()
        try:
            await dispose_engine()
        except Exception:
            pass
        logger.info("👋 Goodbye!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
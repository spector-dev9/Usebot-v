# ZeroX 1.1.0

## Fixed

- Restored the missing `controller.py`, `games.py`, and `host.py`.
- Restored the missing `GameStat` and `HostedBot` database models.
- Fixed `DATABASE_URL` being overwritten in `Config.settings`.
- Added controller configuration variables.
- Made sudo protection fail closed when no sudo user is configured.
- Prevented command-prefix collisions such as `.pingfoo` matching `.ping`.
- Fixed module registry collisions between categories.
- Fixed module manager commands to work with category-qualified registry keys.
- Removed StringSession logging from the client so a session string cannot be written to logs.
- Fixed helper package exports.
- Added `.env.example`.
- Added an offline `verify.py` checker.
- Removed the duplicate `aiosqlite` dependency entry.

## Verified

- All Python files compile successfully.
- Plugin command/listener decorators were counted statically.
- Telethon API usage for `UserUpdate.online` and `TelegramClient.start()` was checked against current Telethon documentation.
- Live Telegram authentication and network/database connectivity still require running the project on the user's machine.

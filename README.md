# ZeroX Userbot

Modular Telegram userbot built with Telethon + SQLAlchemy (async SQLite).

## Features

- Plugin discovery and hot reload
- `.help`, module management, system status
- AFK, notes, filters, identity utilities
- Profile presets / DP archive
- Activity tracking
- Games and text utilities
- Optional controller bot for start/stop/restart/status/logs
- Optional hosted Telegram bots with a viva demo
- Async SQLAlchemy database

## Setup

1. Copy `.env.example` to `.env`.
2. Put your Telegram `API_ID`, `API_HASH`, and phone number in `.env`.
3. Install dependencies:

   `pip install -r requirements.txt`

4. Start ZeroX:

   `python main.py`

5. Optional controller:

   `python controller.py`

On first login, Telethon may ask for the login code and 2FA password.

## Security

- Never commit `.env` or `*.session`.
- `CONTROL_BOT_TOKEN` is a bot token and must stay secret.
- Hosted bot tokens are stored in the local database when using `.host`; protect `data/zerox.db`.
- `.export` intentionally excludes secrets and runtime data.
- `.exportfull` includes secrets/session/database and should only be used when you understand the risk.

## Core commands

- `.help`
- `.help all`
- `.ping`
- `.status`
- `.modules`
- `.commands`
- `.restart` (sudo)
- `.shutdown` (sudo)
- `.modload [category]` (sudo)
- `.modreload <module>` (sudo)
- `.modreloadall` (sudo)
- `.modunload <module>` (sudo)
- `.moddel <module>` (sudo)
- `.export` (sudo)
- `.exportfull` (sudo)

## Controller commands

`/start`, `/stop`, `/restart`, `/status`, `/logs [n]`, `/help`

The controller is disabled unless `CONTROL_BOT_TOKEN` is configured.

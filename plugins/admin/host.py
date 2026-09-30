"""Host — run Telegram bot accounts inside ZeroX."""
import asyncio
import importlib
import inspect
import re
import sys
from functools import wraps

from telethon import Button, TelegramClient, events
from telethon.events import CallbackQuery, InlineQuery
from telethon.sessions import StringSession
from sqlalchemy import select

from Config.settings import Config
from core.logger import setup_logger
from database.connection import get_session
from database.models import HostedBot
from helpers.decorators import command, sudo_only
from utils.messages import Messages

logger = setup_logger(__name__)

_state = sys.modules.setdefault(
    "_zerox_hosted_state", type(sys)("_zerox_hosted_state")
)
if not hasattr(_state, "bots"):
    _state.bots = {}


# ──────────────────────────────────────────────────────────────────
#  SHARED MODULES
# ──────────────────────────────────────────────────────────────────

SHARED_MODULES = {
    "ping",
    "devtools", "texttools", "numtools", "fancy",
    "regex", "color", "emoji", "dictionary", "translate",
    "webtools", "crypto", "currency", "timezone",
    "wikipedia", "github", "facts", "qr", "mailcheck",
    "games", "sendonce",
}


def _find_module_key(registry, target_name: str):
    """
    Return the registry key for a shared module, tolerating
    'color', 'utilities.color', or 'plugins.utilities.color' styles.
    """
    if not registry or not getattr(registry, "modules", None):
        return None
    keys = list(registry.modules.keys())
    if target_name in keys:
        return target_name
    suffix = f".{target_name}"
    for k in keys:
        if k.endswith(suffix):
            return k
    return None


# ──────────────────────────────────────────────────────────────────
#  COMMAND CATALOG — UI only
# ──────────────────────────────────────────────────────────────────

CATEGORIES = {
    "games": {
        "emoji": "🎮",
        "title": "Games",
        "desc": "Play, compete, and challenge",
        "cmds": [
            ("/dice", "Roll a dice (native)"),
            ("/dart", "Throw a dart"),
            ("/bowl", "Roll a bowling ball"),
            ("/basket", "Shoot a basketball"),
            ("/football", "Kick a football"),
            ("/slot", "Spin the slots"),
            ("/8ball <question>", "Ask the magic 8-ball"),
            ("/coinflip", "Flip a coin"),
            ("/rps <rock|paper|scissors>", "Play rock-paper-scissors"),
            ("/duel", "Reply to someone to duel"),
            ("/trivia", "Start a quiz"),
            ("/gstats", "Your game stats"),
            ("/greset", "Reset your stats"),
        ],
    },
    "text": {
        "emoji": "📝",
        "title": "Text tools",
        "desc": "Transform, style, and analyze text",
        "cmds": [
            ("/upper <text>", "Uppercase"),
            ("/lower <text>", "Lowercase"),
            ("/titlecase <text>", "Title Case"),
            ("/swapcase <text>", "Swap case"),
            ("/capital <text>", "Capitalize"),
            ("/reverse <text>", "Reverse text"),
            ("/morse <text>", "Text → Morse"),
            ("/unmorse <morse>", "Morse → text"),
            ("/rot13 <text>", "ROT13 cipher"),
            ("/caesar <n> <text>", "Caesar cipher"),
            ("/count <text>", "Count chars/words/lines"),
            ("/sortlines <text>", "Sort lines"),
            ("/dedupe <text>", "Remove duplicate lines"),
            ("/shufflines <text>", "Shuffle lines"),
            ("/bold <text>", "Bold unicode"),
            ("/italic <text>", "Italic unicode"),
            ("/bolditalic <text>", "Bold-italic unicode"),
            ("/monospace <text>", "Monospace unicode"),
            ("/circle <text>", "Circled letters"),
            ("/fullwidth <text>", "Fullwidth text"),
            ("/smallcaps <text>", "Small caps"),
            ("/flip <text>", "Upside down text"),
            ("/strike <text>", "Strikethrough"),
            ("/underline <text>", "Underline"),
        ],
    },
    "regex": {
        "emoji": "🔍",
        "title": "Regex & extractors",
        "desc": "Pattern match and extract data from text",
        "cmds": [
            ("/retest /pat/ <text>", "Find all matches"),
            ("/repl /pat/ /new/ <text>", "Replace with regex"),
            ("/resplit /pat/ <text>", "Split by pattern"),
            ("/emails <text>", "Extract emails"),
            ("/urls <text>", "Extract URLs"),
            ("/phones <text>", "Extract phone numbers"),
            ("/ips <text>", "Extract IPv4 addresses"),
        ],
    },
    "numbers": {
        "emoji": "🔢",
        "title": "Numbers & colors",
        "desc": "Math, conversions, color tools",
        "cmds": [
            ("/roman <n>", "Decimal → Roman"),
            ("/unroman <roman>", "Roman → decimal"),
            ("/tobase <n> <base>", "Decimal → base N"),
            ("/frombase <v> <base>", "Base N → decimal"),
            ("/temp <v> [C|F|K]", "Temperature conversion"),
            ("/percent <p> <n>", "P% of N"),
            ("/bytes <v> <unit>", "Byte size conversion"),
            ("/aspect <w> <h>", "Simplify aspect ratio"),
            ("/prime <n>", "Prime check"),
            ("/factorial <n>", "Factorial"),
            ("/fib <n>", "Nth Fibonacci"),
            ("/color <#hex>", "Color info + swatch"),
            ("/rgb <r> <g> <b>", "RGB → hex"),
            ("/randomcolor", "Random color"),
            ("/palette <#hex>", "Color palette"),
            ("/gradient <#h1> <#h2> <n>", "Color gradient"),
        ],
    },
    "dev": {
        "emoji": "🧰",
        "title": "Dev & utilities",
        "desc": "Hashing, encoding, IDs, QR",
        "cmds": [
            ("/password [n]", "Random password"),
            ("/uuid", "Generate UUID4"),
            ("/token [n]", "Random hex token"),
            ("/hash <algo> <text>", "md5/sha1/sha256/sha512"),
            ("/b64enc <text>", "Base64 encode"),
            ("/b64dec <b64>", "Base64 decode"),
            ("/urlenc <text>", "URL encode"),
            ("/urldec <text>", "URL decode"),
            ("/bin <text>", "Text → binary"),
            ("/unbin <binary>", "Binary → text"),
            ("/hex <text>", "Text → hex"),
            ("/unhex <hex>", "Hex → text"),
            ("/epoch [ts]", "Unix time / convert"),
            ("/qr <text>", "Generate QR code"),
        ],
    },
    "web": {
        "emoji": "🌐",
        "title": "Web & search",
        "desc": "Translate, look up, fetch",
        "cmds": [
            ("/tr <lang> <text>", "Translate (auto-detect)"),
            ("/langs", "List language codes"),
            ("/wiki <title>", "Wikipedia summary"),
            ("/wikisearch <q>", "Search Wikipedia"),
            ("/randomwiki", "Random article"),
            ("/weather <city>", "Current weather"),
            ("/paste <text>", "Upload to paste service"),
            ("/shorten <url>", "Shorten URL"),
            ("/ipinfo [ip]", "IP geolocation"),
            ("/dns <domain>", "DNS lookup"),
            ("/httpget <url>", "Fetch URL body"),
            ("/ghuser <user>", "GitHub user info"),
            ("/ghrepo <o>/<r>", "GitHub repo info"),
            ("/ghsearch <q>", "Search GitHub repos"),
        ],
    },
    "finance": {
        "emoji": "💰",
        "title": "Crypto & currency",
        "desc": "Live prices and conversions",
        "cmds": [
            ("/price <coin>", "Crypto price (btc, eth, …)"),
            ("/top10", "Top 10 by market cap"),
            ("/trending", "Trending coins"),
            ("/convertcrypto <c> <amt>", "Crypto → USD"),
            ("/fx <src> <dst>", "FX rate (USD INR)"),
            ("/convert <amt> <src> <dst>", "Convert amount"),
            ("/rates <base>", "Common FX rates"),
        ],
    },
    "timefacts": {
        "emoji": "🕒",
        "title": "Time & facts",
        "desc": "Timezones, jokes, quotes, facts",
        "cmds": [
            ("/time [zone]", "Time in a zone"),
            ("/tz <src> to <dst>", "Convert now"),
            ("/timezones", "World clock"),
            ("/joke", "Random joke"),
            ("/quote", "Random quote"),
            ("/fact", "Useless fact"),
            ("/advice", "Random advice"),
            ("/catfact", "Cat fact"),
            ("/dogfact", "Dog fact"),
            ("/chucknorris", "Chuck Norris joke"),
        ],
    },
    "email": {
        "emoji": "📧",
        "title": "Email tools",
        "desc": "Domain and mail-server checks",
        "cmds": [
            ("/mailcheck <email>", "Full domain check"),
            ("/mx <domain>", "MX records"),
            ("/spf <domain>", "SPF record"),
            ("/dmarc <domain>", "DMARC record"),
            ("/disposable", "Disposable domains list"),
        ],
    },
}


# ──────────────────────────────────────────────────────────────────
#  PATTERN CONVERTER — \.cmd  →  /cmd
# ──────────────────────────────────────────────────────────────────

def _botify_pattern(original: str) -> str:
    """Turn `(?i)^\\.dice` into `(?i)^/dice(?:@\\w+)?$`."""
    prefix = "(?i)^\\."
    if original.startswith(prefix):
        rest = original[len(prefix):]
    else:
        rest = re.sub(r'^\(\?i\)\^\\?\.', '', original)

    m = re.match(r'^([a-zA-Z0-9_]+)(.*)$', rest)
    if not m:
        return f"(?i)^/(?:{rest})(?:@\\w+)?"

    cmd, tail = m.group(1), m.group(2)
    if tail:
        return f"(?i)^/{cmd}(?:@\\w+)?{tail}"
    return f"(?i)^/{cmd}(?:@\\w+)?$"


# ──────────────────────────────────────────────────────────────────
#  UI BUILDERS
# ──────────────────────────────────────────────────────────────────

def _welcome_text(bot_name: str, username: str) -> str:
    total_cats = len(CATEGORIES)
    total_cmds = sum(len(c["cmds"]) for c in CATEGORIES.values())
    return (
        f"👋 **Welcome to {bot_name}!**\n"
        f"`@{username}`\n\n"
        f"I'm a multi-purpose Telegram bot running on ZeroX.\n"
        f"**{total_cats} categories · {total_cmds}+ commands.**\n\n"
        f"**🚀 Quick start**\n"
        f"• `/ping` — check latency\n"
        f"• `/dice` — roll a dice\n"
        f"• `/joke` — random joke\n"
        f"• `/tr es hello` — translate to Spanish\n"
        f"• `/price btc` — Bitcoin price\n"
        f"• `/once` — test view-once\n\n"
        f"**📂 Browse categories below** or send `/help` for the full list.\n\n"
        f"_Commands use `/name <arg>` format (slash, not dot)._"
    )


def _home_buttons() -> list:
    keys = list(CATEGORIES.keys())
    rows = []
    for i in range(0, len(keys), 2):
        chunk = keys[i:i+2]
        row = []
        for k in chunk:
            c = CATEGORIES[k]
            label = f"{c['emoji']} {c['title']}"
            row.append(Button.inline(label, data=f"menu:cat:{k}"))
        rows.append(row)
    rows.append([
        Button.inline("📖 Full help", data="menu:help"),
        Button.inline("ℹ️ About", data="menu:about"),
    ])
    return rows


def _category_text(key: str) -> str:
    c = CATEGORIES[key]
    lines = [
        f"{c['emoji']} **{c['title']}**",
        f"_{c['desc']}_",
        "",
    ]
    for cmd, desc in c["cmds"]:
        lines.append(f"• `{cmd}` — {desc}")
    lines.append("")
    lines.append("_Tap ⌫ Back to return to the menu._")
    return "\n".join(lines)


def _back_buttons() -> list:
    return [[Button.inline("⌫ Back to menu", data="menu:home")]]


def _full_help_text() -> str:
    lines = [
        "📖 **Command Reference**",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        "All commands use `/` prefix (Telegram bot convention).",
        "",
    ]
    for key, c in CATEGORIES.items():
        lines.append(f"\n{c['emoji']} **{c['title']}**")
        for cmd, desc in c["cmds"]:
            lines.append(f"• `{cmd}` — {desc}")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("**Meta**")
    lines.append("• `/start` — open menu")
    lines.append("• `/help` — this reference")
    lines.append("• `/about` — bot info")
    lines.append("• `/ping` — latency check")
    lines.append("• `/once [view|5|10|30|60]` — test ephemeral media")
    return "\n".join(lines)


def _about_text(bot_name: str, username: str) -> str:
    return (
        f"ℹ️ **About {bot_name}**\n\n"
        f"• Username: `@{username}`\n"
        f"• Platform: ZeroX Userbot\n"
        f"• Categories: **{len(CATEGORIES)}**\n"
        f"• Commands: **{sum(len(c['cmds']) for c in CATEGORIES.values())}+**\n\n"
        f"This bot is hosted inside ZeroX and shares its utility "
        f"modules. Send `/help` to see everything it can do."
    )


# ──────────────────────────────────────────────────────────────────
#  MENU HANDLERS
# ──────────────────────────────────────────────────────────────────

def _register_menu(client, info):
    bot_name = info["name"]
    username = info["username"] or "bot"

    @client.on(events.NewMessage(pattern=r"^/start(?:@\w+)?(?:\s|$)"))
    async def cmd_start(event):
        await event.reply(
            _welcome_text(bot_name, username),
            buttons=_home_buttons(),
        )

    @client.on(events.NewMessage(pattern=r"^/menu(?:@\w+)?(?:\s|$)"))
    async def cmd_menu(event):
        await event.reply(
            _welcome_text(bot_name, username),
            buttons=_home_buttons(),
        )

    @client.on(events.NewMessage(pattern=r"^/help(?:@\w+)?(?:\s|$)"))
    async def cmd_help(event):
        text = _full_help_text()
        if len(text) > 4000:
            chunks = []
            current = ""
            for line in text.split("\n"):
                if len(current) + len(line) + 1 > 3800:
                    chunks.append(current)
                    current = ""
                current += line + "\n"
            if current:
                chunks.append(current)
            for chunk in chunks:
                await event.reply(chunk)
        else:
            await event.reply(text)

    @client.on(events.NewMessage(pattern=r"^/about(?:@\w+)?(?:\s|$)"))
    async def cmd_about(event):
        await event.reply(_about_text(bot_name, username))

    @client.on(events.CallbackQuery(pattern=r"^menu:"))
    async def menu_cb(event):
        try:
            parts = event.data.decode("utf-8").split(":")
        except Exception:
            await event.answer()
            return

        action = parts[1] if len(parts) > 1 else ""

        if action == "home":
            await event.edit(
                _welcome_text(bot_name, username),
                buttons=_home_buttons(),
            )
            await event.answer()
            return

        if action == "help":
            text = _full_help_text()
            if len(text) > 3800:
                text = text[:3700] + "\n\n_…truncated. Send `/help` for full._"
            await event.edit(text, buttons=_back_buttons())
            await event.answer()
            return

        if action == "about":
            await event.edit(
                _about_text(bot_name, username),
                buttons=_back_buttons(),
            )
            await event.answer()
            return

        if action == "cat" and len(parts) >= 3:
            key = parts[2]
            if key in CATEGORIES:
                await event.edit(
                    _category_text(key),
                    buttons=_back_buttons(),
                )
            await event.answer()
            return

        await event.answer()


# ──────────────────────────────────────────────────────────────────
#  SHARED MODULE PROXY
# ──────────────────────────────────────────────────────────────────

class _BotMessageProxy:
    def __init__(self, event):
        object.__setattr__(self, "_event", event)

    def __getattr__(self, name):
        return getattr(self._event, name)

    def __setattr__(self, name, value):
        setattr(self._event, name, value)

    async def edit(self, *args, **kwargs):
        kwargs.pop("file", None)
        return await self._event.reply(*args, **kwargs)

    async def delete(self, *args, **kwargs):
        try:
            return await self._event.delete(*args, **kwargs)
        except Exception:
            return None


def _wrap_handler_for_bot(func):
    @wraps(func)
    async def wrapper(event):
        if isinstance(event, (CallbackQuery.Event, InlineQuery.Event)):
            return await func(event)
        return await func(_BotMessageProxy(event))
    return wrapper


# ──────────────────────────────────────────────────────────────────
#  SHARED MODULE DISPATCHER
# ──────────────────────────────────────────────────────────────────

def _register_shared_modules(bot_client, registry):
    """
    Attach whitelisted userbot modules to a bot client.

    Tolerant of registry key conventions:
      - 'ping'
      - 'utilities.ping'
      - 'plugins.utilities.ping'
    """
    compiled_handlers = []

    loaded_keys = list(registry.modules.keys()) if registry else []
    logger.info(
        "🎁 shared: registry has %d key(s), sample: %s",
        len(loaded_keys),
        ", ".join(loaded_keys[:8]) + ("…" if len(loaded_keys) > 8 else ""),
    )

    matched = []
    missing = []

    for module_name in sorted(SHARED_MODULES):
        # ── Resolve registry key ──
        module_path = None

        if registry:
            key = _find_module_key(registry, module_name)
            if key:
                info = registry.modules.get(key)
                if info:
                    module_path = info.path
                    logger.debug(
                        "🎁 shared: %s resolved via key %s",
                        module_name, key,
                    )

        # ── Fallback — direct import by convention ──
        if module_path is None:
            for cat in ("utilities", "admin"):
                candidate = f"plugins.{cat}.{module_name}"
                try:
                    importlib.import_module(candidate)
                    module_path = candidate
                    logger.info(
                        "🎁 shared: %s not in registry, fallback %s",
                        module_name, candidate,
                    )
                    break
                except Exception:
                    continue

        if module_path is None:
            missing.append(module_name)
            continue

        # ── Import + register handlers ──
        try:
            module = importlib.import_module(module_path)
        except Exception as e:
            logger.warning("🎁 shared load %s failed: %s", module_name, e)
            missing.append(module_name)
            continue

        count = 0
        for name, obj in inspect.getmembers(module):
            if not callable(obj):
                continue
            try:
                if hasattr(obj, "_is_handler"):
                    bot_pattern = _botify_pattern(obj._pattern)
                    compiled = re.compile(bot_pattern)
                    compiled_handlers.append(
                        (compiled, _wrap_handler_for_bot(obj), module_name)
                    )
                    logger.debug(
                        "🎁 shared %s.%s → %s",
                        module_name, name, bot_pattern,
                    )
                    count += 1
                elif hasattr(obj, "_is_listener"):
                    bot_client.add_event_handler(
                        _wrap_handler_for_bot(obj),
                        obj._event_builder,
                    )
                    count += 1
            except Exception as e:
                logger.warning(
                    "🎁 shared register %s.%s failed: %s",
                    module_name, name, e,
                )

        if count:
            matched.append(module_name)
            logger.info("🎁 shared module %s → %d handler(s)",
                        module_name, count)

    total = len(compiled_handlers)
    logger.info(
        "🎁 shared total: %d command handler(s) from %d module(s)",
        total, len(matched),
    )
    if matched:
        logger.info("🎁 shared matched: %s", ", ".join(matched))
    if missing:
        logger.info("🎁 shared missing: %s", ", ".join(missing))

    if total == 0:
        return 0

    @bot_client.on(events.NewMessage(incoming=True))
    async def _shared_dispatcher(event):
        text = event.raw_text or ""
        if not text:
            return

        for rx, handler, module_name in compiled_handlers:
            m = rx.match(text)
            if m:
                try:
                    event.pattern_match = m
                except Exception:
                    pass
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(
                        "🎁 shared dispatch %s failed: %s",
                        module_name, e, exc_info=True,
                    )
                return

    return total


# ──────────────────────────────────────────────────────────────────
#  SPAWN / STOP
# ──────────────────────────────────────────────────────────────────

async def _spawn(token, registry=None):
    try:
        client = TelegramClient(
            StringSession(),
            Config.API_ID,
            Config.API_HASH,
            device_model="ZeroX Hosted Bot",
            system_version="Linux",
            app_version=Config.VERSION,
        )
        await client.start(bot_token=token)
        me = await client.get_me()
    except Exception as e:
        logger.error("hosted bot login failed: %s", e, exc_info=True)
        return False, f"Login failed: `{e}`", None

    if me.id in _state.bots:
        await client.disconnect()
        return False, f"`@{me.username}` is already running.", None

    info = {
        "id": me.id,
        "username": me.username or "",
        "name": me.first_name or me.username or "Bot",
    }

    _register_menu(client, info)
    shared_count = _register_shared_modules(client, registry)

    _state.bots[me.id] = client
    asyncio.create_task(client.run_until_disconnected())
    logger.info("🤖 Hosted @%s (id=%s) · %d shared handler(s)",
                info["username"], info["id"], shared_count)
    return True, (
        f"Started **{info['name']}** (`@{info['username']}`)\n"
        f"_Shared modules attached: {shared_count} handler(s)_"
    ), info


async def _stop(bot_id):
    client = _state.bots.get(bot_id)
    if not client:
        return False, "Not running."
    try:
        await client.disconnect()
    except Exception:
        pass
    _state.bots.pop(bot_id, None)
    return True, "Stopped."


async def _resolve_id(arg):
    if arg.startswith("@"):
        username = arg[1:]
        async with get_session() as session:
            result = await session.execute(
                select(HostedBot).where(HostedBot.username == username)
            )
            row = result.scalar_one_or_none()
        return row.bot_id if row else None
    return int(arg) if arg.lstrip("-").isdigit() else None


# ──────────────────────────────────────────────────────────────────
#  USERBOT COMMANDS
# ──────────────────────────────────────────────────────────────────

@command(r"host (.+)", "Host a Telegram bot by token")
@sudo_only
async def host_handler(event):
    token = event.pattern_match.group(1).strip()
    if ":" not in token or len(token) < 20:
        await event.edit(Messages.error("Invalid bot token."))
        return

    await event.edit(Messages.loading("Starting hosted bot…"))
    registry = getattr(event.client, "plugin_registry", None)
    ok, message, info = await _spawn(token, registry=registry)
    if not ok:
        await event.edit(Messages.error(message))
        return

    try:
        async with get_session() as session:
            result = await session.execute(
                select(HostedBot).where(HostedBot.bot_id == info["id"])
            )
            row = result.scalar_one_or_none()
            if row is None:
                session.add(HostedBot(
                    bot_id=info["id"], username=info["username"],
                    token=token, enabled=1,
                ))
            else:
                row.username = info["username"]
                row.token = token
                row.enabled = 1
    except Exception as e:
        await _stop(info["id"])
        await event.edit(Messages.error(f"Started bot could not be saved: `{e}`"))
        return

    await event.edit(Messages.success(
        f"{message}\n\n"
        f"Message `@{info['username']}` and send `/start` to see the menu."
    ))


@command(r"unhost (.+)", "Stop a hosted bot")
@sudo_only
async def unhost_handler(event):
    arg = event.pattern_match.group(1).strip()
    bot_id = await _resolve_id(arg)
    if bot_id is None:
        await event.edit(Messages.error("Hosted bot not found."))
        return

    ok, message = await _stop(bot_id)
    if not ok:
        await event.edit(Messages.error(message))
        return

    async with get_session() as session:
        result = await session.execute(
            select(HostedBot).where(HostedBot.bot_id == bot_id)
        )
        row = result.scalar_one_or_none()
        if row:
            row.enabled = 0

    await event.edit(Messages.success(f"Stopped `{bot_id}`."))


@command(r"hostdel (.+)", "Stop and forget a hosted bot")
@sudo_only
async def hostdel_handler(event):
    arg = event.pattern_match.group(1).strip()
    bot_id = await _resolve_id(arg)
    if bot_id is None:
        await event.edit(Messages.error("Hosted bot not found."))
        return

    await _stop(bot_id)
    async with get_session() as session:
        result = await session.execute(
            select(HostedBot).where(HostedBot.bot_id == bot_id)
        )
        row = result.scalar_one_or_none()
        if row:
            await session.delete(row)

    await event.edit(Messages.success(f"Deleted `{bot_id}`."))


@command("hosted", "List hosted bots")
@sudo_only
async def hosted_handler(event):
    async with get_session() as session:
        result = await session.execute(
            select(HostedBot).order_by(HostedBot.created_at.desc())
        )
        rows = result.scalars().all()

    if not rows:
        await event.edit(Messages.info("No hosted bots."))
        return

    lines = ["🤖 **Hosted bots**\n"]
    for row in rows:
        running = "🟢" if row.bot_id in _state.bots else "⚪"
        lines.append(
            f"{running} `@{row.username}` · id `{row.bot_id}` · "
            f"_{'on' if row.enabled else 'off'}_"
        )
    await event.edit("\n".join(lines))


@command("hostboot", "Respawn enabled hosted bots")
@sudo_only
async def hostboot_handler(event):
    await event.edit(Messages.loading("Booting hosted bots…"))
    registry = getattr(event.client, "plugin_registry", None)
    started, failed = await _boot_all(registry=registry)
    await event.edit(Messages.success(
        f"Started **{started}** · failed **{failed}**"
    ))


@command("sharedmods", "List modules available to hosted bots")
async def sharedmods_handler(event):
    await event.edit(
        "🎁 **Shared modules (available inside hosted bots)**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        + "\n".join(f"• `{m}`" for m in sorted(SHARED_MODULES))
        + "\n\n_These run on every hosted bot in addition to the menu UI._"
    )


@command("hostdiag", "Diagnose shared module wiring")
@sudo_only
async def hostdiag_handler(event):
    """Usage: `.hostdiag`"""
    reg = getattr(event.client, "plugin_registry", None)

    lines = ["🔬 **Host diagnostics**\n"]

    if reg is None:
        lines.append("❌ `client.plugin_registry` is **None**")
    else:
        loaded_keys = list(reg.modules.keys())
        lines.append(f"✅ registry: **{len(loaded_keys)}** module(s)")

        sample = ", ".join(f"`{k}`" for k in sorted(loaded_keys)[:12])
        lines.append(f"\n**Sample keys:**\n{sample}")

        found = []
        missing = []
        for name in sorted(SHARED_MODULES):
            key = _find_module_key(reg, name)
            if key:
                found.append(f"`{name}` → `{key}`")
            else:
                missing.append(name)

        lines.append(f"\n**Resolvable:** {len(found)}/{len(SHARED_MODULES)}")
        if found:
            lines.append("```\n" + "\n".join(found) + "\n```")
        if missing:
            lines.append(f"\n**Missing:** {len(missing)}")
            lines.append("```\n" + "\n".join(missing) + "\n```")

    lines.append("\n**Running hosted bots:**")
    if _state.bots:
        for bid in _state.bots:
            lines.append(f"• `{bid}`")
    else:
        lines.append("_(none)_")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3900] + "\n_…truncated_"
    await event.edit(text)


@command("hosthelp", "Hosted bot help")
async def hosthelp_handler(event):
    await event.edit(
        "🤖 **HOST**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "`.host <token>` — start a bot\n"
        "`.unhost <id|@user>` — stop\n"
        "`.hostdel <id|@user>` — stop + remove\n"
        "`.hosted` — list hosted bots\n"
        "`.hostboot` — respawn enabled bots\n"
        "`.sharedmods` — list shared modules\n"
        "`.hostdiag` — diagnose shared module wiring\n\n"
        "**Hosted bots use `/` prefix** (e.g. `/dice`, `/ping`)\n"
        "to avoid collision with the userbot's `.` prefix."
    )


# ──────────────────────────────────────────────────────────────────
#  BOOT
# ──────────────────────────────────────────────────────────────────

async def _boot_all(registry=None):
    try:
        async with get_session() as session:
            result = await session.execute(
                select(HostedBot).where(HostedBot.enabled == 1)
            )
            rows = result.scalars().all()
    except Exception as e:
        logger.warning("host boot DB read failed: %s", e)
        return 0, 0

    started = failed = 0
    for row in rows:
        if row.bot_id in _state.bots:
            continue
        ok, message, _ = await _spawn(row.token, registry=registry)
        if ok:
            started += 1
        else:
            failed += 1
            logger.warning("host boot @%s: %s", row.username, message)
    return started, failed


async def on_startup(client):
    await asyncio.sleep(2)
    registry = getattr(client, "plugin_registry", None)
    await _boot_all(registry=registry)
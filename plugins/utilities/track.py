"""Track — observe a user's online sessions over time."""
import time
from datetime import datetime, timezone

from telethon import events, functions
from telethon.tl.types import (
    UserStatusOnline,
    UserStatusOffline,
    UserStatusRecently,
    UserStatusLastWeek,
    UserStatusLastMonth,
    UserStatusEmpty,
)
from sqlalchemy import select, delete

from helpers.decorators import command, listener
from utils.messages import Messages
from Config.settings import Config
from core.logger import setup_logger
from database.connection import get_session
from database.models import TrackedUser, ActivitySession

logger = setup_logger(__name__)


# ─────────────────────── helpers ───────────────────────

async def _resolve_user(client, event, arg: str | None):
    """Resolve a user from reply, id, or @username."""
    if arg:
        arg = arg.strip()
        try:
            if arg.startswith("@"):
                return await client.get_entity(arg)
            if arg.lstrip("-").isdigit():
                return await client.get_entity(int(arg))
        except Exception as e:
            logger.warning(f"resolve {arg} failed: {e}")
            return None

    if event.is_reply:
        replied = await event.get_reply_message()
        if replied:
            return await replied.get_sender()

    return None


async def _is_tracked(user_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            select(TrackedUser).where(
                TrackedUser.user_id == user_id,
                TrackedUser.enabled == 1,
            )
        )
        return result.scalar_one_or_none() is not None


async def _open_session(user_id: int, chat_id: int | None = None):
    """Start a new session row."""
    async with get_session() as session:
        row = ActivitySession(
            user_id=user_id,
            chat_id=chat_id,
            started_at=datetime.now(timezone.utc),
            ended_at=None,
            duration=0,
        )
        session.add(row)


async def _close_session(user_id: int):
    """Close the most recent open session for user_id."""
    async with get_session() as session:
        result = await session.execute(
            select(ActivitySession)
            .where(
                ActivitySession.user_id == user_id,
                ActivitySession.ended_at.is_(None),
            )
            .order_by(ActivitySession.started_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return

        now = datetime.now(timezone.utc)
        row.ended_at = now
        started = row.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        row.duration = int((now - started).total_seconds())


async def _close_all_open_sessions():
    """Called at startup — mark stale sessions from previous run."""
    async with get_session() as session:
        result = await session.execute(
            select(ActivitySession).where(ActivitySession.ended_at.is_(None))
        )
        rows = result.scalars().all()
        now = datetime.now(timezone.utc)
        for row in rows:
            started = row.started_at
            if started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            row.ended_at = now
            row.duration = max(0, int((now - started).total_seconds()))
        logger.info(f"Closed {len(rows)} stale activity session(s)")


# ─────────────────────── listener ───────────────────────

@listener(events.UserUpdate())
async def _status_watcher(event):
    """Fires when a cached user's online status changes."""
    try:
        user_id = event.user_id
    except AttributeError:
        return

    if not await _is_tracked(user_id):
        return

    online = bool(getattr(event, "online", False))

    if online:
        # Avoid duplicate open sessions
        async with get_session() as session:
            result = await session.execute(
                select(ActivitySession).where(
                    ActivitySession.user_id == user_id,
                    ActivitySession.ended_at.is_(None),
                )
            )
            if result.scalar_one_or_none() is not None:
                return
        await _open_session(user_id)
        logger.info(f"📍 track: user {user_id} ONLINE — session started")
    else:
        await _close_session(user_id)
        logger.info(f"📍 track: user {user_id} OFFLINE — session closed")


# ─────────────────────── commands ───────────────────────

@command(r"track(?:\s+(.+))?", "Start observing a user's online status")
async def track_handler(event):
    """
    Start tracking a user's online sessions.

    Observes status changes while ZeroX runs and stores
    every online/offline transition as a session.

    Usage:
        .track                 (reply to a user)
        .track <user_id>
        .track @username

    Notes:
        - Only records activity observed while ZeroX is running
        - Cannot reconstruct activity from before tracking started
        - Status updates require the user to be in ZeroX's entity cache
        - Use .tracked to list, .sessions <user> to view history
    """
    arg = event.pattern_match.group(1)
    target = await _resolve_user(event.client, event, arg)

    if target is None:
        await event.edit(Messages.error("Couldn't resolve user. Reply or give an id/@username."))
        return

    try:
        async with get_session() as session:
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.user_id == target.id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                row = TrackedUser(user_id=target.id, enabled=1)
                session.add(row)
                action = "started"
            else:
                row.enabled = 1
                action = "resumed"
    except Exception as e:
        logger.error(f"track failed: {e}", exc_info=True)
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    name = f"{target.first_name or ''} {target.last_name or ''}".strip() or str(target.id)
    await event.edit(Messages.success(
        f"📍 Tracking **{name}** ({action}).\n"
        f"_Observer active — history from now on._"
    ))


@command(r"untrack(?:\s+(.+))?", "Stop tracking a user")
async def untrack_handler(event):
    """
    Stop observing a user's online status.

    Usage:
        .untrack               (reply to a user)
        .untrack <user_id>
        .untrack @username

    Notes:
        - Existing session history is preserved
        - Use .track to resume
    """
    arg = event.pattern_match.group(1)
    target = await _resolve_user(event.client, event, arg)

    if target is None:
        await event.edit(Messages.error("Couldn't resolve user."))
        return

    try:
        async with get_session() as session:
            result = await session.execute(
                select(TrackedUser).where(TrackedUser.user_id == target.id)
            )
            row = result.scalar_one_or_none()
            if row is None or row.enabled == 0:
                await event.edit(Messages.warning("That user isn't being tracked."))
                return
            row.enabled = 0
    except Exception as e:
        logger.error(f"untrack failed: {e}", exc_info=True)
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    # close any open session
    await _close_session(target.id)

    name = f"{target.first_name or ''} {target.last_name or ''}".strip() or str(target.id)
    await event.edit(Messages.success(f"Stopped tracking **{name}**."))


@command("tracked", "List all tracked users")
async def tracked_handler(event):
    """
    List every user currently being tracked.

    Usage:
        .tracked
    """
    try:
        async with get_session() as session:
            result = await session.execute(
                select(TrackedUser).order_by(TrackedUser.created_at.desc())
            )
            rows = result.scalars().all()
    except Exception as e:
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    if not rows:
        await event.edit(Messages.info("No users tracked yet."))
        return

    lines = ["📍 **Tracked users**\n"]
    for r in rows:
        try:
            ent = await event.client.get_entity(r.user_id)
            name = f"{ent.first_name or ''} {ent.last_name or ''}".strip() or str(r.user_id)
        except Exception:
            name = str(r.user_id)
        mark = "🟢" if r.enabled else "⚪"
        lines.append(f"{mark} `{r.user_id}` — {name}")
    await event.edit("\n".join(lines))


@command(r"sessions(?:\s+(.+))?", "Show observed sessions for a user")
async def sessions_handler(event):
    """
    Show recorded online sessions for a tracked user.

    Usage:
        .sessions              (reply to a user)
        .sessions <user_id>
        .sessions @username

    Notes:
        - Only shows activity observed while ZeroX was running
        - Durations are second-accurate
        - Empty sessions row = user hasn't come online since tracking started
    """
    arg = event.pattern_match.group(1)
    target = await _resolve_user(event.client, event, arg)

    if target is None:
        await event.edit(Messages.error("Couldn't resolve user."))
        return

    try:
        async with get_session() as session:
            result = await session.execute(
                select(ActivitySession)
                .where(ActivitySession.user_id == target.id)
                .order_by(ActivitySession.started_at.desc())
                .limit(20)
            )
            rows = result.scalars().all()
    except Exception as e:
        await event.edit(Messages.error(f"Database error: {e}"))
        return

    if not rows:
        await event.edit(Messages.info("No observed sessions yet."))
        return

    total = sum(r.duration for r in rows if r.ended_at is not None)
    name = f"{target.first_name or ''} {target.last_name or ''}".strip() or str(target.id)

    def fmt(ts):
        if ts is None:
            return "—"
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts.astimezone().strftime("%H:%M")

    def dur(sec):
        if sec < 60:
            return f"{sec}s"
        m, s = divmod(sec, 60)
        if m < 60:
            return f"{m}m {s}s"
        h, m = divmod(m, 60)
        return f"{h}h {m}m"

    lines = [f"📊 **Sessions for {name}**\n"]
    for r in rows[:10]:
        status = "🟢" if r.ended_at is None else "⚪"
        lines.append(
            f"{status} {fmt(r.started_at)} ─ {fmt(r.ended_at)}  ·  {dur(r.duration)}"
        )
    lines.append("")
    lines.append(f"**Shown:** {min(10, len(rows))} · **Total observed:** {dur(total)}")
    await event.edit("\n".join(lines))


@command("trackhelp", "Show Track module help")
async def track_help_handler(event):
    """
    Show all Track module commands.

    Usage:
        .trackhelp
    """
    await event.edit(
        "📍 **TRACK MODULE**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "**🔹 `.track`** — reply to a user to start observing\n"
        "**🔹 `.track <id>`** — track by id\n"
        "**🔹 `.track @user`** — track by username\n"
        "**🔹 `.untrack`** — stop (history preserved)\n"
        "**🔹 `.tracked`** — list all tracked users\n"
        "**🔹 `.sessions`** — view session history\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ Records only activity observed while ZeroX runs.\n"
        "History cannot be reconstructed before tracking began."
    )
"""SQLAlchemy ORM models for ZEROX."""
from datetime import datetime

from sqlalchemy import (
    BigInteger, DateTime, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .connection import Base


class Preset(Base):
    """Saved snapshot of a user's Telegram profile."""
    __tablename__ = "presets"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_preset_user_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    first_name: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    last_name: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    bio: Mapped[str] = mapped_column(Text, default="", nullable=False)
    username: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    photo_reference: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Preset user={self.user_id} name={self.name!r}>"


class Afk(Base):
    """A user's AFK status. One row per user."""
    __tablename__ = "afk"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    since: Mapped[int] = mapped_column(Integer, nullable=False)  # unix ts

    def __repr__(self) -> str:
        return f"<Afk user={self.user_id} reason={self.reason!r}>"


class TrackedUser(Base):
    """A user whose online status ZeroX observes."""
    __tablename__ = "tracked_users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    enabled: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<TrackedUser {self.user_id} enabled={self.enabled}>"


class ActivitySession(Base):
    """A single observed online session for a tracked user."""
    __tablename__ = "activity_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    chat_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    def __repr__(self) -> str:
        return f"<ActivitySession user={self.user_id} dur={self.duration}s>"
class Note(Base):
    """User-saved text snippet, keyed by name."""
    __tablename__ = "notes"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_note_user_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Note user={self.user_id} name={self.name!r}>"


class Filter(Base):
    """Auto-reply filter: keyword → response."""
    __tablename__ = "filters"
    __table_args__ = (
        UniqueConstraint("user_id", "keyword", name="uq_filter_user_kw"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    keyword: Mapped[str] = mapped_column(String(64), nullable=False)
    response: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Filter user={self.user_id} kw={self.keyword!r}>"

class GameStat(Base):
    """Persistent game statistics."""
    __tablename__ = "game_stats"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dice_played: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    slots_played: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jackpots: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duels_won: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duels_lost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trivia_won: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trivia_lost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class HostedBot(Base):
    """Bot credentials used by the optional hosted-bot module."""
    __tablename__ = "hosted_bots"

    bot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    token: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

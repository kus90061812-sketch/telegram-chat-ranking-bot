from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

try:
    from dotenv import load_dotenv
except ImportError:  # Railway installs python-dotenv; tests can still parse helpers.
    def load_dotenv() -> bool:
        return False


def _as_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _telegram_user_ids(name: str, value: str | None) -> frozenset[int]:
    if not value or not value.strip():
        return frozenset()
    try:
        return frozenset(
            int(item)
            for item in re.split(r"[\s,]+", value.strip())
            if item
        )
    except ValueError as exc:
        raise ValueError(
            f"{name} must contain only Telegram user IDs separated by commas"
        ) from exc


def _excluded_user_ids(value: str | None) -> frozenset[int]:
    return _telegram_user_ids("EXCLUDED_USER_IDS", value)


def _pick_admin_user_ids(value: str | None) -> frozenset[int]:
    return _telegram_user_ids("PICK_ADMIN_USER_IDS", value)


def _broadcast_interval_hours(value: str | None) -> int:
    if value is None or not value.strip():
        return 1
    try:
        hours = int(value)
    except ValueError as exc:
        raise ValueError(
            "WEEKLY_BROADCAST_INTERVAL_HOURS must be an integer"
        ) from exc
    if hours < 1:
        raise ValueError("WEEKLY_BROADCAST_INTERVAL_HOURS must be at least 1")
    return hours


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str
    timezone: ZoneInfo
    min_text_length: int
    min_message_interval_seconds: int
    duplicate_window_seconds: int
    excluded_user_ids: frozenset[int]
    pick_admin_user_ids: frozenset[int]
    weekly_broadcast_interval_hours: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        bot_token = os.getenv("BOT_TOKEN", "").strip()
        if not bot_token:
            raise ValueError("BOT_TOKEN is required")

        timezone_name = os.getenv("TIMEZONE", "Asia/Seoul").strip()
        try:
            timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown TIMEZONE: {timezone_name}") from exc

        database_url = os.getenv("DATABASE_URL", "sqlite:///data/chat_rank.db").strip()
        if database_url.startswith("postgres://"):
            database_url = "postgresql+psycopg://" + database_url[len("postgres://") :]
        elif database_url.startswith("postgresql://"):
            database_url = "postgresql+psycopg://" + database_url[len("postgresql://") :]

        if database_url.startswith("sqlite:///"):
            db_path = database_url.removeprefix("sqlite:///")
            if db_path and db_path != ":memory:":
                Path(db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)

        return cls(
            bot_token=bot_token,
            database_url=database_url,
            timezone=timezone,
            min_text_length=_as_int("MIN_TEXT_LENGTH", 5, 1),
            min_message_interval_seconds=_as_int(
                "MIN_MESSAGE_INTERVAL_SECONDS", 3, 0
            ),
            duplicate_window_seconds=_as_int("DUPLICATE_WINDOW_SECONDS", 60, 0),
            excluded_user_ids=_excluded_user_ids(os.getenv("EXCLUDED_USER_IDS")),
            pick_admin_user_ids=_pick_admin_user_ids(
                os.getenv("PICK_ADMIN_USER_IDS")
            ),
            weekly_broadcast_interval_hours=_broadcast_interval_hours(
                os.getenv("WEEKLY_BROADCAST_INTERVAL_HOURS")
            ),
        )

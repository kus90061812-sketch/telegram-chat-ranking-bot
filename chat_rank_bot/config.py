from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


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


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_url: str
    timezone: ZoneInfo
    min_text_length: int
    min_message_interval_seconds: int
    duplicate_window_seconds: int
    exclude_admins: bool
    admin_cache_seconds: int
    admin_username: str
    admin_password: str
    port: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        bot_token = os.getenv("BOT_TOKEN", "").strip()
        if not bot_token:
            raise ValueError("BOT_TOKEN is required")

        admin_username = os.getenv("ADMIN_USERNAME", "admin").strip() or "admin"
        admin_password = os.getenv("ADMIN_PASSWORD", "").strip()
        if len(admin_password) < 8:
            raise ValueError("ADMIN_PASSWORD must be at least 8 characters")

        timezone_name = os.getenv("TIMEZONE", "Asia/Seoul").strip()
        try:
            timezone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown TIMEZONE: {timezone_name}") from exc

        database_url = os.getenv("DATABASE_URL", "sqlite:///data/chat_rank.db").strip()
        # Railway/Heroku의 예전 postgres:// 주소를 psycopg 형식으로 보정합니다.
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
            exclude_admins=_as_bool(os.getenv("EXCLUDE_ADMINS"), True),
            admin_cache_seconds=_as_int("ADMIN_CACHE_SECONDS", 600, 30),
            admin_username=admin_username,
            admin_password=admin_password,
            port=_as_int("PORT", 8000, 1),
        )

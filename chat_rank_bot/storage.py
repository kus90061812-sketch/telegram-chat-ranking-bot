from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RankEntry:
    user_id: int
    display_name: str
    username: str | None
    count: int


@dataclass(frozen=True)
class PersonalRank:
    rank: int | None
    count: int
    leader_count: int

    @property
    def gap_to_first(self) -> int:
        return max(0, self.leader_count - self.count)


class Storage:
    """Chat counts stored in SQLite locally or PostgreSQL on Railway."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.kind = "postgres" if database_url.startswith("postgresql") else "sqlite"
        self.connection: Any | None = None
        self.lock = threading.RLock()

    @property
    def placeholder(self) -> str:
        return "%s" if self.kind == "postgres" else "?"

    def _sql(self, statement: str) -> str:
        return statement.replace("?", self.placeholder)

    def initialize(self) -> None:
        with self.lock:
            if self.kind == "postgres":
                try:
                    import psycopg
                except ImportError as exc:
                    raise RuntimeError(
                        "PostgreSQL 사용 시 psycopg 설치가 필요합니다."
                    ) from exc
                dsn = self.database_url.replace(
                    "postgresql+psycopg://", "postgresql://", 1
                )
                self.connection = psycopg.connect(dsn)
                id_definition = "BIGSERIAL PRIMARY KEY"
            else:
                db_path = self.database_url.removeprefix("sqlite:///")
                if not db_path:
                    raise ValueError("Invalid SQLite DATABASE_URL")
                if db_path != ":memory:":
                    Path(db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
                self.connection = sqlite3.connect(db_path, check_same_thread=False)
                self.connection.execute("PRAGMA journal_mode=WAL")
                self.connection.execute("PRAGMA busy_timeout=5000")
                id_definition = "INTEGER PRIMARY KEY AUTOINCREMENT"

            statements = [
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    chat_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    display_name VARCHAR(255) NOT NULL,
                    username VARCHAR(255),
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (chat_id, user_id)
                )
                """,
                f"""
                CREATE TABLE IF NOT EXISTS message_events (
                    id {id_definition},
                    chat_id BIGINT NOT NULL,
                    message_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    sent_at TEXT NOT NULL,
                    day_key VARCHAR(10) NOT NULL,
                    week_key VARCHAR(10) NOT NULL,
                    content_hash VARCHAR(64) NOT NULL,
                    CONSTRAINT uq_message_chat_id UNIQUE (chat_id, message_id)
                )
                """,
                "CREATE INDEX IF NOT EXISTS ix_events_chat_day_user "
                "ON message_events (chat_id, day_key, user_id)",
                "CREATE INDEX IF NOT EXISTS ix_events_chat_week_user "
                "ON message_events (chat_id, week_key, user_id)",
                "CREATE INDEX IF NOT EXISTS ix_events_recent_user "
                "ON message_events (chat_id, user_id, sent_at)",
            ]
            cursor = self.connection.cursor()
            try:
                for statement in statements:
                    cursor.execute(statement)
                self.connection.commit()
            finally:
                cursor.close()

    def close(self) -> None:
        with self.lock:
            if self.connection is not None:
                self.connection.close()
                self.connection = None

    def _require_connection(self):
        if self.connection is None:
            raise RuntimeError("Storage.initialize() must be called first")
        return self.connection

    @staticmethod
    def _datetime_value(moment: datetime) -> str:
        return moment.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _parse_datetime(value: str | datetime) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    def update_profile(
        self,
        chat_id: int,
        user_id: int,
        display_name: str,
        username: str | None,
        updated_at: datetime,
    ) -> None:
        statement = self._sql(
            """
            INSERT INTO profiles (chat_id, user_id, display_name, username, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (chat_id, user_id) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                username = EXCLUDED.username,
                updated_at = EXCLUDED.updated_at
            """
        )
        values = (
            chat_id,
            user_id,
            (display_name or str(user_id))[:255],
            username[:255] if username else None,
            self._datetime_value(updated_at),
        )
        with self.lock:
            connection = self._require_connection()
            cursor = connection.cursor()
            try:
                cursor.execute(statement, values)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()

    def add_message(
        self,
        *,
        chat_id: int,
        message_id: int,
        user_id: int,
        sent_at: datetime,
        day_key: str,
        week_key: str,
        content_hash: str,
        min_interval_seconds: int,
        duplicate_window_seconds: int,
    ) -> bool:
        """Store a valid message. False means duplicate, cooldown, or already counted."""
        recent_query = self._sql(
            """
            SELECT sent_at
            FROM message_events
            WHERE chat_id = ? AND user_id = ?
            ORDER BY sent_at DESC
            LIMIT 1
            """
        )
        duplicate_query = self._sql(
            """
            SELECT id
            FROM message_events
            WHERE chat_id = ? AND user_id = ? AND content_hash = ? AND sent_at >= ?
            LIMIT 1
            """
        )
        insert_query = self._sql(
            """
            INSERT INTO message_events
                (chat_id, message_id, user_id, sent_at, day_key, week_key, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (chat_id, message_id) DO NOTHING
            RETURNING id
            """
        )

        with self.lock:
            connection = self._require_connection()
            cursor = connection.cursor()
            try:
                cursor.execute(recent_query, (chat_id, user_id))
                recent = cursor.fetchone()
                if recent:
                    elapsed = (
                        sent_at - self._parse_datetime(recent[0])
                    ).total_seconds()
                    if elapsed < min_interval_seconds:
                        connection.rollback()
                        return False

                if duplicate_window_seconds > 0:
                    duplicate_since = self._datetime_value(
                        sent_at - timedelta(seconds=duplicate_window_seconds)
                    )
                    cursor.execute(
                        duplicate_query,
                        (chat_id, user_id, content_hash, duplicate_since),
                    )
                    if cursor.fetchone():
                        connection.rollback()
                        return False

                cursor.execute(
                    insert_query,
                    (
                        chat_id,
                        message_id,
                        user_id,
                        self._datetime_value(sent_at),
                        day_key,
                        week_key,
                        content_hash,
                    ),
                )
                inserted = cursor.fetchone() is not None
                connection.commit()
                return inserted
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()

    def rankings(self, chat_id: int, key_type: str, key: str) -> list[RankEntry]:
        key_column = self._key_column(key_type)
        statement = self._sql(
            f"""
            SELECT e.user_id, p.display_name, p.username, COUNT(e.id) AS message_count
            FROM message_events AS e
            JOIN profiles AS p ON e.chat_id = p.chat_id AND e.user_id = p.user_id
            WHERE e.chat_id = ? AND e.{key_column} = ?
            GROUP BY e.user_id, p.display_name, p.username
            ORDER BY message_count DESC, e.user_id ASC
            """
        )
        with self.lock:
            cursor = self._require_connection().cursor()
            try:
                cursor.execute(statement, (chat_id, key))
                rows = cursor.fetchall()
            finally:
                cursor.close()
        return [
            RankEntry(
                user_id=int(row[0]),
                display_name=str(row[1]),
                username=str(row[2]) if row[2] else None,
                count=int(row[3]),
            )
            for row in rows
        ]

    def personal_rank(
        self, chat_id: int, user_id: int, key_type: str, key: str
    ) -> PersonalRank:
        ranking = self.rankings(chat_id, key_type, key)
        leader_count = ranking[0].count if ranking else 0
        for position, entry in enumerate(ranking, start=1):
            if entry.user_id == user_id:
                return PersonalRank(position, entry.count, leader_count)
        return PersonalRank(None, 0, leader_count)

    @staticmethod
    def _key_column(key_type: str) -> str:
        if key_type == "day":
            return "day_key"
        if key_type == "week":
            return "week_key"
        raise ValueError("key_type must be 'day' or 'week'")

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_RANKING_TEMPLATE = """🏆 {EVENT_TITLE_BOLD}

☀️ {DAILY_TITLE_BOLD} · {DAY_DATE}
{DAILY_RANKING}

📅 {WEEKLY_TITLE_BOLD} · {WEEK_DATE}
{PRIZE_LINE}
{WEEKLY_RANKING}

{FOOTER}"""

LEGACY_DEFAULT_PERSONAL_TEMPLATE = """📊 {NAME_BOLD}님의 채팅 기록

☀️ 오늘: {DAILY_SUMMARY}
📅 이번 주: {WEEKLY_SUMMARY}

오늘 1위까지: {DAILY_GAP}
주간 1위까지: {WEEKLY_GAP}
🎁 현재 주간 예상 상금: {PRIZE_BOLD}

오늘: {DAY_DATE}
주간: {WEEK_DATE}"""

DEFAULT_PERSONAL_TEMPLATE = """🪶 **내 채팅 기록**

📅 오늘: **{DAILY_COUNT}회**
📆 이번 주: **{WEEKLY_COUNT}회**

5글자 이상 집계 / 초성 집계 X

**▪ 매주 월요일 시상진행**
{PRIZE_TABLE}

**▪▪▪▪▪▪ 포인트로 지급**
**🖥 5글자 이상만 집계됩니다**
**▪▪▪▪▪▪▪**
**일정인원 달성시 일일 이벤트 전환예정**"""

DEFAULT_HELP_TEMPLATE = """💬 {EVENT_TITLE_BOLD}

.채팅순위 — 오늘·이번 주 TOP 순위
.나 — 내 일간·주간 채팅 수와 순위

{HELP_MESSAGE}"""

DEFAULT_RANKING_ROW_TEMPLATE = "{MEDAL} {NAME_BOLD} — {COUNT}회"
LEGACY_DEFAULT_PRIZE_LINE_TEMPLATE = "🎁 {PRIZES}"
DEFAULT_PRIZE_LINE_TEMPLATE = "{PRIZES}"
DEFAULT_EMPTY_RANKING_MESSAGE = "아직 집계된 채팅이 없어요."


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


@dataclass(frozen=True)
class ChatGroup:
    chat_id: int
    title: str


@dataclass(frozen=True)
class ChatSettings:
    chat_id: int
    event_title: str = "채팅 순위"
    daily_title: str = "오늘 순위"
    weekly_title: str = "주간 순위"
    prize_1: str = "10만원"
    prize_2: str = "5만원"
    prize_3: str = "3만원"
    prize_4: str = "2만원"
    footer: str = "한국시간 기준 · 도배성 메시지는 집계되지 않습니다."
    help_message: str = "일간은 매일 00시, 주간은 매주 월요일 00시부터 새로 집계됩니다."
    top_limit: int = 10
    ranking_template: str = DEFAULT_RANKING_TEMPLATE
    personal_template: str = DEFAULT_PERSONAL_TEMPLATE
    help_template: str = DEFAULT_HELP_TEMPLATE
    ranking_row_template: str = DEFAULT_RANKING_ROW_TEMPLATE
    prize_line_template: str = DEFAULT_PRIZE_LINE_TEMPLATE
    empty_ranking_message: str = DEFAULT_EMPTY_RANKING_MESSAGE

    def prize_for_rank(self, rank: int | None) -> str | None:
        if rank is None:
            return None
        prizes = {1: self.prize_1, 2: self.prize_2, 3: self.prize_3, 4: self.prize_4}
        return prizes.get(rank) or None

    def prize_items(self) -> list[tuple[int, str]]:
        return [
            (rank, prize)
            for rank, prize in (
                (1, self.prize_1),
                (2, self.prize_2),
                (3, self.prize_3),
                (4, self.prize_4),
            )
            if prize
        ]


class Storage:
    """Small synchronous store supporting SQLite and Railway PostgreSQL."""

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
                        "PostgreSQL 사용 시 requirements.txt의 psycopg 설치가 필요합니다."
                    ) from exc
                dsn = self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
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
                """
                CREATE TABLE IF NOT EXISTS chat_groups (
                    chat_id BIGINT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS chat_settings (
                    chat_id BIGINT PRIMARY KEY,
                    event_title VARCHAR(255) NOT NULL,
                    daily_title VARCHAR(255) NOT NULL,
                    weekly_title VARCHAR(255) NOT NULL,
                    prize_1 VARCHAR(100) NOT NULL,
                    prize_2 VARCHAR(100) NOT NULL,
                    prize_3 VARCHAR(100) NOT NULL,
                    prize_4 VARCHAR(100) NOT NULL,
                    footer VARCHAR(1000) NOT NULL,
                    help_message VARCHAR(2000) NOT NULL,
                    top_limit INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
                """
                CREATE TABLE IF NOT EXISTS chat_message_templates (
                    chat_id BIGINT PRIMARY KEY,
                    ranking_template TEXT NOT NULL,
                    personal_template TEXT NOT NULL,
                    help_template TEXT NOT NULL,
                    ranking_row_template TEXT NOT NULL,
                    prize_line_template TEXT NOT NULL,
                    empty_ranking_message VARCHAR(500) NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """,
                "CREATE INDEX IF NOT EXISTS ix_events_chat_day_user ON message_events (chat_id, day_key, user_id)",
                "CREATE INDEX IF NOT EXISTS ix_events_chat_week_user ON message_events (chat_id, week_key, user_id)",
                "CREATE INDEX IF NOT EXISTS ix_events_recent_user ON message_events (chat_id, user_id, sent_at)",
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

    def register_chat(self, chat_id: int, title: str, updated_at: datetime) -> None:
        statement = self._sql(
            """
            INSERT INTO chat_groups (chat_id, title, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT (chat_id) DO UPDATE SET
                title = EXCLUDED.title,
                updated_at = EXCLUDED.updated_at
            """
        )
        with self.lock:
            connection = self._require_connection()
            cursor = connection.cursor()
            try:
                cursor.execute(
                    statement,
                    (chat_id, (title or str(chat_id))[:255], self._datetime_value(updated_at)),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()

    def list_chats(self) -> list[ChatGroup]:
        statement = "SELECT chat_id, title FROM chat_groups ORDER BY updated_at DESC"
        with self.lock:
            cursor = self._require_connection().cursor()
            try:
                cursor.execute(statement)
                rows = cursor.fetchall()
            finally:
                cursor.close()
        return [ChatGroup(chat_id=int(row[0]), title=str(row[1])) for row in rows]

    def get_chat_settings(self, chat_id: int) -> ChatSettings:
        settings_statement = self._sql(
            """
            SELECT event_title, daily_title, weekly_title,
                   prize_1, prize_2, prize_3, prize_4,
                   footer, help_message, top_limit
            FROM chat_settings
            WHERE chat_id = ?
            """
        )
        templates_statement = self._sql(
            """
            SELECT ranking_template, personal_template, help_template,
                   ranking_row_template, prize_line_template, empty_ranking_message
            FROM chat_message_templates
            WHERE chat_id = ?
            """
        )
        with self.lock:
            cursor = self._require_connection().cursor()
            try:
                cursor.execute(settings_statement, (chat_id,))
                row = cursor.fetchone()
                cursor.execute(templates_statement, (chat_id,))
                template_row = cursor.fetchone()
            finally:
                cursor.close()
        defaults = ChatSettings(chat_id=chat_id)
        if not row and not template_row:
            return defaults
        personal_template = (
            str(template_row[1]) if template_row else defaults.personal_template
        )
        if personal_template == LEGACY_DEFAULT_PERSONAL_TEMPLATE:
            personal_template = defaults.personal_template
        prize_line_template = (
            str(template_row[4]) if template_row else defaults.prize_line_template
        )
        if prize_line_template == LEGACY_DEFAULT_PRIZE_LINE_TEMPLATE:
            prize_line_template = defaults.prize_line_template
        return ChatSettings(
            chat_id=chat_id,
            event_title=str(row[0]) if row else defaults.event_title,
            daily_title=str(row[1]) if row else defaults.daily_title,
            weekly_title=str(row[2]) if row else defaults.weekly_title,
            prize_1=str(row[3]) if row else defaults.prize_1,
            prize_2=str(row[4]) if row else defaults.prize_2,
            prize_3=str(row[5]) if row else defaults.prize_3,
            prize_4=str(row[6]) if row else defaults.prize_4,
            footer=str(row[7]) if row else defaults.footer,
            help_message=str(row[8]) if row else defaults.help_message,
            top_limit=int(row[9]) if row else defaults.top_limit,
            ranking_template=str(template_row[0]) if template_row else defaults.ranking_template,
            personal_template=personal_template,
            help_template=str(template_row[2]) if template_row else defaults.help_template,
            ranking_row_template=str(template_row[3]) if template_row else defaults.ranking_row_template,
            prize_line_template=prize_line_template,
            empty_ranking_message=str(template_row[5]) if template_row else defaults.empty_ranking_message,
        )

    def save_chat_settings(self, settings: ChatSettings) -> None:
        settings_statement = self._sql(
            """
            INSERT INTO chat_settings (
                chat_id, event_title, daily_title, weekly_title,
                prize_1, prize_2, prize_3, prize_4,
                footer, help_message, top_limit, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (chat_id) DO UPDATE SET
                event_title = EXCLUDED.event_title,
                daily_title = EXCLUDED.daily_title,
                weekly_title = EXCLUDED.weekly_title,
                prize_1 = EXCLUDED.prize_1,
                prize_2 = EXCLUDED.prize_2,
                prize_3 = EXCLUDED.prize_3,
                prize_4 = EXCLUDED.prize_4,
                footer = EXCLUDED.footer,
                help_message = EXCLUDED.help_message,
                top_limit = EXCLUDED.top_limit,
                updated_at = EXCLUDED.updated_at
            """
        )
        settings_values = (
            settings.chat_id,
            settings.event_title[:255],
            settings.daily_title[:255],
            settings.weekly_title[:255],
            settings.prize_1[:100],
            settings.prize_2[:100],
            settings.prize_3[:100],
            settings.prize_4[:100],
            settings.footer[:1000],
            settings.help_message[:2000],
            max(3, min(50, settings.top_limit)),
            self._datetime_value(datetime.now(timezone.utc)),
        )
        templates_statement = self._sql(
            """
            INSERT INTO chat_message_templates (
                chat_id, ranking_template, personal_template, help_template,
                ranking_row_template, prize_line_template,
                empty_ranking_message, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (chat_id) DO UPDATE SET
                ranking_template = EXCLUDED.ranking_template,
                personal_template = EXCLUDED.personal_template,
                help_template = EXCLUDED.help_template,
                ranking_row_template = EXCLUDED.ranking_row_template,
                prize_line_template = EXCLUDED.prize_line_template,
                empty_ranking_message = EXCLUDED.empty_ranking_message,
                updated_at = EXCLUDED.updated_at
            """
        )
        templates_values = (
            settings.chat_id,
            settings.ranking_template[:6000],
            settings.personal_template[:6000],
            settings.help_template[:4000],
            settings.ranking_row_template[:500],
            settings.prize_line_template[:500],
            settings.empty_ranking_message[:500],
            self._datetime_value(datetime.now(timezone.utc)),
        )
        with self.lock:
            connection = self._require_connection()
            cursor = connection.cursor()
            try:
                cursor.execute(settings_statement, settings_values)
                cursor.execute(templates_statement, templates_values)
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
        """Store a valid message. False means duplicate/cooldown/already counted."""
        recent_query = self._sql(
            """
            SELECT sent_at, content_hash
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
        sent_at_value = self._datetime_value(sent_at)

        with self.lock:
            connection = self._require_connection()
            cursor = connection.cursor()
            try:
                cursor.execute(recent_query, (chat_id, user_id))
                recent = cursor.fetchone()
                if recent:
                    elapsed = (sent_at - self._parse_datetime(recent[0])).total_seconds()
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
                        sent_at_value,
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

    def personal_rank(self, chat_id: int, user_id: int, key_type: str, key: str) -> PersonalRank:
        ranking = self.rankings(chat_id, key_type, key)
        leader_count = ranking[0].count if ranking else 0
        for position, entry in enumerate(ranking, start=1):
            if entry.user_id == user_id:
                return PersonalRank(position, entry.count, leader_count)
        return PersonalRank(None, 0, leader_count)

    def cleanup_before(self, cutoff: datetime) -> int:
        statement = self._sql("DELETE FROM message_events WHERE sent_at < ?")
        with self.lock:
            connection = self._require_connection()
            cursor = connection.cursor()
            try:
                cursor.execute(statement, (self._datetime_value(cutoff),))
                deleted = int(cursor.rowcount or 0)
                connection.commit()
                return deleted
            except Exception:
                connection.rollback()
                raise
            finally:
                cursor.close()

    @staticmethod
    def _key_column(key_type: str) -> str:
        if key_type == "day":
            return "day_key"
        if key_type == "week":
            return "week_key"
        raise ValueError("key_type must be 'day' or 'week'")

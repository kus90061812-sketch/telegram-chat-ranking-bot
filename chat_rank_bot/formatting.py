from __future__ import annotations

from html import escape

from .periods import day_label, week_label
from .storage import PersonalRank, RankEntry


PRIZES = {1: "10만", 2: "5만", 3: "3만", 4: "2만"}
TOP_LIMIT = 4
EMPTY_NAME = "집계 없음"


def _display_identity(entry: RankEntry) -> str:
    name = escape(
        entry.display_name
        or (f"@{entry.username}" if entry.username else str(entry.user_id))
    )
    if not entry.username:
        return f"{name} (아이디 없음)"
    username = escape(entry.username.lstrip("@"))
    return f"{name} (@{username})"


def _ranking_rows(entries: list[RankEntry], *, show_prizes: bool) -> str:
    rows: list[str] = []
    for position in range(1, TOP_LIMIT + 1):
        if position <= len(entries):
            entry = entries[position - 1]
            name = _display_identity(entry)
            count = f"{entry.count:,}회"
        else:
            name = EMPTY_NAME
            count = "0회"

        prize = f" {PRIZES[position]}" if show_prizes else ""
        rows.append(f"{position}위{prize} - {name} [ {count} ]")
    return "\n".join(rows)


def daily_ranking_message(entries: list[RankEntry], day_key: str) -> str:
    return (
        f"📅 <b>일일집계</b> · {day_label(day_key)}\n\n"
        f"{_ranking_rows(entries, show_prizes=False)}\n\n"
        "매일 00시 새로 집계"
    )


def weekly_ranking_message(entries: list[RankEntry], week_key: str) -> str:
    return (
        f"📆 <b>주간집계</b> · {week_label(week_key)}\n\n"
        f"{_ranking_rows(entries, show_prizes=True)}\n\n"
        "<b>매주 월요일 포인트지급</b>\n"
        "문의 : @TB935 , @tigertk52"
    )


def _rank_text(result: PersonalRank) -> str:
    return f"{result.rank}위" if result.rank is not None else "집계 전"


def personal_message(daily: PersonalRank, weekly: PersonalRank) -> str:
    return (
        "🪶 <b>내 채팅 기록</b>\n\n"
        f"📅 일일: <b>{daily.count:,}회 · {_rank_text(daily)}</b>\n"
        f"📆 주간: <b>{weekly.count:,}회 · {_rank_text(weekly)}</b>\n\n"
        "5글자 이상 집계 / 초성 집계 X"
    )


def help_message() -> str:
    return (
        "💬 <b>채팅 순위 명령어</b>\n\n"
        ".일일순위 — 오늘 1~4위\n"
        ".주간순위 — 이번 주 1~4위와 상금\n"
        ".나 — 내 일일·주간 채팅 수와 등수\n\n"
        "5글자 이상 집계 / 초성 집계 X"
    )

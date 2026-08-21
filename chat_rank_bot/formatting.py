from __future__ import annotations

from html import escape

from .periods import day_label, week_label
from .storage import ChatSettings, PersonalRank, RankEntry


MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def _safe_name(entry: RankEntry) -> str:
    return escape(entry.display_name or (f"@{entry.username}" if entry.username else str(entry.user_id)))


def ranking_lines(entries: list[RankEntry], limit: int) -> list[str]:
    if not entries:
        return ["아직 집계된 채팅이 없어요."]
    lines: list[str] = []
    for position, entry in enumerate(entries[:limit], start=1):
        marker = MEDALS.get(position, f"{position}위")
        lines.append(f"{marker} <b>{_safe_name(entry)}</b> — {entry.count:,}회")
    return lines


def ranking_message(
    daily: list[RankEntry],
    weekly: list[RankEntry],
    day_key: str,
    week_key: str,
    settings: ChatSettings,
) -> str:
    parts = [
        f"🏆 <b>{escape(settings.event_title)}</b>",
        "",
        f"☀️ <b>{escape(settings.daily_title)}</b> · {day_label(day_key)}",
        *ranking_lines(daily, settings.top_limit),
        "",
        f"📅 <b>{escape(settings.weekly_title)}</b> · {week_label(week_key)}",
    ]
    prize_items = settings.prize_items()
    if prize_items:
        prize_text = " · ".join(
            f"{rank}위 {escape(prize)}" for rank, prize in prize_items
        )
        parts.append(f"🎁 {prize_text}")
    parts.extend(ranking_lines(weekly, settings.top_limit))
    if settings.footer:
        parts.extend(["", escape(settings.footer)])
    return "\n".join(parts)


def _personal_line(label: str, result: PersonalRank) -> str:
    if result.rank is None:
        return f"{label}: 아직 집계 전"
    return f"{label}: <b>{result.count:,}회 · {result.rank}위</b>"


def _gap_line(label: str, result: PersonalRank) -> str:
    if result.rank is None:
        return f"{label} 1위까지: {result.leader_count:,}회"
    if result.rank == 1:
        return f"{label}: 현재 1위 👑"
    return f"{label} 1위까지: {result.gap_to_first:,}회"


def _weekly_prize_line(result: PersonalRank, settings: ChatSettings) -> str:
    prize = settings.prize_for_rank(result.rank)
    if prize:
        return f"🎁 현재 주간 예상 상금: <b>{escape(prize)}</b>"
    return "🎁 현재 주간 예상 상금: 순위권 밖"


def personal_message(
    display_name: str,
    daily: PersonalRank,
    weekly: PersonalRank,
    day_key: str,
    week_key: str,
    settings: ChatSettings,
) -> str:
    return "\n".join(
        [
            f"📊 <b>{escape(display_name)}님의 채팅 기록</b>",
            "",
            f"☀️ {_personal_line('오늘', daily)}",
            f"📅 {_personal_line('이번 주', weekly)}",
            "",
            _gap_line("오늘", daily),
            _gap_line("주간", weekly),
            _weekly_prize_line(weekly, settings),
            "",
            f"오늘: {day_label(day_key)}",
            f"주간: {week_label(week_key)}",
        ]
    )

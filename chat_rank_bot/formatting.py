from __future__ import annotations

import re
from html import escape

from .periods import day_label, week_label
from .storage import ChatSettings, PersonalRank, RankEntry


MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
EXTRA_BLANK_LINES = re.compile(r"\n{3,}")
SIMPLE_BOLD = re.compile(r"\*\*([^*\n]+)\*\*")


def _safe_name(entry: RankEntry) -> str:
    return escape(
        entry.display_name
        or (f"@{entry.username}" if entry.username else str(entry.user_id))
    )


def render_template(template: str, values: dict[str, str]) -> str:
    """Escape admin text, then inject trusted pre-escaped dynamic values."""
    result = escape(template)
    result = SIMPLE_BOLD.sub(r"<b>\1</b>", result)
    for key, value in values.items():
        result = result.replace("{" + key + "}", value)
    result = "\n".join(line.rstrip() for line in result.splitlines()).strip()
    return EXTRA_BLANK_LINES.sub("\n\n", result)


def ranking_lines(
    entries: list[RankEntry], limit: int, settings: ChatSettings
) -> str:
    if not entries:
        return escape(settings.empty_ranking_message)
    lines: list[str] = []
    for position, entry in enumerate(entries[:limit], start=1):
        marker = MEDALS.get(position, f"{position}위")
        safe_name = _safe_name(entry)
        lines.append(
            render_template(
                settings.ranking_row_template,
                {
                    "MEDAL": escape(marker),
                    "POSITION": str(position),
                    "NAME": safe_name,
                    "NAME_BOLD": f"<b>{safe_name}</b>",
                    "COUNT": f"{entry.count:,}",
                },
            )
        )
    return "\n".join(lines)


def _prize_line(settings: ChatSettings) -> str:
    prize_items = settings.prize_items()
    if not prize_items:
        return ""
    prizes = " · ".join(
        f"{rank}위 {escape(prize)}" for rank, prize in prize_items
    )
    return render_template(settings.prize_line_template, {"PRIZES": prizes})


def ranking_message(
    daily: list[RankEntry],
    weekly: list[RankEntry],
    day_key: str,
    week_key: str,
    settings: ChatSettings,
) -> str:
    event_title = escape(settings.event_title)
    daily_title = escape(settings.daily_title)
    weekly_title = escape(settings.weekly_title)
    return render_template(
        settings.ranking_template,
        {
            "EVENT_TITLE": event_title,
            "EVENT_TITLE_BOLD": f"<b>{event_title}</b>",
            "DAILY_TITLE": daily_title,
            "DAILY_TITLE_BOLD": f"<b>{daily_title}</b>",
            "WEEKLY_TITLE": weekly_title,
            "WEEKLY_TITLE_BOLD": f"<b>{weekly_title}</b>",
            "DAY_DATE": day_label(day_key),
            "WEEK_DATE": week_label(week_key),
            "DAILY_RANKING": ranking_lines(daily, settings.top_limit, settings),
            "WEEKLY_RANKING": ranking_lines(weekly, settings.top_limit, settings),
            "PRIZE_LINE": _prize_line(settings),
            "FOOTER": escape(settings.footer),
        },
    )


def _rank_text(result: PersonalRank) -> str:
    return f"{result.rank}위" if result.rank is not None else "집계 전"


def _summary(result: PersonalRank) -> str:
    if result.rank is None:
        return "아직 집계 전"
    return f"<b>{result.count:,}회 · {result.rank}위</b>"


def _gap_text(result: PersonalRank) -> str:
    if result.rank is None:
        return f"{result.leader_count:,}회"
    if result.rank == 1:
        return "현재 1위 👑"
    return f"{result.gap_to_first:,}회"


def personal_message(
    display_name: str,
    daily: PersonalRank,
    weekly: PersonalRank,
    day_key: str,
    week_key: str,
    settings: ChatSettings,
) -> str:
    safe_name = escape(display_name)
    prize = escape(settings.prize_for_rank(weekly.rank) or "순위권 밖")
    return render_template(
        settings.personal_template,
        {
            "NAME": safe_name,
            "NAME_BOLD": f"<b>{safe_name}</b>",
            "DAILY_COUNT": f"{daily.count:,}",
            "DAILY_RANK": _rank_text(daily),
            "DAILY_SUMMARY": _summary(daily),
            "DAILY_GAP": _gap_text(daily),
            "WEEKLY_COUNT": f"{weekly.count:,}",
            "WEEKLY_RANK": _rank_text(weekly),
            "WEEKLY_SUMMARY": _summary(weekly),
            "WEEKLY_GAP": _gap_text(weekly),
            "PRIZE": prize,
            "PRIZE_BOLD": f"<b>{prize}</b>",
            "DAY_DATE": day_label(day_key),
            "WEEK_DATE": week_label(week_key),
        },
    )


def help_message(settings: ChatSettings) -> str:
    event_title = escape(settings.event_title)
    return render_template(
        settings.help_template,
        {
            "EVENT_TITLE": event_title,
            "EVENT_TITLE_BOLD": f"<b>{event_title}</b>",
            "HELP_MESSAGE": escape(settings.help_message),
        },
    )

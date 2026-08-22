from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class PeriodKeys:
    day_key: str
    week_key: str


def period_keys(moment: datetime, timezone: ZoneInfo) -> PeriodKeys:
    local = moment.astimezone(timezone)
    monday = local.date() - timedelta(days=local.weekday())
    return PeriodKeys(day_key=local.date().isoformat(), week_key=monday.isoformat())


def parse_key(key: str) -> date:
    return date.fromisoformat(key)


def day_label(day_key: str) -> str:
    day = parse_key(day_key)
    return f"{day.month}월 {day.day}일"


def week_label(week_key: str) -> str:
    monday = parse_key(week_key)
    sunday = monday + timedelta(days=6)
    if monday.month == sunday.month:
        return f"{monday.month}월 {monday.day}일 ~ {sunday.day}일"
    return f"{monday.month}월 {monday.day}일 ~ {sunday.month}월 {sunday.day}일"


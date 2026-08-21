import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from chat_rank_bot.periods import day_label, period_keys, week_label


KST = ZoneInfo("Asia/Seoul")


class PeriodTests(unittest.TestCase):
    def test_kst_day_changes_at_midnight(self) -> None:
        before = datetime(2026, 8, 21, 14, 59, 59, tzinfo=timezone.utc)
        after = datetime(2026, 8, 21, 15, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(period_keys(before, KST).day_key, "2026-08-21")
        self.assertEqual(period_keys(after, KST).day_key, "2026-08-22")

    def test_week_starts_on_monday_kst(self) -> None:
        sunday = datetime(2026, 8, 23, 14, 59, tzinfo=timezone.utc)
        monday = datetime(2026, 8, 23, 15, 0, 0, tzinfo=timezone.utc)
        self.assertEqual(period_keys(sunday, KST).week_key, "2026-08-17")
        self.assertEqual(period_keys(monday, KST).week_key, "2026-08-24")

    def test_labels(self) -> None:
        self.assertEqual(day_label("2026-08-22"), "8월 22일")
        self.assertEqual(week_label("2026-08-31"), "8월 31일 ~ 9월 6일")


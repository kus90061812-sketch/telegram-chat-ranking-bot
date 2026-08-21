import unittest

from chat_rank_bot.formatting import (
    daily_ranking_message,
    help_message,
    personal_message,
    weekly_ranking_message,
)
from chat_rank_bot.storage import PersonalRank, RankEntry


class FormattingTests(unittest.TestCase):
    def test_daily_ranking_always_shows_positions_one_to_four(self) -> None:
        entries = [
            RankEntry(1, "기강 & 친구", "test", 1284),
            RankEntry(2, "라온", None, 900),
        ]
        result = daily_ranking_message(entries, "2026-08-22")
        self.assertIn("📅 <b>일일집계</b>", result)
        self.assertIn("1위 - 기강 &amp; 친구 [ 1,284회 ]", result)
        self.assertIn("2위 - 라온 [ 900회 ]", result)
        self.assertIn("3위 - 집계 없음 [ 0회 ]", result)
        self.assertIn("4위 - 집계 없음 [ 0회 ]", result)

    def test_weekly_ranking_contains_fixed_prizes_and_contacts(self) -> None:
        entries = [RankEntry(1, "기강", None, 321)]
        result = weekly_ranking_message(entries, "2026-08-17")
        self.assertIn("📆 <b>주간집계</b>", result)
        self.assertIn("1위 10만 - 기강 [ 321회 ]", result)
        self.assertIn("2위 5만 - 집계 없음 [ 0회 ]", result)
        self.assertIn("3위 3만 - 집계 없음 [ 0회 ]", result)
        self.assertIn("4위 2만 - 집계 없음 [ 0회 ]", result)
        self.assertIn("매주 월요일 포인트지급", result)
        self.assertIn("문의 : @TB935 , @tigertk52", result)

    def test_personal_message_always_contains_daily_and_weekly_rank(self) -> None:
        result = personal_message(
            PersonalRank(2, 151, 183),
            PersonalRank(4, 891, 1284),
        )
        self.assertIn("📅 일일: <b>151회 · 2위</b>", result)
        self.assertIn("📆 주간: <b>891회 · 4위</b>", result)

    def test_personal_message_says_not_ranked_when_empty(self) -> None:
        result = personal_message(
            PersonalRank(None, 0, 0),
            PersonalRank(None, 0, 0),
        )
        self.assertIn("0회 · 집계 전", result)

    def test_help_lists_new_commands(self) -> None:
        result = help_message()
        self.assertIn(".일일순위", result)
        self.assertIn(".주간순위", result)
        self.assertNotIn(".채팅순위", result)


if __name__ == "__main__":
    unittest.main()

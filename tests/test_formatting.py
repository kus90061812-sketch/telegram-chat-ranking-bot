import unittest

from chat_rank_bot.formatting import (
    admin_weekly_ranking_message,
    daily_ranking_message,
    finalized_weekly_ranking_message,
    help_message,
    personal_message,
    weekly_ranking_message,
    excluded_users_message,
)
from chat_rank_bot.storage import ExcludedUser, PersonalRank, RankEntry


class FormattingTests(unittest.TestCase):
    def test_excluded_users_message_lists_clickable_profiles_without_mentions(self) -> None:
        result = excluded_users_message(
            [ExcludedUser(123, "제외회원", "hidden_user")]
        )
        self.assertIn("집계 제외 목록", result)
        self.assertIn('<a href="https://t.me/hidden_user">@hidden_user</a>', result)

    def test_daily_ranking_always_shows_positions_one_to_four(self) -> None:
        entries = [
            RankEntry(1, "기강 & 친구", "test", 1284),
            RankEntry(2, "라온", None, 900),
        ]
        result = daily_ranking_message(entries, "2026-08-22")
        self.assertIn("📅 <b>일일집계</b>", result)
        self.assertIn(
            '1위 - 기강 &amp; 친구 '
            '(<a href="https://t.me/test">@test</a>) [ 1,284회 ]',
            result,
        )
        self.assertIn("2위 - 라온 (아이디 없음) [ 900회 ]", result)
        self.assertIn("3위 - 집계 없음 [ 0회 ]", result)
        self.assertIn("4위 - 집계 없음 [ 0회 ]", result)

    def test_weekly_ranking_contains_fixed_prizes_and_contacts(self) -> None:
        entries = [RankEntry(1, "기강", "TB935", 321)]
        result = weekly_ranking_message(entries, "2026-08-17")
        self.assertIn("📆 <b>주간집계</b>", result)
        self.assertIn(
            '1위 10만 - 기강 '
            '(<a href="https://t.me/TB935">@TB935</a>) [ 321회 ]',
            result,
        )
        self.assertIn("2위 5만 - 집계 없음 [ 0회 ]", result)
        self.assertIn("3위 3만 - 집계 없음 [ 0회 ]", result)
        self.assertIn("4위 2만 - 집계 없음 [ 0회 ]", result)
        self.assertIn("매주 월요일 포인트지급", result)
        self.assertIn("주간 누적 입금 10만 원 이상 시 지급", result)
        self.assertIn(
            '문의 : <a href="https://t.me/TB935">@TB935</a> , '
            '<a href="https://t.me/tigertk52">@tigertk52</a>',
            result,
        )

    def test_finalized_weekly_ranking_is_clearly_labeled(self) -> None:
        result = finalized_weekly_ranking_message(
            [RankEntry(1, "기강", "TB935", 777)],
            "2026-08-17",
        )
        self.assertIn("🏆 <b>주간 확정 순위</b> · 8월 17일 ~ 23일", result)
        self.assertIn("1위 10만 - 기강", result)
        self.assertIn("4위 2만 - 집계 없음 [ 0회 ]", result)

    def test_admin_weekly_ranking_only_contains_positions_five_to_ten(self) -> None:
        entries = [
            RankEntry(position, f"회원{position}", f"user{position}", 110 - position)
            for position in range(1, 11)
        ]
        result = admin_weekly_ranking_message(
            entries,
            "2026-08-24",
            "AXIS & VIP",
        )
        self.assertIn("🔒 <b>관리자 전용 · 주간 5~10위</b>", result)
        self.assertIn("AXIS &amp; VIP · 8월 24일 ~ 30일", result)
        self.assertIn("5위 - 회원5", result)
        self.assertIn("10위 - 회원10", result)
        self.assertNotIn("1위 - 회원1", result)
        self.assertNotIn("10만", result)

    def test_usernames_are_regular_profile_links_not_mentions(self) -> None:
        result = daily_ranking_message(
            [RankEntry(1, "회원", "clickable_user", 10)],
            "2026-08-22",
        )
        self.assertIn(
            '<a href="https://t.me/clickable_user">@clickable_user</a>',
            result,
        )
        self.assertNotIn("회원 (@clickable_user)", result)

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
        self.assertIn(".관리자순위", result)
        self.assertNotIn(".채팅순위", result)


if __name__ == "__main__":
    unittest.main()

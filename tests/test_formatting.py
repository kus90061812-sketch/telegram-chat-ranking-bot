import unittest

from chat_rank_bot.formatting import personal_message, ranking_message
from chat_rank_bot.storage import ChatSettings, PersonalRank, RankEntry


class FormattingTests(unittest.TestCase):
    def test_ranking_contains_daily_and_weekly_sections(self) -> None:
        entries = [RankEntry(1, "기강 & 친구", "test", 1284)]
        settings = ChatSettings(chat_id=-100)
        result = ranking_message(entries, entries, "2026-08-22", "2026-08-17", settings)
        self.assertIn("오늘 순위", result)
        self.assertIn("주간 순위", result)
        self.assertIn("1,284회", result)
        self.assertIn("기강 &amp; 친구", result)
        self.assertIn("1위 10만원 · 2위 5만원 · 3위 3만원 · 4위 2만원", result)

    def test_personal_message_contains_counts_ranks_and_gaps(self) -> None:
        result = personal_message(
            "기강 <VIP>",
            PersonalRank(2, 151, 183),
            PersonalRank(3, 891, 1284),
            "2026-08-22",
            "2026-08-17",
            ChatSettings(chat_id=-100),
        )
        self.assertIn("151회 · 2위", result)
        self.assertIn("891회 · 3위", result)
        self.assertIn("오늘 1위까지: 32회", result)
        self.assertIn("주간 1위까지: 393회", result)
        self.assertIn("현재 주간 예상 상금: <b>3만원</b>", result)
        self.assertIn("기강 &lt;VIP&gt;", result)

    def test_person_outside_top_four_has_no_expected_prize(self) -> None:
        result = personal_message(
            "라온",
            PersonalRank(5, 100, 300),
            PersonalRank(5, 500, 1000),
            "2026-08-22",
            "2026-08-17",
            ChatSettings(chat_id=-100),
        )
        self.assertIn("현재 주간 예상 상금: 순위권 밖", result)

    def test_custom_web_settings_change_bot_text(self) -> None:
        settings = ChatSettings(
            chat_id=-100,
            event_title="AXIS 채팅왕",
            daily_title="오늘의 채팅왕",
            weekly_title="이번 주 결승",
            prize_1="20만원",
            prize_2="10만원",
            prize_3="5만원",
            prize_4="",
            footer="매주 월요일 발표",
            help_message="자유롭게 참여하세요.",
            top_limit=5,
        )
        entries = [RankEntry(1, "기강", None, 100)]
        result = ranking_message(entries, entries, "2026-08-22", "2026-08-17", settings)
        self.assertIn("AXIS 채팅왕", result)
        self.assertIn("1위 20만원 · 2위 10만원 · 3위 5만원", result)
        self.assertNotIn("4위", result)
        self.assertIn("매주 월요일 발표", result)

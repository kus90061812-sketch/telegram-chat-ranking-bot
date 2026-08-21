import unittest

from chat_rank_bot.formatting import help_message, personal_message, ranking_message
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
        self.assertIn("현재 주간 예상 상금: <b>순위권 밖</b>", result)

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

    def test_full_templates_can_be_rewritten(self) -> None:
        settings = ChatSettings(
            chat_id=-100,
            ranking_template="🔥 {EVENT_TITLE}\n{WEEKLY_RANKING}\n상금: {PRIZE_LINE}",
            ranking_row_template="{POSITION}등 / {NAME} / {COUNT}개",
            prize_line_template="{PRIZES}",
            personal_template="{NAME}님은 이번 주 {WEEKLY_COUNT}개, {WEEKLY_RANK}",
            help_template="명령어 안내\n{HELP_MESSAGE}",
        )
        entries = [RankEntry(1, "기강", None, 321)]
        ranking = ranking_message(entries, entries, "2026-08-22", "2026-08-17", settings)
        personal = personal_message(
            "기강", PersonalRank(1, 20, 20), PersonalRank(1, 321, 321),
            "2026-08-22", "2026-08-17", settings
        )
        help_text = help_message(settings)
        self.assertIn("🔥 채팅 순위", ranking)
        self.assertIn("1등 / 기강 / 321개", ranking)
        self.assertIn("기강님은 이번 주 321개, 1위", personal)
        self.assertIn("명령어 안내", help_text)

    def test_admin_html_is_escaped_but_dynamic_bold_is_kept(self) -> None:
        settings = ChatSettings(
            chat_id=-100,
            ranking_template="<script>{EVENT_TITLE_BOLD}</script>\n{WEEKLY_RANKING}",
        )
        result = ranking_message(
            [], [RankEntry(1, "<VIP>", None, 10)], "2026-08-22", "2026-08-17", settings
        )
        self.assertIn("&lt;script&gt;<b>채팅 순위</b>&lt;/script&gt;", result)
        self.assertIn("<b>&lt;VIP&gt;</b>", result)

    def test_admin_can_use_simple_bold_markup(self) -> None:
        settings = ChatSettings(
            chat_id=-100,
            help_template="**필독**\n{HELP_MESSAGE}",
        )
        self.assertIn("<b>필독</b>", help_message(settings))

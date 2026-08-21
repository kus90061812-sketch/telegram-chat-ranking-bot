import unittest

from chat_rank_bot.text_rules import dot_command, fingerprint, is_countable_text, normalized_text


class TextRuleTests(unittest.TestCase):
    def test_commands_and_emoji_only_are_not_counted(self) -> None:
        self.assertFalse(is_countable_text("/나", 2))
        self.assertFalse(is_countable_text(".나", 2))
        self.assertFalse(is_countable_text("😀🔥", 2))

    def test_normal_chat_is_counted(self) -> None:
        self.assertTrue(is_countable_text("ㅇㅇ", 2))
        self.assertTrue(is_countable_text("안녕하세요", 2))

    def test_normalization_makes_duplicate_detection_stable(self) -> None:
        self.assertEqual(normalized_text("  안녕   하세요 "), "안녕 하세요")
        self.assertEqual(fingerprint("HELLO"), fingerprint("hello"))

    def test_dot_command(self) -> None:
        self.assertEqual(dot_command(".채팅순위"), ".채팅순위")
        self.assertEqual(dot_command(".나 지금"), ".나")
        self.assertIsNone(dot_command("/나"))

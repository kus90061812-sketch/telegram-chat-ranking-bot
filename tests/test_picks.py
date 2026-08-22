import unittest
from dataclasses import dataclass

from chat_rank_bot.picks import (
    _utf16_length,
    custom_emoji_prefix_html,
    parse_slash_command,
    pick_message_html,
)


@dataclass
class FakeEntity:
    type: str
    offset: int
    length: int
    custom_emoji_id: str | None = None


class PickTests(unittest.TestCase):
    def test_parse_pick_content_preserves_multiple_lines(self) -> None:
        parsed = parse_slash_command("/픽 첫 줄\n둘째 줄", "픽")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.argument, "첫 줄\n둘째 줄")

    def test_other_slash_command_does_not_match(self) -> None:
        self.assertIsNone(parse_slash_command("/픽이모지설정 😀", "픽"))

    def test_custom_emoji_is_converted_to_telegram_html(self) -> None:
        text = "/픽이모지설정 😀"
        emoji_offset = _utf16_length("/픽이모지설정 ")
        entity = FakeEntity("custom_emoji", emoji_offset, 2, "123456")
        self.assertEqual(
            custom_emoji_prefix_html(text, [entity]),
            '<tg-emoji emoji-id="123456">😀</tg-emoji>',
        )

    def test_multiple_custom_emojis_and_fixed_text_are_preserved(self) -> None:
        text = "/픽이모지설정 😀 PICK ⭐"
        first_offset = _utf16_length("/픽이모지설정 ")
        second_offset = _utf16_length("/픽이모지설정 😀 PICK ")
        entities = [
            FakeEntity("custom_emoji", first_offset, 2, "111"),
            FakeEntity("custom_emoji", second_offset, 1, "222"),
        ]
        self.assertEqual(
            custom_emoji_prefix_html(text, entities),
            '<tg-emoji emoji-id="111">😀</tg-emoji> PICK '
            '<tg-emoji emoji-id="222">⭐</tg-emoji>',
        )

    def test_regular_emoji_is_rejected_as_premium_emoji(self) -> None:
        with self.assertRaisesRegex(ValueError, "인식되지"):
            custom_emoji_prefix_html("/픽이모지설정 😀", [])

    def test_pick_content_is_html_escaped(self) -> None:
        self.assertEqual(
            pick_message_html("<b>FIXED</b>", "A < B & C"),
            "<b>FIXED</b>\n\nA &lt; B &amp; C",
        )


if __name__ == "__main__":
    unittest.main()

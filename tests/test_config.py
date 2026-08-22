import unittest

from chat_rank_bot.config import (
    _broadcast_interval_hours,
    _excluded_user_ids,
    _pick_admin_user_ids,
)


class ConfigTests(unittest.TestCase):
    def test_excluded_user_ids_accept_commas_and_spaces(self) -> None:
        self.assertEqual(
            _excluded_user_ids("123, 456 789"),
            frozenset({123, 456, 789}),
        )

    def test_excluded_user_ids_can_be_empty(self) -> None:
        self.assertEqual(_excluded_user_ids(""), frozenset())

    def test_excluded_user_ids_reject_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            _excluded_user_ids("123,abc")

    def test_pick_admin_user_ids_accept_multiple_ids(self) -> None:
        self.assertEqual(
            _pick_admin_user_ids("123, 456"),
            frozenset({123, 456}),
        )

    def test_pick_admin_user_ids_reject_invalid_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "PICK_ADMIN_USER_IDS"):
            _pick_admin_user_ids("123,관리자")

    def test_empty_broadcast_interval_defaults_to_one_hour(self) -> None:
        self.assertEqual(_broadcast_interval_hours(None), 1)
        self.assertEqual(_broadcast_interval_hours("  "), 1)

    def test_broadcast_interval_accepts_whole_hours(self) -> None:
        self.assertEqual(_broadcast_interval_hours("2"), 2)
        self.assertEqual(_broadcast_interval_hours(" 3 "), 3)

    def test_broadcast_interval_rejects_invalid_values(self) -> None:
        for value in ("0", "-1", "1.5", "두시간"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _broadcast_interval_hours(value)


if __name__ == "__main__":
    unittest.main()

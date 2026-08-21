import unittest

from chat_rank_bot.config import _excluded_user_ids


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


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timedelta, timezone

from chat_rank_bot.storage import Storage


def add_message(
    storage: Storage, user_id: int, message_id: int, moment: datetime, content_hash: str
) -> bool:
    storage.update_profile(-100, user_id, f"회원{user_id}", None, moment)
    return storage.add_message(
        chat_id=-100,
        message_id=message_id,
        user_id=user_id,
        sent_at=moment,
        day_key="2026-08-22",
        week_key="2026-08-17",
        content_hash=content_hash,
        min_interval_seconds=3,
        duplicate_window_seconds=60,
    )


class StorageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = Storage("sqlite:///:memory:")
        self.storage.initialize()

    def tearDown(self) -> None:
        self.storage.close()

    def test_rank_and_personal_stats(self) -> None:
        now = datetime(2026, 8, 22, tzinfo=timezone.utc)
        self.assertTrue(add_message(self.storage, 1, 1, now, "a"))
        self.assertTrue(add_message(self.storage, 1, 2, now + timedelta(seconds=4), "b"))
        self.assertTrue(add_message(self.storage, 2, 3, now, "c"))

        ranking = self.storage.rankings(-100, "day", "2026-08-22")
        self.assertEqual([(entry.user_id, entry.count) for entry in ranking], [(1, 2), (2, 1)])
        personal = self.storage.personal_rank(-100, 2, "week", "2026-08-17")
        self.assertEqual(personal.rank, 2)
        self.assertEqual(personal.count, 1)
        self.assertEqual(personal.gap_to_first, 1)

    def test_cooldown_duplicate_and_message_id_deduplication(self) -> None:
        now = datetime(2026, 8, 22, tzinfo=timezone.utc)
        self.assertTrue(add_message(self.storage, 1, 1, now, "same"))
        self.assertFalse(add_message(self.storage, 1, 2, now + timedelta(seconds=2), "different"))
        self.assertFalse(add_message(self.storage, 1, 3, now + timedelta(seconds=5), "same"))
        self.assertTrue(add_message(self.storage, 1, 4, now + timedelta(seconds=61), "same"))
        self.assertFalse(add_message(self.storage, 1, 4, now + timedelta(seconds=70), "new"))

    def test_each_group_has_its_own_ranking(self) -> None:
        now = datetime(2026, 8, 22, tzinfo=timezone.utc)
        self.assertTrue(add_message(self.storage, 1, 1, now, "group-a"))
        self.storage.update_profile(-200, 2, "다른방회원", None, now)
        self.assertTrue(
            self.storage.add_message(
                chat_id=-200,
                message_id=1,
                user_id=2,
                sent_at=now,
                day_key="2026-08-22",
                week_key="2026-08-17",
                content_hash="group-b",
                min_interval_seconds=3,
                duplicate_window_seconds=60,
            )
        )
        self.assertEqual([entry.user_id for entry in self.storage.rankings(-100, "day", "2026-08-22")], [1])
        self.assertEqual([entry.user_id for entry in self.storage.rankings(-200, "day", "2026-08-22")], [2])

    def test_registered_chats_are_available_for_automatic_broadcast(self) -> None:
        now = datetime(2026, 8, 22, tzinfo=timezone.utc)
        self.storage.register_chat(-200, "두 번째 방", now)
        self.storage.register_chat(-100, "첫 번째 방", now)
        self.storage.register_chat(-100, "수정된 첫 번째 방", now)
        self.assertEqual(self.storage.list_chat_ids(), [-200, -100])

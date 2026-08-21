import base64
import threading
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from chat_rank_bot.storage import Storage
from chat_rank_bot.web import create_http_server


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class WebAdminTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = Storage("sqlite:///:memory:")
        self.storage.initialize()
        self.storage.register_chat(
            -100, "AXIS 소통방", datetime(2026, 8, 22, tzinfo=timezone.utc)
        )
        self.settings = SimpleNamespace(
            admin_username="admin", admin_password="password123", port=0
        )
        self.server = create_http_server(
            self.storage, self.settings, host="127.0.0.1", port=0
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
        encoded = base64.b64encode(b"admin:password123").decode("ascii")
        self.auth_header = f"Basic {encoded}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.storage.close()

    def test_admin_requires_password(self) -> None:
        with self.assertRaises(HTTPError) as caught:
            urlopen(f"{self.base_url}/admin", timeout=2)
        self.assertEqual(caught.exception.code, 401)

    def test_admin_page_lists_group(self) -> None:
        request = Request(
            f"{self.base_url}/admin", headers={"Authorization": self.auth_header}
        )
        with urlopen(request, timeout=2) as response:
            html = response.read().decode("utf-8")
        self.assertIn("AXIS 소통방", html)
        self.assertIn("/admin/chat/-100", html)

        edit_request = Request(
            f"{self.base_url}/admin/chat/-100",
            headers={"Authorization": self.auth_header},
        )
        with urlopen(edit_request, timeout=2) as response:
            edit_html = response.read().decode("utf-8")
        self.assertIn("봇 답변 전체 편집", edit_html)
        self.assertIn("name=\"ranking_template\"", edit_html)
        self.assertIn(".filter(Boolean).join('\\n')", edit_html)

    def test_save_changes_updates_database(self) -> None:
        payload = urlencode(
            {
                "event_title": "AXIS 채팅왕",
                "daily_title": "오늘의 순위",
                "weekly_title": "주간 결승",
                "prize_1": "30만원",
                "prize_2": "15만원",
                "prize_3": "5만원",
                "prize_4": "2만원",
                "footer": "월요일 발표",
                "help_message": "도배 금지",
                "top_limit": "8",
                "ranking_template": "순위 전체 {WEEKLY_RANKING}",
                "personal_template": "내 기록 {WEEKLY_COUNT}",
                "help_template": "도움 {HELP_MESSAGE}",
                "ranking_row_template": "{POSITION}위 {NAME} {COUNT}",
                "prize_line_template": "상금 {PRIZES}",
                "empty_ranking_message": "아직 없음",
            }
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/admin/chat/-100",
            data=payload,
            method="POST",
            headers={
                "Authorization": self.auth_header,
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with self.assertRaises(HTTPError) as caught:
            build_opener(NoRedirect).open(request, timeout=2)
        self.assertEqual(caught.exception.code, 303)
        saved = self.storage.get_chat_settings(-100)
        self.assertEqual(saved.event_title, "AXIS 채팅왕")
        self.assertEqual(saved.prize_1, "30만원")
        self.assertEqual(saved.top_limit, 8)
        self.assertEqual(saved.ranking_template, "순위 전체 {WEEKLY_RANKING}")
        self.assertEqual(saved.personal_template, "내 기록 {WEEKLY_COUNT}")

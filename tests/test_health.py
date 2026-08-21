import unittest
from urllib.request import Request, urlopen

from chat_rank_bot.health import start_health_server


class HealthServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = start_health_server(0)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def test_every_path_returns_ok_for_railway_healthcheck(self) -> None:
        for path in ("/", "/health", "/old-admin-path"):
            with urlopen(f"{self.base_url}{path}", timeout=2) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b"OK")

    def test_head_returns_ok(self) -> None:
        request = Request(f"{self.base_url}/health", method="HEAD")
        with urlopen(request, timeout=2) as response:
            self.assertEqual(response.status, 200)


if __name__ == "__main__":
    unittest.main()

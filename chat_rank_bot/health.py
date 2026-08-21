from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class _HealthHandler(BaseHTTPRequestHandler):
    def _ok(self, include_body: bool) -> None:
        body = b"OK"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def do_GET(self) -> None:
        self._ok(include_body=True)

    def do_HEAD(self) -> None:
        self._ok(include_body=False)

    def log_message(self, format: str, *args: object) -> None:
        return


def start_health_server(port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("0.0.0.0", port), _HealthHandler)
    thread = threading.Thread(
        target=server.serve_forever,
        name="railway-healthcheck",
        daemon=True,
    )
    thread.start()
    return server

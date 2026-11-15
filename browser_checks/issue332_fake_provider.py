"""Deterministic OpenAI-compatible local fixture for issue #332 Chrome checks."""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

COUNT_FILE = Path(
    os.environ.get("SIGMA_FAKE_PROVIDER_COUNT_FILE", "/tmp/sigma-issue332-provider-count")
)
LOCK = threading.Lock()
FAIL_NEXT = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        return

    def _json(self, status: int, value):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        global FAIL_NEXT
        if self.path == "/v1/models":
            return self._json(200, {"object": "list", "data": [{"id": "gpt-6.1-sol"}]})
        if self.path == "/__test/fail-next":
            with LOCK:
                FAIL_NEXT = True
            return self._json(200, {"armed": True})
        if self.path == "/__test/count":
            try:
                count = int(COUNT_FILE.read_text())
            except (OSError, ValueError):
                count = 0
            return self._json(200, {"responses": count})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        global FAIL_NEXT
        if self.path != "/v1/responses":
            return self._json(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", "0"))
        request = json.loads(self.rfile.read(length))
        if "Infer exactly one useful" not in request.get("instructions", ""):
            return self._json(400, {"error": {"message": "unexpected test request"}})
        with LOCK:
            try:
                count = int(COUNT_FILE.read_text())
            except (OSError, ValueError):
                count = 0
            COUNT_FILE.write_text(str(count + 1))
            should_fail = FAIL_NEXT
            FAIL_NEXT = False
        if should_fail:
            return self._json(503, {"error": {"message": "deterministic fixture failure"}})
        return self._json(
            200,
            {
                "status": "completed",
                "model": "gpt-6.1-sol",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "title": "Test intersections near the extremal arrangement",
                                        "summary": "Check whether intersection structure constrains arrangements near the known bound.",
                                        "approach": "Compare line arrangements that differ by one intersection from the extremal pattern. Derive a local counting invariant and test small cases; treat computations as exploratory evidence rather than proof.",
                                    }
                                ),
                            }
                        ],
                    }
                ],
            },
        )


if __name__ == "__main__":
    COUNT_FILE.parent.mkdir(parents=True, exist_ok=True)
    COUNT_FILE.write_text("0")
    server = ThreadingHTTPServer(
        ("127.0.0.1", int(os.environ.get("SIGMA_FAKE_PROVIDER_PORT", "8003"))), Handler
    )
    server.serve_forever()

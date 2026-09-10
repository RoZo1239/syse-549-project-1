"""Test scaffolding: run a service on an ephemeral port in a background thread.

Tests talk to the services over real HTTP, because half of what is being tested
is HTTP-level behaviour — status codes, the WWW-Authenticate header, and what a
denial body does not say. Every harness gets its own port and its own in-memory
state, so the suite never touches a running deployment.
"""

import os
import threading
from typing import Any, Dict, Optional, Tuple

from shared.httpjson import request_json

TEST_ENV = {
    "LAB1_TEAM": "test-team",
    "LAB1_CSP_BINDING_TOKEN": "test-binding-token-0123456789",
    "LAB1_RP_INTROSPECT_TOKEN": "test-introspect-token-0123456789",
    # Keep the per-request access log out of the test output.
    "LAB1_QUIET_LOG": "1",
    # Pin the rate limit so the test does not depend on the deployed default.
    "LAB1_AUTH_MAX_ATTEMPTS": "5",
    "LAB1_AUTH_WINDOW_SECONDS": "60",
}


def apply_test_env() -> None:
    """Set the tokens the services refuse to start without."""
    for key, value in TEST_ENV.items():
        os.environ[key] = value


class Harness:
    """A running service plus a client for it."""

    def __init__(self, service: Any) -> None:
        self.service = service
        self.server = service.make_server("127.0.0.1", 0)
        self.port = self.server.server_address[1]
        self.url = "http://127.0.0.1:%d" % self.port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Tuple[int, Dict[str, Any]]:
        return request_json(method, self.url + path, payload, **kwargs)

    def raw(
        self,
        method: str,
        path: str,
        payload: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, Dict[str, str], bytes]:
        """A request that bypasses the JSON client, for malformed-input tests."""
        import http.client

        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        connection.request(method, path, body=payload, headers=headers or {})
        response = connection.getresponse()
        body = response.read()
        header_map = {k.lower(): v for k, v in response.getheaders()}
        connection.close()
        return response.status, header_map, body

    def transcript(self, run_id: Optional[str] = None) -> list:
        path = "/transcript" + ("?run_id=%s" % run_id if run_id else "")
        _, body = self.request("GET", path)
        return body.get("events", [])

    def transcript_text(self) -> str:
        _, headers, body = self.raw("GET", "/transcript")
        return body.decode("utf-8")

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def steps(events: list, outcome: Optional[str] = None) -> list:
    return [e["step"] for e in events if outcome is None or e["outcome"] == outcome]

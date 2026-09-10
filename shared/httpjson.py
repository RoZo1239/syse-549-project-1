"""A very small JSON-over-HTTP client, shared by every service.

Standard library only (`urllib.request`); nothing here needs installing on a
machine where we have no sudo. Proxy environment variables are deliberately
ignored: these four services talk to each other over the loopback/campus
address in `team.json`, and an inherited HTTP_PROXY would silently redirect
that traffic.
"""

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple

DEFAULT_TIMEOUT = 5.0
MAX_RESPONSE_BYTES = 256 * 1024

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


class ServiceUnreachable(Exception):
    """The peer service did not answer at all (down, wrong port, firewalled)."""


def request_json(
    method: str,
    url: str,
    payload: Optional[Dict[str, Any]] = None,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Tuple[int, Dict[str, Any]]:
    """Send a JSON request, return `(status, parsed_body)`.

    A 4xx/5xx is returned like any other response — callers in this lab care
    about the status code, and an exception would hide it. Only a peer that
    cannot be reached at all raises.
    """
    body = None
    request_headers = {"Accept": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(
        url, data=body, headers=request_headers, method=method.upper()
    )
    try:
        with _opener.open(request, timeout=timeout) as response:
            return response.status, _parse(response.read(MAX_RESPONSE_BYTES))
    except urllib.error.HTTPError as exc:
        return exc.code, _parse(exc.read(MAX_RESPONSE_BYTES))
    except (urllib.error.URLError, OSError) as exc:
        raise ServiceUnreachable(str(getattr(exc, "reason", exc))) from None


def get_json(url: str, **kwargs: Any) -> Tuple[int, Dict[str, Any]]:
    return request_json("GET", url, None, **kwargs)


def post_json(url: str, payload: Dict[str, Any], **kwargs: Any) -> Tuple[int, Dict[str, Any]]:
    return request_json("POST", url, payload, **kwargs)


def _parse(raw: bytes) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {"body": parsed}

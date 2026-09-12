"""A fixed-window rate limiter for failed attempts.

Keyed on the client address rather than on the claimed identifier on purpose:
counting failures per identifier lets anyone who knows a subscriber's
identifier lock that subscriber out on demand, which trades an online-guessing
defence for a targeted denial of service. The trade-off is recorded in
docs/decisions.md.
"""

import threading
import time
from typing import Dict, List, Tuple


class RateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._hits: Dict[str, List[float]] = {}

    def check(self, key: str, *, now: float = None) -> Tuple[bool, int]:
        """Record one attempt against `key`.

        Returns `(allowed, retry_after_seconds)`.
        """
        now = time.time() if now is None else now
        cutoff = now - self.window_seconds
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if t > cutoff]
            hits.append(now)
            self._hits[key] = hits
            if len(hits) > self.max_attempts:
                return False, max(1, int(self.window_seconds - (now - hits[0])))
        return True, 0

    def forget(self, key: str) -> None:
        """Clear the counter after a success, so one bad typo is not punished."""
        with self._lock:
            self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits = {}

"""Per-user rate limit (in-memory sliding window). Protects the LLM API spend."""
import threading
import time
from collections import defaultdict, deque

LIMIT = 20
WINDOW_SECONDS = 60


class RateLimiter:
    def __init__(self, limit: int = LIMIT, window: int = WINDOW_SECONDS, clock=time.monotonic):
        self.limit, self.window, self._clock = limit, window, clock
        self._hits: dict[int, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, uid: int) -> bool:
        with self._lock:
            now = self._clock()
            q = self._hits[uid]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
            return True


limiter = RateLimiter()

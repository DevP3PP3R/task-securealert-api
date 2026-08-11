from collections import defaultdict, deque
from collections.abc import Callable
from threading import Lock
from time import monotonic


class DeviceRateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = monotonic,
    ):
        self.limit = limit
        self.window_seconds = window_seconds
        self.clock = clock
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.lock = Lock()

    def allow_request(self, device_id: str) -> bool:
        now = self.clock()
        cutoff = now - self.window_seconds

        with self.lock:
            request_times = self.requests[device_id]

            while request_times and request_times[0] <= cutoff:
                request_times.popleft()

            if len(request_times) >= self.limit:
                return False

            request_times.append(now)
            return True
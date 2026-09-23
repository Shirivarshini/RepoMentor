import time
from collections import OrderedDict, deque
from typing import Any

from app.core.exceptions import AppError
from app.schemas.errors import ErrorCode


class RateLimiter:
    def __init__(self) -> None:
        self.windows: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()

    def check(self, client: str, kind: str, limit: int, seconds: int) -> Any:
        now = time.monotonic()
        key = (client, kind)
        entries = self.windows.setdefault(key, deque())
        self.windows.move_to_end(key)
        while entries and entries[0] <= now - seconds:
            entries.popleft()
        if len(entries) >= limit:
            raise AppError(
                ErrorCode.RATE_LIMIT_EXCEEDED,
                "Request limit reached. Please wait before retrying.",
                details={"retry_after_seconds": max(1, int(seconds - now + entries[0]) + 1)},
            )
        entries.append(now)
        while len(self.windows) > 10000:
            self.windows.popitem(last=False)

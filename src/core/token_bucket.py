import asyncio
from typing import Optional


class TokenBucket:
    """Async token-bucket rate limiter.

    rate: tokens per second
    capacity: maximum tokens (burst)
    """

    def __init__(self, rate: float = 1.0, capacity: int = 2):
        self.rate = float(rate)
        self.capacity = float(capacity)
        self._tokens = float(capacity)
        # use loop time for monotonicity
        self._last = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()

    async def _add_tokens(self):
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last
        if elapsed <= 0:
            return
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last = now

    async def consume(self, tokens: float = 1.0):
        """Consume tokens, waiting if necessary."""
        while True:
            async with self._lock:
                await self._add_tokens()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                needed = tokens - self._tokens
                wait = needed / self.rate if self.rate > 0 else 1.0
            await asyncio.sleep(wait)

    async def try_consume(self, tokens: float = 1.0) -> bool:
        """Non-blocking attempt to consume tokens; returns True if succeeded."""
        async with self._lock:
            await self._add_tokens()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def set_rate(self, rate: float, capacity: Optional[int] = None):
        self.rate = float(rate)
        if capacity is not None:
            self.capacity = float(capacity)
            self._tokens = min(self._tokens, self.capacity)

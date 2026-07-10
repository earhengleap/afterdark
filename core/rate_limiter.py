"""
Rate Limiter - Protect bot from abuse and spam
"""

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger("AfterDark.RateLimiter")


class RateLimiter:
    """
    Rate limiting implementation to prevent abuse.
    Uses sliding window algorithm for accurate rate limiting.

    All state mutations are protected by an asyncio.Lock so this is safe
    to call from multiple concurrent Pyrogram handler coroutines without
    blocking the event loop (unlike threading.Lock).
    """

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60,
        max_concurrent: int = 3,
        cooldown_seconds: int = 300
    ):
        """
        Initialize rate limiter

        Args:
            max_requests: Maximum requests allowed in the time window
            window_seconds: Time window in seconds
            max_concurrent: Maximum concurrent operations per user
            cooldown_seconds: Cooldown period after hitting limit
        """
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.max_concurrent = max_concurrent
        self.cooldown_period = timedelta(seconds=cooldown_seconds)

        # User request timestamps (sliding window)
        self.requests: Dict[int, deque] = defaultdict(deque)

        # Concurrent operations counter
        self.concurrent: Dict[int, int] = defaultdict(int)

        # Cooldown tracking
        self.cooldowns: Dict[int, datetime] = {}

        # Violation tracking
        self.violations: Dict[int, int] = defaultdict(int)

        # asyncio-native lock — safe to await inside coroutines
        self._lock: asyncio.Lock = asyncio.Lock()

    async def is_allowed(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check if user is allowed to make a request.

        Returns:
            (allowed: bool, reason: Optional[str])
        """
        async with self._lock:
            now = datetime.now()

            # Check if user is in cooldown
            if user_id in self.cooldowns:
                cooldown_until = self.cooldowns[user_id]
                if now < cooldown_until:
                    remaining = int((cooldown_until - now).total_seconds())
                    return False, f"⏳ Rate limit exceeded. Please wait {remaining}s before trying again."
                else:
                    del self.cooldowns[user_id]
                    self.violations[user_id] = 0

            # Clean old requests (outside the window)
            user_requests = self.requests[user_id]
            while user_requests and now - user_requests[0] > self.window:
                user_requests.popleft()

            # Check request limit
            if len(user_requests) >= self.max_requests:
                self.violations[user_id] += 1

                # Exponential back-off cooldown (caps at 8× base)
                cooldown_duration = self.cooldown_period * (2 ** min(self.violations[user_id] - 1, 3))
                self.cooldowns[user_id] = now + cooldown_duration

                logger.warning(
                    f"User {user_id} exceeded rate limit "
                    f"({len(user_requests)}/{self.max_requests} in {self.window.seconds}s). "
                    f"Violations: {self.violations[user_id]}"
                )

                return False, (
                    f"🚫 Too many requests! You've made {len(user_requests)} requests in the last "
                    f"{self.window.seconds} seconds.\n"
                    f"Please wait {int(cooldown_duration.total_seconds())} seconds."
                )

            # Check concurrent operations
            if self.concurrent[user_id] >= self.max_concurrent:
                return False, (
                    f"⚠️ You have {self.concurrent[user_id]} downloads in progress.\n"
                    f"Please wait for them to complete before starting new ones."
                )

            # Allow request
            user_requests.append(now)
            return True, None

    async def start_operation(self, user_id: int):
        """Mark start of a concurrent operation"""
        async with self._lock:
            self.concurrent[user_id] += 1
            logger.debug(f"User {user_id} started operation. Concurrent: {self.concurrent[user_id]}")

    async def end_operation(self, user_id: int):
        """Mark end of a concurrent operation"""
        async with self._lock:
            self.concurrent[user_id] = max(0, self.concurrent[user_id] - 1)
            logger.debug(f"User {user_id} ended operation. Concurrent: {self.concurrent[user_id]}")

    async def get_stats(self, user_id: int) -> dict:
        """Get rate limit stats for a user"""
        async with self._lock:
            now = datetime.now()

            user_requests = self.requests[user_id]
            recent_requests = sum(1 for req_time in user_requests if now - req_time <= self.window)

            in_cooldown = user_id in self.cooldowns and now < self.cooldowns[user_id]
            cooldown_remaining = 0
            if in_cooldown:
                cooldown_remaining = int((self.cooldowns[user_id] - now).total_seconds())

            return {
                "user_id": user_id,
                "requests_in_window": recent_requests,
                "max_requests": self.max_requests,
                "window_seconds": self.window.seconds,
                "concurrent_operations": self.concurrent[user_id],
                "max_concurrent": self.max_concurrent,
                "in_cooldown": in_cooldown,
                "cooldown_remaining_seconds": cooldown_remaining,
                "violations": self.violations[user_id],
            }

    async def reset_user(self, user_id: int):
        """Reset rate limit for a user (admin function)"""
        async with self._lock:
            if user_id in self.requests:
                self.requests[user_id].clear()
            self.concurrent[user_id] = 0
            self.cooldowns.pop(user_id, None)
            self.violations[user_id] = 0
            logger.info(f"Rate limit reset for user {user_id}")

    async def cleanup(self):
        """Clean up old data to prevent memory leaks"""
        async with self._lock:
            now = datetime.now()

            inactive_users = [
                uid for uid, reqs in self.requests.items()
                if not reqs or (now - reqs[-1]) > timedelta(hours=24)
            ]

            for user_id in inactive_users:
                del self.requests[user_id]
                self.concurrent.pop(user_id, None)
                self.cooldowns.pop(user_id, None)
                self.violations.pop(user_id, None)

            if inactive_users:
                logger.info(f"Cleaned up rate limiter data for {len(inactive_users)} inactive users")


# Global rate limiter instance
# 10 requests per minute, max 3 concurrent downloads, 5-minute cooldown
rate_limiter = RateLimiter(
    max_requests=10,
    window_seconds=60,
    max_concurrent=3,
    cooldown_seconds=300
)


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance"""
    return rate_limiter

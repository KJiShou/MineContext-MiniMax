#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Rate limiting for MiniMax API calls.
Prevents hitting rate limits while maximizing throughput.
"""

import asyncio
import time
from typing import Optional

from opencontext.utils.logging_utils import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Semaphore-based rate limiter for API calls.

    Features:
    - Max concurrent requests
    - Max requests per minute (token bucket style)
    - Exponential backoff on rate limit errors
    """

    def __init__(
        self,
        max_concurrent: int = 5,
        max_per_minute: int = 60,
        max_retries: int = 3,
    ):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._minute_semaphore = asyncio.Semaphore(max_per_minute)
        self._max_retries = max_retries
        self._rate_limit_hits = 0
        self._concurrent_hits = 0

    async def acquire(self):
        """
        Acquire rate limit permission.

        Usage:
            async with rate_limiter.acquire():
                # make API call
        """
        await self._semaphore.acquire()
        await self._minute_semaphore.acquire()
        self._concurrent_hits += 1
        try:
            yield
        finally:
            self._semaphore.release()
            self._minute_semaphore.release()
            self._concurrent_hits -= 1

    async def execute_with_retry(
        self,
        coro,
        on_rate_limit: Optional[str] = None,
    ):
        """
        Execute coroutine with automatic retry on rate limit errors.

        Args:
            coro: Coroutine to execute
            on_rate_limit: Optional error message for rate limit errors

        Returns:
            Result of coroutine or fallback response
        """
        last_error = None

        for attempt in range(self._max_retries):
            try:
                async with self.acquire():
                    return await coro
            except RateLimitError as e:
                last_error = e
                self._rate_limit_hits += 1
                wait_time = 2**attempt  # Exponential backoff

                if attempt < self._max_retries - 1:
                    logger.warning(
                        f"Rate limit hit, waiting {wait_time}s before retry "
                        f"(attempt {attempt + 1}/{self._max_retries})"
                    )
                    await asyncio.sleep(wait_time)
            except Exception as e:
                logger.error(f"API call failed: {e}")
                raise

        # All retries exhausted
        error_msg = on_rate_limit or f"Rate limit exceeded after {self._max_retries} retries"
        raise RateLimitError(error_msg)

    def stats(self) -> dict:
        """Get rate limiter statistics."""
        return {
            "rate_limit_hits": self._rate_limit_hits,
            "current_concurrent": self._concurrent_hits,
        }


class RateLimitError(Exception):
    """Raised when rate limit is exceeded after all retries."""

    pass


# Global rate limiter instance
_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter()
    return _global_rate_limiter

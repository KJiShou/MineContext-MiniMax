#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Tool-level caching for MiniMax API calls.
Reduces API usage, improves latency, provides idempotency.
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from opencontext.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with timestamp for TTL tracking."""

    response: Any
    timestamp: float


class ToolCache:
    """
    In-memory cache for tool responses.

    Features:
    - TTL-based expiration
    - Hash-based cache keys for idempotency
    - Per-tool TTL configuration
    """

    # Default TTLs per tool type (in seconds)
    DEFAULT_TTL = {
        "web_search": 3600,  # 1 hour
        "image_understanding": 86400,  # 24 hours
    }

    def __init__(self, default_ttl: int = 3600):
        self._cache: Dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    def cache_key(self, tool: str, params: dict) -> str:
        """
        Generate deterministic cache key.

        Ensures idempotency: same tool + same params = same key.
        """
        normalized = json.dumps(params, sort_keys=True, ensure_ascii=True)
        raw = f"{tool}:{normalized}".encode("utf-8")
        return hashlib.md5(raw).hexdigest()

    def get(self, key: str, ttl: Optional[int] = None) -> Optional[Any]:
        """
        Get cached value if exists and not expired.

        Args:
            key: Cache key
            ttl: Time-to-live in seconds (overrides default)

        Returns:
            Cached response or None if not found/expired
        """
        if key not in self._cache:
            return None

        entry = self._cache[key]
        ttl = ttl or self._default_ttl
        age = time.time() - entry.timestamp

        if age > ttl:
            # Expired
            del self._cache[key]
            logger.debug(f"Cache expired for key: {key[:8]}...")
            return None

        logger.debug(f"Cache hit for key: {key[:8]}...")
        return entry.response

    async def get_async(self, key: str, ttl: Optional[int] = None) -> Optional[Any]:
        """Async version of get."""
        async with self._lock:
            return self.get(key, ttl)

    def set(self, key: str, response: Any, ttl: Optional[int] = None):
        """
        Store response in cache.

        Args:
            key: Cache key
            response: Response to cache
            ttl: TTL in seconds (optional)
        """
        self._cache[key] = CacheEntry(
            response=response,
            timestamp=time.time(),
        )
        logger.debug(f"Cached response for key: {key[:8]}...")

    async def set_async(self, key: str, response: Any, ttl: Optional[int] = None):
        """Async version of set."""
        async with self._lock:
            self.set(key, response, ttl)

    def invalidate(self, key: str):
        """Remove specific entry from cache."""
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Invalidated cache for key: {key[:8]}...")

    def clear(self):
        """Clear all cache entries."""
        self._cache.clear()
        logger.info("Cache cleared")

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "entries": len(self._cache),
            "keys": list(self._cache.keys())[:10],  # First 10 for debugging
        }


# Global cache instance
_global_cache: Optional[ToolCache] = None


def get_tool_cache() -> ToolCache:
    """Get global cache instance."""
    global _global_cache
    if _global_cache is None:
        _global_cache = ToolCache()
    return _global_cache

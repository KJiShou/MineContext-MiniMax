#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
MiniMax API base class for tool implementations.
Provides common functionality for web search and image understanding.
"""

import os
import time
from abc import abstractmethod
from typing import Any, Dict, Optional

import httpx

from opencontext.config.global_config import get_config
from opencontext.tools.base import BaseTool
from opencontext.tools.cache import get_tool_cache, ToolCache
from opencontext.tools.metrics import get_metrics_collector
from opencontext.tools.rate_limiter import get_rate_limiter, RateLimiter, RateLimitError
from opencontext.tools.tool_response import ToolResponse, ToolType
from opencontext.utils.logging_utils import get_logger

logger = get_logger(__name__)


class MiniMaxBaseTool(BaseTool):
    """
    Base class for MiniMax tools.

    Provides:
    - API key loading from config
    - Caching with TTL
    - Rate limiting
    - Metrics collection
    - Error recovery
    """

    # Override in subclass with specific TTL
    DEFAULT_TTL = 3600

    def __init__(self):
        super().__init__()
        self._config = get_config("tools.minimax") or {}
        self._api_key = os.environ.get("MINIMAX_API_KEY") or self._config.get("api_key", "")
        self._base_url = os.environ.get("MINIMAX_API_HOST") or self._config.get(
            "base_url", "https://api.minimax.io"
        )
        self._cache = get_tool_cache()
        self._rate_limiter = get_rate_limiter()
        self._metrics = get_metrics_collector()

    @abstractmethod
    def get_type(self) -> str:
        """Return the tool type identifier."""

    @abstractmethod
    async def _execute_api_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the actual API call to MiniMax.

        Subclasses must implement this to make the specific API request.

        Args:
            params: Tool parameters

        Returns:
            Raw API response dict
        """

    @abstractmethod
    def _format_summary(self, data: Any, params: Dict[str, Any]) -> str:
        """
        Format LLM-friendly summary of the response.

        Args:
            data: Response data
            params: Original parameters

        Returns:
            Summary string for LLM consumption
        """

    @abstractmethod
    def _calculate_confidence(self, data: Any) -> float:
        """
        Calculate confidence score for the response.

        Args:
            data: Response data

        Returns:
            Confidence 0.0-1.0
        """

    def _get_cache_ttl(self) -> int:
        """Get cache TTL for this tool type."""
        return self.DEFAULT_TTL

    async def execute_async(self, **kwargs) -> ToolResponse:
        """
        Execute tool with full infrastructure: caching, rate limiting, metrics.
        """
        start_time = time.time()
        params = kwargs

        # Generate cache key
        cache_key = self._cache.cache_key(self.get_name(), params)

        # Check cache
        cached_response = await self._cache.get_async(cache_key, self._get_cache_ttl())
        if cached_response:
            latency_ms = (time.time() - start_time) * 1000
            await self._metrics.record_call(
                self.get_name(), cached_response.status, latency_ms, cached=True
            )
            return cached_response

        try:
            # Execute with rate limiting and retry
            async def api_call():
                return await self._execute_api_call(params)

            data = await self._rate_limiter.execute_with_retry(api_call)

            # Build response
            confidence = self._calculate_confidence(data)
            summary = self._format_summary(data, params)

            response = ToolResponse.success(
                tool_type=self.get_type(),
                data=data,
                confidence=confidence,
                summary=summary,
            )

            # Cache the successful response
            await self._cache.set_async(cache_key, response, self._get_cache_ttl())

            latency_ms = (time.time() - start_time) * 1000
            await self._metrics.record_call(
                self.get_name(), response.status, latency_ms, cached=False
            )

            return response

        except RateLimitError as e:
            latency_ms = (time.time() - start_time) * 1000
            response = ToolResponse.partial(
                tool_type=self.get_type(),
                data=None,
                error_message=str(e),
                confidence=0.3,
            )
            await self._metrics.record_call(
                self.get_name(), "partial", latency_ms, cached=False
            )
            await self._metrics.record_error(self.get_name(), str(e))
            return response

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.exception(f"MiniMax tool {self.get_name()} failed: {e}")
            response = ToolResponse.error(
                tool_type=self.get_type(),
                error_message=str(e),
                confidence=0.0,
            )
            await self._metrics.record_call(
                self.get_name(), "error", latency_ms, cached=False
            )
            await self._metrics.record_error(self.get_name(), str(e))
            return response

    def execute(self, **kwargs) -> ToolResponse:
        """Synchronous execute - wraps async version."""
        import asyncio
        try:
            return asyncio.run(self.execute_async(**kwargs))
        except RuntimeError as e:
            # If already running in an event loop, use a different approach
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, self.execute_async(**kwargs))
                return future.result()

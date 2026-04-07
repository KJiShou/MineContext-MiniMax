#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Observability metrics for MiniMax tools.
Tracks latency, success rate, tool usage, and cache performance.
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from opencontext.utils.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class ToolMetrics:
    """Metrics for a single tool."""

    total_calls: int = 0
    success_calls: int = 0
    error_calls: int = 0
    partial_calls: int = 0
    cache_hits: int = 0
    total_latency_ms: float = 0.0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0-1.0)."""
        if self.total_calls == 0:
            return 0.0
        return self.success_calls / self.total_calls

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate (0.0-1.0)."""
        if self.total_calls == 0:
            return 0.0
        return self.cache_hits / self.total_calls

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency in ms."""
        if self.total_calls == 0:
            return 0.0
        return self.total_latency_ms / self.total_calls


class MetricsCollector:
    """
    Collects and aggregates metrics for all tool operations.

    Thread-safe for concurrent access.
    """

    def __init__(self):
        self._metrics: Dict[str, ToolMetrics] = defaultdict(ToolMetrics)
        self._lock = asyncio.Lock()
        self._errors: List[str] = []
        self._max_errors = 100  # Keep last 100 errors

    async def record_call(
        self,
        tool_name: str,
        status: str,  # "success", "error", "partial"
        latency_ms: float,
        cached: bool = False,
    ):
        """Record a tool call."""
        async with self._lock:
            metrics = self._metrics[tool_name]
            metrics.total_calls += 1
            metrics.total_latency_ms += latency_ms
            metrics.min_latency_ms = min(metrics.min_latency_ms, latency_ms)
            metrics.max_latency_ms = max(metrics.max_latency_ms, latency_ms)

            if status == "success":
                metrics.success_calls += 1
            elif status == "error":
                metrics.error_calls += 1
            elif status == "partial":
                metrics.partial_calls += 1

            if cached:
                metrics.cache_hits += 1

    async def record_error(self, tool_name: str, error: str):
        """Record an error for debugging."""
        async with self._lock:
            self._errors.append(f"[{tool_name}] {error}")
            if len(self._errors) > self._max_errors:
                self._errors.pop(0)

    def get_metrics(self, tool_name: Optional[str] = None) -> Dict:
        """
        Get metrics for a specific tool or all tools.

        Args:
            tool_name: Specific tool name or None for all

        Returns:
            Metrics dictionary
        """
        if tool_name:
            return self._format_metrics(tool_name, self._metrics.get(tool_name))
        else:
            return {
                name: self._format_metrics(name, m)
                for name, m in self._metrics.items()
            }

    def _format_metrics(self, tool_name: str, metrics: Optional[ToolMetrics]) -> Dict:
        """Format metrics for export."""
        if metrics is None:
            return {}

        return {
            "tool": tool_name,
            "total_calls": metrics.total_calls,
            "success_rate": round(metrics.success_rate, 3),
            "cache_hit_rate": round(metrics.cache_hit_rate, 3),
            "latency_ms": {
                "avg": round(metrics.avg_latency_ms, 2),
                "min": round(metrics.min_latency_ms, 2) if metrics.min_latency_ms != float("inf") else 0,
                "max": round(metrics.max_latency_ms, 2),
            },
        }

    def get_recent_errors(self, limit: int = 10) -> List[str]:
        """Get recent errors for debugging."""
        return self._errors[-limit:]

    def summary(self) -> Dict:
        """Get full metrics summary."""
        total_calls = sum(m.total_calls for m in self._metrics.values())
        total_cache_hits = sum(m.cache_hits for m in self._metrics.values())
        total_errors = sum(m.error_calls for m in self._metrics.values())

        return {
            "total_calls": total_calls,
            "total_errors": total_errors,
            "overall_success_rate": (
                round((total_calls - total_errors) / total_calls, 3)
                if total_calls > 0
                else 0.0
            ),
            "overall_cache_hit_rate": (
                round(total_cache_hits / total_calls, 3)
                if total_calls > 0
                else 0.0
            ),
            "by_tool": self.get_metrics(),
        }


# Global metrics collector
_global_metrics: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get global metrics collector instance."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = MetricsCollector()
    return _global_metrics

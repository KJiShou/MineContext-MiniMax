#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for MiniMax web search tool.
"""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Set test environment
os.environ.setdefault("MINIMAX_API_KEY", "test_api_key")
os.environ.setdefault("MINIMAX_API_HOST", "https://api.minimax.io")

from opencontext.tools.operation_tools.minimax_web_search import MinimaxWebSearchTool
from opencontext.tools.tool_response import ToolResponse, ToolStatus
from opencontext.tools.cache import ToolCache
from opencontext.tools.metrics import MetricsCollector


class TestMinimaxWebSearchTool:
    """Tests for MinimaxWebSearchTool."""

    @pytest.fixture
    def tool(self):
        """Create tool instance."""
        return MinimaxWebSearchTool()

    @pytest.fixture
    def mock_cache(self):
        """Create mock cache."""
        return MagicMock(spec=ToolCache)

    @pytest.fixture
    def mock_metrics(self):
        """Create mock metrics collector."""
        return MagicMock(spec=MetricsCollector)

    # === Tool Definition Tests ===

    def test_get_name(self):
        """Test tool name."""
        assert MinimaxWebSearchTool.get_name() == "minimax_web_search"

    def test_get_parameters(self):
        """Test tool parameters schema."""
        params = MinimaxWebSearchTool.get_parameters()
        assert params["type"] == "object"
        assert "query" in params["properties"]
        assert "max_results" in params["properties"]
        assert params["required"] == ["query"]

    def test_get_definition(self):
        """Test tool definition for LLM."""
        definition = MinimaxWebSearchTool.get_definition()
        assert definition["name"] == "minimax_web_search"
        assert "description" in definition
        assert "parameters" in definition

    # === Input Validation Tests ===

    def test_empty_query_returns_error(self, tool):
        """Test that empty query returns error response."""
        response = tool.execute(query="")
        assert response.status == ToolStatus.ERROR.value
        assert "empty" in response.error_message.lower()
        assert response.confidence == 0.0

    def test_whitespace_query_returns_error(self, tool):
        """Test that whitespace-only query returns error."""
        response = tool.execute(query="   ")
        assert response.status == ToolStatus.ERROR.value

    def test_query_too_long_returns_error(self, tool):
        """Test that query exceeding 200 chars returns error."""
        long_query = "a" * 201
        response = tool.execute(query=long_query)
        assert response.status == ToolStatus.ERROR.value
        assert "200" in response.error_message

    # === Summary Formatting Tests ===

    def test_format_summary_with_results(self, tool):
        """Test LLM-friendly summary formatting."""
        data = {
            "results": [
                {"title": "Result 1", "url": "http://example.com/1"},
                {"title": "Result 2", "url": "http://example.com/2"},
            ]
        }
        summary = tool._format_summary(data, {"query": "test"})
        # Should be structured, not prose
        assert "Result 1" in summary
        assert "Result 2" in summary
        assert "test" in summary

    def test_format_summary_empty_results(self, tool):
        """Test summary with no results."""
        data = {"results": []}
        summary = tool._format_summary(data, {"query": "test"})
        assert "No results" in summary

    # === Confidence Calculation Tests ===

    def test_confidence_no_results(self, tool):
        """Test confidence with no results."""
        confidence = tool._calculate_confidence({"results": []})
        assert confidence == 0.0

    def test_confidence_multiple_results(self, tool):
        """Test confidence with multiple results."""
        data = {
            "results": [
                {"title": "Result 1"},
                {"title": "Result 2"},
                {"title": "Result 3"},
            ]
        }
        confidence = tool._calculate_confidence(data)
        assert 0.7 <= confidence <= 0.9

    def test_confidence_with_scores(self, tool):
        """Test confidence with scored results."""
        data = {
            "results": [
                {"title": "Result 1", "score": 0.9},
                {"title": "Result 2", "score": 0.8},
                {"title": "Result 3", "score": 0.85},
            ]
        }
        confidence = tool._calculate_confidence(data)
        assert confidence >= 0.7

    # === ToolResponse Schema Tests ===

    def test_response_has_required_fields(self, tool):
        """Test that ToolResponse has all required fields."""
        # Create a sample response
        from opencontext.tools.tool_response import ToolResponse, ToolStatus

        response = ToolResponse(
            status=ToolStatus.SUCCESS.value,
            type="web_search",
            data={"results": []},
            confidence=0.8,
            cached=False,
            summary="Test summary"
        )

        # Check required fields
        assert hasattr(response, "status")
        assert hasattr(response, "type")
        assert hasattr(response, "data")
        assert hasattr(response, "confidence")
        assert hasattr(response, "cached")
        assert hasattr(response, "summary")
        assert response.status == "success"

    def test_response_status_values(self):
        """Test that ToolStatus enum values are valid."""
        assert ToolStatus.SUCCESS.value == "success"
        assert ToolStatus.ERROR.value == "error"
        assert ToolStatus.PARTIAL.value == "partial"

    # === Caching Tests ===

    def test_cache_key_deterministic(self, tool):
        """Test that cache keys are deterministic (idempotency)."""
        cache = ToolCache()
        key1 = cache.cache_key("minimax_web_search", {"query": "test"})
        key2 = cache.cache_key("minimax_web_search", {"query": "test"})
        key3 = cache.cache_key("minimax_web_search", {"query": "other"})

        assert key1 == key2  # Same params = same key
        assert key1 != key3  # Different params = different key

    def test_cache_ttl(self, tool):
        """Test tool has correct TTL."""
        assert tool._get_cache_ttl() == 3600  # 1 hour


class TestToolCache:
    """Tests for ToolCache."""

    def test_cache_get_miss(self):
        """Test cache miss."""
        cache = ToolCache()
        result = cache.get("nonexistent_key")
        assert result is None

    def test_cache_set_and_get(self):
        """Test cache set and get."""
        cache = ToolCache()
        test_response = {"status": "success", "data": "test"}

        cache.set("test_key", test_response)
        result = cache.get("test_key")

        assert result == test_response

    def test_cache_expiration(self):
        """Test cache expiration after TTL."""
        cache = ToolCache(default_ttl=1)  # 1 second TTL

        cache.set("test_key", "value")
        assert cache.get("test_key") == "value"

        # Wait for expiration
        import time
        time.sleep(1.5)

        assert cache.get("test_key") is None

    def test_cache_invalidate(self):
        """Test cache invalidation."""
        cache = ToolCache()
        cache.set("test_key", "value")
        cache.invalidate("test_key")
        assert cache.get("test_key") is None


class TestMetricsCollector:
    """Tests for MetricsCollector."""

    @pytest.fixture
    def metrics(self):
        """Create metrics collector."""
        return MetricsCollector()

    @pytest.mark.asyncio
    async def test_record_call_success(self, metrics):
        """Test recording successful call."""
        await metrics.record_call("test_tool", "success", 100.0, cached=False)
        result = metrics.get_metrics("test_tool")

        assert result["total_calls"] == 1
        assert result["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_record_call_error(self, metrics):
        """Test recording error call."""
        await metrics.record_call("test_tool", "error", 50.0, cached=False)
        result = metrics.get_metrics("test_tool")

        assert result["total_calls"] == 1
        assert result["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_record_call_cached(self, metrics):
        """Test recording cached call."""
        await metrics.record_call("test_tool", "success", 10.0, cached=True)
        result = metrics.get_metrics("test_tool")

        assert result["cache_hit_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_latency_tracking(self, metrics):
        """Test latency tracking."""
        await metrics.record_call("test_tool", "success", 100.0)
        await metrics.record_call("test_tool", "success", 200.0)
        result = metrics.get_metrics("test_tool")

        assert result["latency_ms"]["avg"] == 150.0
        assert result["latency_ms"]["min"] == 100.0
        assert result["latency_ms"]["max"] == 200.0


# === Integration-like Tests ===

class TestWebSearchIntegration:
    """Integration tests (require API key)."""

    @pytest.fixture
    def tool(self):
        return MinimaxWebSearchTool()

    def test_summary_formatting(self, tool):
        """Test summary formatting with mock data."""
        mock_data = {
            "results": [
                {"title": "Python", "url": "https://python.org", "score": 0.95},
                {"title": "PyPI", "url": "https://pypi.org", "score": 0.90},
            ]
        }
        summary = tool._format_summary(mock_data, {"query": "python"})

        assert "Python" in summary
        assert "PyPI" in summary
        assert "python" in summary

    def test_confidence_calculation_with_scores(self, tool):
        """Test confidence calculation with scored results."""
        mock_data = {
            "results": [
                {"title": "Python", "score": 0.95},
                {"title": "PyPI", "score": 0.90},
                {"title": "Python Docs", "score": 0.85},
            ]
        }
        confidence = tool._calculate_confidence(mock_data)
        assert confidence >= 0.7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for MiniMax image understanding tool.
"""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Set test environment
os.environ.setdefault("MINIMAX_API_KEY", "test_api_key")
os.environ.setdefault("MINIMAX_API_HOST", "https://api.minimax.io")

from opencontext.tools.operation_tools.minimax_image_understanding import MinimaxImageUnderstandingTool
from opencontext.tools.tool_response import ToolResponse, ToolStatus
from opencontext.tools.cache import ToolCache


class TestMinimaxImageUnderstandingTool:
    """Tests for MinimaxImageUnderstandingTool."""

    @pytest.fixture
    def tool(self):
        """Create tool instance."""
        return MinimaxImageUnderstandingTool()

    # === Tool Definition Tests ===

    def test_get_name(self):
        """Test tool name."""
        assert MinimaxImageUnderstandingTool.get_name() == "minimax_image_understanding"

    def test_get_parameters(self):
        """Test tool parameters schema."""
        params = MinimaxImageUnderstandingTool.get_parameters()
        assert params["type"] == "object"
        assert "prompt" in params["properties"]
        assert "image_url" in params["properties"]
        assert params["required"] == ["prompt", "image_url"]

    def test_get_definition(self):
        """Test tool definition for LLM."""
        definition = MinimaxImageUnderstandingTool.get_definition()
        assert definition["name"] == "minimax_image_understanding"
        assert "description" in definition
        assert "parameters" in definition

    # === Input Validation Tests ===

    def test_empty_prompt_returns_error(self, tool):
        """Test that empty prompt returns error response."""
        response = tool.execute(prompt="", image_url="https://example.com/image.jpg")
        assert response.status == ToolStatus.ERROR.value
        assert "empty" in response.error_message.lower()
        assert response.confidence == 0.0

    def test_whitespace_prompt_returns_error(self, tool):
        """Test that whitespace-only prompt returns error."""
        response = tool.execute(prompt="   ", image_url="https://example.com/image.jpg")
        assert response.status == ToolStatus.ERROR.value

    def test_missing_image_url_returns_error(self, tool):
        """Test that missing image_url returns error."""
        response = tool.execute(prompt="What is this?")
        assert response.status == ToolStatus.ERROR.value
        assert "image_url" in response.error_message

    def test_invalid_url_scheme_returns_error(self, tool):
        """Test that non-http URL returns error."""
        response = tool.execute(prompt="What is this?", image_url="ftp://example.com/image.jpg")
        assert response.status == ToolStatus.ERROR.value
        assert "http" in response.error_message.lower()

    def test_local_file_url_returns_error(self, tool):
        """Test that local file URL returns error."""
        response = tool.execute(prompt="What is this?", image_url="file:///path/to/image.jpg")
        assert response.status == ToolStatus.ERROR.value

    # === Summary Formatting Tests ===

    def test_format_summary_with_description(self, tool):
        """Test LLM-friendly summary formatting with description."""
        data = {"description": "A cat sitting on a windowsill"}
        summary = tool._format_summary(data, {"prompt": "Describe this image"})
        assert "cat" in summary
        assert "windowsill" in summary

    def test_format_summary_with_label(self, tool):
        """Test summary with label only."""
        data = {"label": "animal"}
        summary = tool._format_summary(data, {"prompt": "What is this?"})
        assert "animal" in summary

    def test_format_summary_empty(self, tool):
        """Test summary with no data."""
        data = {}
        summary = tool._format_summary(data, {"prompt": "Describe"})
        assert "successfully" in summary

    def test_format_summary_truncation(self, tool):
        """Test that long descriptions are truncated."""
        long_description = "A" * 300
        data = {"description": long_description}
        summary = tool._format_summary(data, {"prompt": "Describe"})
        assert len(summary) < 250  # Should be truncated

    # === Confidence Calculation Tests ===

    def test_confidence_detailed_description(self, tool):
        """Test confidence with detailed description."""
        data = {"description": "A large golden retriever playing fetch in a sunny park", "score": 0.9}
        confidence = tool._calculate_confidence(data)
        assert confidence >= 0.8

    def test_confidence_short_description(self, tool):
        """Test confidence with short description."""
        data = {"description": "A dog"}
        confidence = tool._calculate_confidence(data)
        assert 0.5 <= confidence < 0.8

    def test_confidence_label_only(self, tool):
        """Test confidence with label only."""
        data = {"label": "animal"}
        confidence = tool._calculate_confidence(data)
        assert confidence == 0.7

    def test_confidence_empty(self, tool):
        """Test confidence with no useful data."""
        data = {}
        confidence = tool._calculate_confidence(data)
        assert confidence == 0.5

    # === ToolResponse Schema Tests ===

    def test_response_has_required_fields(self, tool):
        """Test that ToolResponse has all required fields."""
        from opencontext.tools.tool_response import ToolResponse, ToolStatus

        response = ToolResponse(
            status=ToolStatus.SUCCESS.value,
            type="image_understanding",
            data={"description": "A sunset"},
            confidence=0.9,
            cached=False,
            summary="A sunset over the ocean"
        )

        # Check required fields
        assert hasattr(response, "status")
        assert hasattr(response, "type")
        assert hasattr(response, "data")
        assert hasattr(response, "confidence")
        assert hasattr(response, "cached")
        assert hasattr(response, "summary")
        assert response.status == "success"

    # === Caching Tests ===

    def test_cache_ttl(self, tool):
        """Test tool has correct TTL for images."""
        assert tool._get_cache_ttl() == 86400  # 24 hours

    # === API Response Parsing Tests ===

    def test_api_response_structure(self, tool):
        """Test parsing various API response structures."""
        # Response with all fields
        data = {
            "description": "A red car",
            "label": "vehicle",
            "score": 0.85,
            "objects": ["car", "road"]
        }
        confidence = tool._calculate_confidence(data)
        assert confidence >= 0.7


class TestToolRouter:
    """Tests for ToolRouter."""

    @pytest.fixture
    def router(self):
        """Create tool router."""
        from opencontext.tools.tool_router import ToolRouter
        return ToolRouter()

    def test_select_web_search_keyword(self, router):
        """Test web search keyword detection."""
        query = "search for python tutorials"
        tool_name = router._selector.select(query)
        assert tool_name == "minimax_web_search"

    def test_select_web_search_what_is(self, router):
        """Test 'what is' queries route to web search."""
        query = "what is python"
        tool_name = router._selector.select(query)
        assert tool_name == "minimax_web_search"

    def test_select_image_keyword(self, router):
        """Test image keyword detection."""
        query = "describe this image"
        tool_name = router._selector.select(query)
        assert tool_name == "minimax_image_understanding"

    def test_select_screenshot(self, router):
        """Test screenshot detection."""
        query = "analyze this screenshot"
        tool_name = router._selector.select(query)
        assert tool_name == "minimax_image_understanding"

    def test_select_fallback_question(self, router):
        """Test short question falls back to web search."""
        query = "why is the sky blue?"
        tool_name = router._selector.select(query)
        assert tool_name == "minimax_web_search"


# === Adversarial Tests ===

class TestAdversarialInputs:
    """Tests for adversarial/malformed inputs."""

    @pytest.fixture
    def tool(self):
        return MinimaxImageUnderstandingTool()

    def test_sql_injection_in_prompt(self, tool):
        """Test SQL injection in prompt doesn't crash."""
        malicious_prompt = "'; DROP TABLE images; --"
        response = tool.execute(
            prompt=malicious_prompt,
            image_url="https://example.com/image.jpg"
        )
        # Should return error, not crash
        assert response.status in [ToolStatus.ERROR.value, ToolStatus.PARTIAL.value]

    def test_xss_in_url(self, tool):
        """Test XSS attempt in URL doesn't crash."""
        malicious_url = "https://example.com/<script>alert('xss')</script>.jpg"
        response = tool.execute(
            prompt="What is this?",
            image_url=malicious_url
        )
        # Should return error, not crash
        assert response.status in [ToolStatus.ERROR.value, ToolStatus.PARTIAL.value]

    def test_unicode_prompt(self, tool):
        """Test unicode prompt is handled."""
        response = tool.execute(
            prompt="这是什么？🎉",
            image_url="https://example.com/image.jpg"
        )
        # Should not crash, may succeed or error gracefully
        assert response.status in [s.value for s in ToolStatus]

    def test_empty_url(self, tool):
        """Test empty URL returns error."""
        response = tool.execute(prompt="What is this?", image_url="")
        assert response.status == ToolStatus.ERROR.value

    def test_very_long_prompt(self, tool):
        """Test very long prompt is handled."""
        long_prompt = "Describe this image " * 100
        # Should either truncate or return error, not crash
        response = tool.execute(prompt=long_prompt, image_url="https://example.com/image.jpg")
        assert response.status in [s.value for s in ToolStatus]


# === Integration-like Tests ===

class TestImageUnderstandingIntegration:
    """Integration tests (require API key)."""

    @pytest.fixture
    def tool(self):
        return MinimaxImageUnderstandingTool()

    def test_summary_formatting(self, tool):
        """Test summary formatting with mock data."""
        mock_data = {
            "description": "A sunset over the ocean",
            "label": "landscape",
            "score": 0.92
        }
        summary = tool._format_summary(mock_data, {"prompt": "Describe this image"})

        assert "sunset" in summary.lower() or "ocean" in summary.lower()

    def test_confidence_calculation(self, tool):
        """Test confidence calculation with mock data."""
        mock_data = {
            "description": "A sunset over the ocean with beautiful orange and pink colors reflecting on the water",
            "label": "landscape",
            "score": 0.92
        }
        confidence = tool._calculate_confidence(mock_data)
        assert confidence > 0.8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

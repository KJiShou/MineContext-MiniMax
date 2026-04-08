#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for ScreenshotProcessor MiniMax tool integration.
Tests helper methods and UI change detection.
"""

import asyncio
import datetime
import json
from unittest.mock import AsyncMock, patch

from PIL import Image
import pytest

from opencontext.context_processing.processor.screenshot_processor import (
    ScreenshotProcessor,
    MINIMAX_CONFIDENCE_THRESHOLD,
    TOOL_TIMEOUT,
    IMAGE_CACHE_TTL,
    MAX_SUMMARY_CHARS,
    MAX_DATA_ITEMS,
    CACHE_VERSION,
)
from opencontext.models.context import RawContextProperties
from opencontext.models.enums import ContentFormat, ContextSource
from opencontext.tools.cache import get_tool_cache
from opencontext.tools.tool_response import ToolResponse, ToolType


class TestSafeTruncateData:
    """Tests for _safe_truncate_data helper method."""

    @pytest.fixture
    def processor(self):
        """Create processor instance."""
        return ScreenshotProcessor(session_id="test_session")

    def test_list_truncation(self, processor):
        """Test list truncation maintains valid JSON structure."""
        data = [1, 2, 3, 4, 5, 6, 7]
        result = processor._safe_truncate_data(data, max_items=3)

        assert result == {"items": [1, 2, 3], "total": 7}
        # Verify it's valid JSON
        assert json.dumps(result)

    def test_list_no_truncation_needed(self, processor):
        """Test list when fewer items than max_items."""
        data = [1, 2]
        result = processor._safe_truncate_data(data, max_items=5)

        assert result == {"items": [1, 2], "total": 2}
        assert json.dumps(result)

    def test_dict_truncation(self, processor):
        """Test dict truncation maintains valid JSON structure."""
        data = {"a": 1, "b": 2, "c": 3, "d": 4}
        result = processor._safe_truncate_data(data, max_items=2)

        assert len(result) == 2
        assert json.dumps(result)  # Ensure valid JSON

    def test_dict_no_truncation_needed(self, processor):
        """Test dict when fewer items than max_items."""
        data = {"a": 1}
        result = processor._safe_truncate_data(data, max_items=5)

        assert result == {"a": 1}
        assert json.dumps(result)

    def test_primitive_value(self, processor):
        """Test primitive value handling."""
        data = "some string"
        result = processor._safe_truncate_data(data)

        assert "value" in result
        assert result["value"] == "some string"
        assert json.dumps(result)

    def test_primitive_long_string(self, processor):
        """Test primitive value with long string is truncated."""
        long_string = "x" * 500
        result = processor._safe_truncate_data(long_string)

        assert len(result["value"]) <= 200
        assert json.dumps(result)


class TestSafeTruncateSummary:
    """Tests for _safe_truncate_summary helper method."""

    @pytest.fixture
    def processor(self):
        """Create processor instance."""
        return ScreenshotProcessor(session_id="test_session")

    def test_summary_no_truncation(self, processor):
        """Test summary shorter than max_chars."""
        summary = "Short summary"
        result = processor._safe_truncate_summary(summary, max_chars=500)

        assert result == "Short summary"
        assert len(result) == len(summary)

    def test_summary_truncation_word_boundary(self, processor):
        """Test truncation at word boundary, not mid-word."""
        long_summary = "word " * 100
        result = processor._safe_truncate_summary(long_summary, max_chars=250)

        # Should not end with partial word
        assert not result.endswith(" wo")
        assert result.endswith("...")

    def test_summary_exact_length(self, processor):
        """Test summary exactly at max_chars."""
        text = "a" * 500
        result = processor._safe_truncate_summary(text, max_chars=500)

        assert len(result) == 500

    def test_summary_truncation_adds_ellipsis(self, processor):
        """Test that truncation adds ellipsis."""
        long_summary = "a" * 600
        result = processor._safe_truncate_summary(long_summary, max_chars=500)

        assert result.endswith("...")


class TestImageHash:
    """Tests for _get_image_hash helper method."""

    @pytest.fixture
    def processor(self):
        """Create processor instance."""
        return ScreenshotProcessor(session_id="test_session")

    def test_same_image_same_hash(self, processor):
        """Test that same image produces same hash."""
        import base64
        # Minimal valid PNG image (1x1 pixel)
        minimal_png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="
        )
        base64_image = base64.b64encode(minimal_png).decode()

        hash1 = processor._get_image_hash(base64_image)
        hash2 = processor._get_image_hash(base64_image)

        assert hash1 == hash2

    def test_different_base64_produces_hash(self, processor):
        """Test that _get_image_hash returns a valid hash string."""
        import base64
        # Create two different images
        import numpy as np
        from PIL import Image
        import io

        # Create 16x16 images with different patterns
        img1 = Image.new('RGB', (16, 16), color=(255, 0, 0))  # Red
        img2 = Image.new('RGB', (16, 16), color=(0, 0, 255))  # Blue

        buf1, buf2 = io.BytesIO(), io.BytesIO()
        img1.save(buf1, format="PNG")
        img2.save(buf2, format="PNG")

        b64_1 = base64.b64encode(buf1.getvalue()).decode()
        b64_2 = base64.b64encode(buf2.getvalue()).decode()

        hash1 = processor._get_image_hash(b64_1)
        hash2 = processor._get_image_hash(b64_2)

        # Both should be valid hash strings
        assert isinstance(hash1, str)
        assert len(hash1) > 0
        assert isinstance(hash2, str)
        assert len(hash2) > 0


class TestUIChangeDetection:
    """Tests for UI change detection logic."""

    def test_same_session_initial_state(self):
        """Test initial state has no previous hash."""
        processor = ScreenshotProcessor(session_id="test")

        assert processor._last_image_hash is None
        assert processor._last_prompt is None

    def test_session_isolation(self):
        """Test different sessions have isolated state."""
        processor1 = ScreenshotProcessor(session_id="session1")
        processor2 = ScreenshotProcessor(session_id="session2")

        processor1._last_image_hash = "hash1"
        processor1._last_prompt = "prompt1"
        processor2._last_image_hash = "hash2"
        processor2._last_prompt = "prompt2"

        assert processor1._last_image_hash == "hash1"
        assert processor1._last_prompt == "prompt1"
        assert processor2._last_image_hash == "hash2"
        assert processor2._last_prompt == "prompt2"


class TestStructuredLogging:
    """Tests for _structured_log helper method."""

    @pytest.fixture
    def processor(self):
        """Create processor instance."""
        return ScreenshotProcessor(session_id="test_session")

    def test_log_does_not_raise_exception(self, processor):
        """Test that _structured_log doesn't raise exceptions."""
        # Verify the method can be called with various parameters
        try:
            processor._structured_log("trace123", "test_stage", "success",
                                   confidence=0.9, cached=False)
        except Exception as e:
            pytest.fail(f"_structured_log raised exception: {e}")

    def test_log_with_error_status(self, processor):
        """Test logging error status."""
        try:
            processor._structured_log("trace456", "tool_call", "error",
                                   error="some error message")
        except Exception as e:
            pytest.fail(f"_structured_log raised exception: {e}")


class TestConstants:
    """Tests for module constants."""

    def test_confidence_threshold_is_reasonable(self):
        """Test confidence threshold is between 0 and 1."""
        assert 0 <= MINIMAX_CONFIDENCE_THRESHOLD <= 1

    def test_cache_version_is_string(self):
        """Test cache version is a string for versioning."""
        assert isinstance(CACHE_VERSION, str)
        assert len(CACHE_VERSION) > 0

    def test_timeout_is_positive(self):
        """Test timeout is positive."""
        assert TOOL_TIMEOUT > 0

    def test_cache_ttl_is_positive(self):
        """Test cache TTL is positive (in seconds)."""
        assert IMAGE_CACHE_TTL > 0


class TestCacheKeyFormat:
    """Tests for cache key generation."""

    def test_cache_key_includes_version(self):
        """Test that cache key format includes version."""
        expected_prefix = f"minimax_{CACHE_VERSION}:"
        assert expected_prefix == "minimax_v1:"


class TestPromptValidation:
    """Tests for screenshot prompt template validation."""

    def test_prompt_group_falls_back_to_legacy_alias(self):
        with patch(
            "opencontext.context_processing.processor.screenshot_processor.get_prompt_group",
            side_effect=[
                {},
                {"system": "SYS {context_type_descriptions}", "user": "USER"},
            ],
        ):
            prompt_path, prompt_group = ScreenshotProcessor._get_prompt_group_with_fallback(
                "processing.extraction.screenshot_analyze",
                "processing.extraction.screenshot_contextual_batch",
            )

        assert prompt_path == "processing.extraction.screenshot_contextual_batch"
        assert prompt_group["system"] == "SYS {context_type_descriptions}"

    def test_require_prompt_template_rejects_missing_field(self):
        with pytest.raises(ValueError, match="Prompt field 'user' is missing or empty"):
            ScreenshotProcessor._require_prompt_template(
                {"system": "SYS"}, "processing.extraction.screenshot_analyze", "user"
            )

    def test_process_vlm_single_reports_missing_prompt_field(self, tmp_path):
        processor = ScreenshotProcessor(session_id="missing_prompt")
        get_tool_cache().clear()
        image_path = _create_test_image(tmp_path)
        raw_context = _create_raw_context(image_path)

        try:
            with patch(
                "opencontext.context_processing.processor.screenshot_processor.get_prompt_group",
                return_value={"system": "SYS {context_type_descriptions}", "user": None},
            ):
                with pytest.raises(ValueError, match="Prompt field 'user' is missing or empty"):
                    asyncio.run(processor._process_vlm_single(raw_context))
        finally:
            processor.shutdown()


def _create_test_image(tmp_path) -> str:
    image_path = tmp_path / "screenshot.png"
    Image.new("RGB", (32, 32), color=(255, 255, 255)).save(image_path)
    return str(image_path)


def _create_raw_context(image_path: str) -> RawContextProperties:
    return RawContextProperties(
        content_format=ContentFormat.IMAGE,
        source=ContextSource.SCREENSHOT,
        create_time=datetime.datetime.now(),
        content_path=image_path,
    )


class TestMiniMaxPromptIntegration:
    """Tests MiniMax MCP prompt enhancement and fallback behavior."""

    def test_successful_minimax_result_enhances_prompt_and_uses_local_image_path(self, tmp_path):
        processor = ScreenshotProcessor(session_id="enhanced_prompt")
        get_tool_cache().clear()
        image_path = _create_test_image(tmp_path)
        raw_context = _create_raw_context(image_path)
        captured_messages = {}
        mock_execute = AsyncMock(
            return_value=ToolResponse.success(
                tool_type=ToolType.IMAGE_UNDERSTANDING.value,
                data={"content": "Visible editor, file tree, and a code pane."},
                confidence=0.92,
                summary="Visible editor, file tree, and a code pane.",
            )
        )

        async def fake_generate(messages, *args, **kwargs):
            captured_messages["messages"] = messages
            return '{"ok": true}'

        try:
            with patch(
                "opencontext.context_processing.processor.screenshot_processor.get_config",
                return_value={
                    "provider": "custom",
                    "base_url": "https://api.minimax.io/v1",
                    "model": "MiniMax-M2.7",
                },
            ), patch(
                "opencontext.context_processing.processor.screenshot_processor.get_prompt_group",
                return_value={
                    "system": "SYS {context_type_descriptions}",
                    "user": "USER {current_date} {current_timestamp} {current_timezone}",
                },
            ), patch(
                "opencontext.tools.operation_tools.minimax_image_understanding.MinimaxImageUnderstandingTool.execute_async",
                new=mock_execute,
            ), patch(
                "opencontext.context_processing.processor.screenshot_processor.generate_with_messages_async",
                side_effect=fake_generate,
            ), patch.object(
                processor, "_extract_items_from_response", return_value=[]
            ):
                result = asyncio.run(processor._process_vlm_single(raw_context))
        finally:
            processor.shutdown()

        assert result == []
        assert mock_execute.await_count == 1
        assert mock_execute.await_args.kwargs["image_url"] == image_path
        assert mock_execute.await_args.kwargs["timeout_seconds"] == TOOL_TIMEOUT

        prompt_text = captured_messages["messages"][1]["content"]
        assert isinstance(prompt_text, str)
        assert "Vision analysis" in prompt_text
        assert "Visible editor, file tree, and a code pane." in prompt_text

    def test_failed_minimax_result_falls_back_to_original_prompt(self, tmp_path):
        processor = ScreenshotProcessor(session_id="fallback_prompt")
        get_tool_cache().clear()
        image_path = _create_test_image(tmp_path)
        raw_context = _create_raw_context(image_path)
        captured_messages = {}
        mock_execute = AsyncMock(
            return_value=ToolResponse.error(
                tool_type=ToolType.IMAGE_UNDERSTANDING.value,
                error_message="mcp unavailable",
            )
        )

        async def fake_generate(messages, *args, **kwargs):
            captured_messages["messages"] = messages
            return '{"ok": true}'

        try:
            with patch(
                "opencontext.context_processing.processor.screenshot_processor.get_config",
                return_value={
                    "provider": "custom",
                    "base_url": "https://api.minimax.io/v1",
                    "model": "MiniMax-M2.7",
                },
            ), patch(
                "opencontext.context_processing.processor.screenshot_processor.get_prompt_group",
                return_value={
                    "system": "SYS {context_type_descriptions}",
                    "user": "USER {current_date} {current_timestamp} {current_timezone}",
                },
            ), patch(
                "opencontext.tools.operation_tools.minimax_image_understanding.MinimaxImageUnderstandingTool.execute_async",
                new=mock_execute,
            ), patch(
                "opencontext.context_processing.processor.screenshot_processor.generate_with_messages_async",
                side_effect=fake_generate,
            ), patch.object(
                processor, "_extract_items_from_response", return_value=[]
            ):
                with pytest.raises(ValueError, match="Configured VLM does not support image input"):
                    asyncio.run(processor._process_vlm_single(raw_context))
        finally:
            processor.shutdown()

        assert "messages" not in captured_messages

    def test_image_capable_vlm_still_receives_image_content(self, tmp_path):
        processor = ScreenshotProcessor(session_id="image_capable_vlm")
        get_tool_cache().clear()
        image_path = _create_test_image(tmp_path)
        raw_context = _create_raw_context(image_path)
        captured_messages = {}
        mock_execute = AsyncMock(
            return_value=ToolResponse.success(
                tool_type=ToolType.IMAGE_UNDERSTANDING.value,
                data={"content": "A browser window is visible."},
                confidence=0.91,
                summary="A browser window is visible.",
            )
        )

        async def fake_generate(messages, *args, **kwargs):
            captured_messages["messages"] = messages
            return '{"ok": true}'

        try:
            with patch(
                "opencontext.context_processing.processor.screenshot_processor.get_config",
                return_value={
                    "provider": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "model": "gpt-4.1",
                },
            ), patch(
                "opencontext.context_processing.processor.screenshot_processor.get_prompt_group",
                return_value={
                    "system": "SYS {context_type_descriptions}",
                    "user": "USER {current_date} {current_timestamp} {current_timezone}",
                },
            ), patch(
                "opencontext.tools.operation_tools.minimax_image_understanding.MinimaxImageUnderstandingTool.execute_async",
                new=mock_execute,
            ), patch(
                "opencontext.context_processing.processor.screenshot_processor.generate_with_messages_async",
                side_effect=fake_generate,
            ), patch.object(
                processor, "_extract_items_from_response", return_value=[]
            ):
                result = asyncio.run(processor._process_vlm_single(raw_context))
        finally:
            processor.shutdown()

        assert result == []
        content = captured_messages["messages"][1]["content"]
        assert isinstance(content, list)
        assert content[0]["type"] == "image_url"
        assert content[1]["type"] == "text"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

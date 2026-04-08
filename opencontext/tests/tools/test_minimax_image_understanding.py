#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Unit tests for MiniMax image understanding MCP integration.
"""

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image

from opencontext.tools.cache import ToolCache
from opencontext.tools.operation_tools.minimax_image_understanding import (
    MinimaxImageUnderstandingTool,
)
from opencontext.tools.tool_response import ToolStatus


def _build_tool(tool_config=None, vlm_config=None, env=None):
    tool_config = tool_config or {}
    vlm_config = vlm_config or {}
    env = env or {}

    def fake_get_config(path):
        mapping = {
            "tools.minimax": tool_config,
            "vlm_model": vlm_config,
        }
        return mapping.get(path)

    with patch.dict(os.environ, env, clear=True):
        with patch(
            "opencontext.tools.operation_tools.minimax_base.get_config",
            side_effect=fake_get_config,
        ):
            tool = MinimaxImageUnderstandingTool()
            tool._cache = ToolCache()
            return tool


def _create_test_image(tmp_path: Path) -> str:
    image_path = tmp_path / "sample.png"
    Image.new("RGB", (24, 24), color=(255, 255, 255)).save(image_path)
    return str(image_path)


class TestMinimaxImageUnderstandingTool:
    def test_get_name(self):
        assert MinimaxImageUnderstandingTool.get_name() == "minimax_image_understanding"

    def test_get_parameters(self):
        params = MinimaxImageUnderstandingTool.get_parameters()
        assert params["type"] == "object"
        assert "prompt" in params["properties"]
        assert "image_url" in params["properties"]
        assert params["required"] == ["prompt", "image_url"]

    def test_get_definition(self):
        definition = MinimaxImageUnderstandingTool.get_definition()
        assert definition["name"] == "minimax_image_understanding"
        assert "description" in definition
        assert "parameters" in definition

    def test_env_config_overrides_tool_and_vlm_config(self):
        tool = _build_tool(
            tool_config={"api_key": "tool-key", "base_url": "https://api.minimax.io"},
            vlm_config={"api_key": "vlm-key", "base_url": "https://api.minimax.io/v1"},
            env={
                "MINIMAX_API_KEY": "env-key",
                "MINIMAX_API_HOST": "https://api.minimax.io/v1",
            },
        )
        assert tool._api_key == "env-key"
        assert tool._base_url == "https://api.minimax.io"

    def test_tool_config_overrides_vlm_config(self):
        tool = _build_tool(
            tool_config={"api_key": "tool-key", "base_url": "https://api.minimax.io/v1"},
            vlm_config={"api_key": "vlm-key", "base_url": "https://api.minimax.io/v1"},
        )
        assert tool._api_key == "tool-key"
        assert tool._base_url == "https://api.minimax.io"

    def test_vlm_config_fallback_is_used_when_tool_config_missing(self):
        tool = _build_tool(
            vlm_config={"api_key": "vlm-key", "base_url": "https://api.minimax.io/v1"}
        )
        assert tool._api_key == "vlm-key"
        assert tool._base_url == "https://api.minimax.io"

    def test_normalize_base_url_strips_trailing_v1(self):
        assert (
            MinimaxImageUnderstandingTool._normalize_base_url("https://api.minimax.io/v1/")
            == "https://api.minimax.io"
        )

    def test_empty_prompt_returns_error(self):
        tool = _build_tool()
        response = asyncio.run(tool.execute_async(prompt="", image_url="https://example.com/image.jpg"))
        assert response.status == ToolStatus.ERROR.value
        assert "empty" in response.error_message.lower()

    def test_missing_image_url_returns_error(self):
        tool = _build_tool()
        response = asyncio.run(tool.execute_async(prompt="Describe this image"))
        assert response.status == ToolStatus.ERROR.value
        assert "image_url" in response.error_message

    def test_nonexistent_local_file_returns_error(self):
        tool = _build_tool()
        response = asyncio.run(
            tool.execute_async(prompt="Describe this image", image_url="./does-not-exist.png")
        )
        assert response.status == ToolStatus.ERROR.value
        assert "does not exist" in response.error_message

    def test_invalid_scheme_returns_error(self):
        tool = _build_tool()
        response = asyncio.run(
            tool.execute_async(prompt="Describe this image", image_url="ftp://example.com/image.jpg")
        )
        assert response.status == ToolStatus.ERROR.value
        assert "http(s)" in response.error_message

    def test_file_url_returns_error(self):
        tool = _build_tool()
        response = asyncio.run(
            tool.execute_async(prompt="Describe this image", image_url="file:///tmp/image.jpg")
        )
        assert response.status == ToolStatus.ERROR.value
        assert "file://" in response.error_message

    def test_https_url_is_accepted_and_calls_mcp(self):
        tool = _build_tool(
            tool_config={"api_key": "tool-key", "base_url": "https://api.minimax.io"}
        )
        mock_client = MagicMock()
        mock_client.call_tool_text = AsyncMock(return_value="A detailed screenshot analysis.")

        mock_client.close = AsyncMock()
        with patch(
            "opencontext.tools.operation_tools.minimax_image_understanding.create_minimax_mcp_client",
            return_value=mock_client,
        ):
            response = asyncio.run(
                tool.execute_async(
                    prompt="Describe this image",
                    image_url="https://example.com/image.png",
                )
            )

        assert response.status == ToolStatus.SUCCESS.value
        assert response.summary == "A detailed screenshot analysis."
        assert response.data["content"] == "A detailed screenshot analysis."
        assert mock_client.close.await_count == 1

    def test_local_file_is_accepted_and_calls_mcp(self, tmp_path):
        tool = _build_tool(
            tool_config={"api_key": "tool-key", "base_url": "https://api.minimax.io"}
        )
        image_path = _create_test_image(tmp_path)
        mock_client = MagicMock()
        mock_client.call_tool_text = AsyncMock(return_value="Local image analysis.")

        mock_client.close = AsyncMock()
        with patch(
            "opencontext.tools.operation_tools.minimax_image_understanding.create_minimax_mcp_client",
            return_value=mock_client,
        ):
            response = asyncio.run(
                tool.execute_async(
                    prompt="Describe this image",
                    image_url=image_path,
                )
            )

        assert response.status == ToolStatus.SUCCESS.value
        assert response.data["content"] == "Local image analysis."
        assert mock_client.close.await_count == 1

    def test_data_url_is_accepted_and_calls_mcp(self):
        tool = _build_tool(
            tool_config={"api_key": "tool-key", "base_url": "https://api.minimax.io"}
        )
        mock_client = MagicMock()
        mock_client.call_tool_text = AsyncMock(return_value="Data URL analysis.")

        mock_client.close = AsyncMock()
        with patch(
            "opencontext.tools.operation_tools.minimax_image_understanding.create_minimax_mcp_client",
            return_value=mock_client,
        ):
            response = asyncio.run(
                tool.execute_async(
                    prompt="Describe this image",
                    image_url="data:image/png;base64,AAAA",
                )
            )

        assert response.status == ToolStatus.SUCCESS.value
        assert response.data["content"] == "Data URL analysis."
        assert mock_client.close.await_count == 1

    def test_execute_api_call_maps_public_image_url_to_mcp_image_source(self):
        tool = _build_tool(
            tool_config={"api_key": "tool-key", "base_url": "https://api.minimax.io"}
        )
        mock_client = MagicMock()
        mock_client.call_tool_text = AsyncMock(return_value="Mapped analysis.")

        mock_client.close = AsyncMock()
        with patch(
            "opencontext.tools.operation_tools.minimax_image_understanding.create_minimax_mcp_client",
            return_value=mock_client,
        ):
            result = asyncio.run(
                tool._execute_api_call(
                    {"prompt": "Describe this image", "image_url": "https://example.com/image.png"}
                )
            )

        assert result == {"content": "Mapped analysis."}
        assert mock_client.call_tool_text.await_count == 1
        args, kwargs = mock_client.call_tool_text.await_args
        assert args[0] == "understand_image"
        assert args[1] == {
            "prompt": "Describe this image",
            "image_source": "https://example.com/image.png",
        }
        assert kwargs["timeout_seconds"] == 30.0
        assert mock_client.close.await_count == 1

    def test_mcp_startup_failure_returns_error(self):
        tool = _build_tool(
            tool_config={"api_key": "tool-key", "base_url": "https://api.minimax.io"}
        )

        with patch(
            "opencontext.tools.operation_tools.minimax_image_understanding.create_minimax_mcp_client",
            side_effect=RuntimeError("boom"),
        ):
            response = asyncio.run(
                tool.execute_async(
                    prompt="Describe this image",
                    image_url="https://example.com/image.png",
                )
            )

        assert response.status == ToolStatus.ERROR.value
        assert "boom" in response.error_message

    def test_mcp_timeout_returns_error(self):
        tool = _build_tool(
            tool_config={"api_key": "tool-key", "base_url": "https://api.minimax.io"}
        )
        mock_client = MagicMock()
        mock_client.call_tool_text = AsyncMock(side_effect=TimeoutError("timed out"))
        mock_client.close = AsyncMock()

        with patch(
            "opencontext.tools.operation_tools.minimax_image_understanding.create_minimax_mcp_client",
            return_value=mock_client,
        ):
            response = asyncio.run(
                tool.execute_async(
                    prompt="Describe this image",
                    image_url="https://example.com/image.png",
                )
            )

        assert response.status == ToolStatus.ERROR.value
        assert "timed out" in response.error_message
        assert mock_client.close.await_count == 1

#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
MiniMax image understanding tool.
Provides AI-powered image analysis.
"""

import os
from typing import Any, Dict

from opencontext.tools.operation_tools.minimax_mcp_client import get_minimax_mcp_client
from opencontext.tools.operation_tools.minimax_base import MiniMaxBaseTool
from opencontext.tools.tool_response import ToolResponse, ToolType
from opencontext.utils.logging_utils import get_logger

logger = get_logger(__name__)


class MinimaxImageUnderstandingTool(MiniMaxBaseTool):
    """
    MiniMax image understanding tool backed by the official MiniMax MCP server.
    """

    DEFAULT_TTL = 86400  # 24 hours (images don't change)

    @classmethod
    def get_name(cls) -> str:
        return "minimax_image_understanding"

    @classmethod
    def get_description(cls) -> str:
        return """AI-powered image understanding tool that analyzes images using MiniMax's vision model.

**When to use this tool:**
- When the user asks about an image, screenshot, or picture
- When you need to describe, identify, or extract information from an image
- When the query contains "what is this", "describe this", or similar

**Supported formats:**
- JPEG, PNG, GIF, WebP
- Maximum file size: 20MB

**Output format:**
- Returns detailed description of image content
- Includes detected objects, text, and other elements
- LLM-friendly structured output

**Best practices:**
- Provide a clear prompt describing what information you need
- Results are cached for 24 hours
- Works best with clear, well-lit images
"""

    @classmethod
    def get_parameters(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Question or instruction about the image (e.g., 'What is shown?', 'Extract text from this image')",
                },
                "image_url": {
                    "type": "string",
                    "description": "Image input to analyze: HTTP/HTTPS URL, local file path, or data:image URL",
                },
            },
            "required": ["prompt", "image_url"],
        }

    def get_type(self) -> str:
        return ToolType.IMAGE_UNDERSTANDING.value

    async def _execute_api_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute image understanding through the official MiniMax MCP server."""
        prompt = params["prompt"]
        image_url = params["image_url"]
        timeout_seconds = float(params.get("timeout_seconds", 30.0))
        logger.info(f"MiniMax MCP image understanding: {image_url}")

        client = await get_minimax_mcp_client(self._api_key, self._base_url)
        content = await client.call_tool_text(
            "understand_image",
            {"prompt": prompt, "image_source": image_url},
            timeout_seconds=timeout_seconds,
        )
        return {"content": content}

    def _format_summary(self, data: Any, params: Dict[str, Any]) -> str:
        """Return MCP text output directly for downstream prompts."""
        content = data.get("content", "").strip()
        return content or "Image analyzed successfully"

    def _calculate_confidence(self, data: Any) -> float:
        """Estimate confidence from the amount of MCP text returned."""
        content = data.get("content", "").strip()
        if len(content) >= 200:
            return 0.95
        if len(content) >= 80:
            return 0.9
        if len(content) >= 20:
            return 0.75
        if content:
            return 0.6
        return 0.0

    @staticmethod
    def _normalize_image_source(image_url: str) -> str:
        """Normalize local paths without changing URL-like inputs."""
        if not image_url:
            return image_url
        if image_url.startswith(("http://", "https://", "data:")):
            return image_url
        return os.path.expanduser(image_url)

    @staticmethod
    def _looks_like_local_path(image_url: str) -> bool:
        expanded = os.path.expanduser(image_url or "")
        return any(
            [
                expanded.startswith((".", "~")),
                os.path.sep in expanded,
                os.path.altsep and os.path.altsep in expanded,
                len(expanded) > 1 and expanded[1] == ":",
            ]
        )

    async def execute_async(self, **kwargs) -> ToolResponse:
        """
        Override to add validation.
        """
        prompt = kwargs.get("prompt", "")
        image_url = self._normalize_image_source(kwargs.get("image_url", ""))

        if not prompt or len(prompt.strip()) == 0:
            return ToolResponse.error(
                tool_type=self.get_type(),
                error_message="Prompt cannot be empty",
                confidence=0.0,
            )

        if not image_url:
            return ToolResponse.error(
                tool_type=self.get_type(),
                error_message="image_url is required",
                confidence=0.0,
            )

        if image_url.startswith("data:image/") or image_url.startswith(("http://", "https://")):
            kwargs["image_url"] = image_url
            return await super().execute_async(**kwargs)

        if image_url.startswith("file://"):
            return ToolResponse.error(
                tool_type=self.get_type(),
                error_message="file:// URLs are not supported; pass a local filesystem path instead",
                confidence=0.0,
            )

        if "://" in image_url:
            return ToolResponse.error(
                tool_type=self.get_type(),
                error_message="image_url must be an http(s) URL, a local file path, or a data:image URL",
                confidence=0.0,
            )

        if os.path.exists(image_url):
            kwargs["image_url"] = image_url
            return await super().execute_async(**kwargs)

        if self._looks_like_local_path(image_url):
            return ToolResponse.error(
                tool_type=self.get_type(),
                error_message=f"Local image file does not exist: {image_url}",
                confidence=0.0,
            )

        return ToolResponse.error(
            tool_type=self.get_type(),
            error_message="image_url must be an http(s) URL, a local file path, or a data:image URL",
            confidence=0.0,
        )

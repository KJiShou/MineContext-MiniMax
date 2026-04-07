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

import httpx

from opencontext.tools.operation_tools.minimax_base import MiniMaxBaseTool
from opencontext.tools.tool_response import ToolResponse, ToolType
from opencontext.utils.logging_utils import get_logger

logger = get_logger(__name__)


class MinimaxImageUnderstandingTool(MiniMaxBaseTool):
    """
    MiniMax image understanding tool.

    API: POST /v1/images/understand
    Docs: https://platform.minimax.io/docs/guides/token-plan-mcp-guide

    Supports: JPEG, PNG, GIF, WebP (max 20MB)
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
                    "description": "URL of the image to analyze (http:// or https://)",
                    "format": "uri",
                },
            },
            "required": ["prompt", "image_url"],
        }

    def get_type(self) -> str:
        return ToolType.IMAGE_UNDERSTANDING.value

    async def _execute_api_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the MiniMax image understanding API call."""
        prompt = params["prompt"]
        image_url = params["image_url"]

        url = f"{self._base_url}/v1/images/understand"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "mini-m3.5-10M",
            "prompt": prompt,
            "image_url": image_url,
        }

        logger.info(f"MiniMax image understanding: {image_url}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    def _format_summary(self, data: Any, params: Dict[str, Any]) -> str:
        """
        Format LLM-friendly summary.

        Returns concise description of image content.
        """
        description = data.get("description", "")
        label = data.get("label", "")

        if description:
            # Truncate long descriptions for summary
            if len(description) > 200:
                description = description[:200] + "..."
            return description

        if label:
            return f"Image labeled: {label}"

        return "Image analyzed successfully"

    def _calculate_confidence(self, data: Any) -> float:
        """
        Calculate confidence based on response quality.

        Returns:
            0.9+ : High confidence - detailed description with high score
            0.7+ : Medium confidence - description present
            0.5+ : Low confidence - minimal description
            0.0  : No usable data
        """
        description = data.get("description", "")
        label = data.get("label", "")
        score = data.get("score", 0.5)

        if description and len(description) > 50:
            return min(0.95, 0.6 + score * 0.35)

        if description or label:
            return 0.7

        return 0.5

    async def execute_async(self, **kwargs) -> ToolResponse:
        """
        Override to add validation.
        """
        prompt = kwargs.get("prompt", "")
        image_url = kwargs.get("image_url", "")

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

        # Validate URL format
        if not image_url.startswith(("http://", "https://")):
            return ToolResponse.error(
                tool_type=self.get_type(),
                error_message="image_url must start with http:// or https://",
                confidence=0.0,
            )

        return await super().execute_async(**kwargs)

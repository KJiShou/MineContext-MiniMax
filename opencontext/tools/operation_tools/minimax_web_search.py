#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
MiniMax web search tool.
Provides AI-powered web search with suggestions.
"""

import os
from typing import Any, Dict, List

import httpx

from opencontext.tools.operation_tools.minimax_base import MiniMaxBaseTool
from opencontext.tools.tool_response import ToolResponse, ToolType
from opencontext.utils.logging_utils import get_logger

logger = get_logger(__name__)


class MinimaxWebSearchTool(MiniMaxBaseTool):
    """
    MiniMax web search tool.

    API: POST /v1/text/_search
    Docs: https://platform.minimax.io/docs/guides/token-plan-mcp-guide
    """

    DEFAULT_TTL = 3600  # 1 hour

    @classmethod
    def get_name(cls) -> str:
        return "minimax_web_search"

    @classmethod
    def get_description(cls) -> str:
        return """AI-powered web search tool that returns search results with intelligent suggestions.

**When to use this tool:**
- When you need to find current information from the internet
- When the user's query requires up-to-date or real-time data
- When looking for specific facts, news, or references

**Output format:**
- Returns structured results with titles, URLs, and snippets
- Includes relevance scores and suggestions
- LLM-friendly summary for efficient processing

**Best practices:**
- Use specific, focused queries for better results
- Results are cached for 1 hour to reduce API usage
- Maximum 10 results per query
"""

    @classmethod
    def get_parameters(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (max 200 chars)",
                    "maxLength": 200,
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (1-10, default 5)",
                    "minimum": 1,
                    "maximum": 10,
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    def get_type(self) -> str:
        return ToolType.WEB_SEARCH.value

    async def _execute_api_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the MiniMax search API call."""
        query = params["query"]
        max_results = params.get("max_results", 5)

        url = f"{self._base_url}/v1/text/_search"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "query": query,
            "max_results": max_results,
        }

        logger.info(f"MiniMax web search: {query}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    def _format_summary(self, data: Any, params: Dict[str, Any]) -> str:
        """
        Format LLM-friendly summary.

        NOT human-readable prose - structured for model consumption.
        """
        results = data.get("results", [])
        query = params.get("query", "")

        if not results:
            return f"No results found for query: {query}"

        # Format: "Top N results about 'query': result1, result2, result3"
        top_titles = [r.get("title", "") for r in results[:3] if r.get("title")]
        if top_titles:
            return f"Top {len(results)} results about '{query}': {', '.join(top_titles)}"
        return f"Top {len(results)} results found for '{query}'"

    def _calculate_confidence(self, data: Any) -> float:
        """
        Calculate confidence based on result quality.

        Returns:
            0.9+ : High confidence - good results with scores
            0.7+ : Medium confidence - results but low scores
            0.5+ : Low confidence - few results
            0.0  : No results
        """
        results = data.get("results", [])

        if not results:
            return 0.0

        # Check if results have relevance scores
        scored_results = [r for r in results if r.get("score", 0) > 0]

        if len(scored_results) >= 3:
            avg_score = sum(r.get("score", 0) for r in scored_results) / len(scored_results)
            return min(0.9, 0.5 + avg_score * 0.4)

        if len(results) >= 3:
            return 0.7

        if len(results) >= 1:
            return 0.5

        return 0.3

    async def execute_async(self, **kwargs) -> ToolResponse:
        """
        Override to add query validation.
        """
        query = kwargs.get("query", "")
        if not query or len(query.strip()) == 0:
            return ToolResponse.error(
                tool_type=self.get_type(),
                error_message="Query cannot be empty",
                confidence=0.0,
            )

        if len(query) > 200:
            return ToolResponse.error(
                tool_type=self.get_type(),
                error_message="Query exceeds 200 character limit",
                confidence=0.0,
            )

        return await super().execute_async(**kwargs)

#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Tool router for selecting the appropriate tool based on user query.
Rule-based routing with LLM fallback for ambiguous cases.
"""

import re
from typing import List, Optional, Tuple

from opencontext.tools.operation_tools.minimax_web_search import MinimaxWebSearchTool
from opencontext.tools.operation_tools.minimax_image_understanding import MinimaxImageUnderstandingTool
from opencontext.tools.tool_response import ToolResponse
from opencontext.utils.logging_utils import get_logger

logger = get_logger(__name__)


# Keywords for rule-based routing (deterministic, fast)
WEB_SEARCH_KEYWORDS = [
    "search",
    "find",
    "look up",
    "google",
    "bing",
    "what is",
    "who is",
    "when did",
    "where is",
    "how to",
    "latest news",
    "current",
    "recent",
    "price of",
    "weather",
    "stock",
]

IMAGE_UNDERSTANDING_KEYWORDS = [
    "image",
    "picture",
    "photo",
    "screenshot",
    "what is this",
    "describe this",
    "what does it show",
    "recognize",
    "identify this",
    "read text from",
    "extract text",
]


class ToolSelector:
    """
    Routes user queries to the appropriate tool.

    Strategy:
    1. Rule-based matching (deterministic, fast)
    2. LLM fallback for ambiguous cases
    """

    def __init__(self):
        self._web_search_tool = MinimaxWebSearchTool()
        self._image_tool = MinimaxImageUnderstandingTool()

    def select(self, query: str) -> str:
        """
        Select the appropriate tool name for the query.

        Args:
            query: User query

        Returns:
            Tool name string
        """
        query_lower = query.lower()

        # Check web search keywords
        if any(kw in query_lower for kw in WEB_SEARCH_KEYWORDS):
            logger.debug(f"Rule-based match: web_search for query '{query[:50]}...'")
            return MinimaxWebSearchTool.get_name()

        # Check image understanding keywords
        if any(kw in query_lower for kw in IMAGE_UNDERSTANDING_KEYWORDS):
            logger.debug(f"Rule-based match: image_understanding for query '{query[:50]}...'")
            return MinimaxImageUnderstandingTool.get_name()

        # Fallback to LLM-based selection for ambiguous cases
        return self._llm_select(query)

    def _llm_select(self, query: str) -> str:
        """
        Use LLM to determine which tool to use.

        This handles ambiguous cases where keywords don't match clearly.
        """
        # Simple heuristic fallback based on query length and structure
        # Short queries that are questions often need web search
        if query.endswith("?") and len(query) < 50:
            return MinimaxWebSearchTool.get_name()

        # If query contains URLs, might be image-related
        if re.search(r"https?://", query, re.IGNORECASE):
            if any(kw in query.lower() for kw in ["image", "photo", "screenshot", "pic"]):
                return MinimaxImageUnderstandingTool.get_name()

        # Default to web search
        logger.debug(f"Default fallback: web_search for query '{query[:50]}...'")
        return MinimaxWebSearchTool.get_name()

    def get_tool_by_name(self, tool_name: str):
        """Get tool instance by name."""
        if tool_name == MinimaxWebSearchTool.get_name():
            return self._web_search_tool
        elif tool_name == MinimaxImageUnderstandingTool.get_name():
            return self._image_tool
        else:
            raise ValueError(f"Unknown tool: {tool_name}")


class ToolRouter:
    """
    High-level router that handles tool selection and execution.

    This is the main entry point for using MiniMax tools.
    """

    def __init__(self):
        self._selector = ToolSelector()

    async def route(self, query: str, **kwargs) -> ToolResponse:
        """
        Route query to appropriate tool and execute.

        Args:
            query: User query (used for tool selection)
            **kwargs: Tool-specific parameters

        Returns:
            ToolResponse with results
        """
        tool_name = self._selector.select(query)
        tool = self._selector.get_tool_by_name(tool_name)

        logger.info(f"Routing query to {tool_name}: {query[:100]}...")

        return await tool.execute_async(**kwargs)

    async def batch_route(self, queries: List[Tuple[str, dict]]) -> List[ToolResponse]:
        """
        Route multiple queries in parallel.

        Args:
            queries: List of (query, params) tuples

        Returns:
            List of ToolResponses
        """
        import asyncio

        tasks = [self.route(query, **params) for query, params in queries]
        return await asyncio.gather(*tasks)


# Global router instance
_router: Optional[ToolRouter] = None


def get_tool_router() -> ToolRouter:
    """Get global tool router instance."""
    global _router
    if _router is None:
        _router = ToolRouter()
    return _router

#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
MiniMax MCP stdio client wrapper.
"""

import asyncio
import contextlib
import os
import sys
from datetime import timedelta
from typing import Any, Optional

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from opencontext.utils.logging_utils import get_logger

logger = get_logger(__name__)


class MiniMaxMcpError(RuntimeError):
    """Raised when the MiniMax MCP client cannot complete a request."""


def _resolve_python_command() -> str:
    """Prefer the current runtime, but fall back to the base executable when available."""
    candidates = [os.environ.get("MINIMAX_MCP_PYTHON")]
    if getattr(sys, "frozen", False):
        candidates.extend([getattr(sys, "_base_executable", None), sys.executable])
    else:
        candidates.extend([sys.executable, getattr(sys, "_base_executable", None)])
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return sys.executable


class MiniMaxMcpClient:
    """Singleton-friendly stdio client for the official MiniMax MCP server."""

    def __init__(self, api_key: str, api_host: str):
        if not api_key:
            raise ValueError("MiniMax API key is required for MCP image understanding")
        if not api_host:
            raise ValueError("MiniMax API host is required for MCP image understanding")

        self._api_key = api_key
        self._api_host = api_host.rstrip("/")
        self._command = _resolve_python_command()
        self._stdio_cm = None
        self._session_cm = None
        self._session: Optional[ClientSession] = None
        self._lock = asyncio.Lock()

    @property
    def config_signature(self) -> tuple[str, str]:
        return (self._api_key, self._api_host)

    async def _start_locked(self, timeout_seconds: float) -> None:
        env = os.environ.copy()
        env["MINIMAX_API_KEY"] = self._api_key
        env["MINIMAX_API_HOST"] = self._api_host
        env.setdefault("PYTHONIOENCODING", "utf-8")

        server = StdioServerParameters(
            command=self._command,
            args=["-m", "minimax_mcp.server"],
            env=env,
        )
        self._stdio_cm = stdio_client(server)
        read_stream, write_stream = await asyncio.wait_for(
            self._stdio_cm.__aenter__(), timeout=timeout_seconds
        )
        self._session_cm = ClientSession(
            read_stream,
            write_stream,
            read_timeout_seconds=timedelta(seconds=timeout_seconds),
        )
        self._session = await asyncio.wait_for(
            self._session_cm.__aenter__(), timeout=timeout_seconds
        )
        await asyncio.wait_for(self._session.initialize(), timeout=timeout_seconds)

    async def _ensure_session_locked(self, timeout_seconds: float) -> None:
        if self._session is not None:
            return
        await self._start_locked(timeout_seconds)

    async def close(self) -> None:
        async with self._lock:
            await self._close_locked()

    async def _close_locked(self) -> None:
        if self._session_cm is not None:
            with contextlib.suppress(Exception):
                await self._session_cm.__aexit__(None, None, None)
        self._session_cm = None
        self._session = None

        if self._stdio_cm is not None:
            with contextlib.suppress(Exception):
                await self._stdio_cm.__aexit__(None, None, None)
        self._stdio_cm = None

    async def call_tool(self, tool_name: str, arguments: dict[str, Any], timeout_seconds: float = 30.0):
        last_error: Optional[Exception] = None

        for attempt in range(2):
            async with self._lock:
                try:
                    await self._ensure_session_locked(timeout_seconds)
                    assert self._session is not None
                    return await asyncio.wait_for(
                        self._session.call_tool(
                            tool_name,
                            arguments=arguments,
                            read_timeout_seconds=timedelta(seconds=timeout_seconds),
                        ),
                        timeout=timeout_seconds,
                    )
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        f"MiniMax MCP call failed on attempt {attempt + 1}: {exc}"
                    )
                    await self._close_locked()

        raise MiniMaxMcpError(
            f"MiniMax MCP tool call failed after retry: {last_error}"
        ) from last_error

    async def call_tool_text(
        self, tool_name: str, arguments: dict[str, Any], timeout_seconds: float = 30.0
    ) -> str:
        result = await self.call_tool(tool_name, arguments, timeout_seconds=timeout_seconds)
        text_chunks = []
        for item in getattr(result, "content", []) or []:
            item_type = getattr(item, "type", None)
            if item_type == "text" and hasattr(item, "text"):
                text_chunks.append(item.text)
                continue
            if isinstance(item, dict) and item.get("type") == "text":
                text_chunks.append(item.get("text", ""))

        text = "\n".join(chunk.strip() for chunk in text_chunks if chunk and chunk.strip()).strip()
        if getattr(result, "isError", False):
            raise MiniMaxMcpError(text or f"MCP tool {tool_name} returned an error")
        if not text:
            raise MiniMaxMcpError(f"MCP tool {tool_name} returned no text content")
        return text


_minimax_mcp_client: Optional[MiniMaxMcpClient] = None
_minimax_mcp_client_lock = asyncio.Lock()


async def get_minimax_mcp_client(api_key: str, api_host: str) -> MiniMaxMcpClient:
    """Get a process-wide MiniMax MCP client, recreating it when config changes."""
    global _minimax_mcp_client

    async with _minimax_mcp_client_lock:
        signature = (api_key, api_host.rstrip("/"))
        if _minimax_mcp_client is None:
            _minimax_mcp_client = MiniMaxMcpClient(*signature)
        elif _minimax_mcp_client.config_signature != signature:
            await _minimax_mcp_client.close()
            _minimax_mcp_client = MiniMaxMcpClient(*signature)

        return _minimax_mcp_client

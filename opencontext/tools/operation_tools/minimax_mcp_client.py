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
import shutil
import subprocess
import sys
import threading
import weakref
from datetime import timedelta
from typing import Any, Optional

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from opencontext.utils.logging_utils import get_logger

logger = get_logger(__name__)


class MiniMaxMcpError(RuntimeError):
    """Raised when the MiniMax MCP client cannot complete a request."""


def _is_executable_candidate(candidate: Optional[str]) -> bool:
    if not candidate:
        return False
    if os.path.isabs(candidate):
        return os.path.exists(candidate)
    return shutil.which(candidate) is not None


def _can_import_minimax_mcp_with_python(command: str) -> bool:
    if not _is_executable_candidate(command):
        return False

    try:
        result = subprocess.run(
            [
                command,
                "-c",
                "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('minimax_mcp.server') else 1)",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        return result.returncode == 0
    except Exception:
        return False


def _resolve_mcp_server_command() -> tuple[str, list[str], str]:
    """
    Resolve the best way to launch the MiniMax MCP server.

    In frozen builds, prefer the bundled backend executable with a hidden subcommand.
    Otherwise, prefer a Python runtime that can import `minimax_mcp.server`.
    """
    if getattr(sys, "frozen", False):
        command = sys.executable
        if _is_executable_candidate(command):
            return command, ["run-minimax-mcp-server"], "bundled-backend-subcommand"

    explicit_command = os.environ.get("MINIMAX_MCP_COMMAND")
    if explicit_command and _is_executable_candidate(explicit_command):
        return explicit_command, [], "env:MINIMAX_MCP_COMMAND"

    python_candidates = [
        os.environ.get("MINIMAX_MCP_PYTHON"),
        sys.executable,
        getattr(sys, "_base_executable", None),
        shutil.which("python"),
        shutil.which("py"),
    ]
    seen = set()
    for candidate in python_candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if _can_import_minimax_mcp_with_python(candidate):
            return candidate, ["-m", "minimax_mcp.server"], "python-module"

    fallback = sys.executable
    return fallback, ["-m", "minimax_mcp.server"], "fallback-python-module"


class MiniMaxMcpClient:
    """Singleton-friendly stdio client for the official MiniMax MCP server."""

    def __init__(self, api_key: str, api_host: str):
        if not api_key:
            raise ValueError("MiniMax API key is required for MCP image understanding")
        if not api_host:
            raise ValueError("MiniMax API host is required for MCP image understanding")

        self._api_key = api_key
        self._api_host = api_host.rstrip("/")
        self._command, self._args, self._launch_mode = _resolve_mcp_server_command()
        self._stdio_cm = None
        self._session_cm = None
        self._session: Optional[ClientSession] = None
        self._lock = asyncio.Lock()

    @property
    def config_signature(self) -> tuple[str, str]:
        return (self._api_key, self._api_host)

    def describe_runtime(self) -> str:
        return (
            f"launch_mode={self._launch_mode}, command={self._command}, "
            f"args={self._args}, frozen={getattr(sys, 'frozen', False)}, "
            f"sys.executable={sys.executable}, base_executable={getattr(sys, '_base_executable', None)}"
        )

    async def _start_locked(self, timeout_seconds: float) -> None:
        env = os.environ.copy()
        env["MINIMAX_API_KEY"] = self._api_key
        env["MINIMAX_API_HOST"] = self._api_host
        env.setdefault("PYTHONIOENCODING", "utf-8")

        logger.info(f"Starting MiniMax MCP stdio client with {self.describe_runtime()}")

        server = StdioServerParameters(
            command=self._command,
            args=self._args,
            env=env,
        )
        try:
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
        except Exception as exc:
            logger.exception(
                f"Failed to start MiniMax MCP stdio client ({self.describe_runtime()}): {exc}"
            )
            raise

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
                    logger.error(
                        f"MiniMax MCP call failed on attempt {attempt + 1} ({self.describe_runtime()}): {exc}"
                    )
                    await self._close_locked()

        raise MiniMaxMcpError(
            f"MiniMax MCP tool call failed after retry: {last_error} [{self.describe_runtime()}]"
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


_minimax_mcp_clients: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, MiniMaxMcpClient]" = (
    weakref.WeakKeyDictionary()
)
_minimax_mcp_clients_lock = threading.Lock()


async def get_minimax_mcp_client(api_key: str, api_host: str) -> MiniMaxMcpClient:
    """
    Get a MiniMax MCP client scoped to the current event loop.

    The screenshot pipeline creates fresh event loops via `asyncio.run(...)`.
    Reusing asyncio primitives across loops causes `bound to a different event loop`
    errors, so each loop needs its own client instance.
    """
    loop = asyncio.get_running_loop()
    signature = (api_key, api_host.rstrip("/"))

    stale_client: Optional[MiniMaxMcpClient] = None
    with _minimax_mcp_clients_lock:
        client = _minimax_mcp_clients.get(loop)
        if client is None:
            client = MiniMaxMcpClient(*signature)
            _minimax_mcp_clients[loop] = client
            return client

        if client.config_signature != signature:
            stale_client = client
            client = MiniMaxMcpClient(*signature)
            _minimax_mcp_clients[loop] = client
        else:
            return client

    if stale_client is not None:
        await stale_client.close()
    return client


def create_minimax_mcp_client(api_key: str, api_host: str) -> MiniMaxMcpClient:
    """Create a dedicated MiniMax MCP client for a single request."""
    return MiniMaxMcpClient(api_key, api_host.rstrip("/"))

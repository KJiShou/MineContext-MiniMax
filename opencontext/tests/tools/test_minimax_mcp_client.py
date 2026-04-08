#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import sys
from unittest.mock import AsyncMock, patch

from opencontext.tools.operation_tools.minimax_mcp_client import (
    MiniMaxMcpClient,
    _resolve_mcp_server_command,
    get_minimax_mcp_client,
)


class TestResolveMcpServerCommand:
    def test_frozen_build_uses_bundled_backend_subcommand(self):
        with patch.object(sys, "frozen", True, create=True), patch.object(
            sys, "executable", "C:\\bundle\\main.exe"
        ), patch(
            "opencontext.tools.operation_tools.minimax_mcp_client._is_executable_candidate",
            return_value=True,
        ):
            command, args, launch_mode = _resolve_mcp_server_command()

        assert command == "C:\\bundle\\main.exe"
        assert args == ["run-minimax-mcp-server"]
        assert launch_mode == "bundled-backend-subcommand"

    def test_non_frozen_prefers_python_that_can_import_minimax_mcp(self):
        with patch.object(sys, "frozen", False, create=True), patch.object(
            sys, "executable", "C:\\venv\\python.exe"
        ), patch(
            "opencontext.tools.operation_tools.minimax_mcp_client._can_import_minimax_mcp_with_python",
            side_effect=lambda command: command == "C:\\venv\\python.exe",
        ), patch(
            "opencontext.tools.operation_tools.minimax_mcp_client.shutil.which",
            return_value=None,
        ):
            command, args, launch_mode = _resolve_mcp_server_command()

        assert command == "C:\\venv\\python.exe"
        assert args == ["-m", "minimax_mcp.server"]
        assert launch_mode == "python-module"


class TestMiniMaxMcpClient:
    def test_describe_runtime_includes_launch_metadata(self):
        with patch(
            "opencontext.tools.operation_tools.minimax_mcp_client._resolve_mcp_server_command",
            return_value=("C:\\bundle\\main.exe", ["run-minimax-mcp-server"], "bundled"),
        ):
            client = MiniMaxMcpClient("key", "https://api.minimax.io")

        details = client.describe_runtime()
        assert "launch_mode=bundled" in details
        assert "command=C:\\bundle\\main.exe" in details
        assert "run-minimax-mcp-server" in details

    def test_get_minimax_mcp_client_scopes_instances_per_event_loop(self):
        created = []

        def make_client(*args):
            client = AsyncMock()
            client.config_signature = (args[0], args[1].rstrip("/"))
            created.append(client)
            return client

        with patch(
            "opencontext.tools.operation_tools.minimax_mcp_client.MiniMaxMcpClient",
            side_effect=make_client,
        ):
            loop_a = asyncio.new_event_loop()
            loop_b = asyncio.new_event_loop()
            try:
                with patch(
                    "opencontext.tools.operation_tools.minimax_mcp_client.asyncio.get_running_loop",
                    side_effect=[loop_a, loop_a, loop_b],
                ):
                    client_a1 = asyncio.run(
                        get_minimax_mcp_client("key", "https://api.minimax.io")
                    )
                    client_a2 = asyncio.run(
                        get_minimax_mcp_client("key", "https://api.minimax.io")
                    )
                    client_b = asyncio.run(
                        get_minimax_mcp_client("key", "https://api.minimax.io")
                    )
            finally:
                loop_a.close()
                loop_b.close()

        assert client_a1 is client_a2
        assert client_b is not client_a1

    def test_get_minimax_mcp_client_replaces_client_when_signature_changes(self):
        first_client = AsyncMock()
        first_client.config_signature = ("key-a", "https://api.minimax.io")
        second_client = AsyncMock()
        second_client.config_signature = ("key-b", "https://api.minimax.io")

        with patch(
            "opencontext.tools.operation_tools.minimax_mcp_client.MiniMaxMcpClient",
            side_effect=[first_client, second_client],
        ):
            loop = asyncio.new_event_loop()
            try:
                with patch(
                    "opencontext.tools.operation_tools.minimax_mcp_client.asyncio.get_running_loop",
                    return_value=loop,
                ):
                    client_a = asyncio.run(
                        get_minimax_mcp_client("key-a", "https://api.minimax.io")
                    )
                    client_b = asyncio.run(
                        get_minimax_mcp_client("key-b", "https://api.minimax.io")
                    )
            finally:
                loop.close()

        assert client_a is first_client
        assert client_b is second_client
        first_client.close.assert_awaited_once()

# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Common utilities for API routes
"""

import json
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from opencontext.server.opencontext import OpenContext
from opencontext.utils.json_encoder import CustomJSONEncoder

THINK_OPEN_TAG = "<think"
THINK_CLOSE_TAG = "</think"
THINK_OPEN_TAG_ALT = "<think>"
THINK_CLOSE_TAG_ALT = "</think>"


def get_context_lab(request: Request) -> OpenContext:
    """Dependency to get OpenContext instance"""
    context_lab_instance = getattr(request.app.state, "context_lab_instance", None)
    if not context_lab_instance:
        raise HTTPException(status_code=500, detail="OpenContext instance not initialized")
    return context_lab_instance


def convert_resp(data: Any = None, code: int = 0, status: int = 200, message: str = "success"):
    """Convert response to standard JSON format"""
    content = {
        "code": code,
        "status": status,
        "message": message,
    }
    if data is not None:
        content["data"] = data

    # Use CustomJSONEncoder to handle datetime and other special types
    json_content = json.dumps(content, cls=CustomJSONEncoder)
    return JSONResponse(status_code=status, content=json.loads(json_content))


def sanitize_assistant_content(content: Any) -> str:
    """Remove leaked ...</think> blocks from assistant-visible content."""
    if not content:
        return ""

    source = str(content)
    lower_source = source.lower()
    result = []

    index = 0
    inside_think_block = False
    think_open = THINK_OPEN_TAG
    think_close = THINK_CLOSE_TAG

    while index < len(source):
        if inside_think_block:
            close_index = lower_source.find(think_close, index)
            if close_index == -1:
                break

            close_end = source.find(">", close_index)
            if close_end == -1:
                break

            index = close_end + 1
            inside_think_block = False
            continue

        next_tag_start = source.find("<", index)
        if next_tag_start == -1:
            result.append(source[index:])
            break

        result.append(source[index:next_tag_start])
        remaining_lower = lower_source[next_tag_start:]

        if remaining_lower.startswith(think_open):
            open_end = source.find(">", next_tag_start)
            if open_end == -1:
                break

            index = open_end + 1
            inside_think_block = True
            continue

        if remaining_lower.startswith(think_close):
            close_end = source.find(">", next_tag_start)
            if close_end == -1:
                break

            index = close_end + 1
            continue

        # Check for alternate think tag format (...</think>)
        if remaining_lower.startswith(THINK_OPEN_TAG_ALT):
            open_end = source.find(">", next_tag_start)
            if open_end == -1:
                break

            index = open_end + 1
            inside_think_block = True
            think_open = THINK_OPEN_TAG_ALT
            think_close = THINK_CLOSE_TAG_ALT
            continue

        if remaining_lower.startswith(THINK_CLOSE_TAG_ALT):
            close_end = source.find(">", next_tag_start)
            if close_end == -1:
                break

            index = close_end + 1
            continue

        possible_partial_tag = ""
        for char in remaining_lower:
            if char == ">" or not (char.isalpha() or char in "<>/"):
                break
            possible_partial_tag += char

        if len(possible_partial_tag) > 1 and (
            think_open.startswith(possible_partial_tag)
            or think_close.startswith(possible_partial_tag)
            or THINK_OPEN_TAG_ALT.startswith(possible_partial_tag)
            or THINK_CLOSE_TAG_ALT.startswith(possible_partial_tag)
        ):
            break

        result.append(source[next_tag_start])
        index = next_tag_start + 1

    return "".join(result)

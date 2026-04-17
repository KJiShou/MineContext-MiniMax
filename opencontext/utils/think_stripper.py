# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Think tag stripping utilities for removing internal AI reasoning from output.
"""

from typing import Any

THINK_OPEN_TAG = "<think"
THINK_CLOSE_TAG = "</think"
THINK_OPEN_TAG_ALT = "<think>"
THINK_CLOSE_TAG_ALT = ""


def sanitize_assistant_content(content: Any) -> str:
    """Remove leaked ... blocks from assistant-visible content."""
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

        # Check for alternate think tag format (...)
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
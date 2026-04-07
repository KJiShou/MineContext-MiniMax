#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Standardized tool response schema for LLM stability.
Forces consistent output format so LLMs can reliably use tools.
"""

from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from enum import Enum


class ToolStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


class ToolType(str, Enum):
    WEB_SEARCH = "web_search"
    IMAGE_UNDERSTANDING = "image_understanding"


@dataclass
class ToolResponse:
    """
    Standardized tool response schema.

    This forces LLM-friendly output format so models can reliably use tools
    without hallucinating, misinterpreting, or over-calling.
    """

    status: str  # "success" | "error" | "partial"
    type: str  # Tool type identifier
    data: Any  # Structured data payload
    confidence: float  # 0.0-1.0, how confident the tool is in the result
    cached: bool = False  # Whether result came from cache
    error_message: Optional[str] = None  # Error details if status != success
    summary: str = ""  # LLM-friendly summary, model-parsable format

    def __post_init__(self):
        # Validate status
        if self.status not in [s.value for s in ToolStatus]:
            raise ValueError(f"Invalid status: {self.status}")

        # Validate confidence range
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")

    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        result = asdict(self)
        if result["error_message"] is None:
            del result["error_message"]
        return result

    @classmethod
    def success(
        cls,
        tool_type: str,
        data: Any,
        confidence: float = 1.0,
        cached: bool = False,
        summary: str = "",
    ) -> "ToolResponse":
        """Create a success response."""
        return cls(
            status=ToolStatus.SUCCESS.value,
            type=tool_type,
            data=data,
            confidence=confidence,
            cached=cached,
            summary=summary,
        )

    @classmethod
    def error(
        cls,
        tool_type: str,
        error_message: str,
        data: Any = None,
        confidence: float = 0.0,
    ) -> "ToolResponse":
        """Create an error response."""
        return cls(
            status=ToolStatus.ERROR.value,
            type=tool_type,
            data=data,
            confidence=confidence,
            error_message=error_message,
            summary=f"Error: {error_message}",
        )

    @classmethod
    def partial(
        cls,
        tool_type: str,
        data: Any,
        error_message: str,
        confidence: float = 0.5,
    ) -> "ToolResponse":
        """Create a partial response (partial success with issues)."""
        return cls(
            status=ToolStatus.PARTIAL.value,
            type=tool_type,
            data=data,
            confidence=confidence,
            error_message=error_message,
            summary=f"Partial result: {error_message}",
        )

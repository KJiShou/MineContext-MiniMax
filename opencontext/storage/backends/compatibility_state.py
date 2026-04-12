#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from opencontext.config.global_config import get_config
from opencontext.utils.logging_utils import get_logger

logger = get_logger(__name__)

STATE_DIR_NAME = ".vector_backend_state"


def build_embedding_signature(
    backend_name: str, backend_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    embedding_config = get_config("embedding_model") or {}
    backend_options = (backend_config or {}).get("config", {})
    output_dim = embedding_config.get("output_dim")

    if backend_name == "qdrant":
        output_dim = backend_options.get("vector_size", output_dim)

    return {
        "backend": backend_name,
        "model": embedding_config.get("model"),
        "provider": embedding_config.get("provider"),
        "base_url": embedding_config.get("base_url"),
        "output_dim": output_dim,
    }


def load_backend_signature(backend_name: str) -> Optional[Dict[str, Any]]:
    state_path = _get_state_path(backend_name)
    if not state_path.exists():
        return None

    try:
        with state_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        signature = payload.get("signature")
        return signature if isinstance(signature, dict) else None
    except Exception as e:
        logger.warning(f"Failed to read vector backend state from {state_path}: {e}")
        return None


def save_backend_signature(backend_name: str, signature: Dict[str, Any]) -> None:
    state_path = _get_state_path(backend_name)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "backend": backend_name,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "signature": signature,
    }

    with state_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)


def has_signature_changed(backend_name: str, signature: Dict[str, Any]) -> bool:
    previous_signature = load_backend_signature(backend_name)
    return previous_signature is not None and previous_signature != signature


def _get_state_path(backend_name: str) -> Path:
    user_setting_path = get_config("user_setting_path")
    if user_setting_path:
        base_dir = Path(user_setting_path).expanduser().resolve().parent
    else:
        base_dir = Path.cwd() / "config"
    return base_dir / STATE_DIR_NAME / f"{backend_name}.json"

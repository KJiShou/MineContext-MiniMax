#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2025 Beijing Volcano Engine Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from opencontext.storage.backends import compatibility_state


def test_qdrant_signature_prefers_vector_size_override(monkeypatch):
    def fake_get_config(key):
        if key == "embedding_model":
            return {
                "model": "bge-m3",
                "provider": "custom",
                "base_url": "http://localhost:11434/v1",
                "output_dim": 2048,
            }
        if key == "user_setting_path":
            return None
        return None

    monkeypatch.setattr(compatibility_state, "get_config", fake_get_config)

    signature = compatibility_state.build_embedding_signature(
        "qdrant", {"config": {"vector_size": 1024}}
    )

    assert signature["output_dim"] == 1024
    assert signature["model"] == "bge-m3"


def test_saved_backend_signature_detects_user_setting_change(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    user_setting_path = config_dir / "user_setting.yaml"

    def fake_get_config(key):
        if key == "embedding_model":
            return {
                "model": "bge-m3",
                "provider": "custom",
                "base_url": "http://localhost:11434/v1",
                "output_dim": 2048,
            }
        if key == "user_setting_path":
            return str(user_setting_path)
        return None

    monkeypatch.setattr(compatibility_state, "get_config", fake_get_config)

    previous_signature = {
        "backend": "chromadb",
        "model": "nomic-embed-text",
        "provider": "custom",
        "base_url": "http://localhost:11434/v1",
        "output_dim": 768,
    }
    compatibility_state.save_backend_signature("chromadb", previous_signature)

    current_signature = compatibility_state.build_embedding_signature("chromadb", {})

    assert compatibility_state.has_signature_changed("chromadb", current_signature) is True
    state_file = config_dir / compatibility_state.STATE_DIR_NAME / "chromadb.json"
    assert state_file.exists()
    assert Path(state_file).read_text(encoding="utf-8")

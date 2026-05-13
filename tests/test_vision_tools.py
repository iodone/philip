"""Tests for vision settings, client, and tools."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from philip.vision_settings import VisionSettings


def test_vision_settings_read_bub_env(monkeypatch):
    monkeypatch.setenv("BUB_VISION_MODEL", "openai:gpt-4.1-mini")
    monkeypatch.setenv("BUB_VISION_API_KEY", "secret")
    monkeypatch.setenv("BUB_VISION_API_BASE", "https://api.example.com/v1")
    settings = VisionSettings()
    assert settings.model == "openai:gpt-4.1-mini"
    assert settings.api_key == "secret"
    assert settings.api_base == "https://api.example.com/v1"
    assert settings.is_configured is True


def test_vision_settings_not_configured_when_missing(monkeypatch):
    monkeypatch.delenv("BUB_VISION_MODEL", raising=False)
    monkeypatch.delenv("BUB_VISION_API_KEY", raising=False)
    monkeypatch.delenv("BUB_VISION_API_BASE", raising=False)
    settings = VisionSettings()
    assert settings.is_configured is False


def test_vision_settings_partial_config(monkeypatch):
    monkeypatch.setenv("BUB_VISION_MODEL", "openai:gpt-4.1-mini")
    monkeypatch.delenv("BUB_VISION_API_KEY", raising=False)
    monkeypatch.delenv("BUB_VISION_API_BASE", raising=False)
    settings = VisionSettings()
    assert settings.is_configured is False

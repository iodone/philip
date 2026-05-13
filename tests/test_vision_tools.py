"""Tests for vision settings, client, and tools."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

from republic import ToolContext

from philip.vision_settings import VisionSettings


# ---------------------------------------------------------------------------
# Settings tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Tool tests
# ---------------------------------------------------------------------------


@dataclass
class FakeMediaItem:
    """Minimal stand-in for bub.channels.message.MediaItem."""

    url: str | None = None

    async def get_url(self) -> str | None:
        return self.url


def _make_context(media_items: list[dict] | None = None, **extra) -> ToolContext:
    """Build a minimal ToolContext with vision state."""
    state = {
        "vision_current_media": media_items or [],
        "vision_current_image_count": len(media_items) if media_items else 0,
        **extra,
    }
    return ToolContext(tape=None, run_id="test", state=state)


async def test_tool_returns_observation_for_current_images(monkeypatch):
    """Tool calls vision client and returns its observation."""
    from philip.vision_tools import vision_inspect_tool

    monkeypatch.setenv("BUB_VISION_MODEL", "openai:gpt-4.1-mini")
    monkeypatch.setenv("BUB_VISION_API_KEY", "sk-test")
    monkeypatch.setenv("BUB_VISION_API_BASE", "https://api.example.com/v1")

    fake_media = [
        {"media_item": FakeMediaItem(url="data:image/png;base64,abc"), "mime_type": "image/png"}
    ]
    context = _make_context(media_items=fake_media, context="user asks about screenshot")

    with patch("philip.vision_tools.VisionClient") as MockClient:
        instance = MockClient.return_value
        instance.inspect_images = AsyncMock(
            return_value="Image observation: a screenshot showing an error dialog."
        )
        result = await vision_inspect_tool(params=None, context=context)  # type: ignore[arg-type]

    assert "Image observation" in result
    assert "error dialog" in result
    instance.inspect_images.assert_awaited_once()


async def test_tool_returns_readable_error_when_unconfigured(monkeypatch):
    """Tool returns a readable message when vision config is missing."""
    from philip.vision_tools import vision_inspect_tool

    monkeypatch.delenv("BUB_VISION_MODEL", raising=False)
    monkeypatch.delenv("BUB_VISION_API_KEY", raising=False)
    monkeypatch.delenv("BUB_VISION_API_BASE", raising=False)

    context = _make_context()
    result = await vision_inspect_tool(params=None, context=context)  # type: ignore[arg-type]
    assert "unavailable" in result.lower()


async def test_tool_skips_when_no_images(monkeypatch):
    """Tool returns a skip message when no images are in the current message."""
    from philip.vision_tools import vision_inspect_tool

    monkeypatch.setenv("BUB_VISION_MODEL", "openai:gpt-4.1-mini")
    monkeypatch.setenv("BUB_VISION_API_KEY", "sk-test")
    monkeypatch.setenv("BUB_VISION_API_BASE", "https://api.example.com/v1")

    context = _make_context(media_items=[])
    result = await vision_inspect_tool(params=None, context=context)  # type: ignore[arg-type]
    assert "no image" in result.lower()


async def test_tool_applies_max_images(monkeypatch):
    """Tool limits the number of images sent to the vision client."""
    from philip.vision_tools import VisionInspectInput, vision_inspect_tool

    monkeypatch.setenv("BUB_VISION_MODEL", "openai:gpt-4.1-mini")
    monkeypatch.setenv("BUB_VISION_API_KEY", "sk-test")
    monkeypatch.setenv("BUB_VISION_API_BASE", "https://api.example.com/v1")

    fake_media = [
        {"media_item": FakeMediaItem(url="data:image/png;base64,a"), "mime_type": "image/png"},
        {"media_item": FakeMediaItem(url="data:image/png;base64,b"), "mime_type": "image/png"},
        {"media_item": FakeMediaItem(url="data:image/png;base64,c"), "mime_type": "image/png"},
    ]
    context = _make_context(media_items=fake_media)

    with patch("philip.vision_tools.VisionClient") as MockClient:
        instance = MockClient.return_value
        instance.inspect_images = AsyncMock(return_value="observation")

        result = await vision_inspect_tool(
            params=VisionInspectInput(max_images=2),
            context=context,
        )

    assert "observation" in result
    call_args = instance.inspect_images.call_args
    assert len(call_args.kwargs["image_urls"]) == 2


async def test_tool_handles_vision_api_failure(monkeypatch):
    """Tool returns a readable error when the vision API call fails."""
    from philip.vision_tools import vision_inspect_tool

    monkeypatch.setenv("BUB_VISION_MODEL", "openai:gpt-4.1-mini")
    monkeypatch.setenv("BUB_VISION_API_KEY", "sk-test")
    monkeypatch.setenv("BUB_VISION_API_BASE", "https://api.example.com/v1")

    fake_media = [
        {"media_item": FakeMediaItem(url="data:image/png;base64,abc"), "mime_type": "image/png"}
    ]
    context = _make_context(media_items=fake_media)

    with patch("philip.vision_tools.VisionClient") as MockClient:
        instance = MockClient.return_value
        instance.inspect_images = AsyncMock(side_effect=RuntimeError("API timeout"))
        result = await vision_inspect_tool(params=None, context=context)  # type: ignore[arg-type]

    assert "failed" in result.lower()
    assert "API timeout" in result

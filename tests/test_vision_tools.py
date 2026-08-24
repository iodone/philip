"""Tests for vision settings, client, and tools."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

from bub.tools import ToolContext

from philip.tools.vision_client import VisionClient
from philip.tools.vision_settings import VisionSettings

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
    from philip.tools.vision_tools import vision_inspect_tool

    monkeypatch.setenv("BUB_VISION_MODEL", "openai:gpt-4.1-mini")
    monkeypatch.setenv("BUB_VISION_API_KEY", "sk-test")
    monkeypatch.setenv("BUB_VISION_API_BASE", "https://api.example.com/v1")

    fake_media = [
        {
            "media_item": FakeMediaItem(url="data:image/png;base64,abc"),
            "mime_type": "image/png",
        }
    ]
    context = _make_context(
        media_items=fake_media, vision_current_text="user asks about screenshot"
    )

    with patch("philip.tools.vision_tools.VisionClient") as MockClient:
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
    from philip.tools.vision_tools import vision_inspect_tool

    monkeypatch.delenv("BUB_VISION_MODEL", raising=False)
    monkeypatch.delenv("BUB_VISION_API_KEY", raising=False)
    monkeypatch.delenv("BUB_VISION_API_BASE", raising=False)

    context = _make_context()
    result = await vision_inspect_tool(params=None, context=context)  # type: ignore[arg-type]
    assert "unavailable" in result.lower()


async def test_tool_skips_when_no_images(monkeypatch):
    """Tool returns a skip message when no images are in the current message."""
    from philip.tools.vision_tools import vision_inspect_tool

    monkeypatch.setenv("BUB_VISION_MODEL", "openai:gpt-4.1-mini")
    monkeypatch.setenv("BUB_VISION_API_KEY", "sk-test")
    monkeypatch.setenv("BUB_VISION_API_BASE", "https://api.example.com/v1")

    context = _make_context(media_items=[])
    result = await vision_inspect_tool(params=None, context=context)  # type: ignore[arg-type]
    assert "no image" in result.lower()


async def test_tool_applies_max_images(monkeypatch):
    """Tool limits the number of images sent to the vision client."""
    from philip.tools.vision_tools import VisionInspectInput, vision_inspect_tool

    monkeypatch.setenv("BUB_VISION_MODEL", "openai:gpt-4.1-mini")
    monkeypatch.setenv("BUB_VISION_API_KEY", "sk-test")
    monkeypatch.setenv("BUB_VISION_API_BASE", "https://api.example.com/v1")

    fake_media = [
        {
            "media_item": FakeMediaItem(url="data:image/png;base64,a"),
            "mime_type": "image/png",
        },
        {
            "media_item": FakeMediaItem(url="data:image/png;base64,b"),
            "mime_type": "image/png",
        },
        {
            "media_item": FakeMediaItem(url="data:image/png;base64,c"),
            "mime_type": "image/png",
        },
    ]
    context = _make_context(media_items=fake_media)

    with patch("philip.tools.vision_tools.VisionClient") as MockClient:
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
    from philip.tools.vision_tools import vision_inspect_tool

    monkeypatch.setenv("BUB_VISION_MODEL", "openai:gpt-4.1-mini")
    monkeypatch.setenv("BUB_VISION_API_KEY", "sk-test")
    monkeypatch.setenv("BUB_VISION_API_BASE", "https://api.example.com/v1")

    fake_media = [
        {
            "media_item": FakeMediaItem(url="data:image/png;base64,abc"),
            "mime_type": "image/png",
        }
    ]
    context = _make_context(media_items=fake_media)

    with patch("philip.tools.vision_tools.VisionClient") as MockClient:
        instance = MockClient.return_value
        instance.inspect_images = AsyncMock(side_effect=RuntimeError("API timeout"))
        result = await vision_inspect_tool(params=None, context=context)  # type: ignore[arg-type]

    assert "failed" in result.lower()
    assert "API timeout" in result


async def test_tool_passes_message_content_not_metadata_to_vision(monkeypatch):
    """Regression: tool must pass message content (vision_current_text), not
    the builtin context metadata (channel=$...|chat_id=...)."""
    from philip.tools.vision_tools import vision_inspect_tool

    monkeypatch.setenv("BUB_VISION_MODEL", "openai:gpt-4.1-mini")
    monkeypatch.setenv("BUB_VISION_API_KEY", "sk-test")
    monkeypatch.setenv("BUB_VISION_API_BASE", "https://api.example.com/v1")

    fake_media = [
        {
            "media_item": FakeMediaItem(url="data:image/png;base64,abc"),
            "mime_type": "image/png",
        }
    ]
    # Simulate real state: context is metadata,
    # vision_current_text is the actual message
    context = _make_context(
        media_items=fake_media,
        context="channel=$cli|chat_id=default",  # metadata
        vision_current_text="帮我看看这张报错截图怎么修",  # msg
    )

    with patch("philip.tools.vision_tools.VisionClient") as MockClient:
        instance = MockClient.return_value
        instance.inspect_images = AsyncMock(return_value="observation")
        await vision_inspect_tool(params=None, context=context)  # type: ignore[arg-type]

    call_kwargs = instance.inspect_images.call_args.kwargs
    assert call_kwargs["text"] == "帮我看看这张报错截图怎么修"
    assert "channel=" not in call_kwargs["text"]


# ---------------------------------------------------------------------------
# Vision client tests (any-llm amessages path)
# ---------------------------------------------------------------------------


class _FakeBlock:
    def __init__(self, type_: str, text: str | None = None) -> None:
        self.type = type_
        self.text = text


class _FakeResponse:
    def __init__(self, blocks: list[_FakeBlock]) -> None:
        self.content = blocks


async def test_vision_client_uses_amessages_and_extracts_text(monkeypatch):
    """VisionClient calls any_llm.amessages with image content and extracts text."""
    captured: dict = {}

    async def fake_amessages(**kwargs):
        captured.update(kwargs)
        return _FakeResponse(
            [_FakeBlock("text", "可见报错文本：Connection refused"), _FakeBlock("text", "")]
        )

    monkeypatch.setattr("philip.tools.vision_client.amessages", fake_amessages)

    settings = VisionSettings(
        vision_model="openai:gpt-4.1-mini",
        vision_api_key="sk-test",
        vision_api_base="https://api.example.com/v1",
    )
    client = VisionClient(settings)
    result = await client.inspect_images(
        text="看看这张报错截图",
        image_urls=["https://example.com/shot.png"],
    )

    assert captured["model"] == "openai:gpt-4.1-mini"
    assert captured["api_key"] == "sk-test"
    assert captured["api_base"] == "https://api.example.com/v1"
    assert captured["max_tokens"] == 1024
    assert captured["messages"][0]["content"][0]["type"] == "text"
    assert captured["messages"][0]["content"][1]["image_url"]["url"] == (
        "https://example.com/shot.png"
    )
    assert result == "可见报错文本：Connection refused"


async def test_vision_client_fallback_when_no_text(monkeypatch):
    """VisionClient returns the fallback when the model returns no text blocks."""

    async def fake_amessages(**kwargs):
        return _FakeResponse([])

    monkeypatch.setattr("philip.tools.vision_client.amessages", fake_amessages)

    settings = VisionSettings(
        vision_model="openai:gpt-4.1-mini",
        vision_api_key="sk-test",
        vision_api_base="https://api.example.com/v1",
    )
    client = VisionClient(settings)
    result = await client.inspect_images(
        text="", image_urls=["https://example.com/x.png"]
    )
    assert result == "Image observation: no useful visual detail extracted."

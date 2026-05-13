"""Tests for Philip's Bub plugin registration, state injection, and prompt hint."""

from __future__ import annotations

from importlib import metadata

from bub.channels.message import ChannelMessage, MediaItem
from bub.types import State

from philip.plugin import PhilipPlugin


def test_philip_registers_bub_plugin_entry_point():
    entry_points = metadata.entry_points(group="bub")
    assert any(ep.name == "philip" for ep in entry_points)


async def test_load_state_exposes_current_image_media():
    plugin = PhilipPlugin(framework=None)  # type: ignore[arg-type]
    message = ChannelMessage(
        session_id="feishu:123",
        channel="feishu",
        chat_id="123",
        content="look at this",
        media=[
            MediaItem(type="image", mime_type="image/png", url="data:image/png;base64,abc")
        ],
    )
    state = await plugin.load_state(message=message, session_id="feishu:123")
    assert len(state["vision_current_media"]) == 1
    assert state["vision_current_image_count"] == 1


async def test_load_state_empty_media():
    plugin = PhilipPlugin(framework=None)  # type: ignore[arg-type]
    message = ChannelMessage(
        session_id="feishu:123",
        channel="feishu",
        chat_id="123",
        content="hello",
    )
    state = await plugin.load_state(message=message, session_id="feishu:123")
    assert state["vision_current_media"] == []
    assert state["vision_current_image_count"] == 0


def test_system_prompt_advertises_tool_when_images_exist():
    plugin = PhilipPlugin(framework=None)  # type: ignore[arg-type]
    state: State = {
        "vision_current_media": [{"type": "image"}],
        "vision_current_image_count": 1,
    }
    prompt = plugin.system_prompt(prompt="ignored", state=state)
    assert "vision.inspect_current_images" in prompt
    assert "1 image" in prompt.lower()


def test_system_prompt_multiple_images():
    plugin = PhilipPlugin(framework=None)  # type: ignore[arg-type]
    state: State = {
        "vision_current_media": [{"type": "image"}, {"type": "image"}],
        "vision_current_image_count": 2,
    }
    prompt = plugin.system_prompt(prompt="ignored", state=state)
    assert "2 images" in prompt


def test_system_prompt_omits_hint_when_no_images():
    plugin = PhilipPlugin(framework=None)  # type: ignore[arg-type]
    state: State = {
        "vision_current_media": [],
        "vision_current_image_count": 0,
    }
    prompt = plugin.system_prompt(prompt="ignored", state=state)
    assert "vision.inspect_current_images" not in prompt

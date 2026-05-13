"""Philip Bub plugin — vision tool and image-state injection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bub.envelope import content_of, field_of
from bub.framework import BubFramework
from bub.hookspecs import hookimpl
from bub.types import State


class PhilipPlugin:
    """Plugin that injects current-message image state and a vision tool hint."""

    def __init__(self, framework: BubFramework) -> None:
        self.framework = framework
        # Import vision tools to register them in bub's global tool REGISTRY
        import philip.vision_tools  # noqa: F401

    @hookimpl
    async def build_prompt(
        self, message: Any, session_id: str, state: State
    ) -> str:
        """Build a text-only prompt — images go through vision tool, not main model."""
        content = content_of(message)
        if content.startswith(","):
            message.kind = "command"
            return content
        context = field_of(message, "context_str")
        now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        context_prefix = f"{context}\n---Date: {now}---\n" if context else ""
        return f"{context_prefix}{content}"

    @hookimpl
    async def load_state(self, message: Any, session_id: str) -> State:
        images = _image_media(message)
        # Store the actual message content (not metadata) for the vision tool
        content = getattr(message, "content", "") or ""
        return {
            "vision_current_media": images,
            "vision_current_image_count": len(images),
            "vision_current_text": content,
        }

    @hookimpl
    def system_prompt(self, prompt: str | list[dict], state: State) -> str:
        count = int(state.get("vision_current_image_count", 0) or 0)
        if count <= 0:
            return ""
        s = "s" if count > 1 else ""
        return (
            "<vision_tool_hint>\n"
            f"The current message contains {count} image{s}.\n"
            "If image content is relevant to the user's request, call the "
            "vision.inspect_current_images tool. It reads images from the current "
            "inbound message and returns a concise textual observation.\n"
            "</vision_tool_hint>"
        )


def _image_media(message: Any) -> list[dict[str, Any]]:
    """Extract image-type media items from a ChannelMessage."""
    images: list[dict[str, Any]] = []
    for item in getattr(message, "media", None) or []:
        if getattr(item, "type", None) != "image":
            continue
        images.append(
            {
                "type": item.type,
                "mime_type": item.mime_type,
                "filename": item.filename,
                "url": item.url,
                "media_item": item,
            }
        )
    return images

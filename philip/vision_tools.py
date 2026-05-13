"""Vision inspection tool for Philip."""

from __future__ import annotations

from pydantic import BaseModel, Field
from republic import ToolContext

from bub.tools import tool

from philip.vision_client import VisionClient
from philip.vision_settings import VisionSettings


class VisionInspectInput(BaseModel):
    """Input for vision.inspect_current_images tool."""

    focus: str | None = Field(
        default=None,
        description=(
            "Optional inspection focus, e.g. 'read the error text', "
            "'inspect table values', 'look for UI issues'"
        ),
    )
    max_images: int | None = Field(
        default=None,
        ge=1,
        description="Optional limit on how many images to inspect",
    )


async def vision_inspect_tool(
    params: VisionInspectInput | None, *, context: ToolContext
) -> str:
    """Core logic for the vision inspection tool.

    Inspects images from the current inbound message using a multimodal
    vision model and returns a concise textual observation.
    """
    if params is None:
        params = VisionInspectInput()

    settings = VisionSettings()
    if not settings.is_configured:
        return (
            "Vision inspection unavailable: BUB_VISION_MODEL, BUB_VISION_API_KEY, "
            "and BUB_VISION_API_BASE must all be configured."
        )

    media = list(context.state.get("vision_current_media", []) or [])
    if not media:
        return "Vision inspection skipped: the current message has no image attachments."

    if params.max_images is not None:
        media = media[: params.max_images]

    image_urls: list[str] = []
    for item in media:
        media_item = item.get("media_item")
        if media_item is None:
            continue
        url = await media_item.get_url()
        if url:
            image_urls.append(url)

    if not image_urls:
        return "Vision inspection failed: current message images could not be loaded."

    client = VisionClient(settings)
    try:
        observation = await client.inspect_images(
            text=str(context.state.get("vision_current_text", "")),
            image_urls=image_urls,
            focus=params.focus,
        )
    except Exception as exc:
        return f"Vision inspection failed: {exc}"

    return observation


# Register as a Bub tool via the @tool decorator
@tool(name="vision.inspect_current_images", model=VisionInspectInput, context=True)
async def inspect_current_images(
    params: VisionInspectInput, *, context: ToolContext
) -> str:
    """Inspect images from the current inbound message using a multimodal vision model.

    Use this tool when the current message contains image attachments and you need
    to understand the visual content. Returns a concise textual observation describing
    what is visible in the images.

    When to use:
    - User asks about image content directly ("what's in this screenshot?")
    - User text clearly references an attached image ("look at this error")
    - Answer quality materially depends on understanding the image
    """
    return await vision_inspect_tool(params=params, context=context)

"""Thin multimodal vision client using any-llm-sdk (amessages)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from any_llm import amessages

from philip.tools.vision_settings import VisionSettings


class VisionClient:
    """Calls a multimodal model to produce a compressed text observation from images."""

    def __init__(self, settings: VisionSettings) -> None:
        self._settings = settings

    async def inspect_images(
        self,
        *,
        text: str,
        image_urls: list[str],
        focus: str | None = None,
    ) -> str:
        """Send images to vision model, return compressed text."""
        prompt = (
            "Read the attached images and return one concise natural-language "
            "observation block. Prefer visible text, UI state, errors, tables, "
            "and details relevant to the user text."
        )
        if focus:
            prompt = f"{prompt}\nFocus: {focus}"
        if text:
            prompt = f"{prompt}\nUser text: {text}"

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content.extend(
            {"type": "image_url", "image_url": {"url": url}} for url in image_urls
        )

        messages = [{"role": "user", "content": content}]
        response = await amessages(
            model=self._settings.model,
            messages=messages,
            max_tokens=1024,
            api_key=self._settings.api_key,
            api_base=self._settings.api_base,
        )
        if isinstance(response, AsyncIterator):
            raise TypeError("Vision inspection requires a non-streaming response")

        # MessageResponse.content is a list of content blocks; text lives on
        # text-type blocks. Concatenate them to get the observation.
        text_blocks: list[str] = []
        for block in response.content:
            block_text: Any = getattr(block, "text", None)
            if getattr(block, "type", None) == "text" and isinstance(block_text, str):
                text_blocks.append(block_text)
        result = "".join(text_blocks)

        return result.strip() or "Image observation: no useful visual detail extracted."

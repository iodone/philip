"""Thin multimodal vision client using any-llm-sdk (amessages)."""

from __future__ import annotations

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

        content: list[dict] = [{"type": "text", "text": prompt}]
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

        # MessageResponse.content is a list of content blocks; text lives on
        # text-type blocks. Concatenate them to get the observation.
        result = "".join(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text" and getattr(block, "text", None)
        )

        return result.strip() or "Image observation: no useful visual detail extracted."

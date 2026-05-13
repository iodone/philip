"""Thin multimodal vision client using republic.LLM."""

from __future__ import annotations

from republic import LLM

from philip.vision_settings import VisionSettings


class VisionClient:
    """Calls a multimodal model to produce a compressed text observation from images."""

    def __init__(self, settings: VisionSettings) -> None:
        self._llm = LLM(
            model=settings.model,
            api_key=settings.api_key,
            api_base=settings.api_base,
        )

    async def inspect_images(
        self,
        *,
        text: str,
        image_urls: list[str],
        focus: str | None = None,
    ) -> str:
        """Send images to the vision model and return a compressed textual observation."""
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
        result = await self._llm.chat_async(messages=messages, max_tokens=1024)

        return result.strip() or "Image observation: no useful visual detail extracted."

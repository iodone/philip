"""Thin multimodal vision client for compressed image observation."""

from __future__ import annotations

import httpx
from loguru import logger

from philip.vision_settings import VisionSettings


class VisionClient:
    """Calls a multimodal model to produce a compressed text observation from images."""

    def __init__(self, settings: VisionSettings) -> None:
        self.settings = settings

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

        model_name = self.settings.model
        # Strip provider prefix if present (e.g. "openai:gpt-4.1-mini" -> "gpt-4.1-mini")
        if ":" in model_name:
            model_name = model_name.split(":", 1)[-1]

        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": 1024,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }

        base_url = self.settings.api_base.rstrip("/")
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        return _extract_text(data)


def _extract_text(data: dict) -> str:
    """Extract the assistant message text from an OpenAI chat completion response."""
    choices = data.get("choices", [])
    if not choices:
        return "Image observation: no useful visual detail extracted."
    message = choices[0].get("message", {})
    text = (message.get("content") or "").strip()
    return text or "Image observation: no useful visual detail extracted."

"""Vision model settings loaded from BUB_VISION_* environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class VisionSettings(BaseSettings):
    """Configuration for the optional multimodal vision model."""

    model_config = SettingsConfigDict(env_prefix="BUB_", extra="ignore")

    vision_model: str = ""
    vision_api_key: str = ""
    vision_api_base: str = ""

    @property
    def model(self) -> str:
        return self.vision_model

    @property
    def api_key(self) -> str:
        return self.vision_api_key

    @property
    def api_base(self) -> str:
        return self.vision_api_base

    @property
    def is_configured(self) -> bool:
        return bool(self.model and self.api_key and self.api_base)

"""Philip Bub plugin — vision tool and image-state injection."""

from __future__ import annotations

from typing import Any

from bub.framework import BubFramework
from bub.hookspecs import hookimpl
from bub.types import State


class PhilipPlugin:
    """Plugin that injects current-message image state and a vision tool hint."""

    def __init__(self, framework: BubFramework) -> None:
        self.framework = framework

    @hookimpl
    async def load_state(self, message: Any, session_id: str) -> State:
        return {}

    @hookimpl
    def system_prompt(self, prompt: str | list[dict], state: State) -> str:
        return ""

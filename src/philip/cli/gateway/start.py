"""gateway.start — Start Bub message listeners (Telegram, Feishu, etc.)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from rub.adapter import ExecutionResult
from rub.schema import Operation, OperationDetail

OPERATIONS: list[Operation] = [
    Operation(
        operation_id="gateway.start",
        display_name="Start Gateway",
        description="Start Bub message listeners (Telegram, Feishu, etc.)",
        parameters=[],
    ),
]

DETAILS: dict[str, OperationDetail] = {
    "gateway.start": OperationDetail(
        operation_id="gateway.start",
        display_name="Start Gateway",
        description=(
            "Start Bub message listeners via ChannelManager."
            " Pass enable_channel=<name> to enable specific channels."
        ),
        parameters=[],
        input_schema={
            "type": "object",
            "properties": {
                "enable_channel": {
                    "type": "string",
                    "description": "Channel name to enable (can be repeated). Omit for all channels.",
                },
                "workspace": {
                    "type": "string",
                    "description": "Path to the workspace directory",
                },
            },
        },
        invocation_examples=[
            "philip gateway.start",
            "philip gateway.start enable_channel=telegram",
            "philip gateway.start workspace=/path/to/workspace",
        ],
    ),
}


def execute(args: dict[str, Any]) -> ExecutionResult:
    from bub.channels.manager import ChannelManager
    from bub.framework import BubFramework

    framework = BubFramework()

    workspace = args.get("workspace")
    if workspace:
        framework.workspace = Path(workspace).resolve()

    framework.load_hooks()

    enabled: list[str] | None = None
    enable_channel = args.get("enable_channel")
    if enable_channel:
        enabled = [enable_channel]

    manager = ChannelManager(framework, enabled_channels=enabled)

    try:
        asyncio.run(manager.listen_and_run())
        return ExecutionResult(data={"ok": True})
    except KeyboardInterrupt:
        return ExecutionResult(data={"ok": True, "stopped": "interrupted"})


_EXECUTE: dict[str, tuple[bool, Any]] = {
    "gateway.start": (False, execute),
}

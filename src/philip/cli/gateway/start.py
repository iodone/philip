"""gateway.start — Start Bub message listeners (Telegram, Feishu, etc.)."""

from __future__ import annotations

import subprocess
import sys
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
            "Start Bub message listeners. Runs `bub gateway` as a subprocess"
            " to avoid event loop conflicts with lark_oapi's WebSocket client."
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
    cmd = [sys.executable, "-m", "bub", "gateway"]

    workspace = args.get("workspace")
    if workspace:
        cmd.extend(["--workspace", workspace])

    enable_channel = args.get("enable_channel")
    if enable_channel:
        cmd.extend(["--enable-channel", enable_channel])

    try:
        result = subprocess.run(cmd, check=False)
        return ExecutionResult(
            data={
                "ok": result.returncode == 0,
                "returncode": result.returncode,
            }
        )
    except KeyboardInterrupt:
        return ExecutionResult(data={"ok": True, "stopped": "interrupted"})
    except FileNotFoundError:
        return ExecutionResult(
            data={"ok": False, "error": "bub not found in current environment"}
        )


_EXECUTE: dict[str, tuple[bool, Any]] = {
    "gateway.start": (False, execute),
}

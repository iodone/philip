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
            " Bub reads workspace config from .env automatically."
        ),
        parameters=[],
        input_schema={
            "type": "object",
            "properties": {
                "enable_channel": {
                    "type": "string",
                    "description": "Channel name to enable. Omit for all channels.",
                },
            },
        },
        invocation_examples=[
            "philip gateway.start",
            "philip gateway.start enable_channel=telegram",
        ],
    ),
}


def execute(args: dict[str, Any]) -> ExecutionResult:
    cmd = [sys.executable, "-m", "bub", "gateway"]

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

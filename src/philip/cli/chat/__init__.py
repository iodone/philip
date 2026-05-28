"""Chat operations — interactive JSON-RPC REPL."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from typing import Any

from rub.adapter import ExecutionResult
from rub.schema import Operation, OperationDetail, Parameter

# ---------------------------------------------------------------------------
# Declarative operation metadata
# ---------------------------------------------------------------------------

OPERATIONS: list[Operation] = [
    Operation(
        operation_id="rpc.chat",
        display_name="Chat",
        description="Interactive JSON-RPC REPL for local testing",
        parameters=[
            Parameter(
                name="url",
                param_type="string",
                default="http://127.0.0.1:8420/rpc",
                description="JSON-RPC endpoint URL",
            ),
            Parameter(
                name="ws_url",
                param_type="string",
                default="ws://127.0.0.1:8420/ws",
                description="WebSocket endpoint URL",
            ),
            Parameter(
                name="session",
                param_type="string",
                description="Session ID (auto-generated if omitted)",
            ),
            Parameter(
                name="ws",
                param_type="boolean",
                default=False,
                description="Use WebSocket (enables streaming)",
            ),
            Parameter(
                name="stream",
                param_type="boolean",
                default=False,
                description="Use chat.stream (requires ws=true)",
            ),
        ],
    ),
]

DETAILS: dict[str, OperationDetail] = {
    "rpc.chat": OperationDetail(
        operation_id="rpc.chat",
        display_name="Chat",
        description=(
            "Interactive JSON-RPC REPL for local testing."
            " Supports HTTP and WebSocket modes."
        ),
        parameters=OPERATIONS[0].parameters,
        return_type="interactive",
        invocation_examples=[
            "philip rpc.chat",
            "philip rpc.chat ws=true stream=true",
            "philip rpc.chat url=http://localhost:9000/rpc session=my-session",
        ],
    ),
}


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------


async def execute(args: dict[str, Any]) -> ExecutionResult:
    """Run the interactive REPL."""
    await run_chat(
        url=args.get("url", "http://127.0.0.1:8420/rpc"),
        ws_url=args.get("ws_url", "ws://127.0.0.1:8420/ws"),
        session_id=args.get("session"),
        use_ws=bool(args.get("ws", False)),
        stream=bool(args.get("stream", False)),
    )
    return ExecutionResult(data={"status": "session_ended"})


# ---------------------------------------------------------------------------
# REPL implementation
# ---------------------------------------------------------------------------


async def run_chat(
    url: str = "http://127.0.0.1:8420/rpc",
    ws_url: str = "ws://127.0.0.1:8420/ws",
    session_id: str | None = None,
    use_ws: bool = False,
    stream: bool = False,
) -> None:
    if stream and not use_ws:
        raise ValueError("--stream requires --ws")

    sid = session_id or f"cli-{uuid.uuid4().hex[:8]}"
    print(f"Session: {sid}")
    print(f"{'WS' if use_ws else 'HTTP'} mode{' (streaming)' if stream else ''}")
    print("Type your message. /help for commands.\n")

    if use_ws:
        await _ws_chat(ws_url, sid, stream)
    else:
        await _http_chat(url, sid)


def _handle_local_command(line: str, session_id: str) -> bool:
    cmd = line.strip().lower()
    if cmd in ("/quit", "/exit", "/q"):
        print("Bye.")
        raise _ExitRepl()
    if cmd == "/help":
        print("  /session  — show current session ID")
        print("  /quit     — exit (also /exit, /q, Ctrl-D)")
        print("  anything else — send as message")
        return True
    if cmd == "/session":
        print(f"  session_id = {session_id}")
        return True
    return False


class _ExitRepl(Exception):
    pass


async def _http_chat(url: str, session_id: str) -> None:
    import aiohttp

    request_id = 0
    async with aiohttp.ClientSession() as session:
        try:
            while True:
                try:
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, _read_line
                    )
                except (EOFError, KeyboardInterrupt):
                    print("\nBye.")
                    break
                if not line:
                    continue
                try:
                    if _handle_local_command(line, session_id):
                        continue
                except _ExitRepl:
                    break
                request_id += 1
                payload = {
                    "jsonrpc": "2.0",
                    "id": f"cli-{request_id}",
                    "method": "chat.send",
                    "params": {"session_id": session_id, "message": line},
                }
                try:
                    async with session.post(url, json=payload) as resp:
                        body = await resp.json()
                        if "error" in body:
                            code = body["error"]["code"]
                            msg = body["error"]["message"]
                            print(f"[error {code}] {msg}")
                        else:
                            print(body["result"]["text"])
                except aiohttp.ClientError as exc:
                    print(f"[connection error] {exc}", file=sys.stderr)
                    break
        except _ExitRepl:
            pass


async def _ws_chat(url: str, session_id: str, stream: bool) -> None:
    import aiohttp

    request_id = 0
    async with aiohttp.ClientSession() as session:
        try:
            ws = await session.ws_connect(url)
        except aiohttp.ClientError as exc:
            print(f"[connection error] {exc}", file=sys.stderr)
            return
        print(f"Connected to {url}\n")
        try:
            while True:
                try:
                    line = await asyncio.get_event_loop().run_in_executor(
                        None, _read_line
                    )
                except (EOFError, KeyboardInterrupt):
                    print("\nBye.")
                    break
                if not line:
                    continue
                try:
                    if _handle_local_command(line, session_id):
                        continue
                except _ExitRepl:
                    break
                request_id += 1
                method = "chat.stream" if stream else "chat.send"
                payload = {
                    "jsonrpc": "2.0",
                    "id": f"cli-{request_id}",
                    "method": method,
                    "params": {"session_id": session_id, "message": line},
                }
                await ws.send_json(payload)
                if stream:
                    await _receive_stream(ws, f"cli-{request_id}")
                else:
                    await _receive_single(ws, f"cli-{request_id}")
        except _ExitRepl:
            pass
        finally:
            await ws.close()


async def _receive_stream(ws: Any, request_id: str) -> None:
    while True:
        msg = await ws.receive_json(timeout=120)
        if "method" in msg and msg["method"] == "chat.stream.event":
            params = msg["params"]
            event = params.get("event")
            if event == "token":
                sys.stdout.write(params.get("delta", ""))
                sys.stdout.flush()
            elif event == "tool_call":
                name = params.get("name", "")
                args = json.dumps(params.get("args", {}))
                print(f"\n[tool_call] {name}({args})")
            elif event == "tool_result":
                name = params.get("name", "")
                result = params.get("result", "")
                print(f"[tool_result] {name} → {result}")
            elif event == "error":
                print(f"\n[stream error] {params.get('message', '')}")
            elif event == "done":
                sys.stdout.write("\n")
                sys.stdout.flush()
        elif "id" in msg and msg["id"] == request_id:
            if "error" in msg:
                print(f"[error {msg['error']['code']}] {msg['error']['message']}")
            break


async def _receive_single(ws: Any, request_id: str) -> None:
    msg = await ws.receive_json(timeout=120)
    if "error" in msg:
        print(f"[error {msg['error']['code']}] {msg['error']['message']}")
    elif "result" in msg:
        print(msg["result"]["text"])


def _read_line() -> str:
    try:
        return input("you> ")
    except EOFError:
        raise

"""philip chat — interactive JSON-RPC client for local testing."""

from __future__ import annotations

import asyncio
import json
import sys
import uuid

import click


@click.command("chat")
@click.option("--url", default="http://127.0.0.1:8420/rpc", help="JSON-RPC endpoint URL")
@click.option("--ws-url", default="ws://127.0.0.1:8420/ws", help="WebSocket endpoint URL")
@click.option("--session", "session_id", default=None, help="Session ID (auto-generated if omitted)")
@click.option("--ws", "use_ws", is_flag=True, help="Use WebSocket (enables streaming)")
@click.option("--stream", is_flag=True, help="Use chat.stream (requires --ws)")
def chat(url: str, ws_url: str, session_id: str | None, use_ws: bool, stream: bool) -> None:
    """Interactive chat client for Philip JSON-RPC server.

    Examples:
      philip chat
      philip chat --ws --stream
      philip chat --session my-session
      philip chat --url http://localhost:9000/rpc
    """
    if stream and not use_ws:
        click.echo("--stream requires --ws", err=True)
        sys.exit(1)

    sid = session_id or f"cli-{uuid.uuid4().hex[:8]}"
    click.echo(f"Session: {sid}")
    click.echo(f"{'WS' if use_ws else 'HTTP'} mode{' (streaming)' if stream else ''}")
    click.echo("Type your message. Ctrl-D or /quit to exit.\n")

    if use_ws:
        asyncio.run(_ws_chat(ws_url, sid, stream))
    else:
        asyncio.run(_http_chat(url, sid))


async def _http_chat(url: str, session_id: str) -> None:
    """HTTP POST mode — one request per message."""
    import aiohttp

    request_id = 0

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(None, _read_line)
            except (EOFError, KeyboardInterrupt):
                click.echo("\nBye.")
                break

            if not line:
                continue
            if line.strip() in ("/quit", "/exit", "/q"):
                click.echo("Bye.")
                break

            request_id += 1
            payload = {
                "jsonrpc": "2.0",
                "id": f"cli-{request_id}",
                "method": "chat.send",
                "params": {
                    "session_id": session_id,
                    "message": line,
                },
            }

            try:
                async with session.post(url, json=payload) as resp:
                    body = await resp.json()
                    if "error" in body:
                        click.echo(f"[error {body['error']['code']}] {body['error']['message']}")
                    else:
                        click.echo(body["result"]["text"])
            except aiohttp.ClientError as exc:
                click.echo(f"[connection error] {exc}", err=True)
                break


async def _ws_chat(url: str, session_id: str, stream: bool) -> None:
    """WebSocket mode — supports streaming."""
    import aiohttp

    request_id = 0

    async with aiohttp.ClientSession() as session:
        try:
            ws = await session.ws_connect(url)
        except aiohttp.ClientError as exc:
            click.echo(f"[connection error] {exc}", err=True)
            return

        click.echo(f"Connected to {url}\n")

        try:
            while True:
                try:
                    line = await asyncio.get_event_loop().run_in_executor(None, _read_line)
                except (EOFError, KeyboardInterrupt):
                    click.echo("\nBye.")
                    break

                if not line:
                    continue
                if line.strip() in ("/quit", "/exit", "/q"):
                    click.echo("Bye.")
                    break

                request_id += 1
                method = "chat.stream" if stream else "chat.send"
                payload = {
                    "jsonrpc": "2.0",
                    "id": f"cli-{request_id}",
                    "method": method,
                    "params": {
                        "session_id": session_id,
                        "message": line,
                    },
                }

                await ws.send_json(payload)

                if stream:
                    await _receive_stream(ws, f"cli-{request_id}")
                else:
                    await _receive_single(ws, f"cli-{request_id}")
        finally:
            await ws.close()


async def _receive_stream(ws, request_id: str) -> None:
    """Receive streaming events until the final JSON-RPC response."""
    while True:
        msg = await ws.receive_json(timeout=120)
        if "method" in msg and msg["method"] == "chat.stream.event":
            params = msg["params"]
            event = params.get("event")
            if event == "token":
                # Print delta inline (no newline)
                sys.stdout.write(params.get("delta", ""))
                sys.stdout.flush()
            elif event == "tool_call":
                click.echo(f"\n[tool_call] {params.get('name', '')}({json.dumps(params.get('args', {}))})")
            elif event == "tool_result":
                click.echo(f"[tool_result] {params.get('name', '')} → {params.get('result', '')}")
            elif event == "error":
                click.echo(f"\n[stream error] {params.get('message', '')}")
            elif event == "done":
                sys.stdout.write("\n")
                sys.stdout.flush()
        elif "id" in msg and msg["id"] == request_id:
            # Final JSON-RPC response
            if "error" in msg:
                click.echo(f"[error {msg['error']['code']}] {msg['error']['message']}")
            break


async def _receive_single(ws, request_id: str) -> None:
    """Receive a single JSON-RPC response."""
    msg = await ws.receive_json(timeout=120)
    if "error" in msg:
        click.echo(f"[error {msg['error']['code']}] {msg['error']['message']}")
    elif "result" in msg:
        click.echo(msg["result"]["text"])


def _read_line() -> str:
    """Read a line from stdin (blocking, runs in executor)."""
    try:
        return input("you> ")
    except EOFError:
        raise

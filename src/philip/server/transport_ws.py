"""WebSocket transport — /ws JSON-RPC 2.0 endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiohttp import web

from philip.server.jsonrpc import (
    INTERNAL_ERROR,
    JsonRpcError,
    error_response,
    parse_request,
)
from philip.server.service import StreamHandle

if TYPE_CHECKING:
    from philip.server.service import Service


async def handle_ws(request: web.Request, service: Service) -> web.WebSocketResponse:
    """Handle WebSocket upgrade at /ws — bidirectional JSON-RPC."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            raw = msg.data.encode("utf-8")
            parsed = parse_request(raw)

            if isinstance(parsed, JsonRpcError):
                await ws.send_json(parsed.to_dict())
                continue

            try:
                result = await service.dispatch(parsed)

                if isinstance(result, StreamHandle):
                    # Wire up the request id
                    result = StreamHandle(
                        session_id=result.session_id,
                        request_id=parsed.id,
                        events=result.events,
                    )
                    await _stream_to_ws(ws, result)
                else:
                    await ws.send_json(result)
            except Exception as exc:
                await ws.send_json(
                    error_response(
                        parsed.id,
                        INTERNAL_ERROR,
                        f"Internal error: {exc}",
                    )
                )
        elif msg.type == web.WSMsgType.ERROR:
            break

    return ws


async def _stream_to_ws(ws: web.WebSocketResponse, handle: StreamHandle) -> None:
    """Push stream events as JSON-RPC notifications, then a final response."""
    accumulated_text: list[str] = []

    try:
        async for event in handle.events:
            kind = event.kind if hasattr(event, "kind") else event.get("kind", "")
            data = event.data if hasattr(event, "data") else event.get("data", {})

            if kind == "text":
                delta = str(data.get("delta", ""))
                accumulated_text.append(delta)
                await ws.send_json({
                    "jsonrpc": "2.0",
                    "method": "chat.stream.event",
                    "params": {
                        "session_id": handle.session_id,
                        "event": "token",
                        "delta": delta,
                    },
                })
            elif kind == "tool_call":
                await ws.send_json({
                    "jsonrpc": "2.0",
                    "method": "chat.stream.event",
                    "params": {
                        "session_id": handle.session_id,
                        "event": "tool_call",
                        "name": data.get("name", ""),
                        "args": data.get("args", {}),
                    },
                })
            elif kind == "tool_result":
                await ws.send_json({
                    "jsonrpc": "2.0",
                    "method": "chat.stream.event",
                    "params": {
                        "session_id": handle.session_id,
                        "event": "tool_result",
                        "name": data.get("name", ""),
                        "result": data.get("result", ""),
                    },
                })
            elif kind == "error":
                await ws.send_json({
                    "jsonrpc": "2.0",
                    "method": "chat.stream.event",
                    "params": {
                        "session_id": handle.session_id,
                        "event": "error",
                        "message": str(data.get("message", data)),
                    },
                })
            elif kind == "final":
                pass  # handled below
            # usage and other events: skip for now

        # Send final response with the accumulated result
        full_text = "".join(accumulated_text)
        await ws.send_json({
            "jsonrpc": "2.0",
            "method": "chat.stream.event",
            "params": {
                "session_id": handle.session_id,
                "event": "done",
                "text": full_text,
            },
        })

        # Also send the JSON-RPC success response (matches the original request id)
        await ws.send_json({
            "jsonrpc": "2.0",
            "result": {
                "session_id": handle.session_id,
                "text": full_text,
                "status": "completed",
            },
            "id": handle.request_id,
        })

    except Exception as exc:
        await ws.send_json(
            error_response(
                handle.request_id,
                INTERNAL_ERROR,
                f"Stream error: {exc}",
            )
        )


def register_ws_route(app: web.Application, service: Service) -> None:
    """Register /ws route on an existing aiohttp app."""

    async def ws_handler(request: web.Request) -> web.WebSocketResponse:
        return await handle_ws(request, service)

    app.router.add_get("/ws", ws_handler)

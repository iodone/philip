"""WebSocket transport — /ws JSON-RPC 2.0 endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    """Push stream events as JSON-RPC notifications, then a final response.

    Event mapping from Republic StreamEvent:
      text       → chat.stream.event { event: "token", delta }
      tool_call  → chat.stream.event { event: "tool_call", name, args }
      tool_result→ chat.stream.event { event: "tool_result", name, result }
      error      → chat.stream.event { event: "error", message }
      final      → (consumed for text fallback, not emitted as notification)
    """
    accumulated_text: list[str] = []
    final_text: str | None = None

    try:
        async for event in handle.events:
            kind = event.kind if hasattr(event, "kind") else event.get("kind", "")
            data = event.data if hasattr(event, "data") else event.get("data", {})

            # Internal sentinel: turn completed, extract result
            if kind == "__turn_result__":
                turn_result = data.get("result")
                if (
                    turn_result
                    and hasattr(turn_result, "model_output")
                    and final_text is None
                ):
                    final_text = turn_result.model_output
                continue

            if kind == "text":
                delta = str(data.get("delta", ""))
                accumulated_text.append(delta)
                await ws.send_json(
                    {
                        "jsonrpc": "2.0",
                        "method": "chat.stream.event",
                        "params": {
                            "session_id": handle.session_id,
                            "event": "token",
                            "delta": delta,
                        },
                    }
                )
            elif kind == "tool_call":
                await ws.send_json(
                    {
                        "jsonrpc": "2.0",
                        "method": "chat.stream.event",
                        "params": {
                            "session_id": handle.session_id,
                            "event": "tool_call",
                            "name": data.get("name", ""),
                            "args": data.get("args", {}),
                        },
                    }
                )
            elif kind == "tool_result":
                await ws.send_json(
                    {
                        "jsonrpc": "2.0",
                        "method": "chat.stream.event",
                        "params": {
                            "session_id": handle.session_id,
                            "event": "tool_result",
                            "name": data.get("name", ""),
                            "result": data.get("result", ""),
                        },
                    }
                )
            elif kind == "error":
                await ws.send_json(
                    {
                        "jsonrpc": "2.0",
                        "method": "chat.stream.event",
                        "params": {
                            "session_id": handle.session_id,
                            "event": "error",
                            "message": str(data.get("message", data)),
                        },
                    }
                )
            elif kind == "final":
                # Capture final.text as fallback if accumulated text is empty
                final_event_text = data.get("text")
                if final_event_text and not accumulated_text:
                    final_text = str(final_event_text)
            # usage and other events: skip for now

        # Determine best final text: prefer accumulated deltas,
        # fall back to final event text, then turn result text
        full_text = "".join(accumulated_text) or final_text or ""

        # Send done notification
        await ws.send_json(
            {
                "jsonrpc": "2.0",
                "method": "chat.stream.event",
                "params": {
                    "session_id": handle.session_id,
                    "event": "done",
                    "text": full_text,
                },
            }
        )

        # Send JSON-RPC success response (matches the original request id)
        await ws.send_json(
            {
                "jsonrpc": "2.0",
                "result": {
                    "session_id": handle.session_id,
                    "text": full_text,
                    "status": "completed",
                },
                "id": handle.request_id,
            }
        )

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

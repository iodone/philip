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


def register_ws_route(app: web.Application, service: Service) -> None:
    """Register /ws route on an existing aiohttp app."""

    async def ws_handler(request: web.Request) -> web.WebSocketResponse:
        return await handle_ws(request, service)

    app.router.add_get("/ws", ws_handler)

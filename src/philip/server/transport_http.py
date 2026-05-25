"""HTTP transport — POST /rpc JSON-RPC 2.0 endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp import web

from philip.server.jsonrpc import (
    INVALID_REQUEST,
    PARSE_ERROR,
    JsonRpcError,
    error_response,
    parse_request,
)

if TYPE_CHECKING:
    from philip.server.service import Service


async def handle_rpc(request: web.Request, service: Service) -> web.Response:
    """Handle POST /rpc — parse JSON-RPC envelope, dispatch, return response."""
    if request.method != "POST":
        return web.json_response(
            error_response(None, INVALID_REQUEST, "Only POST is allowed"),
            status=405,
        )

    content_type = request.content_type
    if content_type not in ("application/json", "application/json-rpc"):
        return web.json_response(
            error_response(
                None,
                INVALID_REQUEST,
                f"Content-Type must be application/json, got: {content_type}",
            ),
            status=415,
        )

    raw = await request.read()
    if not raw:
        return web.json_response(
            error_response(None, PARSE_ERROR, "Empty request body"),
            status=400,
        )

    parsed = parse_request(raw)
    if isinstance(parsed, JsonRpcError):
        status = 400 if parsed.code in (PARSE_ERROR, INVALID_REQUEST) else 500
        return web.json_response(parsed.to_dict(), status=status)

    from philip.server.service import StreamHandle

    result = await service.dispatch(parsed)
    if isinstance(result, StreamHandle):
        return web.json_response(
            error_response(
                parsed.id,
                -32001,
                "chat.stream requires WebSocket. Connect to /ws instead.",
            ),
            status=400,
        )
    if "error" in result:
        return web.json_response(result, status=400)
    return web.json_response(result)


def create_app(service: Service) -> web.Application:
    """Create aiohttp application with /rpc endpoint."""
    app = web.Application()

    async def rpc_handler(request: web.Request) -> web.Response:
        return await handle_rpc(request, service)

    app.router.add_post("/rpc", rpc_handler)
    # Also accept GET for browser discovery (returns method list)
    app.router.add_route("*", "/rpc", rpc_handler)
    return app

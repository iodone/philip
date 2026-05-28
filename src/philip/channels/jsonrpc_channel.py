"""JsonRpcChannel — Bub channel for JSON-RPC 2.0 over HTTP and WebSocket.

Plugs into Bub's gateway via provide_channels hook. The ChannelManager
handles process_inbound lifecycle; this channel handles transport only.

Request/response correlation:
  - _pending: session_id → deque of (request_id, Future)
    FIFO order ensures concurrent requests on the same session are
    resolved in arrival order.
  - _stream_queues: session_id → (request_id, Queue)
    One active stream per session (Bub processes turns sequentially).
"""

from __future__ import annotations

import asyncio
import os
from collections import deque
from collections.abc import AsyncIterable, AsyncIterator
from typing import Any

from aiohttp import web
from bub.channels.base import Channel
from bub.channels.message import ChannelMessage
from loguru import logger
from republic import StreamEvent

from philip.server.jsonrpc import (
    INVALID_REQUEST,
    PARSE_ERROR,
    JsonRpcError,
    error_response,
    parse_request,
    success_response,
)


class JsonRpcChannel(Channel):
    """JSON-RPC 2.0 channel for Bub gateway.

    Exposes:
      - POST /rpc — JSON-RPC 2.0 over HTTP
      - GET  /ws  — JSON-RPC 2.0 over WebSocket
    """

    name = "jsonrpc"

    @property
    def enabled(self) -> bool:
        return _env_flag("BUB_JSONRPC_ENABLE") or _env_flag("BUB_JSONRPC_ENABLED")

    def __init__(
        self,
        on_receive: Any,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        self._on_receive = on_receive
        self._host = host or os.environ.get("BUB_JSONRPC_HOST", "127.0.0.1")
        self._port = port or int(os.environ.get("BUB_JSONRPC_PORT", "8420"))
        self._app: web.Application | None = None
        self._runner: web.AppRunner | None = None
        self._site: web.TCPSite | None = None
        # session_id → deque of (request_id, Future) for HTTP/WS unary
        self._pending: dict[str, deque[tuple[str, asyncio.Future[dict[str, Any]]]]] = {}
        # session_id → (request_id, Queue) for WS stream
        self._stream_queues: dict[
            str, tuple[str, asyncio.Queue[StreamEvent | None]]
        ] = {}

    # ── Channel lifecycle ──────────────────────────────────────────

    async def start(self, stop_event: asyncio.Event) -> None:
        self._app = web.Application()
        self._app.router.add_post("/rpc", self._handle_rpc)
        self._app.router.add_route("*", "/rpc", self._handle_rpc)
        self._app.router.add_get("/ws", self._handle_ws)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self._host, self._port)
        await self._site.start()
        logger.info("JsonRpcChannel started on http://{}:{}", self._host, self._port)

    async def stop(self) -> None:
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        logger.info("JsonRpcChannel stopped")

    # ── Outbound: called by ChannelManager after process_inbound ──

    async def send(self, message: ChannelMessage) -> None:
        """Resolve the oldest pending request for this session."""
        session_id = message.session_id
        pending_deque = self._pending.get(session_id)
        if pending_deque and len(pending_deque) > 0:
            request_id, future = pending_deque.popleft()
            if not future.done():
                future.set_result(
                    success_response(
                        request_id,
                        {
                            "session_id": session_id,
                            "text": message.content,
                            "status": "completed",
                        },
                    )
                )
            if not pending_deque:
                del self._pending[session_id]

    def stream_events(
        self,
        message: ChannelMessage,
        stream: AsyncIterable[StreamEvent],
    ) -> AsyncIterable[StreamEvent]:
        """Wrap Bub stream to push events to WS clients via queue."""
        session_id = message.session_id
        entry = self._stream_queues.get(session_id)
        queue = entry[1] if entry else None

        async def _wrapper() -> AsyncIterator[StreamEvent]:
            async for event in stream:
                if queue:
                    await queue.put(event)
                yield event
            if queue:
                await queue.put(None)  # sentinel: stream done

        return _wrapper()

    # ── HTTP handler ───────────────────────────────────────────────

    async def _handle_rpc(self, request: web.Request) -> web.Response:
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

        request_id = parsed.id

        # Local methods (don't go through Bub framework)
        if parsed.method == "chat.ping":
            return web.json_response(success_response(request_id, {"pong": True}))

        # Validate session_id
        session_id = parsed.params.get("session_id")
        if not session_id or not isinstance(session_id, str):
            return web.json_response(
                error_response(
                    request_id,
                    -32000,
                    "params.session_id is required and must be a non-empty string",
                ),
                status=400,
            )

        if parsed.method == "session.get":
            return web.json_response(
                success_response(
                    request_id,
                    {
                        "session_id": session_id,
                        "note": "session state lives in Bub tape, not in channel",
                    },
                )
            )

        # Reject streaming over HTTP
        if parsed.method == "chat.stream":
            return web.json_response(
                error_response(
                    request_id,
                    -32001,
                    "chat.stream requires WebSocket. Connect to /ws instead.",
                ),
                status=400,
            )

        # chat.send: feed to Bub via on_receive, wait for response
        if parsed.method == "chat.send":
            message = parsed.params.get("message", "")
            future: asyncio.Future[dict[str, Any]] = (
                asyncio.get_event_loop().create_future()
            )
            pending_deque = self._pending.setdefault(session_id, deque())
            pending_deque.append((request_id, future))

            inbound = ChannelMessage(
                session_id=session_id,
                content=message,
                channel="jsonrpc",
                chat_id=session_id,
            )
            await self._on_receive(inbound)

            try:
                result = await asyncio.wait_for(future, timeout=300)
                return web.json_response(result)
            except TimeoutError:
                # Remove the timed-out request from the deque
                self._remove_pending(session_id, request_id)
                return web.json_response(
                    error_response(request_id, -32603, "Request timed out"),
                    status=504,
                )

        return web.json_response(
            error_response(request_id, -32601, f"Method not found: {parsed.method}"),
            status=400,
        )

    # ── WebSocket handler ──────────────────────────────────────────

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                raw = msg.data.encode("utf-8")
                parsed = parse_request(raw)

                if isinstance(parsed, JsonRpcError):
                    await ws.send_json(parsed.to_dict())
                    continue

                request_id = parsed.id
                session_id = parsed.params.get("session_id")
                if parsed.method != "chat.ping" and (
                    not session_id or not isinstance(session_id, str)
                ):
                    await ws.send_json(
                        error_response(
                            request_id,
                            -32000,
                            "params.session_id is required",
                        )
                    )
                    continue

                if parsed.method == "chat.ping":
                    await ws.send_json(success_response(request_id, {"pong": True}))
                    continue

                if parsed.method == "session.get":
                    await ws.send_json(
                        success_response(
                            request_id,
                            {
                                "session_id": session_id,
                                "note": "session state lives in Bub tape",
                            },
                        )
                    )
                    continue

                if parsed.method == "chat.stream":
                    await self._handle_ws_stream(ws, parsed, session_id, request_id)
                    continue

                if parsed.method == "chat.send":
                    await self._handle_ws_send(ws, parsed, session_id, request_id)
                    continue

                await ws.send_json(
                    error_response(
                        request_id, -32601, f"Method not found: {parsed.method}"
                    )
                )

            elif msg.type == web.WSMsgType.ERROR:
                break

        return ws

    async def _handle_ws_send(
        self,
        ws: web.WebSocketResponse,
        parsed: Any,
        session_id: str,
        request_id: str,
    ) -> None:
        message = parsed.params.get("message", "")
        future: asyncio.Future[dict[str, Any]] = (
            asyncio.get_event_loop().create_future()
        )
        pending_deque = self._pending.setdefault(session_id, deque())
        pending_deque.append((request_id, future))

        inbound = ChannelMessage(
            session_id=session_id,
            content=message,
            channel="jsonrpc",
            chat_id=session_id,
        )
        await self._on_receive(inbound)

        try:
            result = await asyncio.wait_for(future, timeout=300)
            result["id"] = request_id
            await ws.send_json(result)
        except TimeoutError:
            self._remove_pending(session_id, request_id)
            await ws.send_json(error_response(request_id, -32603, "Request timed out"))

    async def _handle_ws_stream(
        self,
        ws: web.WebSocketResponse,
        parsed: Any,
        session_id: str,
        request_id: str,
    ) -> None:
        if session_id in self._stream_queues:
            await ws.send_json(
                error_response(
                    request_id,
                    -32002,
                    f"Session {session_id} already has an active stream",
                )
            )
            return

        message = parsed.params.get("message", "")
        queue: asyncio.Queue[StreamEvent | None] = asyncio.Queue()
        self._stream_queues[session_id] = (request_id, queue)

        inbound = ChannelMessage(
            session_id=session_id,
            content=message,
            channel="jsonrpc",
            chat_id=session_id,
        )
        await self._on_receive(inbound)

        accumulated_text: list[str] = []
        try:
            while True:
                event = await asyncio.wait_for(queue.get(), timeout=300)
                if event is None:
                    break

                kind = event.kind
                data = event.data

                if kind == "text":
                    delta = str(data.get("delta", ""))
                    accumulated_text.append(delta)
                    await ws.send_json(
                        {
                            "jsonrpc": "2.0",
                            "method": "chat.stream.event",
                            "params": {
                                "session_id": session_id,
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
                                "session_id": session_id,
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
                                "session_id": session_id,
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
                                "session_id": session_id,
                                "event": "error",
                                "message": str(data.get("message", data)),
                            },
                        }
                    )

            full_text = "".join(accumulated_text)

            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "method": "chat.stream.event",
                    "params": {
                        "session_id": session_id,
                        "event": "done",
                        "text": full_text,
                    },
                }
            )
            await ws.send_json(
                {
                    "jsonrpc": "2.0",
                    "result": {
                        "session_id": session_id,
                        "text": full_text,
                        "status": "completed",
                    },
                    "id": request_id,
                }
            )
        except TimeoutError:
            await ws.send_json(error_response(request_id, -32603, "Stream timed out"))
        finally:
            self._stream_queues.pop(session_id, None)

    # ── Helpers ────────────────────────────────────────────────────

    def _remove_pending(self, session_id: str, request_id: str) -> None:
        """Remove a specific request from the pending deque."""
        pending_deque = self._pending.get(session_id)
        if pending_deque is None:
            return
        for i, (rid, _) in enumerate(pending_deque):
            if rid == request_id:
                del pending_deque[i]
                break
        if not pending_deque:
            del self._pending[session_id]


def _env_flag(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return value in {"1", "true", "yes", "on"}

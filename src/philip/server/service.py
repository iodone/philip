"""Service layer — dispatches JSON-RPC methods to business logic."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from bub.channels.message import ChannelMessage
from bub.framework import BubFramework
from bub.types import Envelope

from philip.server.jsonrpc import (
    METHOD_NOT_FOUND,
    MISSING_SESSION_ID,
    JsonRpcRequest,
    error_response,
    success_response,
)
from philip.server.session_store import SessionStore

# Sentinel to signal stream completion
_STREAM_DONE = object()


@dataclass(frozen=True)
class StreamHandle:
    """Returned by dispatch when a method produces a stream of events."""

    session_id: str
    request_id: str | int | None
    events: AsyncIterator[Any]


@dataclass
class StreamCaptureRouter:
    """OutboundChannelRouter that captures stream events into a queue.

    Used by chat.stream to intercept Bub's model stream while keeping
    full process_inbound tape/turn semantics.
    """

    queue: asyncio.Queue[Any] = field(default_factory=asyncio.Queue)

    def wrap_stream(
        self, message: Envelope, stream: AsyncIterable[Any]
    ) -> AsyncIterable[Any]:
        """Intercept stream events and forward them to the queue."""

        async def _wrapper() -> AsyncIterator[Any]:
            async for event in stream:
                await self.queue.put(event)
                yield event
            await self.queue.put(_STREAM_DONE)

        return _wrapper()

    async def dispatch_output(self, message: Envelope) -> bool:
        return False

    async def quit(self, session_id: str) -> None:
        pass


class Service:
    """Routes JSON-RPC methods to Bub framework."""

    def __init__(self, session_store: SessionStore, framework: BubFramework) -> None:
        self.sessions = session_store
        self.framework = framework
        self._handlers: dict[str, Any] = {
            "chat.ping": self._handle_ping,
            "session.get": self._handle_session_get,
            "chat.send": self._handle_chat_send,
            "chat.stream": self._handle_chat_stream,
        }

    async def dispatch(self, request: JsonRpcRequest) -> dict[str, Any] | StreamHandle:
        """Dispatch a validated request. Returns dict or StreamHandle."""
        handler = self._handlers.get(request.method)
        if handler is None:
            return error_response(
                request.id,
                METHOD_NOT_FOUND,
                f"Method not found: {request.method}",
            )

        # Enforce session_id for all methods except chat.ping
        if request.method != "chat.ping":
            session_id = request.params.get("session_id")
            if not session_id or not isinstance(session_id, str):
                return error_response(
                    request.id,
                    MISSING_SESSION_ID,
                    "params.session_id is required and must be a non-empty string",
                )

        try:
            result = await handler(request.params)
            if isinstance(result, StreamHandle):
                return result
            return success_response(request.id, result)
        except Exception as exc:
            from philip.server.jsonrpc import INTERNAL_ERROR

            return error_response(
                request.id,
                INTERNAL_ERROR,
                f"Internal error: {exc}",
            )

    async def _handle_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"pong": True}

    async def _handle_session_get(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id: str = params["session_id"]
        session = self.sessions.get(session_id)
        if session is None:
            return {"exists": False, "session_id": session_id}
        return {"exists": True, "session": session.summary()}

    async def _handle_chat_send(self, params: dict[str, Any]) -> dict[str, Any]:
        session_id: str = params["session_id"]
        message: str = params.get("message", "")
        session = self.sessions.get_or_create(session_id)
        session.message_count += 1

        inbound = ChannelMessage(
            session_id=session_id,
            content=message,
            channel="jsonrpc",
            chat_id=session_id,
        )
        result = await self.framework.process_inbound(inbound)
        return {
            "session_id": result.session_id,
            "message_id": f"msg-{session.message_count}",
            "text": result.model_output,
            "status": "completed",
        }

    async def _handle_chat_stream(self, params: dict[str, Any]) -> StreamHandle:
        """Start a streaming chat via process_inbound(stream_output=True).

        Uses StreamCaptureRouter to intercept stream events while keeping
        full tape/turn semantics from process_inbound.
        """
        session_id: str = params["session_id"]
        message: str = params.get("message", "")
        session = self.sessions.get_or_create(session_id)
        session.message_count += 1

        inbound = ChannelMessage(
            session_id=session_id,
            content=message,
            channel="jsonrpc",
            chat_id=session_id,
        )

        router = StreamCaptureRouter()

        async def _run_and_stream() -> AsyncIterator[Any]:
            # Temporarily bind our capture router so _run_model wraps
            # the stream through it
            previous_router = self.framework._outbound_router
            self.framework.bind_outbound_router(router)

            # Run the full turn as a background task so we can consume
            # the queue concurrently
            turn_task = asyncio.create_task(
                self.framework.process_inbound(inbound, stream_output=True)
            )

            try:
                while True:
                    event = await router.queue.get()
                    if event is _STREAM_DONE:
                        # Wait for turn to complete and get the result
                        result = await turn_task
                        yield {
                            "kind": "__turn_result__",
                            "data": {"result": result},
                        }
                        return
                    yield event
            except Exception:
                turn_task.cancel()
                raise
            finally:
                self.framework.bind_outbound_router(previous_router)

        return StreamHandle(
            session_id=session_id,
            request_id=None,  # set by caller
            events=_run_and_stream(),
        )

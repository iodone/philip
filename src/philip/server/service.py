"""Service layer — dispatches JSON-RPC methods to business logic."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from bub.channels.message import ChannelMessage
from bub.framework import BubFramework

from philip.server.jsonrpc import (
    MISSING_SESSION_ID,
    METHOD_NOT_FOUND,
    JsonRpcRequest,
    error_response,
    success_response,
)
from philip.server.session_store import SessionStore


@dataclass(frozen=True)
class StreamHandle:
    """Returned by dispatch when a method produces a stream of events."""

    session_id: str
    request_id: str | int | None
    events: AsyncIterator[Any]


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

    async def dispatch(
        self, request: JsonRpcRequest
    ) -> dict[str, Any] | StreamHandle:
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
        """Start a streaming chat. Returns StreamHandle for WS transport."""
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

        # Get the stream from Bub framework
        # We need to call process_inbound with stream_output=True, but that
        # returns TurnResult after consuming the stream. Instead, we directly
        # use the hook runtime to get the stream.
        stream = await self._start_stream(inbound, session_id)
        return StreamHandle(
            session_id=session_id,
            request_id=None,  # set by caller
            events=stream,
        )

    async def _start_stream(
        self, inbound: ChannelMessage, session_id: str
    ) -> AsyncIterator[Any]:
        """Set up and return the stream events iterator from Bub."""
        from republic import StreamEvent

        framework = self.framework

        # Resolve hooks just like process_inbound does
        state = {"_runtime_workspace": str(framework.workspace)}
        for hook_state in reversed(
            await framework._hook_runtime.call_many(
                "load_state", message=inbound, session_id=session_id
            )
        ):
            if isinstance(hook_state, dict):
                state.update(hook_state)

        prompt = await framework._hook_runtime.call_first(
            "build_prompt", message=inbound, session_id=session_id, state=state
        )
        if not prompt:
            from bub.envelope import content_of

            prompt = content_of(inbound)

        # Get the raw stream
        raw_stream = await framework._hook_runtime.run_model_stream(
            prompt=prompt, session_id=session_id, state=state
        )

        async def _iterate() -> AsyncIterator[Any]:
            if raw_stream is None:
                # Fallback: non-streaming model
                output = await framework._hook_runtime.run_model(
                    prompt=prompt, session_id=session_id, state=state
                )
                if output:
                    yield StreamEvent(kind="text", data={"delta": output})
                yield StreamEvent(kind="final", data={"text": output or "", "ok": True})
                return

            async for event in raw_stream:
                yield event

        return _iterate()

"""Service layer — dispatches JSON-RPC methods to business logic."""

from __future__ import annotations

from typing import Any

from philip.server.jsonrpc import (
    MISSING_SESSION_ID,
    METHOD_NOT_FOUND,
    JsonRpcRequest,
    error_response,
    success_response,
)
from philip.server.session_store import SessionStore


class Service:
    """Routes JSON-RPC methods. First slice: ping + session.get + chat.send stub."""

    def __init__(self, session_store: SessionStore) -> None:
        self.sessions = session_store
        self._handlers: dict[str, Any] = {
            "chat.ping": self._handle_ping,
            "session.get": self._handle_session_get,
            "chat.send": self._handle_chat_send,
        }

    async def dispatch(self, request: JsonRpcRequest) -> dict[str, Any]:
        """Dispatch a validated request and return a JSON-RPC response dict."""
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
        # Stub — no actual Bub integration yet
        return {
            "session_id": session_id,
            "message_id": f"msg-{session.message_count}",
            "status": "accepted",
        }

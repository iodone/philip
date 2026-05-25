"""Tests for philip serve: HTTP transport, WS transport, and CLI."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from bub.channels.message import ChannelMessage
from bub.types import TurnResult

from philip.server.jsonrpc import MISSING_SESSION_ID, METHOD_NOT_FOUND
from philip.server.service import Service
from philip.server.session_store import SessionStore


def _mock_framework() -> MagicMock:
    """Create a mock BubFramework that returns a canned TurnResult."""
    fw = MagicMock()
    fw.workspace = "/tmp/test"

    async def fake_process_inbound(
        inbound: ChannelMessage, stream_output: bool = False
    ) -> TurnResult:
        return TurnResult(
            session_id=inbound.session_id,
            prompt=inbound.content,
            model_output=f"echo: {inbound.content}",
        )

    fw.process_inbound = AsyncMock(side_effect=fake_process_inbound)

    # Mock hook_runtime for streaming
    hook_runtime = MagicMock()
    hook_runtime.call_many = AsyncMock(return_value=[])
    hook_runtime.call_first = AsyncMock(return_value="test prompt")
    hook_runtime.run_model_stream = AsyncMock(return_value=None)
    hook_runtime.run_model = AsyncMock(return_value="echo: stream fallback")
    fw._hook_runtime = hook_runtime

    return fw


def _make_service() -> Service:
    return Service(SessionStore(), _mock_framework())


def _make_app(service: Service | None = None) -> web.Application:
    from philip.server.transport_http import create_app
    from philip.server.transport_ws import register_ws_route

    svc = service or _make_service()
    app = create_app(svc)
    register_ws_route(app, svc)
    return app


async def _post_rpc(cli: TestClient, payload: dict) -> tuple[int, dict]:
    resp = await cli.post(
        "/rpc",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    body = await resp.json()
    return resp.status, body


@pytest.fixture
async def client():
    app = _make_app()
    async with TestServer(app) as server:
        async with TestClient(server) as cli:
            yield cli


# ─── HTTP Transport ──────────────────────────────────────────────


class TestHttpTransport:
    async def test_chat_ping(self, client: TestClient) -> None:
        status, body = await _post_rpc(client, {
            "jsonrpc": "2.0", "id": "r1", "method": "chat.ping", "params": {},
        })
        assert status == 200
        assert body == {"jsonrpc": "2.0", "result": {"pong": True}, "id": "r1"}

    async def test_session_get_new(self, client: TestClient) -> None:
        status, body = await _post_rpc(client, {
            "jsonrpc": "2.0", "id": "r2",
            "method": "session.get", "params": {"session_id": "test-abc"},
        })
        assert status == 200
        assert body["result"]["exists"] is False
        assert body["result"]["session_id"] == "test-abc"

    async def test_session_get_requires_session_id(self, client: TestClient) -> None:
        status, body = await _post_rpc(client, {
            "jsonrpc": "2.0", "id": "r3",
            "method": "session.get", "params": {},
        })
        assert status == 400
        assert body["error"]["code"] == MISSING_SESSION_ID

    async def test_method_not_found(self, client: TestClient) -> None:
        status, body = await _post_rpc(client, {
            "jsonrpc": "2.0", "id": "r4",
            "method": "no.such.method", "params": {},
        })
        assert status == 400
        assert body["error"]["code"] == METHOD_NOT_FOUND

    async def test_chat_send(self, client: TestClient) -> None:
        status, body = await _post_rpc(client, {
            "jsonrpc": "2.0", "id": "r5",
            "method": "chat.send",
            "params": {"session_id": "tape-xyz", "message": "hello"},
        })
        assert status == 200
        r = body["result"]
        assert r["session_id"] == "tape-xyz"
        assert r["status"] == "completed"
        assert r["text"] == "echo: hello"
        assert "message_id" in r

    async def test_chat_send_requires_session_id(self, client: TestClient) -> None:
        status, body = await _post_rpc(client, {
            "jsonrpc": "2.0", "id": "r6",
            "method": "chat.send", "params": {"message": "hello"},
        })
        assert status == 400
        assert body["error"]["code"] == MISSING_SESSION_ID

    async def test_empty_body(self, client: TestClient) -> None:
        resp = await client.post(
            "/rpc", data=b"", headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400

    async def test_wrong_content_type(self, client: TestClient) -> None:
        resp = await client.post(
            "/rpc", data=b"{}", headers={"Content-Type": "text/plain"},
        )
        assert resp.status == 415

    async def test_chat_stream_over_http_rejected(self, client: TestClient) -> None:
        status, body = await _post_rpc(client, {
            "jsonrpc": "2.0", "id": "r7",
            "method": "chat.stream",
            "params": {"session_id": "t1", "message": "hi"},
        })
        assert status == 400
        assert "WebSocket" in body["error"]["message"]


# ─── WebSocket Transport ─────────────────────────────────────────


class TestWsTransport:
    async def test_ws_ping(self, client: TestClient) -> None:
        ws = await client.ws_connect("/ws")
        await ws.send_json({
            "jsonrpc": "2.0", "id": "w1", "method": "chat.ping", "params": {},
        })
        resp = await ws.receive_json(timeout=5)
        assert resp["result"] == {"pong": True}
        assert resp["id"] == "w1"
        await ws.close()

    async def test_ws_session_get(self, client: TestClient) -> None:
        ws = await client.ws_connect("/ws")
        await ws.send_json({
            "jsonrpc": "2.0", "id": "w2",
            "method": "session.get", "params": {"session_id": "ws-test"},
        })
        resp = await ws.receive_json(timeout=5)
        assert resp["result"]["session_id"] == "ws-test"
        assert resp["id"] == "w2"
        await ws.close()

    async def test_ws_chat_send(self, client: TestClient) -> None:
        ws = await client.ws_connect("/ws")
        await ws.send_json({
            "jsonrpc": "2.0", "id": "w3",
            "method": "chat.send",
            "params": {"session_id": "ws-chat", "message": "ping"},
        })
        resp = await ws.receive_json(timeout=5)
        assert resp["result"]["text"] == "echo: ping"
        assert resp["result"]["status"] == "completed"
        assert resp["id"] == "w3"
        await ws.close()

    async def test_ws_error_response(self, client: TestClient) -> None:
        ws = await client.ws_connect("/ws")
        await ws.send_json({
            "jsonrpc": "2.0", "id": "w4",
            "method": "no.such.method", "params": {},
        })
        resp = await ws.receive_json(timeout=5)
        assert "error" in resp
        assert resp["error"]["code"] == METHOD_NOT_FOUND
        await ws.close()

    async def test_ws_missing_session_id(self, client: TestClient) -> None:
        ws = await client.ws_connect("/ws")
        await ws.send_json({
            "jsonrpc": "2.0", "id": "w5",
            "method": "chat.send", "params": {},
        })
        resp = await ws.receive_json(timeout=5)
        assert resp["error"]["code"] == MISSING_SESSION_ID
        await ws.close()

    async def test_ws_invalid_json(self, client: TestClient) -> None:
        ws = await client.ws_connect("/ws")
        await ws.send_str("not json")
        resp = await ws.receive_json(timeout=5)
        assert "error" in resp
        assert resp["error"]["code"] == -32700  # PARSE_ERROR
        await ws.close()

    async def test_ws_multiple_requests(self, client: TestClient) -> None:
        ws = await client.ws_connect("/ws")
        # Send two requests on the same connection
        await ws.send_json({
            "jsonrpc": "2.0", "id": "w6a",
            "method": "chat.ping", "params": {},
        })
        await ws.send_json({
            "jsonrpc": "2.0", "id": "w6b",
            "method": "chat.ping", "params": {},
        })
        r1 = await ws.receive_json(timeout=5)
        r2 = await ws.receive_json(timeout=5)
        assert r1["id"] == "w6a"
        assert r2["id"] == "w6b"
        await ws.close()


# ─── Session Store ───────────────────────────────────────────────


class TestSessionStore:
    def test_get_or_create(self) -> None:
        store = SessionStore()
        s1 = store.get_or_create("abc")
        s2 = store.get_or_create("abc")
        assert s1 is s2

    def test_get_missing(self) -> None:
        store = SessionStore()
        assert store.get("nope") is None

    def test_has(self) -> None:
        store = SessionStore()
        store.get_or_create("abc")
        assert store.has("abc")
        assert not store.has("xyz")


# ─── CLI ─────────────────────────────────────────────────────────


class TestCliServe:
    def test_serve_command_registered(self) -> None:
        from click.testing import CliRunner
        from philip.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"])
        assert result.exit_code == 0
        assert "serve" in result.output.lower()

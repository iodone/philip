"""Tests for philip serve command and HTTP transport contract."""

from __future__ import annotations

import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from philip.server.jsonrpc import MISSING_SESSION_ID, METHOD_NOT_FOUND
from philip.server.service import Service
from philip.server.session_store import SessionStore
from philip.server.transport_http import create_app


def _make_service() -> Service:
    return Service(SessionStore())


def _make_app(service: Service | None = None) -> web.Application:
    return create_app(service or _make_service())


@pytest.fixture
async def client():
    """aiohttp test client for the RPC app."""
    app = _make_app()
    async with TestServer(app) as server:
        async with TestClient(server) as cli:
            yield cli


async def _post_rpc(cli: TestClient, payload: dict) -> tuple[int, dict]:
    resp = await cli.post(
        "/rpc",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    body = await resp.json()
    return resp.status, body


class TestHttpTransport:
    async def test_chat_ping(self, client: TestClient) -> None:
        status, body = await _post_rpc(client, {
            "jsonrpc": "2.0",
            "id": "r1",
            "method": "chat.ping",
            "params": {},
        })
        assert status == 200
        assert body["jsonrpc"] == "2.0"
        assert body["result"] == {"pong": True}
        assert body["id"] == "r1"

    async def test_session_get_new(self, client: TestClient) -> None:
        status, body = await _post_rpc(client, {
            "jsonrpc": "2.0",
            "id": "r2",
            "method": "session.get",
            "params": {"session_id": "test-abc"},
        })
        assert status == 200
        assert body["result"]["exists"] is False
        assert body["result"]["session_id"] == "test-abc"

    async def test_session_get_requires_session_id(self, client: TestClient) -> None:
        status, body = await _post_rpc(client, {
            "jsonrpc": "2.0",
            "id": "r3",
            "method": "session.get",
            "params": {},
        })
        assert status == 400
        assert body["error"]["code"] == MISSING_SESSION_ID

    async def test_method_not_found(self, client: TestClient) -> None:
        status, body = await _post_rpc(client, {
            "jsonrpc": "2.0",
            "id": "r4",
            "method": "no.such.method",
            "params": {},
        })
        assert status == 400
        assert body["error"]["code"] == METHOD_NOT_FOUND

    async def test_chat_send(self, client: TestClient) -> None:
        status, body = await _post_rpc(client, {
            "jsonrpc": "2.0",
            "id": "r5",
            "method": "chat.send",
            "params": {"session_id": "tape-xyz", "message": "hello"},
        })
        assert status == 200
        assert body["result"]["session_id"] == "tape-xyz"
        assert body["result"]["status"] == "accepted"
        assert "message_id" in body["result"]

    async def test_chat_send_requires_session_id(self, client: TestClient) -> None:
        status, body = await _post_rpc(client, {
            "jsonrpc": "2.0",
            "id": "r6",
            "method": "chat.send",
            "params": {"message": "hello"},
        })
        assert status == 400
        assert body["error"]["code"] == MISSING_SESSION_ID

    async def test_empty_body(self, client: TestClient) -> None:
        resp = await client.post(
            "/rpc",
            data=b"",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400

    async def test_wrong_content_type(self, client: TestClient) -> None:
        resp = await client.post(
            "/rpc",
            data=b"{}",
            headers={"Content-Type": "text/plain"},
        )
        assert resp.status == 415


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


class TestCliServe:
    def test_serve_command_registered(self) -> None:
        from click.testing import CliRunner
        from philip.cli.main import main

        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"])
        assert result.exit_code == 0
        assert "serve" in result.output.lower()

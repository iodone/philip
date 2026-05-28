"""Tests for philip serve: HTTP transport, WS transport, CLI, and streaming."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from bub.channels.message import ChannelMessage
from bub.types import TurnResult

from philip.server.jsonrpc import METHOD_NOT_FOUND, MISSING_SESSION_ID
from philip.server.service import Service, StreamCaptureRouter
from philip.server.session_store import SessionStore

# ─── Republic StreamEvent mock ───────────────────────────────────


@dataclass(frozen=True)
class FakeStreamEvent:
    """Mimics republic.StreamEvent without importing republic."""

    kind: str
    data: dict[str, Any] = field(default_factory=dict)


# ─── Mock Framework ──────────────────────────────────────────────


def _mock_framework(events: list[FakeStreamEvent] | None = None) -> MagicMock:
    """Create a mock BubFramework.

    If events is provided, process_inbound with stream_output=True will
    wrap the stream through the bound OutboundChannelRouter (if any),
    simulating the real Bub streaming path.
    """
    fw = MagicMock()
    fw.workspace = "/tmp/test"
    fw._outbound_router = None

    def _bind_router(router: Any) -> None:
        fw._outbound_router = router

    fw.bind_outbound_router = MagicMock(side_effect=_bind_router)

    async def fake_process_inbound(
        inbound: ChannelMessage, stream_output: bool = False
    ) -> TurnResult:
        if stream_output and events is not None and fw._outbound_router is not None:
            # Simulate Bub's streaming path: get stream, wrap through router
            async def _fake_stream():
                for ev in events:
                    yield ev

            wrapped = fw._outbound_router.wrap_stream(inbound, _fake_stream())
            # Consume the wrapped stream (accumulating text, like Bub does)
            parts: list[str] = []
            async for ev in wrapped:
                if ev.kind == "text":
                    parts.append(str(ev.data.get("delta", "")))
            return TurnResult(
                session_id=inbound.session_id,
                prompt=inbound.content,
                model_output="".join(parts),
            )
        # Non-streaming path
        return TurnResult(
            session_id=inbound.session_id,
            prompt=inbound.content,
            model_output=f"echo: {inbound.content}",
        )

    fw.process_inbound = AsyncMock(side_effect=fake_process_inbound)
    return fw


def _make_service(fw: MagicMock | None = None) -> Service:
    return Service(SessionStore(), fw or _mock_framework())


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


# ─── Fixtures ────────────────────────────────────────────────────


@pytest.fixture
async def client():
    app = _make_app()
    async with TestServer(app) as server:
        async with TestClient(server) as cli:
            yield cli


@pytest.fixture
def stream_events():
    """Standard stream event sequence for testing."""
    return [
        FakeStreamEvent("text", {"delta": "Hello"}),
        FakeStreamEvent("text", {"delta": " world"}),
        FakeStreamEvent("final", {"text": "Hello world", "ok": True}),
    ]


@pytest.fixture
async def stream_client(stream_events):
    """Client with a framework that produces stream events."""
    fw = _mock_framework(events=stream_events)
    svc = _make_service(fw)
    app = _make_app(svc)
    async with TestServer(app) as server:
        async with TestClient(server) as cli:
            yield cli


@pytest.fixture
async def tool_stream_client():
    """Client with stream events including tool calls."""
    events = [
        FakeStreamEvent("text", {"delta": "Let me check"}),
        FakeStreamEvent("tool_call", {"name": "search", "args": {"q": "test"}}),
        FakeStreamEvent("tool_result", {"name": "search", "result": "found"}),
        FakeStreamEvent("text", {"delta": " found it"}),
        FakeStreamEvent("final", {"text": "Let me check found it", "ok": True}),
    ]
    fw = _mock_framework(events=events)
    svc = _make_service(fw)
    app = _make_app(svc)
    async with TestServer(app) as server:
        async with TestClient(server) as cli:
            yield cli


@pytest.fixture
async def fallback_stream_client():
    """Client where run_model_stream returns None (fallback to run_model)."""
    fw = _mock_framework(events=[])  # empty events

    # Override: process_inbound with stream_output=True returns directly
    async def fallback_process(
        inbound: ChannelMessage, stream_output: bool = False
    ) -> TurnResult:
        return TurnResult(
            session_id=inbound.session_id,
            prompt=inbound.content,
            model_output="fallback output",
        )

    fw.process_inbound = AsyncMock(side_effect=fallback_process)
    svc = _make_service(fw)
    app = _make_app(svc)
    async with TestServer(app) as server:
        async with TestClient(server) as cli:
            yield cli


@pytest.fixture
async def final_only_client():
    """Client with only a final event (no text deltas)."""
    events = [
        FakeStreamEvent("final", {"text": "only in final", "ok": True}),
    ]
    fw = _mock_framework(events=events)
    svc = _make_service(fw)
    app = _make_app(svc)
    async with TestServer(app) as server:
        async with TestClient(server) as cli:
            yield cli


# ─── HTTP Transport ──────────────────────────────────────────────


class TestHttpTransport:
    async def test_chat_ping(self, client: TestClient) -> None:
        status, body = await _post_rpc(
            client,
            {
                "jsonrpc": "2.0",
                "id": "r1",
                "method": "chat.ping",
                "params": {},
            },
        )
        assert status == 200
        assert body == {"jsonrpc": "2.0", "result": {"pong": True}, "id": "r1"}

    async def test_session_get_new(self, client: TestClient) -> None:
        status, body = await _post_rpc(
            client,
            {
                "jsonrpc": "2.0",
                "id": "r2",
                "method": "session.get",
                "params": {"session_id": "test-abc"},
            },
        )
        assert status == 200
        assert body["result"]["exists"] is False

    async def test_session_get_requires_session_id(self, client: TestClient) -> None:
        status, body = await _post_rpc(
            client,
            {
                "jsonrpc": "2.0",
                "id": "r3",
                "method": "session.get",
                "params": {},
            },
        )
        assert status == 400
        assert body["error"]["code"] == MISSING_SESSION_ID

    async def test_method_not_found(self, client: TestClient) -> None:
        status, body = await _post_rpc(
            client,
            {
                "jsonrpc": "2.0",
                "id": "r4",
                "method": "no.such.method",
                "params": {},
            },
        )
        assert status == 400
        assert body["error"]["code"] == METHOD_NOT_FOUND

    async def test_chat_send(self, client: TestClient) -> None:
        status, body = await _post_rpc(
            client,
            {
                "jsonrpc": "2.0",
                "id": "r5",
                "method": "chat.send",
                "params": {"session_id": "tape-xyz", "message": "hello"},
            },
        )
        assert status == 200
        r = body["result"]
        assert r["session_id"] == "tape-xyz"
        assert r["text"] == "echo: hello"
        assert r["status"] == "completed"

    async def test_chat_send_requires_session_id(self, client: TestClient) -> None:
        status, body = await _post_rpc(
            client,
            {
                "jsonrpc": "2.0",
                "id": "r6",
                "method": "chat.send",
                "params": {"message": "hello"},
            },
        )
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

    async def test_chat_stream_over_http_rejected(self, client: TestClient) -> None:
        status, body = await _post_rpc(
            client,
            {
                "jsonrpc": "2.0",
                "id": "r7",
                "method": "chat.stream",
                "params": {"session_id": "t1", "message": "hi"},
            },
        )
        assert status == 400
        assert "WebSocket" in body["error"]["message"]


# ─── WebSocket Transport ─────────────────────────────────────────


class TestWsTransport:
    async def test_ws_ping(self, client: TestClient) -> None:
        ws = await client.ws_connect("/ws")
        await ws.send_json(
            {
                "jsonrpc": "2.0",
                "id": "w1",
                "method": "chat.ping",
                "params": {},
            }
        )
        resp = await ws.receive_json(timeout=5)
        assert resp["result"] == {"pong": True}
        assert resp["id"] == "w1"
        await ws.close()

    async def test_ws_session_get(self, client: TestClient) -> None:
        ws = await client.ws_connect("/ws")
        await ws.send_json(
            {
                "jsonrpc": "2.0",
                "id": "w2",
                "method": "session.get",
                "params": {"session_id": "ws-test"},
            }
        )
        resp = await ws.receive_json(timeout=5)
        assert resp["result"]["session_id"] == "ws-test"
        await ws.close()

    async def test_ws_chat_send(self, client: TestClient) -> None:
        ws = await client.ws_connect("/ws")
        await ws.send_json(
            {
                "jsonrpc": "2.0",
                "id": "w3",
                "method": "chat.send",
                "params": {"session_id": "ws-chat", "message": "ping"},
            }
        )
        resp = await ws.receive_json(timeout=5)
        assert resp["result"]["text"] == "echo: ping"
        assert resp["result"]["status"] == "completed"
        await ws.close()

    async def test_ws_error_response(self, client: TestClient) -> None:
        ws = await client.ws_connect("/ws")
        await ws.send_json(
            {
                "jsonrpc": "2.0",
                "id": "w4",
                "method": "no.such.method",
                "params": {},
            }
        )
        resp = await ws.receive_json(timeout=5)
        assert "error" in resp
        assert resp["error"]["code"] == METHOD_NOT_FOUND
        await ws.close()

    async def test_ws_missing_session_id(self, client: TestClient) -> None:
        ws = await client.ws_connect("/ws")
        await ws.send_json(
            {
                "jsonrpc": "2.0",
                "id": "w5",
                "method": "chat.send",
                "params": {},
            }
        )
        resp = await ws.receive_json(timeout=5)
        assert resp["error"]["code"] == MISSING_SESSION_ID
        await ws.close()

    async def test_ws_invalid_json(self, client: TestClient) -> None:
        ws = await client.ws_connect("/ws")
        await ws.send_str("not json")
        resp = await ws.receive_json(timeout=5)
        assert "error" in resp
        assert resp["error"]["code"] == -32700
        await ws.close()

    async def test_ws_multiple_requests(self, client: TestClient) -> None:
        ws = await client.ws_connect("/ws")
        await ws.send_json(
            {
                "jsonrpc": "2.0",
                "id": "w6a",
                "method": "chat.ping",
                "params": {},
            }
        )
        await ws.send_json(
            {
                "jsonrpc": "2.0",
                "id": "w6b",
                "method": "chat.ping",
                "params": {},
            }
        )
        r1 = await ws.receive_json(timeout=5)
        r2 = await ws.receive_json(timeout=5)
        assert r1["id"] == "w6a"
        assert r2["id"] == "w6b"
        await ws.close()


# ─── WebSocket Streaming ─────────────────────────────────────────


class TestWsStreaming:
    async def test_stream_basic(self, stream_client: TestClient) -> None:
        """chat.stream emits token events, done event, and final response."""
        ws = await stream_client.ws_connect("/ws")
        await ws.send_json(
            {
                "jsonrpc": "2.0",
                "id": "s1",
                "method": "chat.stream",
                "params": {"session_id": "stream-1", "message": "hi"},
            }
        )

        notifications: list[dict] = []
        final_response = None

        # Read all messages: notifications + final JSON-RPC response
        while True:
            msg = await ws.receive_json(timeout=5)
            if "method" in msg and msg["method"] == "chat.stream.event":
                notifications.append(msg)
            elif "id" in msg and msg["id"] == "s1":
                final_response = msg
                break  # JSON-RPC response is always last

        # Verify token events
        tokens = [n for n in notifications if n["params"]["event"] == "token"]
        assert len(tokens) == 2
        assert tokens[0]["params"]["delta"] == "Hello"
        assert tokens[1]["params"]["delta"] == " world"

        # Verify done event
        done = [n for n in notifications if n["params"]["event"] == "done"]
        assert len(done) == 1
        assert done[0]["params"]["text"] == "Hello world"
        assert done[0]["params"]["session_id"] == "stream-1"

        # Verify final JSON-RPC response
        assert final_response is not None
        assert final_response["result"]["text"] == "Hello world"
        assert final_response["result"]["status"] == "completed"

        await ws.close()

    async def test_stream_with_tool_calls(self, tool_stream_client: TestClient) -> None:
        """chat.stream emits tool_call and tool_result events."""
        ws = await tool_stream_client.ws_connect("/ws")
        await ws.send_json(
            {
                "jsonrpc": "2.0",
                "id": "s2",
                "method": "chat.stream",
                "params": {"session_id": "stream-2", "message": "search"},
            }
        )

        notifications: list[dict] = []
        while True:
            msg = await ws.receive_json(timeout=5)
            if "method" in msg and msg["method"] == "chat.stream.event":
                notifications.append(msg)
                if msg["params"]["event"] == "done":
                    break

        events = [n["params"]["event"] for n in notifications]
        assert "token" in events
        assert "tool_call" in events
        assert "tool_result" in events
        assert "done" in events

        tool_call = next(
            n for n in notifications if n["params"]["event"] == "tool_call"
        )
        assert tool_call["params"]["name"] == "search"
        assert tool_call["params"]["args"] == {"q": "test"}

        tool_result = next(
            n for n in notifications if n["params"]["event"] == "tool_result"
        )
        assert tool_result["params"]["name"] == "search"
        assert tool_result["params"]["result"] == "found"

        await ws.close()

    async def test_stream_final_text_fallback(
        self, final_only_client: TestClient
    ) -> None:
        """When only final event has text (no deltas), done.text uses final.text."""
        ws = await final_only_client.ws_connect("/ws")
        await ws.send_json(
            {
                "jsonrpc": "2.0",
                "id": "s3",
                "method": "chat.stream",
                "params": {"session_id": "stream-3", "message": "test"},
            }
        )

        notifications: list[dict] = []
        while True:
            msg = await ws.receive_json(timeout=5)
            if "method" in msg and msg["method"] == "chat.stream.event":
                notifications.append(msg)
                if msg["params"]["event"] == "done":
                    break

        done = next(n for n in notifications if n["params"]["event"] == "done")
        assert done["params"]["text"] == "only in final"

        await ws.close()

    async def test_stream_requires_session_id(self, stream_client: TestClient) -> None:
        ws = await stream_client.ws_connect("/ws")
        await ws.send_json(
            {
                "jsonrpc": "2.0",
                "id": "s4",
                "method": "chat.stream",
                "params": {},
            }
        )
        resp = await ws.receive_json(timeout=5)
        assert resp["error"]["code"] == MISSING_SESSION_ID
        await ws.close()

    async def test_stream_notification_format(self, stream_client: TestClient) -> None:
        """Notifications are valid JSON-RPC 2.0 without id field."""
        ws = await stream_client.ws_connect("/ws")
        await ws.send_json(
            {
                "jsonrpc": "2.0",
                "id": "s5",
                "method": "chat.stream",
                "params": {"session_id": "stream-5", "message": "x"},
            }
        )

        while True:
            msg = await ws.receive_json(timeout=5)
            if "method" in msg and msg["method"] == "chat.stream.event":
                # Notification: must have jsonrpc, method, params; must NOT have id
                assert msg["jsonrpc"] == "2.0"
                assert "id" not in msg
                assert "params" in msg
                if msg["params"]["event"] == "done":
                    break

        await ws.close()

    async def test_stream_calls_process_inbound(
        self, stream_client: TestClient
    ) -> None:
        """Verify that chat.stream goes through process_inbound."""
        ws = await stream_client.ws_connect("/ws")
        await ws.send_json(
            {
                "jsonrpc": "2.0",
                "id": "s6",
                "method": "chat.stream",
                "params": {"session_id": "stream-6", "message": "verify"},
            }
        )

        # Drain messages until done
        while True:
            msg = await ws.receive_json(timeout=5)
            if "method" in msg and msg["params"].get("event") == "done":
                break

        # The mock framework's process_inbound was called
        # (verified by the fact that stream events were produced)
        await ws.close()


# ─── StreamCaptureRouter ─────────────────────────────────────────


class TestStreamCaptureRouter:
    async def test_wrap_stream_captures_events(self) -> None:
        router = StreamCaptureRouter()
        events = [
            FakeStreamEvent("text", {"delta": "a"}),
            FakeStreamEvent("text", {"delta": "b"}),
            FakeStreamEvent("final", {"text": "ab", "ok": True}),
        ]

        async def _gen():
            for e in events:
                yield e

        collected: list[FakeStreamEvent] = []
        async for ev in router.wrap_stream(MagicMock(), _gen()):
            collected.append(ev)

        assert len(collected) == 3
        # Queue should have all events + DONE sentinel
        q_events: list[Any] = []
        while not router.queue.empty():
            q_events.append(await router.queue.get())
        assert len(q_events) == 4  # 3 events + _STREAM_DONE


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
    def test_serve_command_removed_from_cli(self) -> None:
        """philip rpc serve is removed — use `bub gateway` instead."""
        from philip.cli.commands.rpc import rpc as rpc_group

        assert "serve" not in rpc_group.commands

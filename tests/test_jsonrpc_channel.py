"""Tests for JsonRpcChannel — Bub channel for JSON-RPC 2.0."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from bub.channels.message import ChannelMessage

from philip.channels.jsonrpc_channel import JsonRpcChannel


# ─── Helpers ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class FakeStreamEvent:
    kind: str
    data: dict[str, Any] = field(default_factory=dict)


def _make_channel(
    events: list[FakeStreamEvent] | None = None,
    on_receive: Any = None,
) -> tuple[JsonRpcChannel, list[ChannelMessage]]:
    """Create a JsonRpcChannel that records received messages."""
    received: list[ChannelMessage] = []

    async def _default_on_receive(msg: ChannelMessage) -> None:
        received.append(msg)
        session_id = msg.session_id

        # If stream queue exists, push events through it
        entry = channel._stream_queues.get(session_id)
        if entry is not None and events is not None:
            _request_id, queue = entry
            for ev in events:
                await queue.put(ev)
            await queue.put(None)
            return

        # Otherwise resolve the oldest pending future (for chat.send).
        from philip.server.jsonrpc import success_response

        pending_deque = channel._pending.get(session_id)
        if pending_deque and len(pending_deque) > 0:
            req_id, future = pending_deque.popleft()
            if not future.done():
                future.set_result(success_response(req_id, {
                    "session_id": session_id,
                    "text": "echo: " + msg.content,
                    "status": "completed",
                }))

    handler = on_receive or _default_on_receive
    channel = JsonRpcChannel(on_receive=handler)
    return channel, received


def _init_app(channel: JsonRpcChannel) -> None:
    """Manually init the aiohttp app for testing."""
    channel._app = web.Application()
    channel._app.router.add_post("/rpc", channel._handle_rpc)
    channel._app.router.add_route("*", "/rpc", channel._handle_rpc)
    channel._app.router.add_get("/ws", channel._handle_ws)


@pytest.fixture
async def channel_client():
    """Basic channel client with echo-style responses."""
    channel, received = _make_channel()
    _init_app(channel)
    server = TestServer(channel._app)
    async with TestClient(server) as cli:
        yield cli, channel, received


@pytest.fixture
async def stream_channel_client():
    """Channel client that produces stream events."""
    events = [
        FakeStreamEvent("text", {"delta": "Hello"}),
        FakeStreamEvent("text", {"delta": " world"}),
        FakeStreamEvent("final", {"text": "Hello world", "ok": True}),
    ]
    channel, received = _make_channel(events=events)
    _init_app(channel)
    server = TestServer(channel._app)
    async with TestClient(server) as cli:
        yield cli, channel, received


async def _post_rpc(cli: TestClient, payload: dict) -> tuple[int, dict]:
    resp = await cli.post(
        "/rpc",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    body = await resp.json()
    return resp.status, body


# ─── Channel Interface ──────────────────────────────────────────


class TestChannelInterface:
    def test_name(self) -> None:
        channel, _ = _make_channel()
        assert channel.name == "jsonrpc"

    def test_enabled_with_enable_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUB_JSONRPC_ENABLE", "true")
        monkeypatch.delenv("BUB_JSONRPC_ENABLED", raising=False)
        channel, _ = _make_channel()
        assert channel.enabled is True

    def test_enabled_with_enabled_env_alias(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUB_JSONRPC_ENABLED", "true")
        monkeypatch.delenv("BUB_JSONRPC_ENABLE", raising=False)
        channel, _ = _make_channel()
        assert channel.enabled is True

    def test_enabled_with_env_1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUB_JSONRPC_ENABLE", "1")
        monkeypatch.delenv("BUB_JSONRPC_ENABLED", raising=False)
        channel, _ = _make_channel()
        assert channel.enabled is True

    def test_disabled_without_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("BUB_JSONRPC_ENABLE", raising=False)
        monkeypatch.delenv("BUB_JSONRPC_ENABLED", raising=False)
        channel, _ = _make_channel()
        assert channel.enabled is False

    def test_disabled_with_empty_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BUB_JSONRPC_ENABLE", "")
        monkeypatch.delenv("BUB_JSONRPC_ENABLED", raising=False)
        channel, _ = _make_channel()
        assert channel.enabled is False

    def test_needs_debounce(self) -> None:
        channel, _ = _make_channel()
        assert channel.needs_debounce is False

    def test_provide_channels_hookimpl(self) -> None:
        """PhilipPlugin.provide_channels returns JsonRpcChannel."""
        from philip.plugins.plugin import PhilipPlugin

        plugin = PhilipPlugin.__new__(PhilipPlugin)
        result = plugin.provide_channels(message_handler=lambda msg: None)
        assert len(result) == 1
        assert isinstance(result[0], JsonRpcChannel)
        assert result[0].name == "jsonrpc"


# ─── HTTP via Channel ───────────────────────────────────────────


class TestChannelHttp:
    async def test_ping(self, channel_client) -> None:
        cli, channel, received = channel_client
        status, body = await _post_rpc(cli, {
            "jsonrpc": "2.0", "id": "c1", "method": "chat.ping", "params": {},
        })
        assert status == 200
        assert body["result"] == {"pong": True}

    async def test_chat_send(self, channel_client) -> None:
        cli, channel, received = channel_client
        status, body = await _post_rpc(cli, {
            "jsonrpc": "2.0", "id": "c2",
            "method": "chat.send",
            "params": {"session_id": "s1", "message": "hello"},
        })
        assert status == 200
        assert body["result"]["session_id"] == "s1"
        assert body["result"]["text"] == "echo: hello"
        assert body["result"]["status"] == "completed"
        assert body["id"] == "c2"
        assert len(received) == 1
        assert received[0].content == "hello"
        assert received[0].session_id == "s1"

    async def test_send_requires_session_id(self, channel_client) -> None:
        cli, _, _ = channel_client
        status, body = await _post_rpc(cli, {
            "jsonrpc": "2.0", "id": "c3",
            "method": "chat.send", "params": {"message": "hi"},
        })
        assert status == 400
        assert body["error"]["code"] == -32000

    async def test_method_not_found(self, channel_client) -> None:
        cli, _, _ = channel_client
        status, body = await _post_rpc(cli, {
            "jsonrpc": "2.0", "id": "c4",
            "method": "no.such.method",
            "params": {"session_id": "s1"},
        })
        assert status == 400
        assert body["error"]["code"] == -32601

    async def test_chat_stream_rejected_over_http(self, channel_client) -> None:
        cli, _, _ = channel_client
        status, body = await _post_rpc(cli, {
            "jsonrpc": "2.0", "id": "c5",
            "method": "chat.stream",
            "params": {"session_id": "s1", "message": "hi"},
        })
        assert status == 400
        assert "WebSocket" in body["error"]["message"]


# ─── WebSocket via Channel ──────────────────────────────────────


class TestChannelWs:
    async def test_ws_ping(self, channel_client) -> None:
        cli, _, _ = channel_client
        ws = await cli.ws_connect("/ws")
        await ws.send_json({
            "jsonrpc": "2.0", "id": "w1", "method": "chat.ping", "params": {},
        })
        resp = await ws.receive_json(timeout=5)
        assert resp["result"] == {"pong": True}
        await ws.close()

    async def test_ws_chat_send(self, channel_client) -> None:
        cli, _, received = channel_client
        ws = await cli.ws_connect("/ws")
        await ws.send_json({
            "jsonrpc": "2.0", "id": "w2",
            "method": "chat.send",
            "params": {"session_id": "ws-s1", "message": "test"},
        })
        resp = await ws.receive_json(timeout=5)
        assert resp["result"]["text"] == "echo: test"
        assert resp["result"]["status"] == "completed"
        assert len(received) == 1
        await ws.close()

    async def test_ws_missing_session_id(self, channel_client) -> None:
        cli, _, _ = channel_client
        ws = await cli.ws_connect("/ws")
        await ws.send_json({
            "jsonrpc": "2.0", "id": "w3",
            "method": "chat.send", "params": {},
        })
        resp = await ws.receive_json(timeout=5)
        assert resp["error"]["code"] == -32000
        await ws.close()


# ─── WebSocket Streaming via Channel ────────────────────────────


class TestChannelStream:
    async def test_stream_basic(self, stream_channel_client) -> None:
        cli, channel, received = stream_channel_client
        ws = await cli.ws_connect("/ws")
        await ws.send_json({
            "jsonrpc": "2.0", "id": "s1",
            "method": "chat.stream",
            "params": {"session_id": "st1", "message": "hi"},
        })

        notifications: list[dict] = []
        final_response = None

        while True:
            msg = await ws.receive_json(timeout=5)
            if "method" in msg and msg["method"] == "chat.stream.event":
                notifications.append(msg)
            elif "id" in msg and msg["id"] == "s1":
                final_response = msg
                break

        tokens = [n for n in notifications if n["params"]["event"] == "token"]
        assert len(tokens) == 2
        assert tokens[0]["params"]["delta"] == "Hello"
        assert tokens[1]["params"]["delta"] == " world"

        done = [n for n in notifications if n["params"]["event"] == "done"]
        assert len(done) == 1
        assert done[0]["params"]["text"] == "Hello world"

        assert final_response is not None
        assert final_response["result"]["text"] == "Hello world"
        assert final_response["result"]["status"] == "completed"
        assert final_response["id"] == "s1"
        await ws.close()

    async def test_stream_on_receive_called(self, stream_channel_client) -> None:
        cli, _, received = stream_channel_client
        ws = await cli.ws_connect("/ws")
        await ws.send_json({
            "jsonrpc": "2.0", "id": "s2",
            "method": "chat.stream",
            "params": {"session_id": "st2", "message": "test"},
        })

        while True:
            msg = await ws.receive_json(timeout=5)
            if "method" in msg and msg["params"].get("event") == "done":
                break

        assert len(received) == 1
        assert received[0].content == "test"
        assert received[0].channel == "jsonrpc"
        await ws.close()


# ─── send() callback ────────────────────────────────────────────


class TestChannelSend:
    async def test_send_resolves_oldest_pending(self) -> None:
        """Channel.send() resolves the oldest pending request for the session."""
        channel, _ = _make_channel()
        loop = asyncio.get_event_loop()

        # Queue two requests for the same session
        future1 = loop.create_future()
        future2 = loop.create_future()
        from collections import deque
        pending_deque = channel._pending.setdefault("test-session", deque())
        pending_deque.append(("req-1", future1))
        pending_deque.append(("req-2", future2))

        # send() should resolve the first one
        msg = ChannelMessage(
            session_id="test-session",
            content="first response",
            channel="jsonrpc",
            chat_id="test-session",
        )
        await channel.send(msg)

        assert future1.done()
        assert not future2.done()
        assert future1.result()["result"]["text"] == "first response"
        assert future1.result()["id"] == "req-1"

        # send() again resolves the second
        msg2 = ChannelMessage(
            session_id="test-session",
            content="second response",
            channel="jsonrpc",
            chat_id="test-session",
        )
        await channel.send(msg2)

        assert future2.done()
        assert future2.result()["result"]["text"] == "second response"
        assert future2.result()["id"] == "req-2"
        assert "test-session" not in channel._pending

    async def test_send_no_pending_is_noop(self) -> None:
        """Channel.send() with no pending future does nothing."""
        channel, _ = _make_channel()
        msg = ChannelMessage(
            session_id="no-such",
            content="x",
            channel="jsonrpc",
            chat_id="no-such",
        )
        await channel.send(msg)  # should not raise


# ─── stream_events() ─────────────────────────────────────────────


class TestStreamEvents:
    async def test_stream_events_wraps_and_pushes_to_queue(self) -> None:
        """stream_events() forwards events to the WS queue."""
        channel, _ = _make_channel()
        queue = asyncio.Queue()
        channel._stream_queues["s1"] = ("req-stream-1", queue)

        events = [
            FakeStreamEvent("text", {"delta": "a"}),
            FakeStreamEvent("text", {"delta": "b"}),
        ]

        async def _gen():
            for e in events:
                yield e

        msg = ChannelMessage(
            session_id="s1", content="", channel="jsonrpc", chat_id="s1",
        )
        collected = []
        async for ev in channel.stream_events(msg, _gen()):
            collected.append(ev)

        assert len(collected) == 2
        assert collected[0].data["delta"] == "a"
        # Queue should have events + sentinel
        q_items = []
        while not queue.empty():
            q_items.append(await queue.get())
        assert len(q_items) == 3  # 2 events + None sentinel
        assert q_items[-1] is None

    async def test_stream_events_no_queue_still_yields(self) -> None:
        """stream_events() yields events even without a WS queue."""
        channel, _ = _make_channel()
        events = [FakeStreamEvent("text", {"delta": "x"})]

        async def _gen():
            for e in events:
                yield e

        msg = ChannelMessage(
            session_id="no-queue", content="", channel="jsonrpc", chat_id="no-queue",
        )
        collected = []
        async for ev in channel.stream_events(msg, _gen()):
            collected.append(ev)
        assert len(collected) == 1


# ─── WS edge cases ──────────────────────────────────────────────


class TestChannelWsEdgeCases:
    async def test_ws_invalid_json(self, channel_client) -> None:
        cli, _, _ = channel_client
        ws = await cli.ws_connect("/ws")
        await ws.send_str("not json")
        resp = await ws.receive_json(timeout=5)
        assert "error" in resp
        assert resp["error"]["code"] == -32700
        await ws.close()

    async def test_ws_method_not_found(self, channel_client) -> None:
        cli, _, _ = channel_client
        ws = await cli.ws_connect("/ws")
        await ws.send_json({
            "jsonrpc": "2.0", "id": "w4",
            "method": "no.such.method",
            "params": {"session_id": "s1"},
        })
        resp = await ws.receive_json(timeout=5)
        assert resp["error"]["code"] == -32601
        await ws.close()

    async def test_ws_multiple_requests(self, channel_client) -> None:
        cli, _, _ = channel_client
        ws = await cli.ws_connect("/ws")
        await ws.send_json({
            "jsonrpc": "2.0", "id": "w5a", "method": "chat.ping", "params": {},
        })
        await ws.send_json({
            "jsonrpc": "2.0", "id": "w5b", "method": "chat.ping", "params": {},
        })
        r1 = await ws.receive_json(timeout=5)
        r2 = await ws.receive_json(timeout=5)
        assert r1["id"] == "w5a"
        assert r2["id"] == "w5b"
        await ws.close()

    async def test_ws_session_get(self, channel_client) -> None:
        cli, _, _ = channel_client
        ws = await cli.ws_connect("/ws")
        await ws.send_json({
            "jsonrpc": "2.0", "id": "w6",
            "method": "session.get", "params": {"session_id": "ws-test"},
        })
        resp = await ws.receive_json(timeout=5)
        assert resp["result"]["session_id"] == "ws-test"
        await ws.close()


# ─── HTTP edge cases ─────────────────────────────────────────────


class TestChannelHttpEdgeCases:
    async def test_empty_body(self, channel_client) -> None:
        cli, _, _ = channel_client
        resp = await cli.post(
            "/rpc", data=b"", headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400

    async def test_wrong_content_type(self, channel_client) -> None:
        cli, _, _ = channel_client
        resp = await cli.post(
            "/rpc", data=b"{}", headers={"Content-Type": "text/plain"},
        )
        assert resp.status == 415

    async def test_session_get(self, channel_client) -> None:
        cli, _, _ = channel_client
        status, body = await _post_rpc(cli, {
            "jsonrpc": "2.0", "id": "c6",
            "method": "session.get", "params": {"session_id": "test-abc"},
        })
        assert status == 200
        assert body["result"]["session_id"] == "test-abc"

    async def test_get_method_rejected(self, channel_client) -> None:
        """Non-POST methods to /rpc return 405."""
        cli, _, _ = channel_client
        resp = await cli.get("/rpc")
        assert resp.status == 405


# ─── Stream with tool calls ─────────────────────────────────────


class TestChannelStreamWithTools:
    async def test_stream_tool_call_events(self) -> None:
        """Streaming with tool_call and tool_result events."""
        events = [
            FakeStreamEvent("text", {"delta": "Let me check"}),
            FakeStreamEvent("tool_call", {"name": "search", "args": {"q": "test"}}),
            FakeStreamEvent("tool_result", {"name": "search", "result": "found"}),
            FakeStreamEvent("text", {"delta": " found it"}),
            FakeStreamEvent("final", {"text": "Let me check found it", "ok": True}),
        ]
        channel, received = _make_channel(events=events)
        _init_app(channel)

        server = TestServer(channel._app)
        async with TestClient(server) as cli:
            ws = await cli.ws_connect("/ws")
            await ws.send_json({
                "jsonrpc": "2.0", "id": "t1",
                "method": "chat.stream",
                "params": {"session_id": "tool-s1", "message": "search"},
            })

            notifications = []
            while True:
                msg = await ws.receive_json(timeout=5)
                if "method" in msg and msg["method"] == "chat.stream.event":
                    notifications.append(msg)
                    if msg["params"]["event"] == "done":
                        break

            events_kind = [n["params"]["event"] for n in notifications]
            assert "token" in events_kind
            assert "tool_call" in events_kind
            assert "tool_result" in events_kind
            assert "done" in events_kind

            tool_call = next(n for n in notifications if n["params"]["event"] == "tool_call")
            assert tool_call["params"]["name"] == "search"
            assert tool_call["params"]["args"] == {"q": "test"}

            await ws.close()

    async def test_stream_error_event(self) -> None:
        """Streaming with an error event."""
        events = [
            FakeStreamEvent("text", {"delta": "partial"}),
            FakeStreamEvent("error", {"message": "model overloaded"}),
            FakeStreamEvent("final", {"text": "partial", "ok": False}),
        ]
        channel, _ = _make_channel(events=events)
        _init_app(channel)

        server = TestServer(channel._app)
        async with TestClient(server) as cli:
            ws = await cli.ws_connect("/ws")
            await ws.send_json({
                "jsonrpc": "2.0", "id": "t2",
                "method": "chat.stream",
                "params": {"session_id": "err-s1", "message": "test"},
            })

            notifications = []
            while True:
                msg = await ws.receive_json(timeout=5)
                if "method" in msg and msg["method"] == "chat.stream.event":
                    notifications.append(msg)
                    if msg["params"]["event"] == "done":
                        break

            error_events = [n for n in notifications if n["params"]["event"] == "error"]
            assert len(error_events) == 1
            assert "overloaded" in error_events[0]["params"]["message"]
            await ws.close()


# ─── Concurrent requests ────────────────────────────────────────


class TestConcurrentRequests:
    async def test_same_session_concurrent_send(self) -> None:
        """Two concurrent chat.send on the same session_id both get resolved."""
        channel, received = _make_channel()
        _init_app(channel)

        server = TestServer(channel._app)
        async with TestClient(server) as cli:
            ws = await cli.ws_connect("/ws")
            # Send two requests with same session_id but different request_ids
            await ws.send_json({
                "jsonrpc": "2.0", "id": "conc-1",
                "method": "chat.send",
                "params": {"session_id": "same-sess", "message": "first"},
            })
            await ws.send_json({
                "jsonrpc": "2.0", "id": "conc-2",
                "method": "chat.send",
                "params": {"session_id": "same-sess", "message": "second"},
            })

            r1 = await ws.receive_json(timeout=5)
            r2 = await ws.receive_json(timeout=5)

            # Both should be resolved, in FIFO order
            assert r1["id"] == "conc-1"
            assert r1["result"]["text"] == "echo: first"
            assert r2["id"] == "conc-2"
            assert r2["result"]["text"] == "echo: second"

            assert len(received) == 2
            await ws.close()

    async def test_same_session_concurrent_http_send(self) -> None:
        """Two concurrent HTTP chat.send on the same session_id."""
        channel, received = _make_channel()
        _init_app(channel)

        server = TestServer(channel._app)
        async with TestClient(server) as cli:
            # Fire two requests concurrently
            import asyncio as _aio

            async def _send(req_id: str, msg: str):
                status, body = await _post_rpc(cli, {
                    "jsonrpc": "2.0", "id": req_id,
                    "method": "chat.send",
                    "params": {"session_id": "http-sess", "message": msg},
                })
                return status, body

            # Use tasks to run concurrently
            t1 = _aio.create_task(_send("h1", "alpha"))
            t2 = _aio.create_task(_send("h2", "beta"))

            s1, b1 = await t1
            s2, b2 = await t2

            assert s1 == 200 and s2 == 200
            # Both resolved (order may vary due to concurrency)
            texts = {b1["result"]["text"], b2["result"]["text"]}
            assert texts == {"echo: alpha", "echo: beta"}
            assert len(received) == 2
            await ws.close() if False else None  # no ws here

    async def test_request_id_not_affected_by_session_reuse(self) -> None:
        """request_id correlation works independently of session_id."""
        channel, _ = _make_channel()
        _init_app(channel)

        server = TestServer(channel._app)
        async with TestClient(server) as cli:
            ws = await cli.ws_connect("/ws")
            # Same session, different request_ids
            for i in range(5):
                await ws.send_json({
                    "jsonrpc": "2.0", "id": f"seq-{i}",
                    "method": "chat.send",
                    "params": {"session_id": "reuse-sess", "message": f"msg-{i}"},
                })

            for i in range(5):
                resp = await ws.receive_json(timeout=5)
                assert resp["id"] == f"seq-{i}"
                assert resp["result"]["text"] == f"echo: msg-{i}"

            await ws.close()

    async def test_same_session_concurrent_stream_rejected(self) -> None:
        """Second chat.stream on same session_id is explicitly rejected.

        Uses two separate WS connections — the first holds the stream open,
        the second attempts to start another stream on the same session.
        """
        channel = JsonRpcChannel(on_receive=lambda msg: None)
        _init_app(channel)

        # on_receive pushes one token, holds stream open (no sentinel)
        async def _hold_on_receive(msg: ChannelMessage) -> None:
            entry = channel._stream_queues.get(msg.session_id)
            if entry is None:
                return
            _rid, queue = entry
            await queue.put(FakeStreamEvent("text", {"delta": "hello"}))
            # No sentinel — stream stays open

        channel._on_receive = _hold_on_receive

        server = TestServer(channel._app)
        async with TestClient(server) as cli:
            # First WS: start stream and read first token
            ws1 = await cli.ws_connect("/ws")
            await ws1.send_json({
                "jsonrpc": "2.0", "id": "stream-1",
                "method": "chat.stream",
                "params": {"session_id": "dup-sess", "message": "first"},
            })
            msg = await ws1.receive_json(timeout=5)
            assert msg["params"]["event"] == "token"

            # Second WS: attempt stream on same session — should be rejected
            ws2 = await cli.ws_connect("/ws")
            await ws2.send_json({
                "jsonrpc": "2.0", "id": "stream-2",
                "method": "chat.stream",
                "params": {"session_id": "dup-sess", "message": "second"},
            })
            resp = await ws2.receive_json(timeout=5)
            assert "error" in resp
            assert resp["error"]["code"] == -32002
            assert "active stream" in resp["error"]["message"]
            assert resp["id"] == "stream-2"

            await ws1.close()
            await ws2.close()

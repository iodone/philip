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
        queue = channel._stream_queues.get(session_id)
        if queue is not None and events is not None:
            for ev in events:
                await queue.put(ev)
            await queue.put(None)
            return

        # Otherwise resolve the pending future (for chat.send).
        # Match what Channel.send() produces: success_response(None, result)
        from philip.server.jsonrpc import success_response

        future = channel._pending.get(session_id)
        if future and not future.done():
            future.set_result(success_response(None, {
                "session_id": session_id,
                "text": "echo: " + msg.content,
                "status": "completed",
            }))

    handler = on_receive or _default_on_receive
    channel = JsonRpcChannel(on_receive=handler)
    return channel, received


async def _start_channel(
    channel: JsonRpcChannel,
) -> tuple[TestServer, TestClient]:
    """Start a channel in a test server and return client."""
    server = TestServer(web.Application())
    # We need to mount the channel's routes on the test server's app
    # Instead, use the channel's own app
    app = channel._app
    if app is None:
        # Manually init the app as start() would
        app = web.Application()
        app.router.add_post("/rpc", channel._handle_rpc)
        app.router.add_route("*", "/rpc", channel._handle_rpc)
        app.router.add_get("/ws", channel._handle_ws)
        channel._app = app

    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    return server, client


@pytest.fixture
async def channel_client():
    """Basic channel client with echo-style responses."""
    channel, received = _make_channel()
    # Init the app manually (skip full start() which binds a real TCP site)
    channel._app = web.Application()
    channel._app.router.add_post("/rpc", channel._handle_rpc)
    channel._app.router.add_route("*", "/rpc", channel._handle_rpc)
    channel._app.router.add_get("/ws", channel._handle_ws)

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
    channel._app = web.Application()
    channel._app.router.add_post("/rpc", channel._handle_rpc)
    channel._app.router.add_route("*", "/rpc", channel._handle_rpc)
    channel._app.router.add_get("/ws", channel._handle_ws)

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

    def test_enabled(self) -> None:
        channel, _ = _make_channel()
        assert channel.enabled is True

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
        # on_receive was called
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
    async def test_send_resolves_pending(self) -> None:
        """Channel.send() resolves a pending future for the session."""
        channel, _ = _make_channel()
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        channel._pending["test-session"] = future

        msg = ChannelMessage(
            session_id="test-session",
            content="response text",
            channel="jsonrpc",
            chat_id="test-session",
        )
        await channel.send(msg)

        result = future.result()
        assert result["result"]["text"] == "response text"
        assert result["result"]["status"] == "completed"
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
        channel._stream_queues["s1"] = queue

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
        # No queue registered for this session

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
        channel._app = web.Application()
        channel._app.router.add_post("/rpc", channel._handle_rpc)
        channel._app.router.add_route("*", "/rpc", channel._handle_rpc)
        channel._app.router.add_get("/ws", channel._handle_ws)

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
        channel._app = web.Application()
        channel._app.router.add_post("/rpc", channel._handle_rpc)
        channel._app.router.add_route("*", "/rpc", channel._handle_rpc)
        channel._app.router.add_get("/ws", channel._handle_ws)

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

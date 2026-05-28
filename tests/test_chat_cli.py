"""Tests for philip chat CLI — JSON-RPC client."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from philip.cli.__main__ import app

runner = CliRunner()


# ─── CLI Registration ────────────────────────────────────────────


class TestChatCommandRegistered:
    def test_chat_inspect(self) -> None:
        result = runner.invoke(app, ["chat", "-h"])
        assert result.exit_code == 0
        assert "chat" in result.output.lower()

    def test_chat_discover(self) -> None:
        result = runner.invoke(app, ["-h"])
        assert result.exit_code == 0
        assert "chat" in result.output


# ─── HTTP Client Flow ────────────────────────────────────────────


class TestHttpChat:
    async def test_http_send_and_receive(self) -> None:
        from philip.cli.chat import _http_chat

        mock_response = AsyncMock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        mock_response.json = AsyncMock(
            return_value={
                "jsonrpc": "2.0",
                "result": {
                    "session_id": "s1",
                    "text": "echo: hello",
                    "status": "completed",
                },
                "id": "cli-1",
            }
        )

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.post = MagicMock(return_value=mock_response)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("philip.cli.chat._read_line", side_effect=["hello", EOFError]):
                await _http_chat("http://localhost:8420/rpc", "s1")

        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[0][0] == "http://localhost:8420/rpc"
        payload = call_args[1]["json"]
        assert payload["method"] == "chat.send"
        assert payload["params"]["session_id"] == "s1"
        assert payload["params"]["message"] == "hello"

    async def test_http_error_response(self) -> None:
        from philip.cli.chat import _http_chat

        mock_response = AsyncMock()
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)
        mock_response.json = AsyncMock(
            return_value={
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": "session_id required"},
                "id": "cli-1",
            }
        )

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.post = MagicMock(return_value=mock_response)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("philip.cli.chat._read_line", side_effect=["hi", EOFError]):
                await _http_chat("http://localhost:8420/rpc", "s1")

    async def test_http_connection_error(self) -> None:
        import aiohttp

        from philip.cli.chat import _http_chat

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.post = MagicMock(side_effect=aiohttp.ClientError("refused"))

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("philip.cli.chat._read_line", side_effect=["hi"]):
                await _http_chat("http://localhost:8420/rpc", "s1")


# ─── WebSocket Client Flow ──────────────────────────────────────


class TestWsChat:
    async def test_ws_send_and_receive(self) -> None:
        from philip.cli.chat import _ws_chat

        mock_ws = AsyncMock()
        mock_ws.receive_json = AsyncMock(
            return_value={
                "jsonrpc": "2.0",
                "result": {
                    "session_id": "s1",
                    "text": "echo: test",
                    "status": "completed",
                },
                "id": "cli-1",
            }
        )
        mock_ws.close = AsyncMock()

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.ws_connect = AsyncMock(return_value=mock_ws)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("philip.cli.chat._read_line", side_effect=["test", EOFError]):
                await _ws_chat("ws://localhost:8420/ws", "s1", False)

        mock_ws.send_json.assert_called_once()
        payload = mock_ws.send_json.call_args[0][0]
        assert payload["method"] == "chat.send"

    async def test_ws_stream_receives_events(self) -> None:
        from philip.cli.chat import _ws_chat

        events = [
            {
                "jsonrpc": "2.0",
                "method": "chat.stream.event",
                "params": {
                    "session_id": "s1",
                    "event": "token",
                    "delta": "Hi",
                },
            },
            {
                "jsonrpc": "2.0",
                "method": "chat.stream.event",
                "params": {
                    "session_id": "s1",
                    "event": "done",
                    "text": "Hi",
                },
            },
            {
                "jsonrpc": "2.0",
                "result": {"session_id": "s1", "text": "Hi", "status": "completed"},
                "id": "cli-1",
            },
        ]

        mock_ws = AsyncMock()
        mock_ws.receive_json = AsyncMock(side_effect=events)
        mock_ws.close = AsyncMock()

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.ws_connect = AsyncMock(return_value=mock_ws)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("philip.cli.chat._read_line", side_effect=["hi", EOFError]):
                await _ws_chat("ws://localhost:8420/ws", "s1", True)

        payload = mock_ws.send_json.call_args[0][0]
        assert payload["method"] == "chat.stream"


# ─── Read Line Helper ────────────────────────────────────────────


class TestReadLine:
    def test_read_line_returns_input(self) -> None:
        from philip.cli.chat import _read_line

        with patch("builtins.input", return_value="hello"):
            assert _read_line() == "hello"

    def test_read_line_raises_eof(self) -> None:
        from philip.cli.chat import _read_line

        with patch("builtins.input", side_effect=EOFError):
            with pytest.raises(EOFError):
                _read_line()


# ─── Local Commands ──────────────────────────────────────────────


class TestLocalCommands:
    def test_help_command(self) -> None:
        from philip.cli.chat import _handle_local_command

        assert _handle_local_command("/help", "s1") is True

    def test_session_command(self) -> None:
        from philip.cli.chat import _handle_local_command

        assert _handle_local_command("/session", "my-sid") is True

    def test_quit_raises(self) -> None:
        from philip.cli.chat import _ExitRepl, _handle_local_command

        with pytest.raises(_ExitRepl):
            _handle_local_command("/quit", "s1")

    def test_exit_raises(self) -> None:
        from philip.cli.chat import _ExitRepl, _handle_local_command

        with pytest.raises(_ExitRepl):
            _handle_local_command("/exit", "s1")

    def test_normal_message_not_handled(self) -> None:
        from philip.cli.chat import _handle_local_command

        assert _handle_local_command("hello world", "s1") is False

    def test_http_repl_with_local_commands(self) -> None:
        from philip.cli.chat import _http_chat

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            with patch("philip.cli.chat._read_line", side_effect=["/session", "/quit"]):
                asyncio.run(_http_chat("http://localhost:8420/rpc", "s1"))

        mock_session.post.assert_not_called()

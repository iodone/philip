"""Tests for JSON-RPC 2.0 envelope parsing and validation."""

from __future__ import annotations

import json

from philip.server.jsonrpc import (
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    JsonRpcError,
    JsonRpcRequest,
    error_response,
    parse_request,
    success_response,
)


class TestParseRequest:
    def test_valid_request(self) -> None:
        raw = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": "req-001",
                "method": "chat.ping",
                "params": {},
            }
        ).encode()
        result = parse_request(raw)
        assert isinstance(result, JsonRpcRequest)
        assert result.method == "chat.ping"
        assert result.id == "req-001"
        assert result.params == {}

    def test_valid_request_no_id(self) -> None:
        raw = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "chat.ping",
            }
        ).encode()
        result = parse_request(raw)
        assert isinstance(result, JsonRpcRequest)
        assert result.id is None
        assert result.params == {}

    def test_valid_request_integer_id(self) -> None:
        raw = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 42,
                "method": "chat.ping",
            }
        ).encode()
        result = parse_request(raw)
        assert isinstance(result, JsonRpcRequest)
        assert result.id == 42

    def test_parse_error_invalid_json(self) -> None:
        result = parse_request(b"not json")
        assert isinstance(result, JsonRpcError)
        assert result.code == PARSE_ERROR

    def test_invalid_request_not_object(self) -> None:
        raw = json.dumps([1, 2, 3]).encode()
        result = parse_request(raw)
        assert isinstance(result, JsonRpcError)
        assert result.code == INVALID_REQUEST

    def test_invalid_request_wrong_version(self) -> None:
        raw = json.dumps(
            {
                "jsonrpc": "1.0",
                "method": "chat.ping",
            }
        ).encode()
        result = parse_request(raw)
        assert isinstance(result, JsonRpcError)
        assert result.code == INVALID_REQUEST
        assert "2.0" in result.message

    def test_invalid_request_missing_method(self) -> None:
        raw = json.dumps(
            {
                "jsonrpc": "2.0",
                "params": {},
            }
        ).encode()
        result = parse_request(raw)
        assert isinstance(result, JsonRpcError)
        assert result.code == INVALID_REQUEST

    def test_invalid_request_empty_method(self) -> None:
        raw = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "",
            }
        ).encode()
        result = parse_request(raw)
        assert isinstance(result, JsonRpcError)
        assert result.code == INVALID_REQUEST

    def test_invalid_request_params_not_object(self) -> None:
        raw = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "chat.ping",
                "params": "bad",
            }
        ).encode()
        result = parse_request(raw)
        assert isinstance(result, JsonRpcError)
        assert result.code == INVALID_REQUEST

    def test_null_params_treated_as_empty(self) -> None:
        raw = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "chat.ping",
                "params": None,
            }
        ).encode()
        result = parse_request(raw)
        assert isinstance(result, JsonRpcRequest)
        assert result.params == {}


class TestResponses:
    def test_success_response(self) -> None:
        resp = success_response("req-001", {"pong": True})
        assert resp == {
            "jsonrpc": "2.0",
            "result": {"pong": True},
            "id": "req-001",
        }

    def test_error_response(self) -> None:
        resp = error_response("req-001", METHOD_NOT_FOUND, "nope")
        assert resp["jsonrpc"] == "2.0"
        assert resp["error"]["code"] == METHOD_NOT_FOUND
        assert resp["error"]["message"] == "nope"
        assert resp["id"] == "req-001"

    def test_error_response_with_data(self) -> None:
        resp = error_response(None, PARSE_ERROR, "bad", data={"line": 1})
        assert resp["error"]["data"] == {"line": 1}
        assert resp["id"] is None

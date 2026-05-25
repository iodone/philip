"""JSON-RPC 2.0 envelope parsing and validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

JSONRPC_VERSION = "2.0"

# Standard error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# Application-defined error codes
MISSING_SESSION_ID = -32000


@dataclass(frozen=True)
class JsonRpcRequest:
    """Parsed and validated JSON-RPC 2.0 request."""

    method: str
    params: dict[str, Any]
    id: str | int | None = None


@dataclass(frozen=True)
class JsonRpcError:
    """JSON-RPC 2.0 error response body."""

    code: int
    message: str
    data: Any = None
    id: str | int | None = None

    def to_dict(self) -> dict[str, Any]:
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            error["data"] = self.data
        return {
            "jsonrpc": JSONRPC_VERSION,
            "error": error,
            "id": self.id,
        }


def parse_request(raw: bytes) -> JsonRpcRequest | JsonRpcError:
    """Parse raw bytes into a JsonRpcRequest, or return an error."""
    import json

    try:
        body = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        return JsonRpcError(
            code=PARSE_ERROR,
            message=f"Parse error: {exc}",
        )

    if not isinstance(body, dict):
        return JsonRpcError(
            code=INVALID_REQUEST,
            message="Request must be a JSON object",
        )

    # Validate jsonrpc version
    version = body.get("jsonrpc")
    if version != JSONRPC_VERSION:
        return JsonRpcError(
            code=INVALID_REQUEST,
            message=f"jsonrpc must be \"{JSONRPC_VERSION}\"",
            id=body.get("id"),
        )

    # Validate method
    method = body.get("method")
    if not isinstance(method, str) or not method:
        return JsonRpcError(
            code=INVALID_REQUEST,
            message="method must be a non-empty string",
            id=body.get("id"),
        )

    # Validate params (must be dict if present)
    params = body.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return JsonRpcError(
            code=INVALID_REQUEST,
            message="params must be an object",
            id=body.get("id"),
        )

    return JsonRpcRequest(
        method=method,
        params=params,
        id=body.get("id"),
    )


def success_response(request_id: str | int | None, result: Any) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 success response."""
    return {
        "jsonrpc": JSONRPC_VERSION,
        "result": result,
        "id": request_id,
    }


def error_response(
    request_id: str | int | None,
    code: int,
    message: str,
    data: Any = None,
) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 error response."""
    return JsonRpcError(code=code, message=message, data=data, id=request_id).to_dict()

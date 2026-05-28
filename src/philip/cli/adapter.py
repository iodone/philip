"""PhilipAdapter — rub adapter aggregating all philip operations."""

from __future__ import annotations

from typing import Any

from rub.adapter import Adapter, ExecutionResult
from rub.schema import Operation, OperationDetail

from philip.cli import chat
from philip.cli.wiki import (
    _EXECUTE as _WIKI_EXECUTE,
)
from philip.cli.wiki import (
    DETAILS as _WIKI_DETAILS,
)
from philip.cli.wiki import (
    OPERATIONS as _WIKI_OPS,
)

# ---------------------------------------------------------------------------
# Aggregated declarations
# ---------------------------------------------------------------------------

_ALL_OPERATIONS: list[Operation] = [*chat.OPERATIONS, *_WIKI_OPS]

_ALL_DETAILS: dict[str, OperationDetail] = {**chat.DETAILS, **_WIKI_DETAILS}

# operation_id → (is_async, execute_fn)
_DISPATCH: dict[str, tuple[bool, Any]] = {}
for op in chat.OPERATIONS:
    _DISPATCH[op.operation_id] = (True, chat.execute)
for op_id, fn in _WIKI_EXECUTE.items():
    _DISPATCH[op_id] = (False, fn)


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class PhilipAdapter(Adapter):
    """Rub adapter for philip — agent-native tooling hub."""

    _priority = 100

    async def protocol_name(self) -> str:
        return "philip"

    async def priority(self) -> int:
        return 100

    async def can_handle(self, url: str) -> bool:
        return url.startswith("philip://")

    async def list_operations(self, url: str) -> list[Operation]:
        return _ALL_OPERATIONS

    async def describe_operation(self, url: str, op_id: str) -> OperationDetail:
        if op_id in _ALL_DETAILS:
            return _ALL_DETAILS[op_id]
        for op in _ALL_OPERATIONS:
            if op.operation_id == op_id:
                return OperationDetail(
                    operation_id=op.operation_id,
                    display_name=op.display_name,
                    description=op.description,
                    parameters=op.parameters,
                )
        from rub.errors import OperationNotFoundError

        raise OperationNotFoundError(f"Operation '{op_id}' not found")

    async def execute(
        self,
        url: str,
        op_id: str,
        args: dict[str, Any],
        *,
        auth_headers: dict[str, str] | None = None,
    ) -> ExecutionResult:
        entry = _DISPATCH.get(op_id)
        if entry is None:
            from rub.errors import OperationNotFoundError

            raise OperationNotFoundError(f"Operation '{op_id}' not found")

        is_async, fn = entry
        if is_async:
            return await fn(args)
        return fn(args)
